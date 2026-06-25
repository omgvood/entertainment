"""Discovery новых источников (подсистема Discovery).

Поиск по типовым запросам → скоринг кандидатов → запись в candidate_sources
для ручной модерации (new → approved → seeds.yaml / rejected).

Провайдер поиска вынесен за интерфейс SearchProvider, чтобы DuckDuckGo (MVP, без ключа)
можно было заменить на Serper API без изменения остального кода.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import structlog
from selectolax.parser import HTMLParser
from supabase import Client

from ..config import Settings, load_seeds

log = structlog.get_logger()


# Город-slug → именительный падеж для поисковых запросов.
CITY_NAMES = {"perm": "Пермь", "sochi": "Сочи"}

# Шаблоны запросов: покрываем слабые категории (стендап/мастер-классы/детям) и общую афишу.
QUERY_TEMPLATES = [
    "квиз {city}",
    "стендап {city}",
    "мастер-класс {city}",
    "детские мероприятия {city}",
    "афиша {city}",
]

# Пути, характерные для страниц с событиями — дают бонус к скорингу.
_EVENT_PATH_HINTS = ("/events", "/afisha", "/schedule", "/event", "/poster")

# Домены-агрегаторы/соцсети/поисковики — не кандидаты в источники.
_IGNORE_DOMAINS = {
    "vk.com", "ok.ru", "t.me", "telegram.me", "youtube.com", "youtu.be",
    "instagram.com", "facebook.com", "dzen.ru", "yandex.ru", "google.com",
    "duckduckgo.com", "wikipedia.org", "2gis.ru", "avito.ru",
}

# Сила штрафа Discovery для агрегаторов. Именованная константа — изменение однострочное.
# Не меньше суммы двух сильнейших структурных бонусов (JSON-LD +3, event-path +2 = 5),
# иначе хорошо размеченный агрегатор обгонит локального организатора с теми же сигналами.
_AGGREGATOR_PENALTY = 5

# Федеральные агрегаторы и билетные платформы. В отличие от _IGNORE_DOMAINS, НЕ исключаются
# из обработки — остаются кандидатами, но с пониженным скором (виден в discovery-health и
# при модерации). Домены добавляются вручную по факту появления в Discovery-логах
# (candidate.aggregator_penalty), если:
#   1. являются федеральными агрегаторами (не первоисточниками событий);
#   2. регулярно появляются в Discovery и занимают место локальных организаторов.
# timepad.ru здесь временно: _known_domains() не ловит direct_api без url в seeds.
# После внедрения SourceConfig.domain должен уйти из этого списка.
_AGGREGATOR_PENALTY_DOMAINS = {
    "afisha.ru",
    "ticketland.ru",
    "kassir.ru",
    "timepad.ru",
}

_JSONLD_EVENT_RE = re.compile(r'"@type"\s*:\s*"[^"]*Event"')

# Известные провайдеры (валидация SEARCH_PROVIDERS).
_KNOWN_PROVIDERS = {"serper", "brave", "duckduckgo"}

# После скольких подряд отказов (5xx/сеть) провайдер отключается до конца прогона.
_MAX_CONSECUTIVE_FAILURES = 3


class SearchProvider(ABC):
    """Интерфейс поисковика. Возвращает список URL-результатов по запросу."""

    name: str
    """Человекочитаемое имя для логов/метрик (не зависит от имени класса)."""

    @abstractmethod
    async def search(self, query: str) -> list[str]: ...


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo HTML endpoint — без ключа. Для MVP; нестабилен под нагрузкой.

    ⚠️ С 2026-06 эндпоинт отдаёт HTTP 202 (антибот) → 0 результатов. Оставлен как
    последний резерв; основной путь — keyed-провайдеры (Serper/Brave).
    """

    name = "duckduckgo"
    URL = "https://html.duckduckgo.com/html/"

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def search(self, query: str) -> list[str]:
        try:
            resp = await self.client.post(
                self.URL, data={"q": query}, timeout=20.0, follow_redirects=True
            )
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            log.warning("candidate.search.failed", query=query, provider=self.name, error=str(exc))
            return []

        urls: list[str] = []
        tree = HTMLParser(resp.text)
        for a in tree.css("a.result__a"):
            href = a.attributes.get("href")
            if href:
                urls.append(_unwrap_ddg(href))
        return urls


class SerperProvider(SearchProvider):
    """Google Search через Serper API (https://serper.dev) — keyed, основной провайдер.

    Circuit breaker: 401/403 (битый ключ) или 3 подряд 5xx/сетевых отказа отключают
    провайдер до конца прогона. 429 (rate limit) — временно, без отключения.
    """

    name = "serper"
    URL = "https://google.serper.dev/search"

    def __init__(self, client: httpx.AsyncClient, api_key: str, timeout: float) -> None:
        self.client = client
        self.api_key = api_key
        self.timeout = timeout
        self._disabled = False
        self._consecutive_failures = 0

    async def search(self, query: str) -> list[str]:
        if self._disabled:
            return []
        try:
            resp = await self.client.post(
                self.URL,
                json={"q": query, "gl": "ru", "hl": "ru", "num": 10},
                headers={"X-API-KEY": self.api_key},
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("candidate.search.failed", query=query, provider=self.name, error=str(exc))
            self._note_failure()
            return []

        if resp.status_code in (401, 403):
            log.error("candidate.search.auth_failed", provider=self.name, status=resp.status_code)
            self._disabled = True
            return []
        if resp.status_code == 429:
            log.warning("candidate.search.rate_limited", provider=self.name)
            return []
        if resp.status_code >= 500:
            log.warning("candidate.search.server_error", provider=self.name, status=resp.status_code)
            self._note_failure()
            return []

        try:
            data = resp.json()
        except ValueError:
            log.warning("candidate.search.bad_json", provider=self.name)
            self._note_failure()
            return []

        self._consecutive_failures = 0
        return [item["link"] for item in data.get("organic", []) if item.get("link")]

    def _note_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
            log.error("candidate.search.disabled", provider=self.name,
                      failures=self._consecutive_failures)
            self._disabled = True


class BraveProvider(SearchProvider):
    """Brave Search API (https://brave.com/search/api) — keyed, резервный провайдер.

    Та же логика circuit breaker, что у Serper.
    """

    name = "brave"
    URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, client: httpx.AsyncClient, api_key: str, timeout: float) -> None:
        self.client = client
        self.api_key = api_key
        self.timeout = timeout
        self._disabled = False
        self._consecutive_failures = 0

    async def search(self, query: str) -> list[str]:
        if self._disabled:
            return []
        try:
            resp = await self.client.get(
                self.URL,
                params={"q": query, "count": 10, "country": "ru", "search_lang": "ru"},
                headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                timeout=self.timeout,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("candidate.search.failed", query=query, provider=self.name, error=str(exc))
            self._note_failure()
            return []

        if resp.status_code in (401, 403):
            log.error("candidate.search.auth_failed", provider=self.name, status=resp.status_code)
            self._disabled = True
            return []
        if resp.status_code == 429:
            log.warning("candidate.search.rate_limited", provider=self.name)
            return []
        if resp.status_code >= 500:
            log.warning("candidate.search.server_error", provider=self.name, status=resp.status_code)
            self._note_failure()
            return []

        try:
            data = resp.json()
        except ValueError:
            log.warning("candidate.search.bad_json", provider=self.name)
            self._note_failure()
            return []

        self._consecutive_failures = 0
        results = data.get("web", {}).get("results", [])
        return [r["url"] for r in results if r.get("url")]

    def _note_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
            log.error("candidate.search.disabled", provider=self.name,
                      failures=self._consecutive_failures)
            self._disabled = True


def build_search_providers(
    settings: Settings, client: httpx.AsyncClient
) -> list[SearchProvider]:
    """Строит цепочку провайдеров из settings.search_providers (порядок = приоритет).

    Keyed-провайдеры добавляются только при наличии ключа. DuckDuckGo — последний
    резерв (заблокирован, см. класс). Неизвестные имена пропускаются с предупреждением.
    """
    providers: list[SearchProvider] = []
    timeout = settings.search_timeout_seconds
    for raw in settings.search_providers.split(","):
        name = raw.strip().lower()
        if not name:
            continue
        if name not in _KNOWN_PROVIDERS:
            log.warning("candidate.unknown_provider", name=name)
            continue
        if name == "serper" and settings.serper_api_key:
            providers.append(SerperProvider(client, settings.serper_api_key, timeout))
        elif name == "brave" and settings.brave_api_key:
            providers.append(BraveProvider(client, settings.brave_api_key, timeout))
        elif name == "duckduckgo":
            if providers:
                log.warning("candidate.duckduckgo_fallback", msg="DuckDuckGo может быть заблокирован")
            providers.append(DuckDuckGoProvider(client))
    if not providers:
        log.error("candidate.no_provider", msg="нет доступных провайдеров (проверь ключи/SEARCH_PROVIDERS)")
    return providers


async def _search_with_fallback(
    providers: list[SearchProvider], query: str
) -> tuple[list[str], str]:
    """Пробует провайдеры по очереди, возвращает (urls, имя_провайдера).

    Fallback срабатывает только при пустом результате (ошибка/блок/0 результатов),
    а не по их числу — два релевантных результата лучше десяти мусорных от запасного.
    """
    for provider in providers:
        results = await provider.search(query)
        if results:
            return results, provider.name
    return [], "none"


def _unwrap_ddg(href: str) -> str:
    """DuckDuckGo оборачивает ссылки в /l/?uddg=<real>. Достаём настоящий URL."""
    parsed = urlparse(href)
    if parsed.path.endswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return uddg[0]
    return href


@dataclass
class Candidate:
    domain: str
    city: str
    queries: set[str] = field(default_factory=set)
    sample_urls: list[str] = field(default_factory=list)
    score: int = 0
    has_jsonld_event: bool = False
    first_provider: str = ""
    """Провайдер, первым нашедший домен (для аналитики вклада поисковиков)."""
    first_query: str = ""
    """Запрос, по которому домен найден впервые (для тюнинга шаблонов)."""


def _domain_of(url: str) -> str | None:
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc or None


def _known_domains(city_slug: str) -> set[str]:
    """Домены, уже описанные в seeds.yaml для города — их в кандидаты не берём."""
    cities = load_seeds()
    city = cities.get(city_slug)
    domains: set[str] = set()
    if not city:
        return domains
    for s in city.sources:
        if s.url:
            d = _domain_of(s.url)
            if d:
                domains.add(d)
    return domains


def _rejected_domains(client: Client, city_slug: str) -> set[str]:
    resp = (
        client.table("candidate_sources")
        .select("domain")
        .eq("city", city_slug)
        .eq("status", "rejected")
        .execute()
    )
    return {r["domain"] for r in resp.data}


async def collect_candidates(
    providers: list[SearchProvider],
    client: httpx.AsyncClient,
    city_slug: str,
    skip_domains: set[str],
    *,
    query_limit: int | None = None,
) -> list[Candidate]:
    """Гоняет запросы через цепочку провайдеров, агрегирует по домену и считает score."""
    city_name = CITY_NAMES.get(city_slug, city_slug)
    by_domain: dict[str, Candidate] = {}
    provider_stats: dict[str, dict[str, int]] = {}
    limit = query_limit or len(QUERY_TEMPLATES)
    queries_executed = 0

    for template in QUERY_TEMPLATES:
        if queries_executed >= limit:
            log.warning("candidate.query_limit_reached", limit=limit)
            break
        query = template.format(city=city_name)
        urls, provider_name = await _search_with_fallback(providers, query)
        queries_executed += 1
        stats = provider_stats.setdefault(provider_name, {"queries": 0, "domains": 0})
        stats["queries"] += 1
        log.info("candidate.search.stats", query=query, provider=provider_name, results=len(urls))

        for url in urls:
            domain = _domain_of(url)
            if not domain or domain in skip_domains or domain in _IGNORE_DOMAINS:
                continue
            cand = by_domain.get(domain)
            if cand is None:  # первое обнаружение домена
                cand = Candidate(domain=domain, city=city_slug)
                cand.first_provider = provider_name
                cand.first_query = query
                by_domain[domain] = cand
                stats["domains"] += 1
                log.info("candidate.discovered", domain=domain, provider=provider_name, query=query)
            cand.queries.add(query)
            if len(cand.sample_urls) < 5:
                cand.sample_urls.append(url)

    for cand in by_domain.values():
        await _score_candidate(client, cand)

    scores = [c.score for c in by_domain.values()]
    log.info(
        "candidate.provider.summary",
        city=city_slug,
        stats=provider_stats,
        total_unique_domains=len(by_domain),
        avg_score=round(sum(scores) / len(scores), 1) if scores else 0,
        score_ge_7=sum(1 for s in scores if s >= 7),
    )
    log.info(
        "candidate.search.cost",
        city=city_slug,
        total_queries=queries_executed,
        per_provider={k: v["queries"] for k, v in provider_stats.items()},
    )

    return sorted(by_domain.values(), key=lambda c: c.score, reverse=True)


async def _score_candidate(client: httpx.AsyncClient, cand: Candidate) -> None:
    # +1 за каждый дополнительный запрос, в котором встретился домен
    cand.score += len(cand.queries) - 1
    # +2 если в путях есть событийные маркеры
    if any(any(h in u.lower() for h in _EVENT_PATH_HINTS) for u in cand.sample_urls):
        cand.score += 2
    # +3 если на странице найден JSON-LD типа Event
    if cand.sample_urls:
        try:
            resp = await client.get(
                cand.sample_urls[0], timeout=15.0, follow_redirects=True
            )
            if resp.status_code == 200 and _JSONLD_EVENT_RE.search(resp.text):
                cand.has_jsonld_event = True
                cand.score += 3
        except Exception:  # noqa: BLE001
            pass

    # Штраф агрегаторам — применяется ПОСЛЕДНИМ, после всех начислений: иначе любой бонус,
    # добавленный выше в будущем, нивелирует эффект. endswith ловит поддомены (perm.afisha.ru),
    # без ложных совпадений (myafisha.ru не оканчивается на .afisha.ru).
    if any(
        cand.domain == d or cand.domain.endswith("." + d)
        for d in _AGGREGATOR_PENALTY_DOMAINS
    ):
        score_before = cand.score
        cand.score -= _AGGREGATOR_PENALTY
        log.info(
            "candidate.aggregator_penalty",
            domain=cand.domain,
            score_before=score_before,
            score_after=cand.score,
            penalty=_AGGREGATOR_PENALTY,
        )


def save_candidates(client: Client, candidates: list[Candidate]) -> int:
    """Upsert кандидатов с сохранением status (модерация). Возвращает число записанных."""
    if not candidates:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    written = 0
    for cand in candidates:
        existing = (
            client.table("candidate_sources")
            .select("queries,status")
            .eq("domain", cand.domain)
            .limit(1)
            .execute()
            .data
        )
        merged_queries = set(cand.queries)
        if existing:
            merged_queries |= set(existing[0].get("queries") or [])
        payload = {
            "domain": cand.domain,
            "city": cand.city,
            "queries": sorted(merged_queries),
            "sample_urls": cand.sample_urls,
            "score": cand.score,
            "has_jsonld_event": cand.has_jsonld_event,
            "last_seen": now,
        }
        if existing:
            # статус не трогаем (могли уже approved/rejected), found_at/first_* не трогаем
            client.table("candidate_sources").update(payload).eq(
                "domain", cand.domain
            ).execute()
        else:
            payload["status"] = "new"
            payload["found_at"] = now
            payload["first_provider"] = cand.first_provider
            payload["first_query"] = cand.first_query
            client.table("candidate_sources").insert(payload).execute()
        written += 1
    return written


async def discover_sources(
    city_slug: str,
    supabase: Client | None,
    *,
    settings: Settings | None = None,
    dry_run: bool = False,
) -> list[Candidate]:
    """Главная точка входа CLI-команды discover-sources."""
    if settings is None:
        settings = Settings.from_env()

    skip = _known_domains(city_slug)
    if supabase is not None:
        skip |= _rejected_domains(supabase, city_slug)

    async with httpx.AsyncClient(
        headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
    ) as client:
        providers = build_search_providers(settings, client)
        candidates = await collect_candidates(
            providers, client, city_slug, skip, query_limit=settings.search_query_limit
        )

    if not candidates:
        log.error("candidate.discovery_empty", city=city_slug,
                  msg="0 кандидатов — Discovery не работает или провайдеры заблокированы")

    if not dry_run and supabase is not None:
        written = save_candidates(supabase, candidates)
        log.info("candidate.saved", city=city_slug, count=written)
        if candidates and written == 0:
            log.warning("candidate.discovery_no_new", city=city_slug,
                        msg="кандидаты найдены, но новых нет (все уже в БД)")

    return candidates
