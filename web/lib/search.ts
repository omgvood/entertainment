/**
 * Ядро пользовательского поиска. Чистые функции, без React и DOM.
 *
 * Поиск работает целиком в браузере по уже загруженному массиву событий
 * (571 карточка для Перми): сайт статический, runtime-запросов нет.
 */

import type { EventItem, VenueItem } from "./types";
import { EVENT_TYPE_LABELS, getVenueTypeLabel } from "./types";
import { priceKind } from "./price";
import { TYPE_SYNONYMS, VENUE_TYPE_SYNONYMS, INTENT_SYNONYMS, STOP_WORDS } from "./search-synonyms";
import { addDaysUTC } from "./dateUtil";

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

const MORPH_FACTOR = 0.6;
const PHRASE_TITLE_BONUS = 100;
const PHRASE_VENUE_BONUS = 50;
const BOOST_SOON = 15;
const BOOST_IMAGE = 5;

export interface QueryTerm {
  /** Сам токен плюс токены тегов, в которые он разворачивается. */
  variants: string[];
}

/** Предрассчитанный разворот намерений: слово пользователя → токены тега. */
const INTENT_INDEX = Object.entries(INTENT_SYNONYMS).map(([tag, synonyms]) => ({
  tagTokens: tokenize(tag).filter((t) => !STOP_WORDS.has(t)),
  triggers: [tag, ...synonyms].flatMap(tokenize).filter((t) => !STOP_WORDS.has(t)),
}));

function expandIntent(token: string): string[] {
  const out: string[] = [];
  for (const entry of INTENT_INDEX) {
    if (entry.triggers.some((trigger) => tokensMatch(token, trigger) !== "none")) {
      out.push(...entry.tagTokens);
    }
  }
  return out;
}

export function parseQuery(query: string): QueryTerm[] {
  return tokenize(query)
    .filter((t) => !STOP_WORDS.has(t))
    .map((t) => ({ variants: [t, ...expandIntent(t)] }));
}

/**
 * Скор документа или null, если хотя бы один термин не найден (AND-семантика).
 * Для каждого термина берём лучшее поле, а не сумму по полям: иначе слово,
 * встречающееся и в названии, и в описании, весит больше точного попадания
 * в название, и длинные описания начинают выигрывать.
 */
export function scoreDoc<T>(
  doc: SearchDoc<T>,
  terms: QueryTerm[],
  phrase: string,
): number | null {
  let score = 0;

  for (const term of terms) {
    let best = 0;
    for (const field of doc.fields) {
      if (field.weight <= best) continue; // лучше уже не станет
      for (const docToken of field.tokens) {
        for (const variant of term.variants) {
          const kind = tokensMatch(variant, docToken);
          if (kind === "none") continue;
          const value = field.weight * (kind === "exact" ? 1 : MORPH_FACTOR);
          if (value > best) best = value;
        }
      }
    }
    if (best === 0) return null;
    score += best;
  }

  // Фразовый бонус осмыслен только для многословных запросов: для одного слова
  // он повторяет то, что уже посчитал точный матч.
  if (terms.length >= 2) {
    if (doc.titleText.includes(phrase)) score += PHRASE_TITLE_BONUS;
    if (doc.venueText.includes(phrase)) score += PHRASE_VENUE_BONUS;
  }

  return score;
}

export interface EventHit {
  kind: "event";
  item: EventItem;
  score: number;
}

export interface VenueHit {
  kind: "venue";
  item: VenueItem;
  score: number;
}

export type SearchHit = EventHit | VenueHit;

export function searchEvents(
  docs: SearchDoc<EventItem>[],
  query: string,
  today: string,
): EventHit[] {
  const terms = parseQuery(query);
  if (terms.length === 0) return [];

  const phrase = normalize(query);
  const tomorrow = addDaysUTC(today, 1);
  const hits: EventHit[] = [];

  for (const doc of docs) {
    const base = scoreDoc(doc, terms, phrase);
    if (base === null) continue;

    let score = base;
    // Бусты поднимают, но никогда не отсекают.
    if (doc.item.date === today || doc.item.date === tomorrow) score += BOOST_SOON;
    if (doc.item.imageUrl) score += BOOST_IMAGE;

    hits.push({ kind: "event", item: doc.item, score });
  }

  hits.sort((a, b) => b.score - a.score || a.item.date.localeCompare(b.item.date));
  return hits;
}

export function searchVenues(docs: SearchDoc<VenueItem>[], query: string): VenueHit[] {
  const terms = parseQuery(query);
  if (terms.length === 0) return [];

  const phrase = normalize(query);
  const hits: VenueHit[] = [];

  for (const doc of docs) {
    const score = scoreDoc(doc, terms, phrase);
    if (score === null) continue;
    hits.push({ kind: "venue", item: doc.item, score });
  }

  hits.sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name));
  return hits;
}
