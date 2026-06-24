"""Ретрай LLM-вызовов на RateLimitError с экспоненциальным backoff + jitter."""

from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

import structlog

from .base import RateLimitError


log = structlog.get_logger(__name__)

T = TypeVar("T")


async def with_retry(
    factory: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 2.0,
) -> T:
    """Зовёт factory(), повторяя на RateLimitError. После attempts — пробрасывает последний.

    Jitter разносит синхронно проснувшиеся корутины, чтобы не бить API одновременно.
    """
    last: RateLimitError | None = None
    for attempt in range(attempts):
        try:
            return await factory()
        except RateLimitError as exc:
            last = exc
            if attempt < attempts - 1:
                delay = base_delay * (2**attempt) + random.uniform(0.5, 1.5)
                log.debug("llm.retry", attempt=attempt + 1, delay=round(delay, 2), error=str(exc)[:120])
                await asyncio.sleep(delay)
    assert last is not None  # цикл выполнился ≥1 раз
    raise last
