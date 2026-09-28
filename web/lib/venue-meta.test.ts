import { describe, it, expect } from "vitest";
import { venueUrl, venueJsonLd } from "./venue-meta";
import { CITY_CONFIG } from "./types";
import type { VenueItem } from "./types";

// Сайт отдаёт URL без слэша на конце; ссылка со слэшем проходит через редирект.
const venue: VenueItem = {
  id: "perm-kosmik",
  city: "perm",
  slug: "kosmik",
  name: "Космик",
  type: "bowling",
  updatedAt: "2026-09-29T00:00:00Z",
};

describe("форма URL без слэша на конце", () => {
  it("venueUrl", () => {
    expect(venueUrl(venue)).toMatch(/\/perm\/venues\/kosmik$/);
  });

  it("хлебные крошки venueJsonLd", () => {
    const breadcrumbs = venueJsonLd(venue, "perm").find(
      (o) => (o as { "@type": string })["@type"] === "BreadcrumbList",
    ) as { itemListElement: { item?: string }[] };
    const items = breadcrumbs.itemListElement.map((e) => e.item).filter(Boolean);
    expect(items.length).toBeGreaterThan(0);
    for (const url of items) expect(url).not.toMatch(/\/$/);
  });

  it.each(Object.entries(CITY_CONFIG))("CITY_CONFIG.%s.path", (city, cfg) => {
    expect(cfg.path).toBe(`/${city}`);
  });
});
