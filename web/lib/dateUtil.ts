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
