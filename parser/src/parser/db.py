"""Запись событий в Postgres через Supabase service_role_key (обходит RLS)."""

from __future__ import annotations

from dataclasses import dataclass

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
    """Upsert по первичному ключу id. Возвращает статистику."""
    stats = WriteStats()
    if not events:
        return stats

    # supabase-py upsert работает пачкой. Чтобы получить точный inserted vs updated —
    # это не отдаёт PostgREST на default-настройках. Считаем всё как «записано».
    payload = [e.model_dump(mode="json") for e in events]
    try:
        resp = client.table("events").upsert(payload, on_conflict="id").execute()
        stats.inserted = len(resp.data or [])
        log.info("db.upsert.ok", count=stats.inserted)
    except Exception as exc:  # noqa: BLE001
        stats.errors = len(events)
        log.error("db.upsert.failed", error=str(exc), count=len(events))
        raise

    return stats
