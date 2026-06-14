"""Запись событий в Postgres через Supabase service_role_key (обходит RLS)."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import structlog
from supabase import Client, create_client

from .models import EventRow, Venue


log = structlog.get_logger()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_client(url: str, service_key: str) -> Client:
    """Создаёт клиент с правами service_role (запись разрешена)."""
    return create_client(url, service_key)


@dataclass
class WriteStats:
    inserted: int = 0
    updated: int = 0
    errors: int = 0


def upsert_events(client: Client, events: list[EventRow]) -> WriteStats:
    """Upsert по slug (естественный уникальный ключ события). Возвращает статистику."""
    stats = WriteStats()
    if not events:
        return stats

    payload = [e.model_dump(mode="json", exclude={"event_url"}) for e in events]
    try:
        resp = client.table("events").upsert(payload, on_conflict="slug").execute()
        stats.inserted = len(resp.data or [])
        log.info("db.upsert.ok", count=stats.inserted)
    except Exception as exc:  # noqa: BLE001
        stats.errors = len(events)
        log.error("db.upsert.failed", error=str(exc), count=len(events))
        raise

    return stats


def upsert_venues(
    client: Client, venues: list[Venue], *, insert_only: bool = False
) -> WriteStats:
    """Upsert площадок в таблицу venues по conflict id.

    Стратегия защиты ручного ввода: строки с source='manual' — primary source of truth,
    их автосбор (twogis/playwright) НЕ перезаписывает. Сначала выясняем, какие из id уже
    помечены manual, и исключаем их из payload.

    insert_only=True → ON CONFLICT DO NOTHING (для bootstrap: не перетирать обогащения,
    которые мог проставить refresh-venues).
    """
    stats = WriteStats()
    if not venues:
        return stats

    ids = [v.id for v in venues]
    manual_ids: set[str] = set()
    for i in range(0, len(ids), 100):
        chunk = ids[i : i + 100]
        resp = (
            client.table("venues")
            .select("id")
            .eq("source", "manual")
            .in_("id", chunk)
            .execute()
        )
        manual_ids.update(r["id"] for r in resp.data or [])

    now = _utcnow()
    payload = [
        {**v.model_dump(), "updated_at": now} for v in venues if v.id not in manual_ids
    ]
    if not payload:
        log.info("db.venues.upsert.skipped_all_manual", manual=len(manual_ids))
        return stats

    try:
        resp = (
            client.table("venues")
            .upsert(payload, on_conflict="id", ignore_duplicates=insert_only)
            .execute()
        )
        stats.inserted = len(resp.data or [])
        log.info(
            "db.venues.upsert.ok",
            written=stats.inserted,
            skipped_manual=len(manual_ids),
            insert_only=insert_only,
        )
    except Exception as exc:  # noqa: BLE001
        stats.errors = len(payload)
        log.error("db.venues.upsert.failed", error=str(exc), count=len(payload))
        raise

    return stats


def event_row_to_venue(row: dict, source: str = "twogis") -> Venue:
    """Строка таблицы events (date='always') → Venue. id берём как есть (он уже {city}-{slug}).

    Адаптер между моделями хранения (не валидация). Нормализуем source: events.source =
    'twogis-bowling'/'twogis-billiards'/..., а venue.source = 'twogis' (огрублённая конвенция
    venues; см. upsert_venues manual-guard).
    """
    return Venue(
        id=row["id"],
        city=row["city"],
        name=row["venue_name"],
        type=row["type"],
        address=row.get("address") or None,
        district=row.get("district"),
        image_url=row.get("image_url"),
        source=source,
    )


def sync_venues_from_events(
    client: Client,
    city: str,
    source_like: str = "twogis-%",
    *,
    dry_run: bool = False,
    insert_only: bool = False,
) -> WriteStats:
    """Импорт venues из постоянных мест в events (date='always', twogis-*).

    dry_run — посчитать, но не писать. insert_only — ON CONFLICT DO NOTHING (для bootstrap).
    Используется CLI-командой sync-venues (полная перезапись) и bootstrap (insert-only).
    """
    resp = (
        client.table("events")
        .select("id,city,venue_name,type,address,district,image_url")
        .eq("city", city)
        .eq("date", "always")
        .like("source", source_like)
        .execute()
    )
    venues = [event_row_to_venue(r) for r in (resp.data or [])]
    if dry_run:
        log.info("db.venues.sync.dry_run", city=city, would_import=len(venues))
        return WriteStats()
    return upsert_venues(client, venues, insert_only=insert_only)


def bootstrap_venues_if_empty(client: Client, city: str) -> WriteStats | None:
    """BOOTSTRAP-only: засеять venues из events ТОЛЬКО если для ЭТОГО ГОРОДА нет ни одной строки.

    Если у города уже есть площадки — НЕ трогаем (бережём обогащения refresh-venues).
    Проверка per-city: после сбоя perm=27/sochi=0 даст seed только для sochi.
    INSERT-ONLY: даже при ошибочном срабатывании не перетирает существующие строки.
    Имя намеренно явное — не синхронизация и не обновление, только первичный seed.
    """
    # Existence-check через LIMIT 1 (не count="exact": в схеме venues нет soft-delete,
    # .eq(city) уже скоупит — считать все строки незачем).
    resp = client.table("venues").select("id").eq("city", city).limit(1).execute()
    if resp.data:
        return None
    vstats = sync_venues_from_events(client, city, insert_only=True)
    log.info(
        "db.venues.bootstrap.completed",
        city=city,
        source="events(always)",
        reason="empty_table_recovery",
        inserted=vstats.inserted,
    )
    return vstats


def fetch_events_by_ids(client: Client, ids: list[str]) -> list[EventRow]:
    """Существующие события с указанными id (для кросс-источникового merge).

    id = city+slug, поэтому уже включает город. Возвращает распарсенные EventRow.
    """
    if not ids:
        return []
    rows: list[EventRow] = []
    unique = list({i for i in ids if i})
    for i in range(0, len(unique), 100):
        chunk = unique[i : i + 100]
        resp = client.table("events").select("*").in_("id", chunk).execute()
        for r in resp.data or []:
            try:
                rows.append(EventRow(**r))
            except Exception as exc:  # noqa: BLE001 — битую строку из БД просто пропускаем
                log.warning("db.fetch_ids.row_invalid", id=r.get("id"), error=str(exc))
    return rows


def cleanup_old_events(client: Client, city: str, days_to_keep: int = 1) -> int:
    """Удаляет события с истёкшей датой (не 'always') старше days_to_keep дней.

    Возвращает количество удалённых строк.
    """
    cutoff = (date.today() - timedelta(days=days_to_keep)).isoformat()
    try:
        resp = (
            client.table("events")
            .delete()
            .eq("city", city)
            .neq("date", "always")
            .lt("date", cutoff)
            .execute()
        )
        deleted = len(resp.data or [])
        if deleted:
            log.info("db.cleanup.ok", city=city, deleted=deleted, cutoff=cutoff)
        return deleted
    except Exception as exc:  # noqa: BLE001
        log.warning("db.cleanup.failed", city=city, error=str(exc))
        return 0


def sync_source_events(
    client: Client, source: str, city: str, current_ids: set[str]
) -> int:
    """Удаляет будущие события источника, не вернувшиеся в текущем прогоне.

    Вызывать только для источников с full_snapshot=True.
    Если current_ids пуст (ошибка сети / API вернул 0) — ничего не удаляем,
    логируем WARNING для ручной проверки.
    """
    if not current_ids:
        log.warning(
            "db.sync_source.skipped_empty",
            source=source,
            city=city,
            reason="пустой current_ids — возможный сбой парсинга, синхронизация пропущена",
        )
        return 0

    today = date.today().isoformat()
    try:
        resp = (
            client.table("events")
            .delete()
            .eq("source", source)
            .eq("city", city)
            .neq("date", "always")
            .gte("date", today)
            .not_.in_("id", list(current_ids))
            .execute()
        )
        deleted = len(resp.data or [])
        if deleted:
            log.info(
                "db.sync_source.ok",
                source=source,
                city=city,
                deleted=deleted,
                kept=len(current_ids),
            )
        return deleted
    except Exception as exc:  # noqa: BLE001
        log.warning("db.sync_source.failed", source=source, city=city, error=str(exc))
        return 0


# --- raw_documents (Ingestion): сырьё для перепарса + дедуп вместо parse_state ---

def get_raw_document_hash(client: Client, url: str) -> str | None:
    """Хеш последнего сохранённого контента для url (или None)."""
    resp = (
        client.table("raw_documents").select("hash").eq("url", url).limit(1).execute()
    )
    return resp.data[0]["hash"] if resp.data else None


def save_raw_document(
    client: Client,
    source: str,
    url: str,
    content: str,
    content_type: str = "html",
    content_hash: str | None = None,
) -> str:
    """Архивирует сырьё (upsert по url) и возвращает его хеш."""
    h = content_hash or hashlib.sha256(content.encode("utf-8")).hexdigest()
    client.table("raw_documents").upsert(
        {
            "source": source,
            "url": url,
            "content": content,
            "content_type": content_type,
            "hash": h,
            "fetched_at": _utcnow(),
        },
        on_conflict="url",
    ).execute()
    return h


def cleanup_old_raw_documents(client: Client, days_to_keep: int = 120) -> int:
    """Удаляет сырьё старше days_to_keep дней (TTL). Возвращает число удалённых строк."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_to_keep)).isoformat()
    try:
        resp = (
            client.table("raw_documents").delete().lt("fetched_at", cutoff).execute()
        )
        deleted = len(resp.data or [])
        if deleted:
            log.info("db.raw_cleanup.ok", deleted=deleted, cutoff=cutoff)
        return deleted
    except Exception as exc:  # noqa: BLE001
        log.warning("db.raw_cleanup.failed", error=str(exc))
        return 0


# --- source_health (Analytics): лог запусков + агрегат ---

def record_source_health(
    client: Client,
    source: str,
    city: str,
    *,
    events_found: int,
    errors: int,
    duration_sec: float,
    last_error: str | None = None,
) -> None:
    """Пишет строку в лог source_health и пересчитывает агрегат source_health_agg."""
    try:
        client.table("source_health").insert(
            {
                "source": source,
                "city": city,
                "run_at": _utcnow(),
                "events_found": events_found,
                "errors": errors,
                "duration_sec": round(duration_sec, 3),
                "last_error": last_error,
            }
        ).execute()

        rows = (
            client.table("source_health")
            .select("events_found,errors,run_at")
            .eq("source", source)
            .eq("city", city)
            .execute()
            .data
        )
        total = len(rows)
        if not total:
            return
        successful = [r for r in rows if r["errors"] == 0]
        client.table("source_health_agg").upsert(
            {
                "source": source,
                "city": city,
                "last_run": max(r["run_at"] for r in rows),
                "last_success": max((r["run_at"] for r in successful), default=None),
                "avg_events": round(sum(r["events_found"] for r in rows) / total, 2),
                "success_rate": round(len(successful) / total, 3),
                "total_errors": sum(r["errors"] for r in rows),
            },
            on_conflict="source,city",
        ).execute()
    except Exception as exc:  # noqa: BLE001
        log.warning("db.source_health.failed", source=source, city=city, error=str(exc))


# --- source_quality (Analytics): ценность источника (доля уникальных событий) ---

def record_source_quality(
    client: Client, city: str, per_source: dict[str, tuple[int, int]]
) -> None:
    """Снимок ценности источников за сегодня.

    per_source: {source_name: (events_found, unique_events)}, где unique = не проигравшие
    кросс-источниковый merge другому источнику. Низкий ratio → источник дублирует другие.
    """
    try:
        today = date.today().isoformat()
        payload = [
            {
                "source": source,
                "city": city,
                "snapshot_date": today,
                "events_found": found,
                "unique_events": unique,
                "unique_events_ratio": round(unique / found, 3) if found else None,
            }
            for source, (found, unique) in per_source.items()
            if found
        ]
        if payload:
            client.table("source_quality").upsert(
                payload, on_conflict="source,city,snapshot_date"
            ).execute()
            log.info("db.source_quality.ok", city=city, sources=len(payload))
    except Exception as exc:  # noqa: BLE001
        log.warning("db.source_quality.failed", city=city, error=str(exc))


# --- coverage_stats (Analytics): ежедневный снимок покрытия по категориям ---

def record_coverage(client: Client, city: str) -> None:
    """Снимок «сколько событий по каждому типу» для города на сегодня."""
    try:
        rows = client.table("events").select("type").eq("city", city).execute().data
        counts = Counter(r["type"] for r in rows)
        today = date.today().isoformat()
        payload = [
            {"city": city, "category": t, "count": c, "snapshot_date": today}
            for t, c in counts.items()
        ]
        if payload:
            client.table("coverage_stats").upsert(
                payload, on_conflict="city,category,snapshot_date"
            ).execute()
            log.info("db.coverage.ok", city=city, categories=len(payload))
    except Exception as exc:  # noqa: BLE001
        log.warning("db.coverage.failed", city=city, error=str(exc))
