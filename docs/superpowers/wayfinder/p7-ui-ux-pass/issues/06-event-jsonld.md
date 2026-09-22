# Страницы событий без разметки Schema.org Event

Type: task
Скилл: `superpowers:test-driven-development` — разметку собирает чистая функция (по образцу `venue-meta.ts`), её вывод фиксируется тестом первым
Status: backlog (волна 2)
Blocked by: —
Ветка: `feat/event-jsonld`

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

<Заполняется в конце сессии.>

Локализация: `<команда>`, найдено N мест
Расхождения цифр: <или «нет»>
