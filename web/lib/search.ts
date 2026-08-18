/**
 * Ядро пользовательского поиска. Чистые функции, без React и DOM.
 *
 * Поиск работает целиком в браузере по уже загруженному массиву событий
 * (571 карточка для Перми): сайт статический, runtime-запросов нет.
 */

import type { EventItem, VenueItem } from "./types";
import { EVENT_TYPE_LABELS, getVenueTypeLabel } from "./types";
import { priceKind } from "./price";
import { TYPE_SYNONYMS, VENUE_TYPE_SYNONYMS } from "./search-synonyms";

export type MatchKind = "exact" | "morph" | "none";

export function normalize(s: string): string {
  return s
    .toLowerCase()
    // «ё» (U+0451) лежит за границей диапазона «а-я» (U+0430–U+044F),
    // поэтому замена обязана идти до фильтрации — иначе «ёлка» станет «лка».
    .replace(/ё/g, "е")
    .replace(/[^a-zа-я0-9]+/g, " ")
    // «1 000» → «1000»: разряды числа, а не два разных токена.
    .replace(/(\d)\s+(?=\d{3}\b)/g, "$1")
    .trim();
}

export function tokenize(s: string): string[] {
  return normalize(s).split(" ").filter(Boolean);
}

/**
 * Морфология без стеммера: считаем совпадением общий префикс, допуская
 * расхождение до двух символов в хвосте, но не короче трёх символов.
 *
 * Простого startsWith недостаточно: русские окончания меняют последнюю букву,
 * а не только дописывают её — «опера»/«оперы» не префикс друг друга.
 * Порог в три символа заодно даёт typeahead: «сте» находит «стендап».
 */
export function tokensMatch(a: string, b: string): MatchKind {
  if (a === b) return "exact";
  const min = Math.min(a.length, b.length);
  const need = Math.max(3, min - 2);
  let common = 0;
  while (common < min && a[common] === b[common]) common++;
  return common >= need ? "morph" : "none";
}

export interface DocField {
  weight: number;
  tokens: string[];
}

export interface SearchDoc<T> {
  item: T;
  fields: DocField[];
  /** Нормализованное название — для фразового бонуса. */
  titleText: string;
  /** Нормализованное имя площадки — для фразового бонуса. */
  venueText: string;
}

export function buildEventDoc(event: EventItem): SearchDoc<EventItem> {
  const typeWords = [EVENT_TYPE_LABELS[event.type], ...TYPE_SYNONYMS[event.type]].join(" ");
  // Синтетический токен по price_text, а не по price_max: нулевая цена в БД
  // означает и «бесплатно», и «неизвестно», см. lib/price.ts.
  const freeWords = priceKind(event) === "free" ? "бесплатно free вход свободный" : "";

  return {
    item: event,
    fields: [
      { weight: 100, tokens: tokenize(event.title) },
      { weight: 60, tokens: tokenize(typeWords) },
      { weight: 50, tokens: tokenize(event.venueName) },
      { weight: 30, tokens: tokenize(event.organizer ?? "") },
      { weight: 20, tokens: tokenize([...event.tags, freeWords].join(" ")) },
      { weight: 10, tokens: tokenize(event.description ?? "") },
    ],
    titleText: normalize(event.title),
    venueText: normalize(event.venueName),
  };
}

export function buildVenueDoc(venue: VenueItem): SearchDoc<VenueItem> {
  const typeWords = [
    getVenueTypeLabel(venue.type),
    ...(VENUE_TYPE_SYNONYMS[venue.type] ?? []),
  ].join(" ");

  return {
    item: venue,
    fields: [
      { weight: 100, tokens: tokenize(venue.name) },
      { weight: 60, tokens: tokenize(typeWords) },
      { weight: 15, tokens: tokenize(venue.address ?? "") },
    ],
    titleText: normalize(venue.name),
    venueText: "",
  };
}
