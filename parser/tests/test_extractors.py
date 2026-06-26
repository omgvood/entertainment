"""Тесты для LLM extractors (mock-тесты без реальных API вызовов)."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from parser.extraction import DeepSeekExtractor
from parser.extraction._errors import is_rate_limit, is_request_too_large
from parser.extraction.base import ExtractorError
from parser.extraction.groq_extractor import GroqExtractor, _split_posts
from parser.models import ParsedEvent


def test_is_rate_limit_by_status_code():
    # groq/openai APIStatusError несёт .status_code
    e = Exception("rate")
    e.status_code = 429  # type: ignore[attr-defined]
    assert is_rate_limit(e) is True


def test_is_rate_limit_by_code():
    # google.genai.errors.APIError несёт .code
    e = Exception("server")
    e.code = 503  # type: ignore[attr-defined]
    assert is_rate_limit(e) is True


def test_is_rate_limit_by_substring():
    assert is_rate_limit(Exception("RESOURCE_EXHAUSTED for project")) is True
    assert is_rate_limit(Exception("model is overloaded, try later")) is True
    assert is_rate_limit(Exception("503 UNAVAILABLE")) is True


def test_is_rate_limit_false_for_content_error():
    e = Exception("invalid JSON: unexpected token")
    e.status_code = 400  # type: ignore[attr-defined]
    assert is_rate_limit(e) is False


# --- 413 Request too large: классификация и разбиение батча (GroqExtractor) ---


def test_is_request_too_large_by_status_code():
    e = Exception("oops")
    e.status_code = 413  # type: ignore[attr-defined]
    assert is_request_too_large(e) is True
    # 413 — не rate-limit: чинится разбиением, а не ретраем.
    assert is_rate_limit(e) is False


def test_is_request_too_large_by_substring():
    assert is_request_too_large(Exception("Request too large for model gpt-oss")) is True
    assert is_request_too_large(Exception("413 Request Entity Too Large")) is True
    assert is_request_too_large(Exception("invalid json")) is False


def _make_chunk(n: int) -> str:
    """Батч из n постов в формате pipeline (маркер «=== POST <url> ===» на пост)."""
    return "\n\n".join(f"=== POST https://vk.com/wall-1_{i} ===\nПост {i}" for i in range(n))


def test_split_posts_two_markers():
    h1, h2 = _split_posts(_make_chunk(2))  # type: ignore[misc]
    assert h1.count("=== POST ") == 1
    assert h2.count("=== POST ") == 1


def test_split_posts_three_markers():
    h1, h2 = _split_posts(_make_chunk(3))  # type: ignore[misc]
    # mid = 3 // 2 = 1 → первая половина 1 пост, вторая 2 поста.
    assert h1.count("=== POST ") == 1
    assert h2.count("=== POST ") == 2


def test_split_posts_ten_markers():
    text = _make_chunk(10)
    h1, h2 = _split_posts(text)  # type: ignore[misc]
    assert h1.count("=== POST ") == 5
    assert h2.count("=== POST ") == 5
    # Ни один пост не потерян, ни один не обрезан.
    assert h1.count("=== POST ") + h2.count("=== POST ") == text.count("=== POST ")
    for i in range(10):
        assert f"Пост {i}" in (h1 + h2)


def test_split_posts_single_marker_returns_none():
    assert _split_posts(_make_chunk(1)) is None
    assert _split_posts("<html>листинг без маркеров</html>") is None


def _json_response(events: list[dict]):
    resp = AsyncMock()
    resp.choices = [AsyncMock()]
    resp.choices[0].message.content = json.dumps({"events": events})
    return resp


@pytest.mark.asyncio
async def test_groq_extract_many_splits_on_413():
    """413 на полном батче → деление пополам, склейка результатов, лог groq.batch_split."""
    extractor = GroqExtractor(api_key="mock-key")

    too_large = Exception("Request too large")
    too_large.status_code = 413  # type: ignore[attr-defined]
    ev1 = {**_SAMPLE_EVENT_JSON, "title": "Пост 0"}
    ev2 = {**_SAMPLE_EVENT_JSON, "title": "Пост 1"}

    # Полный батч (2 поста) → 413; каждая половина (1 пост) → валидный JSON.
    side_effects = [too_large, _json_response([ev1]), _json_response([ev2])]

    with patch.object(
        extractor.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = side_effects

        events = await extractor.extract_many(_make_chunk(2), "https://vk.com/club1")

    assert {e.title for e in events} == {"Пост 0", "Пост 1"}
    assert mock_create.call_count == 3  # 1 полный (413) + 2 половины


@pytest.mark.asyncio
async def test_groq_extract_many_413_unsplittable_raises():
    """База рекурсии: один пост + 413 → ExtractorError, без рекурсии."""
    extractor = GroqExtractor(api_key="mock-key")

    too_large = Exception("Request too large")
    too_large.status_code = 413  # type: ignore[attr-defined]

    with patch.object(
        extractor.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = too_large

        with pytest.raises(ExtractorError, match="делить нечего"):
            await extractor.extract_many(_make_chunk(1), "https://vk.com/club1")

    assert mock_create.call_count == 1  # без рекурсивных вызовов


_SAMPLE_EVENT_JSON = {
    "title": "КвизПлиз",
    "type": "quiz",
    "category": None,
    "date": "2026-06-15",
    "time_start": "19:00",
    "time_end": "21:00",
    "price_min": 500,
    "price_max": 500,
    "price_text": "от 500 ₽",
    "address": "Ул. Клубная, 10",
    "venue_name": "КвизПлиз",
    "image_url": None,
}

_SAMPLE_BATCH_RESPONSE = {
    "events": [
        _SAMPLE_EVENT_JSON,
        {
            "title": "КвизПлиз Вторник",
            "type": "quiz",
            "category": None,
            "date": "2026-06-17",
            "time_start": "19:30",
            "time_end": "21:30",
            "price_min": 500,
            "price_max": 500,
            "price_text": "от 500 ₽",
            "address": "Ул. Клубная, 10",
            "venue_name": "КвизПлиз",
            "image_url": None,
        },
    ]
}


@pytest.mark.asyncio
async def test_deepseek_extractor_single_event():
    """Тест extract() с мок-ответом."""
    extractor = DeepSeekExtractor(api_key="mock-key")

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = json.dumps(_SAMPLE_EVENT_JSON)

    with patch.object(extractor.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        event = await extractor.extract(
            html="<html><body>Event</body></html>",
            source_url="https://example.com/event",
        )

    assert event.title == "КвизПлиз"
    assert event.type == "quiz"
    assert event.date == "2026-06-15"
    assert event.price_min == 500
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_deepseek_extractor_batch_events():
    """Тест extract_many() с мок-ответом."""
    extractor = DeepSeekExtractor(api_key="mock-key")

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = json.dumps(_SAMPLE_BATCH_RESPONSE)

    with patch.object(extractor.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        events = await extractor.extract_many(
            html="<html><body>Schedule</body></html>",
            source_url="https://example.com/schedule",
        )

    assert len(events) == 2
    assert events[0].title == "КвизПлиз"
    assert events[1].title == "КвизПлиз Вторник"
    mock_create.assert_called_once()


@pytest.mark.asyncio
async def test_deepseek_extractor_not_an_event():
    """Тест: если LLM вернул title='NOT_AN_EVENT', выбросить исключение."""
    extractor = DeepSeekExtractor(api_key="mock-key")

    not_event = _SAMPLE_EVENT_JSON.copy()
    not_event["title"] = "NOT_AN_EVENT"

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = json.dumps(not_event)

    with patch.object(extractor.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        from parser.extraction.base import ExtractorError

        with pytest.raises(ExtractorError, match="не-событие"):
            await extractor.extract(
                html="<html><body>Not an event</body></html>",
                source_url="https://example.com/not-event",
            )


@pytest.mark.asyncio
async def test_deepseek_extractor_invalid_json():
    """Тест: если LLM вернул не-JSON, выбросить исключение."""
    extractor = DeepSeekExtractor(api_key="mock-key")

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = "Invalid JSON {not valid"

    with patch.object(extractor.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response

        from parser.extraction.base import ExtractorError

        with pytest.raises(ExtractorError, match="не-JSON"):
            await extractor.extract(
                html="<html><body>Event</body></html>",
                source_url="https://example.com/event",
            )
