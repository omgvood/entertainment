# Афиша — агрегатор событий досуга

Сайт-агрегатор афиши Перми и Сочи: концерты, спектакли, выставки, кино, экскурсии, квизы, стендапы, боулинг, бильярд, картинг. Старт — узкая ниша (квизы/места), сейчас — широкая афиша через Timepad.

**Стек:** Python 3.11+ (парсер) · PostgreSQL / Supabase (хранилище) · Next.js 16 SSG (фронтенд) · GitHub Actions (CI/CD) · Vercel (хостинг)

---

## Архитектура

```
GitHub Actions (cron, 00:00 МСК)
    │
    ▼
Python-парсер (parser/)
    ├── direct_api: 2ГИС / Timepad → ParsedEvent (без LLM)
    ├── Discovery: краулер HTML / sitemap (для listing-источников)
    ├── Extraction: JSON-LD (Schema.org) → фолбэк LLM (Gemini / Groq / DeepSeek)
    ├── Dedup: новые URL + хеш листинга (raw_documents) — экономия LLM
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

Проект логически делится на **4 подсистемы**:

| Подсистема | Что входит | Назначение |
|-----------|-----------|-----------|
| **Discovery** | `candidate_sources` | Поиск новых источников → ручная модерация → `seeds.yaml` |
| **Ingestion** | crawlers + API-клиенты + `raw_documents` | Получение и хранение сырого контента |
| **Extraction** | JSON-LD / LLM / теги | Превращение сырья в `ParsedEvent` |
| **Analytics** | `source_health` + `coverage_stats` | Мониторинг здоровья источников и полноты покрытия |

---

## Покрытие по категориям

Успех проекта измеряется **не числом источников, а полнотой покрытия спроса** по категориям.
Пользователю всё равно, откуда данные — важно, найдёт ли он, «куда сходить».

Текущее покрытие (Пермь):

| Категория | Источники | Статус |
|-----------|-----------|--------|
| Концерты | Timepad | ✅ |
| Театр | Timepad | ✅ |
| Выставки | Timepad | ✅ |
| Квизы | QuizPlease + Timepad | ✅ |
| Стендап | Timepad (partial) | ⚠️ нет своей категории в Timepad |
| Квесты | 2ГИС | ✅ |
| Боулинг | 2ГИС | ✅ |
| Детям | Timepad (partial) | ⚠️ |
| Экскурсии | — | ❌ |
| Мастер-классы | — | ❌ |

Категории со статусом ❌/⚠️ — это сигнал, какие источники искать через **Discovery** (`candidate_sources`).
Полнота отслеживается автоматически в таблице `coverage_stats` (исторические снимки по дням).

---

## Метрики успеха

**MVP-1 (Пермь)** — минимум по категориям:

| Категория | Минимум |
|-----------|---------|
| Концерты | 100+ |
| Выставки | 50+ |
| Квизы | 20+ |
| Стендап | 10+ |
| Постоянные места | 100+ |

Общие цели MVP-1: 500+ активных событий · 15+ источников · обновление ≤ 24ч ·
дублей между источниками < 5% · успешность парсинга ≥ 95% ·
необработанных `candidate_sources` (status='new') < 50.

**MVP-2 (Пермь + Сочи):** 1500+ карточек суммарно · 30+ источников.

---

## Что реализовано

Помимо базового пайплайна (discovery → extract → write), добавлены подсистемы для масштабирования
и контроля качества данных:

| Возможность | Что даёт | Где |
|-------------|----------|-----|
| **Теги** (`tags` + `tags_version`) | Основа подборок/рекомендаций. Закрытый набор, версионируемый. LLM выбирает из набора, direct_api получает авто-теги по типу | `taxonomy.py`, `models.py`, промпты экстракторов |
| **Discovery источников** | Поиск новых сайтов → скоринг → `candidate_sources` → ручная модерация → `seeds.yaml` | `sources/candidate_sources.py`, команда `discover-sources` |
| **Raw Documents** | Хранение сырья (HTML/JSON) для перепарса без повторного краулинга; здесь же хеш для дедупа | `db.py` (`save_raw_document`), таблица `raw_documents` |
| **Source Health** | Лог + агрегат по источникам: `events_found`, `errors`, `duration_sec`, `success_rate` | `db.py` (`record_source_health`), таблицы `source_health*` |
| **Coverage Stats** | Ежедневный снимок покрытия по категориям — видно тренды и выпадение категорий | `db.py` (`record_coverage`), таблица `coverage_stats` |
| **Fingerprint** | Кросс-источниковая дедупликация по `title+date+venue` (без UNIQUE — пока статистика) | `validator.py` (`_fingerprint`), поле `events.fingerprint` |
| **Source priority** | Приоритет источника для разрешения дублей | `config.py` (`SourceConfig.priority`) |

Детали по каждому модулю — ниже в разделах «Парсер» и «Модель данных».

---

## Структура репозитория

```
entertainment/
├── parser/                         — Python-парсер событий
│   ├── config/
│   │   └── seeds.yaml              — источники по городам (URL, режим, тип)
│   ├── src/parser/
│   │   ├── cli.py                  — точка входа CLI (discover / discover-sources / run)
│   │   ├── config.py               — Settings + SourceConfig (с priority) + загрузка seeds
│   │   ├── models.py               — ParsedEvent, EventRow (Pydantic) + tags/fingerprint
│   │   ├── taxonomy.py             — закрытый набор тегов + TAGS_VERSION + авто-теги
│   │   ├── pipeline.py             — оркестратор пайплайна + health/coverage/dedup
│   │   ├── db.py                   — upsert + cleanup + raw_documents/health/coverage
│   │   ├── dedup.py                — фильтрация известных URL (per_url)
│   │   ├── validator.py            — конвертация в EventRow + slug + fingerprint
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
│   │       ├── kudago.py           — KudaGo API, широкая афиша (без LLM; Сочи-пилот, отключён)
│   │       └── candidate_sources.py — Discovery новых источников (поиск → скоринг → БД)
│   ├── tests/                      — pytest тесты
│   ├── pyproject.toml              — зависимости и настройки пакета
│   └── README.md                   — документация парсера
│
├── supabase/
│   ├── migrations/                — SQL-миграции схемы (tags, fingerprint, raw_documents, …)
│   └── seeds/                      — тестовые данные (sochi_events.sql)
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
│   ├── parse.yml                   — CI/CD: ежедневный запуск парсера
│   └── discover_sources.yml        — еженедельный поиск новых источников
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
| `discover-sources` | Discovery новых источников: поиск → скоринг → `candidate_sources` (раз в неделю) |
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
- `priority` — приоритет источника при кросс-источниковой дедупликации (выше — побеждает), дефолт `0`
- Для `per_url`/`batch_listing`: `kind` (listing/sitemap), `url`, `url_pattern` (regex)
- Для `direct_api`: `provider` (`twogis` / `timepad` / `kudago`). `twogis` требует `api_query` + `event_type`; `timepad`/`kudago` тип определяют сами по категории (доп. полей не нужно)

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
- `batch_listing` — скачивает страницу целиком. Сначала пробует Schema.org JSON-LD (бесплатно, без LLM); если не нашёл — один LLM-вызов извлекает все события. Пропускается целиком, если HTML не менялся (хеш в `raw_documents`)
- `per_url` — дискавери находит N URL, затем N отдельных LLM-вызовов для каждого
- `direct_api` — вызов внешнего API (2ГИС / Timepad / KudaGo), маппинг JSON → `ParsedEvent` без LLM

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
| `tags` | list[str] | Теги из закрытого набора `taxonomy.ALLOWED_TAGS` (валидатор отбрасывает чужие) |

Валидаторы: формат даты, формат времени, `price_max >= price_min`, фильтрация тегов.

**`EventRow`** (ParsedEvent + служебные поля) — строка в таблице БД:
- `id` — `{city}-{slug}`
- `city` — город
- `slug` — детерминированный URL-ключ
- `source_url` — ссылка на источник
- `source` — имя источника из seeds
- `parsed_at` — UTC timestamp извлечения
- `tags_version` — версия таксономии тегов (дефолт `TAGS_VERSION`)
- `fingerprint` — хеш `title+date+venue` для кросс-источниковой дедупликации

---

### `taxonomy.py` — теги для подборок

Единый источник правды для тегов. Теги — основа будущих подборок («куда сходить с девушкой»,
«бесплатные мероприятия», «интеллектуальный досуг») и рекомендаций.

- **`TAGS_VERSION`** — версия набора. При изменении тегов поднимается; события со старой версией
  можно перепарсить (особенно вместе с `raw_documents`).
- **`ALLOWED_TAGS`** — закрытый набор: `для компании`, `для пары`, `для детей`, `интеллектуальное`,
  `активное`, `творческое`, `вечером`, `днём`, `в помещении`, `на улице`, `бесплатно`.
- **`filter_tags(tags)`** — оставляет только разрешённые теги (вызывается валидатором `ParsedEvent`).
- **`default_tags_for_type(type)`** — авто-теги по типу события для `direct_api`-источников
  (где LLM не вызывается): например `quiz → [интеллектуальное, для компании]`.

LLM-экстракторы получают список разрешённых тегов в системном промпте и выбирают из него;
`direct_api` (2ГИС/Timepad) получают авто-теги в `validator.to_event_row()`.

---

### `pipeline.py` — оркестратор

**`run_city(city_config, extractor, supabase_client, dry_run, source_filter)`**

Главная функция, запускается из CLI для каждого города:
1. Перебирает источники из `CityConfig`, замеряя длительность каждого
2. Для каждого вызывает нужный runner (`_run_per_url_source`, `_run_batch_source`, `_run_direct_api_source`)
3. Пишет здоровье источника в `source_health` (`record_source_health`)
4. Дедупликация по `id` + подсчёт `duplicate_candidates` по `fingerprint` (без схлопывания)
5. Upsert в БД
6. Очистка: `cleanup_old_events` + `cleanup_old_raw_documents` (TTL) + снимок `record_coverage`
7. Возвращает `PipelineResult` (discovered / new / extracted / failed / written / duplicate_candidates)

**`_run_per_url_source(source, extractor, client, dry_run)`**
- Discovery (listing или sitemap) → список URL
- `filter_new_urls()` — убирает уже известные
- Для каждого нового URL: скачать HTML → `extractor.extract()` → `to_event_row()`
- Архивирует сырьё в `raw_documents` (для перепарса)

**`_run_batch_source(source, extractor, supabase, city, dry_run)`**
- Скачать страницу-листинг целиком; посчитать хеш → если не менялся, пропустить (хеш в `raw_documents`)
- Сначала JSON-LD (`extract_jsonld_events`, без LLM); если пусто — один вызов `extractor.extract_many()`
- После успешного извлечения архивирует сырьё + фиксирует хеш в `raw_documents`
- Batch-вариант эффективнее для страниц с полным расписанием (QuizPlease)

**`_run_direct_api_source(source, client, provider_keys)`**
- Диспетчер по `source.provider`: `TwoGisClient` / `TimepadClient` / `KudaGoClient`
- Каждый возвращает `(ParsedEvent, source_url)` без LLM → маппинг и запись в БД

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

**Ingestion (`raw_documents`):**
- `save_raw_document(client, source, url, content, content_type, content_hash)` — upsert сырья по `url`
- `get_raw_document_hash(client, url)` — хеш последнего сохранённого контента (для дедупа `batch_listing`)
- `cleanup_old_raw_documents(client, days=120)` — TTL-очистка сырья

**Analytics (`source_health`, `coverage_stats`):**
- `record_source_health(client, source, city, events_found, errors, duration_sec, last_error)` —
  пишет строку в лог `source_health` и пересчитывает агрегат `source_health_agg` (включая `success_rate`)
- `record_coverage(client, city)` — снимок «сколько событий по каждому типу» в `coverage_stats`

---

### `dedup.py` — дедупликация

**`filter_new_urls(client, city, urls)`** (для `per_url`)
- Запрашивает из БД все `source_url` для города
- Возвращает только те URL, которых ещё нет в базе
- Позволяет не тратить LLM-запросы на уже обработанные страницы

**Дедуп `batch_listing`** — по хешу контента в `raw_documents` (см. `db.get_raw_document_hash`
/ `db.save_raw_document`)
- SHA-256 листинга хранится в `raw_documents.hash` (по `url`), там же лежит само сырьё
- Если HTML листинга не менялся с прошлого прогона — весь LLM/JSON-LD-вызов пропускается
- Хеш фиксируется только после успешного извлечения (упавший прогон повторится)
- Существующие события при этом остаются в БД (upsert ничего не трогает)

---

### `validator.py` — валидация и slug

**`to_event_row(parsed, city, source_url, source)`**
- Конвертирует `ParsedEvent` → `EventRow`
- Генерирует `slug` через `_make_slug(title, date)`
- Формирует `id = {city}-{slug}`
- Проставляет `parsed_at = utcnow()`
- Если теги пустые (direct_api) — подставляет авто-теги `default_tags_for_type(type)`
- Вычисляет `fingerprint` через `_fingerprint(title, date, venue_name)`

**`_fingerprint(title, date, venue)` / `_normalize(s)`**
- `_normalize` приводит строку к канону: нижний регистр, `ё→е`, без пунктуации, схлопнутые пробелы
- `_fingerprint` = `sha256(normalize(title)|date|normalize(venue))[:16]`
- Одно и то же событие из разных источников даёт одинаковый fingerprint → кросс-источниковый дедуп
- **Без UNIQUE** намеренно: сначала собираем статистику (`duplicate_candidates`), constraint позже

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

### `sources/candidate_sources.py` — Discovery новых источников

Контур масштабирования каталога: **поиск в интернете → скоринг → `candidate_sources` → ручная
модерация → `seeds.yaml`**. Запускается командой `discover-sources` (раз в неделю).

- **`SearchProvider`** (ABC) — интерфейс поисковика. Реализация `DuckDuckGoProvider` (HTML, без ключа,
  для MVP). Вынесен за интерфейс, чтобы заменить на Serper API без изменения остального кода.
- **`discover_sources(city, supabase, dry_run)`** — точка входа: гоняет типовые запросы
  (`квиз {city}`, `стендап {city}`, `мастер-класс {city}`, `детские мероприятия {city}`, `афиша {city}`),
  агрегирует домены, считает score, пишет в БД.
- **Скоринг кандидата:** `+3` если на странице найден JSON-LD типа `Event`; `+2` если в пути есть
  `/events`/`/afisha`/`/schedule`; `+1` за каждый дополнительный запрос, в котором встретился домен.
- **Фильтры:** пропускаются домены из `seeds.yaml`, домены со статусом `rejected`, агрегаторы/соцсети.
- **`save_candidates`** сохраняет с **сохранением статуса** (не перетирает `approved`/`rejected`)
  и обновляет `last_seen` — для очистки мусора, который давно не встречается.

---

## GitHub Actions

### `.github/workflows/parse.yml` — ежедневный парсинг

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

### `.github/workflows/discover_sources.yml` — еженедельный поиск источников

**Триггеры:**
- Cron: `0 20 * * 0` (воскресенье 20:00 UTC = 23:00 МСК) — раз в неделю
- `workflow_dispatch` — ручной запуск

**Матрица:** `perm` и `sochi` параллельно. Запускает `python -m parser.cli discover-sources --city {city}`.
Нужны только секреты `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY` (LLM-ключи не требуются).
Результат — кандидаты в таблице `candidate_sources` для ручной модерации.

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
- `EventItem` — зеркало `EventRow` в camelCase (включая `tags: string[]`)
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
| `type` | text | `EventType`: ниша (`quiz`/`standup`/`bowling`/…) + широкие (`concert`/`theater`/`cinema`/…) |
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
| `tags` | text[] | Теги из закрытого набора (для подборок/рекомендаций) |
| `tags_version` | int | Версия таксономии тегов, с которой извлечено событие |
| `fingerprint` | text | Хеш `title+date+venue` для кросс-источниковой дедупликации (без UNIQUE) |
| `venue_id` | text | Ссылка на площадку (планируется, см. «Будущая модель данных») |
| `source` | text | Имя источника из seeds |
| `parsed_at` | timestamptz | Время последнего обновления |

Теги задаются закрытым набором в `parser/src/parser/taxonomy.py` (константа `TAGS_VERSION`).
LLM-экстракторы выбирают теги из набора; для `direct_api`-источников теги проставляются
автоматически по типу события. При изменении набора поднимается `TAGS_VERSION` — события
со старой версией можно перепарсить.

### Таблица `parse_state` (legacy — заменена на `raw_documents`)

| Поле | Тип | Описание |
|------|-----|---------|
| `city` | text | Город (часть PK) |
| `source` | text | Имя источника (часть PK) |
| `content_hash` | text | SHA-256 последнего HTML листинга |
| `updated_at` | timestamptz | Время записи хеша |

Если хеш листинга совпадает с прошлым прогоном — LLM/JSON-LD не вызываются.

> Со временем `parse_state` заменяется таблицей `raw_documents` (хеш хранится там же).

### Таблица `raw_documents` (Ingestion) — сырьё

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | uuid | PK |
| `source` | text | Имя источника |
| `url` | text UNIQUE | Адрес страницы / API-запроса |
| `content` | text | Сырой HTML / JSON / XML / RSS |
| `content_type` | text | `html` / `json` / `xml` / `rss` |
| `hash` | text | SHA-256 контента (дедуп вместо `parse_state`) |
| `fetched_at` | timestamptz | Время загрузки |

Хранит сырьё, чтобы менять промпты/модели/теги без повторного обхода сайтов. Сжатие — на стороне
Postgres TOAST (колонка `text`), TTL — 90–180 дней.

### Таблица `candidate_sources` (Discovery) — кандидаты в источники

| Поле | Тип | Описание |
|------|-----|---------|
| `domain` | text PK | Домен кандидата |
| `city` | text | Город |
| `queries` | text[] | Поисковые запросы, в которых встретился |
| `score` | int | Рейтинг полезности (JSON-LD Event, путь `/events`, частота) |
| `has_jsonld_event` | bool | Найден ли Schema.org Event |
| `status` | text | `new` / `approved` / `rejected` |
| `found_at` / `last_seen` | timestamptz | Первая и последняя находка |

### Таблицы `source_health` / `source_health_agg` (Analytics) — здоровье источников

`source_health` — лог запусков (`events_found`, `errors`, `duration_sec`, `last_error`).
`source_health_agg` — агрегат на источник (`last_success`, `avg_events`, `success_rate`, `total_errors`)
для быстрого дашборда «что сломалось».

### Таблица `coverage_stats` (Analytics) — покрытие по категориям

Ежедневный снимок `(city, category, count, snapshot_date)`. Позволяет видеть тренды и замечать
выпадение категорий (например, квизы упали с 25 до 2 — сломался источник).

### Будущая модель данных — `venues`

Когда карточек станет 1000+, площадки выносятся в отдельную таблицу `venues`
(`id, name, address, district, city`), а `events.venue_id` ссылается на неё —
для страниц площадок, SEO и рекомендаций.

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

# Discovery новых источников (поиск → candidate_sources)
python -m parser.cli discover-sources --city perm            # боевой (пишет в БД)
python -m parser.cli discover-sources --city perm --dry-run  # только вывод кандидатов
```

**Полный список команд:**

| Команда | Назначение | Пишет в БД |
|---------|-----------|-----------|
| `discover --city <c> [--source <s>]` | Отладка краулера: только список найденных URL | нет |
| `run --city <c>` | Полный пайплайн (discovery → extract → write) | да |
| `run --city <c> --dry-run` | Прогон LLM без записи (проверка качества) | нет |
| `run --city <c> --source <s>` | Один источник | да |
| `run … --provider gemini\|groq\|deepseek` | Override LLM-провайдера | да |
| `run … --mode per_url\|batch_listing\|direct_api` | Override режима | да |
| `discover-sources --city <c>` | Поиск новых источников → `candidate_sources` | да |
| `discover-sources --city <c> --dry-run` | Поиск без записи (только вывод) | нет |

### Миграции БД

Схема версионируется SQL-файлами в `supabase/migrations/` (применять по порядку):

```bash
# Через Supabase CLI (нужен залогиненный supabase + связанный проект)
supabase db push

# Либо вручную: выполнить каждый файл из supabase/migrations/ в SQL Editor по возрастанию имени
```

Все миграции идемпотентны (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`) — повторное применение
безопасно. Новые таблицы (`raw_documents`, `source_health*`, `coverage_stats`, `candidate_sources`)
создаются с включённым RLS без политик — доступ только у `service_role` (которым пишет парсер).

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

Для `direct_api`-источников (`twogis`/`timepad`/`kudago`) дискавери не нужен — задаётся `provider` (и для `twogis` ещё `api_query` + `event_type`), сразу `run --dry-run`.
