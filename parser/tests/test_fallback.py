"""Тесты FallbackExtractor + with_retry: фолбэк на rate-limit, проброс контент-ошибок."""

from unittest.mock import AsyncMock, patch

import pytest

from parser.extraction.base import ExtractorError, LLMExtractor, RateLimitError
from parser.extraction.fallback import FallbackExtractor
from parser.extraction.retry import with_retry
from parser.models import ParsedEvent


def _event(title="Тест") -> ParsedEvent:
    return ParsedEvent(
        title=title, type="quiz", date="2026-07-10", time_start="19:00",
        venue_name="Клуб", address="ул. Тест, 1", price_min=0, price_max=0,
        price_text="бесплатно",
    )


class _FakeExtractor(LLMExtractor):
    """Экстрактор-заглушка: либо кидает заданное исключение, либо возвращает событие."""

    def __init__(self, *, raises: Exception | None = None, title: str = "ok") -> None:
        self.raises = raises
        self.title = title
        self.calls = 0

    async def extract(self, html, source_url):
        self.calls += 1
        if self.raises:
            raise self.raises
        return _event(self.title)

    async def extract_many(self, html, source_url):
        self.calls += 1
        if self.raises:
            raise self.raises
        return [_event(self.title)]


@pytest.mark.asyncio
async def test_fallback_on_rate_limit_uses_next_provider():
    primary = _FakeExtractor(raises=RateLimitError("429"))
    secondary = _FakeExtractor(title="from-groq")
    fb = FallbackExtractor([("gemini", primary), ("groq", secondary)], retry_attempts=1)

    events = await fb.extract_many("doc", "https://t.me/x/1")

    assert events[0].title == "from-groq"
    assert primary.calls == 1 and secondary.calls == 1
    assert fb._preferred_idx == 1  # индекс сдвинулся на groq


@pytest.mark.asyncio
async def test_content_error_propagates_without_fallback():
    primary = _FakeExtractor(raises=ExtractorError("битый JSON"))
    secondary = _FakeExtractor(title="from-groq")
    fb = FallbackExtractor([("gemini", primary), ("groq", secondary)], retry_attempts=1)

    with pytest.raises(ExtractorError, match="битый JSON"):
        await fb.extract_many("doc", "https://t.me/x/1")
    assert secondary.calls == 0  # фолбэк не звался


@pytest.mark.asyncio
async def test_all_providers_exhausted_raises_rate_limit():
    a = _FakeExtractor(raises=RateLimitError("429"))
    b = _FakeExtractor(raises=RateLimitError("503"))
    fb = FallbackExtractor([("gemini", a), ("groq", b)], retry_attempts=1)

    with pytest.raises(RateLimitError):
        await fb.extract_many("doc", "https://t.me/x/1")
    assert fb._preferred_idx == 2  # дорос до len → пул помечен исчерпанным

    # Следующий вызов short-circuit'ит без обращения к провайдерам.
    a.calls = b.calls = 0
    with pytest.raises(RateLimitError, match="исчерпали лимиты"):
        await fb.extract_many("doc", "https://t.me/x/2")
    assert a.calls == 0 and b.calls == 0


@pytest.mark.asyncio
async def test_with_retry_recovers_after_one_rate_limit():
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RateLimitError("429 first")
        return "ok"

    with patch("parser.extraction.retry.asyncio.sleep", new_callable=AsyncMock):
        result = await with_retry(factory, attempts=3)

    assert result == "ok"
    assert calls["n"] == 2


# Реальный текст ошибки Gemini free-tier при исчерпании суточной квоты (см. логи 02.07).
_DAILY_QUOTA_MSG = (
    "Gemini rate-limit для https://vk.com/x: 429 RESOURCE_EXHAUSTED. "
    "Quota exceeded for metric: generate_content_free_tier_requests, "
    "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier"
)


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_daily_quota():
    # Суточная квота не восстановится через секунды → ретраить нельзя: factory зовётся 1 раз.
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        raise RateLimitError(_DAILY_QUOTA_MSG)

    with patch("parser.extraction.retry.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        with pytest.raises(RateLimitError):
            await with_retry(factory, attempts=3)

    assert calls["n"] == 1  # без повторов, несмотря на attempts=3
    sleep_mock.assert_not_called()  # без backoff-задержек


@pytest.mark.asyncio
async def test_daily_quota_switches_provider_immediately():
    # Даже при retry_attempts=3 выгоревший по суточной квоте провайдер зовётся один раз,
    # затем сразу фолбэк на следующего.
    primary = _FakeExtractor(raises=RateLimitError(_DAILY_QUOTA_MSG))
    secondary = _FakeExtractor(title="from-groq")
    fb = FallbackExtractor([("gemini", primary), ("groq", secondary)], retry_attempts=3)

    with patch("parser.extraction.retry.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        events = await fb.extract_many("doc", "https://t.me/x/1")

    assert events[0].title == "from-groq"
    assert primary.calls == 1  # ни одного повтора на выгоревшем провайдере
    assert secondary.calls == 1
    sleep_mock.assert_not_called()
