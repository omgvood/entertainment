import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { getEventBySlug, getEventsByCity, getCityToday } from "@/lib/events";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import type { EventItem } from "@/lib/types";
import { eventBadgeStyle, eventPlaceholder } from "@/lib/event-styles";

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
  const events = await getEventsByCity("perm", getCityToday("perm"));
  return events.map((e) => ({ slug: e.slug }));
}

export async function generateMetadata(
  { params }: PageProps<"/perm/events/[slug]">,
): Promise<Metadata> {
  const { slug } = await params;
  const event = await getEventBySlug("perm", slug);
  if (!event) return { title: "Событие не найдено" };

  const title =
    event.metaTitle ?? `${event.title} — Афиша Пермь`;
  const description =
    event.metaDescription ??
    `${EVENT_TYPE_LABELS[event.type]} в Перми. ${event.priceText}. ${event.address}.`;

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
  { params }: PageProps<"/perm/events/[slug]">,
) {
  const { slug } = await params;
  const event = await getEventBySlug("perm", slug);
  if (!event) notFound();

  const placeholder = eventPlaceholder(event.type);

  return (
    <>
      <Header />
      <article className="mx-auto max-w-2xl px-4 pt-6 pb-12 flex-1 w-full">
        <Link
          href="/perm"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent mb-4"
        >
          ← Все события
        </Link>

        <div className="relative aspect-[21/9] bg-bg rounded-[20px] overflow-hidden mb-5">
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
              className={`absolute inset-0 bg-gradient-to-br ${placeholder.gradient} flex items-center justify-center text-9xl`}
              aria-hidden
            >
              {placeholder.emoji}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 mb-3">
          <span
            className={`inline-block text-[10.5px] font-bold px-[10px] py-1 rounded-full uppercase tracking-wider border ${eventBadgeStyle(event.type)}`}
          >
            {EVENT_TYPE_LABELS[event.type]}
          </span>
        </div>

        <h1 className="text-2xl sm:text-[28px] font-extrabold leading-tight mb-4">
          {event.title}
        </h1>

        <p className="text-[14px] font-semibold text-muted mb-4">{event.venueName}</p>

        {event.description && (
          <p className="text-[13.5px] text-muted leading-relaxed mb-5">{event.description}</p>
        )}

        <div className="flex items-start gap-[10px] p-[13px_14px] bg-bg border border-border rounded-xl text-[13px] text-muted mb-5">
          <span aria-hidden>📍</span>
          <span>{event.venueName}, {event.address}</span>
        </div>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[15px] mb-6">
          <dt className="text-muted">Когда:</dt>
          <dd>{formatDate(event)}</dd>

          {event.organizer && (
            <>
              <dt className="text-muted">Организатор:</dt>
              <dd>{event.organizer}</dd>
            </>
          )}
        </dl>

        <div className="flex items-center justify-between gap-3 flex-wrap pt-[14px] border-t border-border">
          <span className="text-lg font-extrabold">
            {event.priceText}
            {event.priceNote && (
              <span className="ml-1 text-[13px] text-muted font-medium">
                ({event.priceNote})
              </span>
            )}
          </span>
          <a
            href={event.sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-[22px] py-[11px] bg-accent text-bg rounded-[10px] font-bold text-[13.5px] hover:bg-accent-hover transition-colors"
          >
            Перейти к источнику →
          </a>
        </div>
      </article>

      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша Пермь · 2026
      </footer>
    </>
  );
}
