/**
 * Арифметика над календарными датами-строками YYYY-MM-DD без обращения
 * к локальной таймзоне выполнения (парсинг/форматирование всегда через UTC-компоненты,
 * поэтому результат не зависит от TZ сервера сборки или браузера).
 */

import type { City } from "./types";

export function addDaysUTC(ymd: string, days: number): string {
  const d = new Date(`${ymd}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

const MONTHS_RU = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

/** "8 августа" — из календарной строки YYYY-MM-DD, без времени. */
export function formatDayMonth(ymd: string): string {
  const [, m, d] = ymd.split("-").map(Number);
  return `${d} ${MONTHS_RU[m - 1]}`;
}

/** IANA-таймзона города — «сегодня» считается по местному времени, не по UTC сервера сборки. */
const CITY_TIMEZONES: Record<City, string> = {
  perm: "Asia/Yekaterinburg", // UTC+5
  sochi: "Europe/Moscow", // UTC+3
};

/** «Сегодня» в таймзоне города — единственное место в кодовой базе, где текущий момент превращается в календарную дату. */
export function getCityToday(city: City): string {
  const timezone = CITY_TIMEZONES[city] ?? "Europe/Moscow";
  // en-CA даёт YYYY-MM-DD; timeZone делает дату местной (билд идёт в 21:00 UTC).
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

/** «Сейчас» в таймзоне города — минуты от местной полуночи, чтобы «через 2 ч» считалось по часам города, а не зрителя. */
export function getCityNowMinutes(city: City): number {
  const timezone = CITY_TIMEZONES[city] ?? "Europe/Moscow";
  // hourCycle h23, иначе полночь приходит как 24:00.
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const hour = Number(parts.find((p) => p.type === "hour")?.value);
  const minute = Number(parts.find((p) => p.type === "minute")?.value);
  return hour * 60 + minute;
}

const WEEKDAYS_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

/** День недели календарной строки: 0 — воскресенье, 6 — суббота. */
export function weekdayUTC(ymd: string): number {
  return new Date(`${ymd}T00:00:00Z`).getUTCDay();
}

/** "Пн 21" — подпись дня в ленте дат. */
export function formatStripDay(ymd: string): string {
  return `${WEEKDAYS_SHORT[weekdayUTC(ymd)]} ${Number(ymd.slice(8))}`;
}

/** "Сб, 19 сентября" — заголовок дня в выдаче и в «Других датах». */
export function formatWeekdayDayMonth(ymd: string): string {
  return `${WEEKDAYS_SHORT[weekdayUTC(ymd)]}, ${formatDayMonth(ymd)}`;
}
