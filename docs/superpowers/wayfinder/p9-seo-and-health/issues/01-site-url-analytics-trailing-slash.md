# SITE_URL на мёртвом домене, нет Метрики и верификации, слэш на конце даёт редирект

Type: task
Скилл: `superpowers:test-driven-development` — форма URL (без слэша на конце) фиксируется тестом в `web/lib/` первым; переменные окружения проверяются на живом сайте
Status: open
Blocked by: —
Ветка: `fix/site-url-and-trailing-slash`
Шаги пользователя: ждут

## Question

Аудит 2026-09-24, пп. 1.1, 1.2, 1.7. Сайт, цель которого — SEO-трафик, невидим для поиска и не измеряется:

1. `sitemap.xml`, `robots.txt`, `canonical` и JSON-LD площадок ведут на `https://entertaiments.vercel.app` (опечатка в `NEXT_PUBLIC_SITE_URL` в Vercel), этот домен отдаёт `404 DEPLOYMENT_NOT_FOUND`.
2. Нет счётчика Яндекс Метрики и мета-тегов верификации Вебмастера и Search Console: код есть, переменные на проде не заданы.
3. Все внутренние ссылки, URL в sitemap и `canonical` записаны со слэшем на конце, а сайт отдаёт форму без слэша: каждая такая ссылка проходит через редирект, `canonical` указывает на URL, который сам редиректит.

Домен остаётся `entertainment-eta.vercel.app` (решение на сведении 2026-09-29).

## Контекст

- Переменная читается в трёх местах, у всех фолбэк `https://afisha-site.ru`: `web/app/sitemap.ts:5`, `web/app/robots.ts:3`, `web/lib/venue-meta.ts:10-11`. Документация: `web/README.md:160`.
- Метрика и верификация: `web/app/layout.tsx:11,20-21` (`NEXT_PUBLIC_YM_ID`, `GOOGLE_SITE_VERIFICATION`, `YANDEX_VERIFICATION`), `web/README.md:128-130,161-163`.
- Слэш на конце (греп 2026-09-29): `web/lib/types.ts:38,46` (`CITY_CONFIG.path`), `web/app/sitemap.ts:17-68`, `web/lib/venue-meta.ts:34,84,90`, `web/components/EventCard.tsx:49`, `OtherDates.tsx:28`, `VenueCard.tsx:12`, `VenueDetail.tsx:36,40`, `VenuesCatalog.tsx:12`, `VenuesSection.tsx:21`. `trailingSlash` в `web/next.config.ts` не задан.
- `NEXT_PUBLIC_*` подставляется при сборке: после смены переменной нужна пересборка.
- Смежное: p7/06 (JSON-LD на страницах событий) берёт тот же `SITE_URL` — после этого тикета получает рабочий домен.

## Шаги пользователя

| Шаг | Где | Статус |
|---|---|---|
| `NEXT_PUBLIC_SITE_URL` = `https://entertainment-eta.vercel.app` (Production и Preview), затем пересборка | Vercel → Project → Settings → Environment Variables | сделан 2026-09-29 — старая запись была типа Secret, а `NEXT_PUBLIC_*` Vercel разрешает только как Config: удалена и заведена заново (Config, Production + Preview), пересборка Production. Проверено: в `sitemap.xml` 688 ссылок на `entertainment-eta.vercel.app`, 0 на `entertaiments`; `robots.txt` исправлен. Запись Development не трогалась |
| Завести счётчик Метрики, задать `NEXT_PUBLIC_YM_ID` | metrika.yandex.ru → Vercel | ждёт |
| Подтвердить сайт, задать `YANDEX_VERIFICATION` и `GOOGLE_SITE_VERIFICATION` | Яндекс Вебмастер, Google Search Console → Vercel | ждёт |

## Цифры

На 2026-09-29 — `https://entertainment-eta.vercel.app/sitemap.xml`: первый `<loc>` = `https://entertaiments.vercel.app/perm/`, `lastmod` 2026-09-28T21:52. Проверено в браузере.

```sql
-- не применимо: проверка на живом сайте, не в БД
```

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| Переменные Vercel (`NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_YM_ID`, `YANDEX_VERIFICATION`, `GOOGLE_SITE_VERIFICATION`) | домен в sitemap/canonical, счётчик, верификация | да — пользователь |
| `web/app/sitemap.ts`, `web/app/robots.ts` | sitemap и robots | да — слэш |
| `web/lib/venue-meta.ts` | `canonical`, JSON-LD и хлебные крошки площадок | да — слэш |
| `web/lib/types.ts` (`CITY_CONFIG.path`) | ссылки шапки на город | да — слэш |
| Компоненты с `href` (список в «Контексте») | ссылки карточек и навигации | да — слэш |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| — | гипотеза: поиск по значению `/\`` и `venues/` в `web/lib/*.test.ts` не делался — сессия делает его сама до первой правки |

## Готово когда

- `https://entertainment-eta.vercel.app/sitemap.xml` и `robots.txt` содержат только `https://entertainment-eta.vercel.app/...`; выборочный URL из sitemap отдаёт 200 без редиректа.
- `canonical` страницы площадки — URL без слэша на конце, отдаёт 200 без редиректа.
- На `/perm` есть `window.ym` и оба мета-тега верификации.
- `cd web && npx vitest run` зелёный, включая новый тест на форму URL.
- Выполнено обновление файла map.md

## Answer

**Кодовая часть сделана, тикет остаётся `open` до шагов пользователя** (решение пользователя 2026-09-29): критерий «на `/perm` есть `window.ym` и оба мета-тега» ждёт счётчика Метрики и кодов верификации. Код для них уже есть в `web/app/layout.tsx`, нужны только переменные в Vercel и пересборка.

- Слэш на конце убран в 20 местах: `sitemap.ts` (8), `venue-meta.ts` (`venueUrl` и хлебные крошки, 3), `CITY_CONFIG.path` (2), `href` в 6 компонентах (7). `trailingSlash` в `next.config.ts` не задаётся: сайт остаётся на форме без слэша. Таблица маршрутов в `web/README.md` исправлена, тикет её не называл.
- Тест `web/lib/venue-meta.test.ts` (4 проверки) до правки падал на слэше. `npx vitest run`: 119 passed (115 + 4). `tsc --noEmit` без ошибок.
- Превью PR #38: в sitemap 344 URL, все на `https://entertainment-eta.vercel.app`, со слэшем на конце 0. `canonical` площадки = `…/perm/venues/12-futov`. `/perm`, `/sochi`, `/perm/venues`, `/perm/venues/12-futov`, `/perm/events/moyo-2026-09-29` отдают 200 без редиректа, та же площадка со слэшем по-прежнему редиректит (контроль). На `/perm` 24 внутренние ссылки, со слэшем 0.
- Прод после мерджа (`560e9d3`), 2026-09-29: sitemap 344 URL, все на `entertainment-eta.vercel.app`, со слэшем 0; `robots.txt` ссылается на `https://entertainment-eta.vercel.app/sitemap.xml`; `canonical` площадки без слэша; `/perm`, `/sochi`, `/perm/venues`, `/perm/venues/12-futov`, `/perm/events/moyo-2026-09-29` — 200 без редиректа. Первые два критерия «Готово когда» выполнены.

Локализация: `grep -rnE "SITE_URL|CITY_CONFIG|trailingSlash"` (символ) + `grep -rnE "/\`|/'|}/"` (значение) по `web/app,lib,components`, плюс тесты, `web/README.md`, `parser/src`, `scripts`, `.github`; найдено 20 мест в коде + 4 строки README; тестов, кодирующих старую форму, нет
Расхождения цифр: в «Шагах пользователя» записано «688 ссылок» в `sitemap.xml`, а 2026-09-29 и прод, и превью отдают 344 `<loc>`. Причину не установил: возможно, двойной подсчёт в XML-просмотре браузера
