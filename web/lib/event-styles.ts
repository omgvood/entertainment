/**
 * Неоновые стили бейджей/плейсхолдеров событий по типу.
 * Аналог web/lib/venue-styles.ts, но для закрытого enum EventType.
 * Единая точка правды — раньше таблицы дублировались в EventCard.tsx
 * и в обеих [slug]/page.tsx.
 * Классы — полные литералы (не собираются из хекс-переменных через шаблонные
 * строки), иначе Tailwind не найдёт arbitrary-value классы при сканировании.
 */

import type { EventType } from "./types";

const PURPLE_BADGE = "text-[#8b5cf6] border-[#8b5cf666] bg-bg";
const PINK_BADGE = "text-[#ff3d7f] border-[#ff3d7f66] bg-bg";
const ORANGE_BADGE = "text-[#ffb37a] border-[#ff9d4d66] bg-bg";
const BLUE_BADGE = "text-[#7fb3ff] border-[#3b7dff66] bg-bg";
const CYAN_BADGE = "text-[#35e0c8] border-[#35e0c84d] bg-bg";
const NEUTRAL_BADGE = "text-[#a89dc4] border-[#4a3d6b] bg-bg";

const BADGE_STYLES: Record<EventType, string> = {
  quiz: PURPLE_BADGE,
  theater: PURPLE_BADGE,
  art: PURPLE_BADGE,
  education: PURPLE_BADGE,
  standup: PINK_BADGE,
  festival: PINK_BADGE,
  party: PINK_BADGE,
  kids: PINK_BADGE,
  exhibition: ORANGE_BADGE,
  karting: ORANGE_BADGE,
  food: ORANGE_BADGE,
  trip: ORANGE_BADGE,
  concert: BLUE_BADGE,
  cinema: BLUE_BADGE,
  science: BLUE_BADGE,
  business: BLUE_BADGE,
  quest: CYAN_BADGE,
  sport: CYAN_BADGE,
  bowling: CYAN_BADGE,
  billiards: CYAN_BADGE,
  hobby: NEUTRAL_BADGE,
  other: NEUTRAL_BADGE,
};

const PURPLE_GRADIENT = "from-[#3a1550] to-[#1b0f2e]";
const PINK_GRADIENT = "from-[#4a0f34] to-[#1b0f2e]";
const ORANGE_GRADIENT = "from-[#5a2e0c] to-[#1b0f2e]";
const BLUE_GRADIENT = "from-[#12305a] to-[#1b0f2e]";
const CYAN_GRADIENT = "from-[#0f4a3f] to-[#1b0f2e]";
const NEUTRAL_GRADIENT = "from-[#2b2440] to-[#1b0f2e]";

const PLACEHOLDER_STYLES: Record<EventType, { gradient: string; emoji: string }> = {
  quiz: { gradient: PURPLE_GRADIENT, emoji: "🧠" },
  theater: { gradient: PURPLE_GRADIENT, emoji: "🎭" },
  art: { gradient: PURPLE_GRADIENT, emoji: "🎨" },
  education: { gradient: PURPLE_GRADIENT, emoji: "🎓" },
  standup: { gradient: PINK_GRADIENT, emoji: "🎤" },
  festival: { gradient: PINK_GRADIENT, emoji: "🎉" },
  party: { gradient: PINK_GRADIENT, emoji: "🎊" },
  kids: { gradient: PINK_GRADIENT, emoji: "🧸" },
  exhibition: { gradient: ORANGE_GRADIENT, emoji: "🖼️" },
  karting: { gradient: ORANGE_GRADIENT, emoji: "🏎️" },
  food: { gradient: ORANGE_GRADIENT, emoji: "🍽️" },
  trip: { gradient: ORANGE_GRADIENT, emoji: "🧳" },
  concert: { gradient: BLUE_GRADIENT, emoji: "🎵" },
  cinema: { gradient: BLUE_GRADIENT, emoji: "🎬" },
  science: { gradient: BLUE_GRADIENT, emoji: "🔬" },
  business: { gradient: BLUE_GRADIENT, emoji: "💼" },
  quest: { gradient: CYAN_GRADIENT, emoji: "🗝️" },
  sport: { gradient: CYAN_GRADIENT, emoji: "⚽" },
  bowling: { gradient: CYAN_GRADIENT, emoji: "🎳" },
  billiards: { gradient: CYAN_GRADIENT, emoji: "🎱" },
  hobby: { gradient: NEUTRAL_GRADIENT, emoji: "🧵" },
  other: { gradient: NEUTRAL_GRADIENT, emoji: "✨" },
};

/** Бейдж типа: цветной текст на тёмной подложке — точки взяты из палитры макета. */
export function eventBadgeStyle(type: EventType): string {
  return BADGE_STYLES[type];
}

/** Плейсхолдер-градиент карточки/hero, когда нет фото. */
export function eventPlaceholder(type: EventType): { gradient: string; emoji: string } {
  return PLACEHOLDER_STYLES[type];
}
