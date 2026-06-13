"""Тесты VK: маппинг event-сообществ, префильтр постов, error envelope (без сети)."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from parser.sources import vk as vk_mod
from parser.sources.vk import (
    VkApiError,
    VkClient,
    event_group_to_parsed,
    event_group_url,
    infer_type,
    is_event_candidate,
    post_url,
    post_within_days,
)


_MSK = timezone(timedelta(hours=3))


def _ts(y, m, d, hh=19, mm=30):
    return datetime(y, m, d, hh, mm, tzinfo=_MSK).timestamp()


_GROUP = {
    "id": 777,
    "name": "Квиз, плиз! в Перми",
    "start_date": _ts(2026, 6, 15, 19, 30),
    "place": {"title": "Бар Лес", "address": "ул. Ленина, 50"},
    "photo_200": "https://example.com/p.jpg",
    "activity": "Интеллектуальные игры",
    "description": "Командная интеллектуальная игра.",
}


def test_infer_type():
    assert infer_type("Стендап вечер") == "standup"
    assert infer_type("Боулинг турнир") == "bowling"
    assert infer_type("Квиз, плиз!") == "quiz"
    assert infer_type("Большой концерт") == "concert"
    assert infer_type("Просто встреча друзей") == "other"


def test_event_group_mapping():
    ev = event_group_to_parsed(_GROUP, "Пермь", today="2026-06-12")
    assert ev is not None
    assert ev.type == "quiz"
    assert ev.date == "2026-06-15"
    assert ev.time_start == "19:30"
    assert ev.venue_name == "Бар Лес"
    assert ev.address == "ул. Ленина, 50"
    assert ev.image_url == "https://example.com/p.jpg"
    assert ev.price_text == "уточняйте"


def test_event_group_past_skipped():
    past = dict(_GROUP, start_date=_ts(2020, 1, 1))
    assert event_group_to_parsed(past, "Пермь", today="2026-06-12") is None


def test_event_group_no_date_skipped():
    no_date = dict(_GROUP, start_date=0)
    assert event_group_to_parsed(no_date, "Пермь", today="2026-06-12") is None


def test_event_group_place_fallback():
    no_place = dict(_GROUP)
    no_place.pop("place")
    ev = event_group_to_parsed(no_place, "Пермь", today="2026-06-12")
    assert ev is not None
    assert ev.address == "Пермь"
    assert ev.venue_name == "Пермь"


def test_event_group_url():
    assert event_group_url(_GROUP) == "https://vk.com/club777"


def test_post_url():
    assert post_url(-123, 456) == "https://vk.com/wall-123_456"


def test_post_within_days():
    now = datetime.now(timezone.utc).timestamp()
    assert post_within_days({"date": now}, 14) is True
    assert post_within_days({"date": now - 20 * 86400}, 14) is False
    assert post_within_days({}, 14) is False


def test_is_event_candidate():
    assert is_event_candidate("Концерт 15 июня, билеты на сайте") is True
    assert is_event_candidate("Начало в 19:00, вход свободный") is True
    assert is_event_candidate("Регистрация: https://org.timepad.ru/event/1/") is True
    assert is_event_candidate("Спасибо всем за прекрасный вечер! 🥳") is False
    assert is_event_candidate("") is False


@pytest.mark.asyncio
async def test_call_rate_limit_retry(monkeypatch):
    """Код 6 (rate limit) → одна повторная попытка, затем успех."""
    monkeypatch.setattr(vk_mod.asyncio, "sleep", _noop_sleep)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"error": {"error_code": 6, "error_msg": "rate"}})
        return httpx.Response(200, json={"response": {"items": []}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await VkClient(client, "key")._call("groups.search", {"q": "Пермь"})
    assert resp == {"items": []}
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_call_closed_group_raises(monkeypatch):
    """Код 15/30 (закрытая стена/группа) → VkApiError (пропустить группу)."""
    monkeypatch.setattr(vk_mod.asyncio, "sleep", _noop_sleep)

    def handler(request):
        return httpx.Response(200, json={"error": {"error_code": 15, "error_msg": "Access denied"}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(VkApiError):
            await VkClient(client, "key")._call("wall.get", {"domain": "x"})


async def _noop_sleep(*_args, **_kwargs):
    return None
