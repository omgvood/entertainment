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
    ├── direct_api: QuizPlease / 2ГИС / Timepad → ParsedEvent (без LLM)
    ├── vk_posts: посты VK-сообществ → префильтр → LLM (1 вызов/пачку)  [сервисный ключ]
    ├── vk_events: события-сообщества → ParsedEvent без LLM  [отключён: нужен user-токен]
    ├── telegram_posts: посты публичных каналов (t.me/s/) → префильтр → LLM (1 вызов/пачку)
    ├── generic: одобренные candidate_sources → JSON-LD / LLM (длинный хвост)
    ├── Discovery: краулер HTML / sitemap (для listing-источников)
    ├── Extraction: JSON-LD (Schema.org) → фолбэк LLM (Gemini / Groq / DeepSeek)
    ├── Dedup: новые URL + хеш листинга (raw_documents) — экономия LLM
    ├── Merge: кросс-источниковое слияние по id с учётом priority
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
| **Discovery** | `candidate_sources` | Поиск новых источников → модерация → `seeds.yaml` или **generic-парсер** (одобренные домены парсятся без ручного кода) |
| **Ingestion** | crawlers + API-клиенты (2ГИС/Timepad/VK/Telegram) + `raw_documents` | Получение и хранение сырого контента |
| **Extraction** | JSON-LD / LLM / теги + `classifiers` (префильтр) | Превращение сырья в `ParsedEvent` |
| **Merge** | `merge.py` + `SourceConfig.priority` | Кросс-источниковое слияние дублей по `id` с обогащением полей |
| **Analytics** | `source_health` + `source_quality` + `coverage_stats` | Здоровье источников, их ценность (уникальность) и полнота покрытия |

---

## Покрытие по категориям

Успех проекта измеряется **не числом источников, а полнотой покрытия спроса** по категориям.
Пользователю всё равно, откуда данные — важно, найдёт ли он, «куда сходить».

Текущее покрытие (Пермь):

| Категория | Источники | Статус |
|-----------|-----------|--------|
| Концерты | Timepad + generic (Пермская филармония) | ✅ |
| Театр | Timepad + generic (Театр-Театр) | ✅ |
| Выставки | Timepad + VK + Telegram | ✅ |
| Квизы | QuizPlease + Timepad | ✅ |
| Стендап | Timepad (partial) + Telegram | ⚠️ нет категории в Timepad; Telegram-каналы организаторов закрывают пробел |
| Квесты | 2ГИС | ✅ |
| Боулинг | 2ГИС | ✅ |
| Детям | Timepad (cat 379) + VK/Telegram | ⚠️ Timepad покрывает; нужны Telegram-каналы детских центров/театров |
| Экскурсии | Timepad (cat 461) + VK/Telegram | ⚠️ Timepad покрывает; нужны каналы музеев и экскурсионных бюро |
| Мастер-классы | Timepad (cat 453, 382) + VK/Telegram | ⚠️ Timepad покрывает; нужны каналы мастерских и арт-пространств |

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
| **VK-источники** | `vk-posts` (посты кураторских сообществ + префильтр + LLM, 1 вызов/пачку) — работает на сервисном ключе. `vk-events` (события-сообщества без LLM) готов, но отключён: `groups.search` требует user-токен | `sources/vk.py`, режимы `vk_posts`/`vk_events` |
| **Telegram-источник** | `telegram-posts` (посты публичных каналов через веб-превью `t.me/s/`, без авторизации) — fetch → префильтр → LLM (1 вызов/пачку). Каналы — объекты с `source_type`/`priority`/`enabled`; провайдер за абстракцией (HTML сейчас, MTProto позже) | `sources/telegram.py`, режим `telegram_posts` |
| **Общий классификатор** | `is_event_candidate(text, source_type)` — единый префильтр «пост похож на анонс» для VK/Telegram/будущих источников. Порог зависит от типа: агрегатор строже, организатор мягче | `classifiers.py` |
| **Source Type** | Природа источника (`api`/`aggregator`/`organizer`/`venue`/`social`) — управляет строгостью префильтра и осмыслением метрик | `config.py` (`SourceType`) |
| **Generic-парсер** | Одобренные в `candidate_sources` домены парсятся автоматически (JSON-LD → LLM в пределах бюджета) — замыкает цикл Discovery → Ingestion. **Запущен для Перми** (2026-06: филармония + Театр-Театр) | `sources/generic.py`, режим `generic` |
| **Discovery источников** | Поиск новых сайтов → скоринг → `candidate_sources` → модерация → `seeds.yaml` или generic | `sources/candidate_sources.py`, команда `discover-sources` |
| **Cross-source merge** | Слияние дублей одного события из разных источников по `id` с учётом `priority` и обогащением пустых полей | `merge.py`, `pipeline.py` |
| **Raw Documents** | Хранение сырья (HTML/JSON) для перепарса без повторного краулинга; здесь же хеш для дедупа | `db.py` (`save_raw_document`), таблица `raw_documents` |
| **Source Health** | Лог + агрегат по источникам: `events_found`, `errors`, `duration_sec`, `success_rate` | `db.py` (`record_source_health`), таблицы `source_health*` |
| **Source Quality** | Ежедневный снимок ценности источника: `unique_events_ratio` (сколько событий уникальны, а сколько дублируют другие источники в merge) — видно, стоит ли держать источник | `db.py` (`record_source_quality`), таблица `source_quality` |
| **Coverage Stats** | Ежедневный снимок покрытия по категориям — видно тренды и выпадение категорий | `db.py` (`record_coverage`), таблица `coverage_stats` |
| **Source priority** | Приоритет источника для разрешения дублей в merge | `config.py` (`SourceConfig.priority`) |
| **Venues (площадки)** | Площадки как отдельная сущность (`venues`) — source of truth для фронта. Наполнение: 2ГИС-источники (`direct_api`) пишут `date='always'`-карточки **напрямую в `venues`** (а не в `events`), enrich через `refresh-venues`, ручная пересборка `sync-venues`. Бекап в git через `export-venues` | `pipeline._run_direct_api_source`, `db.upsert_venues`, `cli.py`, таблица `venues`, `backup_venues.yml` |
| **2ГИС Playwright fallback** | Браузерный сбор venues как fallback-источник: `playwright_2gis.py` + команда `refresh-venues` + отдельный workflow раз в 2 недели. 2ГИС API — primary; Playwright включается при ошибке API или явным флагом. `source='manual'` не перезаписывается. | `sources/playwright_2gis.py`, `cli.py` (`refresh-venues`), `db.upsert_venues`, `refresh_venues.yml` |
| **Точный `source_url`** | Кнопка «Перейти к источнику» ведёт на конкретное событие/пост, а не на листинг/группу/канал. `event_url` (маркер `=== POST <url> ===` для VK/TG, `<a href>`/JSON-LD для web) резолвится в `source_url`; фолбэк на базовый URL (для VK/TG — на сам пост) при пустом/мусорном значении или домене-сокращателе/агрегаторе (`clck.ru`, `vk.cc`, `taplink.ws`, …) | `url_utils.resolve_event_url` (`JUNK_DOMAINS`), `extraction/jsonld.py`, промпты экстракторов |
| **Фильтр прошедших** | Репортажи о прошедшем («сегодня прошёл …») не попадают в БД: постфильтр `date < сегодня` в петлях VK/TG/batch + инструкция LLM игнорировать прошедшее время (ориентир «Сегодня» с днём недели) | `pipeline._is_past_event`, промпты экстракторов |
| **Синхронизация отмен** | Источники с `full_snapshot: true` (QuizPlease) дают полный срез за один вызов. После прогона `sync_source_events` удаляет из БД будущие события источника, которые пропали из ответа API — т.е. отменены. Защита от сбоя: при пустом результате синхронизация пропускается с WARNING. Прошедшие события удаляет TTL (1 день) | `db.sync_source_events`, `pipeline.py`, `config.SourceConfig.full_snapshot`, `seeds.yaml` |

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
│   │   ├── config.py               — Settings + SourceConfig + SourceType + TelegramChannelConfig + seeds
│   │   ├── models.py               — ParsedEvent, EventRow (Pydantic) + tags/fingerprint
│   │   ├── taxonomy.py             — закрытый набор тегов + TAGS_VERSION + авто-теги
│   │   ├── classifiers.py          — общий префильтр is_event_candidate (VK/Telegram/…)
│   │   ├── http_utils.py           — fetch_with_retry (3 попытки, exponential backoff)
│   │   ├── url_utils.py            — resolve_event_url: event_url → source_url + JUNK_DOMAINS
│   │   ├── pipeline.py             — оркестратор пайплайна + health/coverage/quality/merge
│   │   ├── merge.py                — кросс-источниковое слияние дублей по id (priority)
│   │   ├── db.py                   — upsert + cleanup + raw_documents/health/coverage
│   │   ├── dedup.py                — фильтрация известных URL (per_url)
│   │   ├── validator.py            — конвертация в EventRow + slug + fingerprint
│   │   ├── discovery/
│   │   │   ├── base.py             — абстрактный класс DiscoveryStrategy
│   │   │   ├── listing.py          — краулер HTML-листингов
│   │   │   └── sitemap.py          — краулер sitemap.xml
│   │   ├── extraction/
│   │   │   ├── base.py             — LLMExtractor ABC + ExtractorError/RateLimitError
│   │   │   ├── _errors.py          — is_rate_limit: классификация 429/503 SDK-исключений
│   │   │   ├── retry.py            — with_retry: backoff+jitter на RateLimitError
│   │   │   ├── fallback.py         — FallbackExtractor: ретрай + фолбэк цепочки провайдеров
│   │   │   ├── jsonld.py           — Schema.org JSON-LD парсер (перед LLM, без LLM)
│   │   │   ├── gemini_extractor.py — Google Gemini
│   │   │   ├── groq_extractor.py   — Groq Llama 3.3 70B
│   │   │   └── deepseek_extractor.py — DeepSeek V4 Flash (OpenRouter)
│   │   └── sources/
│   │       ├── quizplease.py       — QuizPlease REST API (api.quizplease.ru, без LLM)
│   │       ├── twogis.py           — 2ГИС Catalog API (без LLM)
│   │       ├── playwright_2gis.py   — 2ГИС через браузер (Playwright): fallback-сбор venues
│   │                                  (опц. dep [playwright], только для refresh_venues.yml)
│   │       ├── timepad.py          — Timepad API, широкая афиша; тип по категории (без LLM)
│   │       ├── kudago.py           — KudaGo API, широкая афиша (без LLM; Сочи-пилот, отключён)
│   │       ├── vk.py               — VK API: события-сообщества (без LLM) + посты (LLM)
│   │       ├── telegram.py         — Telegram: посты публичных каналов через t.me/s/ (LLM)
│   │       ├── generic.py          — generic-парсер одобренных candidate_sources (JSON-LD/LLM)
│   │       └── candidate_sources.py — Discovery новых источников (поиск → скоринг → БД)
│   ├── tests/                      — pytest тесты
│   │   ├── conftest.py             — фикстуры (Supabase-заглушки, sample HTML)
│   │   ├── test_classifiers.py     — is_event_candidate (VK/Telegram/типы источников)
│   │   ├── test_db.py              — upsert_events, upsert_venues, WriteStats
│   │   ├── test_discovery.py       — ListingDiscovery, SitemapDiscovery
│   │   ├── test_extractors.py      — DeepSeekExtractor (mock LLM) + is_rate_limit
│   │   ├── test_fallback.py        — FallbackExtractor (фолбэк/проброс/исчерпание) + with_retry
│   │   ├── test_generic.py         — generic-парсер (load_approved_domains, resolve_listing_url)
│   │   ├── test_jsonld.py          — extract_jsonld_events (Schema.org JSON-LD)
│   │   ├── test_kudago.py          — KudaGoClient (маппинг категорий)
│   │   ├── test_merge.py           — merge_rows (priority, enrichment, near_misses)
│   │   ├── test_playwright_2gis.py — parse_cards (HTML-фикстура, без браузера/сети)
│   │   ├── test_telegram.py        — parse_channel_html, TelegramHtmlProvider
│   │   ├── test_timepad.py         — TimepadClient._map_category, пагинация
│   │   ├── test_url_utils.py       — resolve_event_url (относит./мусор/поддомены/фолбэк)
│   │   ├── test_validator.py       — to_event_row, slug, fingerprint, to_venue
│   │   └── test_vk.py              — VkClient, event_group_to_parsed, fetch_wall_posts
│   ├── pyproject.toml              — зависимости и настройки пакета
│   └── README.md                   — документация парсера
│
├── supabase/
│   ├── migrations/                — SQL-миграции схемы (tags, fingerprint, raw_documents, …)
│   └── seeds/
│       ├── sochi_events.sql        — тестовые данные: события Сочи
│       └── venues_backfill.sql     — одноразовый перенос events(always) → venues (первичное наполнение)
│
├── web/                            — Next.js 16 фронтенд
│   ├── app/
│   │   ├── layout.tsx              — корневой layout (Метрика, верификация)
│   │   ├── globals.css             — глобальные стили
│   │   ├── sitemap.ts              — генерация sitemap.xml
│   │   ├── robots.ts               — robots.txt
│   │   ├── perm/
│   │   │   ├── page.tsx            — главная страница Перми (события)
│   │   │   ├── events/[slug]/page.tsx — страница события Перми
│   │   │   └── venues/
│   │   │       ├── page.tsx        — каталог площадок Перми
│   │   │       └── [slug]/page.tsx — детальная страница площадки Перми
│   │   └── sochi/
│   │       ├── page.tsx            — главная страница Сочи (события)
│   │       ├── events/[slug]/page.tsx — страница события Сочи
│   │       └── venues/
│   │           ├── page.tsx        — каталог площадок Сочи
│   │           └── [slug]/page.tsx — детальная страница площадки Сочи
│   ├── components/
│   │   ├── Header.tsx              — шапка с переключателем городов
│   │   ├── CityView.tsx            — сетка карточек + SEO-описание
│   │   ├── Sidebar.tsx             — панель фильтров
│   │   ├── EventCard.tsx           — карточка события
│   │   ├── VenueCard.tsx           — карточка площадки (ссылка на /{city}/venues/{slug}/)
│   │   ├── VenueDetail.tsx         — детальная страница площадки (фото, адрес, карта 2ГИС)
│   │   ├── VenuesCatalog.tsx       — каталог площадок города (страница /{city}/venues/)
│   │   └── VenuesSection.tsx       — секция «Постоянные места» на главной (до 8 карточек)
│   ├── lib/
│   │   ├── types.ts                — EventItem, VenueItem, City, CITY_CONFIG
│   │   ├── events.ts               — запросы к Supabase (getEventsByCity, getEventBySlug)
│   │   ├── venues.ts               — запросы к Supabase (getVenuesByCity, getVenueBySlug)
│   │   ├── venue-meta.ts           — SEO-хелперы площадок (metadata, JSON-LD, род. падеж города)
│   │   ├── venue-styles.ts         — стили карточек/бейджей по типу площадки
│   │   ├── filters.ts              — клиентская фильтрация событий
│   │   └── supabase.ts             — Supabase client (anon key, read-only)
│   ├── CLAUDE.md                   — инструкции Claude Code для фронтенда
│   ├── AGENTS.md                   — инструкции агентов
│   └── README.md                   — документация фронтенда
│
├── .github/workflows/
│   ├── parse.yml                   — CI/CD: ежедневный запуск парсера
│   ├── discover_sources.yml        — еженедельный поиск новых источников
│   ├── backup_venues.yml           — еженедельный снимок venues в git (бекап)
│   └── refresh_venues.yml          — сбор venues из 2ГИС раз в 2 недели (API / Playwright fallback)
│
├── input-output/                   — образцы JSON/xlsx/yaml, PDF-экспорт readme, ключи SSH
├── prototype/                      — ранний UI-прототип (HTML/CSS)
└── docs/
    ├── Конвертер yaml-xlsx/        — утилиты seeds.yaml ↔ Excel
    │   ├── make_seeds_excel.py     — генерирует seeds_editor.xlsx из seeds.yaml (openpyxl)
    │   └── excel_to_seeds.py       — конвертирует seeds_editor.xlsx обратно в seeds.yaml
    └── Условия бесплатного использования API Яндекс.md
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
| `--mode per_url\|batch_listing\|direct_api\|vk_events\|vk_posts\|telegram_posts\|generic` | Переопределить режим извлечения |

Возвращает код выхода 0 если хотя бы половина событий извлечена успешно, иначе 1.

---

### `config.py` — конфигурация

Три датакласса:

**`Settings`** — загружается из переменных окружения:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY` (для DeepSeek через OpenRouter)
- `TWOGIS_API_KEY`, `TIMEPAD_TOKEN`
- `VK_SERVICE_KEY` — сервисный ключ VK mini-app (для источников `vk-events`/`vk-posts`)
- `SEARCH_PROVIDERS` (дефолт `serper`) — поисковики Discovery через запятую, порядок = приоритет
  (`serper,brave,duckduckgo`); `SERPER_API_KEY`, `BRAVE_API_KEY` — ключи keyed-провайдеров;
  `SEARCH_TIMEOUT_SECONDS` (дефолт 20), `SEARCH_QUERY_LIMIT` (дефолт — по числу шаблонов)
- `GENERIC_LLM_BUDGET` (дефолт 10), `GENERIC_DOMAIN_BUDGET` (дефолт 20) — лимиты generic-парсера
- `POST_BATCH_SIZE` (дефолт 5) — сколько VK/TG-постов склеивать в один LLM-вызов
- `LLM_PROVIDER` (gemini / groq / deepseek, дефолт: gemini) — основной провайдер
- `LLM_FALLBACK_PROVIDERS` (дефолт `gemini,groq`) — цепочка для ретрая/фолбэка при 429/503
- `LLM_RETRY_ATTEMPTS` (дефолт 3) — попыток на провайдера при rate-limit перед переключением
- `GEMINI_MODEL`, `GROQ_MODEL`, `DEEPSEEK_MODEL` — модели провайдеров

**`SourceConfig`** — конфигурация одного источника из `seeds.yaml`:
- `name` — уникальное имя источника
- `extraction_mode` — `per_url` / `batch_listing` / `direct_api` / `vk_events` / `vk_posts` / `telegram_posts` / `generic`
- `priority` — приоритет источника при кросс-источниковом merge (выше — побеждает), дефолт `0`
- `full_snapshot` — `true` если один вызов гарантированно возвращает **все** будущие события источника. Включает `sync_source_events` — автоудаление отменённых событий. Устанавливать только при уверенности в полноте: для `batch_listing` с пагинацией/lazy-loading и для `vk_posts`/`telegram_posts`/`generic` — **не устанавливать**
- Для `per_url`/`batch_listing`: `kind` (listing/sitemap), `url`, `url_pattern` (regex)
- Для `direct_api`: `provider` (`quizplease` / `twogis` / `timepad` / `kudago`). `quizplease` требует `quizplease_city_id` (ID города в API, hardcoded в seeds); `twogis` — `api_query` + `event_type`; `timepad`/`kudago` тип определяют сами по категории
- Для `vk_events`: опц. `vk_city_id` (ID города VK для `groups.search`). Для `vk_posts`: `vk_groups` — список screen-name'ов кураторских сообществ
- Для `telegram_posts`: `telegram_sources` — список каналов (объекты `channel` / `source_type` / `priority` / `enabled`)

**`SourceType`** (enum) — природа источника: `api` / `aggregator` / `organizer` / `venue` / `social`.
Управляет строгостью префильтра (`classifiers.is_event_candidate`) и осмыслением метрик качества.

**`TelegramChannelConfig`** — один Telegram-канал: `channel` (screen-name без `https://t.me/`),
`source_type` (дефолт `social`), `priority` (дефолт `40`), `enabled` (дефолт `true`). Объект, а не
строка — чтобы отключать канал и менять приоритет без правок кода.

**`CityConfig`** — список источников одного города.

**`load_seeds()`** — читает `config/seeds.yaml`, возвращает словарь `{city: CityConfig}`.

---

### `config/seeds.yaml` — источники событий

Конфигурационный файл, описывающий откуда брать события для каждого города.

```yaml
cities:
  perm:
    sources:
      # QuizPlease: SPA (Nuxt) — сайт не отдаёт события в статическом HTML.
      # Используем REST API api.quizplease.ru напрямую (city_id=37 зафиксирован).
      - name: quizplease
        extraction_mode: direct_api
        provider: quizplease
        quizplease_city_id: 37
        priority: 60
        full_snapshot: true  # API обходит все страницы → включает sync_source_events

      - name: twogis-bowling
        extraction_mode: direct_api
        provider: twogis
        api_query: "боулинг Пермь"
        event_type: bowling
        priority: 70
```

**Режимы извлечения:**
- `direct_api` — вызов внешнего API (QuizPlease / 2ГИС / Timepad / KudaGo), маппинг JSON → `ParsedEvent` без LLM
- `batch_listing` — скачивает страницу целиком. Сначала пробует Schema.org JSON-LD (бесплатно, без LLM); если не нашёл — один LLM-вызов извлекает все события. Пропускается целиком, если HTML не менялся (хеш в `raw_documents`). Только для статических HTML-страниц — SPA-сайты (Nuxt/Next/React) не работают
- `per_url` — дискавери находит N URL, затем N отдельных LLM-вызовов для каждого
- `vk_events` — VK-сообщества типа «событие» (нативные `start_date`/`place`) → `ParsedEvent` без LLM
- `vk_posts` — посты со стен `vk_groups`: префильтр (дата/маркеры/билеты) → `extract_many` пачками по `POST_BATCH_SIZE` постов (параллельно, с ограничением `_POST_CONCURRENCY`)
- `telegram_posts` — посты публичных каналов `telegram_sources` (веб-превью `t.me/s/`, без авторизации): префильтр (строгость по `source_type`) → `extract_many` пачками по `POST_BATCH_SIZE` постов
- `generic` — одобренные в `candidate_sources` домены: JSON-LD, иначе LLM в пределах бюджета (длинный хвост)

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
| `event_url` | str? | Прямая ссылка на страницу/пост события (промежуточное поле, в БД не пишется — резолвится в `source_url`, см. ниже) |
| `tags` | list[str] | Теги из закрытого набора `taxonomy.ALLOWED_TAGS` (валидатор отбрасывает чужие) |

Валидаторы: формат даты, формат времени, `price_max >= price_min`, фильтрация тегов.

> **`event_url` → `source_url`.** LLM/JSON-LD возвращают `event_url` — прямую ссылку на конкретное
> событие (из маркера `=== POST <url> ===` для VK/TG, из `<a href>`/JSON-LD `url`/`@id` для web).
> Колонки `event_url` в БД нет: `db.upsert_events` исключает поле, а `url_utils.resolve_event_url`
> превращает его в `source_url`. Деталь — раздел «Резолв `source_url`».

**`Venue`** (Pydantic) — строка таблицы `venues` (контур площадок, НЕ events):

| Поле | Тип | Описание |
|------|-----|---------|
| `id` | str | `{city}-{slug}` — детерминированный |
| `city` | str | `perm` / `sochi` |
| `name` | str | Название заведения |
| `type` | str | `bowling` / `billiards` / `karting` / `quest` / ... |
| `address` | str? | Адрес |
| `district` | str? | Район |
| `image_url` | str? | Фото |
| `source` | str | `manual` / `twogis` / `playwright` |

Строки с `source='manual'` — единственные, которые автосбор (twogis/playwright) не перезаписывает.

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
2. Для каждого вызывает нужный runner (`_run_per_url_source`, `_run_batch_source`, `_run_direct_api_source`, `_run_vk_events_source`, `_run_vk_posts_source`, `_run_telegram_posts_source`, `_run_generic_source`)
3. Пишет здоровье источника в `source_health` (`record_source_health`)
4. **Cross-source merge** (`merge.merge_rows`): группирует строки по `id` (= city+slug), выбирает победителя по `priority`, обогащает его пустые поля из проигравших; в боевом режиме подмешивает существующие строки из БД (`fetch_events_by_ids`), чтобы не даунгрейдить карточку источником с меньшим приоритетом
5. После каждого источника (до merge): если `source.full_snapshot` и извлечено > 0 событий — вызывает `sync_source_events`, удаляя будущие события данного источника, которых нет в текущем прогоне (отменены на сайте)
6. Upsert в БД (слияние делит `id` → upsert по slug перезаписывает на месте, удалений не нужно)
7. Очистка: `cleanup_old_events` (TTL 1 день) + `cleanup_old_raw_documents` (TTL) + снимки `record_coverage` и `record_source_quality` (доля уникальных событий по источникам через `_source_quality`)
7. Возвращает `PipelineResult` (discovered / new / extracted / failed / written / **merged** / **near_misses** / **merged_by_source**)

> **`merged_by_source`** (разбивка «источник-проигравший → победитель») — KPI для оценки реальной ценности нового источника: видно, сколько событий VK уникальны, а сколько дублируют Timepad. **`near_misses`** (та же площадка+дата, разные названия) — сигнал-кандидат для будущего fuzzy-матчинга, пока только логируется.

**`_run_per_url_source(source, extractor, client, dry_run)`**
- Discovery (listing или sitemap) → список URL
- `filter_new_urls()` — убирает уже известные
- Для каждого нового URL: скачать HTML → `extractor.extract()` → `to_event_row()`
- Архивирует сырьё в `raw_documents` (для перепарса)

**`_run_batch_source(source, extractor, supabase, city, dry_run)`**
- Скачать страницу-листинг целиком; посчитать хеш → если не менялся, пропустить (хеш в `raw_documents`)
- Сначала JSON-LD (`extract_jsonld_events`, без LLM); если пусто — один вызов `extractor.extract_many()`
- После успешного извлечения архивирует сырьё + фиксирует хеш в `raw_documents`
- Batch-вариант эффективнее для статических страниц с полным расписанием; SPA-сайты (Nuxt/Next) требуют `direct_api` или Playwright

**`_run_direct_api_source(source, client, provider_keys)`**
- Диспетчер по `source.provider`: `QuizPleaseClient` / `TwoGisClient` / `TimepadClient` / `KudaGoClient`
- Каждый возвращает `(ParsedEvent, source_url)` без LLM → маппинг и запись в БД

**Резолв `source_url`** (`url_utils.resolve_event_url(event_url, base_url)`) — общий для VK/Telegram/batch/generic:
- Цель — чтобы кнопка «Перейти к источнику» вела на **конкретное событие/пост**, а не на листинг/группу/канал.
- `event_url` от LLM/JSON-LD: относительные пути web-листингов достраиваются до абсолютного через
  `urljoin(base_url, event_url)`, абсолютные ссылки остаются как есть.
- **Фолбэк на `base_url`** (листинг / `https://vk.com/{group}` / `https://t.me/{channel}` / ссылка на пост), если
  `event_url` пуст, равен мусору (`#`, `javascript:void(0)`) или ведёт на **домен-сокращатель/агрегатор**
  (`clck.ru`, `vk.cc`, `bit.ly`, `taplink.ws`, `goodsbuy.by`, …) — такие LLM иногда ошибочно вытаскивает из тела
  поста. Список — `url_utils.JUNK_DOMAINS`; проверка ловит и поддомены (`heartharmony.taplink.ws`).

**Фильтр прошедших событий** (`_is_past_event(date, today)`) — в петлях VK/Telegram/batch:
- Отсекает репортажи о прошедшем («сегодня прошёл крестный ход»): если `date != 'always'` и `date < сегодня` —
  событие пропускается до записи в БД. `today` берётся один раз на источник.
- **Граничный случай «сегодня».** `date == сегодня` фильтр НЕ ловит (событие могло быть утром, а пост вечером) —
  это закрывает промпт: LLM инструктирована игнорировать посты в прошедшем времени, ориентируясь на дату
  «Сегодня» (передаётся с днём недели на русском: `Воскресенье, 14 июня 2026 года`).

---

### `db.py` — работа с базой данных

**`make_client(settings)`** — создаёт Supabase-клиент с `service_role_key` (обходит RLS, разрешена запись).

**`upsert_events(client, events)`**
- Записывает список `EventRow` в таблицу `events`
- Upsert по `conflict="slug"` — если slug уже есть, обновляет поля
- Возвращает `WriteStats` (inserted, updated, errors)

**`upsert_venues(client, venues)`**
- Записывает список `Venue` в таблицу `venues` через upsert по `conflict="id"`
- **Стратегия защиты ручного ввода:** перед записью выбирает id с `source='manual'` и исключает их из payload — ручные строки недосягаемы для автосбора
- Возвращает `WriteStats`

**`cleanup_old_events(client, city, days_to_keep=1)`**
- Удаляет события: `date < сегодня - 1 день AND date != 'always'`
- Сохраняет: постоянные места (`always`) и вчерашние события (буфер на часовые пояса UTC vs Пермь/Сочи)
- Вызывается автоматически после каждого прогона

**`sync_source_events(client, source, city, current_ids)`**
- Удаляет **будущие** события (`date >= сегодня`) конкретного источника, которых нет в `current_ids`
- Используется только для источников с `full_snapshot=True` — гарантирующих полный срез
- Защита от сбоя: при пустом `current_ids` (упавший парсинг) — ничего не удаляет, пишет WARNING
- Не пересекается с `cleanup_old_events` (та чистит прошлые, эта — отменённые будущие)

**Merge (`fetch_events_by_ids`):**
- `fetch_events_by_ids(client, ids)` — существующие события по `id` (чанками по 100) → `EventRow`; используется кросс-источниковым merge, чтобы обогащать/не даунгрейдить карточки прошлых прогонов

**Ingestion (`raw_documents`):**
- `save_raw_document(client, source, url, content, content_type, content_hash)` — upsert сырья по `url`
- `get_raw_document_hash(client, url)` — хеш последнего сохранённого контента (для дедупа `batch_listing`)
- `cleanup_old_raw_documents(client, days=120)` — TTL-очистка сырья

**Analytics (`source_health`, `source_quality`, `coverage_stats`):**
- `record_source_health(client, source, city, events_found, errors, duration_sec, last_error)` —
  пишет строку в лог `source_health` и пересчитывает агрегат `source_health_agg` (включая `success_rate`)
- `record_source_quality(client, city, per_source)` — снимок ценности источников в `source_quality`
  (`unique_events_ratio` = доля событий, не проигравших merge другому источнику)
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

**`to_venue(parsed, city, source)`**
- Конвертирует `ParsedEvent` (с `date='always'`) → `Venue` для таблицы `venues`
- `slug` строится из `venue_name` (а не из `title`, т.к. у площадки нет даты-суффикса: `bowling-plus`)
- `id = {city}-{slug}` — детерминированный ключ; повторный сбор того же заведения = upsert на месте

**`_fingerprint(title, date, venue)` / `_normalize(s)`**
- `_normalize` приводит строку к канону: нижний регистр, `ё→е`, без пунктуации, схлопнутые пробелы
- `_fingerprint` = `sha256(normalize(title)|date|normalize(venue))[:16]`
- Кросс-источниковый дедуп фактически выполняется по **`id`** (= `city`+`slug`, а `slug` детерминирован из `title`+`date`) в `merge.py` — это публичный ключ карточки, и БД держит одну строку на `slug`. Поле `fingerprint` хранится как вспомогательный сигнал (тоньше `id`: учитывает площадку) для возможной будущей аналитики; **без UNIQUE**.

**`_make_slug(title, date)`**
- Кириллица → транслитерация (встроенный словарь: я→ya, ж→zh, ш→sh и т.д.)
- Unicode NFKD нормализация → ASCII
- Не-буквенные символы → дефис
- Обрезка до 80 символов
- Суффикс даты: `kviz-v-bare-2026-06-01`
- Для `date='always'` дата не добавляется: `bowling-plus`

---

### `merge.py` — кросс-источниковое слияние

Одно событие может прийти из Timepad, VK и сайта организатора. `merge_rows(incoming, existing, priorities)`
схлопывает дубли **по `id`** (= `city`+`slug`, а `slug` детерминирован из `title`+`date`, поэтому
строки одного события обязаны иметь один `id`, и БД всё равно держит одну строку на `slug`).

- **Победитель** — источник с наибольшим `priority`; при равенстве выигрывает свежая строка прогона (incoming), а не БД.
- **Обогащение** — пустые поля победителя (`time_start`, `image_url`, `description`, `organizer`, `district`, цена, теги) добираются из проигравших. Итог — карточка лучше любого отдельного источника.
- **Без удалений** — все слитые строки делят `id`, upsert по `slug` перезаписывает на месте.
- **Чистые функции** — без обращения к БД, тестируются изолированно (`tests/test_merge.py`).
- **Fuzzy-матчинг отложен** — нормализация уже ловит регистр/пунктуацию/ё; разные названия одного события (`near_misses`) пока только считаются, не схлопываются.

Приоритеты в `seeds.yaml`: `timepad` 100, `vk-events` 80, `twogis-*` 70, `quizplease` 60, `telegram-posts` 45, `vk-posts` 40, `generic` 20.

---

### `http_utils.py` — общие HTTP-утилиты

**`fetch_with_retry(client, url, params, *, retries=3, timeout=15)`** — GET с повторными попытками:
- 3 попытки с exponential backoff (`asyncio.sleep(2**attempt)`)
- Retry на 5xx и `httpx.TimeoutException`; 4xx считаются успехом (ошибка конфигурации, не сети)
- Используется в `QuizPleaseClient._fetch_page`; в будущем можно перевести и другие провайдеры

---

### `url_utils.py` — резолв `source_url` события

Превращает `event_url` (из LLM/JSON-LD/маркера поста) в финальный `source_url`. Общий для
VK/Telegram/batch/generic — чтобы кнопка «Перейти к источнику» вела на **конкретное событие/пост**,
а не на листинг/группу/канал. Логика вынесена из `pipeline.py`, чтобы переиспользоваться без дублей.

**`resolve_event_url(event_url, base_url) -> str`** — приоритеты:
1. Пусто / мусор (`""`, `#`, `javascript:void(0)` из `JUNK_URLS`) → фолбэк на `base_url`.
2. Относительный путь (`/afisha/event-slug`, без `netloc`) → достраивается через `urljoin(base_url, …)`.
3. Абсолютный URL на **мусорном домене** (`JUNK_DOMAINS`) → фолбэк на `base_url` (с логом `resolve_event_url.junk_domain`).
4. Иначе — абсолютный `event_url` как есть.

**`JUNK_DOMAINS`** — сокращатели/трекеры/агрегаторы, которые LLM ошибочно тащит из тела поста:
`clck.ru`, `vk.cc`, `bit.ly`, `t.co`, `goo.gl`, `tinyurl.com`, `ow.ly`, `is.gd`, `taplink.ws`,
`taplink.cc`, `goodsbuy.by`. Проверка ловит и **поддомены** (`heartharmony.taplink.ws`) через
суффиксное сравнение `domain == junk or domain.endswith("." + junk)`.

> Примеры: `https://vk.com/wall-80718152_8481` (пост, как есть), `/afisha/show` + `base=teatr.com`
> → `https://teatr.com/afisha/show`, `https://heartharmony.taplink.ws/` → фолбэк на ссылку группы.

---

### `sources/vk.py` — VK API

**`VkClient`** — клиент VK (`api.vk.com/method`, сервисный ключ mini-app, `VK_SERVICE_KEY`). Сервисному
ключу доступны только методы открытых данных (`groups.search`, `groups.getById`, `wall.get`);
`newsfeed.search` недоступен — на нём ничего не строим. Троттлинг ~3 rps, обработка error envelope
(код 6 → ретрай, 15/30 → пропуск закрытой группы).

Два режима:
- **`vk_events`** — `search_event_groups(city)`: VK-сообщества типа «событие» имеют нативные
  `start_date`/`finish_date`/`place` → `event_group_to_parsed()` маппит напрямую, **без LLM**.
  ⚠️ **Отключён в seeds**: `groups.search` запрещён сервисному ключу (Access denied, code 15) —
  нужен пользовательский токен. Код и тесты готовы, ждут user-токена.
- **`vk_posts`** — `fetch_wall_posts(group)`: посты со стен `vk_groups`. **Работает на сервисном
  ключе** (`wall.get` доступен; закрытые группы пропускаются по `VkApiError`). Перед LLM — **префильтр**
  `classifiers.is_event_candidate()` (есть дата/время, маркеры «билеты»/«регистрация»/«вход», ссылка на Timepad)
  и фильтр свежести 14 дней; дедуп постов через `raw_documents` (хеш текста). Посты-кандидаты
  (≤20/группу) бьются на пачки по `POST_BATCH_SIZE` (дефолт 5) → один `extract_many` на пачку,
  пачки параллельно с `_POST_CONCURRENCY`. Каждый пост в пачке помечается маркером
  `=== POST <url> ===` (промпты ОБЯЗАНЫ брать из него `event_url`) → `resolve_event_url`; пусто →
  фолбэк на группу. `save_raw_document` — только при успешном возврате пачки (включая пустой
  результат); при сбое (rate-limit/парс) пост ретраится в следующем прогоне.
  `source_url` события — **прямая ссылка на пост** (`https://vk.com/wall{owner}_{id}`).

> Префильтр `is_event_candidate` вынесен в общий модуль `classifiers.py` (используется и VK, и Telegram).

### `sources/telegram.py` — Telegram (посты публичных каналов)

Telegram-каналы локальных организаторов (стендап/квизы/театры) в РФ часто активнее VK и анонсируют
раньше. Публичные каналы доступны **без авторизации** через веб-превью `https://t.me/s/{channel}`.

- **`TelegramProvider`** (ABC) — абстракция провайдера. Единственная реализация —
  **`TelegramHtmlProvider`** (парсит веб-превью). Если HTML-превью сломают/заблокируют или понадобятся
  закрытые каналы — добавится второй провайдер (MTProto/telethon) без правок pipeline. Заглушку заранее
  не делаем — добавим по реальной необходимости.
- **`parse_channel_html`** — чистая функция: HTML → `[{text, url, date_unix}]` (тестируется без сети).
  Посты без текста (только фото) пропускаются. Структура селекторов задокументирована в коде —
  чинить тут, если разметка `t.me/s/` поедет.
- **Режим `telegram_posts`** (`pipeline._run_telegram_posts_source`): зеркало `vk_posts`. Каналы —
  объекты `TelegramChannelConfig` (можно отключать/менять приоритет). Префильтр
  `classifiers.is_event_candidate(text, source_type)` — **строгость зависит от типа канала**: у агрегатора
  (много рекламы/мемов) нужна дата И маркер, у организатора достаточно одного сигнала. Свежесть 14 дней,
  дедуп через `raw_documents`, `extract_many` пачками по `POST_BATCH_SIZE` (параллельно, `_POST_CONCURRENCY`).
  `source_url` события — **прямая ссылка на конкретный пост** (`https://t.me/{channel}/{id}`): пост помечается
  маркером `=== POST <url> ===`, LLM возвращает его в `event_url`, а `resolve_event_url` подставляет в `source_url`.
  Фолбэк — на `post_url` самого поста, а не на канал (см. «Резолв `source_url`» выше).

### `sources/generic.py` — generic-парсер кандидатов

Замыкает цикл **Discovery → Ingestion**: одобренные в `candidate_sources` (`status='approved'`) домены
парсятся без ручного кода под каждый сайт.

- **`load_approved_domains`** — домены города по убыванию `score`, не больше `GENERIC_DOMAIN_BUDGET` (защита времени прогона).
- **`resolve_listing_url`** — URL листинга: кэш `listing_url` (если `last_verified` свежее 30 дней) → `sample_urls` с event-path-хинтом → пробинг `/afisha` `/events` `/raspisanie` `/schedule`. Результат кэшируется обратно.
- **Извлечение** — сначала JSON-LD (бесплатно, хватает доменам с `has_jsonld_event`), иначе `extract_many` в пределах `GENERIC_LLM_BUDGET` LLM-вызовов на прогон; hash-дедуп листинга через `raw_documents`.
- **Health per-domain** — `source='generic:{domain}'`; хронически падающий домен демотируется вручную (`status='broken'`) по данным `source_health_agg`.
- **Тип события из JSON-LD** — для JSON-LD-ветки тип берётся из Schema.org `@type` через
  `extraction/jsonld.py` (`MusicEvent → concert`, `TheaterEvent → theater`, …), а не хардкодится.
  Родовой `Event` падает на `default_type`. Деталь — раздел «`extraction/jsonld.py`».

**Текущее состояние (Пермь, запущен 2026-06):** включён в `seeds.yaml` (priority 20), бюджеты
`GENERIC_DOMAIN_BUDGET=5` / `GENERIC_LLM_BUDGET=3`. Одобренные домены:

| Домен | listing_url | Извлечение | Категория |
|-------|-------------|-----------|-----------|
| `filarmonia.online` | `/afisha` | JSON-LD (бесплатно) | концерты (Пермская филармония) |
| `teatr-teatr.com` | `/afisha/` | LLM (1 вызов) | театр / детям (Театр-Театр) |

Оба дают `unique_events_ratio = 1.0` — события не дублируют Timepad/VK (это первоисточники
организаторов, а не реагрегаторы). Домены `permopera.ru` / `permm.ru` / `permtuz.ru` /
`teatr-umosta.ru` оставлены в `status='new'`: их афиши JS-рендерятся, статический HTML пуст —
им нужен специализированный источник, а не generic.

> ⚠️ Generic — инструмент **«длинного хвоста»** статических сайтов. SPA/JS-рендеринг и анти-бот
> сайты он не возьмёт — такие при необходимости получают специализированный источник.
>
> ℹ️ **Discovery переведён на keyed-провайдеры.** Бесплатный `DuckDuckGoProvider` отдавал HTTP 202
> (антибот) → 0 кандидатов, поэтому добавлены `SerperProvider` (основной) и `BraveProvider` (резерв)
> за тем же ABC `SearchProvider`, с цепочкой fallback и circuit breaker. Для работы нужен
> `SERPER_API_KEY` в окружении/Secrets. До набора ключа домены можно по-прежнему добавлять вручную
> (INSERT в `candidate_sources` с `first_provider='manual'`). Детали — раздел «`candidate_sources.py`».

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
- `ExtractorError` — исключение при невалидном ответе LLM (контент/JSON/схема)
- `RateLimitError(ExtractorError)` — подкласс для 429/503 (квота/перегрузка). Отделён, чтобы
  ретрай/фолбэк реагировали именно на лимиты, а не на контент-ошибки
- `LLMExtractor` ABC:
  - `extract(html, source_url) -> ParsedEvent` — одно событие с детальной страницы
  - `extract_many(html, source_url) -> list[ParsedEvent]` — список событий со страницы-листинга

---

**`_errors.py`** — классификация исключений SDK

- **`is_rate_limit(exc) -> bool`** — отличает лимит (429/503) от остального. Двойная проверка:
  по структурному коду (`.status_code` у groq/openai, `.code` у `google.genai.errors.APIError`) и
  по подстрокам в тексте (`resource_exhausted`, `unavailable`, `overloaded`, `429`, `503`) — на
  случай, если SDK обернул ошибку без кода. Экстракторы зовут её в `except` блоках API-вызова и
  поднимают `RateLimitError` вместо `ExtractorError`, когда она вернула `True`.

---

**`retry.py`** — повтор LLM-вызова на лимите

- **`with_retry(factory, *, attempts=3, base_delay=2.0)`** — зовёт корутину-фабрику, повторяя
  **только** на `RateLimitError`. Экспоненциальный backoff + **jitter** (`base*2**n + random(0.5,1.5)`)
  — jitter разносит синхронно проснувшиеся корутины, чтобы не бить API одновременно и не продлевать
  429. После `attempts` попыток пробрасывает последний `RateLimitError`. `attempts` берётся из
  `LLM_RETRY_ATTEMPTS`.

---

**`fallback.py`** — `FallbackExtractor` (композит ретрай + фолбэк провайдеров)

Оборачивает цепочку `[(provider, extractor)]` и сам реализует `LLMExtractor` — поэтому
подставляется вместо одиночного экстрактора **без правок в pipeline** (VK/TG/batch/generic/per_url
получают устойчивость прозрачно). Строится в `cli._make_extractor_chain` из `LLM_FALLBACK_PROVIDERS`
(дефолт `gemini,groq`), включая только провайдеров с заданным ключом.

- **Логика** (общий приватный `_run` для `extract` и `extract_many`): начиная с `_preferred_idx`,
  каждый провайдер зовётся через `with_retry`. На устойчивом `RateLimitError` — лог `fallback.switch`
  и переход к следующему. Обычный `ExtractorError` (контент/JSON) — **проброс без фолбэка** (не
  маскируем баги, не двоим расход квоты).
- **Stateful advance-only индекс без Lock.** Выгоревший провайдер сдвигает общий `_preferred_idx`
  вперёд — следующие корутины сразу стартуют со следующего, не бомбя мёртвого. `asyncio`
  однопоточный → чтение/запись int между `await` атомарны, `asyncio.Lock` не нужен. Индекс растёт
  до `len(providers)` (маркер «пул исчерпан»); guard в начале метода короткозамыкает с
  `RateLimitError`, не уходя в `IndexError`. Назад к gemini в рамках прогона не возвращаемся.

> ⚠️ **Лимиты free-tier — узкое место для VK/TG-батчей** (подробнее — «LLM-провайдеры»):
> DeepSeek без кредитов OpenRouter отдаёт `402` (в цепочку по умолчанию не включён); groq
> `llama-3.1-8b-instant` (TPM 6000) не тянет пачку из 5 постов (`413`) — для фолбэка нужен
> `llama-3.3-70b-versatile`.

---

**`jsonld.py`** — Schema.org JSON-LD парсер (без LLM)

Бесплатный путь **перед** LLM: многие сайты встраивают `<script type="application/ld+json">`
с готовым `@type: Event`. Если блок есть и полный — LLM не нужен.

- **`extract_jsonld_events(html, default_type) -> list[ParsedEvent]`** — парсит все JSON-LD блоки,
  разворачивает `@graph`/массивы, маппит каждый `Event` в `ParsedEvent`. Записи без обязательных
  полей (title/date/venue/address) пропускаются — их доберёт LLM-фолбэк.
- **Тип события из `@type`** (`_SCHEMA_TYPE_MAP` + `_resolve_type`): Schema.org-подтип маппится в
  `EventType` — `MusicEvent → concert`, `TheaterEvent → theater`, `ComedyEvent → standup`,
  `ExhibitionEvent → exhibition`, `ScreeningEvent → cinema`, `Festival → festival`,
  `EducationEvent → education`, `SportsEvent → sport`, `BusinessEvent → business`. Родовой `Event`
  и незнакомые подтипы падают на `default_type` источника. Поэтому direct_api/generic-домены с
  известным типом не ломаются, а размеченные сайты (филармония) получают **точный** тип, а не `other`.
- **Цена/время/адрес/фото** — `_parse_offers` / `_parse_datetime` / `_parse_location` / `_parse_image`
  достают поля из вложенных Schema.org-объектов (`Offer`, `PostalAddress`, `Place`).

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

---

### Алгоритмы извлечения по режимам

Каждый `extraction_mode` реализует отдельную ветку в `pipeline.py`. Ниже — пошаговый алгоритм каждого режима, включая где и как используется LLM.

---

#### `direct_api` — API без LLM

Вызов внешнего API с маппингом JSON → `ParsedEvent`. LLM не вызывается ни разу.

```
seeds.yaml (provider + параметры)
  │
  ▼ _fetch_direct_api_items()  ← диспетчер по provider
  │
  ├── quizplease → QuizPleaseClient.search(city_id)
  │       Пагинация по per_page=30 до total_pages.
  │       _map_game(): date «DD.MM.YYYY HH:MM» → YYYY-MM-DD + HH:MM
  │       source_url = game["url"] или /game/{id} (UUID), иначе schedule_url
  │
  ├── twogis → TwoGisClient.search(api_query, event_type)
  │       Пагинация по 10 карточек до max_items=50.
  │       _item_to_event(): name/address/district/photo → ParsedEvent
  │       date = 'always' (постоянные места, у 2ГИС нет цен в листинге)
  │       source_url = 2gis.ru/{city}/search/{query}
  │
  ├── timepad → TimepadClient.search(city_slug)
  │       Пагинация limit/skip, starts_at_min=сегодня, до max_items=500.
  │       _map_category(): categories → EventType (концерт/выставка/квиз/…)
  │       source_url = реальная ссылка на событие timepad.ru/event/…
  │
  └── kudago → KudaGoClient.search(city_slug)   [ОТКЛЮЧЁН — данные устарели]
          _map_event(): categories → EventType
          source_url = kudago.com/…
  │
  ▼ to_event_row(): ParsedEvent → EventRow
      slug = transliterate(title) + '-' + date
      tags = default_tags_for_type(type)  ← авто-теги без LLM
```

---

#### `batch_listing` — листинг + JSON-LD → LLM-фолбэк

Одна HTML-страница со всеми событиями. **1 LLM-вызов** на источник (если JSON-LD не сработал).

```
source.url (URL страницы-листинга)
  │
  ▼ httpx GET (timeout 20s, follow_redirects)
  │
  ▼ SHA-256 хеш HTML
  │   └── raw_documents.get_hash(url) == hash? → ПРОПУСТИТЬ весь источник
  │       (листинг не менялся с прошлого прогона, события в БД актуальны)
  │
  ▼ 1. JSON-LD (Schema.org Event) — бесплатно, без LLM
  │   extraction/jsonld.py → extract_jsonld_events(html, event_type)
  │   └── нашёл события → идти к шагу 3
  │
  ▼ 2. LLM-фолбэк (если JSON-LD дал 0 событий)
  │   Очистка HTML → extractor.extract_many(cleaned_html, url)
  │   → list[ParsedEvent]  ← ОДИН вызов LLM на весь листинг
  │
  ▼ 3. Постфильтр + маппинг каждого ParsedEvent
  │   _is_past_event(date, today) → пропустить репортажи о прошедшем
  │   resolve_event_url(event_url, source.url) → source_url события
  │   to_event_row() → EventRow
  │
  ▼ 4. Сохранить HTML в raw_documents (хеш + сырьё для перепарса)
  │
  ▼ EventRow[] → merge → upsert
```

> ⚠️ `batch_listing` работает только со **статическими HTML-страницами**. SPA-сайты (Nuxt/React/Vue)
> отдают пустой скелет — ноль событий. Такие источники переводятся на `direct_api`.

---

#### `per_url` — один LLM-вызов на каждый URL

Для сайтов, где каждое событие — отдельная страница. **N LLM-вызовов** (по числу новых URL).

```
source.url (URL страницы-листинга или sitemap)
  │
  ▼ Discovery (kind = listing | sitemap)
  │   listing: httpx GET → selectolax → все <a href> → фильтр url_pattern
  │   sitemap: httpx GET → все <loc> → фильтр url_pattern
  │   → list[DiscoveredUrl]
  │
  ▼ Dedup: filter_new_urls(supabase, urls)
  │   Исключает URL, которые уже есть в events.source_url
  │   → только новые URL (sub.new ≤ sub.discovered)
  │
  ▼ Для каждого нового URL:
  │   httpx GET → HTML
  │   extractor.extract(html, url)     ← ОДИН LLM-вызов на URL
  │   to_event_row(parsed, city, url, source)
  │   save_raw_document(url, html)     ← сырьё для перепарса
  │
  ▼ EventRow[] → merge → upsert
```

---

#### `vk_posts` — посты VK → префильтр → LLM (1 вызов/пачку)

Работает на **сервисном ключе** (`VK_SERVICE_KEY`). `wall.get` доступен для открытых сообществ.

```
source.vk_groups = ["perm_afisha", "kudago_perm", ...]
  │
  ▼ Для каждой группы screen_name:
  │
  │   VkClient.fetch_wall_posts(screen, count=100)
  │   → до 100 последних постов (wall.get API)
  │
  │   Префильтр (отбрасываем по порядку):
  │   ├── post_within_days(post, 14)? → нет → ПРОПУСТИТЬ (старый пост)
  │   ├── is_event_candidate(text)?   → нет → ПРОПУСТИТЬ (не похоже на анонс)
  │   │     classifiers.py: есть дата/время ИЛИ маркеры «билеты»/«вход»/«регистрация»
  │   └── raw_documents: SHA-256(text) уже видели? → ПРОПУСТИТЬ (дедуп поста)
  │
  │   Берём до 20 кандидатов, бьём на пачки по POST_BATCH_SIZE (дефолт 5):
  │   «=== POST https://vk.com/wall{owner}_{id} ===\n{text}\n\n=== POST … ===\n…»
  │
  │   asyncio.gather(extractor.extract_many(chunk_doc, group_url) ...)
  │   ← один LLM-вызов на ПАЧКУ, пачки параллельно (Semaphore _POST_CONCURRENCY)
  │   → list[ParsedEvent]  (LLM читает маркер «=== POST url ===» → event_url)
  │
  │   Для каждого ParsedEvent:
  │   ├── _is_past_event(date) → пропустить
  │   └── resolve_event_url(event_url, group_url) → source_url
  │         event_url → прямая ссылка на пост (vk.com/wall-…)
  │         если пустой/мусорный → фолбэк на группу
  │
  │   save_raw_document() для обработанных постов
  │
  ▼ EventRow[] → merge → upsert
```

---

#### `vk_events` — VK-сообщества-«события» без LLM ⚠️ ОТКЛЮЧЁН

Нативные события VK имеют `start_date`, `finish_date`, `place` прямо в API-ответе — LLM не нужен.

```
VkClient.search_event_groups(city_name, vk_city_id)
  ← groups.search (тип=event, город) — ТРЕБУЕТ USER-ТОКЕН
  ← ⚠️ Сервисный ключ получает code=15 (Access denied)
  → list[VkEventGroup]
  │
  ▼ Для каждой group:
  │   event_group_to_parsed(group, city_name)
  │   → ParsedEvent (без LLM: start_date/place маппятся напрямую)
  │
  ▼ EventRow[] → upsert
```

**Включение:** раздобыть user-токен с доступом `groups`, добавить как `VK_USER_TOKEN` в Secrets,
расскомментировать источник в `seeds.yaml`. Код и тесты готовы.

---

#### `telegram_posts` — Telegram-каналы → префильтр → LLM (1 вызов/пачку)

Публичные каналы без авторизации через веб-превью `t.me/s/`. Зеркало `vk_posts`.

```
source.telegram_sources = [{channel, source_type, priority, enabled}, ...]
  │
  ▼ Для каждого канала ch (где ch.enabled=true):
  │
  │   TelegramHtmlProvider.fetch_posts(ch.channel, count=100)
  │   → GET https://t.me/s/{channel}  (без авторизации)
  │   → parse_channel_html(html)
  │   → [{text, url, date_unix}, ...]
  │
  │   Префильтр:
  │   ├── date_unix > сейчас - 14 дней? → нет → ПРОПУСТИТЬ
  │   ├── is_event_candidate(text, ch.source_type)?  → нет → ПРОПУСТИТЬ
  │   │     source_type=aggregator: нужна дата И маркер (много шума)
  │   │     source_type=organizer:  достаточно одного сигнала (сам анонсирует)
  │   └── raw_documents: SHA-256(text) видели? → ПРОПУСТИТЬ (дедуп поста)
  │
  │   Берём до 20 кандидатов, бьём на пачки по POST_BATCH_SIZE (дефолт 5):
  │   «=== POST https://t.me/{channel}/{id} ===\n{text}\n\n=== POST … ===\n…»
  │
  │   asyncio.gather(extractor.extract_many(chunk_doc, channel_url) ...)
  │   ← один LLM-вызов на ПАЧКУ, пачки параллельно (Semaphore _POST_CONCURRENCY)
  │   → list[ParsedEvent]
  │
  │   Для каждого ParsedEvent:
  │   ├── _is_past_event(date) → пропустить
  │   └── resolve_event_url(event_url, channel_url) → source_url
  │         event_url → прямая ссылка на пост (t.me/{channel}/{id})
  │         если пустой/мусорный → фолбэк на канал
  │
  │   save_raw_document() для обработанных постов
  │
  ▼ EventRow[] → merge → upsert
```

---

#### `generic` — одобренные кандидаты → JSON-LD / LLM (длинный хвост)

Домены, прошедшие модерацию (`candidate_sources.status='approved'`), парсятся автоматически.

```
candidate_sources WHERE city=X AND status='approved'
ORDER BY score DESC LIMIT GENERIC_DOMAIN_BUDGET (дефолт 20)
  │
  ▼ Для каждого домена:
  │
  │   resolve_listing_url(domain)
  │   ├── listing_url в кэше (last_verified < 30 дней) → использовать
  │   ├── sample_urls с event-path-хинтом → пробовать
  │   └── пробинг /afisha /events /raspisanie /schedule → первый 200-ответ
  │   (результат кэшируется в candidate_sources.listing_url)
  │
  │   httpx GET listing_url → HTML
  │   SHA-256 хеш → raw_documents дедуп (skip если не менялось)
  │
  │   1. JSON-LD (если has_jsonld_event=true) — бесплатно
  │      extract_jsonld_events(html) → list[ParsedEvent]  → ГОТОВО
  │
  │   2. LLM-фолбэк (если JSON-LD пуст И GENERIC_LLM_BUDGET > 0)
  │      extractor.extract_many(html, listing_url)
  │      GENERIC_LLM_BUDGET -= 1
  │      → list[ParsedEvent]
  │
  │   resolve_event_url(event_url, listing_url) → source_url события
  │   ← прямая ссылка на событие, листинг (/afisha) только фолбэк
  │
  │   record_source_health(source='generic:{domain}')
  │   ← хронически падающий домен → вручную status='broken'
  │
  ▼ EventRow[] → merge → upsert
```

> `GENERIC_LLM_BUDGET=10` означает не более 10 LLM-вызовов на весь прогон для generic-источников.
> Домены с `has_jsonld_event=true` не расходуют бюджет.

---

### LLM-провайдеры

Три провайдера реализуют один интерфейс `LLMExtractor` (`extraction/base.py`).
Переключение: `LLM_PROVIDER=gemini|groq|deepseek` в `.env` или `--provider` в CLI.

#### Сравнительная таблица

| Параметр | Gemini 2.5 Flash | Groq Llama 3.3 70B | DeepSeek V4 Flash |
|----------|-----------------|-------------------|------------------|
| SDK | `google-genai` | `groq` | `openai` (OpenRouter) |
| Модель по умолчанию | `gemini-2.5-flash` | `llama-3.3-70b-versatile` | `deepseek/deepseek-v4-flash` |
| Base URL | Google AI API | api.groq.com | openrouter.ai/api/v1 |
| Structured output | ✅ нативный (`response_schema`) | ❌ только `json_object` | ❌ нет |
| Схема в промпте | не нужна (SDK принудит) | нужна (полный JSON Schema) | нужна (полный JSON Schema) |
| Формат batch-ответа | `list[ParsedEvent]` | `{"events": [...]}` | `{"events": [...]}` |
| HTML-очистка | selectolax → HTML | selectolax + markdownify → Markdown | selectolax + markdownify → Markdown |
| Лимит single | 60k символов HTML | 20k символов Markdown | 20k символов Markdown |
| Лимит batch | 800k символов HTML | 40k символов Markdown | 40k символов Markdown |
| max_tokens single | 2000 | 2000 | 2000 |
| max_tokens batch | 20 000 | 8 000 | 8 000 |
| temperature | 0 | 0 | 0.3 |
| Ключ (env) | `GEMINI_API_KEY` | `GROQ_API_KEY` | `DEEPSEEK_API_KEY` (OpenRouter, нужны кредиты) |

#### Что происходит внутри каждого LLM-вызова

Все три провайдера следуют одной логике, различия — в SDK и форматах:

```
1. Очистка HTML
   Gemini: selectolax удаляет <script> <style> <svg> <iframe> <head>
           → остаётся HTML-дерево body, передаётся как есть
   Groq/DeepSeek: то же + удаляет <header> <footer> <nav> <aside>
                  → markdownify конвертирует в Markdown (экономия токенов ~3-5x)

2. Формирование сообщения (user_msg):
   «Источник: {url}
    Сегодня: {день недели, число месяц год}  ← _today_ru(), ориентир года для дат без года
    HTML/Markdown страницы:\n{cleaned}»

3. Вызов API
   Gemini:     generate_content(system, user_msg, response_schema=ParsedEvent|list[ParsedEvent])
               → API сам валидирует по Pydantic-схеме
   Groq:       chat.completions.create(system, user_msg, response_format=json_object)
               → гарантирован валидный JSON, но не наша схема
   DeepSeek:   chat.completions.create(system, user_msg)
               → свободный текст, ожидаем JSON без гарантий

4. Парсинг ответа
   json.loads(response.text) → dict/list
   ParsedEvent.model_validate(data)  ← Pydantic валидирует поля, типы, форматы
   Если title == "NOT_AN_EVENT" → ExtractorError (страница нерелевантна)
   Если Pydantic упал → ExtractorError (LLM вернул мусор)

5. Для batch: items = data["events"] (Groq/DeepSeek) или data (Gemini)
   Каждый элемент валидируется отдельно; невалидный item → warning, остальные идут дальше
```

#### Ретрай и фолбэк провайдера (`extraction/fallback.py`, `retry.py`, `_errors.py`)

Свободные тиры LLM упираются в лимиты (429 `RESOURCE_EXHAUSTED`, 503 high demand). Чтобы прогон
не терял события, экстрактор оборачивается в композит — прозрачно для всех источников.

- **Классификация** (`_errors.is_rate_limit`): по `.status_code`/`.code` (429/503) и подстрокам
  (`resource_exhausted`, `unavailable`, `overloaded`). Экстракторы кидают `RateLimitError`
  (подкласс `ExtractorError`) на лимит, обычный `ExtractorError` — на контент/парс.
- **Ретрай** (`retry.with_retry`): на `RateLimitError` — экспоненциальный backoff + jitter,
  `LLM_RETRY_ATTEMPTS` попыток на провайдера.
- **Фолбэк** (`FallbackExtractor`): цепочка `LLM_FALLBACK_PROVIDERS` (дефолт `gemini,groq`).
  При исчерпании ретраев у провайдера — переход к следующему. Индекс `_preferred_idx` сдвигается
  вперёд (advance-only, без Lock — asyncio однопоточный), чтобы следующие вызовы не били
  выгоревшего. Контент-ошибка (`ExtractorError`) пробрасывается без фолбэка (не маскируем баги,
  не двоим расход). Цепочку строит `cli._make_extractor_chain` из провайдеров, у кого задан ключ.

> ⚠️ **Лимиты free-tier — узкое место для VK/TG-батчей.** DeepSeek (OpenRouter) требует оплаты —
> без кредитов отдаёт `402`, поэтому в цепочку по умолчанию не включён. Groq `llama-3.1-8b-instant`
> имеет TPM=6000 — пачка из 5 постов (~11k токенов) не лезет (`413 Request too large`); для groq как
> рабочего фолбэка нужен `llama-3.3-70b-versatile` (TPM 12k) и/или меньший `POST_BATCH_SIZE`. Gemini
> 2.5-flash free-tier ограничен по RPD — на тяжёлом прогоне выгорает за день.

#### Системный промпт (общий для всех провайдеров)

Промпты `_SYSTEM_PROMPT_SINGLE` и `_SYSTEM_PROMPT_BATCH` содержат одинаковые правила:

| Правило | Зачем |
|---------|-------|
| Заполнять ТОЛЬКО явно указанное | Предотвращает галлюцинации |
| Не использовать собственные знания о годе — смотреть на ориентир «Сегодня» | Дата без года (23 мая) → текущий или следующий год, а не 2023 из обучения |
| `image_url` — только реальное фото (jpg/png/webp 400+px), не svg/иконки | Отсеивает спрайты интерфейса |
| `event_url` — из маркера `=== POST <url> ===` или `<a href>` в карточке, не из тела поста | Голые ссылки в тексте (clck.ru, vk.cc) не являются источником события |
| Игнорировать прошедшее время («прошёл», «состоялся», «завершился») | Репортажи о прошедших событиях не должны попадать в БД |
| Теги — только из закрытого набора `ALLOWED_TAGS` | Свои теги от LLM отбрасывает `filter_tags()` в валидаторе |
| Single: `title="NOT_AN_EVENT"` если не событие | Batch: пустой массив `[]` |

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

### `sources/playwright_2gis.py` — 2ГИС через браузер (Playwright fallback)

Контур **VENUES**, не events. Используется командой `refresh-venues` как fallback, когда платный
2ГИС Catalog API недоступен или вернул пустой результат. Зависимость опциональная — не входит
в базовый `pip install -e .`, устанавливается только через `pip install -e ".[playwright]"`.

**Почему Playwright, а не Selenium:** нативный async, легче в CI (официальный GitHub Action +
`playwright install chromium --with-deps`), headless chromium из коробки.

**`parse_cards(html, event_type) → list[ParsedEvent]`** — чистая функция (без сети/браузера):
- Принимает готовый HTML выдачи 2ГИС, парсит `selectolax`
- Карточки без названия или без адреса пропускаются — в venues это шум
- Дедуп внутри одной выдачи по паре `(name, address)` — карточки могут задваиваться при lazy-load
- Возвращает `ParsedEvent[]` с `date='always'`, `price_min=price_max=0`, `district=None`
- **Тестируется без сети** на фрагменте HTML (`tests/test_playwright_2gis.py`)

**`scrape_venues(city, query, event_type, max_scrolls, headless) → list[ParsedEvent]`** — async:
1. Открывает `https://2gis.ru/{city}/search/{query}` в headless chromium
2. Применяет `playwright-stealth` (если установлен) — снижает вероятность антибот-проверки
3. Прокручивает панель выдачи `max_scrolls` раз со случайными паузами (0.8–1.8 с) — lazy-load карточек
4. Снимает `page.content()` и передаёт в `parse_cards`

**Антибот 2ГИС:**
- `playwright-stealth` патчит WebDriver-сигнатуры, **пинован на `<2.0`** — v2 изменил API (`stealth_async` переименован), пин в `pyproject.toml` защищает от поломки при автообновлении
- User-Agent реального Chrome (Windows)
- Случайные паузы между скроллами + пауза 1.5–3 с после загрузки страницы
- `locale=ru-RU`

**Хрупкость и актуальные CSS-селекторы** — обфусцированные классы (вида `_1kf6gff`) меняются
при редеплое фронта 2ГИС. Все константы вынесены в блок **«ЧИНИТЬ ТУТ»** с инструкцией (DevTools).
Смена селекторов не затрагивает логику — только константы и тест-фикстуру.

Актуальные (проверено 2026-06):

| Константа | Значение | Описание |
|-----------|---------|---------|
| `_CARD_SELECTOR` | `"div._1kf6gff, div._5b28jpo"` | Органические (`_1kf6gff`) + рекламные (`_5b28jpo`) карточки — оба типа имеют одинаковый доступ к имени и адресу |
| `_LINK_SELECTOR` | `"a._1rehek"` | Anchor-ссылка на заведение; `.text()` = название. Стабильнее класса внутреннего `<span>` — разные типы карточек используют `_lvwrwt`, `_9r89aog` и другие |
| `_ADDRESS_SELECTOR` | `"div._klarpw"` | Адрес. Один `div._klarpw` может содержать несколько узлов: адрес + статус («Закрыто», «Закроется через…»). `parse_cards` перебирает все и берёт первый, не совпадающий с `_STATUS_RE` |
| `_IMAGE_SELECTOR` | `"div._1dk5lq4"` | `<div>` с `background-image: image-set(url(...) 1x, url(...) 2x)` — предпочтительно берётся 2x |
| `_RESULTS_SCROLL_SELECTOR` | `"div._z1qx2c"` | Контейнер прокрутки; при несовпадении деградирует на `page.mouse.wheel` |
| `_STATUS_RE` | `r"(закро\|открыт\|работ\|...)"` | Строки статусов, которые нужно пропускать при выборе адреса из `_klarpw` |

Особенности текущей вёрстки (2026-06, относительно прошлой версии):
- Фото: `<img src>` → `<div style="background-image: image-set(...)">`, используется 2x URL
- Район (`district`): убран из карточки поиска → всегда `None`
- Адрес: суффикс «N филиала» у многофилиальных заведений чистится regex'ом
- NBSP (`\xa0`): заменяется на обычный пробел при извлечении имени и адреса

**Диагностика** при `extracted=0`: `scrape_venues` логирует `html_snippet` (первые 2000 символов)
на уровне `WARNING`. Для локального разбора — `debug_parse_2gis.py` (в `.gitignore`, не коммитить)
принимает сохранённый HTML и находит новые классы от стабильных якорей.

**Ленивый импорт:** `from playwright.async_api import async_playwright` выполняется внутри
`scrape_venues`, а не на уровне модуля — модуль импортируется без ошибки, даже если playwright
не установлен (он нужен только в `refresh_venues.yml`).

---

### `sources/quizplease.py` — QuizPlease REST API

**`QuizPleaseClient`** — клиент к QuizPlease API (`api.quizplease.ru/api/games/schedule/{city_id}`,
без авторизации). LLM не используется.

**Почему `direct_api`, а не `batch_listing`:** сайт `quizplease.ru` — **Nuxt SPA**. Статический HTML
содержит только CSS-скелетоны загрузки (`.game-card-skeleton`); реальные события грузятся через JS-вызов
к REST API. Простой `httpx`-запрос получает пустую оболочку → 0 событий. Решение — обращаться
к API напрямую, как это делает сам браузер.

**`search(city_id)`** — основной метод:
- Перебирает страницы (`per_page=30`) до `total_pages` из поля `pagination` (нет запроса за пределы данных)
- Дедуп внутри прогона по `game.id` (UUID) на случай нестабильной сортировки API
- Каждый пропущенный game логируется через `log.warning("quizplease.skipped_game")` — нет тихих потерь
- `source_url` события: `game.get("url")` из ответа API; если null — страница игры `/.../game/{id}` (id — UUID из API); если нет и id — страница расписания города (`schedule_url`)

**Маппинг полей API (`_map_game`):**

| Поле API | ParsedEvent |
|----------|-------------|
| `title` | `title` |
| `date` (`"DD.MM.YYYY HH:MM"`) | `date` (→ `YYYY-MM-DD`), `time_start` (→ `HH:MM`) |
| `place.title` | `venue_name` |
| `place.address_ru` / `place.address` | `address` |
| `price` / `current_price` | `price_min`, `price_max` |
| `template.background_pc` | `image_url` |
| `"QuizPlease"` (константа) | `organizer` |
| `"quiz"` (константа) | `type` |

Формат даты `DD.MM.YYYY HH:MM` — нестандартный (не ISO), обрабатывается через `datetime.strptime`.
При `isinstance(raw_date, str)` guard — UNIX timestamp или null → `_map_game` вернёт `None`.

**Конфигурация в `seeds.yaml`:**
```yaml
- name: quizplease
  extraction_mode: direct_api
  provider: quizplease
  quizplease_city_id: 37   # Пермь; Сочи = 62 (зафиксировано, не запрашивается в рантайме)
  priority: 60
  full_snapshot: true      # API обходит все страницы (_MAX_PAGES=20) → включает sync_source_events
```

`full_snapshot: true` означает, что QuizPlease API обходит все страницы пагинации и гарантированно
возвращает **все** текущие игры города. После каждого прогона `pipeline.py` вызывает
`sync_source_events` — будущие события, пропавшие из ответа API (отменённые игры), немедленно
удаляются из БД без ожидания истечения даты.

City ID определяется один раз из `api.quizplease.ru/api/cities/short` и хранится в `seeds.yaml`.
В рантайме API городов **не вызывается** — только `games/schedule/{id}`.

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

- **`SearchProvider`** (ABC, поле `name`) — интерфейс поисковика. Реализации:
  - **`SerperProvider`** (основной) — Google Search через Serper API (`google.serper.dev`, keyed).
  - **`BraveProvider`** (резерв) — Brave Search API (keyed).
  - **`DuckDuckGoProvider`** (последний резерв) — HTML без ключа; ⚠️ с 2026-06 отдаёт HTTP 202
    (антибот) → 0 результатов, поэтому используется только если keyed-ключей нет.
  - **Circuit breaker:** 401/403 (битый ключ) или 3 подряд 5xx/сетевых отказа отключают провайдер
    до конца прогона; 429 (rate limit) — временно, без отключения.
- **`build_search_providers(settings, client)`** — строит цепочку из `SEARCH_PROVIDERS`
  (через запятую, порядок = приоритет); keyed-провайдер добавляется только при наличии ключа.
- **`_search_with_fallback(providers, query)`** — пробует провайдеры по очереди; fallback на
  следующий только при пустом результате (не по числу), чтобы запасной не вытеснял релевантную выдачу.
- **`discover_sources(city, supabase, *, settings, dry_run)`** — точка входа: гоняет типовые запросы
  (`квиз {city}`, `стендап {city}`, `мастер-класс {city}`, `детские мероприятия {city}`, `афиша {city}`),
  агрегирует домены, считает score, пишет в БД.
- **Скоринг кандидата:** `+3` если на странице найден JSON-LD типа `Event`; `+2` если в пути есть
  `/events`/`/afisha`/`/schedule`; `+1` за каждый дополнительный запрос, в котором встретился домен.
- **Фильтры:** пропускаются домены из `seeds.yaml`, домены со статусом `rejected`, агрегаторы/соцсети.
- **`save_candidates`** сохраняет с **сохранением статуса** (не перетирает `approved`/`rejected`)
  и обновляет `last_seen` — для очистки мусора, который давно не встречается. У новых доменов
  фиксирует `first_provider`/`first_query` (кто и по какому запросу нашёл первым — для аналитики).
- **Метрики прогона** (structlog): `candidate.search.stats` (по запросу), `candidate.discovered`
  (новый домен + провайдер), `candidate.provider.summary` (вклад провайдеров, avg_score, score≥7),
  `candidate.search.cost` (число запросов на город). Сигналы деградации: `candidate.discovery_empty`
  (0 кандидатов) и `candidate.discovery_no_new` (найдены, но все уже в БД).
- **`discovery-health`** (CLI-команда) — за окно `--days` (дефолт 7) считает новых кандидатов по
  `found_at`, разбивку по `first_provider`/статусам и avg_score; exit code 1 при 0 новых
  (раннее обнаружение поломки Discovery). Запускается шагом в `discover_sources.yml`.

---

## Утилиты (`docs/`)

### `docs/Конвертер yaml-xlsx/` — редактор seeds.yaml в Excel

Инструменты для удобного редактирования `parser/config/seeds.yaml` через Excel:

| Скрипт | Назначение |
|--------|-----------|
| `make_seeds_excel.py` | Читает `seeds.yaml`, генерирует `seeds_editor.xlsx` (форматированная таблица с дропдаунами) |
| `excel_to_seeds.py` | Конвертирует `seeds_editor.xlsx` обратно в `seeds.yaml`; поддерживает `--input` / `--output` |

Удобно для batch-редактирования источников (включить/выключить, изменить приоритет, добавить канал)
без ручного YAML-синтаксиса. Результат проверяется через `python -m parser.cli discover --city perm`.

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
| `VK_SERVICE_KEY` | Сервисный ключ VK mini-app для `vk-events`/`vk-posts` |
| `VERCEL_DEPLOY_HOOK` | URL хука деплоя Vercel |
| `TG_BOT_TOKEN` | Telegram-бот для алертов (опционально) |
| `TG_CHAT_ID` | chat_id для алертов (опционально) |

### `.github/workflows/refresh_venues.yml` — сбор venues раз в 2 недели

**Отдельный workflow**, не встроен в `parse.yml`: Playwright тяжёлый (chromium + зависимости), не
вписывается в 30-мин окно ежедневного парсинга. Площадки меняются редко — раз в 2 недели достаточно.

**Триггеры:**
- Cron: `0 3 1,15 * *` — 1-е и 15-е числа месяца, 03:00 UTC (06:00 МСК)
- `workflow_dispatch` с inputs: `city` (perm / sochi / **all**, дефолт all), `source` (auto / twogis / playwright, дефолт auto)

**Шаги:**
1. `pip install -e ".[playwright]"` — устанавливает базовые зависимости + опциональную группу `playwright`
2. `playwright install chromium --with-deps` — скачивает headless chromium + системные либы в CI
3. `python -m parser.cli refresh-venues --city {city} --source {source}` — сбор и upsert

**Стратегия `source=auto`:**  
→ Пробует 2ГИС Catalog API (быстро, дёшево)  
→ Если `TWOGIS_API_KEY` отсутствует, API вернул ошибку или пустой результат — fallback на Playwright  
→ Playwright-источник помечает строки `source='playwright'`; API — `source='twogis'`

**Секреты:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TWOGIS_API_KEY` (опц. — если нет, сразу Playwright).

**Защита manual-данных:** `db.upsert_venues` перед записью выбирает id с `source='manual'` и пропускает их — ручной ввод через Supabase Table Editor всегда выигрывает.

---

### `.github/workflows/discover_sources.yml` — еженедельный поиск источников

**Триггеры:**
- Cron: `0 20 * * 0` (воскресенье 20:00 UTC = 23:00 МСК) — раз в неделю
- `workflow_dispatch` — ручной запуск

**Матрица:** `perm` и `sochi` параллельно. Запускает `discover-sources --city {city}`, затем
`discovery-health --city {city}` (предупреждение при 0 новых, не валит прогон).
Секреты: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SERPER_API_KEY` (обязателен для рабочего
поиска), `BRAVE_API_KEY` (опц., резерв); `SEARCH_PROVIDERS` задаётся в `env:` workflow.
Результат — кандидаты в таблице `candidate_sources` для модерации.

---

## Фронтенд (`web/`)

Next.js 16 App Router, полностью статический (SSG), React 19, Tailwind CSS v4.

### Маршруты

| URL | Страница |
|-----|---------|
| `/` | 301 редирект → `/perm` |
| `/perm/` | Главная Перми — сетка событий + секция «Постоянные места» |
| `/perm/events/[slug]/` | Детальная страница события Перми |
| `/perm/venues/` | Каталог площадок Перми |
| `/perm/venues/[slug]/` | Детальная страница площадки Перми (JSON-LD SportsActivityLocation) |
| `/sochi/` | Главная Сочи |
| `/sochi/events/[slug]/` | Детальная страница события Сочи |
| `/sochi/venues/` | Каталог площадок Сочи |
| `/sochi/venues/[slug]/` | Детальная страница площадки Сочи |
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

**`VenueCard.tsx`** — карточка площадки в каталоге: фото (или emoji-заглушка), цветной бейдж типа, название, адрес; ссылка на `/{city}/venues/{slug}/`.

**`VenuesCatalog.tsx`** — страница `/{city}/venues/`: заголовок, сетка VenueCard. Хлебная крошка → главная.

**`VenuesSection.tsx`** — секция «Постоянные места» на главной: показывает до 8 площадок + ссылку «Все места» на каталог.

**`VenueDetail.tsx`** — детальная страница площадки: изображение, бейдж типа, адрес, район, дата обновления, ссылка «Найти на 2ГИС» (поиск по имени+адресу). JSON-LD (`SportsActivityLocation` + `BreadcrumbList`) и Open Graph генерируются в `lib/venue-meta.ts`.

### Lib — площадки

**`lib/venues.ts`** — data layer для таблицы `public.venues`:
- `getVenuesByCity(city)` — все площадки города (RLS: публичное чтение через anon-ключ)
- `getVenueBySlug(city, slug)` — одна площадка для детальной страницы
- `rowToVenue()` — snake_case строка БД → camelCase `VenueItem`; slug = id без `{city}-` префикса

**`lib/venue-meta.ts`** — SEO-хелперы площадок (используются обоими городами, без дублирования):
- `buildVenueMetadata(venue, city)` → `Metadata` (title / description / Open Graph)
- `venueJsonLd(venue, city)` → JSON-LD `SportsActivityLocation` + `BreadcrumbList`
- `cityGenitive(city)` — родительный падеж города («Перми» / «Сочи»)

**`lib/venue-styles.ts`** — стили карточек/бейджей по строковому типу площадки (`bowling`, `billiards`, `karting`, `quest`, `other`): цвета бейджа (`venueBadgeStyle`), градиент и emoji заглушки (`venuePlaceholder`).

> Страницы площадок используют **ISR** (`revalidate = 86400`): площадки обновляются раз в 2 недели через `refresh_venues.yml`, а не при каждом деплое. `dynamicParams = true` — площадки, добавленные вручную после билда, рендерятся on-demand.

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
| `sample_urls` | text[] | Примеры найденных URL (для выбора страницы-листинга в generic) |
| `score` | int | Рейтинг полезности (JSON-LD Event, путь `/events`, частота) |
| `has_jsonld_event` | bool | Найден ли Schema.org Event |
| `status` | text | `new` / `approved` / `rejected` / `broken` |
| `listing_url` | text | Кэш страницы-листинга для generic-парсера |
| `last_verified` | timestamptz | Когда `listing_url` последний раз проверялся (TTL 30 дней) |
| `found_at` / `last_seen` | timestamptz | Первая и последняя находка |
| `first_provider` | text | Поисковик, нашедший домен первым (`serper`/`brave`/`manual`/…) |
| `first_query` | text | Запрос, по которому домен найден впервые (тюнинг шаблонов) |

**Жизненный цикл:** `new` (ждёт модерации) → `approved` (generic-парсер забирает домен) →
при хронических падениях вручную `broken` (по данным `source_health_agg`); `rejected` — пропустить навсегда.

### Таблицы `source_health` / `source_health_agg` (Analytics) — здоровье источников

`source_health` — лог запусков (`events_found`, `errors`, `duration_sec`, `last_error`).
`source_health_agg` — агрегат на источник (`last_success`, `avg_events`, `success_rate`, `total_errors`)
для быстрого дашборда «что сломалось».

### Таблица `source_quality` (Analytics) — ценность источника

Ежедневный снимок `(source, city, snapshot_date, events_found, unique_events, unique_events_ratio)`.
`unique_events` = события источника, не проигравшие кросс-источниковый merge (т.е. не дубли других
источников). Низкий `unique_events_ratio` → источник почти полностью дублирует другие, и его можно
отключить. Отвечает на вопрос «**стоит ли держать источник**» (в отличие от `source_health`, который
отвечает «работает ли он»). Считается в `pipeline._source_quality` по `merge.merged_by_source`.

### Таблица `coverage_stats` (Analytics) — покрытие по категориям

Ежедневный снимок `(city, category, count, snapshot_date)`. Позволяет видеть тренды и замечать
выпадение категорий (например, квизы упали с 25 до 2 — сломался источник).

### Таблица `venues` — постоянные заведения (инфраструктура)

Площадки (боулинг/картинг/бильярд/квесты) как отдельная сущность: `id, city, name, type, address,
district, image_url, source, updated_at`. Площадка — не событие (нет даты, меняется редко).
**Primary source of truth = Supabase** (правится через Table Editor); бекап — периодический снимок
в git через `parser-cli export-venues` (workflow `backup_venues.yml`, раз в неделю).

**Источник истины и наполнение:**

```
2ГИС → events(date='always', twogis-*)
               │
               ▼ bootstrap_venues_if_empty (только если venues города пуста, INSERT-only)
            venues ◄── refresh-venues (enrich: актуализация, фото via Playwright)
               │
               ▼
           фронтенд (/{city}/venues)
```

- **`venues` — единственный source of truth для фронта.** Обогащения пишут сюда.
- **`events(date='always')` — recovery snapshot, не бизнес-источник.** Используется только как seed.
- Три пути наполнения:
  - **bootstrap** (`db.bootstrap_venues_if_empty`) — в конце `run`: если у города в `venues` нет ни
    одной строки, засевает из `events(always, twogis-*)`. **INSERT-only** — не перетирает обогащения.
    Делает систему самовосстанавливающейся после очистки (без ключей/cron/Playwright).
  - **`refresh-venues`** (`refresh_venues.yml`, раз в 2 недели) — основной канал качества: 2ГИС API
    primary, `sources/playwright_2gis.py` fallback (фото). Запросы/типы — из `twogis`-источников seeds.
  - **`sync-venues --force`** — ручная полная пересборка из `events` (safe-by-default: без `--force` dry-run).
- Строки `source='manual'` автосбор **не перезаписывает** (`db.upsert_venues`) — ручной ввод приоритетен.

### Что осталось сделать

Статусы: ✅ готово · 🔧 в работе / частично · 📋 запланировано · 💡 идея

#### Ближайшие шаги (MVP-completion)

**1. Подключить фронтенд к `venues`** ✅  
Сделано: фронт читает `venues` (`lib/venues.ts`), есть каталог `/{city}/venues/` и страницы
площадок `/{city}/venues/[slug]/` с SEO (JSON-LD `SportsActivityLocation` + `BreadcrumbList`),
секция «Постоянные места» на главной. `run` авто-засевает `venues` из `events(always)` (bootstrap).

Осталось (отдельные шаги):
- **Убрать 2ГИС из `events`** 📋 — **отложено**: `events(date='always')` пока служит аварийным
  seed для bootstrap. Решать после периода наблюдения за `refresh-venues`; целевое состояние —
  `refresh-venues → venues → фронт`, тогда `events(always)` можно убрать или превратить в snapshot.
- `events.venue_id` → FK на `venues.id` 💡 (страницы площадок + SEO-граф «событие ↔ место»).

**2. Расширить список Telegram-каналов** 📋  
В `seeds.yaml` 3 стартовых канала Перми, для Сочи — 0. Нужно:
- Набрать 15–20 каналов Перми (организаторы + агрегаторы: театры, музеи, кафе, арт-пространства)
- Добавить каналы Сочи с нуля
- Проверить каждый: `https://t.me/s/<channel>` должен отдавать посты без авторизации

**3. Проверить `refresh-venues` + селекторы Playwright** ✅  
Выполнено (2026-06). GHA-лог показал `playwright-stealth 2.0.3` (сломан API) + `extracted=0`
из-за изменившейся вёрстки 2ГИС. Исправлено:
- `playwright-stealth` пинован `<2.0` в `pyproject.toml`
- `_CARD_SELECTOR` обновлён на `div._1kf6gff, div._5b28jpo` (органические + рекламные карточки)
- `_NAME_SELECTOR` (`span._lvwrwt`) заменён на `_LINK_SELECTOR = "a._1rehek"` — стабильнее, покрывает все типы карточек (`_9r89aog` у промо-карточек и др.)
- Фото: извлечение из `background-image: image-set(...)` вместо `<img src>`
- `_klarpw` итерируется с фильтром `_STATUS_RE` — пропускает «Закрыто», «Закроется через…»
- `district=None` (район убран из вёрстки 2ГИС карточек поиска)
- Суффикс «N филиала» и `\xa0` чистятся из адреса
- 9 тестов в `test_playwright_2gis.py` покрывают все сценарии без браузера/сети

**4. Заполнить `venues` вручную (source='manual')** 📋  
Автосбор найдёт всё, что есть на 2ГИС, но не найдёт закрытые/нишевые места. Через
Supabase Table Editor добавить вручную заведения, которых нет в выдаче 2ГИС. Их никакой
автосбор не тронет.

---

#### Источники и покрытие

**5. Discovery по дырявым категориям** 📋  
Добавить в `candidate_sources.py` запросы для категорий ⚠️:
`экскурсии {city}`, `мастер-класс {city}`, `куда сходить с детьми {city}`, `фестиваль {city}`.
Результат — кандидаты в `candidate_sources` → модерация → `seeds.yaml` или generic.

**6. VK user-токен для `vk-events`** 📋  
`vk_events` (VK-сообщества-«события» с нативными датами/адресом → ParsedEvent без LLM) готов,
но отключён: `groups.search` запрещён сервисному ключу (`code=15`, Access denied). Нужен
пользовательский токен с доступом `groups`. Код и тесты готовы — осталось раздобыть токен и
включить в `seeds.yaml`.

**7. Запустить generic-парсер** ✅ (Пермь) / 🔧 (Сочи, Discovery)  
Сделано для Перми (2026-06): включён `generic` в `seeds.yaml` (бюджеты domain=5/LLM=3), одобрены
2 первоисточника (`filarmonia.online` JSON-LD, `teatr-teatr.com` LLM) — 37 уникальных событий,
`unique_events_ratio = 1.0`. Также исправлен баг типизации JSON-LD (`@type → EventType`).

**Починка Discovery (PR #1) — сделано** 🔧

Корень проблемы: бесплатный `DuckDuckGoProvider` стал отдавать HTTP 202 (антибот) → 0 кандидатов
→ `candidate_sources` пустела → generic-парсер оставался без новых доменов. Discovery — первое
звено цепочки `discover-sources → модерация → generic → frontend`, и его поломка останавливала всё.

Что реализовано за готовым ABC `SearchProvider` (без переписывания остального пайплайна):

- **Keyed-провайдеры** — `SerperProvider` (Google через Serper API, основной) и `BraveProvider`
  (Brave Search API, резерв). У ABC появилось поле `name` для логов/метрик.
- **Цепочка с fallback** — `build_search_providers()` строит провайдеров из `SEARCH_PROVIDERS`
  (через запятую, порядок = приоритет); `_search_with_fallback()` пробует их по очереди и
  переключается на следующий **только при пустом результате** (не по числу — чтобы запасной не
  вытеснял релевантную выдачу основного). DuckDuckGo остаётся последним резервом.
- **Circuit breaker** — 401/403 (битый ключ) или 3 подряд 5xx/сетевых отказа отключают провайдер
  до конца прогона; 429 (rate limit) обрабатывается мягко (без отключения). Битый JSON не валит
  прогон. Защита квоты — `SEARCH_QUERY_LIMIT`.
- **Наблюдаемость** — метрики `candidate.search.stats` / `candidate.discovered` /
  `candidate.provider.summary` (вклад провайдеров, avg_score, score≥7) / `candidate.search.cost`;
  сигналы деградации `candidate.discovery_empty` и `candidate.discovery_no_new`. Новая колонка
  `candidate_sources.first_provider` / `first_query` (миграция `20260621000001`) + CLI-команда
  `discovery-health` (exit 1 при 0 новых кандидатов за неделю), вызываемая шагом в workflow.
- **CI** — cron в `discover_sources.yml` возвращён; в env добавлены `SERPER_API_KEY` / `BRAVE_API_KEY`
  / `SEARCH_PROVIDERS`. Тесты — `tests/test_candidate_sources.py` (провайдеры, circuit breaker,
  fallback, фабрика, `first_provider`) на `httpx.MockTransport`, без сети.

**Запущено (2026-06-25):** `SERPER_API_KEY` добавлен в Secrets, миграция `20260621000001`
применена, первый боевой прогон через `discover_sources.yml` прошёл. Serper: 5 запросов × 10
результатов → **26 уникальных доменов** для Перми записаны в `candidate_sources`
(`first_provider='serper'`), fallback на DuckDuckGo не понадобился. `discovery-health` зелёный.
Поток кандидатов восстановлен.

**Наблюдение первого прогона (вход для PR #2) — где «зарыта» доработка модерации:**

Технически Discovery работает, но **скоринг тянет в топ агрегаторы/реселлеры, а не первоисточники** —
а проекту для generic нужны именно сайты организаторов (они дают `unique_events_ratio = 1.0`,
агрегаторы дублируют Timepad). Конкретно по прогону Перми:

- **Топ по score — агрегаторы:** `perm.ticketland.ru` (8), `afisha.ru` (7), `afisha.yandex.ru` (5),
  `perm.kassir.ru`, `perm.kassy.ru`. Они набирают score за JSON-LD `Event` + путь `/events`, хотя
  как источник бесполезны. avg_score прогона ≈ 1.9, score≥7 всего 2.
- **Первоисточники — внизу:** реальные организаторы (`mzgb-perm.ru`, `club60sec.ru`, `pause-perm.ru`,
  `gostandup.ru`, `perm.smuzi-quiz.com`) пришли со score 1–2 — у них на sample-странице нет JSON-LD
  и нет event-path, текущий скоринг их не отличает от шума.
- **Сквозь `_IGNORE_DOMAINS` просачиваются поддомены** агрегаторов/соцсетей: `m.vk.com`,
  `afisha.yandex.ru`, `tripadvisor.ru`. Фильтр в `candidate_sources.py` сравнивает netloc точно
  (после срезания `www.`), но не суффиксно — `vk.com` в списке есть, а `m.vk.com` нет.

Объём доработок (**PR #2**):
- **Суффиксная фильтрация `_IGNORE_DOMAINS`** (дёшево) — отбрасывать домен, если он сам ИЛИ его
  родительский домен в списке (`domain == ignore or domain.endswith("." + ignore)`); расширить
  список явными агрегаторами (`ticketland.ru`, `kassir.ru`, `kassy.ru`, `afisha.ru`, `tripadvisor.ru`).
- **Скоринг под первоисточники, а не под разметку** — отделить «организатор» от «реселлер»
  (домен-агрегатор даёт штраф, а не бонус за JSON-LD); сейчас JSON-LD одинаково плюсует и тем и тем.
- **Полуавтоматическая модерация (`auto-approve`)** — только по семантике первоисточника
  (`has_jsonld_event` + event-path + ≥3 запроса И **не** агрегатор), чтобы ручная модерация не стала
  новым узким местом. Порог — не магическое число, а набор признаков.
- **Включить generic для Сочи** — после набора одобренных доменов Сочи.

**Прочее (вне Discovery):**
- **Спец-источники для SPA-площадок** 💡 — `permopera.ru` / `permm.ru` (афиша за JS) — кандидаты
  на `direct_api`/Playwright, как в своё время `quizplease`.

---

#### Аналитика и инструменты

**8. Дашборд source_quality** 📋  
Сейчас `unique_events_ratio` записывается в `source_quality` молча. Нужно:
- Вывести в конце прогона в stdout таблицу по источникам (ratio, found, unique)
- Либо страницу `/admin/sources` на фронте (защищённая, только авторизованным)

**9. Дедуп v2** 💡  
Текущий дедуп по `id`(=city+slug из title+date) ловит точные совпадения и разброс в регистре/пунктуации.
Не ловит «Квиз» vs «Квиз-вечер» (разные title → разные slug). Идея:
- Per-field priority (VK-пост знает об отмене раньше, чем Timepad)
- Fuzzy-матчинг по `near_misses` (уже накапливается в `pipeline.py`, не используется)
- Freshness weighting: свежий источник о переносе важнее старого о мероприятии

**10. Telegram через MTProto** 💡  
Если веб-превью `t.me/s/` начнут блокировать или понадобятся закрытые каналы:
добавить `TelethonProvider` (реализация существующего ABC `TelegramProvider`), хранить
сессию в GitHub Secrets. Пайплайн менять не нужно — только новый провайдер.

---

#### Фронтенд

**11. Страницы организаторов** 💡  
`organizer` заполняется консистентно (LLM-промпты + Timepad/VK). Страницы `/organizers/{slug}/`
(«все события QuizPlease») — хороший источник органического SEO. Потребует таблицу `organizers`
(FK из `events`).

**12. Функциональный поиск** 💡  
Сейчас поле поиска в шапке — заглушка. Варианты реализации: клиентский full-text поиск через
Postgres `ts_vector` (при сборке) или клиентская библиотека (Fuse.js / MiniSearch по загруженным
событиям, без запросов к серверу).

---

#### Данные / схема

**13. Event provenance** 💡  
Таблица `event_sources (event_id, source, won)`: из каких источников собрано событие и кто
победил в merge. Сейчас merge молча оставляет победителя. Нужно, когда отладка качества данных
станет узким местом.

**14. candidate_sources → Source Registry** 💡  
Таблица уже накапливает `score`/`sample_urls`/`listing_url`/`last_verified`/`status` и дрейфует
в сторону реестра источников. Возможна будущая консолидация с `seeds.yaml`.

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
VK_SERVICE_KEY=...           # сервисный ключ VK mini-app (vk-events / vk-posts)
SERPER_API_KEY=...           # Serper API для discover-sources (основной поисковик)
BRAVE_API_KEY=...            # Brave Search API — резервный поисковик (опц.)
SEARCH_PROVIDERS=serper,brave,duckduckgo  # порядок = приоритет (опц.)
GENERIC_LLM_BUDGET=10        # макс. LLM-вызовов/прогон в generic (опц.)
GENERIC_DOMAIN_BUDGET=20     # макс. доменов/прогон в generic (опц.)
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

# Telegram-каналы (один источник, сухой прогон)
python -m parser.cli run --city perm --source telegram-posts --dry-run

# Discovery новых источников (поиск → candidate_sources)
python -m parser.cli discover-sources --city perm            # боевой (пишет в БД)
python -m parser.cli discover-sources --city perm --dry-run  # только вывод кандидатов

# Здоровье Discovery: новые кандидаты за последние N дней (exit 1 при 0)
python -m parser.cli discovery-health --city perm --days 7

# Бекап площадок: снимок таблицы venues в SQL-файл (для коммита в git)
python -m parser.cli export-venues --output supabase/seeds/venues.sql

# Сбор постоянных заведений в таблицу venues (2ГИС API primary, Playwright fallback)
python -m parser.cli refresh-venues --city perm                  # auto: API, fallback на браузер
python -m parser.cli refresh-venues --city all --source twogis   # только API, без браузера
python -m parser.cli refresh-venues --city perm --source playwright  # только браузер (нужен [playwright])

# Пересборка venues из events(always) — recovery без 2ГИС-ключа (safe-by-default)
python -m parser.cli sync-venues --city all            # dry-run: «would import: N»
python -m parser.cli sync-venues --city all --force    # реальная перезапись из events
```

**Полный список команд:**

| Команда | Назначение | Пишет в БД |
|---------|-----------|-----------|
| `discover --city <c> [--source <s>]` | Отладка краулера: только список найденных URL | нет |
| `run --city <c>` | Полный пайплайн (discovery → extract → write) | да |
| `run --city <c> --dry-run` | Прогон LLM без записи (проверка качества) | нет |
| `run --city <c> --source <s>` | Один источник | да |
| `run … --provider gemini\|groq\|deepseek` | Override LLM-провайдера | да |
| `run … --mode …\|vk_posts\|telegram_posts\|generic` | Override режима | да |
| `discover-sources --city <c>` | Поиск новых источников → `candidate_sources` | да |
| `discover-sources --city <c> --dry-run` | Поиск без записи (только вывод) | нет |
| `discovery-health --city <c> [--days N]` | Новых кандидатов за период; exit 1 при 0 | нет |
| `export-venues [--city <c>] --output <path>` | Снимок таблицы `venues` в SQL-файл (бекап) | нет |
| `refresh-venues --city <c\|all> [--source auto\|twogis\|playwright]` | Сбор заведений в таблицу `venues` из 2ГИС | да (`venues`) |
| `sync-venues --city <c\|all> [--force]` | Пересборка `venues` из `events(always, twogis-*)`. Без `--force` — dry-run | да с `--force` (`venues`) |

### Миграции БД

Схема версионируется SQL-файлами в `supabase/migrations/` (применять по порядку):

```bash
# Через Supabase CLI (нужен залогиненный supabase + связанный проект)
supabase db push

# Либо вручную: выполнить каждый файл из supabase/migrations/ в SQL Editor по возрастанию имени
```

Все миграции идемпотентны (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`) — повторное применение
безопасно. Новые таблицы (`raw_documents`, `source_health*`, `source_quality`, `coverage_stats`,
`candidate_sources`) создаются с включённым RLS без политик — доступ только у `service_role` (которым
пишет парсер). Исключение — `venues`: RLS с политикой публичного чтения (`SELECT USING (true)`), т.к.
площадки предназначены для отображения на сайте.

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
