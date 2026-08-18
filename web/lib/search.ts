/**
 * Ядро пользовательского поиска. Чистые функции, без React и DOM.
 *
 * Поиск работает целиком в браузере по уже загруженному массиву событий
 * (571 карточка для Перми): сайт статический, runtime-запросов нет.
 */

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
