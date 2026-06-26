"""Фильтр spurious date='always' от social/generic-источников.

LLM иногда ставит date='always' постам VK/Telegram/generic без явной даты (анонсы
выставок/«каждую пятницу»). Это не площадки — должно отбраковываться. Покрываем:
предикат is_spurious_always, guard в to_event_row (None), счётчик в _safe_to_event_row,
и наличие правила в промптах всех экстракторов.
"""

import pytest

from parser.models import ParsedEvent
from parser.pipeline import PipelineResult, _safe_to_event_row
from parser.validator import is_spurious_always, to_event_row


def _parsed(date: str, event_type: str = "exhibition") -> ParsedEvent:
    return ParsedEvent(
        title="Тестовое событие",
        type=event_type,
        date=date,
        price_min=0,
        price_max=0,
        price_text="бесплатно",
        address="ул. Тест, 1",
        venue_name="Площадка",
        image_url="https://example.com/i.jpg",
    )


@pytest.mark.parametrize(
    "date, event_type, source, expected",
    [
        # social/generic + always + не-площадка → spurious
        ("always", "exhibition", "vk-posts", True),
        ("always", "standup", "telegram-posts", True),
        ("always", "exhibition", "generic:domain.ru", True),
        ("always", "concert", "generic:domain.ru", True),
        ("always", "other", "generic", True),
        # площадки — 'always' легитимен даже из generic
        ("always", "bowling", "twogis-bowling", False),
        ("always", "bowling", "generic:domain.ru", False),
        ("always", "karting", "generic", False),
        ("always", "quest", "vk-posts", False),
        # не-social источник — не трогаем
        ("always", "exhibition", "twogis-bowling", False),
        ("always", "concert", "timepad", False),
        # конкретная дата — никогда не spurious
        ("2026-07-01", "concert", "vk-posts", False),
        ("2026-07-01", "exhibition", "telegram-posts", False),
    ],
)
def test_is_spurious_always(date, event_type, source, expected):
    assert is_spurious_always(date, event_type, source) is expected


def test_to_event_row_drops_spurious_always():
    """vk-posts + always + exhibition → None (отбраковано)."""
    assert to_event_row(_parsed("always"), "perm", "https://vk.com/wall-1_2", "vk-posts") is None


def test_to_event_row_keeps_venue_always():
    """generic-домен боулинга с always → строка создаётся."""
    row = to_event_row(_parsed("always", "bowling"), "perm", "https://x.ru", "generic:x.ru")
    assert row is not None
    assert row.date == "always"


def test_to_event_row_keeps_dated_post():
    row = to_event_row(_parsed("2026-07-01", "concert"), "perm", "https://vk.com/w", "vk-posts")
    assert row is not None
    assert row.date == "2026-07-01"


def test_safe_to_event_row_counts_skipped():
    """Wrapper инкрементирует skipped_always, когда to_event_row вернул None."""
    sub = PipelineResult()
    row = _safe_to_event_row(_parsed("always"), "perm", "https://vk.com/w", "vk-posts", sub)
    assert row is None
    assert sub.skipped_always == 1


def test_safe_to_event_row_passthrough():
    sub = PipelineResult()
    row = _safe_to_event_row(_parsed("2026-07-01"), "perm", "https://vk.com/w", "vk-posts", sub)
    assert row is not None
    assert sub.skipped_always == 0


def test_prompts_forbid_always_for_posts():
    """Правило запрета 'always' для постов должно жить в каждом промпте каждого экстрактора."""
    from parser.extraction import deepseek_extractor, gemini_extractor, groq_extractor

    phrase = "СТРОГО ЗАПРЕЩЁН"
    for mod in (deepseek_extractor, gemini_extractor, groq_extractor):
        assert phrase in mod._SYSTEM_PROMPT_SINGLE, mod.__name__
        assert phrase in mod._SYSTEM_PROMPT_BATCH, mod.__name__
