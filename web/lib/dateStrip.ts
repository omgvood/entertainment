/**
 * Лента дат над выдачей: Сегодня · Завтра · Выходные · отдельные дни · Все даты.
 * Дата — первое решение пользователя, поэтому она всегда на виду, а выдача
 * по умолчанию показывает один день, а не всю афишу на месяц.
 */

import type { DateSel } from "./filters";
import { addDaysUTC, formatStripDay } from "./dateUtil";

export interface StripItem {
  sel: DateSel;
  label: string;
}

/** Сколько дней вперёд показывать по отдельности, считая сегодня и завтра. */
const STRIP_DAYS = 14;

export function buildDateStrip(today: string): StripItem[] {
  const items: StripItem[] = [
    { sel: "today", label: "Сегодня" },
    { sel: "tomorrow", label: "Завтра" },
    { sel: "weekend", label: "Выходные" },
  ];
  for (let i = 2; i < STRIP_DAYS; i++) {
    const ymd = addDaysUTC(today, i);
    items.push({ sel: ymd, label: formatStripDay(ymd) });
  }
  items.push({ sel: "all", label: "Все даты" });
  return items;
}

/** Первый отдельный день ленты, где есть события; «Выходные» и «Все даты» не в счёт. */
export function firstNonEmptyDay(
  items: StripItem[],
  counts: ReadonlyMap<DateSel, number>,
): DateSel | null {
  for (const item of items) {
    if (item.sel === "weekend" || item.sel === "all") continue;
    if ((counts.get(item.sel) ?? 0) > 0) return item.sel;
  }
  return null;
}
