import { describe, it, expect } from "vitest";
import { buildDateStrip, firstNonEmptyDay } from "./dateStrip";
import type { DateSel } from "./filters";

const TODAY = "2026-09-19"; // суббота

describe("buildDateStrip", () => {
  const strip = buildDateStrip(TODAY);

  it("Сегодня, Завтра, Выходные, 12 отдельных дней, Все даты", () => {
    expect(strip).toHaveLength(16);
    expect(strip.slice(0, 3).map((i) => i.sel)).toEqual(["today", "tomorrow", "weekend"]);
    expect(strip[3]).toEqual({ sel: "2026-09-21", label: "Пн 21" });
    expect(strip[14].sel).toBe("2026-10-02");
    expect(strip[15]).toEqual({ sel: "all", label: "Все даты" });
  });
});

describe("firstNonEmptyDay", () => {
  const strip = buildDateStrip(TODAY);
  const counts = (entries: [DateSel, number][]) => new Map<DateSel, number>(entries);

  it("сегодня непусто — сегодня", () => {
    expect(firstNonEmptyDay(strip, counts([["today", 3]]))).toBe("today");
  });

  it("пропускает «Выходные» и «Все даты» — ищет отдельный день", () => {
    const c = counts([["today", 0], ["tomorrow", 0], ["weekend", 5], ["2026-09-22", 2], ["all", 7]]);
    expect(firstNonEmptyDay(strip, c)).toBe("2026-09-22");
  });

  it("пусто везде — null", () => {
    expect(firstNonEmptyDay(strip, counts([["all", 4]]))).toBeNull();
  });
});
