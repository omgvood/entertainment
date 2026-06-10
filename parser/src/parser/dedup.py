"""Дедуп: не звать LLM повторно.

- per_url:       skip URL, который уже есть в events.source_url (filter_new_urls).
- batch_listing: skip весь LLM-вызов, если HTML листинга не менялся с прошлого прогона
                 (get_source_hash / set_source_hash по таблице parse_state).
"""

from __future__ import annotations

from datetime import datetime, timezone

from supabase import Client


def filter_new_urls(supabase: Client, candidate_urls: list[str]) -> list[str]:
    """Возвращает только те URL, которых ещё нет в таблице events."""
    if not candidate_urls:
        return []

    resp = (
        supabase.table("events")
        .select("source_url")
        .in_("source_url", candidate_urls)
        .execute()
    )
    existing = {row["source_url"] for row in resp.data}
    return [u for u in candidate_urls if u not in existing]


def get_source_hash(supabase: Client, city: str, source: str) -> str | None:
    """Возвращает сохранённый content_hash листинга (city, source) или None."""
    resp = (
        supabase.table("parse_state")
        .select("content_hash")
        .eq("city", city)
        .eq("source", source)
        .limit(1)
        .execute()
    )
    if resp.data:
        return resp.data[0]["content_hash"]
    return None


def set_source_hash(supabase: Client, city: str, source: str, content_hash: str) -> None:
    """Сохраняет (upsert) content_hash листинга для пары (city, source)."""
    supabase.table("parse_state").upsert(
        {
            "city": city,
            "source": source,
            "content_hash": content_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="city,source",
    ).execute()
