"""QuizPlease API клиент (расписание игр по городу).

Endpoint: GET https://api.quizplease.ru/api/games/schedule/{city_id}
Документация: отсутствует публично; endpoint обнаружен через анализ Nuxt-бандла.

Сайт quizplease.ru — SPA (Nuxt), статический HTML не содержит событий.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
import structlog

from ..http_utils import fetch_with_retry
from ..models import ParsedEvent


log = structlog.get_logger()

_API_BASE = "https://api.quizplease.ru/api/games/schedule"
_PER_PAGE = 30
_MAX_PAGES = 20


class QuizPleaseClient:
    def __init__(self, client: httpx.AsyncClient, city_slug: str) -> None:
        self._client = client
        self._city_slug = city_slug

    async def search(self, city_id: int) -> list[tuple[ParsedEvent, str]]:
        results: list[tuple[ParsedEvent, str]] = []
        seen: set[str] = set()
        schedule_url = f"https://{self._city_slug}.quizplease.ru/schedule"

        for page in range(1, _MAX_PAGES + 1):
            games, total_pages = await self._fetch_page(city_id, page)
            if not games:
                break
            for game in games:
                gid = str(game.get("id") or "")
                if gid and gid in seen:
                    continue
                if gid:
                    seen.add(gid)
                parsed = _map_game(game)
                if parsed is None:
                    log.warning("quizplease.skipped_game", id=gid, raw_keys=list(game.keys()))
                    continue
                # URL полей в API нет — fallback на страницу расписания
                event_url = game.get("url") or schedule_url
                results.append((parsed, event_url))
            if page >= total_pages or len(games) < _PER_PAGE:
                break

        return results

    async def _fetch_page(self, city_id: int, page: int) -> tuple[list[dict], int]:
        resp = await fetch_with_retry(
            self._client,
            f"{_API_BASE}/{city_id}",
            params={"per_page": _PER_PAGE, "order": "date", "page": page},
        )
        raw = resp.json()
        # Структура: {"status": ..., "data": {"data": [...], "pagination": {...}}}
        inner = raw.get("data", {}) if isinstance(raw, dict) else {}
        games = inner.get("data") or []
        pagination = inner.get("pagination") or {}
        total_pages = int(pagination.get("total_pages") or 1)
        return games, total_pages


def _map_game(game: dict) -> Optional[ParsedEvent]:
    title = game.get("title") or game.get("name")
    raw_date = game.get("date")

    if not title or not raw_date:
        return None
    if not isinstance(raw_date, str):
        return None

    # Формат API: "DD.MM.YYYY HH:MM"
    try:
        dt = datetime.strptime(raw_date, "%d.%m.%Y %H:%M")
    except ValueError:
        return None

    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M")

    place = game.get("place") or {}
    venue_name = place.get("title") or "QuizPlease"
    address = place.get("address_ru") or place.get("address") or ""

    image_url = None
    template = game.get("template") or {}
    if isinstance(template, dict):
        image_url = template.get("background_pc") or template.get("background_tablet")

    price_val = 0
    raw_price = game.get("price") or game.get("current_price")
    if raw_price is not None:
        try:
            price_val = int(raw_price)
        except (TypeError, ValueError):
            price_val = 0

    price_text = f"{price_val} ₽" if price_val else "Уточняйте у организатора"

    return ParsedEvent(
        title=title,
        type="quiz",
        date=date_str,
        time_start=time_str,
        venue_name=venue_name,
        address=address,
        price_min=price_val,
        price_max=price_val,
        price_text=price_text,
        image_url=image_url,
        organizer="QuizPlease",
    )
