# Час города: helper текущего времени

Type: task
Status: open
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
