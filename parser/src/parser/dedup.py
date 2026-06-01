"""Дедуп: какие URL уже есть в БД (по source_url) и не звать LLM повторно.

Стратегия v1 — простая: skip URL, который уже есть в events.source_url.
В будущем (когда контент будет меняться) — добавим content_hash и переизвлечение при изменении.
"""

from __future__ import annotations

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
