import { describe, it, expect } from "vitest";
import { eventUrl, eventJsonLd, jsonLdScript } from "./event-meta";
import type { EventItem } from "./types";

const base: EventItem = {
  id: "perm-organ",
  city: "perm",
  slug: "organ-2026-09-30",
  title: "Органный вечер",
  type: "concert",
  date: "2026-09-30",
  timeStart: "19:00",
  priceMin: 500,
  priceMax: 700,
  priceText: "от 500 до 700 ₽",
  address: "ул. Ленина, 51",
  venueName: "Органный зал",
  imageUrl: "https://example.org/organ.jpg",
  tags: [],
  sourceUrl: "https://example.org/organ",
  source: "manual",
  parsedAt: "2026-09-29T00:00:00Z",
};

describe("eventUrl", () => {
  it("без слэша на конце", () => {
    expect(eventUrl(base)).toMatch(/\/perm\/events\/organ-2026-09-30$/);
  });
});

describe("eventJsonLd", () => {
  it("Event с названием, адресом места и ссылкой на страницу", () => {
    const ld = eventJsonLd(base)!;
    expect(ld["@type"]).toBe("Event");
    expect(ld.name).toBe("Органный вечер");
    expect(ld.url).toBe(eventUrl(base));
    expect(ld.location).toEqual({
      "@type": "Place",
      name: "Органный зал",
      address: {
        "@type": "PostalAddress",
        streetAddress: "ул. Ленина, 51",
        addressLocality: "Пермь",
      },
    });
  });

  it("startDate в часовом поясе города: Пермь +05:00, Сочи +03:00", () => {
    expect(eventJsonLd(base)!.startDate).toBe("2026-09-30T19:00:00+05:00");
    expect(eventJsonLd({ ...base, city: "sochi" })!.startDate).toBe(
      "2026-09-30T19:00:00+03:00",
    );
  });

  it("без времени — только дата; endDate только при timeEnd", () => {
    const noTime = eventJsonLd({ ...base, timeStart: undefined })!;
    expect(noTime.startDate).toBe("2026-09-30");
    expect(noTime.endDate).toBeUndefined();
    expect(eventJsonLd({ ...base, timeEnd: "21:00" })!.endDate).toBe(
      "2026-09-30T21:00:00+05:00",
    );
  });

  it("событие без даты («always») разметки не получает", () => {
    expect(eventJsonLd({ ...base, date: "always" })).toBeNull();
  });

  it("offers: известная цена, бесплатно, неизвестно", () => {
    expect(eventJsonLd(base)!.offers).toEqual({
      "@type": "Offer",
      price: 500,
      priceCurrency: "RUB",
      url: "https://example.org/organ",
    });
    const free = { ...base, priceMin: 0, priceMax: 0, priceText: "Бесплатно" };
    expect((eventJsonLd(free)!.offers as { price: number }).price).toBe(0);
    const unknown = { ...base, priceMin: 0, priceMax: 0, priceText: "по билетам" };
    expect(eventJsonLd(unknown)!.offers).toBeUndefined();
  });

  it("image только у годной картинки", () => {
    expect(eventJsonLd(base)!.image).toBe("https://example.org/organ.jpg");
    expect(eventJsonLd({ ...base, imageUrl: "https://example.org/logo.svg" })!.image).toBeUndefined();
    expect(eventJsonLd({ ...base, imageUrl: undefined })!.image).toBeUndefined();
  });
});

describe("jsonLdScript", () => {
  it("название с </script> не закрывает тег скрипта", () => {
    const html = jsonLdScript(eventJsonLd({ ...base, title: "</script><b>x" }));
    expect(html).not.toContain("</script>");
    expect(JSON.parse(html).name).toBe("</script><b>x");
  });
});
