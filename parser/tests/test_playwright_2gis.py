"""Тесты Playwright-2ГИС: парсинг карточек заведений из фрагмента HTML (без сети, без браузера).

Фикстура воспроизводит структуру выдачи 2gis.ru/{city}/search/{query} по селекторам из
playwright_2gis (см. блок «СЕЛЕКТОРЫ 2ГИС — ЧИНИТЬ ТУТ»). Если селекторы поедут — обновить
здесь фикстуру вместе с константами в источнике.
"""

from parser.sources.playwright_2gis import parse_cards
from parser.validator import to_venue


# Три карточки: полная, без адреса (пропускается), дубль первой (дедуп внутри выдачи).
_HTML = """
<html><body>
  <div class="_z1qx2c">
    <div class="_1kqrd4hi">
      <span class="_lvwrwt">Космик</span>
      <div class="_klarpw">Пермь, ул. Спешилова, 114</div>
      <div class="_14quei">Мотовилихинский район</div>
      <img src="https://i.2gis.com/cosmic.jpg" />
    </div>
    <div class="_1kqrd4hi">
      <span class="_lvwrwt">Боулинг без адреса</span>
      <img src="https://i.2gis.com/x.jpg" />
    </div>
    <div class="_1kqrd4hi">
      <span class="_lvwrwt">Космик</span>
      <div class="_klarpw">Пермь, ул. Спешилова, 114</div>
    </div>
  </div>
</body></html>
"""


def test_parse_cards_extracts_venues():
    venues = parse_cards(_HTML, "bowling")
    # Карточка без адреса отброшена, дубль схлопнут → остаётся 1.
    assert len(venues) == 1
    v = venues[0]
    assert v.venue_name == "Космик"
    assert v.title == "Космик"
    assert v.date == "always"
    assert v.type == "bowling"
    assert v.address == "Пермь, ул. Спешилова, 114"
    assert v.district == "Мотовилихинский район"
    assert v.image_url == "https://i.2gis.com/cosmic.jpg"
    assert v.price_min == 0 and v.price_max == 0


def test_parse_cards_empty():
    assert parse_cards("<html><body></body></html>", "bowling") == []


def test_to_venue_maps_parsed_event():
    parsed = parse_cards(_HTML, "bowling")[0]
    venue = to_venue(parsed, "perm", "playwright")
    assert venue.id == "perm-kosmik"
    assert venue.city == "perm"
    assert venue.name == "Космик"
    assert venue.type == "bowling"
    assert venue.source == "playwright"
    assert venue.district == "Мотовилихинский район"
