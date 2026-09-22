/**
 * Смысл цены события.
 *
 * В БД `price_max = 0` означает две разные вещи: «бесплатно» и «цена неизвестна».
 * На 2026-09-20 в Перми это 397 строк: у 208 есть словесный признак бесплатности,
 * у 75 — нулевая строка вида `0 ₽`. Различить их можно только по строке
 * `price_text`, которую пишет LLM («Бесплатно» против «по билетам»).
 *
 * `0 ₽` и `от 0 ₽` бесплатностью не считаются: LLM пишет их, когда цены не знает,
 * а у источника цена есть (проверено на занятиях Пермской галереи 2026-09-20).
 *
 * Это заплатка над проблемой данных: устойчивое решение — отдельная колонка,
 * заполняемая парсером. До тех пор каждый потребитель обязан выводить смысл
 * заново, поэтому вывод живёт здесь в единственном экземпляре.
 */

import type { EventItem } from "./types";

const FREE_RE = /бесплатн|вход свободн|свободный вход/i;

export type PriceKind = "free" | "known" | "unknown";

export function priceKind(event: Pick<EventItem, "priceMax" | "priceText">): PriceKind {
  if (event.priceMax > 0) return "known";
  return FREE_RE.test(event.priceText ?? "") ? "free" : "unknown";
}

/**
 * Бейдж цены для карточки быстрого просмотра: короткая метка вместо сырого
 * `priceText` («27900 руб.», «от 235.6 млн ₽»). `unknown` бейджа не даёт —
 * потребитель показывает `priceText` как есть.
 */
export function priceBadge(
  event: Pick<EventItem, "priceMin" | "priceMax" | "priceText">,
): string | null {
  const kind = priceKind(event);
  if (kind === "free") return "Бесплатно";
  if (kind === "unknown") return null;
  return event.priceMin === event.priceMax
    ? `${event.priceMin} ₽`
    : `от ${event.priceMin} ₽`;
}
