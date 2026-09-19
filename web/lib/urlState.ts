/**
 * Состояние главной города в URL: ?date=&type=&pmin=&pmax=&q=.
 * Нужно, чтобы подборкой можно было поделиться и чтобы возврат со страницы
 * события не сбрасывал фильтры. Значения по умолчанию в URL не пишутся.
 */

import type { City, EventType } from "./types";
import { ALL_TYPES, DEFAULT_FILTERS, type DateSel, type Filters } from "./filters";
import { addDaysUTC } from "./dateUtil";

const NAMED_DATES: readonly string[] = ["today", "tomorrow", "weekend", "all"];
const YMD_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Реальная календарная дата: Date молча переносит 30 февраля на 2 марта, ловим сверкой. */
function isRealYmd(s: string): boolean {
  return YMD_RE.test(s) && !Number.isNaN(Date.parse(`${s}T00:00:00Z`)) && addDaysUTC(s, 0) === s;
}

function parseDate(raw: string | null, today: string): DateSel | null {
  if (!raw) return null;
  if (NAMED_DATES.includes(raw)) return raw;
  // День из прошлого в старой ссылке уже не показать — открываем умолчание.
  if (isRealYmd(raw) && raw >= today) return raw;
  return null;
}

function parseNonNegInt(raw: string | null): number | null {
  if (raw === null || !/^\d+$/.test(raw)) return null;
  return Number(raw);
}

export function parseState(search: string, today: string): { filters: Filters; query: string } {
  const params = new URLSearchParams(search);
  const types = new Set(
    (params.get("type") ?? "")
      .split(",")
      .filter((t): t is EventType => (ALL_TYPES as readonly string[]).includes(t)),
  );
  return {
    filters: {
      date: parseDate(params.get("date"), today),
      types,
      priceMin: parseNonNegInt(params.get("pmin")) ?? DEFAULT_FILTERS.priceMin,
      priceMax: parseNonNegInt(params.get("pmax")),
    },
    query: params.get("q") ?? "",
  };
}

export function serializeState(filters: Filters, query: string): string {
  const params = new URLSearchParams();
  const q = query.trim();
  if (q) params.set("q", q);
  if (filters.date !== null) params.set("date", filters.date);
  if (filters.types.size > 0) {
    params.set("type", ALL_TYPES.filter((t) => filters.types.has(t)).join(","));
  }
  if (filters.priceMin > 0) params.set("pmin", String(filters.priceMin));
  if (filters.priceMax !== null) params.set("pmax", String(filters.priceMax));
  const s = params.toString();
  return s ? `?${s}` : "";
}

/** Ключ sessionStorage, где главная оставляет свою строку запроса для ссылки «← Все события». */
export function listStateKey(city: City): string {
  return `afisha:list:${city}`;
}
