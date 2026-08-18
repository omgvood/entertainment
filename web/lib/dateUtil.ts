/**
 * Арифметика над календарными датами-строками YYYY-MM-DD без обращения
 * к локальной таймзоне выполнения (парсинг/форматирование всегда через UTC-компоненты,
 * поэтому результат не зависит от TZ сервера сборки или браузера).
 */

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
