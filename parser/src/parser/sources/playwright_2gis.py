"""2ГИС через браузер (Playwright) — fallback-источник для venues, когда платный API недоступен.

Контур VENUES, не events: отдаёт `ParsedEvent[]` с date='always' (как twogis.py), которые
CLI `refresh-venues` маппит в строки таблицы `venues` (см. validator.to_venue). 2ГИС Catalog
API остаётся primary; этот скрейпер включается только при ошибке/пустом результате API либо
явным флагом `--source playwright`.

Почему Playwright, а не Selenium: легче в CI (официальный GitHub Action + `playwright install`),
нативный async, headless chromium из коробки. Зависимость опциональная (`pip install -e .[playwright]`),
поэтому импорт playwright — ленивый, внутри функций.

⚠️ Антибот 2ГИС: SPA с обфусцированным HTML и проверками на автоматизацию. Применяем
playwright-stealth (если установлен) + случайные задержки. Это хрупко по своей природе — если
сбор перестал работать, в первую очередь смотри СЕЛЕКТОРЫ ниже и не забывай про ручной ввод
заведений через Supabase Table Editor (source='manual', автосбор их не трогает).
"""

from __future__ import annotations

import asyncio
import random
from typing import Optional

import structlog
from selectolax.parser import HTMLParser

from ..models import EventType, ParsedEvent


log = structlog.get_logger()


# ============================================================================
# СЕЛЕКТОРЫ 2ГИС — ЧИНИТЬ ТУТ.
# Классы 2ГИС обфусцированы (вида `_1kqrd4hi`) и меняются при редеплое их фронта.
# Если parse_cards перестал находить карточки — открой 2gis.ru/{city}/search/{query}
# в браузере с DevTools, найди контейнер карточки организации в выдаче и обнови
# селекторы ниже (и заодно фикстуру в tests/test_playwright_2gis.py).
# ============================================================================
_CARD_SELECTOR = "div._1kqrd4hi"        # контейнер одной карточки организации
_NAME_SELECTOR = "span._lvwrwt"         # название заведения
_ADDRESS_SELECTOR = "div._klarpw"       # строка адреса под названием
_DISTRICT_SELECTOR = "div._14quei"      # район (часто отсутствует)
_IMAGE_SELECTOR = "img"                 # превью-фото карточки
# Контейнер прокручиваемой выдачи (для дозагрузки lazy-load карточек):
_RESULTS_SCROLL_SELECTOR = "div._z1qx2c"

_BASE = "https://2gis.ru"
_NAV_TIMEOUT_MS = 30_000


def parse_cards(html: str, event_type: EventType) -> list[ParsedEvent]:
    """HTML выдачи 2ГИС → список ParsedEvent (date='always'). Чистая функция, без сети.

    Карточки без названия или адреса пропускаются — для venues это шум.
    Структура выдачи задокументирована в константах-селекторах выше.
    """
    tree = HTMLParser(html)
    venues: list[ParsedEvent] = []
    seen: set[str] = set()

    for card in tree.css(_CARD_SELECTOR):
        name_node = card.css_first(_NAME_SELECTOR)
        name = name_node.text(strip=True) if name_node else ""
        if not name:
            continue

        addr_node = card.css_first(_ADDRESS_SELECTOR)
        address = addr_node.text(strip=True) if addr_node else ""
        if not address:
            continue

        # Дедуп внутри одной выдачи (карточка может дублироваться при lazy-load).
        key = f"{name}|{address}"
        if key in seen:
            continue
        seen.add(key)

        district_node = card.css_first(_DISTRICT_SELECTOR)
        district = district_node.text(strip=True) if district_node else None

        img_node = card.css_first(_IMAGE_SELECTOR)
        image_url = img_node.attributes.get("src") if img_node else None

        try:
            venues.append(
                ParsedEvent(
                    title=name,
                    type=event_type,
                    date="always",
                    price_min=0,
                    price_max=0,
                    price_text="по тарифам заведения",
                    address=address,
                    venue_name=name,
                    district=district,
                    image_url=image_url or None,
                )
            )
        except Exception as exc:  # noqa: BLE001 — битую карточку просто пропускаем
            log.warning("playwright_2gis.card.skipped", error=str(exc), name=name)

    return venues


async def scrape_venues(
    city: str,
    query: str,
    event_type: EventType,
    *,
    max_scrolls: int = 12,
    headless: bool = True,
) -> list[ParsedEvent]:
    """Браузерный сбор заведений: 2gis.ru/{city}/search/{query} → скрол → parse_cards.

    Импорт playwright ленивый — зависимость опциональная (group [playwright]).
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise RuntimeError(
            "playwright не установлен. Поставь: pip install -e '.[playwright]' "
            "&& playwright install chromium"
        ) from exc

    url = f"{_BASE}/{city}/search/{query}"
    log.info("playwright_2gis.start", city=city, query=query, url=url)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await _apply_stealth(page)
        try:
            await page.goto(url, timeout=_NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            await _human_pause(1.5, 3.0)
            await _scroll_results(page, max_scrolls)
            html = await page.content()
        finally:
            await context.close()
            await browser.close()

    venues = parse_cards(html, event_type)
    log.info("playwright_2gis.ok", city=city, query=query, extracted=len(venues))
    return venues


async def _apply_stealth(page) -> None:
    """playwright-stealth, если доступен. Без него работает, но риск антибота выше."""
    try:
        from playwright_stealth import stealth_async  # type: ignore
    except ImportError:
        log.debug("playwright_2gis.no_stealth")
        return
    try:
        await stealth_async(page)
    except Exception as exc:  # noqa: BLE001
        log.warning("playwright_2gis.stealth_failed", error=str(exc))


async def _scroll_results(page, max_scrolls: int) -> None:
    """Скроллит панель выдачи для дозагрузки lazy-load карточек со случайными паузами."""
    for _ in range(max_scrolls):
        try:
            await page.eval_on_selector(
                _RESULTS_SCROLL_SELECTOR,
                "el => el.scrollBy(0, el.scrollHeight)",
            )
        except Exception:  # noqa: BLE001 — если контейнер не нашли, скроллим окно
            await page.mouse.wheel(0, 4000)
        await _human_pause(0.8, 1.8)


async def _human_pause(lo: float, hi: float) -> None:
    await asyncio.sleep(random.uniform(lo, hi))
