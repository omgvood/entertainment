"""Smoke-тест listing discovery без реальной сети. Используем httpx.MockTransport."""

import httpx
import pytest

from parser.discovery import ListingDiscovery
from parser.sources.candidate_sources import (
    Candidate,
    _AGGREGATOR_PENALTY,
    _AGGREGATOR_PENALTY_DOMAINS,
    _score_candidate,
)


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


# --- Штраф агрегаторам в скоринге Discovery (_score_candidate) -----------------
#
# Скоринг (см. _score_candidate): +1 за каждый доп. запрос, +2 за event-path в URL,
# +3 за JSON-LD Event на странице, -_AGGREGATOR_PENALTY для доменов из списка.

# JSON-LD Event на странице → срабатывает бонус +3.
_JSONLD_HTML = (
    '<html><head><script type="application/ld+json">'
    '{"@type": "MusicEvent", "name": "X"}'
    "</script></head><body>x</body></html>"
)
# Без разметки → бонус +3 не срабатывает, проще считать математику штрафа.
_PLAIN_HTML = "<html><body>no markup</body></html>"


def _make_handler(html: str):
    return lambda request: httpx.Response(200, text=html)


async def _score(domain, *, queries=("афиша Пермь",), sample_urls=(), html=_PLAIN_HTML):
    """Прогоняет домен через _score_candidate и возвращает итоговый score."""
    cand = Candidate(domain=domain, city="perm")
    cand.queries = set(queries)
    cand.sample_urls = list(sample_urls)
    transport = httpx.MockTransport(_make_handler(html))
    async with httpx.AsyncClient(transport=transport) as client:
        await _score_candidate(client, cand)
    return cand.score


# Прочие билетные платформы (afisha.ru/ticketland.ru/kassir.ru) переехали в _IGNORE_DOMAINS —
# они отсеиваются в collect_candidates до скоринга (тесты в test_candidate_sources.py).
# Здесь проверяем сам механизм штрафа на оставшемся пенальти-домене (timepad.ru).
@pytest.mark.parametrize("domain", sorted(_AGGREGATOR_PENALTY_DOMAINS))
@pytest.mark.asyncio
async def test_known_aggregators_penalized(domain):
    """Каждый домен из пенальти-списка получает штраф (защита от случайного удаления домена)."""
    aggregator = await _score(domain)
    normal = await _score("teatr-teatr.com")
    assert aggregator == normal - _AGGREGATOR_PENALTY


@pytest.mark.asyncio
async def test_aggregator_subdomain_penalized():
    """Поддомен пенальти-домена (sub.timepad.ru) тоже штрафуется."""
    sub = await _score("sub.timepad.ru")
    normal = await _score("perm.example.com")
    assert sub == normal - _AGGREGATOR_PENALTY


@pytest.mark.asyncio
async def test_aggregator_no_false_positive():
    """myafisha.ru НЕ совпадает с afisha.ru — суффиксное сравнение не ложно-срабатывает."""
    suspicious = await _score("myafisha.ru")
    normal = await _score("example.com")
    assert suspicious == normal


@pytest.mark.asyncio
async def test_aggregator_penalty_mechanics():
    """Штраф = дельта между агрегатором и обычным доменом при идентичных сигналах.

    Проверяем дельту, а не абсолютный score — тест не сломается при добавлении новых бонусов.
    """
    signals = {
        "queries": ("афиша Пермь", "квиз Пермь"),
        "sample_urls": ["https://x/afisha/show"],
        "html": _JSONLD_HTML,
    }
    aggregator = await _score("timepad.ru", **signals)
    normal = await _score("teatr-teatr.com", **signals)
    assert aggregator == normal - _AGGREGATOR_PENALTY


@pytest.mark.asyncio
async def test_local_organizer_beats_aggregator():
    """Бизнес-цель: локальный организатор обгоняет агрегатор при сильных сигналах у обоих."""
    # timepad.ru: JSON-LD(+3) + event-path(+2) + 2 запроса(+1) − штраф(5) = +1
    aggregator = await _score(
        "timepad.ru",
        queries=("афиша Пермь", "концерт Пермь"),
        sample_urls=["https://timepad.ru/afisha/x"],
        html=_JSONLD_HTML,
    )
    # teatr-teatr.com: JSON-LD(+3) + event-path(+2) + 1 запрос(0) = +5
    organizer = await _score(
        "teatr-teatr.com",
        queries=("афиша Пермь",),
        sample_urls=["https://teatr-teatr.com/afisha/y"],
        html=_JSONLD_HTML,
    )
    assert organizer > aggregator


@pytest.mark.asyncio
async def test_ranking_organizers_above_aggregators():
    """Интеграционный: после сортировки по score организатор обгоняет штрафованный агрегатор."""
    domains = {
        "timepad.ru": ("афиша Пермь", "концерт Пермь"),      # +1 (штраф)
        "teatr-teatr.com": ("афиша Пермь",),                  # +5
        "filarmonia.online": ("афиша Пермь",),                # +5
    }
    scored = []
    for domain, queries in domains.items():
        score = await _score(
            domain,
            queries=queries,
            sample_urls=[f"https://{domain}/afisha/x"],
            html=_JSONLD_HTML,
        )
        scored.append((domain, score))

    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    top2 = {domain for domain, _ in ranked[:2]}
    assert top2 == {"teatr-teatr.com", "filarmonia.online"}
    assert "timepad.ru" not in top2
