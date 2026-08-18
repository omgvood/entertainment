import Link from "next/link";
import type { EventItem } from "@/lib/types";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import { eventBadgeStyle, eventPlaceholder } from "@/lib/event-styles";
import { CardImage } from "./CardImage";

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
  const placeholder = eventPlaceholder(event.type);

  return (
    <Link
      href={`/${event.city}/events/${event.slug}/`}
      className="group bg-surface border border-border rounded-2xl overflow-hidden hover:border-[color:var(--color-border-hi,#4a3d6b)] hover:shadow-[0_22px_44px_-22px_rgba(255,61,127,0.35)] hover:-translate-y-0.5 transition-all duration-150 flex flex-col"
    >
      <div className="relative aspect-video bg-bg">
        <CardImage
          imageUrl={event.imageUrl}
          alt={`${event.title} — ${EVENT_TYPE_LABELS[event.type]} в ${event.venueName}`}
          placeholder={placeholder}
        />
      </div>

      <div className="p-4 pb-[18px] flex flex-col gap-[9px] flex-1">
        <span
          className={`inline-block self-start text-[10.5px] font-bold px-[10px] py-1 rounded-full uppercase tracking-wider border ${eventBadgeStyle(event.type)}`}
        >
          {EVENT_TYPE_LABELS[event.type]}
        </span>

        <h2 className="text-[16px] font-bold leading-tight line-clamp-2">
          {event.title}
        </h2>

        <div className="flex flex-col gap-1 text-[12.5px] text-muted mt-auto">
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
