import type { MetadataRoute } from "next";
import { getEventsByCity } from "@/lib/events";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://afisha-site.ru";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [permEvents, sochiEvents] = await Promise.all([
    getEventsByCity("perm"),
    getEventsByCity("sochi"),
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

  return [...cityPages, ...permEventPages, ...sochiEventPages];
}
