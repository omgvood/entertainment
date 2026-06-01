# Парсер событий

Двухуровневый пайплайн: **discovery (код)** + **extraction (LLM)** → Postgres.

```
[seeds.yaml] → discovery → URL-кандидаты → dedup vs DB → LLM-extract → validate → upsert
```

## Установка локально

```bash
cd parser
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux

pip install -e ".[dev]"
cp .env.example .env            # на Windows: copy .env.example .env
# отредактируй .env, подставь ключи
```

`pip install -e .` ставит пакет `parser` в editable-режиме — дальше `python -m parser.cli ...` работает из любой папки без `PYTHONPATH`.

Нужны ключи:
- **LLM-провайдер** — на выбор:
  - `GEMINI_API_KEY` — [aistudio.google.com](https://aistudio.google.com) → Get API key. Free tier: лимит 20 req/день на Flash/Flash-Lite (production OK для daily cron).
  - `GROQ_API_KEY` — [console.groq.com](https://console.groq.com) → API keys. Free tier: ~1000 req/день на Llama 3.3 70B.
  - Переключение между провайдерами: `LLM_PROVIDER=gemini|groq` в `.env` либо разово через `--provider` в CLI.
- **SUPABASE_SERVICE_ROLE_KEY** — Supabase dashboard → Project Settings → Data API → `service_role` → Reveal. **Этот ключ обходит RLS, никогда не коммитить.**

## Использование

### Дискавери без LLM (проверить seed-конфиг)

```bash
python -m parser.cli discover --city perm
python -m parser.cli discover --city perm --source quizplease
```

Выведет список URL, которые нашёл краулер. Если 0 — значит `url_pattern` в `config/seeds.yaml` не подходит. Открой источник в браузере, посмотри реальные URL событий, поправь regex.

### Полный прогон с LLM, но без записи в БД

```bash
python -m parser.cli run --city perm --source quizplease --dry-run

# Сравнить с Groq:
python -m parser.cli run --city perm --source quizplease --dry-run --provider groq
```

Каждое событие будет извлечено через LLM. В БД ничего не пишется.

### Боевой прогон

```bash
python -m parser.cli run --city perm
```

Дедуп по `source_url`: события, уже лежащие в БД, не перевызываются.

## Как добавить новый источник

1. Открой `config/seeds.yaml`.
2. Добавь блок под нужным городом:
   ```yaml
   - name: my-source
     kind: listing        # или sitemap
     url: https://example.com/events
     url_pattern: "/event/\\d+"
   ```
3. Проверь дискавери: `python -m parser.cli discover --city perm --source my-source`
4. Если URL находятся — запусти `--dry-run`, посмотри что LLM извлекает.
5. Запусти боевой прогон.

## Архитектура

```
parser/
  src/parser/
    config.py          — env + seeds
    models.py          — Pydantic ParsedEvent / EventRow
    discovery/         — base + listing + sitemap (расширяется)
    extraction/        — base + Gemini + Groq (LLM-провайдеры)
    validator.py       — slug-генератор + ParsedEvent → EventRow
    dedup.py           — фильтр уже-существующих URL
    db.py              — Supabase upsert
    pipeline.py        — оркестратор
    cli.py             — точка входа
  config/seeds.yaml    — список источников
  tests/               — smoke-тесты без сети
```

## CI

`.github/workflows/parse.yml` запускает `parser run --city perm` ежедневно в 21:00 UTC (00:00 МСК).

В Settings → Secrets and variables → Actions добавь:
- `GEMINI_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- (опционально) `TG_BOT_TOKEN`, `TG_CHAT_ID` — для алертов в Telegram при падении
