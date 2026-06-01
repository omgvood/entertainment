"""Оркестратор. Два режима:
- per_url:        discovery → dedup → fetch per URL → LLM extract per URL → write
- batch_listing:  fetch listing URL → LLM extract_many (1 вызов) → write
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog
from supabase import Client

from .config import CityConfig, SourceConfig
from .db import WriteStats, cleanup_old_events, upsert_events
from .dedup import filter_new_urls
from .discovery import DiscoveredUrl, ListingDiscovery, SitemapDiscovery
from .extraction import ExtractorError, LLMExtractor
from .models import EventRow, EventType
from .sources import TwoGisClient
from .validator import to_event_row


log = structlog.get_logger()


@dataclass
class PipelineResult:
    discovered: int = 0
    new: int = 0
    extracted: int = 0
    failed: int = 0
    written: int = 0


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
    mode_override: str | None = None,
) -> PipelineResult:
    """Полный прогон по одному городу. supabase=None при --dry-run.

    mode_override: если задан, переопределяет extraction_mode для ВСЕХ источников этого
    прогона (per_url / batch_listing / direct_api) — для разовых сравнений провайдеров.
    """
    result = PipelineResult()

    async with httpx.AsyncClient(
        headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
    ) as client:
        all_rows: list[EventRow] = []

        for source in city.sources:
            if only_source and source.name != only_source:
                continue
            mode = mode_override or source.extraction_mode
            if mode == "batch_listing":
                rows, sub = await _run_batch_source(client, source, extractor, city.slug)
            elif mode == "direct_api":
                rows, sub = await _run_direct_api_source(
                    client, source, city.slug, twogis_api_key
                )
            else:
                rows, sub = await _run_per_url_source(
                    client, source, extractor, supabase, city.slug, dry_run
                )
            all_rows.extend(rows)
            result.discovered += sub.discovered
            result.new += sub.new
            result.extracted += sub.extracted
            result.failed += sub.failed

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

        # 5. Write
        if dry_run or supabase is None:
            log.info("write.skipped", reason="dry-run", would_write=len(all_rows))
        else:
            stats: WriteStats = upsert_events(supabase, all_rows)
            result.written = stats.inserted
            cleanup_old_events(supabase, city.slug)

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
    twogis_api_key: str | None,
) -> tuple[list[EventRow], PipelineResult]:
    """API-источник (2ГИС): JSON → ParsedEvent напрямую, без LLM."""
    sub = PipelineResult()

    if source.provider != "twogis":
        log.error(
            "direct_api.unknown_provider",
            source=source.name,
            provider=source.provider,
        )
        sub.failed = 1
        return [], sub

    if not twogis_api_key:
        log.error("direct_api.missing_key", source=source.name, env="TWOGIS_API_KEY")
        sub.failed = 1
        return [], sub

    if not source.api_query or not source.event_type:
        log.error(
            "direct_api.missing_config",
            source=source.name,
            need=["api_query", "event_type"],
        )
        sub.failed = 1
        return [], sub

    api = TwoGisClient(client, twogis_api_key)
    try:
        parsed_events = await api.search(
            source.api_query,
            event_type=source.event_type,  # type: ignore[arg-type]
        )
    except Exception as exc:  # noqa: BLE001
        log.error("direct_api.failed", source=source.name, error=str(exc))
        sub.failed = 1
        return [], sub

    log.info(
        "direct_api.ok",
        source=source.name,
        query=source.api_query,
        count=len(parsed_events),
    )

    rows: list[EventRow] = []
    for parsed in parsed_events:
        try:
            # source_url для 2ГИС-места — карточка в 2ГИС
            # (точный URL можно собрать из item.id, но пока используем search URL)
            source_url = f"https://2gis.ru/{city_slug}/search/{source.api_query}"
            row = to_event_row(parsed, city_slug, source_url, source.name)
            rows.append(row)
            sub.extracted += 1
        except Exception as exc:  # noqa: BLE001
            sub.failed += 1
            log.warning("direct_api.row_invalid", title=parsed.title, error=str(exc))

    sub.discovered = len(parsed_events)
    sub.new = sub.extracted

    return rows, sub


async def _run_batch_source(
    client: httpx.AsyncClient,
    source: SourceConfig,
    extractor: LLMExtractor,
    city_slug: str,
) -> tuple[list[EventRow], PipelineResult]:
    """Скачиваем listing URL целиком, один LLM-вызов на все события."""
    sub = PipelineResult()

    # 1. Один fetch listing-страницы
    try:
        resp = await client.get(source.url, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.error("batch.fetch.failed", source=source.name, error=str(exc))
        return [], sub

    # 2. Один LLM-вызов
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
