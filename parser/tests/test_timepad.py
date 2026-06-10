"""Тесты маппинга Timepad JSON → ParsedEvent (без сети). Широкая афиша: тип по категории."""

import pytest

from parser.sources.timepad import (
    _item_to_event,
    _map_category,
    _parse_starts_at,
    _parse_ticket_types,
)


_SAMPLE_ITEM = {
    "id": 12345,
    "name": "Квиз «Эйнштейн party» в Перми",
    "starts_at": "2026-06-15T19:30:00+0500",
    "url": "https://exampleorg.timepad.ru/event/12345/",
    "poster_image": {"default_url": "https://example.com/poster.jpg"},
    "description_short": "Интеллектуальная игра для команд.",
    "location": {"city": "Пермь", "address": "ул. Ленина, 50"},
    "ticket_types": [{"price": 700}, {"price": 1200}],
    "categories": [{"id": 2335, "name": "Интеллектуальные игры", "tag": "intellekt"}],
    "organization": {"name": "Эйнштейн"},
}


def test_map_category():
    # ключ — id категории (в ответе событий tag отсутствует)
    assert _map_category([{"id": 2335}]) == "quiz"
    assert _map_category([{"id": 460}]) == "concert"
    assert _map_category([{"id": 452}]) == "business"  # ИТ
    assert _map_category([{"id": 453}]) == "education"  # психология
    # первая распознанная категория выигрывает (399 Красота → other, 459 Театры → theater)
    assert _map_category([{"id": 399}, {"id": 459}]) == "theater"
    # ничего не распознано → other
    assert _map_category([{"id": 399}]) == "other"
    assert _map_category([]) == "other"
    assert _map_category({}) == "other"  # бывает пустой dict вместо списка


def test_item_to_event_type_from_category():
    ev = _item_to_event(_SAMPLE_ITEM, "Пермь")
    assert ev.type == "quiz"  # из categories[].tag = intellekt
    assert ev.title == "Квиз «Эйнштейн party» в Перми"
    assert ev.date == "2026-06-15"
    assert ev.time_start == "19:30"
    assert ev.price_min == 700 and ev.price_max == 1200
    assert ev.price_text == "от 700 до 1200 ₽"
    assert ev.address == "Пермь, ул. Ленина, 50"
    assert ev.image_url == "https://example.com/poster.jpg"
    assert ev.organizer == "Эйнштейн"


def test_item_to_event_concert():
    item = dict(_SAMPLE_ITEM)
    item["categories"] = [{"id": 460, "name": "Концерты"}]
    assert _item_to_event(item, "Сочи").type == "concert"


def test_item_no_categories_is_other():
    item = dict(_SAMPLE_ITEM)
    item["categories"] = []
    assert _item_to_event(item, "Пермь").type == "other"


def test_starts_at_date_only():
    assert _parse_starts_at("2026-07-01") == ("2026-07-01", None)


def test_starts_at_invalid():
    assert _parse_starts_at("not-a-date") == (None, None)


def test_ticket_types_empty_defaults():
    assert _parse_ticket_types(None) == (0, 0, "уточняйте")
    assert _parse_ticket_types([]) == (0, 0, "уточняйте")


def test_ticket_types_single_price():
    assert _parse_ticket_types([{"price": 500}]) == (500, 500, "от 500 ₽")


def test_item_missing_url_raises():
    item = dict(_SAMPLE_ITEM)
    del item["url"]
    with pytest.raises(ValueError):
        _item_to_event(item, "Пермь")
