# Фильтр не-событий (новости/реклама/розыгрыши) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** убрать с сайта карточки, которые не являются событиями (новости, объявления служб, промо, розыгрыши, голосования, open call), не потеряв настоящие события типа `other`.

**Architecture:** три слоя по образцу фильтра spurious `always` + чистка БД.
(1) Префильтр: VK-группам можно задать `source_type` (как Telegram-каналам); новостной паблик `permactive` → `aggregator` (строгий порог: дата И маркер/билеты).
(2) Промпт: правило «что НЕ является событием» в batch-промптах всех трёх экстракторов.
(3) Постфильтр: `validator.is_non_event(title, source)` по узким маркерам заголовка, guard в `to_event_row`, счётчик `skipped_non_event`.
(4) Миграция удаляет накопленные строки по явному списку id, подтверждённому пользователем на dry-run (предикат постфильтра + дочистка известных случаев, которые постфильтр намеренно не ловит). Применяется после мержа в master.

Слои — три разные точки контроля, а не три реализации одного правила: префильтр экономит LLM-вызовы, промпт снижает вероятность ошибки классификации, постфильтр защищает БД от ошибок LLM независимо от качества двух первых.

**Ответственность слоёв.** Постфильтр гарантирует отсечение только однозначно распознаваемых не-событий — это последний защитный слой для узкого класса случаев, а не «защита БД от не-событий вообще». Полнота фильтрации обеспечивается совокупностью трёх слоёв. Поэтому ни один слой по отдельности не обязан ловить всё: то, что сознательно оставлено за другим слоем, не повод донастраивать текущий.

**Постфильтр — эвристический guard, а не классификатор.** Он ловит только то, что узко и однозначно, и никогда не срезает настоящие события. Если для случая нужен широкий маркер («появится», «парковк»), такой маркер не добавляется: случай остаётся на префильтре и промпте. Граница: только social/generic-источники, структурированные (timepad/quizplease/permm/twogis/…) не фильтруются.

**Tech Stack:** Python 3, pytest (asyncio_mode=auto), Supabase Postgres, PyYAML seeds.

**Spec:** дизайн согласован в чате 2026-09-18 (bounded, отдельного spec-файла нет). Выбран вариант **A**: `permactive` остаётся в источниках, но со строгим префильтром.

## Этапы и критерии перехода

| Этап | Результат | Критерий перехода |
|---|---|---|
| 1. Префильтр | `permactive` обрабатывается строго, афиша-группы — как раньше | новости permactive не доходят до LLM, реклама событий из permactive доходит |
| 2. Промпт | LLM знает границу «событие / не событие» | правило подключено ко всем batch-экстракторам и не приводит к потере контрольных событий на реальных постах; эффект на не-событиях фиксируется как наблюдение |
| 3. Постфильтр | однозначные не-события отсекаются перед записью в БД, независимо от LLM | ни одно контрольное событие не отброшено; известные однозначные не-события пойманы узкими маркерами |
| 4. Подготовка миграции | файл с явным списком id | пользователь подтвердил фактический список строк |
| 5. README | архитектура и бизнес-правило зафиксированы | весь набор тестов зелёный |
| — мерж в master — | | |
| 6. Применение миграции | накопленный шум удалён | новых не-событий нет, кроме явно выделенной дельты до активации нового кода; дельта подтверждена отдельно; RETURNING = базовый список + дельта; удалённых id нет в БД; контрольные события на месте |

## Локализация (почему это нужно)

В БД 55 строк `city='perm' AND type='other'`, из них ~15 не события, и все из social-источников:

| Источник | Группа/канал | Не-события |
|---|---|---|
| vk-posts | `permactive` («Пермь Активная», wall-30210603) — городские новости | 11: Мексика, Госдума, Средняя дамба, путепровод, судно на Каме, цены на продукты, «Ждули», розыгрыш двери, парковки ×3 |
| vk-posts | `parmabasket` | «Специальное предложение от сети пиццерий «Пиццбург»» |
| vk-posts | `permm_museum` | «Розыгрыш персональной фотосессии в «ПЕРММ»» |
| vk-posts | `permartmuseum` | «Голосование за номинантов … Russian Traveler Awards 2026» |
| telegram-posts | `permmmuseum` | «Open call на 13 сезон резиденции MaxArt x ПЕРММ» |

- Префильтр: `pipeline.py:699` зовёт `vk_mod.is_event_candidate(text)` без `source_type` → всегда SOCIAL (хватает одной даты). В новостях дата есть всегда.
- LLM: посты идут через `_SYSTEM_PROMPT_BATCH` («ВЕРНИ ВСЕ события без исключения…»). Определения не-события в промпте нет, `NOT_AN_EVENT` в batch запрещён.
- Постфильтра по содержанию нет (только `is_spurious_always`).

## Global Constraints

- Работать в ветке `feat/non-event-filter` (уже создана в worktree `C:\Python\entertainment\.claude\worktrees\angry-mccarthy-1abf7e`). **Перед каждым `git add`/`git commit` отдельным шагом выполнить `git branch --show-current`** и убедиться, что вывод `feat/non-event-filter`.
- Тесты запускать из `parser/` интерпретатором основного venv: `../../../../parser/.venv/Scripts/python.exe -m pytest …` (далее `$PY -m pytest`). `tests/conftest.py` ставит `src/` worktree первым в `sys.path`, поэтому импортируется код worktree, а не основного checkout.
- Базовая линия: `$PY -m pytest -q` → `240 passed`. После каждой задачи весь набор должен быть зелёным.
- Не трогать: `_SYSTEM_PROMPT_SINGLE`, VK-группы Сочи, баги атрибуции (`source_url=vk.com/prmgo` у постов permactive; `event_url` из тела поста у розыгрыша двери). Это отдельные задачи.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- Изменения в боевой БД (Supabase) только после явного «да» пользователя в чате, по списку строк, который пользователь видел.
- Бизнес-правило модели данных: open call / приём заявок, розыгрыши, голосования, промо — не события (решение пользователя 2026-09-18). Фиксируется в README.

## File Structure

| Файл | Что меняется |
|---|---|
| `parser/src/parser/config.py` | поле `SourceConfig.vk_source_types: dict[str, SourceType]` + парсинг в `load_seeds` |
| `parser/config/seeds.yaml` | `vk_source_types: {permactive: aggregator}` у perm `vk-posts`, исправить комментарий к `permactive` |
| `parser/src/parser/pipeline.py` | VK-префильтр берёт `source_type` группы; счётчик `skipped_non_event`; `_safe_to_event_row` различает причины; агрегация и `source_health` |
| `parser/src/parser/extraction/prompts.py` | константа `NON_EVENT_INSTRUCTIONS` |
| `parser/src/parser/extraction/{gemini,groq,deepseek}_extractor.py` | вставить `{NON_EVENT_INSTRUCTIONS}` в `_SYSTEM_PROMPT_BATCH` |
| `parser/src/parser/validator.py` | `_NON_EVENT_TITLE_RE`, `is_non_event`, guard в `to_event_row` |
| `parser/tests/test_non_event.py` | новый файл, растёт по задачам 1–3 |
| `supabase/migrations/20260918000001_remove_non_events_social.sql` | чистка накопленного по подтверждённому списку id |
| `README.md` | строка в таблице фильтров, `vk_source_types`, список тестов |

---

### Task 1: строгий префильтр для новостных VK-групп (`vk_source_types`)

**Files:**
- Modify: `parser/src/parser/config.py` (`SourceConfig` ~стр. 236–241, `load_seeds` ~стр. 292)
- Modify: `parser/config/seeds.yaml` (perm `vk-posts`, ~стр. 190–213)
- Modify: `parser/src/parser/pipeline.py` (импорт стр. 21, префильтр стр. 699)
- Create: `parser/tests/test_non_event.py`

**Interfaces:**
- Produces: `SourceConfig.vk_source_types: dict[str, SourceType]` (по умолчанию `{}`); ключ = screen-name группы из `vk_groups`. Группы без ключа → `SourceType.SOCIAL`.

- [ ] **Step 1: Написать падающие тесты**

Создать `parser/tests/test_non_event.py`:

```python
"""Фильтр не-событий (новости/объявления/реклама) из social/generic-источников.

На /perm среди карточек type='other' около четверти оказались не событиями: новости
городского паблика permactive («Пермь Активная»), розыгрыши, промокоды, голосования,
open call. Причины: VK-префильтр всегда мягкий (SOCIAL, хватает одной даты в новости),
а batch-промпт требует «вернуть ВСЕ события» и не говорит, что не является событием.

Три слоя, как у spurious 'always': строгий префильтр для новостных групп (seeds),
правило в batch-промптах, постфильтр is_non_event по заголовку (guard в to_event_row).
Заголовки и тексты ниже реальные, из БД на 2026-09-18.
"""

import time

import pytest

from parser.classifiers import is_event_candidate
from parser.config import SourceConfig, SourceType, load_seeds
from parser.pipeline import _run_vk_posts_source


# --- слой 1: строгий префильтр для новостных VK-групп ---

PERMACTIVE_NEWS = [
    "🚔 В Перми до 8 октября оставили под арестом 44-летнего гражданина Мексики, которого "
    "проверяют на возможное участие в деятельности наркокартеля.",
    "🅿 Муниципальные парковки в Перми будут работать бесплатно с 18 по 20 сентября — на время "
    "проведения выборов платить за стоянку не потребуется.",
    # «🚢 На Каме появится новое судно стоимостью…» префильтр НЕ ловит («стоимостью» содержит
    # маркер «стоимость»). Его отсекает постфильтр по заголовку (слой 3).
    "📺 Выпуск с его участием покажут 17 сентября в 18:00 на канале «Ю».",
    "🎁 РАЗЫГРЫВАЕМ МЕТАЛЛИЧЕСКУЮ ДВЕРЬ! Участие бесплатное. Всего — 6 победителей. 📅 Итоги 9 ноября.",
]

PERMACTIVE_EVENT = (
    "Пермь, приглашаем на главное авто-мото шоу сезона!\n\nШоу каскадеров 2026\n\n"
    "с 18 по 20 сентября 2026\nСтадион \"Локомотив\"\n\nБилеты на сайте: bitvamashin.ru/perm"
)


def _perm_vk_source() -> SourceConfig:
    return next(s for s in load_seeds()["perm"].sources if s.name == "vk-posts")


def test_permactive_is_strict_in_seeds():
    """permactive («Пермь Активная») — городские новости, а не афиша: строгий префильтр."""
    assert _perm_vk_source().vk_source_types["permactive"] == SourceType.AGGREGATOR


def test_afisha_groups_stay_social():
    """Афиша-группы не трогаем: у них мало новостей, строгий порог срезал бы анонсы-переносы."""
    types = _perm_vk_source().vk_source_types
    for group in ("prmgo", "kudaperm", "permkudapoiti", "perm_where_to_go"):
        assert group not in types


@pytest.mark.parametrize("text", PERMACTIVE_NEWS)
def test_aggregator_threshold_rejects_permactive_news(text):
    assert is_event_candidate(text, SourceType.AGGREGATOR) is False


def test_aggregator_threshold_keeps_permactive_event_ad():
    assert is_event_candidate(PERMACTIVE_EVENT, SourceType.AGGREGATOR) is True


class _FakeVk:
    def __init__(self, walls: dict[str, list[str]]) -> None:
        self._walls = walls

    async def fetch_wall_posts(self, domain: str, *, count: int = 100):
        now = time.time()
        return [
            {"owner_id": -1, "id": i, "date": now, "text": t}
            for i, t in enumerate(self._walls[domain])
        ]


class _RecordingExtractor:
    """Запоминает, какие тексты дошли до LLM, и ничего не извлекает."""

    def __init__(self) -> None:
        self.docs: list[str] = []

    async def extract_many(self, html: str, source_url: str):
        self.docs.append(html)
        return []


async def test_vk_prefilter_uses_group_source_type(monkeypatch):
    """Группа с source_type=aggregator отсеивает новость с датой, обычная (social) пропускает."""
    news = PERMACTIVE_NEWS[1]
    walls = {"newsgroup": [news, PERMACTIVE_EVENT], "afisha": [news]}
    monkeypatch.setattr("parser.pipeline.VkClient", lambda client, key: _FakeVk(walls))
    extractor = _RecordingExtractor()
    source = SourceConfig(
        name="vk-posts",
        extraction_mode="vk_posts",
        vk_groups=["newsgroup", "afisha"],
        vk_source_types={"newsgroup": SourceType.AGGREGATOR},
    )

    await _run_vk_posts_source(None, source, extractor, None, "perm", "key", True, 5, 7000)

    newsgroup_doc, afisha_doc = extractor.docs
    assert "парковки" not in newsgroup_doc
    assert "Шоу каскадеров" in newsgroup_doc
    assert "парковки" in afisha_doc
```

- [ ] **Step 2: Убедиться, что тесты падают по нужной причине**

Run: `$PY -m pytest tests/test_non_event.py -v`
Ожидается:
- `test_permactive_is_strict_in_seeds`, `test_afisha_groups_stay_social` → FAIL: `AttributeError: 'SourceConfig' object has no attribute 'vk_source_types'`
- `test_vk_prefilter_uses_group_source_type` → FAIL: `TypeError: … unexpected keyword argument 'vk_source_types'`
- `test_aggregator_threshold_*` → PASS сразу. Это характеризующие тесты: они фиксируют, что существующий порог AGGREGATOR подходит для permactive. Если какой-то из них падает, остановиться и разобраться до реализации.

- [ ] **Step 3: Поле в `SourceConfig`**

В `parser/src/parser/config.py` сразу после поля `vk_groups` (блок «Для vk_events / vk_posts») добавить:

```python
    vk_source_types: dict[str, SourceType] = field(default_factory=dict)
    """Строгость префильтра по группам vk_groups (screen-name → SourceType). Группы без ключа —
    SOCIAL. aggregator — для пабликов с новостями/рекламой (нужна дата И маркер/билеты)."""
```

- [ ] **Step 4: Парсинг в `load_seeds`**

В `load_seeds` после строки `vk_groups=s.get("vk_groups") or [],` добавить:

```python
                vk_source_types={
                    group: SourceType(t)
                    for group, t in (s.get("vk_source_types") or {}).items()
                },
```

- [ ] **Step 5: seeds.yaml**

В `parser/config/seeds.yaml` у perm-источника `vk-posts` заменить строку
`          - permactive         # активный досуг Перми`
на
`          - permactive         # «Пермь Активная»: городские новости + реклама событий`
и сразу после списка `vk_groups` (после строки `          - parmabasket       # БК «Парма» (баскетбол)`) добавить:

```yaml
        # Строгость префильтра по группам (по умолчанию social: хватает одного сигнала).
        # aggregator: нужна дата И маркер/билеты. permactive — новостной паблик: у новостей
        # всегда есть дата, но нет событийных маркеров (проверено 2026-09-18, test_non_event).
        vk_source_types:
          permactive: aggregator
```

- [ ] **Step 6: Префильтр в VK-петле**

В `parser/src/parser/pipeline.py`:
- строку 21 `from .config import DEDUP_MERGE_SCORE, CityConfig, SourceConfig` заменить на
  `from .config import DEDUP_MERGE_SCORE, CityConfig, SourceConfig, SourceType`
- в `_run_vk_posts_source` перед циклом `for p in posts:` (после комментария «Префильтр: свежие посты-кандидаты…») добавить
  ```python
        source_type = source.vk_source_types.get(screen, SourceType.SOCIAL)
  ```
- строку `            if not vk_mod.is_event_candidate(text):` заменить на
  ```python
            if not is_event_candidate(text, source_type):
  ```
  (`is_event_candidate` уже импортирован из `.classifiers` в стр. 20. Реэкспорт в `sources/vk.py` не трогать.)

- [ ] **Step 7: Тесты зелёные**

Run: `$PY -m pytest tests/test_non_event.py -v` → все PASS.
Run: `$PY -m pytest -q` → `248 passed` (240 + 8 новых).

- [ ] **Step 8: Проверка ветки и коммит**

```bash
git branch --show-current
```
Ожидается `feat/non-event-filter`. Затем:
```bash
git add parser/src/parser/config.py parser/config/seeds.yaml parser/src/parser/pipeline.py parser/tests/test_non_event.py
git commit -m "feat(vk): строгость префильтра по группам; permactive → aggregator

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: правило «что НЕ является событием» в batch-промптах

**Files:**
- Modify: `parser/src/parser/extraction/prompts.py`
- Modify: `parser/src/parser/extraction/gemini_extractor.py` (импорт стр. 20, batch-промпт стр. 70)
- Modify: `parser/src/parser/extraction/groq_extractor.py` (импорт стр. 33, batch-промпт стр. 101)
- Modify: `parser/src/parser/extraction/deepseek_extractor.py` (импорт стр. 22, batch-промпт стр. 90)
- Test: `parser/tests/test_non_event.py`

**Interfaces:**
- Produces: `prompts.NON_EVENT_INSTRUCTIONS: str`, содержит фразу `НЕ являются событиями`.

- [ ] **Step 1: Падающий тест**

Дописать в конец `parser/tests/test_non_event.py`:

```python
# --- слой 2: правило в batch-промптах ---


def test_batch_prompts_exclude_non_events():
    """Посты идут через extract_many → правило обязано быть в BATCH-промпте каждого экстрактора."""
    from parser.extraction import deepseek_extractor, gemini_extractor, groq_extractor

    phrase = "НЕ являются событиями"
    for mod in (deepseek_extractor, gemini_extractor, groq_extractor):
        assert phrase in mod._SYSTEM_PROMPT_BATCH, mod.__name__
```

- [ ] **Step 2: Убедиться, что падает**

Run: `$PY -m pytest tests/test_non_event.py::test_batch_prompts_exclude_non_events -v`
Expected: FAIL `AssertionError: parser.extraction.deepseek_extractor`

- [ ] **Step 3: Константа в `prompts.py`**

Дописать в конец `parser/src/parser/extraction/prompts.py`:

```python


# Правило «что не является событием» для batch-промптов: посты VK/Telegram идут через
# extract_many, а требование «верни ВСЕ события» толкало LLM делать событие из каждого поста
# с датой (новости городских пабликов, промо, розыгрыши). См. test_non_event.
NON_EVENT_INSTRUCTIONS = """\
- Посты и карточки, которые НЕ являются событиями, НЕ извлекай (в batch-режиме просто не \
добавляй их в массив). Событие — это то, куда человек может прийти в конкретное время: \
концерт, спектакль, выставка, ярмарка, мастер-класс, экскурсия, матч, праздник.
- НЕ события: новости и происшествия (аресты, суды, ДТП), законы и инициативы властей, \
объявления городских служб (парковки, ремонт дорог и мостов, перекрытия, транспорт), \
розыгрыши и конкурсы в соцсетях, промокоды, скидки и спецпредложения, голосования, \
приём заявок и open call, выход телепередач, итоги прошедших событий.
- Дата в тексте сама по себе не делает пост событием: «работы начнутся 20 сентября», \
«итоги розыгрыша 9 ноября», «акция до 30 сентября» → пропусти."""
```

- [ ] **Step 4: Подключить в три экстрактора**

В каждом из `gemini_extractor.py`, `groq_extractor.py`, `deepseek_extractor.py`:
- импорт `from .prompts import DATE_ALWAYS_INSTRUCTIONS` заменить на
  `from .prompts import DATE_ALWAYS_INSTRUCTIONS, NON_EVENT_INSTRUCTIONS`
- **внутри `_SYSTEM_PROMPT_BATCH`** (не SINGLE!) сразу после строки `{DATE_ALWAYS_INSTRUCTIONS}` добавить строку `{NON_EVENT_INSTRUCTIONS}`. Номера строк с `{DATE_ALWAYS_INSTRUCTIONS}` в batch-промптах: gemini 70, groq 101, deepseek 90. Первое вхождение (SINGLE) не трогать.

- [ ] **Step 5: Тесты зелёные**

Run: `$PY -m pytest tests/test_non_event.py tests/test_spurious_always.py tests/test_extractors.py -q` → PASS.
Run: `$PY -m pytest -q` → `249 passed`.

- [ ] **Step 6: Проверка эффекта промпта на реальных постах (разовая, вне CI)**

Юнит-тест выше проверяет только наличие правила. Но для части не-событий промпт — единственный барьер: «На Каме появится новое пассажирское судно» проходит префильтр («стоимостью») и намеренно не ловится постфильтром. К тому же `_SYSTEM_PROMPT_BATCH` используют все batch-источники, и слишком широкое правило может срезать настоящие события. В CI эту проверку не ставим: ответ LLM недетерминирован, сеть в тестах не держим.

- **Цель:** подтвердить, что правило не теряет события, и зафиксировать его фактический эффект на не-событиях.
- **Набор** (тексты лежат в `raw_documents.content`, берём по `url`):
  - *не-события:* `vk.com/wall-30210603_3344705` (Мексика), `_3347335` (Госдума), `_3349963` (Средняя дамба), `_3344580` (путепровод), `_3340078` (судно), `_3351178` (цены), `_3352158` («Ждули»), `_3352007` (парковки), `_3350265` (розыгрыш двери); `vk.com/wall-42735432_176424` (Пиццбург); `vk.com/wall-13853229_11362` (розыгрыш фотосессии); `vk.com/wall-5281156_18094` (голосование); `t.me/permmmuseum/3747` (open call);
  - *контрольные события:* `vk.com/wall-1743189_200637` (Толкучка, перенос даты), `vk.com/wall-30210603_3351346` (Шоу каскадеров, пост permactive), `vk.com/wall-17064412_75277` (Осенняя ярмарка), `vk.com/wall-1743189_200468` (Цирк «Империя мастеров»).
- **Как:** throwaway-скрипт в scratchpad, не коммитится. Переиспользует существующий код, в `src/` ничего не добавляется:
  - `Settings.from_env()` (`parser/src/parser/config.py`) — env из `C:\Python\entertainment\parser\.env`;
  - `cli._make_extractor(settings, settings.llm_provider)` (`parser/src/parser/cli.py:37`) — основной провайдер прода, без фолбэк-цепочки, чтобы результат относился к одной модели;
  - `pipeline._chunks_by_budget` + `pipeline._extract_chunk` — те же пачки и маркеры `=== POST <url> ===`, что в проде;
  - сопоставление «пост → извлечено/нет» по `event_url` события.
  Запуск интерпретатором основного venv с `sys.path` на `src/` worktree: проверяется промпт ветки, а не master.
- **Прогон:** 2 раза (недетерминизм). Итог — таблица «пост → извлечено в прогоне 1/2» в чате и в описании PR.
- **Критерий перехода (единственный блокирующий):** правило подключено ко всем batch-экстракторам, и все 4 контрольных события извлечены в обоих прогонах. Если контрольное событие потеряно, сузить формулировку `NON_EVENT_INSTRUCTIONS` и повторить проверку.
- **Наблюдение (не блокирует):** результат по не-событиям фиксируется в таблице как проверка ожидаемого эффекта. Полного покрытия промптом не требуется, промпт по нему не донастраивается: однозначные случаи закрывает постфильтр, остальные — совокупность слоёв. Если не-событие, закрытое только промптом (судно), всё равно извлекается, это записывается в описание PR как известный остаточный риск. Итеративной настройки промпта не делаем.

- [ ] **Step 7: Проверка ветки и коммит**

```bash
git branch --show-current
```
Ожидается `feat/non-event-filter`.
```bash
git add parser/src/parser/extraction/prompts.py parser/src/parser/extraction/gemini_extractor.py parser/src/parser/extraction/groq_extractor.py parser/src/parser/extraction/deepseek_extractor.py parser/tests/test_non_event.py
git commit -m "feat(prompts): batch-промпты не извлекают новости/промо/розыгрыши

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: постфильтр `is_non_event` + guard + счётчик

**Цель:** последний защитный слой для узкого класса однозначно распознаваемых не-событий, прошедших префильтр и LLM. Это не «защита БД от не-событий вообще»: широкие случаи («парковк», «появится», «ремонт») сознательно не входят в его ответственность из-за риска false positive (см. «Ответственность слоёв» в шапке).
**Критерий перехода:** (1) обязательно: ни один заголовок контрольного набора настоящих событий не отбрасывается; (2) цель: известные однозначные не-события пойманы узкими маркерами. Неоднозначные случаи явно перечислены в тесте как «на других слоях» — так при сопровождении видно, что это решение, а не пропуск.

**Files:**
- Modify: `parser/src/parser/validator.py` (новый предикат перед `to_event_row`, guard в `to_event_row`)
- Modify: `parser/src/parser/pipeline.py` (`_safe_to_event_row` стр. 154–166, `PipelineResult` стр. 176, агрегация ~стр. 284–294)
- Test: `parser/tests/test_non_event.py`

**Interfaces:**
- Consumes: `config.SOCIAL_SOURCE_PREFIXES` (уже импортирован в validator).
- Produces: `validator.is_non_event(title: str, source: str) -> bool`; `PipelineResult.skipped_non_event: int`; `to_event_row` возвращает `None` и для не-событий.

- [ ] **Step 1: Падающие тесты**

В `parser/tests/test_non_event.py` расширить импорты вверху файла до:

```python
from parser.classifiers import is_event_candidate
from parser.config import SourceConfig, SourceType, load_seeds
from parser.models import ParsedEvent
from parser.pipeline import PipelineResult, _run_vk_posts_source, _safe_to_event_row
from parser.validator import is_non_event, to_event_row
```

и дописать в конец файла:

```python
# --- слой 3: постфильтр по заголовку ---

# Реальные не-события, попавшие на сайт, которые постфильтр ловит узкими маркерами.
NON_EVENT_TITLES = [
    "Гражданин Мексики под арестом по делу о наркотиках",
    "В Госдуме предложили открывать в детсадах вечерние группы по просьбе родителей",
    "В Перми движение по второй очереди Средней дамбы планируют открыть 18 октября",
    "Капитальный ремонт путепровода на улице Промышленной, 127",
    "Розыгрыш металлической двери Аркан 206",
    "Розыгрыш персональной фотосессии в «ПЕРММ»",
    "Отслеживание цен на продукты",
    "Специальное предложение от сети пиццерий «Пиццбург»",
    "Open call на 13 сезон резиденции MaxArt x ПЕРММ",
    "Голосование за номинантов Национальной туристической премии Russian Traveler Awards 2026",
    "Максим из Краснокамска в телепроекте «Ждули»",
]

# Не-события, которые постфильтр НАМЕРЕННО не ловит: нужный маркер слишком широкий
# («парковк» бывает в названиях событий: «Автокинотеатр на парковке ТРЦ»; «появится» — в
# анонсах). Их закрывают другие слои:
#   «Бесплатные парковки на время выборов» — префильтр (permactive → aggregator) + промпт;
#   «На Каме появится новое пассажирское судно» — промпт (префильтр пропускает: «стоимостью»).
# Накопленные в БД экземпляры удаляются миграцией по явному списку id (Task 4).

# Настоящие события type='other' с того же сайта, должны остаться. Сюда же слова-ловушки:
# «конкурса», «акция», «ярмарка».
REAL_EVENT_TITLES = [
    "Толкучка",
    "ТОЛКУЧКА",
    "Толкучка во дворе соцгородка “Рабочий поселок\"",
    "Шоу каскадёров",
    "Шоу каскадеров 2026",
    "Осенняя ярмарка",
    "Ярмарка и вечер Народного караоке",
    'Цирк "Империя мастеров" в Перми!',
    "Благотворительная акция «Давай дружить!»",
    "Выставка-пристройство собак из приюта «Доброе сердце»",
    "Торжественная церемония награждения победителей конкурса «Музейный Олимп»",
    "Праздничный вечер для ветеранов",
    "Музейная программа «Соль-вода» в музее «Хохловка»",
    "«Полировка ГАЗ‑13 „Чайка“ — вживую в музее: приходите увидеть процесс»",
    "Премьерный показ фильма о Романовых на фестивале «Флаэртиана»",
    "Релакс - Ретрит «Левада»",
    "Видеопрогулка \"Моя любимая книга\"",
]


def _parsed(title: str, date: str = "2026-09-20") -> ParsedEvent:
    return ParsedEvent(
        title=title,
        type="other",
        date=date,
        price_min=0,
        price_max=0,
        price_text="бесплатно",
        address="Пермь",
        venue_name="Пермь",
    )


@pytest.mark.parametrize("title", NON_EVENT_TITLES)
def test_non_event_titles_detected(title):
    assert is_non_event(title, "vk-posts") is True


@pytest.mark.parametrize("title", REAL_EVENT_TITLES)
def test_real_event_titles_kept(title):
    assert is_non_event(title, "vk-posts") is False


@pytest.mark.parametrize("source", ["telegram-posts", "generic:domain.ru", "generic"])
def test_non_event_applies_to_all_social_sources(source):
    assert is_non_event("Розыгрыш металлической двери Аркан 206", source) is True


@pytest.mark.parametrize("source", ["timepad", "quizplease", "permm", "twogis-bowling"])
def test_structured_sources_not_filtered(source):
    """API-источники отдают только события, их заголовки не трогаем."""
    assert is_non_event("Голосование за лучший квиз сезона", source) is False


def test_to_event_row_drops_non_event():
    row = to_event_row(
        _parsed("Розыгрыш металлической двери Аркан 206"), "perm", "https://vk.com/w", "vk-posts"
    )
    assert row is None


def test_to_event_row_keeps_real_event():
    row = to_event_row(_parsed("Осенняя ярмарка"), "perm", "https://vk.com/w", "vk-posts")
    assert row is not None


def test_safe_to_event_row_counts_non_event_separately():
    """Не-событие считается в skipped_non_event, а не в skipped_always."""
    sub = PipelineResult()
    row = _safe_to_event_row(
        _parsed("Гражданин Мексики под арестом по делу о наркотиках"), "perm", "https://vk.com/w", "vk-posts", sub
    )
    assert row is None
    assert sub.skipped_non_event == 1
    assert sub.skipped_always == 0


def test_safe_to_event_row_always_still_counted_as_always():
    sub = PipelineResult()
    _safe_to_event_row(_parsed("Выставка", date="always"), "perm", "https://vk.com/w", "vk-posts", sub)
    assert sub.skipped_always == 1
    assert sub.skipped_non_event == 0
```

- [ ] **Step 2: Убедиться, что падает**

Run: `$PY -m pytest tests/test_non_event.py -q`
Expected: ошибка коллекции `ImportError: cannot import name 'is_non_event' from 'parser.validator'`. Причина: функции ещё нет, а не опечатка.

- [ ] **Step 3: Предикат в `validator.py`**

В `parser/src/parser/validator.py` между `is_spurious_always` и `to_event_row` вставить:

```python
# Эвристический guard, не классификатор: заголовки однозначных не-событий, которые LLM всё
# равно извлекает из постов (новости городских пабликов, объявления служб, розыгрыши/промо,
# голосования, open call). Только узкие маркеры: широкие («конкурс», «акция», «парковк»,
# «появится») встречаются в названиях настоящих событий — такие случаи оставлены префильтру
# и промпту (см. test_non_event). Синхронно с dry-run миграции 20260918000001.
_NON_EVENT_TITLE_RE = re.compile(
    r"розыгрыш|разыгрыва|промокод|специальное предложение|спецпредложение"
    r"|голосовани|open[\s-]?call|опен[\s-]?колл|при[её]м заявок"
    r"|госдум|законопроект|под арест|уголовн|по делу о"
    r"|капитальный ремонт|путепровод|планируют открыть"
    r"|отслеживани|телепроект",
    re.IGNORECASE,
)


def is_non_event(title: str, source: str) -> bool:
    """True: social/generic-источник отдал заголовок новости/объявления/рекламы, а не события.

    Последний рубеж после префильтра и промпта. API-источники (timepad/quizplease/...) отдают
    только события, их не трогаем (как и в is_spurious_always).
    """
    return any(source.startswith(p) for p in SOCIAL_SOURCE_PREFIXES) and bool(
        _NON_EVENT_TITLE_RE.search(title)
    )
```

- [ ] **Step 4: Guard в `to_event_row`**

В `to_event_row` заменить docstring и добавить проверку сразу после блока `if is_spurious_always(...): … return None`:

```python
    """ParsedEvent → EventRow. None, если событие отбраковано (spurious 'always' или не-событие).

    None — последний рубеж против LLM-галлюцинаций date='always' и новостей/рекламы из постов
    VK/Telegram/generic. Caller обязан проверить результат на None и пропустить такую строку.
    """
```

```python
    if is_non_event(parsed.title, source):
        log.warning("validator.non_event_dropped", source=source, title=parsed.title[:80])
        return None
```

- [ ] **Step 5: Счётчик в `pipeline.py`**

1. Импорт стр. 47: `from .validator import is_spurious_always, to_event_row, to_venue` оставить как есть (`is_non_event` в pipeline не нужен).
2. В `PipelineResult` после `skipped_always` добавить:
   ```python
    skipped_non_event: int = 0  # отброшено не-событий по заголовку (новости/реклама/розыгрыши)
   ```
3. Тело `_safe_to_event_row` заменить на:
   ```python
    """Единая точка конвертации в pipeline: to_event_row + учёт отбракованных строк.

    to_event_row возвращает None, когда validator-guard отсёк галлюцинацию date='always'
    (social/generic-источник без явной даты) или не-событие (новость/реклама). Считаем их
    раздельно в sub.skipped_always / sub.skipped_non_event. Каллер пропускает None-строку.
    """
    row = to_event_row(parsed, city, source_url, source)
    if row is None:
        if is_spurious_always(parsed.date, parsed.type, source):
            sub.skipped_always += 1
        else:
            sub.skipped_non_event += 1
    return row
   ```
4. В агрегации по источникам (блок с `result.skipped_always += sub.skipped_always`) добавить:
   ```python
            result.skipped_non_event += sub.skipped_non_event
   ```
   и после `if sub.skipped_always: log.info("source.skipped_always", …)`:
   ```python
            if sub.skipped_non_event:
                log.info("source.skipped_non_event", source=source.name, count=sub.skipped_non_event)
   ```
5. В блоке `source_health` сразу после
   ```python
                if health_last_error is None and sub.skipped_always:
                    health_last_error = f"Отброшено spurious 'always': {sub.skipped_always}"
   ```
   добавить:
   ```python
                elif health_last_error is None and sub.skipped_non_event:
                    health_last_error = f"Отброшено не-событий: {sub.skipped_non_event}"
   ```

- [ ] **Step 6: Тесты зелёные**

Run: `$PY -m pytest tests/test_non_event.py -q` → PASS.
Критерий перехода (см. шапку задачи): все `REAL_EVENT_TITLES` остаются — это обязательно. Если какой-то настоящий заголовок ловится, маркер сужается или убирается, а соответствующее не-событие переносится в комментарий «на других слоях». Расширять маркер ради охвата нельзя.
Run: `$PY -m pytest -q` → всё зелёное (`test_spurious_always.py` и `test_validator.py` без изменений).

- [ ] **Step 7: Проверка ветки и коммит**

```bash
git branch --show-current
```
Ожидается `feat/non-event-filter`.
```bash
git add parser/src/parser/validator.py parser/src/parser/pipeline.py parser/tests/test_non_event.py
git commit -m "feat(validator): постфильтр is_non_event по заголовку + счётчик skipped_non_event

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: подготовка миграции — контрольный список удаляемых строк

**Цель:** зафиксировать в миграции ровно тот набор строк, который пользователь просмотрел и подтвердил.
**Результат:** файл миграции, который удаляет строки по явному списку id; список получен из dry-run и подтверждён пользователем.
**Критерий перехода:** пользователь явно подтвердил **фактический** список строк (id, title, source, city, type). Ожидаемое число строк критерием не является. Главный артефакт задачи — этот список.

Почему по id, а не по предикату:
- предикат постфильтра (Task 3) намеренно не покрывает часть известных не-событий («Бесплатные парковки» ×3, «На Каме появится новое пассажирское судно» с датой 2028-07-01, которую TTL не вычистит ещё почти два года);
- предикат с условием по времени (`parsed_at` старше 1 дня) даёт разный результат в разные моменты, то есть удалённое могло бы не совпасть с подтверждённым.
Правило «миграция = runtime-фильтр» сохраняется так: список A строится тем же предикатом, что и `_NON_EVENT_TITLE_RE`. Список B — разовая дочистка известных случаев, которые фильтр намеренно не ловит.

**Files:**
- Create: `supabase/migrations/20260918000001_remove_non_events_social.sql`

**Interfaces:**
- Consumes: итоговая `validator._NON_EVENT_TITLE_RE` из Task 3 (после всех сужений). SQL-версия обязана совпадать с ней по составу маркеров (`\s` → `[[:space:]]`).

- [ ] **Step 1: Проверить, что `lower()` в БД понимает кириллицу**

Через Supabase MCP `execute_sql`:
```sql
SELECT lower('РОЗЫГРЫШ Госдума Open Call') AS l;
```
Expected: `розыгрыш госдума open call`. Если кириллица осталась заглавной, в запросах ниже заменить `lower(title) ~` на `title ~*`.

- [ ] **Step 2: Список A — строки, которые ловит предикат постфильтра**

По всей БД, без ограничения по городу и типу:
```sql
SELECT id, city, type, source, title, date, parsed_at
FROM events
WHERE (source LIKE 'vk-%' OR source LIKE 'telegram-%' OR source LIKE 'generic:%' OR source = 'generic')
  AND lower(title) ~ '(розыгрыш|разыгрыва|промокод|специальное предложение|спецпредложение|голосовани|open[[:space:]-]?call|опен[[:space:]-]?колл|при[её]м заявок|госдум|законопроект|под арест|уголовн|по делу о|капитальный ремонт|путепровод|планируют открыть|отслеживани|телепроект)'
ORDER BY city, source, title;
```
Регулярка — копия итоговой `_NON_EVENT_TITLE_RE`. Если в Task 3 маркеры сужались, взять итоговый вариант.

- [ ] **Step 3: Список B — известные не-события вне предиката**

```sql
SELECT id, city, type, source, title, date, parsed_at
FROM events
WHERE city = 'perm'
  AND source LIKE 'vk-%'
  AND title IN ('Бесплатные парковки на время выборов', 'На Каме появится новое пассажирское судно')
ORDER BY title, date;
```

- [ ] **Step 4: Пользователь подтверждает объединённый список**

Показать пользователю A ∪ B целиком: id, город, тип, источник, заголовок, дата. Отдельно пометить строки не из Перми и не `type='other'`: они есть в выборке, потому что предикат не ограничен городом и типом. Пользователь вычёркивает лишнее и явно подтверждает список.
Если пользователь вычеркнул настоящее событие, пойманное предикатом A, это дефект постфильтра: вернуться в Task 3, сузить маркер, добавить заголовок в `REAL_EVENT_TITLES`, повторить Step 2.

- [ ] **Step 5: Файл миграции**

Создать `supabase/migrations/20260918000001_remove_non_events_social.sql`. `<ID_…>` заменить фактическими id из подтверждённого списка (каждый id с заголовком в комментарии):

```sql
-- Чистка накопленных не-событий (новости/объявления/промо/розыгрыши) от social-источников.
--
-- Контекст. На /perm около четверти карточек type='other' оказались не событиями: новости
-- городского паблика permactive («Пермь Активная»), розыгрыши, промокоды, голосования, open call.
-- VK-префильтр был всегда мягким (SOCIAL), batch-промпт требовал «вернуть ВСЕ события».
-- Приток перекрыт в коде: vk_source_types (permactive → aggregator), NON_EVENT_INSTRUCTIONS
-- в batch-промптах, постфильтр validator.is_non_event (guard в to_event_row).
--
-- Удаление по явному списку id, подтверждённому пользователем по dry-run 2026-09-18:
--   A — строки, которые ловит предикат validator._NON_EVENT_TITLE_RE (тот же набор маркеров);
--   B — разовая дочистка известных не-событий, которые постфильтр намеренно не ловит
--       (широкие маркеры «парковк»/«появится»): их приток закрывают префильтр и промпт.
DELETE FROM events
WHERE id IN (
  -- A: предикат постфильтра
  '<ID_A1>',  -- <title>
  -- ...
  -- B: дочистка вне предиката
  '<ID_B1>'   -- <title>
)
RETURNING id, title, source, city, type;

-- Проверка после применения: SELECT по этому же списку id должен вернуть 0 строк.
```

- [ ] **Step 6: Проверка ветки и коммит файла**

```bash
git branch --show-current
```
Ожидается `feat/non-event-filter`.
```bash
git add supabase/migrations/20260918000001_remove_non_events_social.sql
git commit -m "chore(db): миграция чистки накопленных не-событий social-источников

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
В боевой БД на этом шаге ничего не меняется: применение — Task 6, после мержа.

---

### Task 5: документация

**Files:**
- Modify: `README.md` (таблица фич после строки «Фильтр spurious `always`», ~стр. 124; список тестов ~стр. 209; описание `vk_posts` ~стр. 400)

- [ ] **Step 1: Строка в таблице фич** (сразу после строки «Фильтр spurious `always`»):

```markdown
| **Фильтр не-событий** | Новости городских пабликов, объявления служб, промо, розыгрыши, голосования и open call просачивались в `other` (~27% карточек `/perm/other` на 2026-09-18, в основном из `permactive`). Три слоя: (1) строгость VK-префильтра по группам `vk_source_types` (`permactive: aggregator`); (2) правило `NON_EVENT_INSTRUCTIONS` в batch-промптах; (3) постфильтр `is_non_event` по заголовку в `to_event_row` (счётчик `skipped_non_event` → `source_health`) — эвристический guard только по узким маркерам и только для social/generic, широкие случаи оставлены префильтру и промпту. Правило модели: open call / приём заявок, розыгрыши, голосования, промо — не события. Накопленное вычищено миграцией по подтверждённому списку id | `seeds.yaml`, `extraction/prompts.py`, `validator.is_non_event`, `pipeline._safe_to_event_row`, миграция `…_remove_non_events_social.sql` |
```

- [ ] **Step 2: Список тестов** (после строки `test_spurious_always.py`):

```markdown
│   │   ├── test_non_event.py       — vk_source_types/префильтр, промпт, is_non_event, guard, счётчик
```

- [ ] **Step 3: Описание `vk_posts`**: в строке ``- `vk_posts` — посты со стен `vk_groups`: префильтр (дата/маркеры/билеты) → …`` заменить `префильтр (дата/маркеры/билеты)` на `префильтр (дата/маркеры/билеты; строгость по группе — `vk_source_types`, по умолчанию social)`.

- [ ] **Step 4: Весь набор + коммит**

Run: `$PY -m pytest -q` → всё зелёное.
```bash
git branch --show-current
```
Ожидается `feat/non-event-filter`.
```bash
git add README.md
git commit -m "docs(readme): фильтр не-событий и vk_source_types

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: применение миграции к боевой БД (после мержа в master)

**Цель:** удалить накопленные не-события, когда приток уже перекрыт кодом в проде.
**Почему после мержа:** пока код не в master, крон продолжает собирать новые не-события старым кодом, и чистка до мержа неполная. Повторной вставки удалённого можно не опасаться: обработанные посты отмечены в `raw_documents` и повторно не извлекаются.
**Две сущности:**
- **базовый список** — id, подтверждённые пользователем в Task 4 до мержа (уже в файле миграции, повторно не пересматривается);
- **дельта** — только строки, появившиеся после dry-run Task 4 и до активации нового кода (первый прогон крона после мержа), то есть собранные ещё старым кодом.

**Критерий перехода:** после мержа нет новых не-событий, кроме явно выделенной дельты, возникшей до активации нового кода. Дельта отдельно подтверждена пользователем и добавлена в cleanup. RETURNING миграции = базовый список + дельта (за вычетом истёкших по TTL); удалённые id отсутствуют в БД; контрольные настоящие события на месте.

- [ ] **Step 1: Предусловие** — PR `feat/non-event-filter` смержен в master, прошёл хотя бы один прогон крона с новым кодом. Зафиксировать время его старта: это момент активации.

- [ ] **Step 2: Повторный dry-run и выделение дельты**

Повторить запросы Task 4 Step 2 и Step 3. Строки, которых нет в базовом списке, разложить по `parsed_at` относительно момента активации:
- `parsed_at` **до** активации → дельта (собрано старым кодом). Показать пользователю только дельту; базовый список повторно не подтверждается;
- `parsed_at` **после** активации → это не дельта, а дефект нового кода: не-событие прошло все три слоя. В cleanup не добавлять молча: показать пользователю и разобрать как находку по слоям (какой слой должен был поймать).
Строки базового списка, которых больше нет в БД (истекли по TTL), — ничего не делать: `DELETE … IN` их просто не найдёт.

- [ ] **Step 3: Добавить подтверждённую дельту в cleanup**

Если дельта непустая и подтверждена, дописать её id в файл миграции отдельным блоком `-- Дельта после мержа (parsed_at до <момент активации>)` отдельным коммитом в master. Перед коммитом проверить ветку через `git branch --show-current`. Миграция ещё не применена, поэтому правка файла безопасна.

- [ ] **Step 4: Применение — только после явного «да» пользователя**

Показать пользователю итоговый список id (базовый + дельта) и спросить подтверждение применения. После «да»: Supabase MCP `apply_migration` с именем `remove_non_events_social` и SQL из файла.

- [ ] **Step 5: Проверка**

1. RETURNING = базовый список + дельта (с поправкой на строки, истёкшие по TTL, из Step 2). Любое расхождение сообщить пользователю.
2. Удалённые записи отсутствуют:
   ```sql
   SELECT id, title FROM events WHERE id IN (<id из файла миграции>);
   ```
   Expected: 0 строк.
3. Контрольные настоящие события на месте — по конкретным id, а не по совпадению заголовка. Перед применением (Step 4) сохранить id строк:
   ```sql
   SELECT id, title FROM events
   WHERE city = 'perm' AND type = 'other' AND title ~* '(толкучк|каскад|ярмарк|цирк|благотворительная акция|музейный олимп)';
   ```
   После применения тот же SELECT по сохранённым id возвращает все строки. Исключение — строки, истёкшие по TTL; такие перечислить.
4. Batch-листинги не просели: сравнить `source_health.events_found` batch-источников (листинги/generic) за последний прогон до мержа и первый после. Резкое падение — сигнал, что правило промпта режет события в листингах; разобрать отдельно. Это закрывает риск для листингов, которых нет в наборе постов Task 2.

---

## Вне скоупа (отдельные задачи)

- Атрибуция: карточки «Бесплатные парковки» имеют `source_url=https://vk.com/prmgo`, хотя текст со стены permactive (`wall-30210603_3352007`).
- `event_url` розыгрыша двери взят из тела поста (`vk.ru/flydoors_perm`) вопреки промпту.
- Регулярка постфильтра заточена под наблюдённые случаи. Новые виды шума отслеживать через `source_health` («Отброшено не-событий: N») и выборку `type='other'`.
