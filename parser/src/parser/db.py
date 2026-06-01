"""Запись событий в Postgres через Supabase service_role_key (обходит RLS)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import structlog
from supabase import Client, create_client

from .models import EventRow


log = structlog.get_logger()


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

    payload = [e.model_dump(mode="json") for e in events]
    try:
        resp = client.table("events").upsert(payload, on_conflict="slug").execute()
        stats.inserted = len(resp.data or [])
        log.info("db.upsert.ok", count=stats.inserted)
    except Exception as exc:  # noqa: BLE001
        stats.errors = len(events)
        log.error("db.upsert.failed", error=str(exc), count=len(events))
        raise

    return stats


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
