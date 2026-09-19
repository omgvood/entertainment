import { describe, it, expect } from "vitest";
import { compareByDateTime, groupByDate, groupSeries, otherDates, seriesKey } from "./series";
import type { EventItem } from "./types";

const mk = (over: Partial<EventItem>): EventItem => ({
  id: `perm-${over.slug ?? "x"}`,
  city: "perm",
  slug: "x",
  title: "Событие",
  type: "exhibition",
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

describe("seriesKey", () => {
  it("игнорирует кавычки и возрастную метку", () => {
    const a = mk({ title: "«Изба сказок» (6+)", venueName: "музей «Хохловка»" });
    const b = mk({ title: "Изба сказок", venueName: "музей Хохловка" });
    expect(seriesKey(a)).toBe(seriesKey(b));
  });

  it("возрастная метка без скобок в конце названия", () => {
    expect(seriesKey(mk({ title: "Лекция «Травознай и древовед» 12+" }))).toBe(
      seriesKey(mk({ title: "Лекция Травознай и древовед" })),
    );
  });

  it("ё и регистр не важны", () => {
    expect(seriesKey(mk({ title: "Ёлка" }))).toBe(seriesKey(mk({ title: "елка" })));
  });

  it("разные площадки — разные серии, даже при одном названии", () => {
    const a = mk({ title: "Пермская деревянная скульптура", venueName: "Пермская галерея" });
    const b = mk({ title: "Пермская деревянная скульптура", venueName: "Пермская художественная галерея" });
    expect(seriesKey(a)).not.toBe(seriesKey(b));
  });

  it("число в названии без плюса не считается возрастной меткой", () => {
    expect(seriesKey(mk({ title: "Лекция 2" }))).not.toBe(seriesKey(mk({ title: "Лекция" })));
  });
});

describe("compareByDateTime", () => {
  it("сначала дата, потом время; без времени — в конец дня", () => {
    const list = [
      mk({ slug: "c", date: "2026-09-21", timeStart: "10:00" }),
      mk({ slug: "b", date: "2026-09-20" }),
      mk({ slug: "a", date: "2026-09-20", timeStart: "18:00" }),
    ].sort(compareByDateTime);
    expect(list.map((e) => e.slug)).toEqual(["a", "b", "c"]);
  });
});

describe("groupSeries", () => {
  it("собирает повторы в одну серию и сортирует её даты", () => {
    const t = "Пермская деревянная скульптура";
    const v = "Пермская галерея";
    const series = groupSeries([
      mk({ slug: "s22", title: t, venueName: v, date: "2026-09-22" }),
      mk({ slug: "circus", title: "Цирк «Империя мастеров» в Перми!", date: "2026-09-20" }),
      mk({ slug: "s20", title: t, venueName: v, date: "2026-09-20" }),
      mk({ slug: "s21", title: t, venueName: v, date: "2026-09-21" }),
    ]);
    expect(series).toHaveLength(2);
    expect(series[0].events.map((e) => e.slug)).toEqual(["s20", "s21", "s22"]);
    expect(series[1].events.map((e) => e.slug)).toEqual(["circus"]);
  });
});

describe("otherDates", () => {
  it("считает различные даты, кроме показанной; сеансы одного дня — одна дата", () => {
    const [s] = groupSeries([
      mk({ slug: "d1-12", date: "2026-09-20", timeStart: "12:00" }),
      mk({ slug: "d1-15", date: "2026-09-20", timeStart: "15:00" }),
      mk({ slug: "d2", date: "2026-09-27", timeStart: "12:00" }),
    ]);
    expect(otherDates(s, s.events[0])).toEqual({ count: 1, lastDate: "2026-09-27" });
  });

  it("null, если других дат нет (даже при нескольких сеансах)", () => {
    const [s] = groupSeries([
      mk({ slug: "a", timeStart: "12:00" }),
      mk({ slug: "b", timeStart: "15:00" }),
    ]);
    expect(otherDates(s, s.events[0])).toBeNull();
  });
});

describe("groupByDate", () => {
  it("группирует подряд идущие элементы по дате", () => {
    const groups = groupByDate(["2026-09-20", "2026-09-20", "2026-09-21"], (d) => d);
    expect(groups).toEqual([
      { date: "2026-09-20", items: ["2026-09-20", "2026-09-20"] },
      { date: "2026-09-21", items: ["2026-09-21"] },
    ]);
  });
});
