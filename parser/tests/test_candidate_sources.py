"""Тесты Discovery-провайдеров: Serper/Brave, circuit breaker, fallback (без сети).

Используем httpx.MockTransport — тот же приём, что в test_vk / test_discovery.
"""

import httpx
import pytest

from parser.config import Settings
from parser.sources.candidate_sources import (
    BraveProvider,
    DuckDuckGoProvider,
    SearchProvider,
    SerperProvider,
    _search_with_fallback,
    build_search_providers,
    collect_candidates,
)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _settings(**over) -> Settings:
    base = dict(supabase_url="http://x", supabase_service_key="k")
    base.update(over)
    return Settings(**base)


# ───────────────────────── Serper ─────────────────────────

@pytest.mark.asyncio
async def test_serper_success():
    def handler(request):
        return httpx.Response(200, json={"organic": [
            {"link": "https://afisha59.ru/events"},
            {"link": "https://teatr.ru/afisha"},
            {"title": "no link here"},
        ]})

    async with _client(handler) as c:
        urls = await SerperProvider(c, "key", 5.0).search("афиша Пермь")
    assert urls == ["https://afisha59.ru/events", "https://teatr.ru/afisha"]


@pytest.mark.asyncio
async def test_serper_empty_organic():
    async with _client(lambda r: httpx.Response(200, json={"organic": []})) as c:
        assert await SerperProvider(c, "key", 5.0).search("q") == []


@pytest.mark.asyncio
async def test_serper_missing_organic_key():
    async with _client(lambda r: httpx.Response(200, json={})) as c:
        assert await SerperProvider(c, "key", 5.0).search("q") == []


@pytest.mark.asyncio
async def test_serper_bad_json():
    async with _client(lambda r: httpx.Response(200, text="<html>not json</html>")) as c:
        assert await SerperProvider(c, "key", 5.0).search("q") == []


@pytest.mark.asyncio
async def test_serper_500_returns_empty():
    async with _client(lambda r: httpx.Response(500, text="oops")) as c:
        assert await SerperProvider(c, "key", 5.0).search("q") == []


@pytest.mark.asyncio
async def test_serper_timeout_returns_empty():
    def handler(request):
        raise httpx.TimeoutException("slow")

    async with _client(handler) as c:
        assert await SerperProvider(c, "key", 5.0).search("q") == []


@pytest.mark.asyncio
async def test_serper_401_disables_provider():
    """401 (битый ключ) → провайдер отключается, второй вызов не бьёт в сеть."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, json={"message": "bad key"})

    async with _client(handler) as c:
        p = SerperProvider(c, "key", 5.0)
        assert await p.search("q1") == []
        assert await p.search("q2") == []
    assert calls["n"] == 1  # второй search() короткозамкнут _disabled


@pytest.mark.asyncio
async def test_serper_429_does_not_disable():
    """429 (rate limit) — временно: после него провайдер продолжает работать."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"message": "slow down"})
        return httpx.Response(200, json={"organic": [{"link": "https://ok.ru/x"}]})

    async with _client(handler) as c:
        p = SerperProvider(c, "key", 5.0)
        assert await p.search("q1") == []
        assert await p.search("q2") == ["https://ok.ru/x"]
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_serper_three_failures_disable_provider():
    """3 подряд 5xx → circuit breaker отключает провайдер до конца прогона."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(503, text="down")

    async with _client(handler) as c:
        p = SerperProvider(c, "key", 5.0)
        for _ in range(5):
            await p.search("q")
    assert calls["n"] == 3  # после 3-го отказа _disabled, запросы прекращаются


# ───────────────────────── Brave ─────────────────────────

@pytest.mark.asyncio
async def test_brave_success():
    def handler(request):
        return httpx.Response(200, json={"web": {"results": [
            {"url": "https://perm-afisha.ru/events"},
            {"title": "no url"},
        ]}})

    async with _client(handler) as c:
        urls = await BraveProvider(c, "key", 5.0).search("афиша Пермь")
    assert urls == ["https://perm-afisha.ru/events"]


# ───────────────────────── fallback ─────────────────────────

class _FakeProvider(SearchProvider):
    def __init__(self, name, results):
        self.name = name
        self._results = results

    async def search(self, query):
        return self._results


@pytest.mark.asyncio
async def test_fallback_uses_second_when_first_empty():
    providers = [
        _FakeProvider("serper", []),
        _FakeProvider("brave", ["https://x.ru/events"]),
    ]
    urls, name = await _search_with_fallback(providers, "q")
    assert urls == ["https://x.ru/events"]
    assert name == "brave"


@pytest.mark.asyncio
async def test_fallback_all_fail():
    providers = [_FakeProvider("serper", []), _FakeProvider("brave", [])]
    urls, name = await _search_with_fallback(providers, "q")
    assert urls == []
    assert name == "none"


# ───────────────────────── factory ─────────────────────────

def test_build_providers_unknown_name_skipped():
    s = _settings(search_providers="serper,bogus", serper_api_key="k")
    providers = build_search_providers(s, client=httpx.AsyncClient())
    assert [p.name for p in providers] == ["serper"]


def test_build_providers_order_and_keys():
    s = _settings(
        search_providers="serper,brave,duckduckgo",
        serper_api_key="s", brave_api_key="b",
    )
    providers = build_search_providers(s, client=httpx.AsyncClient())
    assert [p.name for p in providers] == ["serper", "brave", "duckduckgo"]


def test_build_providers_serper_without_key_falls_to_ddg():
    s = _settings(search_providers="serper,duckduckgo")  # ключа нет
    providers = build_search_providers(s, client=httpx.AsyncClient())
    assert [p.name for p in providers] == ["duckduckgo"]


def test_build_providers_empty_when_no_keys():
    s = _settings(search_providers="serper,brave")  # ключей нет, ddg не указан
    providers = build_search_providers(s, client=httpx.AsyncClient())
    assert providers == []


# ───────────────────────── collect_candidates ─────────────────────────

@pytest.mark.asyncio
async def test_collect_records_first_provider(monkeypatch):
    """first_provider/first_query проставляются при первом обнаружении домена."""
    provider = _FakeProvider("serper", ["https://newsite.ru/afisha/concert"])

    # _score_candidate ходит в сеть GET — отдаём пустой 200, чтобы не считать JSON-LD.
    async with _client(lambda r: httpx.Response(200, text="")) as c:
        cands = await collect_candidates([provider], c, "perm", skip_domains=set())

    assert len(cands) == 1
    cand = cands[0]
    assert cand.domain == "newsite.ru"
    assert cand.first_provider == "serper"
    assert "Пермь" in cand.first_query
