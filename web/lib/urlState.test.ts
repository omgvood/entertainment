import { describe, it, expect } from "vitest";
import { listStateKey, parseState, serializeState } from "./urlState";
import { DEFAULT_FILTERS, type Filters } from "./filters";
import type { EventType } from "./types";

const TODAY = "2026-09-19";

describe("parseState", () => {
  it("пустая строка — состояние по умолчанию", () => {
    expect(parseState("", TODAY)).toEqual({ filters: DEFAULT_FILTERS, query: "" });
  });

  it("именованные даты и будущий день принимаются", () => {
    expect(parseState("?date=weekend", TODAY).filters.date).toBe("weekend");
    expect(parseState("?date=2026-09-25", TODAY).filters.date).toBe("2026-09-25");
  });

  it("прошедшая, несуществующая или мусорная дата — умолчание", () => {
    expect(parseState("?date=2026-09-10", TODAY).filters.date).toBeNull();
    expect(parseState("?date=2026-13-45", TODAY).filters.date).toBeNull();
    expect(parseState("?date=2026-02-30", TODAY).filters.date).toBeNull();
    expect(parseState("?date=yesterday", TODAY).filters.date).toBeNull();
  });

  it("неизвестные типы отбрасываются", () => {
    expect([...parseState("?type=concert,foo", TODAY).filters.types]).toEqual(["concert"]);
  });

  it("битая цена — умолчание", () => {
    const { filters } = parseState("?pmin=-5&pmax=abc", TODAY);
    expect(filters.priceMin).toBe(0);
    expect(filters.priceMax).toBeNull();
  });
});

describe("serializeState", () => {
  it("умолчание не пишется в URL", () => {
    expect(serializeState(DEFAULT_FILTERS, "  ")).toBe("");
  });

  it("типы в порядке ALL_TYPES — строка не зависит от порядка кликов", () => {
    const f: Filters = { ...DEFAULT_FILTERS, types: new Set<EventType>(["theater", "concert"]) };
    expect(serializeState(f, "")).toBe("?type=concert%2Ctheater");
  });

  it("туда и обратно", () => {
    const f: Filters = {
      date: "2026-09-20",
      types: new Set<EventType>(["concert", "theater"]),
      priceMin: 500,
      priceMax: 2000,
    };
    const back = parseState(serializeState(f, "джаз"), TODAY);
    expect(back.query).toBe("джаз");
    expect(back.filters.date).toBe("2026-09-20");
    expect([...back.filters.types].sort()).toEqual(["concert", "theater"]);
    expect(back.filters.priceMin).toBe(500);
    expect(back.filters.priceMax).toBe(2000);
  });
});

describe("listStateKey", () => {
  it("свой ключ на город", () => {
    expect(listStateKey("perm")).toBe("afisha:list:perm");
  });
});
