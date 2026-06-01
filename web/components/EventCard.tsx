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
};

const PLACEHOLDER_STYLES: Record<EventType, { gradient: string; emoji: string }> = {
  quiz:      { gradient: "from-[#ede7ff] to-[#c8b6ff]", emoji: "🧠" },
  standup:   { gradient: "from-[#ffe7ee] to-[#ffb3c1]", emoji: "🎤" },
  bowling:   { gradient: "from-[#e7f5ff] to-[#a5d8ff]", emoji: "🎳" },
  billiards: { gradient: "from-[#e7f9ec] to-[#b2f2bb]", emoji: "🎱" },
  karting:   { gradient: "from-[#fff4e0] to-[#ffd8a8]", emoji: "🏎️" },
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
