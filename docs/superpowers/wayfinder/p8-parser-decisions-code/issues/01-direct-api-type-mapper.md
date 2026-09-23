# direct_api: маппер типов врёт — permopera всегда concert, permm/`_EVENTS_URL` всегда exhibition

Type: task
Скилл: `mattpocock-skills:tdd` — старое поведение (`event_type` константой на весь источник) фиксируется тестом `test_permopera.py`/`test_permm.py` первым, до правки маппера
Status: resolved
Blocked by: —
Ветка: `fix/direct-api-type-mapper`

## Question

Решение «Точность типов у direct_api» принято 2026-09-22 (карта p2, тикет 12) и закончилось выводом «чинить маппер... у двух источников», но тикет на код не был заведён. На `master` 2026-09-22 `permopera` по-прежнему отдаёт `event_type: concert` для всех событий источника (константа в `seeds.yaml`), `permm` по-прежнему отдаёт `event_type: exhibition` и для `_EXHIBITIONS_URL`, и для `_EVENTS_URL`.

## Контекст

- Решение: `docs/superpowers/wayfinder/p2-data-fixes/issues/12-direct-api-type-accuracy.md`, `## Answer`. Сверка с сайтами (снимок 2026-09-22): `permopera` — де-факто 9/9 (100%) событий в выборке не концерты (опера/экскурсия/другое, жанр виден на странице карточки); `permm` — 2/2 проверенных из фида `_EVENTS_URL` не выставки, доля по выборке ~22% (2/9), концентрируется именно в этом фиде, а не во всём мапере.
- `timepad` и `quizplease` решением явно исключены из правки — не трогать.
- Механизм по коду (p2/12, подтверждено повторным грепом 2026-09-22): `permopera.py:34-48` и `permm.py:34-48` берут `type=event_type` из аргумента `search()`, который приходит одной константой из `parser/config/seeds.yaml` (`event_type: concert` для `permopera`, `event_type: exhibition` для `permm` — обе ветки `seeds.yaml`, строки с `event_type: concert`/`event_type: exhibition` см. блок JSON-LD дефолтов, `seeds.yaml:266-284`), и присваивается всем событиям источника без разбора содержимого.
- `permm.py:26-27`: `_EXHIBITIONS_URL = f"{_BASE}/json/exhibitions/active"`, `_EVENTS_URL = f"{_BASE}/json/events/sub/home"` — второй эндпоинт по докстрингу сам заявляет смесь «экскурсии, лекции, фестивали», но в `search()` (permm.py:34-48) получает тот же `event_type`, что и первый.
- Не проверено решением p2/12 (осталось на код-тикет): жанр в сыром HTML-фрагменте `permopera` (`/playbills/playbill`, откуда парсит `parse_cards`) — если жанр там есть, можно детектировать per-event; если нет, p2/12 предложил эвристику по заголовку (`Цикл экскурсий`/`Экскурсия` → `trip`, остальное → `theater`, не `concert`, так как это оперные/балетные постановки).
- Тип напрямую кормит авто-теги (`TYPE_DEFAULT_TAGS`, тикет 02 этой карты) и группы типов UI (`p7-ui-ux-pass/issues/05-type-groups-code.md`) — правка этого тикета снижает шум в обоих.

## Цифры

На 2026-09-22 (снимок p2/12): `permopera` 9 будущих событий, все `concert`; `permm` 9 будущих событий, все `exhibition` (из них ошибочны 2/9 из фида `_EVENTS_URL`). Перед правкой пересчитать и разбить `permm` по фиду (`_EXHIBITIONS_URL` vs `_EVENTS_URL`), в снимке p2/12 разбивка по фиду не считалась отдельно.

```sql
-- SQL: не прогнан
select source, type, count(*) from events
where city = 'perm' and source in ('permopera', 'permm')
  and date >= to_char(current_date, 'YYYY-MM-DD')
group by 1, 2 order by 1, 2;
```

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| `parser/src/parser/sources/permopera.py` | берёт `type=event_type` из аргумента `search()` | да — per-event эвристика или детект жанра |
| `parser/src/parser/sources/permm.py:34-48` | `search()` не различает `_EXHIBITIONS_URL`/`_EVENTS_URL` при простановке типа | да — развести дефолт по эндпоинту |
| `parser/config/seeds.yaml` | константа `event_type` на весь источник | проверить — возможно, остаётся дефолтом для `_EXHIBITIONS_URL`, но не для `_EVENTS_URL` |
| `parser/src/parser/taxonomy.py` (`TYPE_DEFAULT_TAGS`) | получает более точный `type` на входе | нет, за пределами тикета |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| `parser/tests/test_permopera.py` | проверить фикстуры на `event_type == "concert"` как ожидаемое значение — переписать под новую логику |
| `parser/tests/test_permm.py` | проверить фикстуры на `event_type == "exhibition"` для событий из `_EVENTS_URL` — переписать |

## Готово когда

- `permopera`: события с жанром «экскурсия» получают `trip` (или ближайший подходящий тип из `EventType`), не `concert`; остальное — `theater`, не `concert`.
- `permm`: события из `_EVENTS_URL` получают тип, отличный от `exhibition` (дефолт `other` или per-title эвристика для лекций/экскурсий); события из `_EXHIBITIONS_URL` не меняются.
- `timepad`, `quizplease` не тронуты.
- `pytest parser/tests/test_permopera.py parser/tests/test_permm.py` зелёные с новыми фикстурами.
- Выполнено обновление файла map.md

## Answer

**permopera — тип по метке из карточки, а не эвристика по заголовку.** В карточке есть блок «Авторы, Тип события, Возраст» (`h3[data-element="event-name"] + div p`), так что тип определяется для каждого события отдельно, как тикет и предусматривал на случай «жанр в HTML есть». Карта меток: Опера/Балет → `theater`, Концерт → `concert`, Экскурсия → `trip`, «Другие события» → `other`. Метки нет или она незнакома (на живой афише 2026-09-23 встретилась «Дрейф») → `event_type` из `seeds.yaml`, фолбэк переведён `concert` → `theater`.

Критерий «остальное → `theater`, не `concert`» в «Готово когда» опирался на снимок p2/12 (9 из 9 — не концерты). На 2026-09-23 это уже неверно: на живой афише 4 метки «Концерт» из 15, в БД 2 из 10 будущих (оба «Шостакович 120») — правило «всё остальное → theater» переписало бы их неверно. Отклонение от критерия согласовано с пользователем в сессии, решение p2/12 («чинить маппер») данными не опровергнуто.

**permm — фид `_EVENTS_URL`: «Выставка…» → `exhibition`, остальное → `other`.** Развилка «A или B» из «Готово когда» решена пользователем в пользу минимальной эвристики. Весь фид → `other` (вариант A) испортил бы 3 из 5 событий фида в БД: это «Выставка «…»», то есть настоящие выставки. Фид `_EXHIBITIONS_URL` не тронут. `_map_item` получил флаг `from_events_feed`, `search()` передаёт его для второго фида.

Живой прогон клиентов 2026-09-23 (без записи в БД): permopera — concert 2, theater 3, trip 3, other 1; permm — 4 события фида событий стали `other` («Спектакль «Альбатрос»», лекция, арт-медиация и др.), «Выставка «…»» остались `exhibition`. `timepad`, `quizplease` не тронуты.

**Перепарсинг не нужен отдельно:** `upsert` идёт по `slug` (заголовок + дата, без типа) — следующий ежедневный прогон перезапишет `type` у существующих строк.

Тесты: `test_permopera.py` — метка → тип (4 кейса на снимке живой афиши `fixtures/permopera_playbill_genres.json`), фолбэк на незнакомую метку, старое `type == "concert"` переписано на `theater` (карточка с меткой «Опера»); `test_permm.py` — 3 кейса правила фида событий на заголовках из БД. `pytest` — 296 passed. Провязка флага в `search()` покрыта только живым прогоном, не юнит-тестом (нужна сеть).

Вне scope, найдено по ходу: `permm` отдаёт одну выставку дважды — из `/exhibition/<slug>` и `/events/vystavka-<slug>` под разными заголовками («Звучит Увертюра» / «Выставка «Звучит увертюра»»), в БД 3 такие пары. `title_score` у них не 1.0, фикс тикета 03 их не склеит.

Локализация: `grep -rn "permopera\|permm" config/seeds.yaml src tests` + `grep -rn "event_type" src/parser` + греп по значениям `"concert"`/`"exhibition"` в `tests/`, найдено 12 мест (`permopera.py`, `permm.py`, `seeds.yaml`, `pipeline.py:604-611`, `test_permopera.py`, `test_permm.py`, `test_non_event.py:199`, `test_config.py:16`, `test_fuzzy.py:269`, 3 фикстуры) — менялись 4 + новая фикстура.
Расхождения цифр: да — permopera в БД 10 будущих (в тикете 9), из них 2 настоящих концерта (в тикете 0); permm 9 (совпадает), разбивка по фиду: 4 из `_EXHIBITIONS_URL`, 5 из `_EVENTS_URL`, из них 2 не выставки (совпадает с 2/9 тикета).
