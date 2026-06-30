"""Клиент Пермского театра оперы и балета (permopera.ru).

Афиша месяца отдаётся эндпоинтом
  GET /playbills/playbill?month=YYYY-MM-01&front=1&json=1
но это НЕ структурированный JSON: ответ — {"content": "<html-фрагмент карточек>"}.
Карточки парсим selectolax по стабильным data-атрибутам (data-post-id / event-date / event-card).
Браузер и LLM не нужны. Эндпоинт требует браузерных заголовков (X-Requested-With/Referer),
иначе отдаёт HTTP 400.

Адреса/цены в карточке нет → venue/address из seeds, price 0 / «по билетам».
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import httpx
import structlog
from selectolax.parser import HTMLParser

from ..models import ParsedEvent


log = structlog.get_logger()

_BASE = "https://permopera.ru"
_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{_BASE}/playbills/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


class PermOperaClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(
        self, *, event_type: str, venue_name: str, address: str
    ) -> list[tuple[ParsedEvent, str]]:
        today = date.today()
        results: list[tuple[ParsedEvent, str]] = []
        seen: set[str] = set()

        # Текущий и следующий месяц — афиша на ~60 дней вперёд.
        for month in (today.replace(day=1), _next_month(today)):
            html = await self._fetch_month(month.isoformat())
            for parsed, source_url in parse_cards(
                html,
                event_type=event_type,
                venue_name=venue_name,
                address=address,
                today=today.isoformat(),
            ):
                if source_url in seen:
                    continue
                seen.add(source_url)
                results.append((parsed, source_url))

        return results

    async def _fetch_month(self, month: str) -> str:
        url = f"{_BASE}/playbills/playbill"
        resp = await self._client.get(
            url,
            params={"month": month, "front": 1, "json": 1},
            headers=_HEADERS,
            timeout=20.0,
        )
        resp.raise_for_status()  # 400 (нет заголовков/токена) → HTTPStatusError → warning в pipeline
        raw = resp.json()
        return raw.get("content", "") if isinstance(raw, dict) else ""


def _next_month(d: date) -> date:
    return d.replace(day=1, month=d.month % 12 + 1, year=d.year + (1 if d.month == 12 else 0))


def parse_cards(
    html: str, *, event_type: str, venue_name: str, address: str, today: str
) -> list[tuple[ParsedEvent, str]]:
    """Чистая функция: HTML-фрагмент афиши → [(ParsedEvent, source_url)]. Без сети.

    Стабильные якоря разметки (ЧИНИТЬ ТУТ, если вёрстка permopera поедет):
      article[data-element="event-card"]      — карточка спектакля
      link[data-element="event-date"] content — ISO дата-время "YYYY-MM-DDTHH:MM:SS"
      a[href*="/playbills/playbill/"]          — ссылка на спектакль + его название
    """
    out: list[tuple[ParsedEvent, str]] = []
    for card in HTMLParser(html).css('article[data-element="event-card"]'):
        date_str, time_str = _card_datetime(card)
        if not date_str or date_str < today:  # пропускаем прошедшие спектакли
            continue

        link = card.css_first('a[href*="/playbills/playbill/"]')
        if link is None:
            continue
        title = " ".join(link.text().split())
        href = link.attributes.get("href") or ""
        if not title or not href:
            continue

        img = card.css_first("img")
        image_url = img.attributes.get("src") if img else None

        out.append(
            (
                ParsedEvent(
                    title=title[:300],
                    type=event_type,  # type: ignore[arg-type]
                    date=date_str,
                    time_start=time_str,
                    venue_name=venue_name,
                    address=address,
                    price_min=0,
                    price_max=0,
                    price_text="по билетам",
                    image_url=image_url,
                    organizer=venue_name,
                ),
                href,
            )
        )
    return out


def _card_datetime(card) -> tuple[Optional[str], Optional[str]]:
    """('YYYY-MM-DD', 'HH:MM') из link[data-element=event-date]; фолбэк на data-calendar-date."""
    link = card.css_first('link[data-element="event-date"]')
    content = link.attributes.get("content") if link else None
    if content and "T" in content:
        date_part, _, time_part = content.partition("T")
        return date_part, time_part[:5] or None
    return card.attributes.get("data-calendar-date"), None
