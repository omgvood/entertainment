# Дубли: не занижать score при точном совпадении названия

Type: task
Скилл: `mattpocock-skills:tdd` — регресс-кейс «Балетный квартал» обязателен как тест, чтобы правка `score_pair` его не задела
Status: open
Blocked by: —
Ветка: `fix/dedup-title-score`

## Question

Решение «Дубли, которые серия не склеивает» принято 2026-09-22 (карта p2, тикет 14): в `fuzzy.py::score_pair` не применять `_venue_factor`, когда `title_score == 1.0`. Тикет на код не заведён, `fuzzy.py` не тронут.

## Контекст

- Решение: `docs/superpowers/wayfinder/p2-data-fixes/issues/14-unmerged-duplicates.md`, `## Answer`. Ключевой факт: 19 пар `dedup_candidates` со статусом `candidate` делятся на три группы по `title_score` — 6 пар с ровно `1.000` (настоящие дубли, площадка названа по-разному между источниками), 8 пар «Балетный квартал» (0.754–0.842, ложные срабатывания — разные экскурсии одной серии), 5 прочих настоящих дублей (0.771–0.833, диапазон пересекается с «Балетным кварталом» — порог поднимать нельзя).
- Фикс закрывает только первую группу (6/19): не применять `_venue_factor` при `title_score == 1.0`, не поднимать общий порог — иначе заденет «Балетный квартал» (его `title_score` физически не превышает 0.842).
- Локализация p2/14: скорер `parser/src/parser/fuzzy.py`, пороги `parser/src/parser/config.py:36-40` (`DEDUP_MERGE_SCORE=0.95`, `DEDUP_CANDIDATE_SCORE=0.75`), запись в БД `parser/src/parser/db.py:440-474`. Повторный грep 2026-09-22 подтвердил `fuzzy.py::score_pair` (строка объявления ~153) и `_venue_factor` (~140).
- Явно решено НЕ делать (см. `Out of scope` карты этого эффорта): разрешатель кандидатов для оставшихся 13 пар — score-порогом их не различить, дороже пользы для ~5 реальных дублей в снапшоте; накопленные 19 пар руками не трогать — `dedup_candidates` пересчитывается каждым прогоном (TTL 1 день, `cleanup_old_dedup_candidates`), фикс сам переклассифицирует нужные пары на следующем прогоне.
- Тест `test_fuzzy.py` существует (`parser/tests/test_fuzzy.py`) — новый кейс должен покрыть все три группы, включая «Балетный квартал» как регресс.

## Цифры

На 2026-09-22 (снимок p2/14): 19 пар `decision='candidate'`, средний score 0.812, против 70 `auto_merge`. Проверить, что 6 пар с `title_score == 1.000` по-прежнему актуальны — таблица пересчитывается ежедневно.

```sql
-- SQL: не прогнан (Supabase MCP, read-only)
select id, title_score, venue_score, score, decision
from dedup_candidates
where decision = 'candidate'
order by title_score desc;
```

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| `parser/src/parser/fuzzy.py::score_pair` | применяет `_venue_factor` ко всем парам | да — пропускать при `title_score == 1.0` |
| `parser/tests/test_fuzzy.py` | тесты скорера | да — добавить кейсы на три группы |
| `parser/src/parser/config.py:36-40` | пороги `DEDUP_MERGE_SCORE`/`DEDUP_CANDIDATE_SCORE` | нет, по решению не трогать |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| `parser/tests/test_fuzzy.py` | текущие кейсы `score_pair` — проверить, есть ли уже кейс с `title_score == 1.0` и разными venue |

## Готово когда

- `score_pair`: при `title_score == 1.0` итоговый score не занижается `_venue_factor`.
- Тест на «Балетный квартал» (или эквивалентная фикстура: высокий `title_score` < 1.0, `venue_score` совпадает) остаётся в диапазоне `candidate`, не переходит в `auto_merge`.
- Тест на пару с `title_score == 1.0` и разными формулировками площадки переходит в `auto_merge`.
- `pytest parser/tests/test_fuzzy.py` зелёный.
- Выполнено обновление файла map.md

## Answer

<Заполняется в конце сессии.>

Локализация: `<команда>`, найдено N мест
Расхождения цифр: <или «нет»>
