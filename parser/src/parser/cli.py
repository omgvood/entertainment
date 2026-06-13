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

from .config import LlmProvider, Settings, load_seeds
from .db import make_client
from .discovery import ListingDiscovery, SitemapDiscovery
from .extraction import DeepSeekExtractor, GeminiExtractor, GroqExtractor, LLMExtractor
from .pipeline import run_city


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
    extractor = _make_extractor(settings, provider)
    print(f"LLM provider: {provider}, model: {settings.model_for(provider)}", file=sys.stderr)

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
    if args.cmd == "run":
        return asyncio.run(_cmd_run(args))
    return 1


if __name__ == "__main__":
    sys.exit(main())
