"""Fuzzy-дедуп (слой 2): «Квиз в баре» и «Квиз-вечер в баре» — одно событие.

Слой 1 (merge.merge_rows) схлопывает точные совпадения по id (= city+slug, а slug
детерминирован из title+date). Здесь ловим то, что отличается формулировкой названия.

Чистые функции: ни БД, ни сети, ни LLM. Метрики — stdlib (difflib), без внешних
зависимостей: сравнение идёт по коротким строкам и внутри одной даты, скорости хватает.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import EventRow
from .validator import _normalize


# Служебные слова: их совпадение ничего не говорит о том, одно ли это событие.
_STOPWORDS = frozenset({
    "в", "на", "и", "с", "по", "для", "от", "до", "из", "у", "о", "об",
    "за", "под", "над", "при", "а", "но", "или",
})

# Гласные + ь/й: типичное окончание русской словоформы («парка»/«парку» → «парк»).
# Согласную на конце не трогаем, иначе «класс» превратится в «клас» и разойдётся с «классы».
_ENDINGS = frozenset("аеиоуыэюяьй")

# Вложенность засчитывается, только если короткий заголовок достаточно содержателен:
# иначе «Йога» ⊂ «Йога на набережной» даст 1.0 на пустом месте.
_MIN_CONTAINMENT_TOKENS = 2
_MIN_CONTAINMENT_CHARS = 12

# Кавычечный сегмент: внутренние кавычки в класс не входят, поэтому вложенные
# «Яблочный Спас в «Хохловке»» дают один сегмент, а не два.
_QUOTED = re.compile(r"«[^«»]*»|\"[^\"]*\"|“[^”]*”")
# Между соседними сегментами перечня стоит только разделитель списка: «A», «B» / «A» и «B».
_LIST_SEPARATOR = re.compile(r"[\s,;]*(?:и)?[\s,;]*")


@dataclass(frozen=True)
class PairScore:
    """Оценка пары: итог + разбивка по сигналам (пишется в dedup_candidates для калибровки)."""

    score: float
    title_score: float
    venue_score: float
    reason: str
    """'ok' | 'time_mismatch' | 'same_distinct_source' (жёсткие guard'ы)
    | 'no_supporting_signals' (штраф 0.9)."""
    score_without_containment: float = 0.0
    """Тот же score, но без метрики вложенности — по нему кластеризация узнаёт рёбра,
    которые держатся только на «короткий заголовок ⊂ длинный»."""


def stem(word: str) -> str:
    """Лёгкий стеммер: отбрасывает конечную гласную у длинных слов, режет до 6 символов.

    Задача — свести словоформы одного слова («парка»/«парку» → «парк»), не склеив разные
    («программа» и «прогулка» остаются различны). Полноценная морфология не нужна и
    потянула бы зависимость (pymorphy) ради пары процентов точности.
    """
    if len(word) > 4 and word[-1] in _ENDINGS:
        word = word[:-1]
    return word[:6]


def tokens(text: str) -> set[str]:
    """Текст → множество значимых основ (без стоп-слов и слов короче 3 символов)."""
    return {
        stem(w)
        for w in _normalize(text).split()
        if len(w) > 2 and w not in _STOPWORDS
    }


def _char_ratio(a: str, b: str) -> float:
    """Посимвольное сходство. Второй вариант — без пробелов: «аудио спектакль» и
    «аудиоспектакль» отличаются ровно пробелом, и токенные метрики их не видят."""
    return max(
        SequenceMatcher(None, a, b).ratio(),
        SequenceMatcher(None, a.replace(" ", ""), b.replace(" ", "")).ratio(),
    )


def _containment(a: set[str], b: set[str], shorter: str) -> float:
    """|A∩B| / min(|A|,|B|) — ловит «Акция X» ⊂ «АКЦИЯ X: ПОДРОБНОСТИ».

    shorter — более короткий из двух нормализованных заголовков. Если он беден
    (меньше 2 основ или короче 12 символов), метрика выбывает из max(): вложенность
    короткого названия в длинное сама по себе ничего не доказывает.
    """
    smaller = min(len(a), len(b))
    if smaller < _MIN_CONTAINMENT_TOKENS or len(shorter) < _MIN_CONTAINMENT_CHARS:
        return 0.0
    return len(a & b) / smaller


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def is_enumeration(title: str) -> bool:
    """«Мастер-классы: «Единорог», «Планета», «Ёжик»» — перечень разных событий.

    Признак — два кавычечных сегмента подряд, между которыми только запятая или «и».
    Осмысленный текст между кавычками перечня не делает: «АРТ-парк»: Мастер-класс
    «Цветы из бумаги» — это цикл и одно его занятие, обычный дубль.
    """
    spans = [m.span() for m in _QUOTED.finditer(title)]
    return any(
        _LIST_SEPARATOR.fullmatch(title[end:start])
        for (_, end), (start, _) in zip(spans, spans[1:])
    )


def text_score(a: str, b: str, *, use_containment: bool = True) -> float:
    """Сходство двух текстов: максимум из трёх метрик — каждая ловит свой тип дубля.

    use_containment=False убирает вложенность из максимума: так кластеризация узнаёт,
    держится ли пара только на ней.
    """
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    ta, tb = tokens(a), tokens(b)
    # Вложенность ищем по сырому длинному заголовку: _normalize срезает кавычки,
    # а перечень опознаётся именно по ним.
    shorter, longer = (na, b) if len(na) <= len(nb) else (nb, a)
    containment = (
        _containment(ta, tb, shorter)
        if use_containment and not is_enumeration(longer)
        else 0.0
    )
    return max(_char_ratio(na, nb), containment, _jaccard(ta, tb))


def _venue_factor(venue_score: float) -> float:
    """Множитель за площадку: помочь не может, навредить — может.

    Аддитивная форма (0.75*title + 0.25*venue) штрафовала бы за непохожие площадки даже
    при идентичном названии и времени; здесь похожая площадка просто не мешает.
    """
    if venue_score > 0.6:
        return 1.0
    if venue_score > 0.3:
        return 0.85
    return 0.5


def score_pair(
    a: EventRow, b: EventRow, *, distinct_sources: frozenset[str] = frozenset()
) -> PairScore:
    """Насколько вероятно, что a и b — одно событие. Одинаковость city+date подразумевается.

    distinct_sources — источники, у которых одна строка = одно событие (см. SourceConfig
    .distinct_events). Две строки такого источника не сливаются никогда.
    """
    # Источник сам гарантирует различность: у каждой игры QuizPlease свой id в API, и
    # «Квиз, плиз! PERM» с «Квиз, плиз! [новички] PERM» в одном зале в 19:30 — две игры.
    # Текстом это не отличить: «Фотография как искусство» и «…(12+)» — настоящий дубль.
    if a.source == b.source and a.source in distinct_sources:
        return PairScore(0.0, 0.0, 0.0, "same_distinct_source")

    # Жёсткий guard: разное время в один день на одной площадке — это разные сеансы
    # (планетарий, квизы в баре), а не разная формулировка одного анонса.
    if a.time_start and b.time_start and a.time_start != b.time_start:
        return PairScore(0.0, 0.0, 0.0, "time_mismatch")

    title = text_score(a.title, b.title)
    title_plain = text_score(a.title, b.title, use_containment=False)

    # Пустая площадка хотя бы у одного — нейтрально: у VK/Telegram-постов venue_name
    # часто не извлекается, и штраф за это отсекал бы настоящие дубли.
    has_venues = bool(a.venue_name.strip()) and bool(b.venue_name.strip())
    venue = text_score(a.venue_name, b.venue_name) if has_venues else 0.0
    factor = _venue_factor(venue) if has_venues else 1.0

    # Ни площадки, ни времени не подтвердили совпадение — сливать по одному названию рискованно.
    reason = "ok"
    if not has_venues and not (a.time_start and b.time_start):
        factor *= 0.9
        reason = "no_supporting_signals"

    return PairScore(
        round(title * factor, 3), round(title, 3), round(venue, 3), reason,
        round(title_plain * factor, 3),
    )


@dataclass(frozen=True)
class ScoredPair:
    """Посчитанная пара — для записи в dedup_candidates и для вывода dedup-backfill."""

    a: EventRow
    b: EventRow
    score: PairScore


# Скобочное уточнение — часть одного названия, а не отдельное событие.
_PARENTHESES = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")


def _drop_umbrella_edges(
    edges: list[tuple[EventRow, EventRow, bool]], merge_threshold: float
) -> list[tuple[EventRow, EventRow, bool]]:
    """Убирает рёбра-вложенности у зонтичных заголовков.

    «День Строгановых» вкладывается и в «…: книжная выставка», и в «…: показ фильма»,
    а те друг на друга не похожи — значит это программа дня, а не три формулировки одного
    анонса. Попарно такую вложенность от настоящего дубля («Культурная среда» ⊂ «Культурная
    среда: бесплатный вход…») не отличить: решает только вид всего кластера.

    Скобочные уточнения различием не считаем — «…(Воскресенье)» и «…(Спешилова 111/3)»
    остаются одним событием, и их общий короткий заголовок зонтичным не делают.
    """
    linked = {frozenset((a.id, b.id)) for a, b, _ in edges}
    children: dict[str, list[EventRow]] = {}
    for a, b, weak in edges:
        if weak:
            children.setdefault(a.id, []).append(b)
            children.setdefault(b.id, []).append(a)

    hubs = {
        row_id
        for row_id, kids in children.items()
        if any(
            frozenset((x.id, y.id)) not in linked
            and text_score(
                _PARENTHESES.sub(" ", x.title), _PARENTHESES.sub(" ", y.title)
            ) < merge_threshold
            for i, x in enumerate(kids)
            for y in kids[i + 1:]
        )
    }
    return [
        (a, b, weak)
        for a, b, weak in edges
        if not (weak and (a.id in hubs or b.id in hubs))
    ]


def cluster_events(
    rows: list[EventRow],
    *,
    merge_threshold: float,
    report_threshold: float,
    distinct_sources: frozenset[str] = frozenset(),
) -> tuple[list[list[EventRow]], list[ScoredPair]]:
    """Группирует строки в кластеры-дубли: ребро при score >= merge_threshold,
    кластер = компонента связности.

    Попарного слияния мало: «День рождения парка Горького» приходит четырьмя
    формулировками, и при A~B, B~C, A≁C нужен один кластер, а не два пересекающихся.

    Возвращает (кластеры, пары): кластеры включают одиночек; пары — всё, что набрало
    >= report_threshold (включая слитые — они нужны как аудит auto-merge).
    """
    blocks: dict[tuple[str, str], list[EventRow]] = {}
    for r in rows:
        if r.date == "always":  # площадки живут в venues, матчинг по названию им не нужен
            continue
        blocks.setdefault((r.city, r.date), []).append(r)

    parent: dict[str, str] = {r.id: r.id for block in blocks.values() for r in block}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # сжатие пути
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            # Корень — лексикографически меньший id: результат не зависит от порядка обхода.
            parent[max(rx, ry)] = min(rx, ry)

    pairs: list[ScoredPair] = []
    edges: list[tuple[EventRow, EventRow, bool]] = []
    for block in blocks.values():
        ordered = sorted(block, key=lambda r: r.id)  # детерминированный порядок сравнений
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                ps = score_pair(a, b, distinct_sources=distinct_sources)
                if ps.score >= report_threshold:
                    pairs.append(ScoredPair(a, b, ps))
                if ps.score >= merge_threshold:
                    # Слабое ребро — то, что без вложенности порога бы не набрало.
                    edges.append((a, b, ps.score_without_containment < merge_threshold))

    for a, b, _weak in _drop_umbrella_edges(edges, merge_threshold):
        union(a.id, b.id)

    grouped: dict[str, list[EventRow]] = {}
    for block in blocks.values():
        for r in block:
            grouped.setdefault(find(r.id), []).append(r)

    clusters = [sorted(members, key=lambda r: r.id) for members in grouped.values()]
    clusters.sort(key=lambda c: c[0].id)
    return clusters, pairs
