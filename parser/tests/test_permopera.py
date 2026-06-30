"""Тесты парсинга карточек permopera.ru (HTML-в-JSON) → ParsedEvent (без сети)."""

import json
from datetime import date
from pathlib import Path

from parser.sources.permopera import _next_month, parse_cards


_FX = Path(__file__).resolve().parent / "fixtures"
_DEFAULTS = dict(
    event_type="concert",
    venue_name="Пермский театр оперы и балета им. П. И. Чайковского",
    address="Пермь, ул. Петропавловская, 25а",
)


def _content() -> str:
    return json.loads((_FX / "permopera_playbill.json").read_text(encoding="utf-8"))["content"]


def test_parse_cards_extracts_events():
    # today в прошлом → все карточки фикстуры проходят фильтр прошедших
    events = parse_cards(_content(), today="2000-01-01", **_DEFAULTS)
    assert len(events) >= 1
    ev, source_url = events[0]
    assert ev.title
    assert ev.date and len(ev.date) == 10  # YYYY-MM-DD
    assert ev.time_start is None or len(ev.time_start) == 5  # HH:MM
    assert ev.venue_name == _DEFAULTS["venue_name"]
    assert ev.address == _DEFAULTS["address"]
    assert ev.type == "concert"
    assert ev.price_text == "по билетам"
    assert source_url.startswith("https://permopera.ru/playbills/playbill/")


def test_past_events_filtered():
    # today в далёком будущем → ни одна карточка не проходит
    assert parse_cards(_content(), today="2999-01-01", **_DEFAULTS) == []


def test_empty_html():
    assert parse_cards("<div></div>", today="2000-01-01", **_DEFAULTS) == []


def test_next_month():
    assert _next_month(date(2026, 7, 15)) == date(2026, 8, 1)
    assert _next_month(date(2026, 12, 3)) == date(2027, 1, 1)
