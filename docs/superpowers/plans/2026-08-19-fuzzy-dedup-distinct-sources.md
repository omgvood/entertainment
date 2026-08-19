# Fuzzy-дедуп: защита от самодублей источника — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Закрыть последнее семейство ложных слияний слоя 2 (две разные игры QuizPlease схлопываются в одну карточку) и снять шумный алерт, после чего безопасно применить `dedup-backfill` к Перми.

**Architecture:** В `seeds.yaml` вводится опциональный флаг источника `distinct_events` — «одна строка этого источника всегда одно событие». Имена таких источников собираются в `frozenset` в двух точках входа (`pipeline.run_city`, `cli._cmd_dedup_backfill`) — ровно тем же способом, каким там уже собирается `priorities`, — и пробрасываются до `fuzzy.score_pair`, где становятся жёстким guard'ом рядом с существующим `time_mismatch`.

**Tech Stack:** Python 3.10+, stdlib (`re`, `difflib`), pytest. Новых зависимостей нет.

**Spec:** `docs/superpowers/specs/2026-08-18-fuzzy-dedup-design.md` (раздел «Ложные срабатывания containment» описывает два уже закрытых семейства; этот план добавляет третье)

**Ветка:** `fix/fuzzy-containment-enumeration` — продолжаем в ней, поверх коммита `c37f98e`.

**Постоянное место плана:** при исполнении скопировать в `docs/superpowers/plans/2026-08-19-fuzzy-dedup-distinct-sources.md` и закоммитить вместе с Task 1.

## Global Constraints

- `parser/src/parser/fuzzy.py` остаётся чистым: ни БД, ни сети, ни конфигов — только stdlib. Конфиг приходит параметром.
- Все новые параметры — с дефолтом, чтобы существующие вызовы и 233 теста не переписывались.
- Комментарии и докстринги — по-русски, в стиле файла: объясняем «почему», а не «что».
- Пороги живут в `parser/src/parser/config.py`: `DEDUP_MERGE_SCORE = 0.95`, `DEDUP_CANDIDATE_SCORE = 0.75`. Не менять.
- Команда тестов из каталога `parser/`: `python -m pytest -q`. На Windows перед выводом с кириллицей — `PYTHONIOENCODING=utf-8`.
- Базовая линия: **233 теста зелёные** на `c37f98e`.

---

## Context

Слой 2 fuzzy-дедупа (`fuzzy.py` + `merge.fuzzy_merge`) не даёт создать вторую карточку событию, которое уже есть под другой формулировкой названия. Коммит `c37f98e` закрыл два семейства ложных слияний, найденных на живых данных Перми: перечни (`Мастер-классы: «Единорог», «Планета», «Ёжик»` поглощал три отдельных МК) и зонтичные программы (`День Строгановых` поглощал свои подсобытия — кластер из 9). На 691 карточке Перми это сократило схлопывания с 69 до 48.

Полный предпросмотр бэкфилла после этой правки вскрыл **третье семейство**, которое ни один из двух guard'ов не ловит:

```
2026-08-18 19:30  Ресторан Кама  Квиз, плиз! PERM            → /game/019fdb0b-078d-…
2026-08-18 19:30  Ресторан Кама  Квиз, плиз! [новички] PERM  → /game/019fdb0c-76a9-…
```

Это две **разные игры** QuizPlease — разные `game_id` в API, разные страницы билетов; обычная и «новичковая» идут параллельно в одном зале. `containment` даёт 1.0 (`{квиз, плиз, perm}` ⊂ `{квиз, плиз, новичк, perm}`), время и площадка совпадают, ни `time_mismatch`, ни `is_enumeration`, ни `_drop_umbrella_edges` не срабатывают. Повторяется на 2026-08-18 и 2026-08-25.

**Дефект пре-существующий**, не от правки `c37f98e`, и он активный: сейчас обе карточки живы только потому, что попали в БД до включения слоя 2 (кластер из одних уже записанных строк слой 2 не трогает — см. спеку, «Семантика write-time guard»). На новой неделе, когда обе игры придут свежими, `fuzzy_merge` создаст одну и молча выбросит вторую. `dedup-backfill --apply` удалит одну прямо сейчас.

**Текстовой эвристикой это не лечится.** Скобочный маркер не признак разного события: в тех же данных `«Фотография как искусство»` vs `«Фотография как искусство» (12+)` — настоящий дубль. Различает их только природа источника: QuizPlease отдаёт по строке на игру, и две его строки не могут быть одним событием.

**Почему нельзя переиспользовать `full_snapshot`.** Соблазнительно взять существующий флаг (`quizplease` им уже помечен), но он отвечает на другой вопрос — «источник отдаёт полный срез, можно синхронизировать отмены». Проверка показала, что `permm` тоже `full_snapshot: true`, и при этом даёт **настоящие** самодубли: `permm.py` читает два эндпоинта (`/json/events/…` и `/json/exhibitions/active`), и один экспонат приходит дважды —

```
2026-10-23  Выставка «Стечение обстоятельств»  → permm.ru/events/vystavka-stecenie-obstoyatelstv
2026-10-23  Стечение обстоятельств             → permm.ru/exhibition/stechenie-obstojatelstv
```

плюс ещё две такие пары на 2026-12-31. Переиспользование `full_snapshot` сломало бы три настоящих слияния. Нужен отдельный, опт-ин флаг.

**Итог после этого плана:** бэкфилл Перми при пороге 0.95 даст 37 кластеров и 46 удалений вместо нынешних 39/48 — уйдут ровно две квиз-пары.

## File Structure

| Файл | Ответственность | Что меняется |
|---|---|---|
| `parser/src/parser/fuzzy.py` | Чистый скорер + кластеризация | `score_pair` и `cluster_events` получают `distinct_sources`; новый жёсткий guard |
| `parser/src/parser/merge.py` | Слой 2 поверх кластеров | `fuzzy_merge` пробрасывает `distinct_sources` в `cluster_events` |
| `parser/src/parser/config.py` | `SourceConfig` + разбор seeds | Новое поле `distinct_events` |
| `parser/config/seeds.yaml` | Источники по городам | `distinct_events: true` у обоих `quizplease` (perm + sochi) |
| `parser/src/parser/pipeline.py` | Оркестратор ежедневного прогона | Сбор `distinct_sources`; порог алерта по размеру кластера |
| `parser/src/parser/cli.py` | Команда `dedup-backfill` | Сбор `distinct_sources` |
| `parser/tests/test_fuzzy.py` | Тесты скорера | +4 теста (Task 1) |
| `parser/tests/test_merge.py` | Тесты слоя 2 | +1 тест (Task 2) |
| `parser/tests/test_config.py` | **Создать.** Контракт seeds.yaml | +2 теста (Task 2) |
| `README.md`, `docs/superpowers/specs/2026-08-18-fuzzy-dedup-design.md` | Документация | Описание третьего семейства и флага |

---

### Task 1: Жёсткий guard в скорере

Механизм целиком внутри чистого модуля: `fuzzy.py` узнаёт имена «атомарных» источников параметром и никогда не сливает две строки одного такого источника.

**Files:**
- Modify: `parser/src/parser/fuzzy.py` (`PairScore.reason` строка 49, `score_pair` строка 152, `cluster_events` строка 232)
- Modify: `parser/src/parser/merge.py` (`fuzzy_merge` строка 171, вызов `cluster_events` строка 190)
- Test: `parser/tests/test_fuzzy.py`

**Interfaces:**
- Produces: `fuzzy.score_pair(a, b, *, distinct_sources: frozenset[str] = frozenset()) -> PairScore`
- Produces: `fuzzy.cluster_events(rows, *, merge_threshold, report_threshold, distinct_sources: frozenset[str] = frozenset())`
- Produces: `merge.fuzzy_merge(rows, existing, priorities, distinct_sources: frozenset[str] = frozenset()) -> FuzzyResult`
- Produces: новое значение `PairScore.reason` — `"same_distinct_source"`

- [ ] **Step 1: Написать падающие тесты**

Дописать в конец `parser/tests/test_fuzzy.py`. Хелпер `_row(title, venue, time_start=None, source="vk-posts", date="2026-08-16")` уже есть в начале файла, `_clusters_of(rows, merge_threshold=MERGE)` — ниже по файлу.

```python
def test_score_pair_same_distinct_source_never_merges():
    """Две игры QuizPlease в одном зале в 19:30 — разные игры, а не переформулировка."""
    a = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="quizplease")
    b = _row("Квиз, плиз! [новички] PERM", "Ресторан Кама", "19:30", source="quizplease")
    assert score_pair(a, b, distinct_sources=frozenset({"quizplease"})) == PairScore(
        0.0, 0.0, 0.0, "same_distinct_source"
    )


def test_score_pair_distinct_guard_applies_only_within_one_source():
    """Флаг запрещает слияние внутри источника: кросс-источниковый дубль по-прежнему ловится."""
    a = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="quizplease")
    b = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="vk-posts")
    assert score_pair(a, b, distinct_sources=frozenset({"quizplease"})).score >= MERGE


def test_cluster_distinct_source_rows_stay_apart():
    a = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="quizplease")
    b = _row("Квиз, плиз! [новички] PERM", "Ресторан Кама", "19:30", source="quizplease")
    clusters, _pairs = cluster_events(
        [a, b], merge_threshold=MERGE, report_threshold=CANDIDATE,
        distinct_sources=frozenset({"quizplease"}),
    )
    assert [len(c) for c in clusters] == [1, 1]


def test_cluster_same_source_without_flag_still_merges():
    """ПЕРММ отдаёт один экспонат двумя эндпоинтами — его самодубли настоящие."""
    a = _row("Выставка «Стечение обстоятельств»", "Музей современного искусства «ПЕРММ»",
             source="permm")
    b = _row("Стечение обстоятельств", "Музей современного искусства «ПЕРММ»", source="permm")
    assert len(_clusters_of([a, b])[0]) == 2
```

- [ ] **Step 2: Убедиться, что тесты падают**

Из каталога `parser/`:

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_fuzzy.py -q -k "distinct or same_source_without_flag"
```

Ожидается: три первых теста падают с `TypeError: score_pair() got an unexpected keyword argument 'distinct_sources'` / `cluster_events() got an unexpected keyword argument`. Четвёртый (`without_flag`) проходит сразу — он фиксирует поведение, которое нельзя сломать.

- [ ] **Step 3: Добавить guard в `score_pair`**

В `parser/src/parser/fuzzy.py` заменить сигнатуру и начало `score_pair`:

```python
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
```

Обновить докстринг поля `reason` в `PairScore`:

```python
    reason: str
    """'ok' | 'time_mismatch' | 'same_distinct_source' (жёсткие guard'ы)
    | 'no_supporting_signals' (штраф 0.9)."""
```

- [ ] **Step 4: Пробросить параметр через `cluster_events`**

Там же, в `fuzzy.py`:

```python
def cluster_events(
    rows: list[EventRow],
    *,
    merge_threshold: float,
    report_threshold: float,
    distinct_sources: frozenset[str] = frozenset(),
) -> tuple[list[list[EventRow]], list[ScoredPair]]:
```

и в теле цикла сравнений заменить вызов:

```python
                ps = score_pair(a, b, distinct_sources=distinct_sources)
```

- [ ] **Step 5: Пробросить параметр через `fuzzy_merge`**

В `parser/src/parser/merge.py`:

```python
def fuzzy_merge(
    rows: list[EventRow],
    existing: list[EventRow],
    priorities: dict[str, int],
    distinct_sources: frozenset[str] = frozenset(),
) -> FuzzyResult:
```

и в вызове `cluster_events` внутри неё добавить аргумент:

```python
    clusters, pairs = cluster_events(
        [*rows, *pool],
        merge_threshold=DEDUP_MERGE_SCORE,
        report_threshold=DEDUP_CANDIDATE_SCORE,
        distinct_sources=distinct_sources,
    )
```

- [ ] **Step 6: Убедиться, что тесты проходят**

```bash
PYTHONIOENCODING=utf-8 python -m pytest -q
```

Ожидается: `237 passed` (233 базовых + 4 новых), вывод чистый, без warnings.

- [ ] **Step 7: Коммит**

```bash
git add parser/src/parser/fuzzy.py parser/src/parser/merge.py parser/tests/test_fuzzy.py
git commit -m "feat(fuzzy): источники с атомарными событиями не сливаются сами с собой"
```

---

### Task 2: Проброс флага из seeds.yaml

Механизм из Task 1 включается на реальных источниках. Сбор множества повторяет уже существующий рядом сбор `priorities` — те же две точки входа.

**Files:**
- Modify: `parser/src/parser/config.py` (`SourceConfig.full_snapshot` строка 201, `load_seeds` строка 283)
- Modify: `parser/config/seeds.yaml` (строки 31 и 123 — блоки `quizplease` городов sochi и perm)
- Modify: `parser/src/parser/pipeline.py` (сбор `priorities` строка 224, вызов `fuzzy_merge` строка 330)
- Modify: `parser/src/parser/cli.py` (сбор `priorities` строка 400, вызов `cluster_events` строка 413)
- Test: `parser/tests/test_merge.py`, `parser/tests/test_config.py` (создать)

**Interfaces:**
- Consumes: `merge.fuzzy_merge(..., distinct_sources)` и `fuzzy.cluster_events(..., distinct_sources)` из Task 1
- Produces: `config.SourceConfig.distinct_events: bool = False`

- [ ] **Step 1: Написать падающие тесты**

Дописать в конец `parser/tests/test_merge.py` (хелпер `_row(title, date, venue, source, **over)` и `_PRI` уже есть в начале файла; `fuzzy_merge` уже импортирован):

```python
def test_fuzzy_distinct_source_rows_are_both_written():
    """Две игры QuizPlease в одном зале в одно время должны попасть в БД обе."""
    a = _row("Квиз, плиз! PERM", "2026-08-18", "Ресторан Кама", "quizplease",
             time_start="19:30")
    b = _row("Квиз, плиз! [новички] PERM", "2026-08-18", "Ресторан Кама", "quizplease",
             time_start="19:30")
    res = fuzzy_merge([a, b], [], _PRI, frozenset({"quizplease"}))
    assert len(res.rows_to_upsert) == 2
    assert res.fuzzy_merged == 0
```

Создать `parser/tests/test_config.py`:

```python
"""Контракт seeds.yaml: флаги, от которых зависит поведение дедупа."""

from parser.config import load_seeds


def _source(city: str, name: str):
    return next(s for s in load_seeds()[city].sources if s.name == name)


def test_quizplease_marked_as_distinct_events():
    """Одна строка API QuizPlease = одна игра: слой 2 не должен склеивать их между собой."""
    assert _source("perm", "quizplease").distinct_events is True
    assert _source("sochi", "quizplease").distinct_events is True


def test_permm_not_marked_as_distinct_events():
    """У ПЕРММ два JSON-эндпоинта пересекаются — его самодубли настоящие, флаг не ставим."""
    assert _source("perm", "permm").distinct_events is False
```

- [ ] **Step 2: Убедиться, что тесты падают**

```bash
PYTHONIOENCODING=utf-8 python -m pytest tests/test_config.py tests/test_merge.py -q -k "distinct_events or distinct_source"
```

Ожидается: `test_config.py` падает с `AttributeError: 'SourceConfig' object has no attribute 'distinct_events'`; тест в `test_merge.py` может пройти сразу (Task 1 уже добавил параметр) — это нормально, он закрепляет поведение на уровне слоя 2.

- [ ] **Step 3: Добавить поле в `SourceConfig`**

В `parser/src/parser/config.py`, сразу после блока `full_snapshot`:

```python
    distinct_events: bool = False
    # True = одна строка источника всегда одно событие (у каждой игры QuizPlease свой id
    # в API). Тогда fuzzy-дедуп не сливает две строки этого источника между собой, как бы
    # ни были похожи названия. НЕ ставить источникам, которые склеивают несколько
    # эндпоинтов: permm читает /json/events и /json/exhibitions, один экспонат приходит
    # оттуда дважды — там самодубли настоящие и должны схлопываться.
```

В `load_seeds`, рядом со строкой `full_snapshot=s.get("full_snapshot", False),`:

```python
                distinct_events=s.get("distinct_events", False),
```

- [ ] **Step 4: Проставить флаг в seeds.yaml**

В обоих блоках `- name: quizplease` (город `sochi` ~строка 26 и город `perm` ~строка 119), следующей строкой после `full_snapshot: true`:

```yaml
        distinct_events: true  # у каждой игры свой id в API → две строки = две разные игры
```

- [ ] **Step 5: Собрать множество в пайплайне**

В `parser/src/parser/pipeline.py`, рядом со сбором `priorities`:

```python
    priorities = {s.name: s.priority for s in city.sources}
    distinct_sources = frozenset(s.name for s in city.sources if s.distinct_events)
```

и в вызове слоя 2:

```python
        fuzzy = fuzzy_merge(merge.rows_to_upsert, existing, priorities, distinct_sources)
```

- [ ] **Step 6: Собрать множество в `dedup-backfill`**

В `parser/src/parser/cli.py`, в `_cmd_dedup_backfill`, рядом со сбором `priorities`:

```python
    priorities = {s.name: s.priority for s in cities[args.city].sources}
    distinct_sources = frozenset(
        s.name for s in cities[args.city].sources if s.distinct_events
    )
```

и в вызове кластеризации:

```python
    clusters, _pairs = cluster_events(
        rows,
        merge_threshold=args.threshold,
        report_threshold=args.threshold,
        distinct_sources=distinct_sources,
    )
```

- [ ] **Step 7: Убедиться, что тесты проходят**

```bash
PYTHONIOENCODING=utf-8 python -m pytest -q
```

Ожидается: `240 passed` (237 после Task 1 + 3 новых).

- [ ] **Step 8: Коммит**

```bash
git add parser/src/parser/config.py parser/config/seeds.yaml parser/src/parser/pipeline.py parser/src/parser/cli.py parser/tests/test_merge.py parser/tests/test_config.py
git commit -m "feat(seeds): флаг distinct_events; QuizPlease не сливается сам с собой"
```

---

### Task 3: Порог алерта по размеру кластера

Конфигурационная правка одной константы — нового теста нет, поведенческого шва под него не существует, а заводить его ради константы значит усложнять `run_city` без пользы. Проверяется полным прогоном тестов и грепом.

**Files:**
- Modify: `parser/src/parser/pipeline.py` (строка 343)

- [ ] **Step 1: Поднять порог**

`FuzzyResult.largest_cluster > 3` уходит в `PipelineResult.warnings` → Telegram-алерт. До правки `c37f98e` крупные кластеры почти всегда были ложными; теперь максимальный кластер на живых данных Перми — 4, и он настоящий (четыре формулировки обзорной экскурсии ПЕРММ). Порог `> 3` будет слать алерт каждый день на здоровых данных.

В `parser/src/parser/pipeline.py`:

```python
        # Порог 4, а не 3: после guard'ов на перечни и зонтики (см. fuzzy.py) кластер из
        # четырёх формулировок одной экскурсии ПЕРММ — норма, а не сигнал сбоя.
        if fuzzy.largest_cluster > 4:
```

Текст самого предупреждения (`f"fuzzy-дедуп: кластер из {fuzzy.largest_cluster} карточек — проверь порог"`) не меняется.

- [ ] **Step 2: Проверить, что ничего не сломалось**

```bash
PYTHONIOENCODING=utf-8 python -m pytest -q
```

Ожидается: `240 passed`.

- [ ] **Step 3: Коммит**

```bash
git add parser/src/parser/pipeline.py
git commit -m "chore(pipeline): алерт по кластеру от 5 карточек, а не от 4"
```

---

### Task 4: Документация

**Files:**
- Modify: `README.md` (раздел «`fuzzy.py` + `merge.fuzzy_merge` — Dedup v2 (слой 2)», описание `score_pair`)
- Modify: `docs/superpowers/specs/2026-08-18-fuzzy-dedup-design.md` (раздел «Ложные срабатывания containment»)
- Modify: `README.md` (раздел `config.py` → `SourceConfig`, где перечислены поля источника)

- [ ] **Step 1: Описать guard в README**

В описании `score_pair` дописать после существующего абзаца про `time_mismatch`:

```markdown
  Второй жёсткий guard — `distinct_sources`: две строки источника, помеченного в seeds
  `distinct_events: true`, не сливаются никогда. QuizPlease отдаёт по строке на игру
  (свой `game_id`), и «Квиз, плиз! PERM» с «Квиз, плиз! [новички] PERM» в одном зале
  в 19:30 — две разные игры; текстом их не отличить (`«Фотография как искусство»` vs
  `«…» (12+)` в тех же данных — настоящий дубль). Флаг опт-ин и **не** равен
  `full_snapshot`: `permm` полон, но читает два эндпоинта, и его самодубли настоящие.
```

В описании `SourceConfig` в разделе `config.py` добавить строку списка полей:

```markdown
- `distinct_events` — `true`, если одна строка источника всегда одно событие (у каждой игры
  QuizPlease свой id). Запрещает fuzzy-слою сливать две строки этого источника между собой.
  Не путать с `full_snapshot` (полнота среза для синхронизации отмен): `permm` — `full_snapshot`,
  но не `distinct_events`, потому что склеивает два JSON-эндпоинта и один экспонат приходит дважды
```

- [ ] **Step 2: Дописать третье семейство в спеку**

В `docs/superpowers/specs/2026-08-18-fuzzy-dedup-design.md`, в конец раздела «Ложные срабатывания containment», добавить:

```markdown
**Третье семейство — самодубли источника (найдено предпросмотром бэкфилла).** `Квиз, плиз! PERM`
⊂ `Квиз, плиз! [новички] PERM` при совпадающих площадке и времени даёт 1.0, но это две разные
игры QuizPlease (разные `game_id`, разные страницы билетов). Текстовой эвристики нет: скобочный
маркер не признак различия (`«Фотография как искусство»` vs `«…» (12+)` — настоящий дубль).
Лечится природой источника: флаг `distinct_events` в seeds объявляет «одна строка = одно
событие», и `score_pair` жёстко возвращает 0 для двух строк такого источника.

Переиспользовать `full_snapshot` для этого нельзя: он про полноту среза, а не про атомарность.
`permm` помечен `full_snapshot`, но читает два эндпоинта (`/json/events/…` и
`/json/exhibitions/active`), и один экспонат приходит дважды (`Выставка «Стечение обстоятельств»`
и `Стечение обстоятельств`, ещё две такие пары на 2026-12-31) — эти самодубли настоящие
и обязаны схлопываться.
```

- [ ] **Step 3: Коммит**

```bash
git add README.md docs/superpowers/specs/2026-08-18-fuzzy-dedup-design.md
git commit -m "docs: третье семейство ложных слияний и флаг distinct_events"
```

---

## Ручной этап: бэкфилл Перми

**Не задача для агента.** `--apply` необратимо удаляет боевые карточки и убивает их URL (риск 404 на проиндексированных страницах). Выполняет человек, после просмотра предпросмотра.

- [ ] **Шаг 1: Предпросмотр (безопасно, без записи)**

```bash
python -m parser.cli dedup-backfill --city perm --threshold 0.95
```

Ожидается: **37 кластеров, 46 карточек к удалению**. Если цифры 39/48 — значит `distinct_events` не доехал до `cli.py`, вернуться к Task 2 Step 6.

- [ ] **Шаг 2: Просмотр списка человеком**

Проверить, что в выводе больше нет пар `Квиз, плиз! PERM` / `Квиз, плиз! [новички] PERM` (даты 2026-08-18 и 2026-08-25).

Отдельно решить по возрастным вариантам — на мой взгляд это один дубль, но карточки живые:

```
2026-08-18 18:30  «Пермская деревянная скульптура»
2026-08-18 18:30  Детская сборная экскурсия «Пермская деревянная скульптура» (7+)
2026-08-18 18:30  Сборная экскурсия «Пермская деревянная скульптура» (7–12 лет)
```

- [ ] **Шаг 3: Применение**

```bash
python -m parser.cli dedup-backfill --city perm --threshold 0.95 --apply
```

Порог именно `0.95`. Дефолт команды — `DEDUP_CANDIDATE_SCORE = 0.75`, а серая зона по построению ~40% ложная (`Мастер-класс «Крабики»` ↔ `«Лошадки»` = 0.80, `День флага в парках города` ↔ `в саду Свердлова` = 0.75) — на нём удалятся настоящие карточки.

Сочи бэкфилл не нужен: в БД 2 события.

- [ ] **Шаг 4: Push и PR**

```bash
git push -u origin fix/fuzzy-containment-enumeration
```

PR в `master`; дождаться CI (`.github/workflows/parse.yml` гоняет тесты).

---

## Verification

**Модульно** — из каталога `parser/`:

```bash
PYTHONIOENCODING=utf-8 python -m pytest -q
```

Ожидается `240 passed`, вывод чистый.

**На живых данных.** Скрипт-предпросмотр из этой сессии лежит в скретчпаде
(`…/scratchpad/backfill_preview.py`): он тянет карточки Перми из сохранённого дампа и гоняет
настоящий `cluster_events`. После Task 2 обновить его вызов, добавив
`distinct_sources=frozenset({"quizplease"})`, и сверить: было 39 кластеров / 48 удалений,
должно стать **37 / 46**, максимальный кластер — 4 (обзорная экскурсия ПЕРММ).

Дамп при необходимости пересобирается через Supabase MCP (проект `taixlqbbepudndqhnehj`):

```sql
select json_agg(json_build_array(id, city, date, title, coalesce(venue_name,''), time_start, source))::text
from events where city='perm' and date <> 'always';
```

**Сквозная проверка пайплайна** (не пишет в БД):

```bash
python -m parser.cli run --city perm --source quizplease --dry-run
```

В логе `dedup.fuzzy` поля `merged` и `in_source` для quizplease должны быть `0`.

## Вне объёма

- **Карточки-перечни как таковые.** `Мастер-классы: «Единорог», «Планета», «Ёжик»` остаётся в БД рядом с тремя реальными МК. Это дефект извлечения (LLM лепит афишу-агрегат из одного поста), а не дедупа — отдельная задача к промптам `extraction/prompts.py`.
- **LLM-арбитр для серой зоны 0.75–0.95.** Отложен спекой осознанно; `dedup_candidates` копит материал.
- **Кластер «День рождения парка Горького» ×4** — известный предел (общих основ 2 из 6), правилами не ловится.
