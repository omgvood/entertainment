/**
 * SEO-хелперы страниц событий (Пермь и Сочи): canonical и JSON-LD `Event`.
 * Образец — `venue-meta.ts`.
 */

import { CITY_CONFIG } from "./types";
import type { EventItem } from "./types";
import { SITE_URL } from "./venue-meta";
import { cityUtcOffset } from "./dateUtil";
import { priceKind } from "./price";
import { isUsableImage } from "./venue-styles";

/** Абсолютный URL страницы события. */
export function eventUrl(event: Pick<EventItem, "city" | "slug">): string {
  return `${SITE_URL}/${event.city}/events/${event.slug}`;
}

/** JSON-LD `Event`; у событий без даты («always») startDate нет — разметки тоже. */
export function eventJsonLd(event: EventItem): Record<string, unknown> | null {
  if (event.date === "always") return null;

  const offset = cityUtcOffset(event.city);
  const at = (time: string) => `${event.date}T${time}:00${offset}`;

  const ld: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "Event",
    name: event.title,
    url: eventUrl(event),
    startDate: event.timeStart ? at(event.timeStart) : event.date,
    location: {
      "@type": "Place",
      name: event.venueName,
      address: {
        "@type": "PostalAddress",
        streetAddress: event.address,
        addressLocality: CITY_CONFIG[event.city].label,
      },
    },
  };
  if (event.timeStart && event.timeEnd) ld.endDate = at(event.timeEnd);
  if (isUsableImage(event.imageUrl)) ld.image = event.imageUrl;

  const kind = priceKind(event);
  if (kind !== "unknown") {
    ld.offers = {
      "@type": "Offer",
      price: kind === "free" ? 0 : event.priceMin,
      priceCurrency: "RUB",
      url: event.sourceUrl,
    };
  }
  return ld;
}

/** JSON для `<script type="application/ld+json">`: `<` экранирован, чтобы текст из источника не закрыл тег. */
export function jsonLdScript(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
