"""Тесты для LLM extractors (mock-тесты без реальных API вызовов)."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from parser.extraction import DeepSeekExtractor
from parser.models import ParsedEvent


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
