"""Дедуп: не звать LLM повторно.

- per_url:       skip URL, который уже есть в events.source_url (filter_new_urls).
- batch_listing: skip весь LLM-вызов, если HTML листинга не менялся с прошлого прогона
                 (хеш контента в raw_documents — см. db.get_raw_document_hash / save_raw_document).
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
