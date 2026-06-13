"""Тесты generic-парсера: резолв listing URL, JSON-LD-first, LLM-бюджет (без реальной БД)."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from parser.sources.generic import _fresh, _run_domain, resolve_listing_url


_JSONLD_HTML = """
<html><head>
<script type="application/ld+json">
{"@type":"Event","name":"Тест событие","startDate":"2026-06-15T19:00",
 "location":{"name":"Площадка","address":"ул. Тестовая, 1"}}
</script></head><body>x</body></html>
"""

_PLAIN_HTML = "<html><body>" + ("афиша " * 200) + "</body></html>"


# --- Фейки для обхода БД и LLM ---

class _FakeResp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def in_(self, *a, **k): return self
    def order(self, *a, **k): return self
    def limit(self, *a, **k): return self
    def update(self, *a, **k): return self
    def upsert(self, *a, **k): return self
    def insert(self, *a, **k): return self
    def execute(self): return _FakeResp([])


class _FakeSupabase:
    def table(self, _name): return _FakeQuery()


class _FakeExtractor:
    def __init__(self, events):
        self._events = events
        self.called = False

    async def extract(self, html, url):  # не используется
        raise NotImplementedError

    async def extract_many(self, html, url):
        self.called = True
        return self._events


def _client(html):
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=html)))


# --- _fresh ---

def test_fresh():
    now = datetime.now(timezone.utc)
    assert _fresh((now - timedelta(days=5)).isoformat()) is True
    assert _fresh((now - timedelta(days=40)).isoformat()) is False
    assert _fresh(None) is False
    assert _fresh("мусор") is False


# --- resolve_listing_url: порядок приоритета ---

@pytest.mark.asyncio
async def test_resolve_cached_fresh():
    fresh = datetime.now(timezone.utc).isoformat()
    cand = {"listing_url": "https://x.ru/afisha", "last_verified": fresh, "sample_urls": []}
    async with _client(_PLAIN_HTML) as client:
        assert await resolve_listing_url(client, "x.ru", cand) == "https://x.ru/afisha"


@pytest.mark.asyncio
async def test_resolve_sample_url_hint():
    cand = {
        "listing_url": None, "last_verified": None,
        "sample_urls": ["https://x.ru/about", "https://x.ru/events/123"],
    }
    async with _client(_PLAIN_HTML) as client:
        assert await resolve_listing_url(client, "x.ru", cand) == "https://x.ru/events/123"


@pytest.mark.asyncio
async def test_resolve_probe_fallback():
    cand = {"listing_url": None, "last_verified": None, "sample_urls": []}
    async with _client(_PLAIN_HTML) as client:
        url = await resolve_listing_url(client, "x.ru", cand)
    assert url.startswith("https://x.ru")


# --- _run_domain: JSON-LD short-circuit и LLM-бюджет ---

@pytest.mark.asyncio
async def test_jsonld_short_circuits_llm():
    cand = {
        "domain": "x.ru",
        "listing_url": "https://x.ru/afisha",
        "last_verified": datetime.now(timezone.utc).isoformat(),
        "sample_urls": [],
    }
    extractor = _FakeExtractor(events=[])
    async with _client(_JSONLD_HTML) as client:
        rows, used_llm, err = await _run_domain(
            client, _FakeSupabase(), extractor, "perm", cand, allow_llm=True
        )
    assert len(rows) == 1
    assert used_llm is False
    assert extractor.called is False  # LLM не звали — хватило JSON-LD


@pytest.mark.asyncio
async def test_budget_exhausted_skips_llm():
    cand = {
        "domain": "x.ru",
        "listing_url": "https://x.ru/afisha",
        "last_verified": datetime.now(timezone.utc).isoformat(),
        "sample_urls": [],
    }
    extractor = _FakeExtractor(events=[])
    async with _client(_PLAIN_HTML) as client:  # без JSON-LD
        rows, used_llm, err = await _run_domain(
            client, _FakeSupabase(), extractor, "perm", cand, allow_llm=False
        )
    assert rows == []
    assert used_llm is False
    assert extractor.called is False  # бюджет исчерпан → LLM не звали
