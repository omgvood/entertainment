"""CLI: точка входа для cron и локальных запусков.

Примеры:
    # Сухой прогон (без LLM и без записи в БД) — проверить только discovery:
    python -m parser.cli discover --city perm

    # Полный прогон по одному источнику в --dry-run (LLM зовём, но не пишем):
    python -m parser.cli run --city perm --source quizplease --dry-run

    # Боевой прогон (всё):
    python -m parser.cli run --city perm
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import httpx
import structlog

from .config import CityConfig, LlmProvider, Settings, SourceConfig, load_seeds
from .db import make_client, sync_venues_from_events, upsert_venues
from .discovery import ListingDiscovery, SitemapDiscovery
from .extraction import DeepSeekExtractor, FallbackExtractor, GeminiExtractor, GroqExtractor, LLMExtractor
from .models import ParsedEvent, Venue
from .pipeline import run_city
from .validator import to_venue


def _make_extractor(settings: Settings, provider: LlmProvider) -> LLMExtractor:
    model = settings.model_for(provider)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY не задан — нужен для provider=gemini")
        return GeminiExtractor(api_key=settings.gemini_api_key, model=model)
    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY не задан — нужен для provider=groq")
        return GroqExtractor(api_key=settings.groq_api_key, model=model)
    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise RuntimeError("DEEPSEEK_API_KEY не задан — нужен для provider=deepseek")
        return DeepSeekExtractor(api_key=settings.deepseek_api_key, model=model)
    raise ValueError(f"Неизвестный провайдер: {provider!r}")


def _make_extractor_chain(settings: Settings, primary: LlmProvider) -> LLMExtractor:
    """Цепочка провайдеров для ретрая+фолбэка: primary, затем остальные из
    settings.llm_fallback_providers, у кого задан ключ. При 429/503 переключаемся дальше."""
    keys = {
        "gemini": settings.gemini_api_key,
        "groq": settings.groq_api_key,
        "deepseek": settings.deepseek_api_key,
    }
    order: list[LlmProvider] = [primary]
    for p in settings.llm_fallback_providers.split(","):
        p = p.strip()  # type: ignore[assignment]
        if p and p in keys and p not in order:
            order.append(p)  # type: ignore[arg-type]

    providers = [(p, _make_extractor(settings, p)) for p in order if keys.get(p)]
    if not providers:
        raise RuntimeError(f"Нет ключа ни для одного провайдера из цепочки {order}")
    return FallbackExtractor(providers, retry_attempts=settings.llm_retry_attempts)


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s")
    # httpx логирует полный URL каждого запроса — для 2ГИС там в query API-ключ.
    # Глушим INFO-логи httpx/httpcore, ошибки (4xx/5xx) всё равно вылезут на WARNING+.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.KeyValueRenderer(),
        ],
    )


async def _cmd_discover(args: argparse.Namespace) -> int:
    """Только дискавери, без LLM и записи. Полезно для отладки seed-конфига."""
    cities = load_seeds()
    if args.city not in cities:
        print(f"Город {args.city!r} не описан в seeds.yaml", file=sys.stderr)
        return 1
    city = cities[args.city]

    async with httpx.AsyncClient(
        headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
    ) as client:
        for source in city.sources:
            if args.source and source.name != args.source:
                continue
            print(f"\n=== {source.name} ({source.kind}) ===")
            if source.kind == "listing":
                strat = ListingDiscovery(
                    client, source.name, source.url, source.url_pattern or ""
                )
            else:
                strat = SitemapDiscovery(
                    client, source.name, source.url, source.url_pattern
                )
            try:
                urls = await strat.discover()
            except Exception as exc:  # noqa: BLE001
                print(f"  ОШИБКА: {exc}")
                continue
            print(f"  Найдено URL: {len(urls)}")
            for u in urls[:10]:
                print(f"    {u.url}")
            if len(urls) > 10:
                print(f"    ... ещё {len(urls) - 10}")
    return 0


async def _cmd_discover_sources(args: argparse.Namespace) -> int:
    """Поиск новых источников → candidate_sources (Discovery). Раз в неделю."""
    from .sources.candidate_sources import discover_sources

    supabase = None
    if not args.dry_run:
        settings = Settings.from_env()
        _setup_logging(settings.log_level)
        supabase = make_client(settings.supabase_url, settings.supabase_service_key)

    candidates = await discover_sources(args.city, supabase, dry_run=args.dry_run)

    print(f"\nКандидаты для {args.city} (по убыванию score):")
    for c in candidates[:30]:
        flag = " [JSON-LD Event]" if c.has_jsonld_event else ""
        print(f"  {c.score:>3}  {c.domain}{flag}  (запросов: {len(c.queries)})")
    print(f"\nВсего кандидатов: {len(candidates)}"
          f"{' (dry-run, не сохранено)' if args.dry_run else ''}")
    return 0


_VENUE_COLUMNS = (
    "id", "city", "name", "type", "address", "district", "image_url", "source", "updated_at"
)


def _sql_literal(value: object) -> str:
    """Значение → SQL-литерал (строки в кавычках с экранированием, None → NULL)."""
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def _cmd_export_venues(args: argparse.Namespace) -> int:
    """Снимок таблицы venues в SQL-файл (бекап в git). Supabase free tier бекапов не делает."""
    settings = Settings.from_env()
    _setup_logging(settings.log_level)
    supabase = make_client(settings.supabase_url, settings.supabase_service_key)

    query = supabase.table("venues").select("*").order("id")
    if args.city:
        query = query.eq("city", args.city)
    rows = query.execute().data or []

    lines = [
        "-- Снимок таблицы venues (автогенерация parser-cli export-venues).",
        f"-- Строк: {len(rows)}" + (f", город: {args.city}" if args.city else ""),
        "",
    ]
    for r in rows:
        cols = ", ".join(_VENUE_COLUMNS)
        vals = ", ".join(_sql_literal(r.get(c)) for c in _VENUE_COLUMNS)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in _VENUE_COLUMNS if c != "id")
        lines.append(
            f"INSERT INTO venues ({cols}) VALUES ({vals})\n"
            f"  ON CONFLICT (id) DO UPDATE SET {updates};"
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Экспортировано venues: {len(rows)} → {out}")
    return 0


def _twogis_venue_sources(city: CityConfig) -> list[SourceConfig]:
    """direct_api источники с provider=twogis — у них берём пары (api_query, event_type)."""
    return [
        s
        for s in city.sources
        if s.provider == "twogis" and s.api_query and s.event_type
    ]


async def _collect_via_twogis(
    client: httpx.AsyncClient, sources: list[SourceConfig], api_key: str
) -> list[ParsedEvent]:
    from .sources.twogis import TwoGisClient

    twogis = TwoGisClient(client, api_key)
    out: list[ParsedEvent] = []
    for s in sources:
        out.extend(await twogis.search(s.api_query, event_type=s.event_type))  # type: ignore[arg-type]
    return out


async def _collect_via_playwright(
    city_slug: str, sources: list[SourceConfig]
) -> list[ParsedEvent]:
    from .sources.playwright_2gis import scrape_venues

    out: list[ParsedEvent] = []
    for s in sources:
        out.extend(await scrape_venues(city_slug, s.api_query, s.event_type))  # type: ignore[arg-type]
    return out


async def _collect_venues(
    city: CityConfig, settings: Settings, *, source: str
) -> tuple[list[Venue], str]:
    """Собирает заведения города. Возвращает (venues, использованный_источник).

    source='twogis'     — только API (без fallback).
    source='playwright' — только браузер.
    source='auto'       — пробуем API, при ошибке/пустом результате fallback на Playwright.
    """
    twogis_sources = _twogis_venue_sources(city)
    if not twogis_sources:
        print(f"  У города {city.slug!r} нет twogis-источников в seeds.yaml", file=sys.stderr)
        return [], source

    used = source
    parsed: list[ParsedEvent] = []

    if source == "playwright":
        parsed = await _collect_via_playwright(city.slug, twogis_sources)
    else:
        async with httpx.AsyncClient(
            headers={"User-Agent": "EventsBot/1.0 (pet-project)"}
        ) as client:
            try:
                if not settings.twogis_api_key:
                    raise RuntimeError("нет TWOGIS_API_KEY")
                parsed = await _collect_via_twogis(
                    client, twogis_sources, settings.twogis_api_key
                )
                used = "twogis"
            except Exception as exc:  # noqa: BLE001
                if source == "twogis":
                    raise
                print(f"  2ГИС API недоступен ({exc}) — fallback на Playwright", file=sys.stderr)
                parsed = []

        if source == "auto" and not parsed:
            print("  2ГИС API вернул пусто — fallback на Playwright", file=sys.stderr)
            parsed = await _collect_via_playwright(city.slug, twogis_sources)
            used = "playwright"

    venues = [to_venue(p, city.slug, used) for p in parsed]
    return venues, used


async def _cmd_refresh_venues(args: argparse.Namespace) -> int:
    """Сбор постоянных заведений → таблица venues (НЕ events). 2ГИС API primary, Playwright fallback."""
    settings = Settings.from_env()
    _setup_logging(settings.log_level)
    supabase = make_client(settings.supabase_url, settings.supabase_service_key)

    cities = load_seeds()
    targets = list(cities) if args.city == "all" else [args.city]
    for t in targets:
        if t not in cities:
            print(f"Город {t!r} не описан в seeds.yaml", file=sys.stderr)
            return 1

    rc = 0
    for slug in targets:
        print(f"\n=== {slug} (source={args.source}) ===", file=sys.stderr)
        try:
            venues, used = await _collect_venues(cities[slug], settings, source=args.source)
        except Exception as exc:  # noqa: BLE001
            print(f"  ОШИБКА сбора: {exc}", file=sys.stderr)
            rc = 1
            continue
        stats = upsert_venues(supabase, venues)
        print(
            f"  {slug}: собрано {len(venues)} (источник {used}), "
            f"записано {stats.inserted}, ошибок {stats.errors}"
        )
    return rc


def _cmd_sync_venues(args: argparse.Namespace) -> int:
    """Пересборка venues из events(date='always', twogis-*).

    Safe-by-default: без --force только dry-run (печатает «would import: N»). Это full-overwrite
    инструмент — с --force перезапишет venues и затрёт обогащения refresh-venues (Playwright).
    Отличие от bootstrap в run: тот INSERT-only и срабатывает лишь на пустой таблице.
    """
    settings = Settings.from_env()
    _setup_logging(settings.log_level)
    supabase = make_client(settings.supabase_url, settings.supabase_service_key)

    cities = load_seeds()
    targets = list(cities) if args.city == "all" else [args.city]
    for t in targets:
        if t not in cities:
            print(f"Город {t!r} не описан в seeds.yaml", file=sys.stderr)
            return 1

    for slug in targets:
        stats = sync_venues_from_events(supabase, slug, dry_run=not args.force)
        if args.force:
            print(f"  {slug}: записано venues {stats.inserted}, ошибок {stats.errors}")
        else:
            print(f"  {slug}: dry-run (без записи) — запусти с --force для перезаписи")
    return 0


async def _cmd_run(args: argparse.Namespace) -> int:
    """Полный пайплайн."""
    settings = Settings.from_env()
    _setup_logging(settings.log_level)

    cities = load_seeds()
    if args.city not in cities:
        print(f"Город {args.city!r} не описан в seeds.yaml", file=sys.stderr)
        return 1
    city = cities[args.city]

    provider: LlmProvider = args.provider or settings.llm_provider
    extractor = _make_extractor_chain(settings, provider)
    print(f"LLM primary: {provider}, model: {settings.model_for(provider)}", file=sys.stderr)

    supabase = None if args.dry_run else make_client(
        settings.supabase_url, settings.supabase_service_key
    )

    result = await run_city(
        city,
        extractor,
        supabase,
        dry_run=args.dry_run,
        only_source=args.source,
        twogis_api_key=settings.twogis_api_key,
        timepad_token=settings.timepad_token,
        vk_service_key=settings.vk_service_key,
        generic_llm_budget=settings.generic_llm_budget,
        generic_domain_budget=settings.generic_domain_budget,
        post_batch_size=settings.post_batch_size,
        mode_override=args.mode,
    )
    print(
        f"\nГотово: discovered={result.discovered}, "
        f"new={result.new}, extracted={result.extracted}, "
        f"failed={result.failed}, written={result.written}, "
        f"merged={result.merged}, near_misses={result.near_misses}"
    )
    if result.merged_by_source:
        print(f"  merge по источникам: {result.merged_by_source}")
    return 0 if result.failed < result.extracted else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="parser")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_disc = sub.add_parser("discover", help="Только дискавери, без LLM и записи")
    p_disc.add_argument("--city", required=True)
    p_disc.add_argument("--source", help="Имя одного источника")

    p_ds = sub.add_parser("discover-sources", help="Поиск новых источников (Discovery)")
    p_ds.add_argument("--city", required=True)
    p_ds.add_argument(
        "--dry-run",
        action="store_true",
        help="Не писать в candidate_sources, только вывести кандидатов",
    )

    p_ev = sub.add_parser("export-venues", help="Снимок venues → SQL-файл (бекап в git)")
    p_ev.add_argument("--city", help="Только один город (опц.)")
    p_ev.add_argument(
        "--output",
        default="supabase/seeds/venues.sql",
        help="Куда писать SQL (по умолчанию supabase/seeds/venues.sql)",
    )

    p_rv = sub.add_parser(
        "refresh-venues", help="Сбор постоянных заведений → таблица venues (2ГИС API / Playwright)"
    )
    p_rv.add_argument("--city", required=True, help="perm / sochi / all")
    p_rv.add_argument(
        "--source",
        choices=["auto", "twogis", "playwright"],
        default="auto",
        help="auto (API, fallback на Playwright) / twogis (только API) / playwright (только браузер)",
    )

    p_sv = sub.add_parser(
        "sync-venues",
        help="Пересборка venues из events(always, twogis-*). Safe-by-default: --force для записи",
    )
    p_sv.add_argument("--city", required=True, help="perm / sochi / all")
    p_sv.add_argument(
        "--force",
        action="store_true",
        help="Реально записать (без флага — dry-run). Перезапишет обогащения refresh-venues",
    )

    p_run = sub.add_parser("run", help="Полный пайплайн")
    p_run.add_argument("--city", required=True)
    p_run.add_argument("--source", help="Имя одного источника")
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Не писать в БД, не дедупить против БД",
    )
    p_run.add_argument(
        "--provider",
        choices=["gemini", "groq", "deepseek"],
        default=None,
        help="Override LLM_PROVIDER из .env (для разовых сравнений)",
    )
    p_run.add_argument(
        "--mode",
        choices=[
            "per_url", "batch_listing", "direct_api",
            "vk_events", "vk_posts", "telegram_posts", "generic",
        ],
        default=None,
        help="Override extraction_mode из seeds.yaml (для разовых тестов)",
    )

    args = parser.parse_args()

    if args.cmd == "discover":
        return asyncio.run(_cmd_discover(args))
    if args.cmd == "discover-sources":
        return asyncio.run(_cmd_discover_sources(args))
    if args.cmd == "export-venues":
        return _cmd_export_venues(args)
    if args.cmd == "refresh-venues":
        return asyncio.run(_cmd_refresh_venues(args))
    if args.cmd == "sync-venues":
        return _cmd_sync_venues(args)
    if args.cmd == "run":
        return asyncio.run(_cmd_run(args))
    return 1


if __name__ == "__main__":
    sys.exit(main())
