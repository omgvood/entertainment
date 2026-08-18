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

from .config import DEDUP_CANDIDATE_SCORE, DEDUP_MERGE_SCORE
from .fuzzy import ScoredPair, cluster_events
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
    """Близкие дубли: та же площадка + дата, но разные id (разные названия) — сырой сигнал

    для сравнения с fuzzy-метрикой. Не схлопываем (риск ложных слияний), только считаем.
    """
    by_key: dict[tuple[str, str], set[str]] = {}
    for r in [*incoming, *existing]:
        venue = _normalize(r.venue_name)
        if not venue:
            continue
        by_key.setdefault((venue, r.date), set()).add(r.id)
    return sum(len(ids) - 1 for ids in by_key.values() if len(ids) > 1)


@dataclass
class FuzzyResult:
    rows_to_upsert: list[EventRow] = field(default_factory=list)
    fuzzy_merged: int = 0
    """Сколько новых карточек НЕ создано (строк схлопнуто)."""
    fuzzy_merged_in_source: int = 0
    """Из них — дубли внутри одного источника (KPI unique_events_ratio их не считает)."""
    largest_cluster: int = 0
    """Размер наибольшего кластера: >3 — сигнал, что порог поехал и склеивает лишнее."""
    candidates: list[ScoredPair] = field(default_factory=list)


def _pick_winner(rows: list[EventRow], priorities: dict[str, int]) -> EventRow:
    """Победитель кластера: выше priority, при равенстве — лексикографически меньший id.

    Детерминированность важнее «лучшести»: иначе победитель, а с ним slug и URL,
    прыгал бы между прогонами при смене порядка источников.
    """
    return min(rows, key=lambda r: (-priorities.get(r.source, 0), r.id))


def resolve_cluster(
    cluster: list[EventRow],
    priorities: dict[str, int],
    *,
    prefer: list[EventRow] | None = None,
) -> tuple[EventRow, list[EventRow]]:
    """Кластер дублей → (обогащённый победитель, проигравшие).

    Публичная точка входа: ею пользуются и слой 2 в пайплайне, и разовая команда
    dedup-backfill — правило выбора победителя обязано быть одно на оба пути.

    prefer — подмножество, из которого победитель обязан быть выбран. В пайплайне это
    уже записанные строки: их id — живой URL, и менять его нельзя.
    """
    winner = _pick_winner(prefer or cluster, priorities)
    losers = [r for r in cluster if r.id != winner.id]
    return _enrich(winner, losers), losers


def fuzzy_merge(
    rows: list[EventRow],
    existing: list[EventRow],
    priorities: dict[str, int],
) -> FuzzyResult:
    """Слой 2: не даёт создать новую карточку событию, которое уже есть под другим названием.

    rows     — то, что собирались писать (результат merge_rows).
    existing — события города на затронутые даты из БД (пул кандидатов; в dry-run пуст).

    Write-time guard: ежедневный прогон умеет только не создавать новый id. Кластер из
    одних уже записанных строк не трогаем — выбросив такую строку из upsert, мы её не
    удалим, а лишь перестанем обновлять. Такие пары уходят в candidates → dedup-backfill.
    """
    result = FuzzyResult()
    by_id = {r.id: r for r in rows}
    persisted_ids = {r.id for r in existing}
    pool = [r for r in existing if r.id not in by_id]

    clusters, pairs = cluster_events(
        [*rows, *pool],
        merge_threshold=DEDUP_MERGE_SCORE,
        report_threshold=DEDUP_CANDIDATE_SCORE,
    )
    result.candidates = pairs

    kept: list[EventRow] = []
    for cluster in clusters:
        result.largest_cluster = max(result.largest_cluster, len(cluster))
        if len(cluster) == 1:
            row = cluster[0]
            if row.id in by_id:
                kept.append(row)
            continue

        persisted = [r for r in cluster if r.id in persisted_ids]
        fresh = [r for r in cluster if r.id not in persisted_ids]

        if not fresh:
            # Все карточки уже в БД — оставляем как есть, разбирать их будет dedup-backfill.
            kept.extend(r for r in cluster if r.id in by_id)
            continue

        winner, losers = resolve_cluster(cluster, priorities, prefer=persisted or None)
        kept.append(winner)
        # Уцелевшие записанные карточки, не ставшие победителем, продолжают жить своей жизнью.
        kept.extend(r for r in persisted if r.id != winner.id and r.id in by_id)

        for loser in losers:
            if loser.id in persisted_ids:
                continue  # записанную карточку слой 2 не убирает
            result.fuzzy_merged += 1
            if loser.source == winner.source:
                result.fuzzy_merged_in_source += 1

    result.rows_to_upsert = kept
    return result
