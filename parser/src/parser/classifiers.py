"""Общий префильтр «пост похож на анонс события» — перед дорогим LLM-вызовом.

Один классификатор для всех текстовых источников (VK, Telegram, в будущем RSS/прочее).
Порог зависит от SourceType: у агрегаторов (много рекламы/мемов) фильтр строже, у
организаторов/соцсетей — мягче. Отсекает шум до LLM, экономя токены.

Сейчас это простой regex+keyword классификатор. Если позже понадобится ML/LLM-классификатор
(например, маленькая модель перед основным extract_many), сигнатуру можно сохранить —
pipeline вызывает только is_event_candidate(text, source_type).
"""

from __future__ import annotations

import re

from .config import SourceType


# Событийные маркеры: текст-кандидат, если есть дата/время ИЛИ маркеры ИЛИ ссылка на билеты.
_EVENT_MARKERS = (
    "состоится", "билет", "регистраци", "вход", "начало", "когда:", "адрес:",
    "стоимость", "афиш", "приглашаем", "пройдёт", "пройдет",
)
_TICKET_HOSTS = ("timepad.ru", "qtickets", "yandex.ru/afisha", "kassir", "ticketscloud")
_DATE_RE = re.compile(
    r"\b\d{1,2}[\s.]*(январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр)"
    r"|\b\d{1,2}[./]\d{1,2}\b"  # 15.06 / 15/06
    r"|\b\d{1,2}:\d{2}\b",      # 19:00
    re.IGNORECASE,
)


def is_event_candidate(text: str, source_type: SourceType = SourceType.SOCIAL) -> bool:
    """True, если текст похож на анонс события.

    AGGREGATOR (много шума) — строже: нужна дата И (маркеры или ссылка на билеты).
    Остальные (ORGANIZER/SOCIAL/...) — мягче: достаточно одного сигнала.
    """
    if not text:
        return False
    low = text.lower()
    has_date = bool(_DATE_RE.search(low))
    has_marker = any(m in low for m in _EVENT_MARKERS)
    has_ticket = any(h in low for h in _TICKET_HOSTS)

    if source_type == SourceType.AGGREGATOR:
        return has_date and (has_marker or has_ticket)
    return has_date or has_marker or has_ticket
