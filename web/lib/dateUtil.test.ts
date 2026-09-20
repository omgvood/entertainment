import { afterEach, describe, it, expect, vi } from "vitest";
import { formatStripDay, formatWeekdayDayMonth, getCityNowMinutes, getCityToday, weekdayUTC } from "./dateUtil";

describe("форматтеры дней", () => {
  it("weekdayUTC: 2026-09-19 — суббота", () => {
    expect(weekdayUTC("2026-09-19")).toBe(6);
    expect(weekdayUTC("2026-09-20")).toBe(0);
  });

  it("formatStripDay — короткий день недели и число", () => {
    expect(formatStripDay("2026-09-21")).toBe("Пн 21");
    expect(formatStripDay("2026-10-03")).toBe("Сб 3");
  });

  it("formatWeekdayDayMonth — день недели, число, месяц", () => {
    expect(formatWeekdayDayMonth("2026-09-19")).toBe("Сб, 19 сентября");
  });
});

describe("getCityToday", () => {
  afterEach(() => vi.useRealTimers());

  it("считает дату в таймзоне города, а не в UTC", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-18T20:00:00Z")); // Пермь UTC+5 → 01:00 19-го, Сочи UTC+3 → 23:00 18-го
    expect(getCityToday("perm")).toBe("2026-09-19");
    expect(getCityToday("sochi")).toBe("2026-09-18");
  });
});

describe("getCityNowMinutes", () => {
  afterEach(() => vi.useRealTimers());

  it("считает минуты от полуночи в таймзоне города, а не зрителя", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-19T10:30:00Z")); // Пермь UTC+5 → 15:30, Сочи UTC+3 → 13:30
    expect(getCityNowMinutes("perm")).toBe(15 * 60 + 30);
    expect(getCityNowMinutes("sochi")).toBe(13 * 60 + 30);
  });

  it("полночь города — 0 минут", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-18T19:00:00Z")); // Пермь UTC+5 → 00:00 19-го
    expect(getCityNowMinutes("perm")).toBe(0);
  });
});
