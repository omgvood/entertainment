import type { MetadataRoute } from "next";
import { getEventsByCity } from "@/lib/events";
import { getVenuesByCity } from "@/lib/venues";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://afisha-site.ru";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [permEvents, sochiEvents, permVenues, sochiVenues] = await Promise.all([
    getEventsByCity("perm"),
    getEventsByCity("sochi"),
    getVenuesByCity("perm"),
    getVenuesByCity("sochi"),
  ]);

  const cityPages: MetadataRoute.Sitemap = [
    {
      url: `${SITE_URL}/perm/`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1,
    },
    {
      url: `${SITE_URL}/sochi/`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1,
    },
  ];

  const venueCatalogPages: MetadataRoute.Sitemap = [
    {
      url: `${SITE_URL}/perm/venues/`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${SITE_URL}/sochi/venues/`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.7,
    },
  ];

  const venuePages: MetadataRoute.Sitemap = [
    ...permVenues.map((v) => ({
      url: `${SITE_URL}/perm/venues/${v.slug}/`,
      lastModified: new Date(v.updatedAt),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
    ...sochiVenues.map((v) => ({
      url: `${SITE_URL}/sochi/venues/${v.slug}/`,
      lastModified: new Date(v.updatedAt),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
  ];

  const permEventPages: MetadataRoute.Sitemap = permEvents.map((e) => ({
    url: `${SITE_URL}/perm/events/${e.slug}/`,
    lastModified: new Date(e.parsedAt),
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  const sochiEventPages: MetadataRoute.Sitemap = sochiEvents.map((e) => ({
    url: `${SITE_URL}/sochi/events/${e.slug}/`,
    lastModified: new Date(e.parsedAt),
    changeFrequency: "weekly" as const,
    priority: 0.7,
  }));

  return [
    ...cityPages,
    ...venueCatalogPages,
    ...permEventPages,
    ...sochiEventPages,
    ...venuePages,
  ];
}
