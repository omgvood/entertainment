# Час города: helper текущего времени

Type: task
Скилл: superpowers:test-driven-development — тест с `vi.setSystemTime` на два города
Status: closed
Blocked by: —
Ветка: `fix/city-clock-helper`

## Question

Для пометок «через 2 ч» и «началось в 15:00» нужен текущий момент в таймзоне города, а не в таймзоне зрителя. `getCityToday` уже живёт в `web/lib/dateUtil.ts` и отдаёт только календарную дату; часов и минут города не отдаёт никто. `new Date().getHours()` у зрителя из Москвы даст сдвиг на два часа относительно Перми.

## Контекст

- На `master` в `dateUtil.ts` уже есть `addDaysUTC`, `formatDayMonth`, `getCityToday`, `weekdayUTC`, `formatStripDay`, `formatWeekdayDayMonth` — helper времени добавляется к ним.
- Таймзоны: Пермь `Asia/Yekaterinburg`, Сочи `Europe/Moscow`.
- Файл намеренно работает на UTC-компонентах и не знает локальной таймзоны — новый helper должен идти тем же путём, через `Intl.DateTimeFormat` с `timeZone`.
- Потребители: карточка (тикет 07) и счётчики чипов после решения тикета 06.

## Готово когда

- В `web/lib/dateUtil.ts` есть функция, отдающая «сейчас» города как `HH:MM` или минуты от полуночи.
- Тест в `dateUtil.test.ts` с `vi.setSystemTime` проверяет два города в один момент и получает разное время.
- `npx vitest run` зелёный.

## Answer

Локализация: `grep -rn "getCityToday\|CITY_TIMEZONES"` (символ) + `grep -rn "Asia/Yekaterinburg\|Europe/Moscow"` и `grep -rn "getHours\|setSystemTime"` (значение), найдено 12 мест в коде — и ни одного потребителя «часов города»: `getCityToday` всюду используется только как календарная дата (`page.tsx` ×4, `sitemap.ts`, `CityView.tsx`, ре-экспорт в `events.ts`), `getHours()` в `web/` не встречается вообще. Таймзоны заданы ровно в одном месте — `CITY_TIMEZONES` в `dateUtil.ts`. Значит helper — чистое дополнение, ломать нечего; правку видят только `dateUtil.ts` и `dateUtil.test.ts`.

Развилка из «Готово когда» («`HH:MM` или минуты от полуночи») решена в пользу **минут от полуночи**: `getCityNowMinutes(city): number`. Оба будущих потребителя (06 — «идёт сейчас», 07 — «через 2 ч») считают разницу, а «началось в 15:00» берёт время из данных события, не из «сейчас». `HH:MM` выводится из минут, обратно — нет.

Реализация (`web/lib/dateUtil.ts`): `Intl.DateTimeFormat("en-GB", { timeZone, hour, minute, hourCycle: "h23" }).formatToParts(new Date())` — тем же путём, что `getCityToday`, без обращения к локальной таймзоне. `hourCycle: "h23"` взят явно: при `hour12: false` полночь в части сред приходит как `24:00`, и тест «полночь города — 0 минут» это ловит.

TDD: тест написан первым, падал с `TypeError: getCityNowMinutes is not a function` (2 failed | 4 passed), после правки — `npx vitest run`: 7 файлов, 96 тестов, всё зелёное; `npx tsc --noEmit` чистый.

Два случая в тесте: момент `2026-09-19T10:30:00Z` даёт Перми 930 минут (15:30), Сочи 810 (13:30) — разное время в один момент; момент `2026-09-18T19:00:00Z` даёт Перми 0 — граница полуночи.

Не сделано осознанно: форматтер `HH:MM` (нет потребителя), README не трогал — helper без потребителя описывать в разделе архитектуры рано, строка про `dateUtil.ts` (`README.md:1893`) пойдёт обновлением вместе с тикетом 07.
