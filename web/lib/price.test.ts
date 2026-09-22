import { describe, it, expect } from "vitest";
import { priceBadge, priceKind } from "./price";

const ev = (priceMax: number, priceText: string) => ({ priceMax, priceText });
const badgeEv = (priceMin: number, priceMax: number, priceText: string) => ({
  priceMin,
  priceMax,
  priceText,
});

describe("priceKind", () => {
  it.each([
    ["Бесплатно"],
    ["бесплатно"],
    ["БЕСПЛАТНО"],
    ["Вход свободный"],
    ["Вход свободный!"],
    ["ВХОД СВОБОДНЫЙ"],
  ])("считает бесплатным price_text=%s", (text) => {
    expect(priceKind(ev(0, text))).toBe("free");
  });

  it.each([
    ["по билетам"],
    ["Билеты"],
    ["Уточняйте"],
    ["Билетов нет"],
    [""],
    ["0 ₽"],
    ["От 0 ₽"],
  ])(
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

describe("priceBadge", () => {
  it("бесплатное событие даёт «Бесплатно»", () => {
    expect(priceBadge(badgeEv(0, 0, "Бесплатно"))).toBe("Бесплатно");
  });

  it("известная одна цена без разброса — «{цена} ₽»", () => {
    expect(priceBadge(badgeEv(600, 600, "600 ₽"))).toBe("600 ₽");
  });

  it("известная цена с разбросом — «от {минимум} ₽»", () => {
    expect(priceBadge(badgeEv(440, 700, "от 440 до 700 ₽"))).toBe("от 440 ₽");
  });

  it("неизвестная цена — нет бейджа (null)", () => {
    expect(priceBadge(badgeEv(0, 0, "по билетам"))).toBeNull();
  });
});
