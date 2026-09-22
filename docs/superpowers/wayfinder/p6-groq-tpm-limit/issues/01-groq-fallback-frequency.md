# Groq TPM-лимит: как часто и насколько дорого фолбэк на Gemini

Type: research
Скилл: `mattpocock-skills:research` — нужны цифры из логов/`source_health`, прежде чем решать, стоит ли что-то менять
Status: open
Blocked by: —
Ветка: `research/groq-tpm-fallback-frequency`

## Question

После миграции Groq → `openai/gpt-oss-120b` batch-вызовы на free-tier почти всегда упираются в лимит 8K TPM и уходят в фолбэк на Gemini (`README.md:127`). Это описано в README как ожидаемое поведение («на free-tier batch-вызов почти всегда упирается»), но неизвестно: насколько «почти всегда» — 50% вызовов или 95%; сколько дополнительной нагрузки на дневную квоту Gemini это создаёт; есть ли уже случаи `is_daily_quota_exhausted` на Gemini, вызванные именно этим оттоком.

## Контекст

- `README.md:127` — описание миграции и причины упора в TPM.
- `parser/src/parser/extraction/groq_extractor.py`, `extraction/_errors.py` (`is_rate_limit`, `is_daily_quota_exhausted`).
- `extraction/fallback.py` (`FallbackExtractor`) — цепочка провайдеров, `LLM_FALLBACK_PROVIDERS` (дефолт `gemini,groq`).
- `db.py` (`record_source_health`) — таблица `source_health`, куда пишутся ошибки/успешность по источнику.

## Цифры

```sql
-- SQL: не прогнан
select date_trunc('day', created_at) as day, count(*) as rate_limit_fallbacks
from source_health
where provider = 'groq' and error ilike '%rate%'
group by 1 order by 1 desc limit 30;
```

```
# команда: не прогнана
python -m parser.cli run --city perm --dry-run --provider groq
# посмотреть в stdout, сколько батчей ушло в фолбэк за один прогон
```

`SQL/команда: прогнаны <дата>` — ставит сессия, которая их реально выполнила.

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| `source_health` | Лог ошибок/успешности по источнику | Нет, читается как источник цифр |
| Дневная квота Gemini (20 запросов/сутки/модель) | Общий бюджет LLM-извлечения | Нет в этом тикете — только измеряется нагрузка на неё |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| `parser/tests/test_fallback.py` | Проверяет механику фолбэка — не про частоту в проде |

## Готово когда

- Есть цифра: доля/количество batch-вызовов Groq, ушедших в фолбэк на Gemini, за последние 30 дней.
- Понятно, были ли случаи исчерпания дневной квоты Gemini, которые можно связать с этим оттоком.
- Результат — отчёт с цифрами, не решение (решение — следующий тикет).

## Answer

<Заполняется в конце сессии.>

Локализация: `<команда>`, найдено N мест
Расхождения цифр: <или «нет»>
