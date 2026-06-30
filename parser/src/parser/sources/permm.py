"""Клиент музея современного искусства ПЕРММ (permm.ru).

Сайт — SPA, статический HTML пуст. Под капотом открытые JSON-эндпоинты:
  GET /json/exhibitions/active  — активные выставки (диапазон дат)
  GET /json/events/sub/home     — ближайшие события (экскурсии, лекции, фестивали)

LLM и браузер не нужны — JSON структурирован. Адрес/площадки в JSON нет, берём из seeds
(venue_name/address). Цены тоже нет → 0 / «по билетам».
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
import structlog

from ..http_utils import fetch_with_retry
from ..models import ParsedEvent


log = structlog.get_logger()

_BASE = "https://permm.ru"
_EXHIBITIONS_URL = f"{_BASE}/json/exhibitions/active"
_EVENTS_URL = f"{_BASE}/json/events/sub/home"


class PermMuseumClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(
        self, *, event_type: str, venue_name: str, address: str
    ) -> list[tuple[ParsedEvent, str]]:
        results: list[tuple[ParsedEvent, str]] = []
        seen: set[str] = set()

        exhibitions = (await self._fetch(_EXHIBITIONS_URL)).get("data") or []
        for raw in exhibitions:
            self._collect(raw, results, seen, event_type=event_type, venue_name=venue_name, address=address)

        # У /events/sub/home структура другая: data[].events — список списков событий.
        for group in (await self._fetch(_EVENTS_URL)).get("data") or []:
            for bucket in group.get("events") or []:
                for raw in bucket if isinstance(bucket, list) else [bucket]:
                    self._collect(raw, results, seen, event_type=event_type, venue_name=venue_name, address=address)

        return results

    async def _fetch(self, url: str) -> dict:
        resp = await fetch_with_retry(self._client, url)
        raw = resp.json()
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _collect(raw, results, seen, **kwargs) -> None:
        item_id = str(raw.get("id") or raw.get("url") or "")
        if item_id and item_id in seen:
            return
        if item_id:
            seen.add(item_id)
        parsed = _map_item(raw, **kwargs)
        if parsed is None:
            log.warning("permm.skipped_item", id=item_id, raw_keys=list(raw.keys()))
            return
        url = raw.get("url") or ""
        source_url = f"{_BASE}{url}" if url.startswith("/") else (url or _BASE)
        results.append((parsed, source_url))


def _parse_date(value: Optional[str]) -> Optional[str]:
    """'DD.MM.YYYY' → 'YYYY-MM-DD'. None/мусор → None."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _resolve_image(media: Optional[str]) -> Optional[str]:
    """media_url_extended бывает '/storage/media/x.jpg' либо проксированный
    '/storage/tilda/https://static.tildacdn.com/...'. Достаём реальный URL."""
    if not media or not isinstance(media, str):
        return None
    if media.startswith("http"):
        return media
    idx = media.find("http")
    if idx > 0:  # встроенный абсолютный URL после префикса прокси
        return media[idx:]
    return f"{_BASE}{media}" if media.startswith("/") else media


def _map_item(
    raw: dict, *, event_type: str, venue_name: str, address: str
) -> Optional[ParsedEvent]:
    title = (raw.get("title_extended") or "").strip()
    starts_at = _parse_date(raw.get("starts_at"))
    ends_at = _parse_date(raw.get("ends_at"))

    if not title or not starts_at:
        return None

    # Диапазонная выставка → date=ends_at: slug стабилен, карточка видна пока активна,
    # TTL удалит её когда ends_at < сегодня. Одиночное событие → date=starts_at.
    date_str = ends_at if (ends_at and ends_at != starts_at) else starts_at

    description = raw.get("sub_title_extended") or None
    if description:
        description = description[:500]

    return ParsedEvent(
        title=title[:300],
        type=event_type,  # type: ignore[arg-type]
        date=date_str,
        venue_name=venue_name,
        address=address,
        price_min=0,
        price_max=0,
        price_text="по билетам",
        image_url=_resolve_image(raw.get("media_url_extended")),
        description=description,
        organizer=venue_name,
    )
