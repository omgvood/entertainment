/**
 * Группировка уже отфильтрованного (по типу/цене) списка событий на 3 корзины
 * для главной города. today — готовая календарная строка от getCityToday(city),
 * никакого нового Date() для текущего момента здесь нет.
 */

import type { EventItem } from "./types";
import { addDaysUTC } from "./dateUtil";

export interface DayGroups {
  today: EventItem[];
  tomorrow: EventItem[];
  later: EventItem[];
}

export function groupByDay(events: EventItem[], today: string): DayGroups {
  const tomorrow = addDaysUTC(today, 1);
  const result: DayGroups = { today: [], tomorrow: [], later: [] };

  for (const event of events) {
    if (event.date === today) result.today.push(event);
    else if (event.date === tomorrow) result.tomorrow.push(event);
    else result.later.push(event);
  }

  return result;
}
