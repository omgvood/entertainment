"""Композитный экстрактор: ретрай + фолбэк между провайдерами при rate-limit.

Прозрачен для всех источников (VK/TG/batch/generic/per_url) — реализует тот же интерфейс
LLMExtractor, поэтому подставляется вместо одиночного экстрактора без правок в pipeline.
"""

from __future__ import annotations

from typing import Awaitable, Callable, TypeVar

import structlog

from ..models import ParsedEvent
from .base import LLMExtractor, RateLimitError
from .retry import with_retry


log = structlog.get_logger(__name__)

T = TypeVar("T")


class FallbackExtractor(LLMExtractor):
    """Перебирает провайдеров при устойчивом rate-limit (429/503).

    Stateful advance-only индекс `_preferred_idx`: когда провайдер исчерпал ретраи с
    rate-limit, индекс сдвигается вперёд, и все последующие вызовы стартуют со следующего
    провайдера (не бомбя выгоревший). asyncio однопоточный — чтение/запись int между await
    атомарны, Lock не нужен. На обычной ExtractorError (контент/JSON) — проброс без фолбэка.
    """

    def __init__(
        self,
        providers: list[tuple[str, LLMExtractor]],
        *,
        retry_attempts: int = 3,
    ) -> None:
        if not providers:
            raise ValueError("FallbackExtractor требует хотя бы одного провайдера")
        self.providers = providers
        self.retry_attempts = retry_attempts
        self._preferred_idx = 0

    async def _run(self, call: Callable[[LLMExtractor], Awaitable[T]]) -> T:
        start = self._preferred_idx
        if start >= len(self.providers):
            log.error("fallback.all_exhausted")
            raise RateLimitError("все LLM-провайдеры исчерпали лимиты в этом прогоне")

        last: RateLimitError | None = None
        for i in range(start, len(self.providers)):
            name, extractor = self.providers[i]
            try:
                return await with_retry(
                    lambda ex=extractor: call(ex), attempts=self.retry_attempts
                )
            except RateLimitError as exc:
                last = exc
                # Сдвигаем общий индекс только с текущей «головы», чтобы не откатить чужой прогресс.
                if i == self._preferred_idx:
                    self._preferred_idx = i + 1  # может стать == len → следующий вызов short-circuit
                log.warning("fallback.switch", failed=name, error=str(exc)[:120])
        assert last is not None  # цикл выполнился ≥1 раз
        raise last

    async def extract(self, html: str, source_url: str) -> ParsedEvent:
        return await self._run(lambda ex: ex.extract(html, source_url))

    async def extract_many(self, html: str, source_url: str) -> list[ParsedEvent]:
        return await self._run(lambda ex: ex.extract_many(html, source_url))
