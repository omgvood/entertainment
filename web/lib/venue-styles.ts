/**
 * Стили карточек/страниц площадок по типу.
 * В отличие от EventType (закрытый enum), тип площадки — string из БД,
 * поэтому ключи мягкие, а getVenueStyle() гарантирует fallback.
 */

const BADGE_STYLES: Record<string, string> = {
  bowling: "bg-[#e7f5ff] text-[#1971c2]",
  billiards: "bg-[#e7f9ec] text-[#2b8a3e]",
  karting: "bg-[#fff4e0] text-[#d97706]",
  quest: "bg-[#e7fbf5] text-[#0d9488]",
  other: "bg-[#eef0f3] text-[#475569]",
};

const PLACEHOLDER_STYLES: Record<string, { gradient: string; emoji: string }> = {
  bowling: { gradient: "from-[#e7f5ff] to-[#a5d8ff]", emoji: "🎳" },
  billiards: { gradient: "from-[#e7f9ec] to-[#b2f2bb]", emoji: "🎱" },
  karting: { gradient: "from-[#fff4e0] to-[#ffd8a8]", emoji: "🏎️" },
  quest: { gradient: "from-[#e7fbf5] to-[#99f6e4]", emoji: "🗝️" },
  other: { gradient: "from-[#eef0f3] to-[#cbd5e1]", emoji: "✨" },
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
