import { describe, it, expect } from "vitest";
import { priceKind } from "./price";

const ev = (priceMax: number, priceText: string) => ({ priceMax, priceText });

describe("priceKind", () => {
  it.each([
    ["Бесплатно"],
    ["бесплатно"],
    ["БЕСПЛАТНО"],
    ["Вход свободный"],
    ["Вход свободный!"],
    ["ВХОД СВОБОДНЫЙ"],
    ["0 ₽"],
    ["От 0 ₽"],
  ])("считает бесплатным price_text=%s", (text) => {
    expect(priceKind(ev(0, text))).toBe("free");
  });

  it.each([["по билетам"], ["Билеты"], ["Уточняйте"], ["Билетов нет"], [""]])(
    "считает цену неизвестной при price_text=%s",
    (text) => {
      expect(priceKind(ev(0, text))).toBe("unknown");
    },
  );

  it("считает цену известной, когда price_max > 0", () => {
    expect(priceKind(ev(700, "от 500 ₽"))).toBe("known");
  });

  it("не падает на null из БД", () => {
    expect(priceKind(ev(0, null as unknown as string))).toBe("unknown");
  });
});
