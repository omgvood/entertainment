"""Тесты JSON-LD экстрактора (без сети и LLM)."""

from parser.extraction import extract_jsonld_events


_HTML_WITH_EVENT = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "Квиз «Мозгобойня»",
  "startDate": "2026-06-15T19:00:00+03:00",
  "endDate": "2026-06-15T21:30:00+03:00",
  "image": "https://example.com/poster.jpg",
  "description": "Командная игра в баре.",
  "location": {
    "@type": "Place",
    "name": "Бар Соль",
    "address": {"@type": "PostalAddress", "streetAddress": "ул. Ленина, 10", "addressLocality": "Пермь"}
  },
  "offers": {"@type": "Offer", "price": "500", "priceCurrency": "RUB"},
  "organizer": {"@type": "Organization", "name": "Мозгобойня"}
}
</script>
</head><body>...</body></html>
"""

_HTML_GRAPH = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"WebSite","name":"site"},
  {"@type":"TheaterEvent","name":"Стендап вечер","startDate":"2026-07-01",
   "location":{"name":"Клуб","address":"Комсомольский пр., 1"},
   "offers":{"lowPrice":300,"highPrice":800}}
]}
</script>
</head><body></body></html>
"""

_HTML_NO_JSONLD = "<html><body><h1>Just a page</h1></body></html>"


def test_extract_single_event():
    events = extract_jsonld_events(_HTML_WITH_EVENT, "quiz")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "Квиз «Мозгобойня»"
    assert ev.type == "quiz"
    assert ev.date == "2026-06-15"
    assert ev.time_start == "19:00"
    assert ev.time_end == "21:30"
    assert ev.price_min == 500 and ev.price_max == 500
    assert ev.price_text == "от 500 ₽"
    assert ev.venue_name == "Бар Соль"
    assert ev.address == "ул. Ленина, 10, Пермь"
    assert ev.image_url == "https://example.com/poster.jpg"
    assert ev.organizer == "Мозгобойня"


def test_extract_from_graph_and_price_range():
    events = extract_jsonld_events(_HTML_GRAPH, "standup")
    assert len(events) == 1
    ev = events[0]
    assert ev.title == "Стендап вечер"
    assert ev.date == "2026-07-01"
    assert ev.time_start is None
    assert ev.price_min == 300 and ev.price_max == 800
    assert ev.price_text == "от 300 до 800 ₽"
    assert ev.address == "Комсомольский пр., 1"


def test_schema_type_overrides_default():
    """Подтип Schema.org (MusicEvent) → concert, игнорируя default_type."""
    html = """
    <script type="application/ld+json">
    {"@type":"MusicEvent","name":"Органный концерт","startDate":"2026-07-02T19:00:00+03:00",
     "location":{"name":"Органный зал","address":"ул. Ленина, 51Б"}}
    </script>
    """
    events = extract_jsonld_events(html, "other")
    assert len(events) == 1
    assert events[0].type == "concert"


def test_generic_event_falls_back_to_default():
    """Родовой @type=Event не имеет маппинга → берётся default_type."""
    html = """
    <script type="application/ld+json">
    {"@type":"Event","name":"Непонятное событие","startDate":"2026-07-02",
     "location":{"name":"Площадка","address":"ул. Мира, 1"}}
    </script>
    """
    events = extract_jsonld_events(html, "other")
    assert len(events) == 1
    assert events[0].type == "other"


def test_no_jsonld_returns_empty():
    assert extract_jsonld_events(_HTML_NO_JSONLD, "quiz") == []


def test_skips_event_without_required_fields():
    html = """
    <script type="application/ld+json">
    {"@type":"Event","name":"Безместное","startDate":"2026-06-15"}
    </script>
    """
    # Нет location → пропускаем (доберёт LLM).
    assert extract_jsonld_events(html, "quiz") == []


def test_missing_price_defaults():
    html = """
    <script type="application/ld+json">
    {"@type":"Event","name":"Бесплатный квиз","startDate":"2026-06-20",
     "location":{"name":"Лофт","address":"ул. Мира, 5"}}
    </script>
    """
    events = extract_jsonld_events(html, "quiz")
    assert len(events) == 1
    assert events[0].price_min == 0 and events[0].price_max == 0
    assert events[0].price_text == "уточняйте"
