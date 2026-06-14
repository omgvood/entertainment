"""Timepad API клиент (широкая афиша, оба города).

Тянет весь поток предстоящих событий города и типизирует каждое по его категории Timepad
(`categories[].tag` → EventType), как `kudago.py`. LLM не участвует.

Документация: https://dev.timepad.ru/api/
Endpoint: GET https://api.timepad.ru/v1/events  (Authorization: Bearer <token>)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

import httpx
import structlog

from ..models import EventType, ParsedEvent


log = structlog.get_logger()

_API_BASE = "https://api.timepad.ru/v1/events"

# city_slug в seeds → название города для параметра Timepad `cities[]`.
CITY_NAMES: dict[str, str] = {
    "perm": "Пермь",
    "sochi": "Сочи",
}

# Категория Timepad (id) → наш EventType. Не найдено → 'other'.
# В ответе событий у категорий есть только id+name (без tag), поэтому ключ — id.
# id взяты из /v1/dictionary/event_categories.
_CATEGORY_MAP: dict[int, EventType] = {
    2335: "quiz",       # Интеллектуальные игры
    460: "concert",     # Концерты
    459: "theater",     # Театры
    458: "exhibition",  # Выставки
    457: "party",       # Вечеринки
    374: "cinema",      # Кино
    376: "sport",       # Спорт
    379: "kids",        # Для детей
    217: "business",    # Бизнес
    452: "business",    # ИТ и интернет
    453: "education",   # Психология и самопознание
    382: "education",   # Иностранные языки
    1315: "education",  # Образование за рубежом
    2465: "science",    # Наука
    456: "food",        # Еда
    461: "trip",        # Экскурсии и путешествия
    524: "hobby",       # Хобби и творчество
    525: "art",         # Искусство и культура
    # 399 Красота, 462 Другие события, 463 Другие развлечения, 1940 Гражданские → other
}


class TimepadClient:
    def __init__(self, client: httpx.AsyncClient, token: str) -> None:
        self.client = client
        self.token = token

    async def search(
        self, city_slug: str, *, max_items: int = 500
    ) -> list[tuple[ParsedEvent, str]]:
        """Грузит предстоящие события города. Возвращает (событие, реальная ссылка Timepad).

        Тип каждого события — из его категории Timepad. Пагинация через limit/skip.
        """
        city_name = CITY_NAMES.get(city_slug)
        if not city_name:
            log.warning("timepad.unknown_city", city=city_slug)
            return []

        PAGE_SIZE = 100  # потолок Timepad
        today = date.today().isoformat()

        events: list[tuple[ParsedEvent, str]] = []
        skip = 0
        while skip < max_items:
            params = {
                "limit": str(PAGE_SIZE),
                "skip": str(skip),
                "cities[]": city_name,
                "starts_at_min": today,
                "sort": "+starts_at",
                "fields": "location,poster_image,description_short,ticket_types,categories",
            }
            resp = await self.client.get(
                _API_BASE,
                params=params,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=20.0,
            )
            if resp.status_code == 403:
                log.error(
                    "timepad.forbidden",
                    city=city_slug,
                    skip=skip,
                    body=resp.text[:500],
                )
            resp.raise_for_status()
            data = resp.json()

            values = data.get("values") or []
            if not values:
                break

            for it in values:
                try:
                    ev = _item_to_event(it, city_name)
                    events.append((ev, it["url"]))
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "timepad.item.skipped", error=str(exc), item_id=it.get("id")
                    )

            if len(values) < PAGE_SIZE:
                break
            skip += PAGE_SIZE

        log.info("timepad.search.ok", city=city_slug, extracted=len(events))
        return events


def _map_category(categories: Any) -> EventType:
    """categories[].id → EventType. Первая распознанная категория, иначе 'other'."""
    if isinstance(categories, list):
        for c in categories:
            if isinstance(c, dict):
                mapped = _CATEGORY_MAP.get(c.get("id"))
                if mapped:
                    return mapped
    return "other"


def _item_to_event(item: dict[str, Any], city_name: str) -> ParsedEvent:
    name = (item.get("name") or "").strip()
    if len(name) < 3:
        raise ValueError("слишком короткое name")

    date_str, time_start = _parse_starts_at(item.get("starts_at"))
    if not date_str:
        raise ValueError(f"не удалось разобрать starts_at={item.get('starts_at')!r}")

    address = _parse_address(item.get("location"), city_name)
    venue_name = _parse_venue(item.get("location")) or name
    price_min, price_max, price_text = _parse_ticket_types(item.get("ticket_types"))

    url = item.get("url")
    if not url:
        raise ValueError("у события нет url")

    poster = item.get("poster_image") or {}
    image_url = poster.get("default_url") or poster.get("uri")

    desc = item.get("description_short")
    description = desc.strip()[:500] if isinstance(desc, str) and desc.strip() else None

    return ParsedEvent(
        title=name[:300],
        type=_map_category(item.get("categories")),
        date=date_str,
        time_start=time_start,
        price_min=price_min,
        price_max=price_max,
        price_text=price_text,
        address=address,
        venue_name=venue_name,
        image_url=image_url,
        description=description,
        organizer=(item.get("organization") or {}).get("name"),
    )


def _parse_starts_at(v: Any) -> tuple[Optional[str], Optional[str]]:
    """'2026-06-15T19:00:00+0500' → ('2026-06-15', '19:00')."""
    if not isinstance(v, str) or len(v) < 10:
        return None, None
    date_part = v[:10]
    try:
        datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        return None, None
    time_part = None
    if "T" in v and len(v) >= 16:
        hhmm = v[11:16]
        try:
            datetime.strptime(hhmm, "%H:%M")
            time_part = hhmm
        except ValueError:
            time_part = None
    return date_part, time_part


def _parse_address(location: Any, city_name: str) -> str:
    if isinstance(location, dict):
        addr = (location.get("address") or "").strip()
        city = (location.get("city") or city_name).strip()
        if addr:
            return f"{city}, {addr}" if city and city not in addr else addr
        if city:
            return city
    return city_name


def _parse_venue(location: Any) -> Optional[str]:
    if isinstance(location, dict):
        # У Timepad нет отдельного venue name; адрес — лучший доступный ориентир.
        addr = (location.get("address") or "").strip()
        return addr or None
    return None


def _parse_ticket_types(v: Any) -> tuple[int, int, str]:
    """ticket_types[].price → (min, max, price_text). Нет цен → 0/0/'уточняйте'."""
    prices: list[int] = []
    if isinstance(v, list):
        for t in v:
            if not isinstance(t, dict):
                continue
            p = t.get("price")
            if isinstance(p, (int, float)) and not isinstance(p, bool):
                prices.append(int(p))
    if not prices:
        return 0, 0, "уточняйте"
    pmin, pmax = min(prices), max(prices)
    if pmin == pmax:
        price_text = "бесплатно" if pmin == 0 else f"от {pmin} ₽"
    else:
        price_text = f"от {pmin} до {pmax} ₽"
    return pmin, pmax, price_text
