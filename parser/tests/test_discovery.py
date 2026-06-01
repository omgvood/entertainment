"""Smoke-тест listing discovery без реальной сети. Используем httpx.MockTransport."""

import httpx
import pytest

from parser.discovery import ListingDiscovery


_FAKE_HTML = """
<!DOCTYPE html>
<html><body>
  <a href="/game-page?id=123">Игра 1</a>
  <a href="/game-page?id=456">Игра 2</a>
  <a href="/about">О нас</a>
  <a href="https://other.example/game-page?id=789">Внешняя</a>
  <a href="/game-page?id=123">Дубль</a>
</body></html>
"""


def _handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=_FAKE_HTML)


@pytest.mark.asyncio
async def test_listing_discovery_filters_and_dedupes():
    transport = httpx.MockTransport(_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        strat = ListingDiscovery(
            client=client,
            source_name="quizplease",
            url="https://perm.quizplease.ru/schedule",
            url_pattern=r"/game-page\?id=\d+",
        )
        urls = await strat.discover()

    found = sorted(u.url for u in urls)
    assert found == [
        "https://other.example/game-page?id=789",
        "https://perm.quizplease.ru/game-page?id=123",
        "https://perm.quizplease.ru/game-page?id=456",
    ]
    assert all(u.source == "quizplease" for u in urls)
