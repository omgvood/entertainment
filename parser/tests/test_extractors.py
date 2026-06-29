"""Тесты для LLM extractors (mock-тесты без реальных API вызовов)."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from parser.extraction import DeepSeekExtractor
from parser.extraction._errors import is_rate_limit
from parser.extraction.base import RateLimitError
from parser.extraction.groq_extractor import GroqExtractor
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


# --- Groq 413 «Request too large … TPM» = rate-limit (фолбэк на Gemini, без разбиения) ---

# Реальный текст ошибки Groq free-tier: фикс. оверхед (system ~2k + max_tokens) сам по себе
# превышает 8K TPM, поэтому даже крошечный вход даёт 413 — это лимит, а не размер входа.
_GROQ_TPM_413 = (
    "Error code: 413 - {'error': {'message': 'Request too large for model "
    "`openai/gpt-oss-120b` in organization `org_x` service tier `on_demand` on tokens per "
    "minute (TPM): Limit 8000, Requested 10251, please reduce your message size and try "
    "again.', 'type': 'tokens', 'code': 'rate_limit_exceeded'}}"
)


def test_is_rate_limit_groq_tpm_413():
    """TPM-413 классифицируется как rate-limit → уйдёт в ретрай/фолбэк, а не в ExtractorError."""
    e = Exception(_GROQ_TPM_413)
    e.status_code = 413  # type: ignore[attr-defined]
    assert is_rate_limit(e) is True
    # Достаточно и одного текста без статус-кода (SDK мог обернуть без него).
    assert is_rate_limit(Exception(_GROQ_TPM_413)) is True


@pytest.mark.asyncio
async def test_groq_extract_many_tpm_413_raises_rate_limit():
    """extract_many на TPM-413 поднимает RateLimitError (а не ExtractorError) → фолбэк сработает."""
    extractor = GroqExtractor(api_key="mock-key")

    exc = Exception(_GROQ_TPM_413)
    exc.status_code = 413  # type: ignore[attr-defined]

    with patch.object(
        extractor.client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.side_effect = exc

        with pytest.raises(RateLimitError):
            await extractor.extract_many("=== POST https://x ===\nпост", "https://x")


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
