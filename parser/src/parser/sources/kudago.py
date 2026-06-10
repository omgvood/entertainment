"""KudaGo Public API клиент (широкая афиша, пилот по Сочи).

Endpoint: GET https://kudago.com/public-api/v1.4/events/  (ключ не нужен)
Документация: https://docs.kudago.com/api/

KudaGo НЕ поддерживает Пермь (HTTP 400) и не имеет категорий под нишу MVP-1.
Используется только для Сочи как пилот «широкой афиши» — категории маппятся в
расширенные EventType (concert/theater/exhibition/...). LLM не участвует.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

import httpx
import structlog

from ..models import EventType, ParsedEvent


log = structlog.get_logger()

_API_BASE = "https://kudago.com/public-api/v1.4/events/"

_FIELDS = "id,title,dates,place,price,images,categories,site_url,description"

# Категория KudaGo → наш EventType. Не найдено в словаре → 'other'.
_CATEGORY_MAP: dict[str, EventType] = {
    "concert": "concert",
    "theater": "theater",
    "exhibition": "exhibition",
    "festival": "festival",
    "quest": "quest",
    "party": "party",
}

_PRICE_RE = re.compile(r"\d[\d\s]*")


class KudaGoClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def search(
        self, location: str, *, max_items: int = 300
    ) -> list[tuple[ParsedEvent, str]]:
        """Грузит актуальные события локации. Возвращает (событие, site_url)."""
        PAGE_SIZE = 100
        today = date.today()
        events: list[tuple[ParsedEvent, str]] = []
        page = 1
        seen = 0

        while seen < max_items:
            params = {
                "location": location,
                "actual_since": str(int(_unix_midnight(today))),
                "fields": _FIELDS,
                "expand": "place,dates",
                "text_format": "text",
                "page_size": str(PAGE_SIZE),
                "page": str(page),
                "order_by": "dates",
            }
            resp = await self.client.get(_API_BASE, params=params, timeout=20.0)
            if resp.status_code == 404:
                break  # страниц больше нет
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results") or []
            if not results:
                break
            seen += len(results)

            for it in results:
                try:
                    parsed = _item_to_event(it, today)
                    if parsed is not None:
                        events.append((parsed, it.get("site_url") or ""))
                except Exception as exc:  # noqa: BLE001
                    log.warning("kudago.item.skipped", error=str(exc), item_id=it.get("id"))

            if not data.get("next"):
                break
            page += 1

        log.info("kudago.search.ok", location=location, extracted=len(events))
        return events


def _unix_midnight(d: date) -> float:
    from datetime import datetime, timezone

    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp()


def _item_to_event(item: dict[str, Any], today: date) -> Optional[ParsedEvent]:
    title = (item.get("title") or "").strip()
    if len(title) < 3:
        return None

    date_str, time_start = _next_date(item.get("dates") or [], today)
    if not date_str:
        return None  # нет предстоящей даты — прошедшее событие

    place = item.get("place")
    if not isinstance(place, dict):
        return None  # онлайн/без места — пропускаем (нужны venue+address)
    venue_name = (place.get("title") or "").strip()
    address = (place.get("address") or "").strip()
    if not venue_name or not address:
        return None

    site_url = item.get("site_url")
    if not site_url:
        return None

    price_min, price_max, price_text = _parse_price(item.get("price"))
    event_type = _map_category(item.get("categories") or [])
    image_url = _first_image(item.get("images") or [])
    desc = item.get("description")
    description = desc.strip()[:500] if isinstance(desc, str) and desc.strip() else None

    return ParsedEvent(
        title=title[:300],
        type=event_type,
        date=date_str,
        time_start=time_start,
        price_min=price_min,
        price_max=price_max,
        price_text=price_text,
        address=address,
        venue_name=venue_name,
        image_url=image_url,
        description=description,
    )


def _next_date(dates: list[dict[str, Any]], today: date) -> tuple[Optional[str], Optional[str]]:
    """Ближайшая дата с start_date >= сегодня. start_time '19:30:00' → '19:30'."""
    today_str = today.isoformat()
    upcoming = [
        d for d in dates if isinstance(d, dict) and (d.get("start_date") or "") >= today_str
    ]
    if not upcoming:
        return None, None
    d = min(upcoming, key=lambda x: x.get("start_date") or "")
    start_date = d.get("start_date")
    start_time = d.get("start_time")
    time_part = None
    if isinstance(start_time, str) and len(start_time) >= 5:
        time_part = start_time[:5]
    return start_date, time_part


def _map_category(categories: list[str]) -> EventType:
    for c in categories:
        mapped = _CATEGORY_MAP.get(c)
        if mapped:
            return mapped
    return "other"


def _parse_price(price: Any) -> tuple[int, int, str]:
    """KudaGo price — строка ('от 1500 рублей', '', 'Бесплатно')."""
    if not isinstance(price, str) or not price.strip():
        return 0, 0, "уточняйте"
    text = price.strip()
    if "беспл" in text.lower():
        return 0, 0, "бесплатно"
    nums = [int(m.group().replace(" ", "")) for m in _PRICE_RE.finditer(text)]
    if not nums:
        return 0, 0, text[:80]
    pmin, pmax = min(nums), max(nums)
    return pmin, pmax, text[:80]


def _first_image(images: list[Any]) -> Optional[str]:
    for img in images:
        if isinstance(img, dict):
            url = img.get("image")
            if url:
                return url
    return None
