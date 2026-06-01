# Парсер событий

Двухуровневый пайплайн: **discovery (код)** + **extraction (LLM)** → Postgres.

```
seeds.yaml
    │
    ▼
Discovery ──── listing-краулер (QuizPlease)
               sitemap-краулер (будущие источники)
               2ГИС API (боулинг / бильярд / картинг)
    │
    ▼ список URL / JSON-объектов
Dedup ────────── сравнение с source_url уже в БД → пропустить известные
    │
    ▼ только новые
LLM Extraction ─ Gemini 2.5 Flash-Lite / Groq Llama-3.3 70B
                 один промпт → структурированный ParsedEvent (Pydantic)
    │
    ▼
Validator ─────── slug, дата, цена ≥ 0, обязательные поля
    │
    ▼
Supabase upsert ─ on_conflict="slug" → новые вставляются, старые обновляются
    │
    ▼
Cleanup ──────── DELETE events WHERE date < today-7days AND date != 'always'
```

Режим `direct_api` (2ГИС) не использует LLM — JSON из API маппится напрямую.

---

## Быстрый старт (локально)

```bash
cd parser
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux

pip install -e ".[dev]"
cp .env.example .env
# Отредактируй .env — подставь ключи
```

`pip install -e .` устанавливает пакет `parser` в editable-режиме — `python -m parser.cli ...` работает из любой папки.

### Нужные ключи

| Переменная | Где взять | Зачем |
|---|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API key | LLM-извлечение (free tier: ~1500 req/день на Flash-Lite) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) → API Keys | Альтернативный LLM (free tier: ~1000 req/день) |
| `TWOGIS_API_KEY` | [partner.api.2gis.com](https://partner.api.2gis.com) | Места «всегда» (боулинг/бильярд/картинг) |
| `SUPABASE_URL` | Supabase → Settings → API → Project URL | Адрес БД |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → service_role | Запись в БД (обходит RLS, **не коммитить**) |

Переключение LLM-провайдера: `LLM_PROVIDER=gemini` или `LLM_PROVIDER=groq` в `.env`, либо разово через `--provider`.

---

## Команды CLI

### Только дискавери (без LLM, без записи)

Проверить, что краулер находит нужные URL:

```bash
python -m parser.cli discover --city perm
python -m parser.cli discover --city sochi --source quizplease
```

Если результат пустой — открой источник в браузере, посмотри реальные URL событий, поправь `url_pattern` в `config/seeds.yaml`.

### Сухой прогон (LLM работает, в БД не пишет)

```bash
python -m parser.cli run --city perm --dry-run
python -m parser.cli run --city perm --source quizplease --dry-run

# Сравнить провайдеры:
python -m parser.cli run --city perm --dry-run --provider groq
```

### Боевой прогон

```bash
python -m parser.cli run --city perm
python -m parser.cli run --city sochi
```

---

## Города и источники (`config/seeds.yaml`)

Текущая конфигурация:

| Город | Источник | Режим | Описание |
|---|---|---|---|
| perm | quizplease | batch_listing | QuizPlease Пермь — один LLM-вызов на всё расписание |
| perm | twogis-bowling | direct_api | Боулинг-клубы Перми из 2ГИС |
| perm | twogis-billiards | direct_api | Бильярдные Перми из 2ГИС |
| perm | twogis-karting | direct_api | Картинг-центры Перми из 2ГИС |
| sochi | quizplease | batch_listing | QuizPlease Сочи |
| sochi | twogis-bowling | direct_api | Боулинг Сочи |
| sochi | twogis-billiards | direct_api | Бильярд Сочи |
| sochi | twogis-karting | direct_api | Картинг Сочи |

### Режимы извлечения

- **batch_listing** — скачиваем страницу целиком, один LLM-вызов извлекает все события сразу. Используется для QuizPlease.
- **direct_api** — вызываем внешнее API (2ГИС), маппим JSON → `ParsedEvent` без LLM.
- **per_url** — дискавери находит N URL → N отдельных LLM-вызовов. Для источников с детальными страницами событий.

### Добавить новый источник

1. Открой `config/seeds.yaml`, добавь блок:

```yaml
- name: my-source
  kind: listing          # или sitemap
  url: https://example.com/events
  url_pattern: "/event/\\d+"
  extraction_mode: batch_listing  # или per_url
```

2. Проверь дискавери: `python -m parser.cli discover --city perm --source my-source`
3. Если URL находятся — `--dry-run`, посмотри что LLM извлекает
4. Боевой прогон: `python -m parser.cli run --city perm --source my-source`

---

## Логика очистки данных

После каждого прогона автоматически:

- **Удаляются** события с `date < сегодня - 7 дней` (прошедшие мероприятия)
- **Остаются** события с `date = 'always'` (боулинг, бильярд, картинг — работают ежедневно)
- **Остаются** будущие и недавно прошедшие (до 7 дней) — для буфера

На уровне фронтенда пользователю показываются только события с `date >= сегодня` или `date = 'always'`.

---

## Архитектура модулей

```
parser/
├── config/
│   └── seeds.yaml          — источники по городам (URL, режим, тип события)
├── src/parser/
│   ├── cli.py              — точка входа: discover / run / --dry-run / --provider
│   ├── config.py           — Settings (env-переменные) + load_seeds()
│   ├── models.py           — ParsedEvent (LLM-ответ), EventRow (строка БД)
│   ├── pipeline.py         — оркестратор: запускает источники, дедупит, пишет в БД
│   ├── db.py               — upsert_events() + cleanup_old_events()
│   ├── dedup.py            — фильтрация уже известных source_url
│   ├── validator.py        — ParsedEvent → EventRow (slug, типы, санитизация)
│   ├── discovery/
│   │   ├── listing.py      — краулер страниц-листингов
│   │   └── sitemap.py      — краулер sitemap.xml
│   ├── extraction/
│   │   ├── gemini_extractor.py   — Gemini через google-genai SDK
│   │   └── groq_extractor.py     — Groq через groq SDK
│   └── sources/
│       └── twogis.py       — 2ГИС Places API → ParsedEvent
└── tests/                  — smoke-тесты без сети (pytest)
```

---

## CI / GitHub Actions

Файл: `.github/workflows/parse.yml`

- **Расписание:** ежедневно в 21:00 UTC (00:00 МСК)
- **Matrix:** запускает `perm` и `sochi` параллельно
- **После парсинга:** отправляет хук в Vercel → сайт пересобирается с актуальными данными
- **При ошибке:** опционально отправляет сообщение в Telegram

### Необходимые GitHub Secrets (Settings → Secrets → Actions)

Секреты должны быть в **Environment "Production"**:

| Secret | Описание |
|---|---|
| `SUPABASE_URL` | URL проекта Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role ключ (запись в БД) |
| `GEMINI_API_KEY` | Ключ Gemini API |
| `TWOGIS_API_KEY` | Ключ 2ГИС API |
| `VERCEL_DEPLOY_HOOK` | URL хука деплоя (Vercel → Settings → Git → Deploy Hooks) |
| `TG_BOT_TOKEN` | (опционально) Telegram-бот для алертов |
| `TG_CHAT_ID` | (опционально) chat_id для алертов |
