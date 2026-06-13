"""Кросс-источниковая дедупликация (Шаг 6).

Одно реальное событие из Timepad, VK и сайта организатора схлопывается в одну карточку.
Единица дедупа — `id` (= city + slug, а slug детерминирован из title+date): БД и так держит
одну строку на slug, поэтому строки с одинаковым id ОБЯЗАНЫ слиться. Победитель — источник
с наибольшим priority из seeds.yaml; его пустые поля дозаполняются из проигравших.

Чистые функции — без обращения к БД (тестируются изолированно). Слияние на стороне Python,
а не UNIQUE-констрейнтом: констрейнт умеет только отклонять, а нам нужно поле-в-поле объединять
с учётом приоритета. Удалять ничего не нужно — все слитые строки делят id, и upsert по slug
перезаписывает карточку на месте.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from .models import EventRow
from .taxonomy import filter_tags
from .validator import _normalize


log = structlog.get_logger()

# Поля, которые победитель добирает из проигравших, если у него они пусты.
_FILLABLE = ("time_start", "time_end", "image_url", "description", "organizer", "district")


@dataclass
class MergeResult:
    rows_to_upsert: list[EventRow] = field(default_factory=list)
    merged: int = 0
    merged_by_source: dict[str, int] = field(default_factory=dict)
    near_misses: int = 0


def _priority(row: EventRow, priorities: dict[str, int]) -> int:
    return priorities.get(row.source, 0)


def _enrich(winner: EventRow, losers: list[EventRow]) -> EventRow:
    """Возвращает копию winner, дозаполненную пустыми полями из losers (или winner как есть)."""
    updates: dict[str, object] = {}
    for f in _FILLABLE:
        if getattr(winner, f) is None:
            for loser in losers:
                val = getattr(loser, f)
                if val is not None:
                    updates[f] = val
                    break
    # Цена: если у победителя её нет (0/0), берём первую реальную из проигравших.
    if winner.price_min == 0 and winner.price_max == 0:
        for loser in losers:
            if loser.price_min or loser.price_max:
                updates["price_min"] = loser.price_min
                updates["price_max"] = loser.price_max
                updates["price_text"] = loser.price_text
                if loser.price_note:
                    updates["price_note"] = loser.price_note
                break
    # Теги: объединение (с фильтрацией по таксономии).
    union: list[str] = list(winner.tags)
    for loser in losers:
        for t in loser.tags:
            if t not in union:
                union.append(t)
    merged_tags = filter_tags(union)
    if merged_tags != list(winner.tags):
        updates["tags"] = merged_tags

    return winner.model_copy(update=updates) if updates else winner


def merge_rows(
    incoming: list[EventRow],
    existing: list[EventRow],
    priorities: dict[str, int],
) -> MergeResult:
    """Схлопывает строки с одинаковым id (incoming ∪ existing) в одну карточку-победителя.

    incoming  — строки, готовые к записи в этом прогоне.
    existing  — строки из БД с теми же id (тот же город).
    priorities — {source_name: priority}; неизвестный источник → 0.

    rows_to_upsert — по одной строке на id: победитель (возможно обогащённый из проигравших).
    """
    result = MergeResult()

    # incoming идут первыми → при равном priority побеждает свежая строка прогона, не БД.
    groups: dict[str, list[EventRow]] = {}
    for r in [*incoming, *existing]:
        groups.setdefault(r.id, []).append(r)

    for rows in groups.values():
        winner = rows[0]
        for r in rows[1:]:
            if _priority(r, priorities) > _priority(winner, priorities):
                winner = r

        losers = [r for r in rows if r is not winner]
        result.rows_to_upsert.append(_enrich(winner, losers))

        for loser in losers:
            if loser.source != winner.source:
                result.merged += 1
                key = f"{loser.source}→{winner.source}"
                result.merged_by_source[key] = result.merged_by_source.get(key, 0) + 1

    result.near_misses = _count_near_misses(incoming, existing)
    return result


def _count_near_misses(incoming: list[EventRow], existing: list[EventRow]) -> int:
    """Близкие дубли: та же площадка + дата, но разные id (разные названия) — кандидаты на

    будущий fuzzy-матчинг. Не схлопываем (риск ложных слияний), только считаем.
    """
    by_key: dict[tuple[str, str], set[str]] = {}
    for r in [*incoming, *existing]:
        venue = _normalize(r.venue_name)
        if not venue:
            continue
        by_key.setdefault((venue, r.date), set()).add(r.id)
    return sum(len(ids) - 1 for ids in by_key.values() if len(ids) > 1)
