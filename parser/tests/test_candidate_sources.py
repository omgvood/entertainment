"""Тесты Discovery-провайдеров: Serper/Brave, circuit breaker, fallback (без сети).

Используем httpx.MockTransport — тот же приём, что в test_vk / test_discovery.
"""

from unittest.mock import MagicMock

import httpx
import pytest

from parser.config import Settings
from parser.sources.candidate_sources import (
    BraveProvider,
    Candidate,
    DuckDuckGoProvider,
    SearchProvider,
    SerperProvider,
    _is_ignored,
    _search_with_fallback,
    _should_auto_approve,
    build_search_providers,
    collect_candidates,
    save_candidates,
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


@pytest.mark.asyncio
async def test_collect_skips_subdomains():
    """Поддомен агрегатора (perm.kassir.ru) отсекается — kassir.ru в _IGNORE_DOMAINS."""
    provider = _FakeProvider("serper", [
        "https://perm.kassir.ru/events",
        "https://goodsite.ru/afisha",
    ])
    async with _client(lambda r: httpx.Response(200, text="")) as c:
        cands = await collect_candidates([provider], c, "perm", skip_domains=set())

    domains = {c.domain for c in cands}
    assert "perm.kassir.ru" not in domains
    assert "goodsite.ru" in domains


# ───────────────────────── _is_ignored ─────────────────────────

@pytest.mark.parametrize("domain", [
    "m.vk.com", "perm.kassir.ru", "afisha.yandex.ru",
    "vk.com", "ticketland.ru", "kassy.ru", "tripadvisor.ru",
])
def test_is_ignored_true(domain):
    assert _is_ignored(domain) is True


@pytest.mark.parametrize("domain", [
    "myafisha.ru", "kassirperm.ru", "goodsite.ru", "vkcom.ru",
])
def test_is_ignored_no_false_positives(domain):
    assert _is_ignored(domain) is False


def test_is_ignored_www_prefix():
    assert _is_ignored("www.vk.com") is True


@pytest.mark.parametrize("domain", ["VK.COM", "M.VK.COM", "Perm.Kassir.Ru"])
def test_is_ignored_case_insensitive(domain):
    assert _is_ignored(domain) is True


def test_is_ignored_hierarchy_direction(monkeypatch):
    """Запись 'afisha.yandex.ru' в сете блокирует её саму, но НЕ родителя yandex.ru.

    yandex.ru здесь и так в _IGNORE_DOMAINS, поэтому проверяем на изолированном сете
    через _match_domain_set напрямую.
    """
    from parser.sources.candidate_sources import _match_domain_set
    s = {"afisha.yandex.ru"}
    assert _match_domain_set("afisha.yandex.ru", s) is True
    assert _match_domain_set("sub.afisha.yandex.ru", s) is True
    assert _match_domain_set("yandex.ru", s) is False


# ───────────────────────── _should_auto_approve ─────────────────────────

def _cand(domain, *, jsonld=True, urls=("https://x.ru/afisha/1",), n_queries=3) -> Candidate:
    return Candidate(
        domain=domain,
        city="perm",
        queries={f"q{i}" for i in range(n_queries)},
        sample_urls=list(urls),
        has_jsonld_event=jsonld,
    )


def test_auto_approve_true():
    assert _should_auto_approve(_cand("organizer.ru")) is True


def test_auto_approve_false_aggregator():
    assert _should_auto_approve(_cand("timepad.ru")) is False


def test_auto_approve_false_builder():
    assert _should_auto_approve(_cand("vanya.tilda.ws")) is False


def test_auto_approve_false_builder_subdomain():
    assert _should_auto_approve(_cand("sub.client.tilda.ws")) is False


def test_auto_approve_false_no_jsonld():
    assert _should_auto_approve(_cand("organizer.ru", jsonld=False)) is False


def test_auto_approve_false_no_event_path():
    assert _should_auto_approve(_cand("organizer.ru", urls=("https://x.ru/news/1",))) is False


def test_auto_approve_false_few_queries():
    assert _should_auto_approve(_cand("organizer.ru", n_queries=2)) is False


# ───────────────────────── save_candidates ─────────────────────────

class _FakeTable:
    """Мок client.table('candidate_sources') с записью insert/update payload."""

    def __init__(self, existing: list[dict], log: dict) -> None:
        self._existing = existing
        self._log = log

    # select(...).eq(...).limit(...).execute().data
    def select(self, *a):
        return self

    def eq(self, *a):
        return self

    def limit(self, *a):
        return self

    def insert(self, payload):
        self._log["insert"] = payload
        return self

    def update(self, payload):
        self._log["update"] = payload
        return self

    def execute(self):
        return MagicMock(data=self._existing)


def _save_client(existing: list[dict]) -> tuple[MagicMock, dict]:
    log: dict = {}
    client = MagicMock()
    client.table.return_value = _FakeTable(existing, log)
    return client, log


def test_save_new_auto_approved():
    """Новый домен с критериями → INSERT со status='approved'."""
    client, log = _save_client(existing=[])
    save_candidates(client, [_cand("organizer.ru")])
    assert log["insert"]["status"] == "approved"


def test_save_new_no_criteria():
    """Новый домен без JSON-LD → INSERT со status='new'."""
    client, log = _save_client(existing=[])
    save_candidates(client, [_cand("organizer.ru", jsonld=False)])
    assert log["insert"]["status"] == "new"


def test_save_existing_new_upgrades_to_approved():
    """Существующая запись status='new', критерии выполнены → UPDATE со status='approved'."""
    client, log = _save_client(existing=[{"status": "new", "queries": []}])
    save_candidates(client, [_cand("organizer.ru")])
    assert log["update"]["status"] == "approved"


def test_save_existing_approved_not_overwritten():
    """Существующая status='approved' → status в payload отсутствует (не трогаем)."""
    client, log = _save_client(existing=[{"status": "approved", "queries": []}])
    save_candidates(client, [_cand("organizer.ru")])
    assert "status" not in log["update"]


def test_save_existing_rejected_not_overwritten():
    """Существующая status='rejected' → status в payload отсутствует (ручное решение модератора)."""
    client, log = _save_client(existing=[{"status": "rejected", "queries": []}])
    save_candidates(client, [_cand("organizer.ru")])
    assert "status" not in log["update"]
