# Сбои источников молчат: Timepad 403 три недели, 2ГИС и Telegram без причины

Type: task
Скилл: `superpowers:systematic-debugging` → `superpowers:test-driven-development` — причина `last_error = null` при `errors > 0` фиксируется тестом в `test_pipeline_warnings.py` первым
Status: open
Blocked by: —
Ветка: `fix/parser-silent-failures`

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
- Timepad 403 — протухший токен в GitHub Secrets, не IP-блок: диагностика в памяти проекта `timepad-source` (вне git, `~/.claude/projects/.../memory/`). Токен продлевает пользователь.
- Смежное: p6/01 (частота фолбэка Groq) упрётся в тот же пробел — причины LLM-сбоев в `source_health` нет.

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
- Timepad: `events_found > 0` хотя бы в Перми в прогоне после продления токена.
- Telegram получает одно сообщение на прогон вместо отдельных.
- `cd parser && python -m pytest -q` зелёный.
- Выполнено обновление файла map.md

## Answer

<Заполняется в конце сессии.>

Локализация: `<команда>`, найдено N мест
Расхождения цифр: <или «нет»>
