"""Перевод ParsedEvent → EventRow (готов к записи в БД).

Здесь генерируется детерминированный id и slug.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from .models import EventRow, ParsedEvent, Venue
from .taxonomy import default_tags_for_type


def to_event_row(parsed: ParsedEvent, city: str, source_url: str, source: str) -> EventRow:
    slug = _make_slug(parsed.title, parsed.date)
    data = parsed.model_dump()
    # direct_api источники (2ГИС/Timepad) не проставляют теги — подставляем авто-теги по типу.
    if not data["tags"]:
        data["tags"] = default_tags_for_type(parsed.type)
    return EventRow(
        **data,
        id=f"{city}-{slug}",
        city=city,
        slug=slug,
        source_url=source_url,
        source=source,
        parsed_at=EventRow.make_parsed_at_now(),
        fingerprint=_fingerprint(parsed.title, parsed.date, parsed.venue_name),
    )


def to_venue(parsed: ParsedEvent, city: str, source: str) -> Venue:
    """ParsedEvent заведения (date='always') → строка таблицы venues.

    Источники venues (2ГИС API и Playwright) отдают тот же ParsedEvent, что и события,
    с date='always'. Здесь маппим его в плоскую venue-строку с детерминированным id.
    """
    slug = _make_slug(parsed.venue_name, "always")
    return Venue(
        id=f"{city}-{slug}",
        city=city,
        name=parsed.venue_name,
        type=parsed.type,
        address=parsed.address or None,
        district=parsed.district,
        image_url=parsed.image_url,
        source=source,
    )


def _normalize(s: str) -> str:
    """Нормализация для fingerprint: нижний регистр, ё→е, без пунктуации, схлопнутые пробелы."""
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _fingerprint(title: str, date: str, venue_name: str) -> str:
    """Хеш для кросс-источниковой дедупликации. Без UNIQUE — сначала собираем статистику."""
    key = f"{_normalize(title)}|{date}|{_normalize(venue_name)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


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
