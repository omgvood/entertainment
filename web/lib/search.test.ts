import { describe, it, expect } from "vitest";
import {
  buildEventDoc,
  buildVenueDoc,
  normalize,
  parseQuery,
  searchEvents,
  searchVenues,
  tokenize,
  tokensMatch,
} from "./search";
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

  it("не добавляет токен «бесплатно» при price_text=0 ₽", () => {
    expect(allTokens(buildEventDoc({ ...baseEvent, priceText: "0 ₽" }))).not.toContain(
      "бесплатно",
    );
  });

  it.each([["Бесплатно"], ["Вход свободный"]])(
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

const mkEvent = (over: Partial<EventItem>): EventItem => ({ ...baseEvent, ...over });
const TODAY = "2026-08-18";

describe("parseQuery", () => {
  it("выбрасывает стоп-слова и слова-обращения", () => {
    expect(parseQuery("куда сходить на квиз").map((t) => t.variants[0])).toEqual(["квиз"]);
  });

  it("возвращает пустой список, если запрос состоит только из стоп-слов", () => {
    expect(parseQuery("куда сходить")).toEqual([]);
  });

  it("разворачивает намерение в токены тега", () => {
    expect(parseQuery("свидание")[0].variants).toContain("пары");
  });
});

describe("searchEvents", () => {
  const docs = [
    mkEvent({ id: "a", slug: "a", title: "Квиз, плиз!", type: "quiz", date: "2026-09-01" }),
    mkEvent({ id: "b", slug: "b", title: "Вишнёвый сад", type: "theater", date: "2026-09-01" }),
    mkEvent({
      id: "c",
      slug: "c",
      title: "Тайны города",
      type: "quiz",
      date: "2026-09-01",
      description: "Интеллектуальный квиз для компании",
    }),
  ].map(buildEventDoc);

  it("находит события по метке типа, а не только по названию", () => {
    const ids = searchEvents(docs, "квиз", TODAY).map((h) => h.item.id);
    expect(ids).toContain("a");
    expect(ids).toContain("c");
    expect(ids).not.toContain("b");
  });

  it("ранжирует совпадение в названии выше совпадения в описании", () => {
    const hits = searchEvents(docs, "квиз", TODAY);
    expect(hits[0].item.id).toBe("a");
  });

  it("применяет AND: карточка без одного из терминов выбрасывается", () => {
    const ids = searchEvents(docs, "квиз вишнёвый", TODAY).map((h) => h.item.id);
    expect(ids).toEqual([]);
  });

  it("берёт max по полям, а не сумму", () => {
    const both = buildEventDoc(
      mkEvent({ id: "d", slug: "d", title: "Опера", type: "concert", description: "Опера" }),
    );
    const titleOnly = buildEventDoc(
      mkEvent({ id: "e", slug: "e", title: "Опера", type: "concert" }),
    );
    const [a, b] = [
      searchEvents([both], "опера", TODAY)[0].score,
      searchEvents([titleOnly], "опера", TODAY)[0].score,
    ];
    expect(a).toBe(b);
  });

  it("даёт фразовый бонус за совпадение всей фразы в названии", () => {
    const exact = buildEventDoc(mkEvent({ id: "f", slug: "f", title: "Пермская опера" }));
    const split = buildEventDoc(mkEvent({ id: "g", slug: "g", title: "Опера в Перми: гала" }));
    const hits = searchEvents([split, exact], "пермская опера", TODAY);
    expect(hits[0].item.id).toBe("f");
  });

  it("поднимает событие сегодня над таким же событием в будущем", () => {
    const soon = buildEventDoc(mkEvent({ id: "h", slug: "h", title: "Квиз", date: TODAY }));
    const later = buildEventDoc(mkEvent({ id: "i", slug: "i", title: "Квиз", date: "2026-09-30" }));
    expect(searchEvents([later, soon], "квиз", TODAY)[0].item.id).toBe("h");
  });

  it("возвращает пустой результат на запрос из одних стоп-слов", () => {
    expect(searchEvents(docs, "куда сходить", TODAY)).toEqual([]);
  });

  it("находит события с тегом «для пары» по запросу «свидание»", () => {
    const dating = buildEventDoc(mkEvent({ id: "j", slug: "j", tags: ["для пары"] }));
    expect(searchEvents([dating], "свидание", TODAY)).toHaveLength(1);
  });

  it("находит бесплатные события по запросу «бесплатно»", () => {
    const free = buildEventDoc(mkEvent({ id: "k", slug: "k", priceText: "Вход свободный" }));
    const paid = buildEventDoc(mkEvent({ id: "l", slug: "l", priceMax: 500, priceText: "500 ₽" }));
    const ids = searchEvents([free, paid], "бесплатно", TODAY).map((h) => h.item.id);
    expect(ids).toEqual(["k"]);
  });
});

describe("searchVenues", () => {
  it("находит площадки по типу", () => {
    const docs = [
      buildVenueDoc({
        id: "perm-strike",
        city: "perm",
        slug: "strike",
        name: "Страйк",
        type: "bowling",
        updatedAt: "2026-08-18T00:00:00Z",
      }),
    ];
    expect(searchVenues(docs, "боулинг")).toHaveLength(1);
  });
});
