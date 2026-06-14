"""Тесты чистых функций db.py (без сети/клиента)."""

from parser.db import event_row_to_venue


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
