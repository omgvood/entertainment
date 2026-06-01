# Афиша — фронтенд

Next.js 16 (App Router, SSG) + Supabase + Tailwind CSS v4.

Агрегатор досуга: квизы, стендапы, боулинг, бильярд, картинг. Города: **Пермь**, **Сочи**.

---

## Архитектура

```
Supabase (Postgres)
    │  читается при сборке (SSG)
    ▼
Next.js build
    │  генерирует статические HTML-страницы
    ▼
Vercel CDN ← пользователь
```

Сайт полностью статический — нет серверного рендеринга в рантайме. Данные актуализируются через ночной пересбор (Vercel Deploy Hook из GitHub Actions).

---

## Структура маршрутов

| URL | Страница | SSG |
|---|---|---|
| `/` | 301 редирект → `/perm` | — |
| `/perm/` | Главная Перми | Собирается при деплое |
| `/perm/events/[slug]/` | Страница события Перми | Генерируется для каждого события |
| `/sochi/` | Главная Сочи | Собирается при деплое |
| `/sochi/events/[slug]/` | Страница события Сочи | Генерируется для каждого события |
| `/sitemap.xml` | Авто-генерация из БД | — |
| `/robots.txt` | Allow all + ссылка на sitemap | — |

---

## Структура кода

```
web/
├── app/
│   ├── layout.tsx              — корневой layout: Яндекс.Метрика, верификация поисковиков
│   ├── sitemap.ts              — генерация sitemap.xml из Supabase
│   ├── robots.ts               — robots.txt
│   ├── perm/
│   │   ├── page.tsx            — главная страница Перми
│   │   └── events/[slug]/
│   │       └── page.tsx        — страница события Перми
│   └── sochi/
│       ├── page.tsx            — главная страница Сочи
│       └── events/[slug]/
│           └── page.tsx        — страница события Сочи
├── components/
│   ├── Header.tsx              — шапка с переключателем городов
│   ├── CityView.tsx            — сетка карточек + фильтры + SEO-описание города
│   ├── Sidebar.tsx             — панель фильтров (тип, дата, цена)
│   └── EventCard.tsx           — карточка события
└── lib/
    ├── types.ts                — EventItem, City, CITY_CONFIG
    ├── events.ts               — запросы к Supabase (getEventsByCity, getEventBySlug)
    ├── filters.ts              — клиентская фильтрация (тип, дата, цена)
    └── supabase.ts             — Supabase client (anon key, read-only)
```

---

## Модель данных

Таблица `events` в Supabase Postgres:

| Поле | Тип | Описание |
|---|---|---|
| `id` | uuid | Первичный ключ |
| `city` | text | `perm` или `sochi` |
| `slug` | text | Уникальный URL-идентификатор (UNIQUE constraint) |
| `title` | text | Название события |
| `type` | text | `quiz` / `standup` / `bowling` / `billiards` / `karting` |
| `date` | text | `YYYY-MM-DD` или `always` (для постоянных мест) |
| `time_start` | text | Время начала `HH:MM` |
| `price_min` | int | Минимальная цена для фильтра |
| `price_max` | int | Максимальная цена для фильтра |
| `price_text` | text | Строка для отображения: «от 500 до 1000 ₽» |
| `address` | text | Адрес |
| `venue_name` | text | Название площадки |
| `source_url` | text | Ссылка на источник / регистрацию |
| `image_url` | text | Картинка карточки |
| `meta_title` | text | SEO заголовок страницы события |
| `meta_description` | text | SEO описание страницы события |
| `parsed_at` | timestamptz | Время последнего обновления парсером |

---

## Фильтрация событий

**Серверная (при запросе к Supabase):**
- Только события текущего города
- `date >= сегодня` или `date = 'always'` — прошедшие события не показываются
- Сортировка по дате по возрастанию

**Клиентская (в браузере, без запроса к серверу):**
- По типу (квиз / стендап / боулинг / бильярд / картинг)
- По дате (сегодня / завтра / выходные / любая)
- По цене (диапазон)
- Чекбокс «только с фиксированной датой» — скрывает `always`-события при фильтре по дате

---

## SEO

Каждая страница имеет:
- `<title>` и `<meta description>` по шаблону
- Open Graph теги
- Schema.org Event JSON-LD (на странице события)
- Canonical URL
- `sitemap.xml` — генерируется из БД при каждом деплое
- SEO-текстовый блок на главной каждого города (для индексации по ключевым словам)

### Аналитика и верификация

Задаются через env-переменные в Vercel:

| Переменная | Назначение |
|---|---|
| `NEXT_PUBLIC_YM_ID` | ID счётчика Яндекс.Метрики |
| `YANDEX_VERIFICATION` | Код верификации Яндекс.Вебмастер |
| `GOOGLE_SITE_VERIFICATION` | Код верификации Google Search Console |

---

## Локальная разработка

```bash
cd web
npm install
cp .env.example .env.local
# Вставь NEXT_PUBLIC_SUPABASE_URL и NEXT_PUBLIC_SUPABASE_ANON_KEY
npm run dev
```

Открой [http://localhost:3000](http://localhost:3000).

---

## Деплой (Vercel)

**Настройки проекта в Vercel:**
- **Root Directory:** `web`
- **Framework Preset:** Next.js

**Environment Variables (Vercel → Settings → Environment Variables):**

| Переменная | Описание |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | URL проекта Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Публичный anon-ключ (read-only) |
| `NEXT_PUBLIC_SITE_URL` | Домен сайта, напр. `https://afisha-site.ru` (для sitemap) |
| `NEXT_PUBLIC_YM_ID` | ID счётчика Яндекс.Метрики (опционально) |
| `YANDEX_VERIFICATION` | Код верификации Яндекс.Вебмастер (опционально) |
| `GOOGLE_SITE_VERIFICATION` | Код верификации Google Search Console (опционально) |

Сайт пересобирается автоматически после каждого прогона парсера через Vercel Deploy Hook.
