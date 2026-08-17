/**
 * Клиентская фильтрация событий.
 * Все вычисления дат — синхронные, делаются в render-функции CityView (client component).
 * SSR-mismatch невозможен: серверный prerender использует DEFAULT_FILTERS (when='any', даты не задействованы).
 */

import type { EventItem, EventType } from "./types";
import { addDaysUTC } from "./dateUtil";

export type WhenFilter = "today" | "tomorrow" | "weekend" | "any";

export interface Filters {
  types: ReadonlySet<EventType>;
  when: WhenFilter;
  priceMin: number;
  priceMax: number;
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

export const DEFAULT_FILTERS: Filters = {
  types: new Set(ALL_TYPES),
  when: "any",
  priceMin: 0,
  priceMax: 5000,
};

/**
 * Возвращает Set дат «этих выходных» (ближайших Сб и Вс, включая сегодня если оно Сб/Вс).
 * Окно — 7 дней вперёд начиная с today, чтобы поймать ближайшие Сб и Вс.
 * dayOfWeekUTC берём из того же UTC-парсинга, что и addDaysUTC — иначе день недели
 * может съехать на границе суток при отличии локальной TZ от UTC.
 */
function getWeekendDates(today: string): Set<string> {
  const result = new Set<string>();
  for (let i = 0; i < 7; i++) {
    const ymd = addDaysUTC(today, i);
    const dow = new Date(`${ymd}T00:00:00Z`).getUTCDay();
    if (dow === 6 || dow === 0) result.add(ymd);
  }
  return result;
}

export function applyFilters(events: EventItem[], filters: Filters, today: string): EventItem[] {
  const tomorrow = addDaysUTC(today, 1);
  const weekend = filters.when === "weekend" ? getWeekendDates(today) : null;

  return events.filter((event) => {
    // 1. Тип
    if (!filters.types.has(event.type)) return false;

    // 2. Когда
    if (filters.when !== "any") {
      if (filters.when === "today" && event.date !== today) return false;
      if (filters.when === "tomorrow" && event.date !== tomorrow) return false;
      if (filters.when === "weekend" && !weekend!.has(event.date)) return false;
    }

    // 3. Цена — пересечение диапазонов
    if (event.priceMax < filters.priceMin) return false;
    if (event.priceMin > filters.priceMax) return false;

    return true;
  });
}
