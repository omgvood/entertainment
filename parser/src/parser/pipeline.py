"""Оркестратор. Два режима:
- per_url:        discovery → dedup → fetch per URL → LLM extract per URL → write
- batch_listing:  fetch listing URL → LLM extract_many (1 вызов) → write
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date as _date, datetime, timezone

import httpx
import structlog
from supabase import Client

from .classifiers import is_event_candidate
from .config import CityConfig, SourceConfig
from .db import (
    WriteStats,
    cleanup_old_events,
    cleanup_old_raw_documents,
    fetch_events_by_ids,
    get_raw_document_hash,
    record_coverage,
    record_source_health,
    record_source_quality,
    save_raw_document,
    sync_source_events,
    upsert_events,
    upsert_venues,
)
from .dedup import filter_new_urls
from .discovery import DiscoveredUrl, ListingDiscovery, SitemapDiscovery
from .extraction import ExtractorError, LLMExtractor, extract_jsonld_events
from .merge import merge_rows
from .models import EventRow, EventType, ParsedEvent, Venue
from .sources import KudaGoClient, QuizPleaseClient, TelegramHtmlProvider, TimepadClient, TwoGisClient, VkClient
from .sources import vk as vk_mod
from .sources.generic import run_generic
from .url_utils import resolve_event_url
from .validator import to_event_row, to_venue


log = structlog.get_logger()

# Параллелизм LLM-вызовов при чанковой обработке VK/TG (защита от RPM-лимитов провайдеров).
# Батч 5 постов × 2 параллельных вызова = ≤10 постов в полёте — мягче бьёт по RPM.
_POST_CONCURRENCY = 2


def _chunks(seq: list, size: int):
    """Разбивает список на пачки по size элементов."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _hash_html(html: str, *, playwright: bool = False) -> str:
    """SHA-256 контента листинга для дедупа неизменных прогонов (raw_documents).

    Для статических страниц (playwright=False) хешируем сырой HTML — он стабилен между
    прогонами. Для SPA (playwright=True) — нельзя: Nuxt/Next встраивают в DOM динамические
    блоки (`<script id="__NUXT_DATA__">` с токенами/таймстампами, рандомизированные классы
    гидратации), и хеш сырого HTML «мигал» бы каждый прогон → лишние LLM-вызовы. Поэтому
    структурно вычищаем не-контентные теги через selectolax и хешируем только нормализованный
    видимый текст: он меняется ровно тогда, когда меняется состав афиши.
    """
    if not playwright:
        return hashlib.sha256(html.encode("utf-8")).hexdigest()

    from selectolax.parser import HTMLParser

    tree = HTMLParser(html)
    for tag in tree.css("script, style, meta, link, input[type='hidden'], template"):
        tag.decompose()
    body = tree.body
    if body is not None:
        text = body.text(deep=True, strip=True)
        text = re.sub(r"\s+", " ", text).strip()
    else:
        text = html
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _extract_chunk(
    extractor: LLMExtractor,
    posts: list[tuple[str, str]],
    base_url: str,
    sem: asyncio.Semaphore,
) -> tuple[list[ParsedEvent], list[tuple[str, str]]]:
    """Пачка постов → один LLM-вызов. Каждый пост помечается маркером «=== POST <url> ===»
    (промпты обязаны брать из него event_url). base_url = группа/канал — фолбэк атрибуции.

    Возвращает (события, posts) — posts нужны вызывающему, чтобы пометить их обработанными
    в raw_documents (в success-ветке, включая пустой результат)."""
    async with sem:
        # text.strip() + пропуск пустых: дешёвая страховка (префильтр уже отсеял не-события).
        chunk_doc = "\n\n".join(
            f"=== POST {url} ===\n{t}" for url, text in posts if (t := text.strip())
        )
        if not chunk_doc.strip():
            log.debug("extract.skip_empty_chunk", base_url=base_url)
            return [], posts
        events = await extractor.extract_many(chunk_doc, base_url)
        return events, posts


def _is_past_event(event_date: str, today_str: str) -> bool:
    """True, если дата события строго раньше сегодня — отсев репортажей о прошедшем.

    'always' (постоянные места) и невалидные строки прошлыми не считаются: дату
    валидирует Pydantic при сборке ParsedEvent, ValueError здесь — лишь подстраховка.
    """
    if event_date == "always":
        return False
    try:
        return _date.fromisoformat(event_date) < _date.fromisoformat(today_str)
    except ValueError:
        return False


@dataclass
class PipelineResult:
    discovered: int = 0
    new: int = 0
    extracted: int = 0
    failed: int = 0
    written: int = 0
    duplicate_candidates: int = 0
    merged: int = 0
    near_misses: int = 0
    merged_by_source: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.merged_by_source is None:
            self.merged_by_source = {}


def _make_discovery(client: httpx.AsyncClient, source: SourceConfig):
    if source.kind == "listing":
        if not source.url_pattern:
            raise ValueError(f"listing-источник {source.name} требует url_pattern")
        return ListingDiscovery(client, source.name, source.url, source.url_pattern)
    if source.kind == "sitemap":
        return SitemapDiscovery(client, source.name, source.url, source.url_pattern)
    raise ValueError(f"Неизвестный kind={source.kind!r} для {source.name}")


async def run_city(
    city: CityConfig,
    extractor: LLMExtractor,
    supabase: Client | None,
    *,
    dry_run: bool = False,
    only_source: str | None = None,
    twogis_api_key: str | None = None,
    timepad_token: str | None = None,
    vk_service_key: str | None = None,
    generic_llm_budget: int = 10,
    generic_domain_budget: int = 20,
    post_batch_size: int = 5,
    mode_override: str | None = None,
) -> PipelineResult:
    """Полный прогон по одному городу. supabase=None при --dry-run.

    mode_override: если задан, переопределяет extraction_mode для ВСЕХ источников этого
    прогона (per_url / batch_listing / direct_api) — для разовых сравнений провайдеров.
    """
    result = PipelineResult()
    provider_keys = {"twogis": twogis_api_key, "timepad": timepad_token}
    priorities = {s.name: s.priority for s in city.sources}

    async with httpx.AsyncClient(
        headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
    ) as client:
        all_rows: list[EventRow] = []

        for source in city.sources:
            if not source.enabled:
                log.info("source.disabled", source=source.name)
                continue
            if only_source and source.name != only_source:
                continue
            mode = mode_override or source.extraction_mode
            started = time.perf_counter()
            if mode == "batch_listing":
                rows, sub = await _run_batch_source(
                    client, source, extractor, supabase, city.slug, dry_run
                )
            elif mode == "playwright_listing":
                rows, sub = await _run_batch_source(
                    client, source, extractor, supabase, city.slug, dry_run,
                    use_playwright=True,
                )
            elif mode == "direct_api":
                rows, sub = await _run_direct_api_source(
                    client, source, supabase, city.slug, provider_keys, dry_run
                )
            elif mode == "vk_events":
                rows, sub = await _run_vk_events_source(
                    client, source, city.slug, vk_service_key
                )
            elif mode == "vk_posts":
                rows, sub = await _run_vk_posts_source(
                    client, source, extractor, supabase, city.slug, vk_service_key, dry_run,
                    post_batch_size,
                )
            elif mode == "telegram_posts":
                rows, sub = await _run_telegram_posts_source(
                    client, source, extractor, supabase, city.slug, dry_run, post_batch_size
                )
            elif mode == "generic":
                rows, sub = await _run_generic_source(
                    client, extractor, supabase, city.slug,
                    generic_llm_budget, generic_domain_budget,
                )
            else:
                rows, sub = await _run_per_url_source(
                    client, source, extractor, supabase, city.slug, dry_run
                )
            duration = time.perf_counter() - started
            if source.full_snapshot and not dry_run and supabase is not None and rows:
                sync_source_events(supabase, source.name, city.slug, {r.id for r in rows})
            all_rows.extend(rows)
            result.discovered += sub.discovered
            result.new += sub.new
            result.extracted += sub.extracted
            result.failed += sub.failed

            if not dry_run and supabase is not None:
                record_source_health(
                    supabase,
                    source.name,
                    city.slug,
                    events_found=sub.extracted,
                    errors=sub.failed,
                    duration_sec=duration,
                )

        # 4. Кросс-источниковый merge по id (= city+slug). Несколько источников с одинаковым
        # title+date дают одинаковый id — схлопываем в победителя по priority, обогащая его
        # пустые поля из проигравших. existing из БД участвуют, чтобы (а) сохранять данные
        # прошлых прогонов и (б) не даунгрейдить карточку источником с меньшим priority.
        existing: list[EventRow] = []
        if not (dry_run or supabase is None):
            existing = fetch_events_by_ids(supabase, [r.id for r in all_rows])
        extracted_by_source = Counter(r.source for r in all_rows)
        merge = merge_rows(all_rows, existing, priorities)
        all_rows = merge.rows_to_upsert
        result.merged = merge.merged
        result.near_misses = merge.near_misses
        result.merged_by_source = merge.merged_by_source
        result.duplicate_candidates = merge.merged  # обратная совместимость поля
        if merge.merged or merge.near_misses:
            log.info(
                "dedup.merge",
                merged=merge.merged,
                near_misses=merge.near_misses,
                by_source=merge.merged_by_source,
            )

        # 5. Write. Слияние делит id, поэтому upsert по slug перезаписывает карточку на месте —
        # отдельных удалений не требуется.
        if dry_run or supabase is None:
            log.info("write.skipped", reason="dry-run", would_write=len(all_rows))
        else:
            stats: WriteStats = upsert_events(supabase, all_rows)
            result.written = stats.inserted
            cleanup_old_events(supabase, city.slug)
            cleanup_old_raw_documents(supabase)
            record_coverage(supabase, city.slug)
            record_source_quality(
                supabase, city.slug, _source_quality(extracted_by_source, merge.merged_by_source)
            )

    return result


def _source_quality(
    extracted_by_source: Counter, merged_by_source: dict[str, int]
) -> dict[str, tuple[int, int]]:
    """{source: (events_found, unique_events)} для record_source_quality.

    unique = извлечено − проиграно кросс-источниковому merge. merged_by_source — ключи
    вида 'loser→winner' (см. merge.py), считаем потери по источнику-проигравшему.
    """
    losses: Counter = Counter()
    for key, cnt in merged_by_source.items():
        loser = key.split("→", 1)[0]
        losses[loser] += cnt
    return {
        source: (found, found - losses.get(source, 0))
        for source, found in extracted_by_source.items()
    }


async def _run_per_url_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    extractor: LLMExtractor,
    supabase: Client | None,
    city_slug: str,
    dry_run: bool,
) -> tuple[list[EventRow], PipelineResult]:
    sub = PipelineResult()

    # 1. Discovery
    all_urls: list[DiscoveredUrl] = []
    try:
        strategy = _make_discovery(client, source)
        found = await strategy.discover()
        log.info("discovery.ok", city=city_slug, source=source.name, count=len(found))
        all_urls = found
    except Exception as exc:  # noqa: BLE001
        log.error("discovery.failed", city=city_slug, source=source.name, error=str(exc))
        return [], sub

    sub.discovered = len(all_urls)

    # 2. Dedup
    if dry_run or supabase is None:
        new_urls = all_urls
    else:
        existing_check = [u.url for u in all_urls]
        keep = set(filter_new_urls(supabase, existing_check))
        new_urls = [u for u in all_urls if u.url in keep]
    sub.new = len(new_urls)
    log.info("dedup.ok", source=source.name, new=sub.new, skipped=sub.discovered - sub.new)

    # 3. Fetch + LLM extract
    rows: list[EventRow] = []
    for d in new_urls:
        try:
            resp = await client.get(d.url, follow_redirects=True, timeout=20.0)
            resp.raise_for_status()
            parsed = await extractor.extract(resp.text, d.url)
            row = to_event_row(parsed, city_slug, d.url, d.source)
            rows.append(row)
            sub.extracted += 1
            if not dry_run and supabase is not None:
                save_raw_document(supabase, d.source, d.url, resp.text, "html")
            log.info("extract.ok", url=d.url, title=parsed.title)
        except ExtractorError as exc:
            sub.failed += 1
            log.warning("extract.skipped", url=d.url, reason=str(exc))
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.error("extract.failed", url=d.url, error=str(exc))

    return rows, sub


async def _run_direct_api_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    supabase: Client | None,
    city_slug: str,
    provider_keys: dict[str, str | None],
    dry_run: bool,
) -> tuple[list[EventRow], PipelineResult]:
    """API-источник: JSON провайдера → ParsedEvent напрямую, без LLM.

    Каждый провайдер возвращает пары (ParsedEvent, source_url) — у 2ГИС это поисковая
    карточка, у Timepad — реальная ссылка на событие.

    Постоянные места (date='always', напр. 2ГИС-боулинг) — это не события, а площадки:
    их пишем напрямую в таблицу venues (source of truth для фронта), а не в events.
    Датированные записи (date != 'always') уходят в events как обычно.
    """
    sub = PipelineResult()

    try:
        items = await _fetch_direct_api_items(client, source, city_slug, provider_keys)
    except _DirectApiConfigError as exc:
        log.error("direct_api.config", source=source.name, reason=str(exc))
        sub.failed = 1
        return [], sub
    except Exception as exc:  # noqa: BLE001
        log.error("direct_api.failed", source=source.name, error=str(exc))
        sub.failed = 1
        return [], sub

    if items is None:
        log.error(
            "direct_api.unknown_provider", source=source.name, provider=source.provider
        )
        sub.failed = 1
        return [], sub

    log.info("direct_api.ok", source=source.name, provider=source.provider, count=len(items))

    rows: list[EventRow] = []
    venues: list[Venue] = []
    for parsed, source_url in items:
        try:
            if parsed.date == "always":
                # source venue-таблицы огрублён до 'twogis' (а не 'twogis-bowling'),
                # как в db.event_row_to_venue — manual-guard в upsert_venues по нему.
                venues.append(to_venue(parsed, city_slug, "twogis"))
            else:
                rows.append(to_event_row(parsed, city_slug, source_url, source.name))
                sub.extracted += 1
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.warning("direct_api.row_invalid", title=parsed.title, error=str(exc))

    if venues:
        log.info(
            "pipeline.direct_api.venues_routed", source=source.name, count=len(venues)
        )
        if not dry_run and supabase is not None:
            upsert_venues(supabase, venues)

    sub.discovered = len(items)
    sub.new = sub.extracted
    return rows, sub


class _DirectApiConfigError(RuntimeError):
    """Не хватает ключа или обязательного параметра конфигурации источника."""


async def _fetch_direct_api_items(
    client: httpx.AsyncClient,
    source: SourceConfig,
    city_slug: str,
    provider_keys: dict[str, str | None],
) -> list[tuple[ParsedEvent, str]] | None:
    """Диспетчер по provider. None → провайдер неизвестен.

    twogis/timepad требуют event_type из конфига; kudago сам маппит категории.
    """
    if source.provider == "twogis":
        key = provider_keys.get("twogis")
        if not key:
            raise _DirectApiConfigError("нет TWOGIS_API_KEY")
        if not source.api_query or not source.event_type:
            raise _DirectApiConfigError("нужны api_query и event_type")
        parsed = await TwoGisClient(client, key).search(
            source.api_query, event_type=source.event_type  # type: ignore[arg-type]
        )
        # У 2ГИС реальной ссылки на событие нет — используем поисковую карточку.
        url = f"https://2gis.ru/{city_slug}/search/{source.api_query}"
        return [(p, url) for p in parsed]

    if source.provider == "timepad":
        token = provider_keys.get("timepad")
        if not token:
            raise _DirectApiConfigError("нет TIMEPAD_TOKEN")
        # Широкая афиша: тип определяется по категории события внутри клиента.
        return await TimepadClient(client, token).search(city_slug)

    if source.provider == "kudago":
        # Ключ не нужен; тип события маппится из категорий KudaGo внутри клиента.
        return await KudaGoClient(client).search(source.api_query or city_slug)

    if source.provider == "quizplease":
        if not source.quizplease_city_id:
            raise _DirectApiConfigError("нужен quizplease_city_id")
        return await QuizPleaseClient(client, city_slug).search(source.quizplease_city_id)

    return None


async def _run_vk_events_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    city_slug: str,
    vk_service_key: str | None,
) -> tuple[list[EventRow], PipelineResult]:
    """VK-сообщества типа «событие» → ParsedEvent напрямую, без LLM."""
    sub = PipelineResult()
    if not vk_service_key:
        log.error("vk_events.config", source=source.name, reason="нет VK_SERVICE_KEY")
        sub.failed = 1
        return [], sub

    city_name = vk_mod.CITY_NAMES.get(city_slug, city_slug)
    try:
        groups = await VkClient(client, vk_service_key).search_event_groups(
            city_name, city_id=source.vk_city_id
        )
    except Exception as exc:  # noqa: BLE001
        log.error("vk_events.failed", source=source.name, error=str(exc))
        sub.failed = 1
        return [], sub

    rows: list[EventRow] = []
    for g in groups:
        parsed = vk_mod.event_group_to_parsed(g, city_name)
        if parsed is None:
            continue
        try:
            rows.append(
                to_event_row(parsed, city_slug, vk_mod.event_group_url(g), source.name)
            )
            sub.extracted += 1
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.warning("vk_events.row.invalid", title=parsed.title, error=str(exc))

    log.info("vk_events.ok", source=source.name, groups=len(groups), extracted=sub.extracted)
    sub.discovered = len(groups)
    sub.new = sub.extracted
    return rows, sub


async def _run_vk_posts_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    extractor: LLMExtractor,
    supabase: Client | None,
    city_slug: str,
    vk_service_key: str | None,
    dry_run: bool,
    post_batch_size: int,
) -> tuple[list[EventRow], PipelineResult]:
    """Посты со стен кураторских VK-сообществ → префильтр → LLM (1 вызов на пачку постов).

    source_url события — ссылка на конкретный пост (event_url из маркера / фолбэк на группу).
    Посты идут пачками по post_batch_size, пачки — параллельно с ограничением _POST_CONCURRENCY.
    """
    sub = PipelineResult()
    if not vk_service_key:
        log.error("vk_posts.config", source=source.name, reason="нет VK_SERVICE_KEY")
        sub.failed = 1
        return [], sub
    if not source.vk_groups:
        log.warning("vk_posts.no_groups", source=source.name)
        return [], sub

    vk = VkClient(client, vk_service_key)
    rows: list[EventRow] = []

    for screen in source.vk_groups:
        try:
            posts = await vk.fetch_wall_posts(screen, count=100)
        except vk_mod.VkApiError as exc:
            log.warning("vk_posts.group.skipped", group=screen, reason=str(exc))
            continue
        except Exception as exc:  # noqa: BLE001
            log.error("vk_posts.group.failed", group=screen, error=str(exc))
            sub.failed += 1
            continue

        # Префильтр: свежие посты-кандидаты, ещё не обработанные (raw_documents по хешу текста).
        candidates: list[tuple[str, str]] = []
        for p in posts:
            if not vk_mod.post_within_days(p, 14):
                continue
            text = p.get("text") or ""
            if not vk_mod.is_event_candidate(text):
                continue
            url = vk_mod.post_url(p.get("owner_id"), p.get("id"))
            if not dry_run and supabase is not None:
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if get_raw_document_hash(supabase, url) == text_hash:
                    continue
            candidates.append((url, text))
            if len(candidates) >= 20:
                break

        sub.discovered += len(candidates)
        if not candidates:
            continue

        # Малые батчи: пачки по post_batch_size постов на LLM-вызов (экономия квоты), маркер
        # «=== POST <url> ===» закрепляет event_url за постом. Параллелим с семафором.
        group_url = f"https://vk.com/{screen}"
        sem = asyncio.Semaphore(_POST_CONCURRENCY)
        tasks = [
            _extract_chunk(extractor, chunk, group_url, sem)
            for chunk in _chunks(candidates, post_batch_size)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        today_str = _date.today().isoformat()
        for result in results:
            if isinstance(result, Exception):  # BaseException захватил бы CancelledError
                # Сбой чанка (rate-limit/парс) — посты НЕ помечаем, ретраим в след. прогоне.
                sub.failed += 1
                log.error("vk_posts.extract.failed", group=screen, error=str(result), exc_info=result)
                continue
            # isinstance+continue выше сужают тип до tuple — распаковка безопасна.
            post_events, chunk_posts = result

            # Успех (включая пустой результат) → помечаем ВСЕ посты чанка обработанными.
            if not dry_run and supabase is not None:
                for post_url, text in chunk_posts:
                    save_raw_document(supabase, source.name, post_url, text, "vk_post")

            for parsed in post_events:
                try:
                    if _is_past_event(parsed.date, today_str):
                        log.debug("vk_posts.skip.past", title=parsed.title[:50], date=parsed.date)
                        continue
                    event_src_url = resolve_event_url(parsed.event_url, group_url)
                    log.debug(
                        "vk_posts.event_url",
                        title=parsed.title[:50],
                        raw=parsed.event_url,
                        resolved=event_src_url,
                    )
                    rows.append(to_event_row(parsed, city_slug, event_src_url, source.name))
                    sub.extracted += 1
                except Exception as exc:  # noqa: BLE001
                    sub.failed += 1
                    log.warning("vk_posts.row.invalid", title=parsed.title, error=str(exc))

    log.info("vk_posts.ok", source=source.name, extracted=sub.extracted)
    sub.new = sub.extracted
    return rows, sub


async def _run_telegram_posts_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    extractor: LLMExtractor,
    supabase: Client | None,
    city_slug: str,
    dry_run: bool,
    post_batch_size: int,
) -> tuple[list[EventRow], PipelineResult]:
    """Посты публичных Telegram-каналов (t.me/s/) → префильтр → LLM (1 вызов на пачку постов).

    Зеркало vk-posts. Строгость префильтра берётся из source_type канала: у агрегаторов
    (много шума) фильтр строже, у организаторов — мягче. source_url события — ссылка на
    конкретный пост (event_url из маркера / фолбэк на канал).
    """
    sub = PipelineResult()
    if not source.telegram_sources:
        log.warning("telegram_posts.no_channels", source=source.name)
        return [], sub

    provider = TelegramHtmlProvider(client)
    now_ts = datetime.now(timezone.utc).timestamp()
    rows: list[EventRow] = []

    for ch in source.telegram_sources:
        if not ch.enabled:
            continue
        try:
            posts = await provider.fetch_posts(ch.channel, count=100)
        except Exception as exc:  # noqa: BLE001
            log.error("telegram_posts.channel.failed", channel=ch.channel, error=str(exc))
            sub.failed += 1
            continue

        # Префильтр: свежие посты-кандидаты, ещё не обработанные (raw_documents по хешу текста).
        candidates: list[tuple[str, str]] = []
        for p in posts:
            ts = p.get("date_unix")
            if not isinstance(ts, (int, float)) or ts < now_ts - 14 * 86400:
                continue
            text = p.get("text") or ""
            if not is_event_candidate(text, ch.source_type):
                continue
            url = p.get("url")
            if not url:
                continue
            if not dry_run and supabase is not None:
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if get_raw_document_hash(supabase, url) == text_hash:
                    continue
            candidates.append((url, text))
            if len(candidates) >= 20:
                break

        sub.discovered += len(candidates)
        if not candidates:
            continue

        # Малые батчи: см. _run_vk_posts_source. base_url = канал — фолбэк атрибуции.
        channel_url = f"https://t.me/{ch.channel}"
        sem = asyncio.Semaphore(_POST_CONCURRENCY)
        tasks = [
            _extract_chunk(extractor, chunk, channel_url, sem)
            for chunk in _chunks(candidates, post_batch_size)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        today_str = _date.today().isoformat()
        for result in results:
            if isinstance(result, Exception):  # BaseException захватил бы CancelledError
                # Сбой чанка (rate-limit/парс) — посты НЕ помечаем, ретраим в след. прогоне.
                sub.failed += 1
                log.error("telegram_posts.extract.failed", channel=ch.channel, error=str(result), exc_info=result)
                continue
            # isinstance+continue выше сужают тип до tuple — распаковка безопасна.
            post_events, chunk_posts = result

            # Успех (включая пустой результат) → помечаем ВСЕ посты чанка обработанными.
            if not dry_run and supabase is not None:
                for post_url, text in chunk_posts:
                    save_raw_document(supabase, f"telegram:{ch.channel}", post_url, text, "telegram_post")

            for parsed in post_events:
                try:
                    if _is_past_event(parsed.date, today_str):
                        log.debug("telegram_posts.skip.past", title=parsed.title[:50], date=parsed.date)
                        continue
                    event_src_url = resolve_event_url(parsed.event_url, channel_url)
                    log.debug(
                        "telegram_posts.event_url",
                        title=parsed.title[:50],
                        raw=parsed.event_url,
                        resolved=event_src_url,
                    )
                    rows.append(to_event_row(parsed, city_slug, event_src_url, source.name))
                    sub.extracted += 1
                except Exception as exc:  # noqa: BLE001
                    sub.failed += 1
                    log.warning("telegram_posts.row.invalid", title=parsed.title, error=str(exc))

    log.info("telegram_posts.ok", source=source.name, extracted=sub.extracted)
    sub.new = sub.extracted
    return rows, sub


async def _run_generic_source(
    client: httpx.AsyncClient,
    extractor: LLMExtractor,
    supabase: Client | None,
    city_slug: str,
    llm_budget: int,
    domain_budget: int,
) -> tuple[list[EventRow], PipelineResult]:
    """Одобренные в candidate_sources домены → JSON-LD / LLM (длинный хвост)."""
    sub = PipelineResult()
    rows, extracted, failed = await run_generic(
        client, supabase, extractor, city_slug,
        domain_budget=domain_budget, llm_budget=llm_budget,
    )
    sub.extracted = extracted
    sub.failed = failed
    sub.discovered = len(rows)
    sub.new = extracted
    return rows, sub


async def _run_batch_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    extractor: LLMExtractor,
    supabase: Client | None,
    city_slug: str,
    dry_run: bool,
    *,
    use_playwright: bool = False,
) -> tuple[list[EventRow], PipelineResult]:
    """Скачиваем listing URL целиком. JSON-LD → (фолбэк) один LLM-вызов на все события.

    use_playwright=True — страница рендерится headless-браузером (режим playwright_listing)
    для SPA, где httpx видит пустой скелет. Дальнейшая обработка идентична batch_listing.
    """
    sub = PipelineResult()

    # 1. Один fetch listing-страницы (httpx для статики, Playwright для SPA)
    try:
        if use_playwright:
            from .sources.playwright_fetcher import render_page

            html = await render_page(source.url)
        else:
            resp = await client.get(source.url, follow_redirects=True, timeout=20.0)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:  # noqa: BLE001
        log.error("batch.fetch.failed", source=source.name, error=str(exc))
        return [], sub

    # 2. Дедуп по хешу контента: если листинг не менялся — не зовём LLM/JSON-LD.
    # Хеш хранится в raw_documents (по url) — там же лежит само сырьё для перепарса.
    # Для SPA хешируем только видимый текст (см. _hash_html): сырой DOM нестабилен.
    content_hash = _hash_html(html, playwright=use_playwright)
    if not dry_run and supabase is not None:
        if get_raw_document_hash(supabase, source.url) == content_hash:
            log.info("batch.skip.unchanged", source=source.name, url=source.url)
            return [], sub

    # 3. JSON-LD (бесплатно) перед LLM. Нужен default_type из конфига источника.
    parsed_events: list[ParsedEvent] = []
    if source.event_type:
        try:
            parsed_events = extract_jsonld_events(html, source.event_type)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            log.warning("jsonld.failed", source=source.name, error=str(exc))
        if parsed_events:
            log.info(
                "jsonld.ok", source=source.name, url=source.url, count=len(parsed_events)
            )

    # 4. Фолбэк на LLM, если JSON-LD ничего не дал.
    if not parsed_events:
        try:
            parsed_events = await extractor.extract_many(html, source.url)
        except ExtractorError as exc:
            log.warning("batch.extract.skipped", source=source.name, reason=str(exc))
            sub.failed = 1
            return [], sub
        except Exception as exc:  # noqa: BLE001
            log.error("batch.extract.failed", source=source.name, error=str(exc))
            sub.failed = 1
            return [], sub

        log.info(
            "batch.extract.ok",
            source=source.name,
            url=source.url,
            count=len(parsed_events),
        )

    # Извлечение прошло — архивируем сырьё + фиксируем хеш (raw_documents): следующий
    # неизменный прогон пропустим, а сырьё можно перепарсить новым промптом/моделью.
    if not dry_run and supabase is not None:
        save_raw_document(
            supabase, source.name, source.url, html, "html", content_hash
        )

    # 3. Маппинг в EventRow. source_url = прямая ссылка на событие (event_url из JSON-LD/LLM,
    # относительные достраиваются через urljoin), иначе фолбэк на listing URL.
    # Дедуп между прогонами обеспечивается уникальностью (city, slug) на стороне БД.
    rows: list[EventRow] = []
    today_str = _date.today().isoformat()
    for parsed in parsed_events:
        try:
            if _is_past_event(parsed.date, today_str):
                log.debug("batch.skip.past", title=parsed.title[:50], date=parsed.date)
                continue
            event_src_url = resolve_event_url(parsed.event_url, source.url)
            log.debug(
                "batch.event_url",
                title=parsed.title[:50],
                raw=parsed.event_url,
                resolved=event_src_url,
                base=source.url,
            )
            row = to_event_row(parsed, city_slug, event_src_url, source.name)
            rows.append(row)
            sub.extracted += 1
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.warning("batch.row.invalid", title=parsed.title, error=str(exc))

    sub.discovered = len(parsed_events)
    sub.new = sub.extracted  # дедуп фактически делает upsert в БД

    return rows, sub
