import Image from "next/image";
import Link from "next/link";
import type { EventItem, EventType } from "@/lib/types";
import { EVENT_TYPE_LABELS } from "@/lib/types";

const BADGE_STYLES: Record<EventType, string> = {
  quiz: "bg-[#ede7ff] text-[#5a3eee]",
  standup: "bg-[#ffe7ee] text-[#d63672]",
  bowling: "bg-[#e7f5ff] text-[#1971c2]",
  billiards: "bg-[#e7f9ec] text-[#2b8a3e]",
  karting: "bg-[#fff4e0] text-[#d97706]",
  concert: "bg-[#e7ecff] text-[#3b5bdb]",
  theater: "bg-[#f3e8ff] text-[#7e22ce]",
  exhibition: "bg-[#fff0e7] text-[#c2410c]",
  festival: "bg-[#ffe9f0] text-[#db2777]",
  quest: "bg-[#e7fbf5] text-[#0d9488]",
  party: "bg-[#fef9c3] text-[#a16207]",
  cinema: "bg-[#e7eefc] text-[#2b4ec2]",
  sport: "bg-[#e7f9ec] text-[#157f3c]",
  education: "bg-[#eef2ff] text-[#4f46e5]",
  business: "bg-[#eef0f3] text-[#334155]",
  art: "bg-[#fdeef7] text-[#a21caf]",
  kids: "bg-[#fff1e7] text-[#ea580c]",
  food: "bg-[#fef3e2] text-[#b45309]",
  trip: "bg-[#e7f7f4] text-[#0f766e]",
  hobby: "bg-[#f3f0ff] text-[#6d28d9]",
  science: "bg-[#e9f2ff] text-[#1d4ed8]",
  other: "bg-[#eef0f3] text-[#475569]",
};

const PLACEHOLDER_STYLES: Record<EventType, { gradient: string; emoji: string }> = {
  quiz:      { gradient: "from-[#ede7ff] to-[#c8b6ff]", emoji: "🧠" },
  standup:   { gradient: "from-[#ffe7ee] to-[#ffb3c1]", emoji: "🎤" },
  bowling:   { gradient: "from-[#e7f5ff] to-[#a5d8ff]", emoji: "🎳" },
  billiards: { gradient: "from-[#e7f9ec] to-[#b2f2bb]", emoji: "🎱" },
  karting:   { gradient: "from-[#fff4e0] to-[#ffd8a8]", emoji: "🏎️" },
  concert:    { gradient: "from-[#e7ecff] to-[#b3c5ff]", emoji: "🎵" },
  theater:    { gradient: "from-[#f3e8ff] to-[#d8b4fe]", emoji: "🎭" },
  exhibition: { gradient: "from-[#fff0e7] to-[#ffc9a8]", emoji: "🖼️" },
  festival:   { gradient: "from-[#ffe9f0] to-[#fbb6ce]", emoji: "🎉" },
  quest:      { gradient: "from-[#e7fbf5] to-[#99f6e4]", emoji: "🗝️" },
  party:      { gradient: "from-[#fef9c3] to-[#fde68a]", emoji: "🎊" },
  cinema:     { gradient: "from-[#e7eefc] to-[#a9c2f5]", emoji: "🎬" },
  sport:      { gradient: "from-[#e7f9ec] to-[#a7e9bd]", emoji: "⚽" },
  education:  { gradient: "from-[#eef2ff] to-[#c7d2fe]", emoji: "🎓" },
  business:   { gradient: "from-[#eef0f3] to-[#cbd5e1]", emoji: "💼" },
  art:        { gradient: "from-[#fdeef7] to-[#f5c2e7]", emoji: "🎨" },
  kids:       { gradient: "from-[#fff1e7] to-[#ffd2b0]", emoji: "🧸" },
  food:       { gradient: "from-[#fef3e2] to-[#fcd9a3]", emoji: "🍽️" },
  trip:       { gradient: "from-[#e7f7f4] to-[#a3e6db]", emoji: "🧳" },
  hobby:      { gradient: "from-[#f3f0ff] to-[#d6c8fb]", emoji: "🧵" },
  science:    { gradient: "from-[#e9f2ff] to-[#b6d2fb]", emoji: "🔬" },
  other:      { gradient: "from-[#eef0f3] to-[#cbd5e1]", emoji: "✨" },
};

function isUsableImage(url?: string): boolean {
  if (!url) return false;
  // svg-иконки (rating/difficulty/markers) — не годятся как карточка 400×300
  if (url.toLowerCase().endsWith(".svg")) return false;
  return true;
}

const MONTHS_RU = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

function formatDate(event: EventItem): string {
  if (event.date === "always") return "ежедневно";
  const [, m, d] = event.date.split("-").map(Number);
  const day = `${d} ${MONTHS_RU[m - 1]}`;
  return event.timeStart ? `${day}, ${event.timeStart}` : day;
}

export function EventCard({ event }: { event: EventItem }) {
  return (
    <Link
      href={`/${event.city}/events/${event.slug}/`}
      className="group bg-surface border border-border rounded-xl overflow-hidden shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-150 flex flex-col"
    >
      <div className="relative aspect-[4/3] bg-[#ddd]">
        {isUsableImage(event.imageUrl) ? (
          <Image
            src={event.imageUrl!}
            alt={`${event.title} — ${EVENT_TYPE_LABELS[event.type]} в ${event.venueName}`}
            fill
            sizes="(min-width: 1200px) 25vw, (min-width: 768px) 33vw, 50vw"
            className="object-cover"
            unoptimized
          />
        ) : (
          <div
            className={`absolute inset-0 bg-gradient-to-br ${PLACEHOLDER_STYLES[event.type].gradient} flex items-center justify-center text-6xl`}
            aria-hidden
          >
            {PLACEHOLDER_STYLES[event.type].emoji}
          </div>
        )}
      </div>

      <div className="p-3 pb-4 flex flex-col gap-2 flex-1">
        <span
          className={`inline-block self-start text-[11px] font-semibold px-2 py-[3px] rounded-full uppercase tracking-wider ${BADGE_STYLES[event.type]}`}
        >
          {EVENT_TYPE_LABELS[event.type]}
        </span>

        <h2 className="text-[15px] font-semibold leading-tight line-clamp-2">
          {event.title}
        </h2>

        <div className="flex flex-col gap-1 text-[13px] text-muted mt-auto">
          <span>📅 {formatDate(event)}</span>
          <span>
            💰 {event.priceText}
            {event.priceNote && (
              <small className="ml-1 text-[11px] opacity-85">
                {event.priceNote}
              </small>
            )}
          </span>
          <span>📍 {event.address}</span>
        </div>
      </div>
    </Link>
  );
}
