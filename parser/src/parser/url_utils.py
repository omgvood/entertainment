"""Резолв source_url события: event_url из LLM/JSON-LD → абсолютная ссылка, иначе фолбэк.

Вынесено из pipeline.py, чтобы переиспользовать в generic-парсере и петлях VK/TG.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

import structlog


log = structlog.get_logger(__name__)

# Мусорные значения event_url от LLM/JSON-LD — трактуем как «ссылки нет» (фолбэк на листинг).
JUNK_URLS: frozenset[str] = frozenset({"", "#", "javascript:void(0)"})

# Сокращатели/трекеры/агрегаторы, которые LLM ошибочно вытаскивает из тела VK/TG-поста.
JUNK_DOMAINS: set[str] = {
    "clck.ru", "vk.cc", "bit.ly", "t.co", "goo.gl",
    "tinyurl.com", "ow.ly", "is.gd",
    "taplink.ws", "taplink.cc",   # агрегаторы ссылок
    "goodsbuy.by",                # affiliate-редиректы из постов
}


def resolve_event_url(event_url: str | None, base_url: str) -> str:
    """event_url события → абсолютный source_url. Пусто/мусор → base_url (листинг/группа/канал).

    Относительные ссылки достраиваются по base_url. Голые ссылки-сокращатели/агрегаторы
    из тела поста (clck.ru, vk.cc, sub.taplink.ws …) отбрасываем на фолбэк.
    """
    if not event_url or event_url.strip() in JUNK_URLS:
        return base_url

    url = event_url.strip()
    parsed = urlparse(url)

    # Относительный путь («/afisha/event-slug») — собираем с base_url.
    if not parsed.netloc:
        return urljoin(base_url, url)

    # Абсолютный URL — отсекаем мусорные домены (включая поддомены: heartharmony.taplink.ws).
    domain = parsed.netloc.lower()
    if any(domain == junk or domain.endswith("." + junk) for junk in JUNK_DOMAINS):
        log.debug("resolve_event_url.junk_domain", url=url, domain=domain, fallback=base_url)
        return base_url

    return url
