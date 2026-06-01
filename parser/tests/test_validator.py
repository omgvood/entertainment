"""Smoke-тесты валидатора и slug-генератора. Без сети, без LLM."""

from parser.models import ParsedEvent
from parser.validator import to_event_row, _make_slug


def test_slug_cyrillic_to_translit():
    s = _make_slug("Квиз «Мозгобойня» в баре Соль", "2026-06-03")
    assert s == "kviz-mozgoboynya-v-bare-sol-2026-06-03"


def test_slug_always_no_suffix():
    s = _make_slug("Боулинг «Капитан»", "always")
    assert s == "bouling-kapitan"


def test_to_event_row_fills_service_fields():
    parsed = ParsedEvent(
        title="QuizPlease «Классика»",
        type="quiz",
        date="2026-06-01",
        time_start="19:00",
        price_min=800,
        price_max=800,
        price_text="от 800 ₽",
        address="ул. Куйбышева, 14",
        venue_name="Бар Сезон",
        image_url="https://example.com/img.png",
    )
    row = to_event_row(parsed, "perm", "https://quizplease.ru/perm/123", "quizplease")
    assert row.city == "perm"
    assert row.id == f"perm-{row.slug}"
    assert row.source == "quizplease"
    assert row.source_url == "https://quizplease.ru/perm/123"
    assert row.parsed_at  # ISO timestamp


def test_parsed_event_rejects_bad_date():
    import pytest
    with pytest.raises(ValueError, match="date"):
        ParsedEvent(
            title="X",
            type="quiz",
            date="01.06.2026",  # неправильный формат
            price_min=0,
            price_max=0,
            price_text="бесплатно",
            address="X",
            venue_name="X",
            image_url="https://x",
        )


def test_parsed_event_rejects_price_min_gt_max():
    import pytest
    with pytest.raises(ValueError, match="price_max"):
        ParsedEvent(
            title="X",
            type="quiz",
            date="2026-06-01",
            price_min=1000,
            price_max=500,
            price_text="X",
            address="X",
            venue_name="X",
            image_url="https://x",
        )
