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
import re

import structlog
from selectolax.parser import HTMLParser

from ..models import EventType, ParsedEvent


log = structlog.get_logger()


# ============================================================================
# СЕЛЕКТОРЫ 2ГИС — ЧИНИТЬ ТУТ.
# Классы 2ГИС обфусцированы (вида `_1kf6gff`) и меняются при редеплое их фронта.
# Если parse_cards перестал находить карточки — открой 2gis.ru/{city}/search/{query}
# в браузере, сохрани HTML (DevTools → Console: copy(document.body.outerHTML)),
# запусти debug_parse_2gis.py и обнови константы ниже + фикстуру в tests/test_playwright_2gis.py.
# Стабильные якоря (меняются реже): _NAME_SELECTOR, _ADDRESS_SELECTOR.
# ============================================================================
_CARD_SELECTOR = "div._1kf6gff, div._5b28jpo"
                                   # _1kf6gff — органические результаты
                                   # _5b28jpo — рекламные карточки (promoted)
                                   # доступ к имени и адресу одинаков для обоих типов
_LINK_SELECTOR = "a._1rehek"       # anchor на страницу заведения; .text() = название
                                   # (стабильнее, чем класс span — разные типы карточек
                                   #  используют _lvwrwt, _9r89aog и т.д.)
_ADDRESS_SELECTOR = "div._klarpw"  # строка адреса (также содержит статусы — см. _STATUS_RE)
_IMAGE_SELECTOR = "div._1dk5lq4"   # фото-div с background-image (первый = основное фото)
# Контейнер прокручиваемой выдачи (для дозагрузки lazy-load карточек).
# При несовпадении _scroll_results падает в except → fallback на page.mouse.wheel:
_RESULTS_SCROLL_SELECTOR = "div._z1qx2c"

# Строки-статусы, которые 2ГИС кладёт в тот же div._klarpw, что и адрес.
# Без ^ — ловит «Временно не работает», «До открытия 40 мин.» и т.п.
_STATUS_RE = re.compile(
    r"(закро|открыт|работ|круглосуточ|перерыв|обед|до открытия|временно|филиал)",
    re.IGNORECASE,
)

_BG_URL_2X = re.compile(r'url\(["\']?(https://[^"\')\s]+)["\']?\)\s*2x')
_BG_URL_ANY = re.compile(r'url\(["\']?(https://[^"\')\s]+)["\']?\)')

_BASE = "https://2gis.ru"
_NAV_TIMEOUT_MS = 30_000


def _extract_bg_image(style: str | None) -> str | None:
    """Извлекает URL из background-image CSS (приоритет: 2x > любой)."""
    if not style:
        return None
    m = _BG_URL_2X.search(style)
    if m:
        return m.group(1)
    m = _BG_URL_ANY.search(style)
    return m.group(1) if m else None


def parse_cards(html: str, event_type: EventType) -> list[ParsedEvent]:
    """HTML выдачи 2ГИС → список ParsedEvent (date='always'). Чистая функция, без сети.

    Карточки без названия или адреса пропускаются — для venues это шум.
    Структура выдачи задокументирована в константах-селекторах выше.
    """
    tree = HTMLParser(html)
    venues: list[ParsedEvent] = []
    seen: set[str] = set()

    for card in tree.css(_CARD_SELECTOR):
        # Имя — из anchor-ссылки на заведение; независимо от класса внутреннего span.
        link = card.css_first(_LINK_SELECTOR)
        name = link.text(strip=True).replace("\xa0", " ").strip() if link else ""
        if not name:
            continue

        # Адрес — первый _klarpw, который не является строкой статуса.
        # В одной карточке может быть несколько _klarpw: адрес + статус работы.
        address = ""
        for addr_node in card.css(_ADDRESS_SELECTOR):
            text = addr_node.text(strip=True).replace("\xa0", " ").strip()
            # Убираем суффикс «N филиала» (иногда клеится к адресу в том же узле).
            text = re.sub(r"\s*\d+\s+филиал[а-я]*\s*$", "", text).strip()
            if text and not _STATUS_RE.search(text):
                address = text
                break
        if not address:
            continue

        # Дедуп внутри одной выдачи (карточка может дублироваться при lazy-load).
        key = f"{name}|{address}"
        if key in seen:
            continue
        seen.add(key)

        # Фото: 2ГИС использует background-image вместо <img>.
        img_node = card.css_first(_IMAGE_SELECTOR)
        image_url = _extract_bg_image(img_node.attributes.get("style") if img_node else None)

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
                    district=None,  # район убран из карточки в текущей вёрстке 2ГИС
                    image_url=image_url,
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
    if not venues:
        # Помогает диагностировать: антибот-заглушка или сломанные селекторы.
        snippet = html[:2000].replace("\n", " ")
        log.warning("playwright_2gis.empty_result", city=city, query=query, html_snippet=snippet)
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
