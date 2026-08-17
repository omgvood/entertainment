/**
 * Стили карточек/страниц площадок по типу.
 * В отличие от EventType (закрытый enum), тип площадки — string из БД,
 * поэтому ключи мягкие, а getVenueStyle() гарантирует fallback.
 * Цвета — та же неоновая палитра, что в web/lib/event-styles.ts (bowling/billiards/karting/quest
 * используют те же hue, что и одноимённые EventType, для визуальной согласованности).
 */

const BADGE_STYLES: Record<string, string> = {
  bowling: "text-[#35e0c8] border-[#35e0c84d] bg-bg",
  billiards: "text-[#35e0c8] border-[#35e0c84d] bg-bg",
  karting: "text-[#ffb37a] border-[#ff9d4d66] bg-bg",
  quest: "text-[#35e0c8] border-[#35e0c84d] bg-bg",
  other: "text-[#a89dc4] border-[#4a3d6b] bg-bg",
};

const PLACEHOLDER_STYLES: Record<string, { gradient: string; emoji: string }> = {
  bowling: { gradient: "from-[#0f4a3f] to-[#1b0f2e]", emoji: "🎳" },
  billiards: { gradient: "from-[#0f4a3f] to-[#1b0f2e]", emoji: "🎱" },
  karting: { gradient: "from-[#5a2e0c] to-[#1b0f2e]", emoji: "🏎️" },
  quest: { gradient: "from-[#0f4a3f] to-[#1b0f2e]", emoji: "🗝️" },
  other: { gradient: "from-[#2b2440] to-[#1b0f2e]", emoji: "✨" },
};

export function venueBadgeStyle(type: string): string {
  return BADGE_STYLES[type] ?? BADGE_STYLES.other;
}

export function venuePlaceholder(type: string): { gradient: string; emoji: string } {
  return PLACEHOLDER_STYLES[type] ?? PLACEHOLDER_STYLES.other;
}

/** svg-иконки не годятся как фото карточки. */
export function isUsableImage(url?: string): boolean {
  if (!url) return false;
  if (url.toLowerCase().endsWith(".svg")) return false;
  return true;
}
