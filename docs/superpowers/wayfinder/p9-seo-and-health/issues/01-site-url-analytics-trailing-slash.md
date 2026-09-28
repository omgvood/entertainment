# SITE_URL на мёртвом домене, нет Метрики и верификации, слэш на конце даёт редирект

Type: task
Скилл: `superpowers:test-driven-development` — форма URL (без слэша на конце) фиксируется тестом в `web/lib/` первым; переменные окружения проверяются на живом сайте
Status: open
Blocked by: —
Ветка: `fix/site-url-and-trailing-slash`

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
- Шаги пользователя (агент не меняет настройки аккаунтов): исправить `NEXT_PUBLIC_SITE_URL` в Vercel (Production и Preview) на `https://entertainment-eta.vercel.app`; завести счётчик Метрики; подтвердить сайт в Вебмастере и Search Console и задать три переменные.

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

<Заполняется в конце сессии.>

Локализация: `<команда>`, найдено N мест
Расхождения цифр: <или «нет»>
