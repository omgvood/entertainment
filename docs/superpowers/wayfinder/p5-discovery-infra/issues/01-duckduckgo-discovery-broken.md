# DuckDuckGo Discovery сломан (202-ответы)

Type: task
Скилл: `systematic-debugging` → `test-driven-development` → фикс → `verification-before-completion` — причина уже известна (202-ответы вместо результатов поиска), это доводка, а не разведка
Status: open
Blocked by: —
Ветка: `fix/duckduckgo-discovery-202`

## Question

Провайдер DuckDuckGo в Discovery (`SEARCH_PROVIDERS`) возвращает 202 вместо результатов поиска — по факту не работает, `candidate_sources` сейчас наполняется вручную через WebSearch + Supabase MCP в обход автоматического Discovery. Нужно понять, чинится ли 202 (retry/заголовки/эндпоинт) или провайдера стоит отключить/заменить, и довести до рабочего состояния или до явного решения не чинить.

## Контекст

- `parser/src/parser/discovery/` — краулеры Discovery (`listing.py`, `sitemap.py`).
- `config.py` — `SEARCH_PROVIDERS` (дефолт `serper`), `SERPER_API_KEY`/`BRAVE_API_KEY` для keyed-провайдеров; DuckDuckGo — безключевой, видимо через HTML/lite-эндпоинт.
- `discover-sources` (CLI): по README (`cli.py`) выходит с кодом 1, если все keyed-провайдеры отключились по авторизации — нужно проверить, как ведёт себя при сломанном DuckDuckGo в цепочке.
- Ручной обходной путь сейчас: `candidate_sources` наполняется через WebSearch + Supabase MCP (зафиксировано в памяти сессий, не в коде).

## Цифры

```sql
-- SQL: не прогнан
select provider, count(*) from candidate_sources
where created_at > now() - interval '30 days'
group by provider;
```

`SQL: прогнан <дата>` — ставит сессия, которая реально выполнила запрос: показывает, находит ли DuckDuckGo вообще что-то за последний месяц.

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| `parser/src/parser/discovery/` (провайдер-клиент DuckDuckGo) | Делает HTTP-запрос к DuckDuckGo | Да — фикс или удаление |
| `discovery-health` (CLI) | Считает новых кандидатов за окно, exit 1 при нуле | Нет, но должен показать эффект фикса |
| `parser/tests/test_candidate_sources.py` | Тестирует поисковые провайдеры, circuit breaker | Возможно — если провайдер меняется или удаляется |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| `parser/tests/test_candidate_sources.py` | Искать по значению `duckduckgo` — может фиксировать текущее (сломанное) поведение как ожидаемое |

## Готово когда

- Либо DuckDuckGo снова возвращает результаты (`discovery-health` видит кандидатов от него), либо провайдер явно убран из `SEARCH_PROVIDERS`/кода с объяснением, почему чинить не стоит.
- Ручной обходной путь (WebSearch + Supabase MCP) либо остаётся документированным запасным вариантом, либо перестаёт быть нужен.

## Answer

<Заполняется в конце сессии.>

Локализация: `<команда>`, найдено N мест
Расхождения цифр: <или «нет»>
