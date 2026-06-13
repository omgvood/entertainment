"""Telegram как источник событий — посты публичных каналов через веб-превью t.me/s/.

Telegram-каналы локальных организаторов (стендап, квизы, театры) в РФ часто активнее VK
и публикуют анонсы раньше. Публичные каналы доступны без авторизации по адресу
`https://t.me/s/{channel}` — обычный HTML, парсится selectolax (как остальные источники).

Архитектура повторяет vk-posts: fetch → префильтр (classifiers.is_event_candidate) →
один LLM extract_many на канал. Дедуп постов — через raw_documents по хешу текста.

Провайдер вынесен за абстракцию TelegramProvider: сейчас единственная реализация —
TelegramHtmlProvider (веб-превью). Если HTML-превью заблокируют/сломают или понадобятся
закрытые каналы — добавится второй провайдер (например, на telethon/MTProto) без правок
pipeline. Заранее заглушку не делаем — добавим, когда появится конкретная боль.

ВНИМАНИЕ: t.me/s/ — это веб-превью, его HTML Telegram не обещает стабильным. Если разметка
поедет — чинить parse_channel_html (структура задокументирована в самой функции).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

import httpx
import structlog
from selectolax.parser import HTMLParser


log = structlog.get_logger()

_PREVIEW_BASE = "https://t.me/s"
_FETCH_TIMEOUT = 20.0


class TelegramProvider(ABC):
    """Источник постов Telegram-канала. Реализации: HTML-превью, (в будущем) MTProto."""

    @abstractmethod
    async def fetch_posts(self, channel: str, *, count: int = 50) -> list[dict[str, Any]]:
        """Посты канала, новые в конце. Каждый: {text, url, date_unix}."""
        ...


class TelegramHtmlProvider(TelegramProvider):
    """Парсит веб-превью https://t.me/s/{channel} — без авторизации, только публичные каналы."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch_posts(self, channel: str, *, count: int = 50) -> list[dict[str, Any]]:
        url = f"{_PREVIEW_BASE}/{channel}"
        resp = await self.client.get(url, follow_redirects=True, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        posts = parse_channel_html(resp.text)
        # Превью отдаёт последние посты в хронологическом порядке — берём хвост (свежие).
        return posts[-count:]


def parse_channel_html(html: str) -> list[dict[str, Any]]:
    """HTML веб-превью канала → список постов {text, url, date_unix}.

    Структура t.me/s/ (на момент написания):
      .tgme_widget_message               — контейнер поста
        .tgme_widget_message_text        — текст поста
        a.tgme_widget_message_date       — ссылка на пост (href = t.me/{channel}/{id})
          time[datetime]                 — ISO-дата публикации

    Посты без текста (только фото/видео) пропускаются — извлекать нечего.
    """
    tree = HTMLParser(html)
    posts: list[dict[str, Any]] = []
    for msg in tree.css(".tgme_widget_message"):
        text_node = msg.css_first(".tgme_widget_message_text")
        text = text_node.text(separator="\n", strip=True) if text_node else ""
        if not text:
            continue

        date_link = msg.css_first("a.tgme_widget_message_date")
        url = date_link.attributes.get("href") if date_link else None
        if not url:
            continue

        time_node = msg.css_first("time")
        iso = time_node.attributes.get("datetime") if time_node else None
        posts.append({"text": text, "url": url, "date_unix": _iso_to_unix(iso)})
    return posts


def _iso_to_unix(iso: Optional[str]) -> Optional[float]:
    """ISO-8601 ('2026-06-13T12:00:00+00:00') → Unix timestamp. None/мусор → None."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None
