"""Оркестратор. Два режима:
- per_url:        discovery → dedup → fetch per URL → LLM extract per URL → write
- batch_listing:  fetch listing URL → LLM extract_many (1 вызов) → write
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import httpx
import structlog
from supabase import Client

from .config import CityConfig, SourceConfig
from .db import (
    WriteStats,
    cleanup_old_events,
    cleanup_old_raw_documents,
    get_raw_document_hash,
    record_coverage,
    record_source_health,
    save_raw_document,
    upsert_events,
)
from .dedup import filter_new_urls
from .discovery import DiscoveredUrl, ListingDiscovery, SitemapDiscovery
from .extraction import ExtractorError, LLMExtractor, extract_jsonld_events
from .models import EventRow, EventType, ParsedEvent
from .sources import KudaGoClient, TimepadClient, TwoGisClient
from .validator import to_event_row


log = structlog.get_logger()


@dataclass
class PipelineResult:
    discovered: int = 0
    new: int = 0
    extracted: int = 0
    failed: int = 0
    written: int = 0
    duplicate_candidates: int = 0


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
    mode_override: str | None = None,
) -> PipelineResult:
    """Полный прогон по одному городу. supabase=None при --dry-run.

    mode_override: если задан, переопределяет extraction_mode для ВСЕХ источников этого
    прогона (per_url / batch_listing / direct_api) — для разовых сравнений провайдеров.
    """
    result = PipelineResult()
    provider_keys = {"twogis": twogis_api_key, "timepad": timepad_token}

    async with httpx.AsyncClient(
        headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
    ) as client:
        all_rows: list[EventRow] = []

        for source in city.sources:
            if only_source and source.name != only_source:
                continue
            mode = mode_override or source.extraction_mode
            started = time.perf_counter()
            if mode == "batch_listing":
                rows, sub = await _run_batch_source(
                    client, source, extractor, supabase, city.slug, dry_run
                )
            elif mode == "direct_api":
                rows, sub = await _run_direct_api_source(
                    client, source, city.slug, provider_keys
                )
            else:
                rows, sub = await _run_per_url_source(
                    client, source, extractor, supabase, city.slug, dry_run
                )
            duration = time.perf_counter() - started
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

        # 4. Дедуп по id — если два источника (или два item'а 2ГИС) дали одинаковый
        # slug, Postgres не сможет upsert-нуть их в одном batch. Оставляем последний.
        deduped: dict[str, EventRow] = {}
        collisions = 0
        for r in all_rows:
            if r.id in deduped:
                collisions += 1
                log.warning(
                    "dedup.collision",
                    id=r.id,
                    kept_title=deduped[r.id].title,
                    skipped_title=r.title,
                )
            deduped[r.id] = r
        all_rows = list(deduped.values())
        if collisions:
            log.info("dedup.summary", collisions=collisions, final_count=len(all_rows))

        # 4b. Кросс-источниковые кандидаты на дубль: одинаковый fingerprint (title+date+venue),
        # но разный slug/источник. НЕ схлопываем (constraint вводим позже) — только считаем.
        fp_groups: dict[str, int] = {}
        for r in all_rows:
            if r.fingerprint:
                fp_groups[r.fingerprint] = fp_groups.get(r.fingerprint, 0) + 1
        result.duplicate_candidates = sum(n - 1 for n in fp_groups.values() if n > 1)
        if result.duplicate_candidates:
            log.info(
                "dedup.fingerprint_candidates",
                duplicate_candidates=result.duplicate_candidates,
            )

        # 5. Write
        if dry_run or supabase is None:
            log.info("write.skipped", reason="dry-run", would_write=len(all_rows))
        else:
            stats: WriteStats = upsert_events(supabase, all_rows)
            result.written = stats.inserted
            cleanup_old_events(supabase, city.slug)
            cleanup_old_raw_documents(supabase)
            record_coverage(supabase, city.slug)

    return result


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
    city_slug: str,
    provider_keys: dict[str, str | None],
) -> tuple[list[EventRow], PipelineResult]:
    """API-источник: JSON провайдера → ParsedEvent напрямую, без LLM.

    Каждый провайдер возвращает пары (ParsedEvent, source_url) — у 2ГИС это поисковая
    карточка, у Timepad — реальная ссылка на событие.
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
    for parsed, source_url in items:
        try:
            rows.append(to_event_row(parsed, city_slug, source_url, source.name))
            sub.extracted += 1
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.warning("direct_api.row_invalid", title=parsed.title, error=str(exc))

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

    return None


async def _run_batch_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    extractor: LLMExtractor,
    supabase: Client | None,
    city_slug: str,
    dry_run: bool,
) -> tuple[list[EventRow], PipelineResult]:
    """Скачиваем listing URL целиком. JSON-LD → (фолбэк) один LLM-вызов на все события."""
    sub = PipelineResult()

    # 1. Один fetch listing-страницы
    try:
        resp = await client.get(source.url, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.error("batch.fetch.failed", source=source.name, error=str(exc))
        return [], sub

    # 2. Дедуп по хешу контента: если листинг не менялся — не зовём LLM/JSON-LD.
    # Хеш хранится в raw_documents (по url) — там же лежит само сырьё для перепарса.
    content_hash = hashlib.sha256(resp.text.encode("utf-8")).hexdigest()
    if not dry_run and supabase is not None:
        if get_raw_document_hash(supabase, source.url) == content_hash:
            log.info("batch.skip.unchanged", source=source.name, url=source.url)
            return [], sub

    # 3. JSON-LD (бесплатно) перед LLM. Нужен default_type из конфига источника.
    parsed_events: list[ParsedEvent] = []
    if source.event_type:
        try:
            parsed_events = extract_jsonld_events(resp.text, source.event_type)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            log.warning("jsonld.failed", source=source.name, error=str(exc))
        if parsed_events:
            log.info(
                "jsonld.ok", source=source.name, url=source.url, count=len(parsed_events)
            )

    # 4. Фолбэк на LLM, если JSON-LD ничего не дал.
    if not parsed_events:
        try:
            parsed_events = await extractor.extract_many(resp.text, source.url)
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
            supabase, source.name, source.url, resp.text, "html", content_hash
        )

    # 3. Маппинг в EventRow. В batch-режиме source_url у всех — это listing URL
    # (точную ссылку на конкретное событие LLM не знает, можно добавить отдельным полем позже).
    # Дедуп между прогонами обеспечивается уникальностью (city, slug) на стороне БД.
    rows: list[EventRow] = []
    for parsed in parsed_events:
        try:
            row = to_event_row(parsed, city_slug, source.url, source.name)
            rows.append(row)
            sub.extracted += 1
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.warning("batch.row.invalid", title=parsed.title, error=str(exc))

    sub.discovered = len(parsed_events)
    sub.new = sub.extracted  # дедуп фактически делает upsert в БД

    return rows, sub
