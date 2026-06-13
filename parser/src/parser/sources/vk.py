"""VK API клиент (vk.com) — крупнейший источник локальных событий в РФ.

Работает с сервисным ключом mini-app: доступны только методы открытых данных
(`groups.search`, `groups.getById`, `wall.get`). `newsfeed.search` сервисному ключу
недоступен — на нём ничего не строим.

Два режима использования (см. pipeline):
  vk-events — VK-сообщества типа «событие» имеют нативные start_date/finish_date/place,
              маппятся в ParsedEvent напрямую, без LLM.
  vk-posts  — посты со стен кураторских сообществ: свободный русский текст, через LLM
              (extract_many, один вызов на сообщество). Перед LLM — префильтр постов.

Документация: https://dev.vk.com/method
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import structlog

from ..classifiers import is_event_candidate  # noqa: F401 — re-export для обратной совместимости
from ..models import EventType, ParsedEvent


log = structlog.get_logger()

_API_BASE = "https://api.vk.com/method"
_API_VERSION = "5.199"
_THROTTLE_SEC = 0.35  # сервисный ключ ~3 rps на приложение

# city_slug → название города (именительный) для groups.search.
CITY_NAMES: dict[str, str] = {"perm": "Пермь", "sochi": "Сочи"}

# Дата события показывается в МСК (+3). Пермь фактически +5, но риск только у событий,
# стартующих в интервале 00:00–02:00 — приемлемо для MVP.
_DISPLAY_TZ = timezone(timedelta(hours=3))

# Ключевые слова → EventType. Применяется к названию/activity сообщества (vk-events)
# и доступно LLM-фолбэку как ориентир. Первое совпадение выигрывает.
_TYPE_KEYWORDS: list[tuple[tuple[str, ...], EventType]] = [
    (("квиз", "quiz", "интеллектуальн"), "quiz"),
    (("стендап", "стэндап", "stand up", "standup", "стенд-ап"), "standup"),
    (("боулинг",), "bowling"),
    (("бильярд",), "billiards"),
    (("картинг",), "karting"),
    (("концерт",), "concert"),
    (("театр", "спектакл"), "theater"),
    (("выставк",), "exhibition"),
    (("фестивал",), "festival"),
    (("квест",), "quest"),
    (("вечеринк", "party", "пати"), "party"),
    (("кино", "showing", "кинопоказ"), "cinema"),
    (("мастер-класс", "мастер класс", "воркшоп", "workshop", "лекци"), "education"),
    (("бизнес", "нетворкинг"), "business"),
    (("спорт", "турнир", "забег", "марафон"), "sport"),
    (("выстав",), "exhibition"),
]

class VkApiError(RuntimeError):
    """VK вернул error envelope, не подлежащий ретраю (закрытая стена/группа и т.п.)."""


class VkClient:
    def __init__(
        self, client: httpx.AsyncClient, service_key: str, *, version: str = _API_VERSION
    ) -> None:
        self.client = client
        self.service_key = service_key
        self.version = version

    async def _call(self, method: str, params: dict[str, Any]) -> Any:
        """Вызов метода VK. Возвращает payload поля `response`.

        Обрабатывает error envelope: код 6 (too many requests) → одна повторная попытка
        после паузы; коды 15/30 (закрытая стена/группа) → VkApiError (пропустить).
        """
        full = {**params, "access_token": self.service_key, "v": self.version}
        for attempt in range(2):
            await asyncio.sleep(_THROTTLE_SEC)
            resp = await self.client.get(f"{_API_BASE}/{method}", params=full, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                err = data["error"]
                code = err.get("error_code")
                if code == 6 and attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                if code in (15, 30):
                    raise VkApiError(f"{method}: {err.get('error_msg')} (code {code})")
                raise RuntimeError(
                    f"VK {method} error {code}: {err.get('error_msg')}"
                )
            return data.get("response")
        raise RuntimeError(f"VK {method}: исчерпаны попытки (rate limit)")

    async def search_event_groups(
        self, city_name: str, *, city_id: Optional[int] = None, count: int = 100
    ) -> list[dict[str, Any]]:
        """Ищет VK-сообщества типа «событие» по городу и возвращает их с деталями.

        groups.search(type=event) → id'шники → groups.getById(fields=start_date,...).

        ВНИМАНИЕ: groups.search ТРЕБУЕТ ПОЛЬЗОВАТЕЛЬСКИЙ токен. Сервисному ключу mini-app
        метод запрещён (Access denied, code 15) — на нём поднимется VkApiError. Поэтому
        источник vk-events в seeds.yaml отключён; ждёт user-токена. wall.get (vk-posts) работает.
        """
        search_params: dict[str, Any] = {
            "q": city_name,
            "type": "event",
            "count": min(count, 1000),
            "country_id": 1,
        }
        if city_id:
            search_params["city_id"] = city_id
        found = await self._call("groups.search", search_params)
        items = (found or {}).get("items") or []
        group_ids = [str(g["id"]) for g in items if g.get("id")]
        if not group_ids:
            return []

        # groups.getById: до 500 id за вызов, страничим.
        groups: list[dict[str, Any]] = []
        for i in range(0, len(group_ids), 500):
            chunk = group_ids[i : i + 500]
            resp = await self._call(
                "groups.getById",
                {
                    "group_ids": ",".join(chunk),
                    "fields": "start_date,finish_date,place,description,photo_200,activity",
                },
            )
            # 5.199 возвращает {"groups": [...]}; старые версии — просто список.
            if isinstance(resp, dict):
                groups.extend(resp.get("groups") or [])
            elif isinstance(resp, list):
                groups.extend(resp)
        return groups

    async def fetch_wall_posts(
        self, domain: str, *, count: int = 100
    ) -> list[dict[str, Any]]:
        """Посты со стены сообщества (filter=owner — только записи самого сообщества)."""
        resp = await self._call(
            "wall.get",
            {"domain": domain, "count": min(count, 100), "filter": "owner"},
        )
        return (resp or {}).get("items") or []


# --- Чистые функции маппинга/фильтрации (тестируются без сети) ---


def infer_type(text: str) -> EventType:
    """EventType по ключевым словам в тексте. Не распознано → 'other'."""
    low = (text or "").lower()
    for keywords, etype in _TYPE_KEYWORDS:
        if any(k in low for k in keywords):
            return etype
    return "other"


def _ts_to_date_time(ts: Any) -> tuple[Optional[str], Optional[str]]:
    """Unix timestamp → ('YYYY-MM-DD', 'HH:MM') в МСК. 0/None → (None, None)."""
    if not isinstance(ts, (int, float)) or isinstance(ts, bool) or ts <= 0:
        return None, None
    dt = datetime.fromtimestamp(int(ts), tz=_DISPLAY_TZ)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def event_group_to_parsed(
    group: dict[str, Any], city_name: str, *, today: Optional[str] = None
) -> Optional[ParsedEvent]:
    """VK event-сообщество → ParsedEvent. None, если нет/прошла дата или короткое имя."""
    name = (group.get("name") or "").strip()
    if len(name) < 3:
        return None

    date_str, time_start = _ts_to_date_time(group.get("start_date"))
    if not date_str:
        return None
    today = today or datetime.now(_DISPLAY_TZ).strftime("%Y-%m-%d")
    if date_str < today:
        return None

    _, time_end = _ts_to_date_time(group.get("finish_date"))

    place = group.get("place") or {}
    address = (place.get("address") or "").strip()
    venue_name = (place.get("title") or "").strip()
    if not address:
        address = venue_name or city_name
    if not venue_name:
        venue_name = address or city_name

    desc = group.get("description")
    description = desc.strip()[:500] if isinstance(desc, str) and desc.strip() else None

    return ParsedEvent(
        title=name[:300],
        type=infer_type(f"{name} {group.get('activity') or ''}"),
        date=date_str,
        time_start=time_start,
        time_end=time_end,
        price_min=0,
        price_max=0,
        price_text="уточняйте",
        address=address,
        venue_name=venue_name,
        image_url=group.get("photo_200"),
        description=description,
        organizer=name,
    )


def event_group_url(group: dict[str, Any]) -> str:
    """Ссылка на VK event-сообщество."""
    return f"https://vk.com/club{group.get('id')}"


def post_url(owner_id: Any, post_id: Any) -> str:
    """owner_id, post_id → постоянная ссылка на пост (owner_id у сообществ отрицательный)."""
    return f"https://vk.com/wall{owner_id}_{post_id}"


def post_within_days(post: dict[str, Any], days: int, *, now_ts: Optional[float] = None) -> bool:
    """True, если пост опубликован не раньше, чем `days` дней назад."""
    ts = post.get("date")
    if not isinstance(ts, (int, float)) or isinstance(ts, bool):
        return False
    now_ts = now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp()
    return ts >= now_ts - days * 86400
