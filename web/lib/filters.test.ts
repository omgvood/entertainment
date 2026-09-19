import { describe, it, expect } from "vitest";
import { DEFAULT_FILTERS, inDateSel, matchesEvent, visibleSeries } from "./filters";
import { groupSeries } from "./series";
import type { EventItem, EventType } from "./types";

const mk = (over: Partial<EventItem>): EventItem => ({
  id: `perm-${over.slug ?? "x"}`,
  city: "perm",
  slug: "x",
  title: "Событие",
  type: "concert",
  date: "2026-09-20",
  priceMin: 0,
  priceMax: 0,
  priceText: "по билетам",
  address: "адрес",
  venueName: "площадка",
  tags: [],
  sourceUrl: "https://example.com",
  source: "test",
  parsedAt: "2026-09-19T00:00:00Z",
  ...over,
});

describe("matchesEvent — тип", () => {
  it("пустой набор типов пропускает всё", () => {
    expect(matchesEvent(mk({ type: "theater" }), DEFAULT_FILTERS)).toBe(true);
  });

  it("выбранный тип оставляет только его (регрессия: клик по чипу убирал тип)", () => {
    const onlyConcerts = { ...DEFAULT_FILTERS, types: new Set<EventType>(["concert"]) };
    expect(matchesEvent(mk({ type: "concert" }), onlyConcerts)).toBe(true);
    expect(matchesEvent(mk({ type: "theater" }), onlyConcerts)).toBe(false);
  });
});

describe("matchesEvent — цена", () => {
  const narrow = { ...DEFAULT_FILTERS, priceMin: 500, priceMax: 5000 };

  it("показывает событие с неизвестной ценой даже при нижней границе", () => {
    expect(matchesEvent(mk({ priceText: "по билетам" }), narrow)).toBe(true);
  });

  it("прячет бесплатное событие при нижней границе", () => {
    expect(matchesEvent(mk({ priceText: "Бесплатно" }), narrow)).toBe(false);
  });

  it("оставляет обычную фильтрацию для событий с известной ценой", () => {
    const cheap = mk({ priceMin: 100, priceMax: 200, priceText: "200 ₽" });
    expect(matchesEvent(cheap, narrow)).toBe(false);
    expect(matchesEvent(cheap, DEFAULT_FILTERS)).toBe(true);
  });

  it("по умолчанию верхней границы нет (раньше молча прятало всё дороже 5000 ₽)", () => {
    const pricey = mk({ priceMin: 7000, priceMax: 12000, priceText: "от 7000 ₽" });
    expect(matchesEvent(pricey, DEFAULT_FILTERS)).toBe(true);
  });
});

describe("inDateSel", () => {
  const TUE = "2026-09-15";
  const SAT = "2026-09-19";
  const SUN = "2026-09-20";

  it("today / tomorrow / конкретный день / all", () => {
    expect(inDateSel(TUE, "today", TUE)).toBe(true);
    expect(inDateSel("2026-09-16", "tomorrow", TUE)).toBe(true);
    expect(inDateSel("2026-09-16", "today", TUE)).toBe(false);
    expect(inDateSel("2026-09-22", "2026-09-22", TUE)).toBe(true);
    expect(inDateSel("2026-10-30", "all", TUE)).toBe(true);
  });

  it("во вторник выходные — ближайшие суббота и воскресенье", () => {
    expect(inDateSel("2026-09-19", "weekend", TUE)).toBe(true);
    expect(inDateSel("2026-09-20", "weekend", TUE)).toBe(true);
    expect(inDateSel(TUE, "weekend", TUE)).toBe(false);
    expect(inDateSel("2026-09-21", "weekend", TUE)).toBe(false);
  });

  it("в субботу выходные — сегодня и завтра", () => {
    expect(inDateSel(SAT, "weekend", SAT)).toBe(true);
    expect(inDateSel(SUN, "weekend", SAT)).toBe(true);
  });

  it("в воскресенье выходные — только сегодня, не следующая суббота", () => {
    expect(inDateSel(SUN, "weekend", SUN)).toBe(true);
    expect(inDateSel("2026-09-26", "weekend", SUN)).toBe(false);
  });
});

describe("visibleSeries", () => {
  const series = groupSeries([
    mk({ slug: "sun-free", date: "2026-09-20", priceText: "Бесплатно" }),
    mk({ slug: "mon-paid", date: "2026-09-21", priceMin: 1000, priceMax: 1000, priceText: "1000 ₽" }),
  ]);

  it("показывает первый сеанс в окне дат", () => {
    const [view] = visibleSeries(series, DEFAULT_FILTERS, "all", "2026-09-19");
    expect(view.shown.slug).toBe("sun-free");
  });

  it("показывает сеанс, прошедший фильтр цены, а не просто первый по дате", () => {
    const paid = { ...DEFAULT_FILTERS, priceMin: 500 };
    const views = visibleSeries(series, paid, "all", "2026-09-19");
    expect(views.map((v) => v.shown.slug)).toEqual(["mon-paid"]);
  });

  it("серия не видна, если ни один сеанс не попал в окно и фильтры", () => {
    const paid = { ...DEFAULT_FILTERS, priceMin: 500 };
    expect(visibleSeries(series, paid, "2026-09-20", "2026-09-19")).toEqual([]);
  });
});
