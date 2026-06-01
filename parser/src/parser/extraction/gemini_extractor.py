"""Google Gemini (Flash / Flash-Lite) экстрактор события.

Использует нативный structured output: response_mime_type=application/json
+ response_schema=ParsedEvent (для одиночного) или list[ParsedEvent] (для batch).
"""

from __future__ import annotations

import json
from datetime import date

import structlog
from google import genai
from google.genai import types
from selectolax.parser import HTMLParser

from ..models import ParsedEvent
from .base import ExtractorError, LLMExtractor


log = structlog.get_logger()


_SYSTEM_PROMPT_SINGLE = """Ты — экстрактор данных о развлекательных событиях в Перми. На вход — HTML страницы события. На выход — JSON по предоставленной схеме.

Правила:
- Заполняй ТОЛЬКО то, что явно указано на странице. Не выдумывай.
- Если опциональное поле не указано или неоднозначно — null.
- price_min/price_max в рублях, целые числа. Если на странице одна цена — повтори в price_min и price_max.
- price_text — готовая строка для UI: 'от 500 ₽', 'от 500 до 1000 ₽', 'от 300 ₽ за дорожку/час'.
- Для боулинга/бильярда/картинга (мест с постоянным расписанием) date='always'.
- date в формате YYYY-MM-DD для конкретных событий. time_start/end в формате HH:MM.
- image_url — это должна быть РЕАЛЬНАЯ ФОТОГРАФИЯ события или площадки (типичный JPG/PNG/WebP постер 400+px). НЕ svg-иконки сложности, не маркеры, не маленькие значки рейтинга. Если нет нормальной фотографии — null.
- Если страница не похожа на страницу события — заполни title значением "NOT_AN_EVENT" (валидация на нашей стороне отбросит).

Про год даты:
- Если на странице дата указана БЕЗ года (например, «23 мая», «12 июня (пт)») — используй год из ориентира «Сегодня» в user-сообщении.
- Если получившаяся дата ОКАЗАЛАСЬ В ПРОШЛОМ относительно «Сегодня» — возьми следующий год.
- НИКОГДА не подставляй год из своих знаний/обучения — всегда смотри на ориентир «Сегодня»."""


_SYSTEM_PROMPT_BATCH = """Ты — экстрактор данных о развлекательных событиях в Перми. На вход — HTML страницы СО СПИСКОМ событий (расписание, афиша). На выход — JSON-массив со ВСЕМИ событиями, которые упомянуты на странице.

КРИТИЧЕСКИ ВАЖНО — полнота:
- ВЕРНИ ВСЕ события без исключения. Не пропускай ни одной карточки. На странице обычно 10-30 событий — должны быть все.
- Просканируй HTML до конца. Не останавливайся на первых 5-10 — иди дальше, пока не закончатся карточки/блоки событий.
- Карточки обычно повторяются в одинаковой структуре — найди этот паттерн и пройди ПО ВСЕМ его повторениям.
- Финально пересчитай свой массив и убедись, что число объектов = числу карточек на странице.

Правила извлечения:
- Заполняй ТОЛЬКО то, что явно указано. Не выдумывай.
- Если опциональное поле не указано или неоднозначно — null.
- price_min/price_max в рублях, целые числа. Если цена одна — повтори в обоих полях.
- price_text — готовая строка для UI: 'от 500 ₽', 'от 500 до 1000 ₽'.
- Для мест с постоянным расписанием (боулинг/бильярд/картинг) — date='always'.
- date в формате YYYY-MM-DD. time_start/end в формате HH:MM.
- image_url — это должна быть РЕАЛЬНАЯ ФОТОГРАФИЯ события или площадки (типичный JPG/PNG/WebP постер 400+px). Игнорируй:
  • SVG-иконки и пиктограммы (рейтинги, уровни сложности, маркеры, стрелки, logo)
  • Маленькие аватарки и значки (<200px)
  • Спрайты UI-элементов
  Если на странице нет нормальной фотографии для конкретного события — используй фото площадки/организатора (обычно есть большое промо-изображение в шапке листинга). Если совсем ничего подходящего нет — null.
- НЕ используй значение "NOT_AN_EVENT" — в batch-режиме при отсутствии событий просто верни пустой массив [].

Про год даты:
- Если на странице дата указана БЕЗ года (например, «23 мая», «12 июня (пт)») — используй год из ориентира «Сегодня» в user-сообщении.
- Если получившаяся дата ОКАЗАЛАСЬ В ПРОШЛОМ относительно «Сегодня» — возьми следующий год (расписания публикуются на ближайшие месяцы вперёд).
- НИКОГДА не подставляй год из своих знаний/обучения — всегда смотри на ориентир «Сегодня»."""


class GeminiExtractor(LLMExtractor):
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def extract(self, html: str, source_url: str) -> ParsedEvent:
        cleaned = _clean_html(html)
        today = date.today().isoformat()
        user_msg = (
            f"Источник: {source_url}\n"
            f"Сегодня: {today}\n\n"
            f"HTML страницы события:\n\n{cleaned}"
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT_SINGLE,
                    response_mime_type="application/json",
                    response_schema=ParsedEvent,
                    temperature=0,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise ExtractorError(f"Gemini API error для {source_url}: {exc}") from exc

        if not response.text:
            raise ExtractorError(
                f"Gemini вернул пустой ответ для {source_url}. "
                f"Возможно, блок safety: {getattr(response, 'prompt_feedback', None)}"
            )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ExtractorError(
                f"Gemini вернул не-JSON для {source_url}: {response.text[:200]!r}"
            ) from exc

        try:
            event = ParsedEvent.model_validate(data)
        except Exception as exc:
            raise ExtractorError(
                f"LLM вернул невалидный event для {source_url}: {exc}"
            ) from exc

        if event.title.strip() == "NOT_AN_EVENT":
            raise ExtractorError(f"LLM пометил страницу как не-событие: {source_url}")

        return event

    async def extract_many(self, html: str, source_url: str) -> list[ParsedEvent]:
        # Листинг может быть жирным (300+ KB). Gemini 2.5 Flash/Lite держат 1M контекста,
        # обрезать почти не нужно — берём щедрый лимит. Перед отправкой логируем размеры.
        cleaned = _clean_html(html, max_chars=800_000)
        log.info(
            "batch.input_size",
            source_url=source_url,
            raw_chars=len(html),
            cleaned_chars=len(cleaned),
        )
        today = date.today().isoformat()
        user_msg = (
            f"Источник: {source_url}\n"
            f"Сегодня: {today}\n\n"
            f"HTML страницы расписания/афиши:\n\n{cleaned}"
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=user_msg,
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT_BATCH,
                    response_mime_type="application/json",
                    response_schema=list[ParsedEvent],
                    temperature=0,
                    # больше токенов на выход — batch ответ может быть длинным
                    max_output_tokens=20_000,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            raise ExtractorError(f"Gemini API error для {source_url}: {exc}") from exc

        if not response.text:
            raise ExtractorError(
                f"Gemini вернул пустой ответ для {source_url}. "
                f"Возможно, блок safety: {getattr(response, 'prompt_feedback', None)}"
            )

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise ExtractorError(
                f"Gemini вернул не-JSON для {source_url}: {response.text[:200]!r}"
            ) from exc

        if not isinstance(data, list):
            raise ExtractorError(
                f"Gemini в batch-режиме вернул не-массив для {source_url}: тип {type(data).__name__}"
            )

        results: list[ParsedEvent] = []
        for idx, item in enumerate(data):
            try:
                event = ParsedEvent.model_validate(item)
                if event.title.strip() == "NOT_AN_EVENT":
                    continue
                results.append(event)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "extract.batch.item_invalid",
                    source_url=source_url,
                    index=idx,
                    error=str(exc),
                )
        return results


def _clean_html(html: str, max_chars: int = 60_000) -> str:
    """Выбрасываем теги, которые не несут смысла для извлечения, и обрезаем размер."""
    tree = HTMLParser(html)
    for tag in ["script", "style", "noscript", "svg", "iframe", "head"]:
        for node in tree.css(tag):
            node.decompose()
    body = tree.css_first("body") or tree.root
    text = body.html or ""
    if len(text) > max_chars:
        text = text[:max_chars] + "\n<!-- truncated -->"
    return text
