import Link from "next/link";
import type { EventItem } from "@/lib/types";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import { eventBadgeStyle, eventPlaceholder } from "@/lib/event-styles";
import { CardImage } from "./CardImage";
import { formatDayMonth } from "@/lib/dateUtil";
import { priceBadge } from "@/lib/price";
import { eventTimeStatus } from "@/lib/eventTiming";

function formatDate(event: EventItem): string {
  if (event.date === "always") return "ежедневно";
  const day = formatDayMonth(event.date);
  return event.timeStart ? `${day}, ${event.timeStart}` : day;
}

/** Первая строка карточки — решение тикета 06: относительная метка для сегодняшних событий. */
function timeLine(event: EventItem, today: string, nowMinutes: number): string {
  const status = eventTimeStatus(event, today, nowMinutes);
  if (status.kind === "live") return "Идёт сейчас";
  if (status.kind === "started") return status.label;
  if (status.kind === "upcoming") return `${formatDate(event)} · ${status.label}`;
  return formatDate(event);
}

interface EventCardProps {
  event: EventItem;
  /** Серия: сколько ещё дат и до какой — из lib/series.otherDates. */
  moreDates?: { count: number; lastDate: string } | null;
  /** «Сегодня» и минуты от полуночи в таймзоне города — для timeLine (тикет 06). */
  today: string;
  nowMinutes: number;
}

function pluralDates(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return "дат";
  if (mod10 === 1) return "дата";
  if (mod10 >= 2 && mod10 <= 4) return "даты";
  return "дат";
}

export function EventCard({ event, moreDates, today, nowMinutes }: EventCardProps) {
  const placeholder = eventPlaceholder(event.type);
  const badge = priceBadge(event);

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
          priceLabel={badge ?? event.priceText}
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

        <p className="text-[13px] text-muted font-semibold">{event.venueName}</p>

        {event.description && (
          <p className="line-clamp-2 text-[12.5px] text-muted/80 leading-relaxed">
            {event.description}
          </p>
        )}

        {event.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {event.tags.slice(0, 2).map((tag) => (
              <span
                key={tag}
                className="text-[10.5px] text-muted bg-bg border border-border px-[9px] py-[3px] rounded-full"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-1 text-[12.5px] text-muted mt-auto">
          <span>
            📅 {timeLine(event, today, nowMinutes)}
            {moreDates && (
              <small className="ml-1 text-[11px] text-accent-cyan">
                · ещё {moreDates.count} {pluralDates(moreDates.count)} до {formatDayMonth(moreDates.lastDate)}
              </small>
            )}
          </span>
          <span>
            💰 {badge ?? event.priceText}
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
