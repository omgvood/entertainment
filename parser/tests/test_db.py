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
