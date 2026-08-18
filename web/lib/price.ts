/**
 * Смысл цены события.
 *
 * В БД `price_max = 0` означает две разные вещи: «бесплатно» и «цена неизвестна».
 * На 2026-08 в Перми это 347 против 175 событий. Различить их можно только по
 * строке `price_text`, которую пишет LLM («Бесплатно» против «по билетам»).
 *
 * Это заплатка над проблемой данных: устойчивое решение — отдельная колонка,
 * заполняемая парсером. До тех пор каждый потребитель обязан выводить смысл
 * заново, поэтому вывод живёт здесь в единственном экземпляре.
 */

import type { EventItem } from "./types";

const FREE_RE = /бесплатн|вход свободн|свободный вход|^0\s*₽|^от 0\s*₽|^0$/i;

export type PriceKind = "free" | "known" | "unknown";

export function priceKind(event: Pick<EventItem, "priceMax" | "priceText">): PriceKind {
  if (event.priceMax > 0) return "known";
  return FREE_RE.test(event.priceText ?? "") ? "free" : "unknown";
}
