import { describe, it, expect } from "vitest";
import { applyFilters, DEFAULT_FILTERS } from "./filters";
import type { EventItem } from "./types";

const TODAY = "2026-08-18";

const mk = (over: Partial<EventItem>): EventItem => ({
  id: "perm-x",
  city: "perm",
  slug: "x",
  title: "Событие",
  type: "concert",
  date: "2026-08-20",
  priceMin: 0,
  priceMax: 0,
  priceText: "по билетам",
  address: "адрес",
  venueName: "площадка",
  tags: [],
  sourceUrl: "https://example.com",
  source: "test",
  parsedAt: "2026-08-18T00:00:00Z",
  ...over,
});

describe("applyFilters — цена", () => {
  const narrow = { ...DEFAULT_FILTERS, priceMin: 500, priceMax: 5000 };

  it("показывает событие с неизвестной ценой даже при нижней границе", () => {
    const unknown = mk({ priceText: "по билетам" });
    expect(applyFilters([unknown], narrow, TODAY)).toHaveLength(1);
  });

  it("прячет бесплатное событие при нижней границе", () => {
    const free = mk({ priceText: "Бесплатно" });
    expect(applyFilters([free], narrow, TODAY)).toHaveLength(0);
  });

  it("оставляет обычную фильтрацию для событий с известной ценой", () => {
    const cheap = mk({ priceMin: 100, priceMax: 200, priceText: "200 ₽" });
    expect(applyFilters([cheap], narrow, TODAY)).toHaveLength(0);
    expect(applyFilters([cheap], DEFAULT_FILTERS, TODAY)).toHaveLength(1);
  });
});
