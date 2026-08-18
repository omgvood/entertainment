import { describe, it, expect } from "vitest";
import { buildEventDoc, buildVenueDoc, normalize, tokenize, tokensMatch } from "./search";
import type { EventItem, VenueItem } from "./types";

const baseEvent: EventItem = {
  id: "perm-test",
  city: "perm",
  slug: "test",
  title: "Вишнёвый сад",
  type: "theater",
  date: "2026-08-20",
  priceMin: 0,
  priceMax: 0,
  priceText: "по билетам",
  address: "ул. Ленина, 51",
  venueName: "Театр-Театр",
  tags: [],
  sourceUrl: "https://example.com",
  source: "test",
  parsedAt: "2026-08-18T00:00:00Z",
};

/** Все токены документа одной плоской пачкой — для проверки наличия. */
const allTokens = (doc: { fields: { tokens: string[] }[] }) =>
  doc.fields.flatMap((f) => f.tokens);

describe("normalize", () => {
  it("приводит к нижнему регистру", () => {
    expect(normalize("Пермская Опера")).toBe("пермская опера");
  });

  it("заменяет ё на е до фильтрации, иначе ё выпадет из диапазона а-я", () => {
    expect(normalize("Ёлка")).toBe("елка");
    expect(normalize("вдвоём")).toBe("вдвоем");
  });

  it("превращает любую пунктуацию в пробел", () => {
    expect(normalize("«Мастер-класс»: рисуем!")).toBe("мастер класс рисуем");
  });

  it("склеивает разряды чисел", () => {
    expect(normalize("до 1 000 рублей")).toBe("до 1000 рублей");
  });

  it("не склеивает числа, не похожие на разряды", () => {
    expect(normalize("5 человек")).toBe("5 человек");
  });
});

describe("tokenize", () => {
  it("возвращает список непустых токенов", () => {
    expect(tokenize("  Квиз,  Плиз!  ")).toEqual(["квиз", "плиз"]);
  });

  it("возвращает пустой массив для пустой строки", () => {
    expect(tokenize("   ")).toEqual([]);
  });
});

describe("tokensMatch", () => {
  it("распознаёт точное совпадение", () => {
    expect(tokensMatch("квиз", "квиз")).toBe("exact");
  });

  it.each([
    ["квиз", "квизы"],
    ["опера", "оперы"],
    ["спектакль", "спектакли"],
    ["дети", "детей"],
    ["пермь", "пермская"],
    ["сте", "стендап"],
    ["стенда", "стендап"],
  ])("считает морфологическим совпадением %s/%s", (a, b) => {
    expect(tokensMatch(a, b)).toBe("morph");
  });

  it.each([
    ["театр", "тетрис"],
    ["бар", "баня"],
    ["ст", "стендап"],
  ])("не считает совпадением %s/%s", (a, b) => {
    expect(tokensMatch(a, b)).toBe("none");
  });
});

describe("buildEventDoc", () => {
  it("кладёт метку типа и синонимы в отдельное поле весом 60", () => {
    const doc = buildEventDoc(baseEvent);
    const typeField = doc.fields.find((f) => f.weight === 60)!;
    expect(typeField.tokens).toContain("спектакль");
    expect(typeField.tokens).toContain("театр");
    expect(typeField.tokens).toContain("theater");
  });

  it("не добавляет токен «бесплатно», когда цена неизвестна", () => {
    expect(allTokens(buildEventDoc(baseEvent))).not.toContain("бесплатно");
  });

  it.each([["Бесплатно"], ["Вход свободный"], ["0 ₽"]])(
    "добавляет токен «бесплатно» при price_text=%s",
    (priceText) => {
      const doc = buildEventDoc({ ...baseEvent, priceText });
      expect(allTokens(doc)).toContain("бесплатно");
    },
  );

  it("нормализует текст названия для фразового бонуса", () => {
    expect(buildEventDoc(baseEvent).titleText).toBe("вишневый сад");
  });

  it("не падает на пустых организаторе и описании", () => {
    expect(() => buildEventDoc(baseEvent)).not.toThrow();
  });
});

describe("buildVenueDoc", () => {
  it("индексирует имя, тип и адрес площадки", () => {
    const venue: VenueItem = {
      id: "perm-strike",
      city: "perm",
      slug: "strike",
      name: "Страйк",
      type: "bowling",
      address: "ул. Мира, 1",
      updatedAt: "2026-08-18T00:00:00Z",
    };
    const doc = buildVenueDoc(venue);
    expect(doc.fields.find((f) => f.weight === 100)!.tokens).toContain("страйк");
    expect(doc.fields.find((f) => f.weight === 60)!.tokens).toContain("боулинг");
    expect(doc.fields.find((f) => f.weight === 15)!.tokens).toContain("мира");
  });
});
