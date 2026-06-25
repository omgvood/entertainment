"""Рендер произвольной SPA-страницы через Playwright → готовый HTML для batch-извлечения.

Зачем: сайты на Nuxt/Next/React (permopera.ru, permm.ru, …) при обычном httpx GET отдают
пустой HTML-скелет — события дорисовываются JavaScript-ом в браузере. Этот модуль поднимает
headless Chromium, ждёт окончания JS-рендера и возвращает полный DOM. Дальше HTML идёт в
нетронутую цепочку pipeline._run_batch_source (JSON-LD → LLM), как для статических листингов.

Отличие от sources/playwright_2gis.py: там навигация по выдаче 2ГИС со скроллом и парсингом
карточек; здесь — универсальный рендер одного URL без знания структуры сайта.

Зависимость playwright — опциональная (`pip install -e '.[playwright]'`), поэтому импорт
ленивый, внутри функции. _apply_stealth дублируется здесь намеренно (не импортируется из
playwright_2gis), чтобы модуль был самодостаточным и не падал при правках 2ГИС-скрейпера.
"""

from __future__ import annotations

import asyncio

import structlog


log = structlog.get_logger()


_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_NAV_TIMEOUT_MS = 30_000


async def render_page(url: str, *, timeout_ms: int = _NAV_TIMEOUT_MS) -> str:
    """Headless Chromium → отрендеренный HTML (полный DOM после JS-гидратации).

    - Ждёт `networkidle` (нет сетевой активности 500мс) — момент, когда Nuxt дорисовал афишу.
    - При таймауте networkidle (тяжёлая аналитика держит соединение) — не падает, берёт
      что уже отрендерилось.
    - Явно проверяет HTTP-статус: page.goto НЕ бросает на 4xx/5xx (в отличие от httpx) —
      иначе скормили бы LLM кастомную страницу 404 и сожгли токены.
    - Минимальный скролл вниз — триггерит lazy-load карточек на длинных листингах.
    - try/finally вокруг браузера и контекста — иначе RuntimeError(HTTP) оставил бы
      процесс Chromium висеть зомби в долгоживущем прогоне парсера.

    Импорт playwright ленивый — зависимость опциональная (extras [playwright]).
    """
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise RuntimeError(
            "playwright не установлен. Поставь: pip install -e '.[playwright]' "
            "&& playwright install chromium"
        ) from exc

    log.info("playwright_fetcher.start", url=url)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(locale="ru-RU", user_agent=_USER_AGENT)
            try:
                page = await context.new_page()
                await _apply_stealth(page)

                try:
                    response = await page.goto(
                        url, timeout=timeout_ms, wait_until="networkidle"
                    )
                except PlaywrightTimeoutError:
                    # networkidle не наступил (метрики/аналитика) — DOM обычно уже построен.
                    log.warning("playwright_fetcher.networkidle_timeout", url=url)
                    response = None

                if response is not None and response.status >= 400:
                    raise RuntimeError(
                        f"playwright_fetcher: HTTP {response.status} for {url}"
                    )

                # Триггерим lazy-load: один скролл вниз + тик event loop на подгрузку.
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.0)

                html = await page.content()
            finally:
                await context.close()
        finally:
            await browser.close()

    log.info("playwright_fetcher.ok", url=url, html_len=len(html))
    return html


async def _apply_stealth(page) -> None:
    """playwright-stealth, если установлен. Без него работает, но риск антибота выше."""
    try:
        from playwright_stealth import stealth_async  # type: ignore

        await stealth_async(page)
    except ImportError:
        log.debug("playwright_fetcher.no_stealth")
    except Exception as exc:  # noqa: BLE001
        log.warning("playwright_fetcher.stealth_failed", error=str(exc))
