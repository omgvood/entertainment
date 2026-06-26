"""Groq (openai/gpt-oss-120b и др.) экстрактор события.

Отличия от Gemini:
- Schema не enforced на стороне API. Используем response_format=json_object — модель
  гарантированно вернёт валидный JSON, но не гарантированно по нашей схеме. Поэтому
  схему прокидываем в system-prompt и валидируем Pydantic'ом на нашей стороне.
- Для batch просим модель вернуть {"events": [...]} (top-level массив в json_object не
  допускается Groq API — нужен объект).
- API OpenAI-совместимый.

TPM free-tier у gpt-oss (8K) ниже, чем был у прежней llama-3.3-70b (12K): пачка из 5 постов
(~11k токенов) не влезает и даёт 413 Request too large. Поэтому extract_many на 413 делит
батч пополам по границам постов (маркеры «=== POST <url> ===») и переизвлекает рекурсивно.
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import structlog
from groq import AsyncGroq
from markdownify import markdownify
from selectolax.parser import HTMLParser

from ..models import ParsedEvent
from ._errors import is_rate_limit, is_request_too_large
from .base import ExtractorError, LLMExtractor, RateLimitError
from .prompts import DATE_ALWAYS_INSTRUCTIONS


log = structlog.get_logger()

_POST_MARKER = "=== POST "  # граница поста в батче VK/TG (pipeline вставляет «=== POST <url> ===»)

_DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
_MONTHS_RU = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def _today_ru() -> str:
    """Дата «Сегодня» с днём недели на русском (без системной locale) — ориентир для LLM."""
    d = date.today()
    return f"{_DAYS_RU[d.weekday()]}, {d.day} {_MONTHS_RU[d.month - 1]} {d.year} года"


def _schema_for_prompt() -> str:
    """JSON-schema ParsedEvent в виде строки, чтобы вставить в system-prompt."""
    schema = ParsedEvent.model_json_schema()
    return json.dumps(schema, ensure_ascii=False, indent=2)


_SCHEMA_TEXT = _schema_for_prompt()


_SYSTEM_PROMPT_SINGLE = f"""Ты — экстрактор данных о развлекательных событиях в Перми. На вход — HTML страницы события. На выход — ОДИН JSON-объект по нижеуказанной схеме.

JSON Schema события (Pydantic):
{_SCHEMA_TEXT}

Правила:
- Возвращай ТОЛЬКО валидный JSON-объект, без markdown-обёртки, без комментариев.
- Заполняй ТОЛЬКО то, что явно указано на странице. Не выдумывай.
- Если опциональное поле не указано или неоднозначно — null.
- price_min/price_max в рублях, целые числа. Если цена одна — повтори в обоих полях.
- price_text — готовая строка для UI: 'от 500 ₽', 'от 500 до 1000 ₽'.
{DATE_ALWAYS_INSTRUCTIONS}
- date в формате YYYY-MM-DD. time_start/end в формате HH:MM.
- image_url — РЕАЛЬНАЯ фотография (jpg/png/webp 400+px), НЕ svg-иконка/значок. Иначе null.
- organizer — название организатора/компании-устроителя (например 'QuizPlease'), если явно указано; иначе null.
- event_url — прямая ссылка на страницу конкретного события (искать в <link rel="canonical"> или <meta property="og:url">). Если страница сама является страницей события — верни её URL. Если это листинг — null.
- tags — выбери из ЗАКРЫТОГО набора (можно несколько/ноль): "для компании", "для пары", "для детей", "интеллектуальное", "активное", "творческое", "вечером", "днём", "в помещении", "на улице", "бесплатно". Свои теги не придумывай.
- Если страница не похожа на событие — в title значение "NOT_AN_EVENT".

Про год даты:
- Если на странице дата без года — бери год из ориентира «Сегодня» в user-сообщении.
- Если получившаяся дата в прошлом — возьми следующий год.
- НЕ подставляй год из своих знаний — смотри на ориентир «Сегодня»."""


_SYSTEM_PROMPT_BATCH = f"""Ты — экстрактор данных о развлекательных событиях в Перми. На вход — HTML страницы со списком событий. На выход — ОДИН JSON-объект формата {{"events": [<event1>, <event2>, ...]}}, где каждый event соответствует нижеуказанной схеме.

JSON Schema одного события (Pydantic):
{_SCHEMA_TEXT}

КРИТИЧЕСКИ ВАЖНО — полнота:
- Верни ВСЕ события без исключения. Не пропускай ни одной карточки. На странице обычно 10-30 событий.
- Просканируй HTML до конца. Не останавливайся на первых 5-10.
- Карточки повторяются в одинаковой структуре — найди паттерн и пройди по всем повторениям.
- Финально пересчитай свой массив и убедись: число объектов = числу карточек на странице.
- Если событий нет — верни {{"events": []}}.

Правила извлечения:
- Возвращай ТОЛЬКО валидный JSON-объект {{"events": [...]}}, без markdown-обёртки.
- Заполняй ТОЛЬКО то, что явно указано. Не выдумывай.
- Если опциональное поле не указано — null.
- price_min/price_max в рублях, целые числа. Если цена одна — повтори.
- price_text — готовая строка для UI: 'от 500 ₽', 'от 500 до 1000 ₽'.
{DATE_ALWAYS_INSTRUCTIONS}
- date — YYYY-MM-DD. time_start/end — HH:MM.
- image_url — РЕАЛЬНАЯ фотография (jpg/png/webp), НЕ svg-иконка/значок. Иначе null.
- organizer — название организатора/компании-устроителя (например 'QuizPlease'), если явно указано; иначе null.
- event_url: если перед текстом поста присутствует маркер «=== POST <url> ===», ты ОБЯЗАН использовать этот url как event_url для всех событий из этого поста. Если маркера нет, но в HTML карточки есть явный <a href="..."> на страницу события — используй его. Если ни того, ни другого нет — null.
  НИКОГДА не извлекай URL из тела текста поста: голые ссылки в тексте (clck.ru, vk.cc и другие сокращатели) — НЕ являются event_url. Не выдумывай, не угадывай event_url и не инкрементируй ID из URL других постов.
- Не извлекай события, которые уже завершились на момент публикации поста. Ориентируйся на дату «Сегодня» из user-сообщения. Если пост написан в прошедшем времени («прошёл», «прошел», «состоялся», «отгремел», «завершился», «прошедший») — ИГНОРИРУЙ событие, даже если оно было сегодня.
- tags — выбери из ЗАКРЫТОГО набора (можно несколько/ноль): "для компании", "для пары", "для детей", "интеллектуальное", "активное", "творческое", "вечером", "днём", "в помещении", "на улице", "бесплатно". Свои теги не придумывай.

Про год даты:
- Если на странице дата без года — бери год из ориентира «Сегодня» в user-сообщении.
- Если дата в прошлом — следующий год.
- НЕ подставляй год из своих знаний."""


class GroqExtractor(LLMExtractor):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b") -> None:
        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def extract(self, html: str, source_url: str) -> ParsedEvent:
        cleaned = _clean_html(html)
        today = _today_ru()
        user_msg = (
            f"Источник: {source_url}\n"
            f"Сегодня: {today}\n\n"
            f"HTML страницы события:\n\n{cleaned}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT_SINGLE},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=2000,
            )
        except Exception as exc:  # noqa: BLE001
            if is_rate_limit(exc):
                raise RateLimitError(f"Groq rate-limit для {source_url}: {exc}") from exc
            raise ExtractorError(f"Groq API error для {source_url}: {exc}") from exc

        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise ExtractorError(f"Groq вернул пустой ответ для {source_url}")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExtractorError(
                f"Groq вернул не-JSON для {source_url}: {text[:200]!r}"
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
        # На batch допускаем чуть больше — листинг содержит всю афишу.
        # 40k символов markdown ≈ 10-12k токенов. Free-tier gpt-oss = 8K TPM, поэтому пачка из
        # 5 постов в него не влезает (413) — обрабатывается разбиением ниже (см. except).
        cleaned = _clean_html(html, max_chars=40_000)
        today = _today_ru()
        log.info(
            "batch.input_size",
            source_url=source_url,
            raw_chars=len(html),
            cleaned_chars=len(cleaned),
        )
        user_msg = (
            f"Источник: {source_url}\n"
            f"Сегодня: {today}\n\n"
            f"HTML страницы расписания/афиши:\n\n{cleaned}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT_BATCH},
                    {"role": "user", "content": user_msg},
                ],
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=8000,
            )
        except Exception as exc:  # noqa: BLE001
            if is_rate_limit(exc):
                raise RateLimitError(f"Groq rate-limit для {source_url}: {exc}") from exc
            if is_request_too_large(exc):
                # 413: вход превысил TPM-лимит модели. Делим батч постов пополам по границам
                # маркеров «=== POST <url> ===» и переизвлекаем каждую половину рекурсивно.
                halves = _split_posts(html)
                if halves is None:
                    # < 2 постов — делить нечего (один пост либо листинг без маркеров).
                    # fallback to error; для огромного единого листинга — рассмотреть truncation
                    # max_chars (8K TPM ≈ 32k символов), пока крупные листинги идут через JSON-LD.
                    raise ExtractorError(
                        f"Groq 413 (слишком большой вход), делить нечего для {source_url}: {exc}"
                    ) from exc
                left, right = halves
                log.info(
                    "groq.batch_split",
                    source_url=source_url,
                    posts=html.count(_POST_MARKER),
                    parts=2,
                )
                return await self.extract_many(left, source_url) + await self.extract_many(
                    right, source_url
                )
            raise ExtractorError(f"Groq API error для {source_url}: {exc}") from exc

        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise ExtractorError(f"Groq вернул пустой ответ для {source_url}")

        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            log.debug("extract.bad_response", provider="groq", raw=str(text)[:1000])
            raise ExtractorError(
                f"Groq вернул не-JSON для {source_url}: {text[:200]!r}"
            ) from exc

        # Ожидаем {"events": [...]}. Допускаем альтернативы на случай вольной интерпретации.
        items = (
            data.get("events")
            if isinstance(data, dict)
            else data if isinstance(data, list) else None
        )
        if items is None:
            raise ExtractorError(
                f"Groq не вернул events-массив для {source_url}: keys={list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
            )

        results: list[ParsedEvent] = []
        for idx, item in enumerate(items):
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


def _split_posts(text: str) -> tuple[str, str] | None:
    """Делит батч постов пополам по границам маркеров «=== POST ».

    Возвращает (первая_половина, вторая_половина) либо None, если делить нечего
    (< 2 маркеров — один пост или листинг без маркеров). Маркеры задают границы постов,
    поэтому ни один пост не рвётся внутри. Инвариант: posts(h1)+posts(h2) == posts(text).
    """
    positions = [m.start() for m in re.finditer(re.escape(_POST_MARKER), text)]
    if len(positions) < 2:
        return None
    mid = positions[len(positions) // 2]  # средний маркер — точка разреза
    return text[:mid].rstrip(), text[mid:]


def _clean_html(html: str, max_chars: int = 20_000) -> str:
    """Жмём HTML до Markdown — Groq free-tier TPM тесный (8K у gpt-oss).

    1. selectolax выбрасывает script/style/svg/header/footer/nav/aside.
    2. markdownify конвертит остаток в Markdown (без атрибутов, без вложений).
    3. На выходе обрезаем по символам как страховку.
    """
    tree = HTMLParser(html)
    for tag in [
        "script", "style", "noscript", "svg", "iframe", "head",
        "header", "footer", "nav", "aside",
    ]:
        for node in tree.css(tag):
            node.decompose()
    body = tree.css_first("body") or tree.root
    md = markdownify(body.html or "", heading_style="ATX", strip=["img"])
    # Сжимаем пустые строки и лишние пробелы.
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    if len(md) > max_chars:
        md = md[:max_chars] + "\n\n<!-- truncated -->"
    return md
