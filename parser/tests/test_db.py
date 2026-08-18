"""Тесты чистых функций db.py (без сети/клиента)."""

from unittest.mock import MagicMock

from parser.db import event_row_to_venue, sync_source_events


# --- sync_source_events ---

def _mock_client(deleted_rows: list) -> tuple[MagicMock, MagicMock]:
    """Мок цепочки client.table(...).delete().eq()...execute()."""
    client = MagicMock()
    execute = MagicMock(return_value=MagicMock(data=deleted_rows))
    chain = client.table.return_value.delete.return_value
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.gte.return_value = chain
    chain.not_ = MagicMock()
    chain.not_.in_.return_value = chain
    chain.execute = execute
    return client, execute


def test_sync_source_events_deletes_stale():
    client, execute = _mock_client([{"id": "sochi-old-quiz"}])
    deleted = sync_source_events(client, "quizplease", "sochi", {"sochi-new-1", "sochi-new-2"})
    assert deleted == 1
    execute.assert_called_once()


def test_sync_source_events_skips_empty_ids():
    client, execute = _mock_client([])
    deleted = sync_source_events(client, "quizplease", "sochi", set())
    assert deleted == 0
    execute.assert_not_called()


def test_sync_source_events_returns_zero_on_exception():
    client = MagicMock()
    chain = client.table.return_value.delete.return_value
    chain.eq.return_value = chain
    chain.neq.return_value = chain
    chain.gte.return_value = chain
    chain.not_ = MagicMock()
    chain.not_.in_.return_value = chain
    chain.execute.side_effect = RuntimeError("connection error")
    deleted = sync_source_events(client, "quizplease", "sochi", {"sochi-id-1"})
    assert deleted == 0


def test_sync_source_events_nothing_stale():
    client, execute = _mock_client([])
    deleted = sync_source_events(client, "quizplease", "sochi", {"sochi-id-1", "sochi-id-2"})
    assert deleted == 0
    execute.assert_called_once()


def test_event_row_to_venue_maps_fields():
    row = {
        "id": "perm-u-trofima",
        "city": "perm",
        "venue_name": "У Трофима",
        "type": "billiards",
        "address": "Пермь, Пожарная улица, 14 к3",
        "district": "Дзержинский район",
        "image_url": "https://example.com/photo.jpg",
    }
    v = event_row_to_venue(row)
    assert v.id == "perm-u-trofima"  # id берётся как есть
    assert v.city == "perm"
    assert v.name == "У Трофима"  # venue_name → name
    assert v.type == "billiards"
    assert v.address == "Пермь, Пожарная улица, 14 к3"
    assert v.district == "Дзержинский район"
    assert v.image_url == "https://example.com/photo.jpg"
    assert v.source == "twogis"  # огрублённая конвенция venues


def test_event_row_to_venue_optional_fields_default_none():
    row = {
        "id": "sochi-relax",
        "city": "sochi",
        "venue_name": "Relax",
        "type": "bowling",
        "address": "",      # пустая строка → None
        "district": None,
        "image_url": None,
    }
    v = event_row_to_venue(row)
    assert v.address is None
    assert v.district is None
    assert v.image_url is None
    assert v.source == "twogis"


def test_event_row_to_venue_source_override():
    row = {
        "id": "perm-x",
        "city": "perm",
        "venue_name": "X",
        "type": "karting",
    }
    v = event_row_to_venue(row, source="manual")
    assert v.source == "manual"
    assert v.address is None  # row.get отсутствующих полей → None


# --- dedup_candidates ---

from parser.db import fetch_events_for_dedup, record_dedup_candidates
from parser.fuzzy import PairScore, ScoredPair
from parser.models import ParsedEvent
from parser.validator import to_event_row


def _event(title: str, source: str = "vk-posts"):
    p = ParsedEvent(
        title=title, type="other", date="2026-08-16", time_start="14:00",
        price_min=0, price_max=0, price_text="уточняйте",
        address="ул. Тест, 1", venue_name="Сквер",
    )
    return to_event_row(p, "perm", "http://u", source)


def test_fetch_events_for_dedup_queries_unique_real_dates():
    """'always' и повторы отбрасываются: площадки не матчим, лишних запросов не делаем."""
    client = MagicMock()
    chain = client.table.return_value.select.return_value
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    fetch_events_for_dedup(client, "perm", ["2026-08-16", "2026-08-16", "always"])
    assert chain.in_.call_args.args == ("date", ["2026-08-16"])


def test_fetch_events_for_dedup_without_real_dates_makes_no_query():
    client = MagicMock()
    assert fetch_events_for_dedup(client, "perm", ["always"]) == []
    client.table.assert_not_called()


def test_record_dedup_candidates_orders_pair_ids():
    """event_id_a — лексикографически меньший: иначе UNIQUE(a,b) пропустит зеркальную пару."""
    client = MagicMock()
    a = _event("Ярмарка")           # perm-yarmarka-2026-08-16
    b = _event("Акция Обнимака")    # perm-aktsiya-obnimaka-2026-08-16 — лексикографически меньше
    record_dedup_candidates(client, "perm", [ScoredPair(a, b, PairScore(0.97, 1.0, 1.0, "ok"))], 0.95)
    payload = client.table.return_value.upsert.call_args.args[0]
    assert payload[0]["event_id_a"] == b.id
    assert payload[0]["event_id_b"] == a.id
    assert payload[0]["decision"] == "auto_merge"


def test_record_dedup_candidates_marks_grey_zone():
    """score ниже порога слияния → строка помечается candidate, а не auto_merge."""
    client = MagicMock()
    pair = ScoredPair(_event("Ярмарка"), _event("Акция Обнимака"), PairScore(0.80, 0.8, 1.0, "ok"))
    record_dedup_candidates(client, "perm", [pair], 0.95)
    payload = client.table.return_value.upsert.call_args.args[0]
    assert payload[0]["decision"] == "candidate"


def test_record_dedup_candidates_no_pairs_no_query():
    client = MagicMock()
    record_dedup_candidates(client, "perm", [], 0.95)
    client.table.assert_not_called()
