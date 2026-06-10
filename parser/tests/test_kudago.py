"""Тесты маппинга KudaGo JSON → ParsedEvent (без сети)."""

from datetime import date

from parser.sources.kudago import (
    _map_category,
    _next_date,
    _parse_price,
    _item_to_event,
)


_TODAY = date(2026, 6, 10)


def test_map_category():
    assert _map_category(["concert", "festival"]) == "concert"
    assert _map_category(["festival"]) == "festival"
    assert _map_category(["cinema"]) == "other"
    assert _map_category([]) == "other"


def test_parse_price():
    assert _parse_price("от 1500 рублей") == (1500, 1500, "от 1500 рублей")
    assert _parse_price("от 500 до 2000 руб") == (500, 2000, "от 500 до 2000 руб")
    assert _parse_price("Бесплатно") == (0, 0, "бесплатно")
    assert _parse_price("") == (0, 0, "уточняйте")
    assert _parse_price(None) == (0, 0, "уточняйте")


def test_next_date_picks_upcoming():
    dates = [
        {"start_date": "2026-01-01", "start_time": "10:00:00"},  # прошлое
        {"start_date": "2026-07-05", "start_time": "19:30:00"},
        {"start_date": "2026-06-20", "start_time": "20:00:00"},
    ]
    assert _next_date(dates, _TODAY) == ("2026-06-20", "20:00")


def test_next_date_all_past():
    assert _next_date([{"start_date": "2020-01-01"}], _TODAY) == (None, None)


def test_item_to_event_full():
    item = {
        "id": 1,
        "title": "Концерт в Сочи",
        "dates": [{"start_date": "2026-06-20", "start_time": "20:00:00"}],
        "place": {"title": "Зал", "address": "ул. Морская, 1"},
        "price": "от 1500 рублей",
        "images": [{"image": "https://media.kudago.com/x.jpg"}],
        "categories": ["concert"],
        "site_url": "https://sochi.kudago.com/event/x/",
    }
    ev = _item_to_event(item, _TODAY)
    assert ev is not None
    assert ev.title == "Концерт в Сочи"
    assert ev.type == "concert"
    assert ev.date == "2026-06-20"
    assert ev.time_start == "20:00"
    assert ev.price_min == 1500
    assert ev.venue_name == "Зал"
    assert ev.address == "ул. Морская, 1"
    assert ev.image_url == "https://media.kudago.com/x.jpg"


def test_item_without_place_skipped():
    item = {
        "title": "Онлайн-событие",
        "dates": [{"start_date": "2026-06-20"}],
        "place": None,
        "site_url": "https://x",
    }
    assert _item_to_event(item, _TODAY) is None
