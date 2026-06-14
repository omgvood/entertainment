"""Shared HTTP utilities."""

from __future__ import annotations

import asyncio

import httpx


async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict | None = None,
    *,
    retries: int = 3,
    timeout: float = 15.0,
) -> httpx.Response:
    """GET с повторными попытками на 5xx и timeout. Exponential backoff."""
    for attempt in range(retries):
        try:
            resp = await client.get(url, params=params, timeout=timeout)
            if resp.status_code >= 500 and attempt < retries - 1:
                await asyncio.sleep(2**attempt)
                continue
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException:
            if attempt < retries - 1:
                await asyncio.sleep(2**attempt)
                continue
            raise
    raise RuntimeError("unreachable")
