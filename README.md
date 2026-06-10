# Афиша — агрегатор событий досуга

Сайт-агрегатор развлечений для Перми и Сочи: квизы, стендапы, боулинг, бильярд, картинг.

**Стек:** Python 3.11+ (парсер) · PostgreSQL / Supabase (хранилище) · Next.js 16 SSG (фронтенд) · GitHub Actions (CI/CD) · Vercel (хостинг)

---

## Архитектура

```
GitHub Actions (cron, 00:00 МСК)
    │
    ▼
Python-парсер (parser/)
    ├── Discovery: краулер HTML / sitemap / 2ГИС API
    ├── LLM Extraction: Gemini / Groq / DeepSeek → ParsedEvent
    ├── Validation: slug, типы, даты
    └── DB Write: upsert в Supabase Postgres
    │
    ▼
Supabase Postgres
    │  читается при сборке (SSG)
    ▼
Next.js build (web/)
    │  генерирует статические HTML-страницы
    ▼
Vercel CDN ← пользователь
```

Сайт полностью статический — нет серверного рендеринга в рантайме. После каждого прогона парсера GitHub Actions отправляет хук в Vercel, сайт пересобирается с актуальными данными.

---

## Структура репозитория

```
entertainment/
├── parser/                         — Python-парсер событий
│   ├── config/
│   │   └── seeds.yaml              — источники по городам (URL, режим, тип)
│   ├── src/parser/
│   │   ├── cli.py                  — точка входа CLI
│   │   ├── config.py               — Settings + загрузка seeds
│   │   ├── models.py               — ParsedEvent, EventRow (Pydantic)
│   │   ├── pipeline.py             — оркестратор пайплайна
│   │   ├── db.py                   — upsert + cleanup в Supabase
│   │   ├── dedup.py                — фильтрация известных URL
│   │   ├── validator.py            — конвертация в EventRow + slug
│   │   ├── discovery/
│   │   │   ├── base.py             — абстрактный класс DiscoveryStrategy
│   │   │   ├── listing.py          — краулер HTML-листингов
│   │   │   └── sitemap.py          — краулер sitemap.xml
│   │   ├── extraction/
│   │   │   ├── base.py             — абстрактный класс LLMExtractor
│   │   │   ├── jsonld.py           — Schema.org JSON-LD парсер (перед LLM, без LLM)
│   │   │   ├── gemini_extractor.py — Google Gemini
│   │   │   ├── groq_extractor.py   — Groq Llama 3.3 70B
│   │   │   └── deepseek_extractor.py — DeepSeek V4 Flash (OpenRouter)
│   │   └── sources/
│   │       ├── twogis.py           — 2ГИС Catalog API (без LLM)
│   │       ├── timepad.py          — Timepad API, широкая афиша; тип по категории (без LLM)
│   │       └── kudago.py           — KudaGo API, широкая афиша (без LLM; Сочи-пилот, отключён)
│   ├── tests/                      — pytest тесты
│   ├── pyproject.toml              — зависимости и настройки пакета
│   └── README.md                   — документация парсера
│
├── web/                            — Next.js 16 фронтенд
│   ├── app/
│   │   ├── layout.tsx              — корневой layout (Метрика, верификация)
│   │   ├── sitemap.ts              — генерация sitemap.xml
│   │   ├── robots.ts               — robots.txt
│   │   ├── perm/
│   │   │   ├── page.tsx            — главная страница Перми
│   │   │   └── events/[slug]/page.tsx — страница события Перми
│   │   └── sochi/
│   │       ├── page.tsx            — главная страница Сочи
│   │       └── events/[slug]/page.tsx — страница события Сочи
│   ├── components/
│   │   ├── Header.tsx              — шапка с переключателем городов
│   │   ├── CityView.tsx            — сетка карточек + SEO-описание
│   │   ├── Sidebar.tsx             — панель фильтров
│   │   └── EventCard.tsx           — карточка события
│   ├── lib/
│   │   ├── types.ts                — EventItem, City, CITY_CONFIG
│   │   ├── events.ts               — запросы к Supabase (getEventsByCity, getEventBySlug)
│   │   ├── filters.ts              — клиентская фильтрация
│   │   └── supabase.ts             — Supabase client (anon key, read-only)
│   └── README.md                   — документация фронтенда
│
├── .github/workflows/
│   └── parse.yml                   — CI/CD: ежедневный запуск парсера
│
├── input/                          — образцы JSON-данных для тестирования
├── prototype/                      — ранний UI-прототип (HTML/CSS)
└── events_site_plan.md             — спецификация MVP (на русском)
```

---

## Парсер (`parser/`)

### `cli.py` — точка входа

Разбирает аргументы командной строки и запускает нужную ветку пайплайна.

**Команды:**

| Команда | Что делает |
|---------|-----------|
| `discover` | Только discovery без LLM и записи в БД. Используется для отладки краулеров |
| `run` | Полный пайплайн: discovery → dedup → LLM-извлечение → валидация → запись в БД |

**Флаги:**

| Флаг | Описание |
|------|---------|
| `--city perm\|sochi` | Город для обработки (обязателен) |
| `--source NAME` | Запустить только один источник (опционально) |
| `--dry-run` | LLM работает, но в БД не пишет. Для проверки качества извлечения |
| `--provider gemini\|groq\|deepseek` | Переключить LLM-провайдер разово |
| `--mode per_url\|batch_listing\|direct_api` | Переопределить режим извлечения |

Возвращает код выхода 0 если хотя бы половина событий извлечена успешно, иначе 1.

---

### `config.py` — конфигурация

Три датакласса:

**`Settings`** — загружается из переменных окружения:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`
- `TWOGIS_API_KEY`, `TIMEPAD_TOKEN`
- `LLM_PROVIDER` (gemini / groq / deepseek, дефолт: gemini)
- `GEMINI_MODEL`, `GROQ_MODEL`, `DEEPSEEK_MODEL` — модели провайдеров

**`SourceConfig`** — конфигурация одного источника из `seeds.yaml`:
- `name` — уникальное имя источника
- `extraction_mode` — `per_url` / `batch_listing` / `direct_api`
- Для `per_url`/`batch_listing`: `kind` (listing/sitemap), `url`, `url_pattern` (regex)
- Для `direct_api`: `provider` (twogis), `api_query`, `event_type`

**`CityConfig`** — список источников одного города.

**`load_seeds()`** — читает `config/seeds.yaml`, возвращает словарь `{city: CityConfig}`.

---

### `config/seeds.yaml` — источники событий

Конфигурационный файл, описывающий откуда брать события для каждого города.

```yaml
cities:
  perm:
    sources:
      - name: quizplease
        extraction_mode: batch_listing
        kind: listing
        url: https://quizplease.ru/game-page?city=perm
        url_pattern: "/game-page\\?id=\\d+"

      - name: twogis-bowling
        extraction_mode: direct_api
        provider: twogis
        api_query: "боулинг Пермь"
        event_type: bowling
```

**Режимы извлечения:**
- `batch_listing` — скачивает страницу целиком. Сначала пробует Schema.org JSON-LD (бесплатно, без LLM); если не нашёл — один LLM-вызов извлекает все события. Пропускается целиком, если HTML не менялся (хеш в `parse_state`)
- `per_url` — дискавери находит N URL, затем N отдельных LLM-вызовов для каждого
- `direct_api` — вызов внешнего API (2ГИС), маппинг JSON → `ParsedEvent` без LLM

---

### `models.py` — модели данных

**`EventType`** (enum): ниша MVP-1 — `quiz`, `standup`, `bowling`, `billiards`, `karting`; широкая афиша MVP-2 (Timepad, тип по категории) — `concert`, `theater`, `exhibition`, `festival`, `quest`, `party`, `cinema`, `sport`, `education`, `business`, `art`, `kids`, `food`, `trip`, `hobby`, `science`, `other`

**`ParsedEvent`** (Pydantic) — результат LLM-извлечения:

| Поле | Тип | Описание |
|------|-----|---------|
| `title` | str (3-300 символов) | Название события |
| `type` | EventType | Тип события |
| `date` | str | `YYYY-MM-DD` или `always` |
| `price_min` / `price_max` | int ≥ 0 | Диапазон цен |
| `price_text` | str | Строка для отображения: «от 500 ₽» |
| `address` | str | Полный адрес |
| `venue_name` | str | Название площадки |
| `time_start` / `time_end` | str? | Время `HH:MM` (опционально) |
| `image_url` | str? | URL изображения ≤ 500 символов |
| `description` | str? | Описание ≤ 500 символов |
| `organizer` | str? | Организатор |
| `district` | str? | Район города |

Валидаторы: формат даты, формат времени, `price_max >= price_min`.

**`EventRow`** (ParsedEvent + служебные поля) — строка в таблице БД:
- `id` — `{city}-{slug}`
- `city` — город
- `slug` — детерминированный URL-ключ
- `source_url` — ссылка на источник
- `source` — имя источника из seeds
- `parsed_at` — UTC timestamp извлечения

---

### `pipeline.py` — оркестратор

**`run_city(city_config, extractor, supabase_client, dry_run, source_filter)`**

Главная функция, запускается из CLI для каждого города:
1. Перебирает источники из `CityConfig`
2. Для каждого вызывает нужный runner (`_run_per_url_source`, `_run_batch_source`, `_run_direct_api_source`)
3. Дедупликация по source_url
4. Upsert в БД
5. Очистка старых событий
6. Возвращает `PipelineResult` со счётчиками (discovered / new / extracted / failed / written)

**`_run_per_url_source(source, extractor, client, dry_run)`**
- Discovery (listing или sitemap) → список URL
- `filter_new_urls()` — убирает уже известные
- Для каждого нового URL: скачать HTML → `extractor.extract()` → `to_event_row()`

**`_run_batch_source(source, extractor, client, dry_run)`**
- Скачать страницу-листинг целиком
- Один вызов `extractor.extract_many()` → список `ParsedEvent`
- Batch-вариант эффективнее для страниц с полным расписанием (QuizPlease)

**`_run_direct_api_source(source, client, dry_run)`**
- `TwoGisClient.search()` → готовые `ParsedEvent` без LLM
- Маппинг и запись в БД

---

### `db.py` — работа с базой данных

**`make_client(settings)`** — создаёт Supabase-клиент с `service_role_key` (обходит RLS, разрешена запись).

**`upsert_events(client, events)`**
- Записывает список `EventRow` в таблицу `events`
- Upsert по `conflict="slug"` — если slug уже есть, обновляет поля
- Возвращает `WriteStats` (inserted, updated, errors)

**`cleanup_old_events(client, city)`**
- Удаляет события: `date < сегодня - 7 дней AND date != 'always'`
- Сохраняет: постоянные места (`always`) и события ближайших 7 дней (буфер на случай отмены парсинга)
- Вызывается автоматически после каждого прогона

---

### `dedup.py` — дедупликация

**`filter_new_urls(client, city, urls)`** (для `per_url`)
- Запрашивает из БД все `source_url` для города
- Возвращает только те URL, которых ещё нет в базе
- Позволяет не тратить LLM-запросы на уже обработанные страницы

**`get_source_hash` / `set_source_hash`** (для `batch_listing`)
- Хранят SHA-256 листинга в таблице `parse_state` по ключу `(city, source)`
- Если HTML листинга не менялся с прошлого прогона — весь LLM/JSON-LD-вызов пропускается
- Существующие события при этом остаются в БД (upsert ничего не трогает)

---

### `validator.py` — валидация и slug

**`to_event_row(parsed, city, source_url, source)`**
- Конвертирует `ParsedEvent` → `EventRow`
- Генерирует `slug` через `_make_slug(title, date)`
- Формирует `id = {city}-{slug}`
- Проставляет `parsed_at = utcnow()`

**`_make_slug(title, date)`**
- Кириллица → транслитерация (встроенный словарь: я→ya, ж→zh, ш→sh и т.д.)
- Unicode NFKD нормализация → ASCII
- Не-буквенные символы → дефис
- Обрезка до 80 символов
- Суффикс даты: `kviz-v-bare-2026-06-01`
- Для `date='always'` дата не добавляется: `bowling-plus`

---

### `discovery/` — стратегии обнаружения URL

**`base.py`** — абстрактный базовый класс:
- `DiscoveredUrl` — датакласс с полями `url` и `source`
- `DiscoveryStrategy` — ABC с методом `discover() -> list[DiscoveredUrl]`

**`listing.py`** — `ListingDiscovery`:
- Скачивает HTML-страницу через `httpx`
- `selectolax` ищет все теги `<a href="...">`
- Фильтрует по `url_pattern` (regex)
- Конвертирует относительные пути в абсолютные (`urljoin`)
- Дедуплицирует найденные URL

**`sitemap.py`** — `SitemapDiscovery`:
- Скачивает `sitemap.xml`
- Извлекает все теги `<loc>` с URL страниц
- Фильтрует по `url_pattern` (regex)

---

### `extraction/` — LLM-извлечение

Все экстракторы реализуют один интерфейс:

**`base.py`**:
- `ExtractorError` — исключение при невалидном ответе LLM
- `LLMExtractor` ABC:
  - `extract(html, source_url) -> ParsedEvent` — одно событие с детальной страницы
  - `extract_many(html, source_url) -> list[ParsedEvent]` — список событий со страницы-листинга

---

**`gemini_extractor.py`** — `GeminiExtractor`

Использует Google Gemini через `google-genai` SDK.

- **Модель:** `gemini-2.5-flash-lite` (по умолчанию) — самая дешёвая в Flash-семействе
- **`extract()`:**
  - Очищает HTML (удаляет script/style/svg/iframe/head)
  - Отправляет в Gemini с системным промптом (~40 строк)
  - Промпт: извлечь поля события в JSON, обработать отсутствующий год в дате, фильтровать SVG/иконки, вернуть `title="NOT_AN_EVENT"` если страница не о событии
  - Использует `response_schema=ParsedEvent` — SDK валидирует структуру
- **`extract_many()`:**
  - Лимит: 800k символов очищенного HTML
  - `response_schema=list[ParsedEvent]`
  - `max_output_tokens=20000` для длинных расписаний
  - Фильтрует записи с `title="NOT_AN_EVENT"`

---

**`groq_extractor.py`** — `GroqExtractor`

Использует Groq SDK с моделью `llama-3.3-70b-versatile`.

- **Отличие от Gemini:** API не валидирует схему — JSON-схема встроена в системный промпт
- **`extract()`:**
  - `response_format={"type": "json_object"}` — гарантирует валидный JSON
  - Конвертирует HTML → Markdown через `markdownify` для экономии токенов
  - Лимит 40k символов (тоньше бюджет чем у Gemini)
- **`extract_many()`:**
  - Ответ обёрнут в `{"events": [...]}` — Groq не поддерживает top-level массивы
  - Вытаскивает `response["events"]`

---

**`deepseek_extractor.py`** — `DeepSeekExtractor`

Использует DeepSeek V4 Flash через OpenRouter (OpenAI-совместимый API).

- **SDK:** `openai` с `base_url="https://openrouter.ai/api/v1"`
- **Модель:** `deepseek/deepseek-v4-flash`
- **`extract()`:**
  - Полная JSON-схема встроена в системный промпт (DeepSeek не поддерживает structured output)
  - `temperature=0.3`, `max_tokens=2000`
- **`extract_many()`:**
  - `max_tokens=8000`, ответ в формате `{"events": [...]}`
  - `temperature=0.3`
- HTML → Markdown конвертация, лимит 40k символов

---

### `sources/twogis.py` — 2ГИС API

**`TwoGisClient`** — клиент к 2ГИС Catalog API (`catalog.api.2gis.com/3.0/items`).

**`search(query, event_type, max_items=50)`**:
- Постраничный поиск: 10 результатов за запрос, обходит до `max_items`
- Запросы: `"боулинг Пермь"`, `"бильярд Сочи"`, `"картинг Пермь"` и т.д.
- Возвращает список `ParsedEvent` с `date='always'` (постоянно работающие места)
- Цена по умолчанию: 0–0 (в листинге API нет цен)

**Маппинг полей из JSON ответа API:**

| Поле API | Поле ParsedEvent |
|----------|-----------------|
| `name_ex.primary` | `title`, `venue_name` |
| `full_address_name` | `address` |
| `adm_div[type=district].name` | `district` |
| `external_content[subtype=main_photo].url` | `image_url` |

**Вспомогательные методы:**
- `_item_to_event(item, event_type)` — маппинг одного JSON-объекта → `ParsedEvent`
- `_district_from_adm_div(adm_div)` — извлекает район из административного деления
- `_photo_from_external_content(content)` — находит главную фотографию

---

### `sources/timepad.py` — Timepad API

**`TimepadClient`** — клиент к Timepad (`api.timepad.ru/v1/events`, Bearer-токен `TIMEPAD_TOKEN`).

**`search(city_slug, max_items=500)`** — тянет предстоящие события города (пагинация limit/skip,
`starts_at_min=сегодня`) и возвращает пары `(ParsedEvent, url)` с реальной ссылкой на событие.
Это источник **широкой афиши** для обоих городов: тип события определяется не источником, а его
категорией Timepad через `_map_category(categories)` (словарь `tag → EventType`, например
`intellekt → quiz`, `concert → concert`, `it → business`; нераспознанное → `other`).

У Timepad нет категории «стендап» — такие события приходят как `concert`/`other`; точный тип
`standup` остаётся за нишевыми источниками (QuizPlease).

### `sources/kudago.py` — KudaGo API (отключён)

**`KudaGoClient`** — клиент к KudaGo (`kudago.com/public-api`, без ключа), маппинг категорий →
`EventType`. Источник в `seeds.yaml` **закомментирован**: данные KudaGo по Сочи устарели, Пермь
не поддерживается. Код готов на случай обновления данных.

---

## GitHub Actions (`.github/workflows/parse.yml`)

**Триггеры:**
- Cron: `0 21 * * *` (21:00 UTC = 00:00 МСК) — ежедневно
- `workflow_dispatch` — ручной запуск из интерфейса GitHub

**Матрица:** `perm` и `sochi` запускаются параллельно в двух джобах.

**Шаги каждой джобы:**
1. Checkout кода
2. Python 3.12 с кэшем pip
3. `pip install -e .` из `parser/`
4. `python -m parser.cli run --city {city}` с секретами из env
5. При ошибке: Telegram-уведомление (если настроено)

**После успеха:** отправляет POST на `VERCEL_DEPLOY_HOOK` → сайт пересобирается.  
Деплой триггерится при частичном успехе (хотя бы один город прошёл).

**Секреты (Environment "Production"):**

| Secret | Описание |
|--------|---------|
| `SUPABASE_URL` | URL проекта Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role ключ (запись в БД) |
| `GEMINI_API_KEY` | Google Gemini API |
| `TWOGIS_API_KEY` | 2ГИС Catalog API |
| `TIMEPAD_TOKEN` | Timepad API (Bearer-токен) для direct_api источников |
| `VERCEL_DEPLOY_HOOK` | URL хука деплоя Vercel |
| `TG_BOT_TOKEN` | Telegram-бот для алертов (опционально) |
| `TG_CHAT_ID` | chat_id для алертов (опционально) |

---

## Фронтенд (`web/`)

Next.js 16 App Router, полностью статический (SSG), React 19, Tailwind CSS v4.

### Маршруты

| URL | Страница |
|-----|---------|
| `/` | 301 редирект → `/perm` |
| `/perm/` | Главная Перми — сетка событий |
| `/perm/events/[slug]/` | Детальная страница события Перми |
| `/sochi/` | Главная Сочи |
| `/sochi/events/[slug]/` | Детальная страница события Сочи |
| `/sitemap.xml` | Автогенерация из БД при деплое |
| `/robots.txt` | Allow all + ссылка на sitemap |

### Ключевые файлы

**`app/layout.tsx`**
- Метаданные по умолчанию: шаблон `<title>`, описание
- Верификация Google / Яндекс через `env`-переменные
- Yandex Metrika: вставляет счётчик через `NEXT_PUBLIC_YM_ID`

**`app/perm/page.tsx`** / **`app/sochi/page.tsx`**
- Server Component, вызывает `getEventsByCity(city)` при сборке
- Формирует SEO-метаданные страницы города
- Рендерит `<Header>` + `<CityView>` + `<Footer>`

**`app/perm/events/[slug]/page.tsx`** (аналогично для Сочи)
- `generateStaticParams()` — генерирует список всех slug при сборке
- `generateMetadata()` — динамические `<title>` / `<description>` / Open Graph
- Рендер: изображение (или emoji-заглушка с градиентом) · тип (цветной бейдж) · название · дата/время · цена · адрес · описание · кнопка «Перейти к источнику»

**`lib/events.ts`**
- `getEventsByCity(city)` — запрос к Supabase: `city=X AND (date='always' OR date>=today)`, сортировка по дате
- `getEventBySlug(city, slug)` — для детальной страницы
- `rowToEvent()` — snake_case строка БД → camelCase `EventItem` TypeScript

**`lib/filters.ts`** — клиентская фильтрация без запросов к серверу:
- По типу события
- По дате (сегодня / завтра / выходные)
- По цене (диапазон)
- Чекбокс «только с фиксированной датой» (скрывает `always`-события)

**`lib/types.ts`** — типы TypeScript:
- `EventItem` — зеркало `EventRow` в camelCase
- `CITY_CONFIG` — метаданные городов (label, path, metaTitle, description)
- `EVENT_TYPE_LABELS` — отображаемые названия типов

### Компоненты

**`Header.tsx`** — липкая шапка:
- Логотип / название сайта
- Переключатель городов (подсвечивает активный)
- Поле поиска (placeholder, пока не функционален)

**`EventCard.tsx`** — карточка события в сетке:
- Изображение или заглушка с эмодзи типа
- Цветной бейдж типа
- Название, дата, цена, площадка

**`CityView.tsx`** — страница города:
- Сетка карточек (4 колонки desktop, 2 mobile)
- Sidebar с фильтрами
- SEO-текстовый блок для индексации

**`Sidebar.tsx`** — панель фильтров (тип, дата, цена)

### SEO

- `<title>` + `<meta description>` на каждой странице
- Open Graph теги для соцсетей
- Schema.org Event JSON-LD на детальных страницах
- Canonical URL
- `sitemap.xml` генерируется из БД при каждом деплое

---

## Модель данных (таблица `events`)

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | text | `{city}-{slug}` |
| `city` | text | `perm` или `sochi` |
| `slug` | text UNIQUE | URL-идентификатор (транслит + дата) |
| `title` | text | Название события |
| `type` | text | `quiz` / `standup` / `bowling` / `billiards` / `karting` |
| `date` | text | `YYYY-MM-DD` или `always` |
| `time_start` | text | `HH:MM` |
| `price_min` | int | Минимальная цена |
| `price_max` | int | Максимальная цена |
| `price_text` | text | Отображаемая строка цены |
| `address` | text | Адрес |
| `venue_name` | text | Площадка |
| `source_url` | text | Ссылка на источник |
| `image_url` | text | Изображение |
| `description` | text | Описание |
| `organizer` | text | Организатор |
| `district` | text | Район города |
| `source` | text | Имя источника из seeds |
| `parsed_at` | timestamptz | Время последнего обновления |

---

## Быстрый старт

### Парсер

```bash
cd parser
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows

pip install -e ".[dev]"
cp .env.example .env
# Отредактируй .env — добавь ключи
```

**Переменные окружения:**

```env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
GEMINI_API_KEY=...
TWOGIS_API_KEY=...
TIMEPAD_TOKEN=...
LLM_PROVIDER=gemini   # gemini | groq | deepseek
```

**Команды:**

```bash
# Проверить краулер без LLM
python -m parser.cli discover --city perm

# Сухой прогон (LLM работает, в БД не пишет)
python -m parser.cli run --city perm --dry-run

# Боевой прогон
python -m parser.cli run --city perm
python -m parser.cli run --city sochi

# Один источник с другим провайдером
python -m parser.cli run --city perm --source quizplease --provider groq
```

### Фронтенд

```bash
cd web
npm install
cp .env.example .env.local
# Вставь NEXT_PUBLIC_SUPABASE_URL и NEXT_PUBLIC_SUPABASE_ANON_KEY
npm run dev
```

Открой [http://localhost:3000](http://localhost:3000).

**Переменные окружения Vercel:**

| Переменная | Описание |
|-----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | URL проекта Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Публичный anon-ключ (read-only) |
| `NEXT_PUBLIC_SITE_URL` | Домен сайта (для sitemap) |
| `NEXT_PUBLIC_YM_ID` | ID счётчика Яндекс.Метрики (опционально) |
| `YANDEX_VERIFICATION` | Код верификации Яндекс.Вебмастер (опционально) |
| `GOOGLE_SITE_VERIFICATION` | Код верификации Google Search Console (опционально) |

---

## Добавление нового источника

1. Открой `parser/config/seeds.yaml`, добавь блок в нужный город:

```yaml
- name: my-source
  extraction_mode: batch_listing   # или per_url
  kind: listing                    # или sitemap
  url: https://example.com/events
  url_pattern: "/event/\\d+"
```

2. Проверь дискавери: `python -m parser.cli discover --city perm --source my-source`
3. Если URL находятся — сухой прогон: `python -m parser.cli run --city perm --source my-source --dry-run`
4. Боевой прогон: `python -m parser.cli run --city perm --source my-source`
