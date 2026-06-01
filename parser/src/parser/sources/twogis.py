"""2ГИС Catalog API клиент.

Отдаёт `ParsedEvent[]` для запроса вида «боулинг Пермь». Каждая организация → событие с date='always'.

Документация: https://docs.2gis.com/ru/api/search
Endpoint: GET https://catalog.api.2gis.com/3.0/items

LLM в этом источнике НЕ участвует — JSON ответа маппится в ParsedEvent напрямую.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
import structlog

from ..models import EventType, ParsedEvent


log = structlog.get_logger()

_API_BASE = "https://catalog.api.2gis.com/3.0/items"

_FIELDS = ",".join([
    "items.id",
    "items.name_ex",
    "items.full_address_name",
    "items.address_name",
    "items.address_comment",
    "items.point",
    "items.schedule",
    "items.contact_groups",
    "items.external_content",  # фотографии
    "items.adm_div",
])


class TwoGisClient:
    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self.client = client
        self.api_key = api_key

    async def search(
        self,
        query: str,
        event_type: EventType,
        *,
        max_items: int = 50,
    ) -> list[ParsedEvent]:
        """Ищет организации по запросу. Возвращает массив ParsedEvent с date='always'.

        API 2ГИС отдаёт максимум 10 записей за запрос, поэтому страничим
        page=1,2,... до достижения max_items или пустого ответа.
        """
        PAGE_SIZE = 10  # потолок API
        max_pages = max(1, (max_items + PAGE_SIZE - 1) // PAGE_SIZE)

        events: list[ParsedEvent] = []
        total_items_seen = 0

        for page in range(1, max_pages + 1):
            params = {
                "q": query,
                "key": self.api_key,
                "fields": _FIELDS,
                "page_size": str(PAGE_SIZE),
                "page": str(page),
                "type": "branch",
            }
            resp = await self.client.get(_API_BASE, params=params, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()

            meta_code = data.get("meta", {}).get("code")
            if meta_code == 404:
                # Нормальный признак «страниц больше нет».
                break
            if meta_code and meta_code != 200:
                raise RuntimeError(
                    f"2GIS API вернул meta.code={meta_code}: "
                    f"{data.get('meta', {}).get('error', {})}"
                )

            items = data.get("result", {}).get("items", []) or []
            if not items:
                break
            total_items_seen += len(items)

            for it in items:
                try:
                    ev = _item_to_event(it, event_type)
                    events.append(ev)
                except Exception as exc:  # noqa: BLE001
                    log.warning(
                        "twogis.item.skipped",
                        error=str(exc),
                        item_id=it.get("id"),
                        name=(it.get("name_ex") or {}).get("primary"),
                    )

            # Дальше идти бессмысленно — последняя страница пришла неполной.
            if len(items) < PAGE_SIZE:
                break

        log.info(
            "twogis.search.ok",
            query=query,
            items_seen=total_items_seen,
            extracted=len(events),
        )
        return events


def _item_to_event(item: dict[str, Any], event_type: EventType) -> ParsedEvent:
    name_ex = item.get("name_ex") or {}
    name = name_ex.get("primary") or name_ex.get("name") or item.get("name", "")
    if not name:
        raise ValueError("у организации нет name")

    address = (
        item.get("full_address_name")
        or item.get("address_name")
        or item.get("address_comment")
        or ""
    )
    if not address:
        raise ValueError("у организации нет адреса")

    district = _district_from_adm_div(item.get("adm_div") or [])
    image_url = _photo_from_external_content(item.get("external_content") or [])

    return ParsedEvent(
        title=name,
        type=event_type,
        date="always",
        price_min=0,
        price_max=0,
        price_text="по тарифам заведения",
        address=address,
        venue_name=name,
        district=district,
        image_url=image_url,
    )


def _district_from_adm_div(adm_div: list[dict[str, Any]]) -> Optional[str]:
    """В 2ГИС adm_div — массив с city/district/etc. Ищем элемент с type=district."""
    for d in adm_div:
        if d.get("type") == "district":
            return d.get("name")
    return None


def _photo_from_external_content(ext: list[dict[str, Any]]) -> Optional[str]:
    """external_content — массив, ищем main_photo."""
    for c in ext:
        if c.get("subtype") in ("main_photo", "photo"):
            url = c.get("main_photo_url") or c.get("url")
            if url:
                return url
    return None
