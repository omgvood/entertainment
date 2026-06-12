"""Таксономия тегов событий.

Закрытый список тегов + версия. При изменении набора поднимай TAGS_VERSION —
события с устаревшей версией можно перепарсить (вместе с raw_documents).
"""

from __future__ import annotations

TAGS_VERSION = 1

# Закрытый набор тегов v1. LLM выбирает из него; всё, что вне набора, отбрасывается.
ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        "для компании",
        "для пары",
        "для детей",
        "интеллектуальное",
        "активное",
        "творческое",
        "вечером",
        "днём",
        "в помещении",
        "на улице",
        "бесплатно",
    }
)

# Авто-теги для direct_api источников (2ГИС/Timepad), где LLM не вызывается.
# Маппинг по EventType. Только теги из ALLOWED_TAGS.
TYPE_DEFAULT_TAGS: dict[str, list[str]] = {
    "quiz": ["интеллектуальное", "для компании"],
    "standup": ["для компании", "вечером"],
    "bowling": ["активное", "для компании", "в помещении"],
    "billiards": ["для компании", "в помещении"],
    "karting": ["активное", "для компании"],
    "concert": ["вечером"],
    "theater": ["вечером", "в помещении"],
    "exhibition": ["творческое", "в помещении"],
    "festival": ["для компании"],
    "quest": ["для компании", "интеллектуальное"],
    "party": ["для компании", "вечером"],
    "cinema": ["в помещении"],
    "kids": ["для детей"],
    "art": ["творческое"],
    "science": ["интеллектуальное"],
    "sport": ["активное"],
}


def filter_tags(tags: list[str]) -> list[str]:
    """Оставляет только разрешённые теги, сохраняя порядок и убирая дубли."""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        if tag in ALLOWED_TAGS and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def default_tags_for_type(event_type: str) -> list[str]:
    """Авто-теги для direct_api события по его типу (пустой список, если тип не в карте)."""
    return list(TYPE_DEFAULT_TAGS.get(event_type, []))
