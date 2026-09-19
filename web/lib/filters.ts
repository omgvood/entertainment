/**
 * Фильтрация серий событий. Все вычисления дат — синхронные, делаются в
 * render-функции CityView (client component). SSR рендерит DEFAULT_FILTERS —
 * mismatch невозможен, т.к. дата/тип/цена читаются из URL только на клиенте.
 */

import type { EventItem, EventType } from "./types";
import type { EventSeries } from "./series";
import { addDaysUTC, weekdayUTC } from "./dateUtil";
import { priceKind } from "./price";

/** Выбор в ленте дат; кроме именованных — конкретный день `YYYY-MM-DD`. */
export type DateSel = "today" | "tomorrow" | "weekend" | "all" | (string & {});

export interface Filters {
  /** null — «по умолчанию»: сегодня, а если сегодня пусто — ближайший день с событиями. В URL не пишется. */
  date: DateSel | null;
  /** Пустой набор — все типы. */
  types: ReadonlySet<EventType>;
  priceMin: number;
  /** null — без верхней границы. */
  priceMax: number | null;
}

export const ALL_TYPES: readonly EventType[] = [
  "quiz",
  "standup",
  "bowling",
  "billiards",
  "karting",
  "concert",
  "theater",
  "exhibition",
  "festival",
  "quest",
  "party",
  "cinema",
  "sport",
  "education",
  "business",
  "art",
  "kids",
  "food",
  "trip",
  "hobby",
  "science",
  "other",
];

/**
 * Типы, реально присутствующие в событиях города (в порядке ALL_TYPES).
 * Пермь (узкая ниша) покажет только свои типы, Сочи — плюс широкие из KudaGo.
 */
export function availableTypes(events: EventItem[]): EventType[] {
  return ALL_TYPES.filter((t) => events.some((e) => e.type === t));
}

/**
 * Типы, реально присутствующие в событиях города, отсортированные по убыванию
 * частоты (число событий этого типа). При равном count — порядок ALL_TYPES
 * (availableTypes уже возвращает типы в порядке ALL_TYPES, поэтому стабильная
 * сортировка Array.prototype.sort по count сохраняет этот tie-break бесплатно).
 */
export function typesByFrequency(events: EventItem[]): EventType[] {
  const types = availableTypes(events);
  const counts = new Map<EventType, number>();
  for (const t of types) {
    counts.set(t, events.filter((e) => e.type === t).length);
  }
  return [...types].sort((a, b) => counts.get(b)! - counts.get(a)!);
}

export const DEFAULT_FILTERS: Filters = {
  date: null,
  types: new Set(),
  priceMin: 0,
  priceMax: null,
};

/** Тип и цена — всё, что не про дату. */
export function matchesEvent(event: EventItem, filters: Filters): boolean {
  if (filters.types.size > 0 && !filters.types.has(event.type)) return false;

  // Событие с неизвестной ценой («по билетам», «Уточняйте») предикат
  // пропускает: в БД такая цена неотличима от нуля, и прятать карточку
  // из-за пробела в данных хуже, чем показать её. Подробнее — lib/price.ts.
  if (priceKind(event) !== "unknown") {
    if (event.priceMax < filters.priceMin) return false;
    if (filters.priceMax !== null && event.priceMin > filters.priceMax) return false;
  }
  return true;
}

/**
 * Даты «этих выходных»: ближайшие Сб и Вс, включая сегодня. В воскресенье это
 * только сегодня — следующая суббота относится уже к другим выходным.
 */
function getWeekendDates(today: string): Set<string> {
  const result = new Set<string>();
  for (let i = 0; i < 7; i++) {
    const ymd = addDaysUTC(today, i);
    const dow = weekdayUTC(ymd);
    if (dow === 6 || dow === 0) result.add(ymd);
    if (dow === 0) break;
  }
  return result;
}

export function inDateSel(date: string, sel: DateSel, today: string): boolean {
  switch (sel) {
    case "all":
      return true;
    case "today":
      return date === today;
    case "tomorrow":
      return date === addDaysUTC(today, 1);
    case "weekend":
      return getWeekendDates(today).has(date);
    default:
      return date === sel;
  }
}

export interface SeriesView {
  series: EventSeries;
  /** Сеанс, который показывает карточка: первый по дате среди прошедших фильтры и окно. */
  shown: EventItem;
}

export function visibleSeries(
  series: EventSeries[],
  filters: Filters,
  sel: DateSel,
  today: string,
): SeriesView[] {
  const views: SeriesView[] = [];
  for (const s of series) {
    const shown = s.events.find((e) => matchesEvent(e, filters) && inDateSel(e.date, sel, today));
    if (shown) views.push({ series: s, shown });
  }
  return views;
}
