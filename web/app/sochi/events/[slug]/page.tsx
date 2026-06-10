import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { getEventBySlug, getEventsByCity } from "@/lib/events";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import type { EventItem, EventType } from "@/lib/types";

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
  if (url.toLowerCase().endsWith(".svg")) return false;
  return true;
}

const MONTHS_RU = [
  "января","февраля","марта","апреля","мая","июня",
  "июля","августа","сентября","октября","ноября","декабря",
];

function formatDate(event: EventItem): string {
  if (event.date === "always") return "Доступно ежедневно";
  const [, m, d] = event.date.split("-").map(Number);
  const day = `${d} ${MONTHS_RU[m - 1]}`;
  if (event.timeStart && event.timeEnd)
    return `${day}, ${event.timeStart}–${event.timeEnd}`;
  if (event.timeStart) return `${day}, ${event.timeStart}`;
  return day;
}

export async function generateStaticParams() {
  const events = await getEventsByCity("sochi");
  return events.map((e) => ({ slug: e.slug }));
}

type SlugParams = { params: Promise<{ slug: string }> };

export async function generateMetadata(
  { params }: SlugParams,
): Promise<Metadata> {
  const { slug } = await params;
  const event = await getEventBySlug("sochi", slug);
  if (!event) return { title: "Событие не найдено" };

  const title =
    event.metaTitle ?? `${event.title} — Афиша Сочи`;
  const description =
    event.metaDescription ??
    `${EVENT_TYPE_LABELS[event.type]} в Сочи. ${event.priceText}. ${event.address}.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: event.imageUrl ? [event.imageUrl] : undefined,
    },
  };
}

export default async function EventPage(
  { params }: SlugParams,
) {
  const { slug } = await params;
  const event = await getEventBySlug("sochi", slug);
  if (!event) notFound();

  return (
    <>
      <Header city="sochi" />
      <article className="mx-auto max-w-3xl px-4 pt-6 pb-12 flex-1 w-full">
        <Link
          href="/sochi"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent mb-4"
        >
          ← Все события
        </Link>

        <div className="relative aspect-[16/9] bg-[#ddd] rounded-xl overflow-hidden mb-5">
          {isUsableImage(event.imageUrl) ? (
            <Image
              src={event.imageUrl!}
              alt={`${event.title} — ${EVENT_TYPE_LABELS[event.type]} в ${event.venueName}`}
              fill
              sizes="(min-width: 1024px) 768px, 100vw"
              className="object-cover"
              unoptimized
              priority
            />
          ) : (
            <div
              className={`absolute inset-0 bg-gradient-to-br ${PLACEHOLDER_STYLES[event.type].gradient} flex items-center justify-center text-9xl`}
              aria-hidden
            >
              {PLACEHOLDER_STYLES[event.type].emoji}
            </div>
          )}
        </div>

        <span
          className={`inline-block text-[11px] font-semibold px-2 py-[3px] rounded-full uppercase tracking-wider mb-3 ${BADGE_STYLES[event.type]}`}
        >
          {EVENT_TYPE_LABELS[event.type]}
        </span>

        <h1 className="text-2xl sm:text-3xl font-bold leading-tight mb-4">
          {event.title}
        </h1>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[15px] mb-6">
          <dt className="text-muted">Когда:</dt>
          <dd>{formatDate(event)}</dd>

          <dt className="text-muted">Цена:</dt>
          <dd>
            {event.priceText}
            {event.priceNote && (
              <span className="ml-1 text-[13px] text-muted">
                ({event.priceNote})
              </span>
            )}
          </dd>

          <dt className="text-muted">Где:</dt>
          <dd>
            <div>{event.venueName}</div>
            <div className="text-muted text-[14px]">{event.address}</div>
          </dd>

          {event.organizer && (
            <>
              <dt className="text-muted">Организатор:</dt>
              <dd>{event.organizer}</dd>
            </>
          )}
        </dl>

        {event.description && (
          <p className="text-[15px] leading-relaxed mb-6">{event.description}</p>
        )}

        <a
          href={event.sourceUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-5 py-3 bg-accent text-white rounded-lg font-medium hover:bg-accent-hover transition-colors"
        >
          Перейти к источнику →
        </a>
      </article>

      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша · 2026
      </footer>
    </>
  );
}
