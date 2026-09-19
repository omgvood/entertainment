/**
 * Серии событий: одно и то же событие (выставка, регулярная экскурсия, цирк
 * на гастролях) лежит в БД отдельной строкой на каждую дату. Лента показывает
 * серию одной карточкой с пометкой «ещё N дат».
 *
 * Ключ консервативный — название + площадка. «Пермская галерея» и «Пермская
 * художественная галерея» не склеиваются: лишняя карточка безобиднее, чем
 * слияние разных событий (тот же выбор, что в fuzzy-дедупе парсера).
 */

import type { EventItem } from "./types";
import { normalize } from "./search";

export interface EventSeries {
  key: string;
  /** Все даты серии по возрастанию даты и времени начала. */
  events: EventItem[];
}

/** Возрастные метки «6+», «(12+)»: один спектакль приходит из разных источников с меткой и без. */
const AGE_MARK_RE = /\(?\b\d{1,2}\+\)?/g;

export function seriesKey(e: Pick<EventItem, "title" | "venueName">): string {
  return `${normalize(e.title.replace(AGE_MARK_RE, " "))}|${normalize(e.venueName)}`;
}

/** По дате, затем по времени начала; событие без времени — в конец своего дня. */
export function compareByDateTime(a: EventItem, b: EventItem): number {
  if (a.date !== b.date) return a.date < b.date ? -1 : 1;
  const ta = a.timeStart ?? "99:99";
  const tb = b.timeStart ?? "99:99";
  return ta < tb ? -1 : ta > tb ? 1 : 0;
}

/** Серии в порядке первого появления во входе — для поиска это порядок релевантности. */
export function groupSeries(events: EventItem[]): EventSeries[] {
  const byKey = new Map<string, EventSeries>();
  for (const event of events) {
    const key = seriesKey(event);
    const existing = byKey.get(key);
    if (existing) existing.events.push(event);
    else byKey.set(key, { key, events: [event] });
  }
  const result = [...byKey.values()];
  for (const series of result) series.events.sort(compareByDateTime);
  return result;
}

/** Сколько ещё различных дат у серии, кроме показанной, и до какой даты она идёт. */
export function otherDates(
  series: EventSeries,
  shown: EventItem,
): { count: number; lastDate: string } | null {
  const dates = new Set(series.events.map((e) => e.date));
  dates.delete(shown.date);
  if (dates.size === 0) return null;
  return { count: dates.size, lastDate: series.events[series.events.length - 1].date };
}

/** Группы подряд идущих элементов с одной датой; вход должен быть отсортирован по дате. */
export function groupByDate<T>(
  items: T[],
  dateOf: (item: T) => string,
): { date: string; items: T[] }[] {
  const groups: { date: string; items: T[] }[] = [];
  for (const item of items) {
    const date = dateOf(item);
    const last = groups[groups.length - 1];
    if (last && last.date === date) last.items.push(item);
    else groups.push({ date, items: [item] });
  }
  return groups;
}
