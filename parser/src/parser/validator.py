"""Перевод ParsedEvent → EventRow (готов к записи в БД).

Здесь генерируется детерминированный id и slug.
"""

from __future__ import annotations

import re
import unicodedata

from .models import EventRow, ParsedEvent


def to_event_row(parsed: ParsedEvent, city: str, source_url: str, source: str) -> EventRow:
    slug = _make_slug(parsed.title, parsed.date)
    return EventRow(
        **parsed.model_dump(),
        id=f"{city}-{slug}",
        city=city,
        slug=slug,
        source_url=source_url,
        source=source,
        parsed_at=EventRow.make_parsed_at_now(),
    )


# Простой словарь транслита (без внешних зависимостей).
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _make_slug(title: str, date: str) -> str:
    """Формирует URL-безопасный slug из заголовка + даты."""
    # транслит
    s = "".join(_TRANSLIT.get(ch.lower(), ch) for ch in title.lower())
    # нормализация юникода (на случай оставшихся диакритик)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    # только a-z 0-9 и дефис
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    # ограничение длины + хвост датой
    s = s[:80]
    suffix = "" if date == "always" else f"-{date}"
    return f"{s}{suffix}"
