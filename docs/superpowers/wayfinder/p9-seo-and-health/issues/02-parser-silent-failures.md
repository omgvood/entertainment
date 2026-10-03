# Сбои источников молчат: Timepad 403 три недели, 2ГИС и Telegram без причины

Type: task
Скилл: `superpowers:systematic-debugging` → `superpowers:test-driven-development` — причина `last_error = null` при `errors > 0` фиксируется тестом в `test_pipeline_warnings.py` первым
Status: open
Blocked by: —
Ветка: `fix/parser-silent-failures`
Шаги пользователя: ждут

## Question

Аудит 2026-09-24, п. 4.1. Парсер больше половины источников прогоняет вслепую:

1. **Timepad** (приоритет 100) отвечает 403 в обоих городах каждый день. Алерт шлётся ежедневно, и его перестали читать.
2. **`twogis-*`** в событийном пайплайне падают каждый день в обоих городах. Площадки и так собирает `refresh_venues.yml`.
3. **Причина сбоя теряется.** В `sub.warnings`, а значит в Telegram и в `source_health.last_error`, попадают только HTTP 400/401/403 у `direct_api`. Остальные ветки — конфиг-ошибки, 5xx, каналы Telegram, группы VK, LLM-экстракция — только увеличивают `failed`. Поэтому у `twogis-*`, `telegram-posts`, `vk-posts`, `generic` в `source_health` стоит `errors > 0` при `last_error = null`.

## Контекст

- Единственное место, где ошибка попадает в warnings: `parser/src/parser/pipeline.py:513`. Ветки только с `sub.failed += 1` (греп 2026-09-29): `:472, :475, :546, :653, :699, :738, :774, :814, :854, :890, :1022`.
- `last_error` берётся из `sub.warnings[0]`: `pipeline.py:299-311` → `db.py:340-352` (`record_source_health`).
- Отправка в Telegram: `.github/workflows/parse.yml:66-83` → `scripts/notify_warnings.py`.
- `twogis-*` в событийном пайплайне: `parser/config/seeds.yaml:35-49` (Сочи, 3 источника), `:129-167` (Пермь, 6 источников).
- Timepad 403 — протухший токен в GitHub Secrets, не IP-блок: диагностика в памяти проекта `timepad-source` (вне git, `~/.claude/projects/.../memory/`).
- Смежное: p6/01 (частота фолбэка Groq) упрётся в тот же пробел — причины LLM-сбоев в `source_health` нет.

## Шаги пользователя

| Шаг | Где | Статус |
|---|---|---|
| Продлить токен Timepad и обновить секрет (не горит, решение 2026-09-29) | timepad.ru → кабинет организатора → API; GitHub → Settings → Secrets and variables → Actions | ждёт |

## Цифры

На 2026-09-29, окно 2026-09-24…27: Timepad — `events_found = 0`, `last_error = 'timepad: HTTP 403 — проверь токен/ключ API'` каждый день в обоих городах (с 2026-09-07, около 21 дня). 27.09 ошибки у 11 из 15 источников Перми, у 4 из 8 в Сочи.

```sql
-- SQL: прогнан 2026-09-29
select (run_at at time zone 'UTC')::date d, city, count(*) n,
       count(*) filter (where errors>0) with_err,
       string_agg(case when errors>0 then source end, ',') err_src
from source_health where run_at > now() - interval '4 days'
group by 1,2 order by 1 desc,2;
```

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| `parser/src/parser/pipeline.py` (ветки `sub.failed += 1`) | считает сбой без причины | да — причина в `warnings` |
| `pipeline.py:299-311` | `last_error` из первого warning | возможно |
| `scripts/notify_warnings.py`, `parse.yml:66-83` | шлёт warnings в Telegram | да — один дайджест на прогон |
| `parser/config/seeds.yaml` | `twogis-*` в событийном пайплайне | да — выключить |
| `source_health` (таблица) | история прогонов | нет, читается для проверки |
| GitHub Secrets (токен Timepad) | авторизация | да — пользователь |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| `parser/tests/test_pipeline_warnings.py` | держит текущее правило «в warnings только 400/401/403» — проверить по значению `403`, `warnings` |

## Готово когда

- После ближайшего прогона в `source_health` у каждой строки с `errors > 0` непустой `last_error`.
- `twogis-*` отсутствуют в `source_health` событийного прогона; `refresh_venues.yml` не тронут.
- Timepad: `events_found > 0` хотя бы в Перми в прогоне после продления токена (шаг пользователя; пока он `ждёт`, критерий не блокирует закрытие остальных пунктов — переносится строкой в «Отложено» `_next-session.md`).
- Telegram получает одно сообщение на прогон вместо отдельных.
- `cd parser && python -m pytest -q` зелёный.
- Выполнено обновление файла map.md

## Answer

2026-09-29, ветка `fix/parser-silent-failures`. Кодовая часть сделана; тикет остаётся `open` до проверки на проде (ближайший прогон после мерджа) и до решения по Timepad.

Локализация: `grep -n "failed = 1\|failed += \|failed=" parser/src/parser/pipeline.py` + `grep -rn "warnings\|last_error" parser/src parser/scripts parser/tests` + по значению `grep -rn "400/401/403"`, найдено 27 мест (20 веток сбоя в `pipeline.py`, 5 возвратов сбоя в `sources/generic.py`, `notify_warnings.py`, 1 абзац `README.md`).
Расхождения цифр: да —
- тикет назвал 11 веток `sub.failed += 1`, ещё 9 с `sub.failed = 1` (`:504, :516, :520, :527, :627, :637, :682, :977, :981`) пропущены;
- `sources/generic.py` сам пишет строки `generic:<домен>` в `source_health` без `last_error` — в «Кто зависит» не было;
- `last_error = "Отброшено spurious 'always'"` при `errors > 0` (vk-posts 26.09) — пропуск маскировал сбой;
- путь `scripts/notify_warnings.py` не существует, файл — `parser/scripts/notify_warnings.py`;
- **2ГИС** падает не «без причины»: лог GHA 27.09 — `meta.code=403 Authorization error, incorrect key` при HTTP 200, `TWOGIS_API_KEY` невалиден. Значит, и API-ветка `refresh-venues` не работает (предположение: спасает фолбэк Playwright при `source=auto`, не проверялось);
- **Timepad**: тело 403 в CI — HTML-челлендж Cloudflare («Just a moment...»), а не JSON-ответ API. Гипотеза: блок по IP раннера, новый токен может не помочь — противоречит памяти `timepad-source`. Проверка пользователем 2026-09-29 (`curl` без токена с домашнего IP): `403 application/json`, `"Запрос требует указание токена"` — API отвечает JSON, челленджа нет. Челлендж только у раннера GitHub → блок по IP вероятнее протухшего токена; окончательно проверит прогон с новым токеном.

Что сделано:
- `pipeline._record_failure(sub, source, reason, exc)` — единая точка сбоя: `failed += 1` + причина `"<источник>: <что>: <тип>: <текст>"[:200]`; заменены все 20 веток. Текст для HTTP 400/401/403 прежний.
- `run_city`: несколько сбоев одного источника → одна строка «первый (+N)»: и `last_error`, и Telegram.
- `generic.py`: `_run_domain`/`run_generic` возвращают причины вместо счётчика; `last_error` у `generic:<домен>` и у агрегата `generic`.
- `seeds.yaml`: 9 источников `twogis-*` → `enabled: false`; `refresh-venues` их по-прежнему берёт (`_twogis_venue_sources` не смотрит на `enabled`), `refresh_venues.yml` не тронут.
- `notify_warnings.py`: бэктик в тексте исключения заменяется на `'` — иначе Telegram Markdown отвечает 400 и алерт теряется.
- Дайджест: решение пользователя — чтение B, «одно сообщение на город», уже так и было; правок не потребовало.
- Тесты: +5 (`test_pipeline_warnings.py` ×3, `test_generic.py`, `test_config.py`), `cd parser && python -m pytest -q` → 303 passed.

Не сделано / вне тикета: `batch.fetch.failed` и `discovery.failed` не увеличивают `failed` вовсе — сбой там невидим даже как `errors > 0`.

- **Проверено на проде 2026-10-03 (частично):** по `source_health` за 4 прогона (30.09–03.10) нет строк `errors > 0` с `last_error is null` и нет строк `twogis-*` (0 из 14 источников в сутки). **Не проверено:** сообщение в Telegram (одно на город, разметка) — в логе `parse.yml` от 01.10 в шаге уведомления `TG_BOT_TOKEN`/`TG_CHAT_ID` пустые, а не `***` (гипотеза: секреты не заданы). Тикет `open` из-за Timepad и этого пункта.
