/**
 * Клиентская фильтрация событий.
 * Все вычисления дат — синхронные, делаются в render-функции CityView (client component).
 * SSR-mismatch невозможен: серверный prerender использует DEFAULT_FILTERS (when='any', даты не задействованы).
 */

import type { EventItem, EventType } from "./types";

export type WhenFilter = "today" | "tomorrow" | "weekend" | "any";

export interface Filters {
  types: ReadonlySet<EventType>;
  when: WhenFilter;
  priceMin: number;
  priceMax: number;
  /** Если true — скрыть события с date='always' (боулинг/бильярд/картинг). */
  onlyFixedDate: boolean;
}

export const ALL_TYPES: readonly EventType[] = [
  "quiz",
  "standup",
  "bowling",
  "billiards",
  "karting",
];

export const DEFAULT_FILTERS: Filters = {
  types: new Set(ALL_TYPES),
  when: "any",
  priceMin: 0,
  priceMax: 5000,
  onlyFixedDate: true,
};

function toYMD(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * Возвращает Set дат «этих выходных» (ближайших Сб и Вс, включая сегодня если оно Сб/Вс).
 * Окно — 7 дней вперёд начиная с today, чтобы поймать ближайшие Сб и Вс.
 */
function getWeekendDates(today: Date): Set<string> {
  const result = new Set<string>();
  for (let i = 0; i < 7; i++) {
    const d = new Date(today);
    d.setDate(today.getDate() + i);
    const dow = d.getDay();
    if (dow === 6 || dow === 0) result.add(toYMD(d));
  }
  return result;
}

export function applyFilters(events: EventItem[], filters: Filters): EventItem[] {
  const now = new Date();
  const today = toYMD(now);
  const tomorrowDate = new Date(now);
  tomorrowDate.setDate(now.getDate() + 1);
  const tomorrow = toYMD(tomorrowDate);
  const weekend = filters.when === "weekend" ? getWeekendDates(now) : null;

  return events.filter((event) => {
    // 1. Тип
    if (!filters.types.has(event.type)) return false;

    // 2. Только с фиксированной датой
    if (filters.onlyFixedDate && event.date === "always") return false;

    // 3. Когда (для 'always' пропускаем — оно доступно всегда; иначе сравниваем точно)
    if (filters.when !== "any" && event.date !== "always") {
      if (filters.when === "today" && event.date !== today) return false;
      if (filters.when === "tomorrow" && event.date !== tomorrow) return false;
      if (filters.when === "weekend" && !weekend!.has(event.date)) return false;
    }

    // 4. Цена — пересечение диапазонов
    if (event.priceMax < filters.priceMin) return false;
    if (event.priceMin > filters.priceMax) return false;

    return true;
  });
}
