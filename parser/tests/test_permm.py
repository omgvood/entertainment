"""Тесты маппинга permm.ru JSON → ParsedEvent (без сети)."""

import json
from pathlib import Path

from parser.sources.permm import _map_item, _parse_date, _resolve_image


_FX = Path(__file__).resolve().parent / "fixtures"
_DEFAULTS = dict(
    event_type="exhibition",
    venue_name="Музей современного искусства ПЕРММ",
    address="Пермь, бул. Гагарина, 24",
)


def _exhibitions() -> list[dict]:
    return json.loads((_FX / "permm_exhibitions.json").read_text(encoding="utf-8"))["data"]


def test_parse_date():
    assert _parse_date("11.06.2026") == "2026-06-11"
    assert _parse_date(None) is None
    assert _parse_date("") is None
    assert _parse_date("мусор") is None


def test_resolve_image():
    # обычный относительный путь → префикс домена
    assert _resolve_image("/storage/media/x.jpg") == "https://permm.ru/storage/media/x.jpg"
    # tilda-прокси со встроенным абсолютным URL → достаём встроенный
    proxied = "/storage/tilda/https://static.tildacdn.com/a/b.jpg"
    assert _resolve_image(proxied) == "https://static.tildacdn.com/a/b.jpg"
    # уже абсолютный
    assert _resolve_image("https://cdn.ru/p.jpg") == "https://cdn.ru/p.jpg"
    assert _resolve_image(None) is None


def test_exhibition_range_uses_ends_at():
    # Диапазонная выставка (starts != ends) → date = ends_at (стабильный slug, видна пока активна).
    raw = _exhibitions()[0]
    assert raw["starts_at"] == "11.06.2026" and raw["ends_at"] == "31.12.2026"
    ev = _map_item(raw, **_DEFAULTS)
    assert ev is not None
    assert ev.date == "2026-12-31"
    assert ev.venue_name == _DEFAULTS["venue_name"]
    assert ev.address == _DEFAULTS["address"]
    assert ev.type == "exhibition"
    assert ev.price_text == "по билетам"
    assert ev.image_url and ev.image_url.startswith("https://")


def test_single_day_uses_starts_at():
    # ends_at == starts_at → date = starts_at
    raw = {"title_extended": "Лекция", "starts_at": "20.06.2026", "ends_at": "20.06.2026"}
    ev = _map_item(raw, **_DEFAULTS)
    assert ev is not None and ev.date == "2026-06-20"


def test_null_ends_at_uses_starts_at():
    raw = {"title_extended": "Событие", "starts_at": "15.07.2026", "ends_at": None}
    ev = _map_item(raw, **_DEFAULTS)
    assert ev is not None and ev.date == "2026-07-15"


def test_skip_without_title_or_date():
    assert _map_item({"starts_at": "20.06.2026"}, **_DEFAULTS) is None
    assert _map_item({"title_extended": "X", "starts_at": None}, **_DEFAULTS) is None


def test_description_truncated_to_500():
    raw = {"title_extended": "Выставка", "starts_at": "20.06.2026", "sub_title_extended": "a" * 800}
    ev = _map_item(raw, **_DEFAULTS)
    assert ev is not None and len(ev.description) == 500
