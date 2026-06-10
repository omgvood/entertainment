"""Извлечение событий из Schema.org JSON-LD (<script type="application/ld+json">).

Бесплатный и точный путь ПЕРЕД LLM: многие event-сайты встраивают структурированный
блок `@type: Event` с готовыми date/price/location. Если он есть и полный — LLM не нужен.

Schema.org не различает квиз/стендап/боулинг, поэтому `type` берётся из конфига источника
(`default_type`). Записи без обязательных полей (title/date/address/venue) пропускаются —
их доберёт LLM-фолбэк.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import structlog
from selectolax.parser import HTMLParser

from ..models import EventType, ParsedEvent


log = structlog.get_logger()

# @type значения Schema.org, которые считаем событием (Event + подтипы).
_EVENT_TYPES = {
    "Event",
    "TheaterEvent",
    "ComedyEvent",
    "MusicEvent",
    "SocialEvent",
    "Festival",
    "ExhibitionEvent",
    "ScreeningEvent",
    "EducationEvent",
    "SportsEvent",
    "BusinessEvent",
}


def extract_jsonld_events(html: str, default_type: EventType) -> list[ParsedEvent]:
    """Парсит все <script type="application/ld+json"> и возвращает события.

    Пустой список означает «JSON-LD событий не найдено» — вызывающий код должен
    откатиться на LLM.
    """
    blocks = _iter_jsonld_objects(html)
    events: list[ParsedEvent] = []
    for obj in blocks:
        if not _is_event(obj):
            continue
        parsed = _object_to_event(obj, default_type)
        if parsed is not None:
            events.append(parsed)
    return events


def _iter_jsonld_objects(html: str) -> list[dict[str, Any]]:
    """Достаёт каждый JSON-LD блок, разворачивает массивы и @graph в плоский список dict'ов."""
    tree = HTMLParser(html)
    objects: list[dict[str, Any]] = []
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text(strip=False)
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _flatten(data):
            if isinstance(item, dict):
                objects.append(item)
    return objects


def _flatten(data: Any) -> list[Any]:
    """Разворачивает list и @graph в плоский список объектов."""
    if isinstance(data, list):
        out: list[Any] = []
        for el in data:
            out.extend(_flatten(el))
        return out
    if isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            return _flatten(data["@graph"])
        return [data]
    return []


def _is_event(obj: dict[str, Any]) -> bool:
    t = obj.get("@type")
    if isinstance(t, list):
        return any(x in _EVENT_TYPES for x in t)
    return t in _EVENT_TYPES


def _object_to_event(obj: dict[str, Any], default_type: EventType) -> Optional[ParsedEvent]:
    """Маппинг одного JSON-LD Event → ParsedEvent. None, если нет обязательных полей."""
    title = _clean_str(obj.get("name"))
    if not title or len(title) < 3:
        return None

    date_str, time_start = _parse_datetime(obj.get("startDate"))
    if not date_str:
        return None
    _, time_end = _parse_datetime(obj.get("endDate"))

    venue_name, address = _parse_location(obj.get("location"))
    if not venue_name or not address:
        return None

    price_min, price_max, price_text = _parse_offers(obj.get("offers"))

    try:
        return ParsedEvent(
            title=title[:300],
            type=default_type,
            date=date_str,
            time_start=time_start,
            time_end=time_end,
            price_min=price_min,
            price_max=price_max,
            price_text=price_text,
            address=address,
            venue_name=venue_name,
            image_url=_parse_image(obj.get("image")),
            description=_clean_description(obj.get("description")),
            organizer=_parse_organizer(obj.get("organizer")),
        )
    except Exception as exc:  # noqa: BLE001 — невалидную запись просто пропускаем
        log.warning("jsonld.item_invalid", title=title, error=str(exc))
        return None


def _clean_str(v: Any) -> Optional[str]:
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return None


def _clean_description(v: Any) -> Optional[str]:
    s = _clean_str(v)
    return s[:500] if s else None


def _parse_datetime(v: Any) -> tuple[Optional[str], Optional[str]]:
    """ISO 8601 startDate → (YYYY-MM-DD, HH:MM|None). Поддерживает date-only и datetime."""
    s = _clean_str(v)
    if not s:
        return None, None
    # '2026-06-15T19:00:00+03:00' или '2026-06-15'
    date_part = s[:10]
    try:
        datetime.strptime(date_part, "%Y-%m-%d")
    except ValueError:
        return None, None
    time_part = None
    if "T" in s and len(s) >= 16:
        hhmm = s[11:16]
        try:
            datetime.strptime(hhmm, "%H:%M")
            time_part = hhmm
        except ValueError:
            time_part = None
    return date_part, time_part


def _parse_location(v: Any) -> tuple[Optional[str], Optional[str]]:
    """location → (venue_name, address). location.address бывает строкой или PostalAddress."""
    if isinstance(v, list):
        v = v[0] if v else None
    if not isinstance(v, dict):
        return None, None
    name = _clean_str(v.get("name"))
    addr = v.get("address")
    address: Optional[str]
    if isinstance(addr, str):
        address = _clean_str(addr)
    elif isinstance(addr, dict):
        parts = [
            _clean_str(addr.get("streetAddress")),
            _clean_str(addr.get("addressLocality")),
        ]
        address = ", ".join(p for p in parts if p) or None
    else:
        address = None
    return name, address


def _parse_offers(v: Any) -> tuple[int, int, str]:
    """offers (dict | list) → (price_min, price_max, price_text). Нет цены → 0/0/'уточняйте'."""
    offers = v if isinstance(v, list) else [v] if isinstance(v, dict) else []
    prices: list[int] = []
    for o in offers:
        if not isinstance(o, dict):
            continue
        for key in ("price", "lowPrice", "highPrice"):
            p = _to_int_price(o.get(key))
            if p is not None:
                prices.append(p)
    if not prices:
        return 0, 0, "уточняйте"
    pmin, pmax = min(prices), max(prices)
    if pmin == pmax:
        price_text = "бесплатно" if pmin == 0 else f"от {pmin} ₽"
    else:
        price_text = f"от {pmin} до {pmax} ₽"
    return pmin, pmax, price_text


def _to_int_price(v: Any) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        cleaned = v.replace(" ", "").replace(",", ".")
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    return None


def _parse_image(v: Any) -> Optional[str]:
    if isinstance(v, str):
        return _clean_str(v)
    if isinstance(v, list):
        for el in v:
            url = _parse_image(el)
            if url:
                return url
        return None
    if isinstance(v, dict):
        return _clean_str(v.get("url"))
    return None


def _parse_organizer(v: Any) -> Optional[str]:
    if isinstance(v, list):
        v = v[0] if v else None
    if isinstance(v, dict):
        return _clean_str(v.get("name"))
    return _clean_str(v)
