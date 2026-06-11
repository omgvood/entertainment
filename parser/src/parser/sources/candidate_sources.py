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

from ..config import load_seeds

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

_JSONLD_EVENT_RE = re.compile(r'"@type"\s*:\s*"[^"]*Event"')


class SearchProvider(ABC):
    """Интерфейс поисковика. Возвращает список URL-результатов по запросу."""

    @abstractmethod
    async def search(self, query: str) -> list[str]: ...


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo HTML endpoint — без ключа. Для MVP; нестабилен под нагрузкой."""

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
            log.warning("candidate.search.failed", query=query, error=str(exc))
            return []

        urls: list[str] = []
        tree = HTMLParser(resp.text)
        for a in tree.css("a.result__a"):
            href = a.attributes.get("href")
            if href:
                urls.append(_unwrap_ddg(href))
        return urls


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
    provider: SearchProvider,
    client: httpx.AsyncClient,
    city_slug: str,
    skip_domains: set[str],
) -> list[Candidate]:
    """Гоняет запросы, агрегирует по домену и считает score."""
    city_name = CITY_NAMES.get(city_slug, city_slug)
    by_domain: dict[str, Candidate] = {}

    for template in QUERY_TEMPLATES:
        query = template.format(city=city_name)
        urls = await provider.search(query)
        for url in urls:
            domain = _domain_of(url)
            if not domain or domain in skip_domains or domain in _IGNORE_DOMAINS:
                continue
            cand = by_domain.setdefault(domain, Candidate(domain=domain, city=city_slug))
            cand.queries.add(query)
            if len(cand.sample_urls) < 5:
                cand.sample_urls.append(url)

    for cand in by_domain.values():
        await _score_candidate(client, cand)

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
            "score": cand.score,
            "has_jsonld_event": cand.has_jsonld_event,
            "last_seen": now,
        }
        if existing:
            # статус не трогаем (могли уже approved/rejected), found_at не трогаем
            client.table("candidate_sources").update(payload).eq(
                "domain", cand.domain
            ).execute()
        else:
            payload["status"] = "new"
            payload["found_at"] = now
            client.table("candidate_sources").insert(payload).execute()
        written += 1
    return written


async def discover_sources(
    city_slug: str,
    supabase: Client | None,
    *,
    dry_run: bool = False,
) -> list[Candidate]:
    """Главная точка входа CLI-команды discover-sources."""
    skip = _known_domains(city_slug)
    if supabase is not None:
        skip |= _rejected_domains(supabase, city_slug)

    async with httpx.AsyncClient(
        headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
    ) as client:
        provider = DuckDuckGoProvider(client)
        candidates = await collect_candidates(provider, client, city_slug, skip)

    if not dry_run and supabase is not None:
        written = save_candidates(supabase, candidates)
        log.info("candidate.saved", city=city_slug, count=written)

    return candidates
