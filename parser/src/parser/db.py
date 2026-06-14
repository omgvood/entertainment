"""Запись событий в Postgres через Supabase service_role_key (обходит RLS)."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import structlog
from supabase import Client, create_client

from .models import EventRow


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


def cleanup_old_events(client: Client, city: str, days_to_keep: int = 7) -> int:
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
