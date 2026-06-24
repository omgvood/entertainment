"""Generic-парсер одобренных кандидатов (замыкает цикл Discovery → Ingestion).

Берёт домены из candidate_sources со status='approved' и парсит их афишу без ручного
кода под каждый сайт: сначала бесплатный JSON-LD, иначе — LLM (в пределах бюджета).

Это инструмент «длинного хвоста» статических сайтов. SPA/JS-рендеринг и анти-бот сайты
generic не возьмёт — такие при необходимости получают специализированный источник.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from supabase import Client

from ..extraction import ExtractorError, LLMExtractor, extract_jsonld_events
from ..models import EventRow, ParsedEvent
from ..db import get_raw_document_hash, record_source_health, save_raw_document
from ..url_utils import resolve_event_url
from ..validator import to_event_row


log = structlog.get_logger()

# Пути-кандидаты для листинга афиши, если у домена не сохранён listing_url.
_PROBE_PATHS = ("/afisha", "/events", "/poster", "/raspisanie", "/schedule")
_EVENT_PATH_HINTS = ("/events", "/afisha", "/schedule", "/event", "/poster", "/raspisanie")
_LISTING_TTL_DAYS = 30  # как часто перепроверять закэшированный listing_url


async def load_approved_domains(
    supabase: Client, city_slug: str, *, limit: int
) -> list[dict]:
    """Одобренные домены города по убыванию score, не больше limit (защита времени прогона)."""
    resp = (
        supabase.table("candidate_sources")
        .select("domain,sample_urls,listing_url,last_verified,has_jsonld_event")
        .eq("city", city_slug)
        .eq("status", "approved")
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )
    return resp.data or []


def _fresh(last_verified: str | None) -> bool:
    if not last_verified:
        return False
    try:
        dt = datetime.fromisoformat(last_verified.replace("Z", "+00:00"))
    except ValueError:
        return False
    return dt > datetime.now(timezone.utc) - timedelta(days=_LISTING_TTL_DAYS)


async def resolve_listing_url(
    client: httpx.AsyncClient, domain: str, candidate: dict
) -> str | None:
    """Определяет URL страницы-листинга: кэш → sample_urls с хинтом → пробинг путей."""
    cached = candidate.get("listing_url")
    if cached and _fresh(candidate.get("last_verified")):
        return cached

    for u in candidate.get("sample_urls") or []:
        if any(h in u.lower() for h in _EVENT_PATH_HINTS):
            return u

    base = f"https://{domain}"
    for path in ("",) + _PROBE_PATHS:
        url = base + path
        try:
            resp = await client.get(url, follow_redirects=True, timeout=15.0)
            if resp.status_code == 200 and len(resp.text) > 500:
                return str(resp.url)
        except Exception:  # noqa: BLE001
            continue
    return None


def _update_listing_cache(supabase: Client, domain: str, url: str) -> None:
    try:
        supabase.table("candidate_sources").update(
            {"listing_url": url, "last_verified": datetime.now(timezone.utc).isoformat()}
        ).eq("domain", domain).execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("generic.cache.failed", domain=domain, error=str(exc))


async def run_generic(
    client: httpx.AsyncClient,
    supabase: Client | None,
    extractor: LLMExtractor,
    city_slug: str,
    *,
    domain_budget: int,
    llm_budget: int,
) -> tuple[list[EventRow], int, int]:
    """Парсит одобренные домены. Возвращает (строки, extracted, failed).

    Health пишется per-domain (source='generic:{domain}'). В --dry-run (supabase=None)
    читать candidate_sources неоткуда — логируем skip и выходим.
    """
    if supabase is None:
        log.info("generic.skip", reason="нет supabase (--dry-run): candidate_sources недоступна")
        return [], 0, 0

    domains = await load_approved_domains(supabase, city_slug, limit=domain_budget)
    if not domains:
        log.info("generic.no_domains", city=city_slug)
        return [], 0, 0

    all_rows: list[EventRow] = []
    extracted = 0
    failed = 0
    llm_left = llm_budget

    for cand in domains:
        domain = cand["domain"]
        started = time.perf_counter()
        rows, used_llm, err = await _run_domain(
            client, supabase, extractor, city_slug, cand, allow_llm=llm_left > 0
        )
        if used_llm:
            llm_left -= 1
        all_rows.extend(rows)
        extracted += len(rows)
        failed += err
        record_source_health(
            supabase,
            f"generic:{domain}",
            city_slug,
            events_found=len(rows),
            errors=err,
            duration_sec=time.perf_counter() - started,
        )

    log.info(
        "generic.done", city=city_slug, domains=len(domains),
        extracted=extracted, failed=failed, llm_used=llm_budget - llm_left,
    )
    return all_rows, extracted, failed


async def _run_domain(
    client: httpx.AsyncClient,
    supabase: Client,
    extractor: LLMExtractor,
    city_slug: str,
    candidate: dict,
    *,
    allow_llm: bool,
) -> tuple[list[EventRow], bool, int]:
    """Один домен: резолв URL → fetch (1 стр.) → JSON-LD → (бюджет) LLM. (rows, used_llm, errors)."""
    domain = candidate["domain"]

    listing_url = await resolve_listing_url(client, domain, candidate)
    if not listing_url:
        log.warning("generic.no_listing", domain=domain)
        return [], False, 1
    _update_listing_cache(supabase, domain, listing_url)

    try:
        resp = await client.get(listing_url, follow_redirects=True, timeout=20.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        log.warning("generic.fetch.failed", domain=domain, url=listing_url, error=str(exc))
        return [], False, 1

    content_hash = hashlib.sha256(resp.text.encode("utf-8")).hexdigest()
    if get_raw_document_hash(supabase, listing_url) == content_hash:
        log.info("generic.skip.unchanged", domain=domain, url=listing_url)
        return [], False, 0

    # JSON-LD (бесплатно) — этого хватит доменам с has_jsonld_event.
    parsed: list[ParsedEvent] = []
    try:
        parsed = extract_jsonld_events(resp.text, "other")
    except Exception as exc:  # noqa: BLE001
        log.warning("generic.jsonld.failed", domain=domain, error=str(exc))
    if parsed:
        log.info("generic.jsonld.ok", domain=domain, count=len(parsed))

    used_llm = False
    if not parsed:
        if not allow_llm:
            log.info("generic.llm.budget_exhausted", domain=domain)
            return [], False, 0
        used_llm = True
        try:
            parsed = await extractor.extract_many(resp.text, listing_url)
        except ExtractorError as exc:
            log.warning("generic.extract.skipped", domain=domain, reason=str(exc))
            return [], used_llm, 1
        except Exception as exc:  # noqa: BLE001
            log.error("generic.extract.failed", domain=domain, error=str(exc))
            return [], used_llm, 1
        log.info("generic.extract.ok", domain=domain, count=len(parsed))

    save_raw_document(supabase, f"generic:{domain}", listing_url, resp.text, "html", content_hash)

    rows: list[EventRow] = []
    errors = 0
    for p in parsed:
        try:
            # source_url = ссылка на само событие (event_url из JSON-LD/LLM), иначе листинг.
            src_url = resolve_event_url(p.event_url, listing_url)
            rows.append(to_event_row(p, city_slug, src_url, f"generic:{domain}"))
        except Exception as exc:  # noqa: BLE001
            errors += 1
            log.warning("generic.row.invalid", domain=domain, title=p.title, error=str(exc))
    return rows, used_llm, errors
