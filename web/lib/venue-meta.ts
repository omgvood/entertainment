/**
 * Общие SEO-хелперы для страниц площадок (используются и Пермью, и Сочи).
 * Держим metadata + JSON-LD в одном месте, чтобы perm/sochi не дублировали логику.
 */

import type { Metadata } from "next";
import { CITY_CONFIG, getVenueTypeLabel } from "./types";
import type { City, VenueItem } from "./types";

export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://afisha-site.ru";

/** Род. падеж города («Афиша Перми», «в Перми»). Сочи не склоняется. */
const CITY_GENITIVE: Record<City, string> = {
  perm: "Перми",
  sochi: "Сочи",
};

export function cityGenitive(city: City): string {
  return CITY_GENITIVE[city];
}

/** Schema.org-тип под конкретную площадку — Google любит конкретику. */
function schemaType(type: string): string {
  if (type === "bowling" || type === "karting" || type === "billiards") {
    return "SportsActivityLocation";
  }
  if (type === "quest") return "EntertainmentBusiness";
  return "LocalBusiness";
}

/** Абсолютный URL страницы площадки. */
export function venueUrl(venue: VenueItem): string {
  return `${SITE_URL}/${venue.city}/venues/${venue.slug}/`;
}

export function buildVenueMetadata(venue: VenueItem, city: City): Metadata {
  const typeLabel = getVenueTypeLabel(venue.type);
  const inCity = cityGenitive(city);
  const title = `${typeLabel} «${venue.name}» в ${inCity} — адрес, фото и карта`;
  const description = `${venue.name}, ${CITY_CONFIG[city].label}${
    venue.address ? `, ${venue.address}` : ""
  }. Адрес, район, расположение на карте.`;

  return {
    title,
    description,
    alternates: { canonical: venueUrl(venue) },
    openGraph: {
      title,
      description,
      images: venue.imageUrl ? [venue.imageUrl] : undefined,
    },
  };
}

/** JSON-LD: место (LocalBusiness/...) + хлебные крошки. */
export function venueJsonLd(venue: VenueItem, city: City): object[] {
  const place: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": schemaType(venue.type),
    name: venue.name,
    url: venueUrl(venue),
    areaServed: CITY_CONFIG[city].label,
  };
  if (venue.imageUrl) place.image = venue.imageUrl;
  if (venue.address) {
    place.address = {
      "@type": "PostalAddress",
      streetAddress: venue.address,
      addressLocality: CITY_CONFIG[city].label,
    };
  }
  place.dateModified = venue.updatedAt;

  const breadcrumbs = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: `Афиша ${cityGenitive(city)}`,
        item: `${SITE_URL}/${city}/`,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Площадки",
        item: `${SITE_URL}/${city}/venues/`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: venue.name,
      },
    ],
  };

  return [place, breadcrumbs];
}
