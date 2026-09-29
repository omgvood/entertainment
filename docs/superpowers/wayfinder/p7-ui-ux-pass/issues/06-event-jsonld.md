# Страницы событий без разметки Schema.org Event

Type: task
Скилл: `superpowers:test-driven-development` — разметку собирает чистая функция (по образцу `venue-meta.ts`), её вывод фиксируется тестом первым
Status: open (слот после p7/13, решение пользователя 2026-09-29)
Blocked by: —
Ветка: `feat/event-jsonld`
Шаги пользователя: ждут — validator.schema.org на превью PR

## Question

Страницы площадок размечены JSON-LD, а страницы событий — нет. Проверено 2026-09-22 на `/perm/events/vecher-fortepiannoy-muzyki-valentina-malinina-2026-09-23`: `script[type="application/ld+json"]` отсутствует. Для афиши это основная разметка — без неё поисковик не покажет в выдаче сниппет с датой и ценой. Пункт уже есть в роадмапе README (п. 13, 📋).

## Контекст

- `README.md`, «**13. Schema.org `Event` на страницах событий**»: делать по образцу `web/lib/venue-meta.ts` — хелпер `event-meta.ts` и вставка в обе `events/[slug]/page.tsx`; там же сказано, что canonical тоже нет.
- Образец: `web/lib/venue-meta.ts` (`SportsActivityLocation` + `BreadcrumbList`).
- Время начала — в часовом поясе города: `getCityNowMinutes` и таймзоны в `web/lib/dateUtil.ts` (p2, тикет «Час города»).
- Цена в `offers`: сейчас «бесплатно / неизвестно / известно» определяет регулярное выражение `priceKind()` в `web/lib/price.ts`; после тикета 08 — колонка `price_kind`. Если цена неизвестна, `offers` не выводить.
- **Пересечение:** тикет 07 правит те же `[slug]/page.tsx`. Этот тикет идёт раньше (волна 2).

## Цифры

Не применимо.

## Кто зависит

| Место | Что делает | Меняется |
|---|---|---|
| `web/lib/event-meta.ts` | сборка JSON-LD события | да, новое |
| `web/app/perm/events/[slug]/page.tsx`, `web/app/sochi/events/[slug]/page.tsx` | страница события | да — вставка разметки и canonical |
| `web/lib/price.ts` | вид цены | нет, только читается |
| `README.md` п. 13 | роадмап | да — отметить ✅ |

## Тесты, кодирующие старое поведение

| Файл:строка | Как выражено старое поведение |
|---|---|
| — | у `venue-meta.ts` тестов нет; новое поведение покрывается новым тестом |

## Готово когда

- На странице события есть JSON-LD `Event`: `name`, `startDate` с часовым поясом, `location` (`Place` с адресом), `image` — только если картинка годная (правило из спека палитры); `offers` — только при известной цене или «бесплатно».
- На странице события есть canonical.
- Разметка проходит validator.schema.org — проверяет пользователь вручную на превью.
- `npx vitest run`, `npm run build`, `npm run lint` проходят; README п. 13 отмечен.
- Выполнено обновление файла map.md

## Answer

2026-09-29, ветка `feat/event-jsonld` (в основном чекауте, без worktree: `node_modules` уже там — отступление от шага 5 протокола).

- **Разметка:** `web/lib/event-meta.ts` — `eventUrl`, `eventJsonLd`, `jsonLdScript`. `Event`: `name`, `url`, `startDate` (`YYYY-MM-DDTHH:MM:00+05:00` у Перми, `+03:00` у Сочи; без `timeStart` — только дата), `endDate` только при `timeEnd`, `location` — `Place` с `PostalAddress` (`streetAddress` = `address`, `addressLocality` = город), `image` только при `isUsableImage` (из `venue-styles.ts`; строгое правило спека палитры — p7/07), `offers` — `Offer` с `price = priceMin` (или 0 для «бесплатно»), `RUB`, `url = sourceUrl`; при `priceKind = unknown` — без `offers`. У событий `date = "always"` разметки `Event` нет (нет `startDate`); таких в БД на 2026-09-29 — 0.
- **Часовой пояс:** `cityUtcOffset(city)` в `web/lib/dateUtil.ts` — сдвиг через `Intl` (`longOffset`) по той же `CITY_TIMEZONES`, второй таблицы нет.
- **Экранирование:** `jsonLdScript` заменяет `<` на `\u003c` — название из источника с `</script>` не закрывает тег. У площадок (`components/VenueDetail.tsx:31`) та же дыра не тронута — вне тикета.
- **Страницы:** в обеих `app/{perm,sochi}/events/[slug]/page.tsx` — `alternates.canonical` в `generateMetadata` и `<script type="application/ld+json">`. README п. 13 → ✅, дерево `lib/` дополнено.
- **Проверка:** `event-meta.test.ts` (8 тестов) написан первым — красный (модуля нет) → зелёный. `npx vitest run` — 131 passed (было 123); `npm run build` проходит; `npm run lint` — одно старое предупреждение в `layout.tsx`. Preview (`next dev`): `/perm/events/kontsert-muzyka-nas-svyazala-2026-09-30` — canonical и `Event` со `startDate` `2026-09-30T17:00:00+05:00`, `offers.price` 0; `/sochi/events/mezhdunarodnaya-restorannaya-premiya-wheretoeat-yug-2026-2026-09-28` — `startDate` только датой, `addressLocality` «Сочи», консоль без ошибок. Домен в URL локально — фолбэк `afisha-site.ru` (как у площадок), на проде — `NEXT_PUBLIC_SITE_URL`.
- **Не сделано сессией:** validator.schema.org — шаг пользователя по «Готово когда»; до него тикет `open`.
- **Замечено по данным (не правилось):** у события Сочи `address` = название отеля, без улицы — в `streetAddress` уходит оно же; это зона p7/02.

Локализация: `git grep -n -e "ld+json" -e canonical -e event-meta -e venue-meta -e SITE_URL -- web README.md`, найдено 9 мест (сверх тикета: `lib/dateUtil.ts` — приватная `CITY_TIMEZONES`, `lib/venue-styles.ts` — `isUsableImage`, README `:263` — дерево `lib/`; `sitemap.ts`/`robots.ts` со своими `SITE_URL` — не меняются)
Расхождения цифр: строки `alt` в `[slug]/page.tsx` съехали с 83/85 на 94/96 (к этому тикету не относятся); иначе нет
