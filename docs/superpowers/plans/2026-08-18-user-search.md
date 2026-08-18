# Пользовательский поиск (фаза 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Расположение файла.** План написан в plan-mode, поэтому лежит вне репозитория. Первым действием при исполнении скопировать его в `docs/superpowers/plans/2026-08-18-user-search.md` и закоммитить.

## Context

Поиск на сайте фактически отсутствует: в [`FilterBar.tsx:51`](../../../Python/entertainment/web/components/FilterBar.tsx) стоит `<input type="search">` без `value` и `onChange` — мёртвая заглушка. Пользователь может отфильтровать афишу по типу, дате и цене, но не может найти «стендап», «Пермская опера» или «квиз».

Строим ранжированный клиентский поиск по событиям и площадкам. Ранжированный, а не `contains()`: совпадение в названии должно весить больше, чем в описании.

**Почему на клиенте, а не через Postgres `ts_vector`.** Сайт полностью статический (SSG), runtime-запросов нет вообще. При этом весь массив будущих событий города уже уезжает в браузер: 571 событие для Перми, ~150 КБ текста. Поиск по нему в памяти — 1-2 мс, ноль инфраструктуры, ноль сетевых задержек. `ts_vector` потребовал бы serverless-роут ради задачи, которая решается линейным проходом. Порог пересмотра — примерно 10 000 событий на город.

**Ключевая находка разведки, определившая половину дизайна.** Названия событий не содержат слова, обозначающего тип: из 94 концертов Перми слово «концерт» есть в названии у 28, из 19 квизов — у 9, из 22 вечеринок — у 0. Поэтому в индекс добавлено синтетическое поле `typeLabel` (метка типа + синонимы) с весом 60 — без него запрос «квиз» находит меньше половины квизов.

**Вторая находка — поломка в данных.** У 522 из 641 события `price_max = 0`, но это два разных смысла: 347 действительно бесплатны («Бесплатно», «Вход свободный»), а 175 — цена неизвестна («по билетам», «Уточняйте»). Различить можно только регекспом по `price_text`. Отсюда два следствия: синтетический токен «бесплатно» строится по `price_text`, а не по `price_max`; и существующий фильтр цены чинится тем же предикатом (Task 5).

**Goal:** Ранжированный поиск по событиям и площадкам города, работающий целиком в браузере, с честной интеграцией в существующие фильтры.

**Architecture:** Чистое ядро в `web/lib/` (нормализация → токенизация → поисковый документ → скоринг), над ним тонкий UI-слой в `CityView`. Индекс строится один раз при монтировании через `useMemo` из уже загруженного массива; каждый ввод — линейный проход. Состояние запроса живёт в `CityView` рядом с `filters`, синхронизируется в `?q=` через `history.replaceState`.

**Tech Stack:** TypeScript, Next.js 16 (SSG, client components), React 19, vitest (новая зависимость, только на чистые функции).

**Spec:** Отдельного файла спеки нет — проектные решения зафиксированы в Global Constraints ниже и в комментариях к задачам.

---

## Global Constraints

- **Никаких новых рантайм-зависимостей.** `vitest` добавляется только в `devDependencies`.
- **Сайт остаётся статическим.** Ни серверных компонентов с динамикой, ни route handlers, ни `useSearchParams()` из `next/navigation` (он требует `<Suspense>` и уводит страницу из чистого SSG).
- **Внутри `web/lib/` импорты относительные** (`./types`, а не `@/lib/types`) — как уже сделано в `filters.ts`. Это позволяет запускать vitest без конфига с алиасами.
- **В тестах импорты из `vitest` явные** (`import { describe, it, expect } from "vitest"`), без глобалов: `tsconfig.json` включает `**/*.ts`, и `next build` типизирует тестовые файлы тоже.
- **Все словарные значения хранятся в нормализованном виде** (нижний регистр, без `ё`) и всё равно прогоняются через `tokenize` при инициализации.
- **Веса ранжирования:** `title` 100, `typeLabel` 60, `venueName` 50, `organizer` 30, `tags` 20, `description` 10. Для площадок: `name` 100, `typeLabel` 60, `address` 15.
- **Коэффициент морфологического совпадения** 0.6, точного — 1.0.
- **Скор термина — `max` по полям, а не сумма.** Слово, встречающееся и в названии, и в описании, даёт 100, а не 110. Иначе длинные описания начинают выигрывать у точных совпадений в названии.
- **AND по терминам:** если хотя бы один термин запроса не найден ни в одном поле, карточка выбрасывается.
- **Бусты не отсекают, только поднимают:** +15 событию сегодня/завтра, +5 при наличии картинки (заполнено у 350/641 — сигнал живой).
- **`source priority` в ранжировании не участвует.** Колонки нет в таблице `events`, она живёт в `seeds.yaml` и отвечает на вопрос «кому верить при склейке дублей», а не «насколько это релевантно запросу».
- **Порог активации поиска — 2 символа И хотя бы один осмысленный термин.** 0-1 символ показывает обычные секции дня; запрос из одних стоп-слов («куда сходить») — тоже, а не «ничего не нашлось».
- **Фаза 2 (intent-парсер) в этот план не входит.** Она заблокирована качеством данных по цене — см. Follow-up.

---

## Структура файлов

**Создаются:**

| Файл | Ответственность |
|---|---|
| `web/lib/price.ts` | `priceKind(event) → 'free' \| 'known' \| 'unknown'` — единственное место, где строка `price_text` превращается в смысл. Используют и поиск, и фильтр |
| `web/lib/search-synonyms.ts` | Словари: `TYPE_SYNONYMS`, `VENUE_TYPE_SYNONYMS`, `INTENT_SYNONYMS`, `STOP_WORDS`. Только данные, без логики |
| `web/lib/search.ts` | Ядро: `normalize`, `tokenize`, `tokensMatch`, `parseQuery`, `buildEventDoc`, `buildVenueDoc`, `scoreDoc`, `searchEvents`, `searchVenues` |
| `web/lib/price.test.ts` | Тесты `priceKind` |
| `web/lib/search.test.ts` | Тесты ядра |
| `web/lib/filters.test.ts` | Тесты изменённого предиката цены |

**Изменяются:**

| Файл | Что меняется |
|---|---|
| `web/package.json` | `vitest` в devDependencies, скрипт `test` |
| `web/lib/filters.ts` | Предикат цены пропускает события с неизвестной ценой |
| `web/components/FilterBar.tsx` | Живой инпут (`query`/`onQueryChange`, Escape, ✕) + мобильная вёрстка |
| `web/components/CityView.tsx` | Состояние поиска, выдача, группа «Места», `VenuesSection` внутрь, `?q=` |
| `web/app/perm/page.tsx`, `web/app/sochi/page.tsx` | Полный массив `venues` уходит в `CityView`, `VenuesSection` оттуда убирается |
| `README.md` | Раздел про поиск, структура репозитория, снятие пункта 12 из роадмапа |

---

### Task 1: Тестовый раннер и предикат цены

Фундамент: `npm test` начинает работать, и появляется общий предикат, от которого зависят Task 3 и Task 5.

**Files:**
- Modify: `web/package.json`
- Create: `web/lib/price.ts`
- Test: `web/lib/price.test.ts`

**Interfaces:**
- Consumes: `EventItem` из `web/lib/types.ts`
- Produces: `type PriceKind = "free" | "known" | "unknown"`; `priceKind(event: Pick<EventItem, "priceMax" | "priceText">): PriceKind`

- [ ] **Шаг 1: Установить vitest**

```bash
cd web && npm install --save-dev vitest
```

- [ ] **Шаг 2: Добавить скрипт в `web/package.json`**

В блок `"scripts"`, после `"lint": "eslint"`:

```json
    "test": "vitest run"
```

- [ ] **Шаг 3: Написать падающий тест**

Создать `web/lib/price.test.ts`:

```ts
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
```

- [ ] **Шаг 4: Убедиться, что тест падает**

Запустить: `cd web && npm test`
Ожидается: FAIL — `Failed to resolve import "./price"`

- [ ] **Шаг 5: Реализовать `web/lib/price.ts`**

```ts
/**
 * Смысл цены события.
 *
 * В БД `price_max = 0` означает две разные вещи: «бесплатно» и «цена неизвестна».
 * На 2026-08 в Перми это 347 против 175 событий. Различить их можно только по
 * строке `price_text`, которую пишет LLM («Бесплатно» против «по билетам»).
 *
 * Это заплатка над проблемой данных: устойчивое решение — отдельная колонка,
 * заполняемая парсером. До тех пор каждый потребитель обязан выводить смысл
 * заново, поэтому вывод живёт здесь в единственном экземпляре.
 */

import type { EventItem } from "./types";

const FREE_RE = /бесплатн|вход свободн|свободный вход|^0\s*₽|^от 0\s*₽|^0$/i;

export type PriceKind = "free" | "known" | "unknown";

export function priceKind(event: Pick<EventItem, "priceMax" | "priceText">): PriceKind {
  if (event.priceMax > 0) return "known";
  return FREE_RE.test(event.priceText ?? "") ? "free" : "unknown";
}
```

- [ ] **Шаг 6: Убедиться, что тесты проходят**

Запустить: `cd web && npm test`
Ожидается: PASS, 14 тестов

- [ ] **Шаг 7: Коммит**

```bash
git add web/package.json web/package-lock.json web/lib/price.ts web/lib/price.test.ts
git commit -m "feat(web): добавить vitest и предикат priceKind"
```

---

### Task 2: Нормализация, токенизация, морфологический матч

Самый нагруженный граничными случаями кусок. Ошибка здесь тихо портит всю выдачу, поэтому тесты табличные и подробные.

**Files:**
- Create: `web/lib/search-synonyms.ts`
- Create: `web/lib/search.ts`
- Test: `web/lib/search.test.ts`

**Interfaces:**
- Consumes: `EventType` из `./types`
- Produces: `normalize(s: string): string`; `tokenize(s: string): string[]`; `type MatchKind = "exact" | "morph" | "none"`; `tokensMatch(a: string, b: string): MatchKind`; словари `TYPE_SYNONYMS`, `VENUE_TYPE_SYNONYMS`, `INTENT_SYNONYMS`, `STOP_WORDS`

- [ ] **Шаг 1: Написать падающий тест**

Создать `web/lib/search.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { normalize, tokenize, tokensMatch } from "./search";

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
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `cd web && npm test`
Ожидается: FAIL — `Failed to resolve import "./search"`

- [ ] **Шаг 3: Создать словари `web/lib/search-synonyms.ts`**

```ts
/**
 * Словари поиска. Только данные, без логики.
 * Все значения — в нормализованном виде (нижний регистр, без «ё»);
 * при сборке индекса они всё равно прогоняются через tokenize.
 */

import type { EventType } from "./types";

/**
 * Разговорные слова для типа события. Нужны потому, что название события
 * почти никогда не содержит слова, обозначающего тип: из 94 концертов Перми
 * слово «концерт» есть в названии у 28, из 22 вечеринок — у нуля.
 * Метка типа из EVENT_TYPE_LABELS добавляется к этому списку отдельно.
 */
export const TYPE_SYNONYMS: Record<EventType, string[]> = {
  quiz: ["quiz", "квиз", "викторина", "мозгобойня"],
  standup: ["standup", "стендап", "стэндап", "комик", "открытый микрофон"],
  bowling: ["bowling", "боулинг"],
  billiards: ["billiards", "бильярд", "пул"],
  karting: ["karting", "картинг"],
  concert: ["concert", "концерт", "музыка", "выступление"],
  theater: ["theater", "театр", "спектакль", "постановка"],
  exhibition: ["exhibition", "выставка", "экспозиция", "вернисаж"],
  festival: ["festival", "фестиваль", "фест"],
  quest: ["quest", "квест"],
  party: ["party", "вечеринка", "тусовка", "дискотека"],
  cinema: ["cinema", "кино", "фильм", "кинопоказ"],
  sport: ["sport", "спорт", "матч", "турнир"],
  education: ["education", "лекция", "курс", "семинар", "тренинг"],
  business: ["business", "бизнес", "конференция", "форум", "нетворкинг"],
  art: ["art", "искусство", "арт"],
  kids: ["kids", "детям", "детский", "семейный"],
  food: ["food", "еда", "гастрономия", "дегустация"],
  trip: ["trip", "экскурсия", "прогулка", "тур"],
  hobby: ["hobby", "хобби", "мастер класс", "рукоделие"],
  science: ["science", "наука", "научпоп"],
  other: [],
};

/** То же для типов площадок из таблицы venues (тип — строка, не enum). */
export const VENUE_TYPE_SYNONYMS: Record<string, string[]> = {
  bowling: ["bowling", "боулинг", "дорожка"],
  billiards: ["billiards", "бильярд", "пул"],
  karting: ["karting", "картинг"],
  quest: ["quest", "квест"],
};

/**
 * Разворот запроса в теги таксономии: «свидание» должно находить события
 * с тегом «для пары». Ключ — значение тега из parser/src/parser/taxonomy.py,
 * значение — слова, которыми это намерение выражают пользователи.
 */
export const INTENT_SYNONYMS: Record<string, string[]> = {
  "для детей": ["детям", "ребенком", "детьми", "семейный"],
  "для пары": ["свидание", "романтика", "вдвоем", "девушкой", "парнем"],
  "для компании": ["друзьями", "компанией"],
  вечером: ["вечер", "вечерний", "ночью"],
  бесплатно: ["free", "даром"],
  активное: ["спортивное", "подвижное"],
};

/**
 * Выкидываются только из запроса, не из документов.
 * Без слов-обращений запрос «куда сходить на квиз» даёт AND по «куда»+«сходить»
 * и возвращает ноль результатов.
 */
export const STOP_WORDS = new Set([
  "в", "на", "с", "и", "или", "для", "по", "до", "от", "за", "к", "у", "о", "об", "бы",
  "куда", "где", "что", "чем", "сходить", "пойти", "идти", "можно", "хочу",
  "хочется", "посоветуй", "подскажи", "найди",
]);
```

- [ ] **Шаг 4: Реализовать низкий уровень в `web/lib/search.ts`**

```ts
/**
 * Ядро пользовательского поиска. Чистые функции, без React и DOM.
 *
 * Поиск работает целиком в браузере по уже загруженному массиву событий
 * (571 карточка для Перми): сайт статический, runtime-запросов нет.
 */

export type MatchKind = "exact" | "morph" | "none";

export function normalize(s: string): string {
  return s
    .toLowerCase()
    // «ё» (U+0451) лежит за границей диапазона «а-я» (U+0430–U+044F),
    // поэтому замена обязана идти до фильтрации — иначе «ёлка» станет «лка».
    .replace(/ё/g, "е")
    .replace(/[^a-zа-я0-9]+/g, " ")
    // «1 000» → «1000»: разряды числа, а не два разных токена.
    .replace(/(\d)\s+(?=\d{3}\b)/g, "$1")
    .trim();
}

export function tokenize(s: string): string[] {
  return normalize(s).split(" ").filter(Boolean);
}

/**
 * Морфология без стеммера: считаем совпадением общий префикс, допуская
 * расхождение до двух символов в хвосте, но не короче трёх символов.
 *
 * Простого startsWith недостаточно: русские окончания меняют последнюю букву,
 * а не только дописывают её — «опера»/«оперы» не префикс друг друга.
 * Порог в три символа заодно даёт typeahead: «сте» находит «стендап».
 */
export function tokensMatch(a: string, b: string): MatchKind {
  if (a === b) return "exact";
  const min = Math.min(a.length, b.length);
  const need = Math.max(3, min - 2);
  let common = 0;
  while (common < min && a[common] === b[common]) common++;
  return common >= need ? "morph" : "none";
}
```

- [ ] **Шаг 5: Убедиться, что тесты проходят**

Запустить: `cd web && npm test`
Ожидается: PASS, все тесты `normalize` / `tokenize` / `tokensMatch`

- [ ] **Шаг 6: Коммит**

```bash
git add web/lib/search.ts web/lib/search-synonyms.ts web/lib/search.test.ts
git commit -m "feat(web): нормализация, токенизация и морфологический матч"
```

---

### Task 3: Поисковый документ

**Files:**
- Modify: `web/lib/search.ts`
- Test: `web/lib/search.test.ts`

**Interfaces:**
- Consumes: `priceKind` из `./price`; `TYPE_SYNONYMS`, `VENUE_TYPE_SYNONYMS` из `./search-synonyms`; `EVENT_TYPE_LABELS`, `getVenueTypeLabel`, `EventItem`, `VenueItem` из `./types`
- Produces: `interface DocField { weight: number; tokens: string[] }`; `interface SearchDoc<T> { item: T; fields: DocField[]; titleText: string; venueText: string }`; `buildEventDoc(event: EventItem): SearchDoc<EventItem>`; `buildVenueDoc(venue: VenueItem): SearchDoc<VenueItem>`

- [ ] **Шаг 1: Написать падающий тест**

Дописать в `web/lib/search.test.ts`. Импорт из `./search` **дописать в существующую строку** Task 2, а не добавлять второй `import` из того же модуля:

```ts
// было: import { normalize, tokenize, tokensMatch } from "./search";
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
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `cd web && npm test`
Ожидается: FAIL — `buildEventDoc is not a function`

- [ ] **Шаг 3: Реализовать построение документа**

Дописать в `web/lib/search.ts`:

```ts
import type { EventItem, VenueItem } from "./types";
import { EVENT_TYPE_LABELS, getVenueTypeLabel } from "./types";
import { priceKind } from "./price";
import { TYPE_SYNONYMS, VENUE_TYPE_SYNONYMS } from "./search-synonyms";

export interface DocField {
  weight: number;
  tokens: string[];
}

export interface SearchDoc<T> {
  item: T;
  fields: DocField[];
  /** Нормализованное название — для фразового бонуса. */
  titleText: string;
  /** Нормализованное имя площадки — для фразового бонуса. */
  venueText: string;
}

export function buildEventDoc(event: EventItem): SearchDoc<EventItem> {
  const typeWords = [EVENT_TYPE_LABELS[event.type], ...TYPE_SYNONYMS[event.type]].join(" ");
  // Синтетический токен по price_text, а не по price_max: нулевая цена в БД
  // означает и «бесплатно», и «неизвестно», см. lib/price.ts.
  const freeWords = priceKind(event) === "free" ? "бесплатно free вход свободный" : "";

  return {
    item: event,
    fields: [
      { weight: 100, tokens: tokenize(event.title) },
      { weight: 60, tokens: tokenize(typeWords) },
      { weight: 50, tokens: tokenize(event.venueName) },
      { weight: 30, tokens: tokenize(event.organizer ?? "") },
      { weight: 20, tokens: tokenize([...event.tags, freeWords].join(" ")) },
      { weight: 10, tokens: tokenize(event.description ?? "") },
    ],
    titleText: normalize(event.title),
    venueText: normalize(event.venueName),
  };
}

export function buildVenueDoc(venue: VenueItem): SearchDoc<VenueItem> {
  const typeWords = [
    getVenueTypeLabel(venue.type),
    ...(VENUE_TYPE_SYNONYMS[venue.type] ?? []),
  ].join(" ");

  return {
    item: venue,
    fields: [
      { weight: 100, tokens: tokenize(venue.name) },
      { weight: 60, tokens: tokenize(typeWords) },
      { weight: 15, tokens: tokenize(venue.address ?? "") },
    ],
    titleText: normalize(venue.name),
    venueText: "",
  };
}
```

- [ ] **Шаг 4: Убедиться, что тесты проходят**

Запустить: `cd web && npm test`
Ожидается: PASS

- [ ] **Шаг 5: Коммит**

```bash
git add web/lib/search.ts web/lib/search.test.ts
git commit -m "feat(web): построение поискового документа события и площадки"
```

---

### Task 4: Разбор запроса, скоринг и поиск

**Files:**
- Modify: `web/lib/search.ts`
- Test: `web/lib/search.test.ts`

**Interfaces:**
- Consumes: всё из Task 2-3; `INTENT_SYNONYMS`, `STOP_WORDS` из `./search-synonyms`; `addDaysUTC` из `./dateUtil`
- Produces: `interface QueryTerm { variants: string[] }`; `parseQuery(query: string): QueryTerm[]`; `scoreDoc<T>(doc, terms, phrase): number | null`; `type SearchHit`, `EventHit`, `VenueHit`; `searchEvents(docs, query, today): EventHit[]`; `searchVenues(docs, query): VenueHit[]`

- [ ] **Шаг 1: Написать падающий тест**

Дописать в `web/lib/search.test.ts`, добавив `parseQuery`, `searchEvents`, `searchVenues` в тот же единственный импорт из `./search`:

```ts
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
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `cd web && npm test`
Ожидается: FAIL — `parseQuery is not a function`

- [ ] **Шаг 3: Реализовать разбор запроса и скоринг**

Дописать в `web/lib/search.ts`:

```ts
import { addDaysUTC } from "./dateUtil";
import { INTENT_SYNONYMS, STOP_WORDS } from "./search-synonyms";

const MORPH_FACTOR = 0.6;
const PHRASE_TITLE_BONUS = 100;
const PHRASE_VENUE_BONUS = 50;
const BOOST_SOON = 15;
const BOOST_IMAGE = 5;

export interface QueryTerm {
  /** Сам токен плюс токены тегов, в которые он разворачивается. */
  variants: string[];
}

/** Предрассчитанный разворот намерений: слово пользователя → токены тега. */
const INTENT_INDEX = Object.entries(INTENT_SYNONYMS).map(([tag, synonyms]) => ({
  tagTokens: tokenize(tag).filter((t) => !STOP_WORDS.has(t)),
  triggers: [tag, ...synonyms].flatMap(tokenize).filter((t) => !STOP_WORDS.has(t)),
}));

function expandIntent(token: string): string[] {
  const out: string[] = [];
  for (const entry of INTENT_INDEX) {
    if (entry.triggers.some((trigger) => tokensMatch(token, trigger) !== "none")) {
      out.push(...entry.tagTokens);
    }
  }
  return out;
}

export function parseQuery(query: string): QueryTerm[] {
  return tokenize(query)
    .filter((t) => !STOP_WORDS.has(t))
    .map((t) => ({ variants: [t, ...expandIntent(t)] }));
}

/**
 * Скор документа или null, если хотя бы один термин не найден (AND-семантика).
 * Для каждого термина берём лучшее поле, а не сумму по полям: иначе слово,
 * встречающееся и в названии, и в описании, весит больше точного попадания
 * в название, и длинные описания начинают выигрывать.
 */
export function scoreDoc<T>(
  doc: SearchDoc<T>,
  terms: QueryTerm[],
  phrase: string,
): number | null {
  let score = 0;

  for (const term of terms) {
    let best = 0;
    for (const field of doc.fields) {
      if (field.weight <= best) continue; // лучше уже не станет
      for (const docToken of field.tokens) {
        for (const variant of term.variants) {
          const kind = tokensMatch(variant, docToken);
          if (kind === "none") continue;
          const value = field.weight * (kind === "exact" ? 1 : MORPH_FACTOR);
          if (value > best) best = value;
        }
      }
    }
    if (best === 0) return null;
    score += best;
  }

  // Фразовый бонус осмыслен только для многословных запросов: для одного слова
  // он повторяет то, что уже посчитал точный матч.
  if (terms.length >= 2) {
    if (doc.titleText.includes(phrase)) score += PHRASE_TITLE_BONUS;
    if (doc.venueText.includes(phrase)) score += PHRASE_VENUE_BONUS;
  }

  return score;
}

export interface EventHit {
  kind: "event";
  item: EventItem;
  score: number;
}

export interface VenueHit {
  kind: "venue";
  item: VenueItem;
  score: number;
}

export type SearchHit = EventHit | VenueHit;

export function searchEvents(
  docs: SearchDoc<EventItem>[],
  query: string,
  today: string,
): EventHit[] {
  const terms = parseQuery(query);
  if (terms.length === 0) return [];

  const phrase = normalize(query);
  const tomorrow = addDaysUTC(today, 1);
  const hits: EventHit[] = [];

  for (const doc of docs) {
    const base = scoreDoc(doc, terms, phrase);
    if (base === null) continue;

    let score = base;
    // Бусты поднимают, но никогда не отсекают.
    if (doc.item.date === today || doc.item.date === tomorrow) score += BOOST_SOON;
    if (doc.item.imageUrl) score += BOOST_IMAGE;

    hits.push({ kind: "event", item: doc.item, score });
  }

  hits.sort((a, b) => b.score - a.score || a.item.date.localeCompare(b.item.date));
  return hits;
}

export function searchVenues(docs: SearchDoc<VenueItem>[], query: string): VenueHit[] {
  const terms = parseQuery(query);
  if (terms.length === 0) return [];

  const phrase = normalize(query);
  const hits: VenueHit[] = [];

  for (const doc of docs) {
    const score = scoreDoc(doc, terms, phrase);
    if (score === null) continue;
    hits.push({ kind: "venue", item: doc.item, score });
  }

  hits.sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name));
  return hits;
}
```

- [ ] **Шаг 4: Убедиться, что тесты проходят**

Запустить: `cd web && npm test`
Ожидается: PASS

- [ ] **Шаг 5: Коммит**

```bash
git add web/lib/search.ts web/lib/search.test.ts
git commit -m "feat(web): ранжированный поиск по событиям и площадкам"
```

---

### Task 5: Починить предикат цены в фильтрах

Пермиссивная семантика: если цена неизвестна, фильтр цены к событию не применяется. Прятать карточку из-за пробела в данных хуже, чем показать её.

**Files:**
- Modify: `web/lib/filters.ts:105-108`
- Test: `web/lib/filters.test.ts`

**Interfaces:**
- Consumes: `priceKind` из `./price`
- Produces: изменений в сигнатуре `applyFilters` нет

- [ ] **Шаг 1: Написать падающий тест**

Создать `web/lib/filters.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { applyFilters, DEFAULT_FILTERS } from "./filters";
import type { EventItem } from "./types";

const TODAY = "2026-08-18";

const mk = (over: Partial<EventItem>): EventItem => ({
  id: "perm-x",
  city: "perm",
  slug: "x",
  title: "Событие",
  type: "concert",
  date: "2026-08-20",
  priceMin: 0,
  priceMax: 0,
  priceText: "по билетам",
  address: "адрес",
  venueName: "площадка",
  tags: [],
  sourceUrl: "https://example.com",
  source: "test",
  parsedAt: "2026-08-18T00:00:00Z",
  ...over,
});

describe("applyFilters — цена", () => {
  const narrow = { ...DEFAULT_FILTERS, priceMin: 500, priceMax: 5000 };

  it("показывает событие с неизвестной ценой даже при нижней границе", () => {
    const unknown = mk({ priceText: "по билетам" });
    expect(applyFilters([unknown], narrow, TODAY)).toHaveLength(1);
  });

  it("прячет бесплатное событие при нижней границе", () => {
    const free = mk({ priceText: "Бесплатно" });
    expect(applyFilters([free], narrow, TODAY)).toHaveLength(0);
  });

  it("оставляет обычную фильтрацию для событий с известной ценой", () => {
    const cheap = mk({ priceMin: 100, priceMax: 200, priceText: "200 ₽" });
    expect(applyFilters([cheap], narrow, TODAY)).toHaveLength(0);
    expect(applyFilters([cheap], DEFAULT_FILTERS, TODAY)).toHaveLength(1);
  });
});
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `cd web && npm test`
Ожидается: FAIL на первом тесте — событие с неизвестной ценой отсекается (`0 < 500`)

- [ ] **Шаг 3: Изменить `web/lib/filters.ts`**

Добавить импорт после существующих:

```ts
import { priceKind } from "./price";
```

Заменить блок цены (строки 105-108):

```ts
    // 3. Цена — пересечение диапазонов.
    // Событие с неизвестной ценой («по билетам», «Уточняйте») предикат
    // пропускает: в БД такая цена неотличима от нуля, и прятать карточку
    // из-за пробела в данных хуже, чем показать её. Подробнее — lib/price.ts.
    if (priceKind(event) !== "unknown") {
      if (event.priceMax < filters.priceMin) return false;
      if (event.priceMin > filters.priceMax) return false;
    }
```

- [ ] **Шаг 4: Убедиться, что тесты проходят**

Запустить: `cd web && npm test`
Ожидается: PASS, весь набор

- [ ] **Шаг 5: Коммит**

```bash
git add web/lib/filters.ts web/lib/filters.test.ts
git commit -m "fix(web): не прятать события с неизвестной ценой из-под фильтра"
```

---

### Task 6: Перенести VenuesSection внутрь CityView

Чистый рефакторинг без изменения поведения. Нужен для Task 8: при активном поиске блок «Постоянные места» должен прятаться, а состояние поиска живёт в `CityView`. Заодно `CityView` получает полный массив площадок, необходимый для поиска по ним.

**Files:**
- Modify: `web/components/CityView.tsx`
- Modify: `web/app/perm/page.tsx:21-36`
- Modify: `web/app/sochi/page.tsx:21-36`

**Interfaces:**
- Produces: `CityViewProps` получает новое обязательное поле `venues: VenueItem[]`

- [ ] **Шаг 1: Расширить пропсы CityView**

В `web/components/CityView.tsx` заменить импорт типов и интерфейс:

```tsx
import type { City, EventItem, VenueItem } from "@/lib/types";
import { VenuesSection } from "./VenuesSection";

interface CityViewProps {
  events: EventItem[];
  /** Все площадки города: восемь идут в секцию «Постоянные места», остальные участвуют в поиске. */
  venues: VenueItem[];
  city: City;
  /** Календарная дата "сегодня" в таймзоне города — из getCityToday(city), см. page.tsx. */
  today: string;
}

export function CityView({ events, venues, city, today }: CityViewProps) {
```

- [ ] **Шаг 2: Отрисовать секцию площадок внутри CityView**

В `web/components/CityView.tsx`, между блоком секций дня и SEO-блоком (после закрывающего `)}` условного рендера, перед `<section className="pt-8 border-t border-border">`):

```tsx
      {venues.length > 0 && (
        <VenuesSection venues={venues.slice(0, 8)} city={city} totalCount={venues.length} />
      )}
```

- [ ] **Шаг 3: Убрать VenuesSection из страницы Перми**

В `web/app/perm/page.tsx` удалить импорт `VenuesSection` и заменить тело `return`:

```tsx
  return (
    <>
      <Header city="perm" />
      <CityView events={events} venues={venues} city="perm" today={today} />
      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша · 2026
      </footer>
    </>
  );
```

- [ ] **Шаг 4: То же для страницы Сочи**

В `web/app/sochi/page.tsx` удалить импорт `VenuesSection` и заменить тело `return` аналогично, подставив `"sochi"`.

- [ ] **Шаг 5: Проверить сборку и вид страницы**

```bash
cd web && npx tsc --noEmit && npm run lint
```

Затем запустить dev-сервер через preview-инструмент и убедиться: секция «Постоянные места» на `/perm/` осталась на месте, показывает 8 карточек и ссылку «Все площадки →». Отступы не поехали.

- [ ] **Шаг 6: Коммит**

```bash
git add web/components/CityView.tsx web/app/perm/page.tsx web/app/sochi/page.tsx
git commit -m "refactor(web): перенести секцию площадок внутрь CityView"
```

---

### Task 7: Оживить поле поиска в FilterBar

**Files:**
- Modify: `web/components/FilterBar.tsx`

**Interfaces:**
- Consumes: ничего нового
- Produces: `FilterBarProps` получает `query: string` и `onQueryChange: (value: string) => void`

- [ ] **Шаг 1: Расширить пропсы**

В `web/components/FilterBar.tsx`:

```tsx
interface FilterBarProps {
  filters: Filters;
  onChange: (next: Filters) => void;
  availableTypes: readonly EventType[];
  query: string;
  onQueryChange: (value: string) => void;
}

export function FilterBar({ filters, onChange, availableTypes, query, onQueryChange }: FilterBarProps) {
```

- [ ] **Шаг 2: Подключить инпут и добавить кнопку очистки**

Заменить блок поля поиска (строки 49-57):

```tsx
      <div className="relative w-full md:w-[240px] md:flex-none">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[13px]">⌕</span>
        <input
          type="search"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onQueryChange("");
          }}
          placeholder="Название, площадка, организатор…"
          aria-label="Поиск по афише"
          className="w-full bg-bg border border-border rounded-full text-[13px] text-ink pl-8 pr-8 py-2 focus:outline-none focus:border-accent"
        />
        {query && (
          <button
            type="button"
            onClick={() => onQueryChange("")}
            aria-label="Очистить поиск"
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted text-[13px] hover:text-ink"
          >
            ✕
          </button>
        )}
      </div>
```

- [ ] **Шаг 3: Починить мобильную вёрстку**

Поиск становится главным элементом управления, и требовать ради него горизонтальный скролл нельзя. Четыре точечные правки классов:

Внешний контейнер (строка 48):

```tsx
    <div className="relative flex flex-col md:flex-row md:items-center gap-3 md:gap-[14px] p-3 bg-surface border border-border rounded-2xl md:overflow-x-auto">
```

Оба разделителя — добавить `hidden md:block`:

```tsx
      <div className="hidden md:block w-px self-stretch bg-border flex-shrink-0" />
```

Контейнер чипов типа (строка 60):

```tsx
      <div className="flex gap-2 flex-wrap md:flex-nowrap md:flex-none relative">
```

Кнопка «Ещё фильтры» (строка 127) — `ml-auto` только на десктопе:

```tsx
        className="md:ml-auto flex-none self-start md:self-auto text-[12.5px] font-semibold px-3.5 py-[7px] rounded-lg border border-border text-muted bg-bg whitespace-nowrap"
```

- [ ] **Шаг 4: Временно передать пропсы из CityView, чтобы проект собирался**

В `web/components/CityView.tsx` добавить состояние и прокинуть его (полноценная выдача — в Task 8):

```tsx
  const [query, setQuery] = useState("");
```

И в разметке:

```tsx
        <FilterBar
          filters={filters}
          onChange={setFilters}
          availableTypes={types}
          query={query}
          onQueryChange={setQuery}
        />
```

- [ ] **Шаг 5: Проверить типы и вид**

```bash
cd web && npx tsc --noEmit && npm run lint
```

На dev-сервере проверить при ширине 375px: поле занимает всю строку, чипы переносятся, горизонтального скролла нет. Раскрыть «Ещё N» и «Ещё фильтры» — выпадающие блоки открываются и не обрезаны. При ширине 1280px вид не изменился. Текст в поле печатается, ✕ появляется и очищает, Escape очищает.

- [ ] **Шаг 6: Коммит**

```bash
git add web/components/FilterBar.tsx web/components/CityView.tsx
git commit -m "feat(web): оживить поле поиска и починить мобильную вёрстку фильтров"
```

---

### Task 8: Выдача результатов

**Files:**
- Modify: `web/components/CityView.tsx`

**Interfaces:**
- Consumes: `buildEventDoc`, `buildVenueDoc`, `parseQuery`, `searchEvents`, `searchVenues` из `@/lib/search`
- Produces: ничего наружу

- [ ] **Шаг 1: Добавить вычисление результатов**

В `web/components/CityView.tsx` добавить импорты:

```tsx
import { buildEventDoc, buildVenueDoc, parseQuery, searchEvents, searchVenues } from "@/lib/search";
import { VenueCard } from "./VenueCard";
```

После существующих `useMemo`:

```tsx
  // Порог в 2 символа плюс проверка на осмысленность: запрос «куда сходить»
  // состоит из одних стоп-слов, терминов не даёт, и показывать по нему
  // «ничего не нашлось» неправильно — это обычный просмотр афиши.
  const queryTerms = useMemo(() => parseQuery(query), [query]);
  const searchActive = query.trim().length >= 2 && queryTerms.length > 0;

  const eventDocs = useMemo(() => events.map(buildEventDoc), [events]);
  const venueDocs = useMemo(() => venues.map(buildVenueDoc), [venues]);

  // Считаем два множества: hits — что нашёл поиск, visible — что осталось
  // после фильтров. Разница показывается подсказкой «скрыто фильтрами»,
  // иначе AND между поиском и фильтрами превращается в ловушку.
  const hits = useMemo(
    () => (searchActive ? searchEvents(eventDocs, query, today) : []),
    [searchActive, eventDocs, query, today],
  );
  const visible = useMemo(
    () => applyFilters(hits.map((h) => h.item), filters, today),
    [hits, filters, today],
  );
  const venueHits = useMemo(
    () => (searchActive ? searchVenues(venueDocs, query) : []),
    [searchActive, venueDocs, query],
  );

  const hiddenByFilters = hits.length - visible.length;
```

- [ ] **Шаг 2: Развести две ветки рендера**

Заменить блок с `totalFound === 0 ? ... : ...` на:

```tsx
      {searchActive ? (
        <SearchResults
          events={visible}
          venues={venueHits.map((h) => h.item)}
          query={query}
          hiddenByFilters={hiddenByFilters}
          onResetFilters={() => setFilters(DEFAULT_FILTERS)}
          onClearQuery={() => setQuery("")}
        />
      ) : totalFound === 0 ? (
        <EmptyState onReset={() => setFilters(DEFAULT_FILTERS)} />
      ) : (
        <>
          <DaySection title="Сегодня" date={today} events={groups.today} />
          <DaySection title="Завтра" date={tomorrow} events={groups.tomorrow} />
          <DaySection title="Дальше" events={later} />
        </>
      )}
```

Секцию площадок из Task 6 обернуть в `!searchActive`, чтобы на экране не было двух разных подборок мест:

```tsx
      {!searchActive && venues.length > 0 && (
        <VenuesSection venues={venues.slice(0, 8)} city={city} totalCount={venues.length} />
      )}
```

- [ ] **Шаг 3: Добавить компонент выдачи**

В конец `web/components/CityView.tsx`, рядом с `DaySection` и `EmptyState`:

```tsx
/**
 * Выдача поиска. Секции «Сегодня / Завтра / Дальше» при активном запросе
 * схлопываются в один список: иначе карточка с релевантностью 160 в «Дальше»
 * оказывается визуально ниже карточки с 30 в «Сегодня», и ранжирование теряется.
 */
function SearchResults({
  events,
  venues,
  query,
  hiddenByFilters,
  onResetFilters,
  onClearQuery,
}: {
  events: EventItem[];
  venues: VenueItem[];
  query: string;
  hiddenByFilters: number;
  onResetFilters: () => void;
  onClearQuery: () => void;
}) {
  if (events.length === 0 && venues.length === 0) {
    return (
      <div className="bg-surface border border-border rounded-xl p-10 text-center">
        <p className="text-lg font-semibold mb-2">По запросу «{query}» ничего не нашлось</p>
        <p className="text-sm text-muted mb-5">
          Проверьте раскладку и опечатки или попробуйте более общее слово — например,
          «концерт» вместо названия площадки.
        </p>
        <div className="flex gap-2 justify-center flex-wrap">
          <button
            type="button"
            onClick={onClearQuery}
            className="px-4 py-2 bg-accent text-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Очистить поиск
          </button>
          {hiddenByFilters > 0 && (
            <button
              type="button"
              onClick={onResetFilters}
              className="px-4 py-2 border border-border text-muted rounded-lg text-sm font-medium hover:text-ink transition-colors"
            >
              Сбросить фильтры
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      {events.length > 0 && (
        <section>
          <div className="flex items-baseline gap-3 mb-[18px]" aria-live="polite">
            <h2 className="text-[19px] font-extrabold m-0">Найдено</h2>
            <span className="text-[13px] text-muted">
              {events.length} {pluralEvents(events.length)}
            </span>
          </div>
          <div className="grid gap-5 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
            {events.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
          {hiddenByFilters > 0 && (
            <p className="mt-4 text-[13px] text-muted">
              Ещё {hiddenByFilters} {pluralEvents(hiddenByFilters)} скрыто фильтрами ·{" "}
              <button
                type="button"
                onClick={onResetFilters}
                className="text-accent hover:text-accent-hover font-medium"
              >
                Сбросить
              </button>
            </p>
          )}
        </section>
      )}

      {venues.length > 0 && (
        <section>
          <div className="flex items-baseline gap-3 mb-[18px]">
            <h2 className="text-[19px] font-extrabold m-0">Места</h2>
            <span className="text-[13px] text-muted">{venues.length}</span>
          </div>
          <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
            {venues.map((venue) => (
              <VenueCard key={venue.id} venue={venue} />
            ))}
          </div>
        </section>
      )}
    </>
  );
}
```

Добавить импорт `VenueCard`:

```tsx
import { VenueCard } from "./VenueCard";
```

Импорт `VenueItem` в списке типов уже добавлен в Task 6.

- [ ] **Шаг 4: Проверить типы и поведение**

```bash
cd web && npx tsc --noEmit && npm run lint && npm test
```

На dev-сервере прогнать чеклист запросов из раздела Verification.

- [ ] **Шаг 5: Коммит**

```bash
git add web/components/CityView.tsx
git commit -m "feat(web): ранжированная выдача поиска по событиям и площадкам"
```

---

### Task 9: Синхронизация запроса с URL

**Files:**
- Modify: `web/components/CityView.tsx`

- [ ] **Шаг 1: Добавить чтение и запись `?q=`**

В `web/components/CityView.tsx` расширить импорт React и добавить два эффекта после объявления состояния:

```tsx
import { useEffect, useMemo, useState } from "react";
```

```tsx
  // Статический HTML один на все query-строки, поэтому ?q= читается только
  // на клиенте. useSearchParams() из next/navigation не годится: он требует
  // <Suspense> и уводит страницу из чистого SSG.
  const [urlRead, setUrlRead] = useState(false);

  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("q");
    if (initial) setQuery(initial);
    setUrlRead(true);
  }, []);

  useEffect(() => {
    if (!urlRead) return; // не затирать ?q= до того, как он прочитан
    const id = setTimeout(() => {
      const url = new URL(window.location.href);
      const trimmed = query.trim();
      if (trimmed) url.searchParams.set("q", trimmed);
      else url.searchParams.delete("q");
      // replaceState, а не pushState: иначе «Назад» отматывает запрос по буквам.
      window.history.replaceState(null, "", url);
    }, 300);
    return () => clearTimeout(id);
  }, [query, urlRead]);
```

- [ ] **Шаг 2: Проверить**

```bash
cd web && npx tsc --noEmit && npm run lint
```

На dev-сервере: набрать «квиз» — через ~300 мс в адресной строке появляется `?q=квиз`. Обновить страницу — запрос восстановился, выдача та же. Очистить поле — `?q=` исчез. Нажать «Назад» — страница не отматывается по буквам.

Отдельно проверить мелькание: открыть `/perm/?q=опера` в новой вкладке и посмотреть на первый кадр. Ожидаемое поведение — возможен один кадр обычной сетки до переключения на результаты; `EmptyState` при этом не мелькает никогда, потому что до срабатывания эффекта запрос пуст.

Если мелькание заметно глазом, заменить первый `useEffect` на `useLayoutEffect` через изоморфный шим (React ругается на `useLayoutEffect` при SSR):

```tsx
const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;
```

- [ ] **Шаг 3: Коммит**

```bash
git add web/components/CityView.tsx
git commit -m "feat(web): синхронизировать поисковый запрос с ?q= в URL"
```

---

### Task 10: Документация

**Files:**
- Modify: `README.md`

- [ ] **Шаг 1: Исправить устаревшее описание Header**

Строка 1793 утверждает, что поле поиска живёт в шапке — его там нет с редизайна. Заменить пункт списка `Header.tsx` на:

```markdown
- Переключатель городов (подсвечивает активный)
```

- [ ] **Шаг 2: Описать поиск в разделе про фронтенд**

После блока `**lib/filters.ts**` (строка 1777) добавить:

```markdown
**`lib/search.ts`** — ранжированный клиентский поиск по событиям и площадкам:
- `normalize` / `tokenize` — нижний регистр, `ё→е` **до** фильтрации по диапазону
  (`ё` U+0451 лежит за границей `а-я`), любая пунктуация → пробел, склейка разрядов «1 000» → «1000»
- `tokensMatch` — морфология без стеммера: общий префикс с допуском в 2 символа хвоста,
  но не короче 3. Ловит «опера»/«оперы», где `startsWith` промахивается; заодно даёт typeahead с 3-го символа
- `buildEventDoc` — поля с весами: `title` 100, **`typeLabel` + синонимы 60**, `venueName` 50,
  `organizer` 30, `tags` 20, `description` 10. Поле типа обязательно: из 94 концертов Перми
  слово «концерт» есть в названии только у 28, из 22 вечеринок — у нуля
- `scoreDoc` — `max` по полям (не сумма), AND по терминам, фразовый бонус для многословных запросов
- `searchEvents` / `searchVenues` — бусты +15 за сегодня/завтра и +5 за картинку, сортировка по скору

**`lib/search-synonyms.ts`** — словари: `TYPE_SYNONYMS`, `VENUE_TYPE_SYNONYMS`,
`INTENT_SYNONYMS` (разворот «свидание» → тег «для пары»), `STOP_WORDS` (включая слова-обращения
«куда», «сходить» — без них запрос «куда сходить на квиз» даёт ноль результатов по AND).

**`lib/price.ts`** — `priceKind(event)` → `free` / `known` / `unknown`. В БД `price_max = 0`
означает и «бесплатно», и «цена неизвестна» (347 против 175 событий Перми), различить можно
только по строке `price_text`. Используется и поиском (синтетический токен «бесплатно»),
и фильтром цены (события с неизвестной ценой предикат пропускает, а не прячет).
```

- [ ] **Шаг 3: Обновить структуру репозитория**

В блоке `web/lib/` (строки 242-249) добавить строки:

```
│   │   ├── search.ts               — ранжированный клиентский поиск (ядро)
│   │   ├── search-synonyms.ts      — словари синонимов, намерений и стоп-слов
│   │   ├── price.ts                — priceKind: free / known / unknown
```

- [ ] **Шаг 4: Снять пункт 12 из роадмапа**

Заменить блок «**12. Функциональный поиск** 💡» (строки 2194-2197) на:

```markdown
**12. Функциональный поиск** ✅ / 💡  
Фаза 1 реализована: ранжированный клиентский поиск по событиям и площадкам
(`lib/search.ts`, веса по полям, морфология без стеммера, AND по терминам, `?q=` в URL).
Фаза 2 — разбор намерения без LLM (`«вечером с девушкой до 1000»` → ограничения + бусты по тегам) —
**заблокирована качеством данных по цене**: пока `price_max = 0` означает и «бесплатно»,
и «неизвестно», ограничение «до N рублей» либо не отсекает ничего, либо теряет четверть афиши.
Разблокируется пунктом 16.
```

- [ ] **Шаг 5: Добавить пункт про цену в раздел «Данные / схема»**

После пункта 15 добавить:

```markdown
**16. Разделить «бесплатно» и «цена неизвестна»** 📋  
`price_max = 0` сейчас означает две разные вещи: 347 событий Перми действительно бесплатны
(«Бесплатно», «Вход свободный»), а 175 — с неизвестной ценой («по билетам», «Уточняйте»).
Фронтенд различает их регекспом по `price_text` (`web/lib/price.ts`), но это заплатка:
каждый новый потребитель обязан выводить смысл заново из строки, которую пишет LLM.
Решение — колонка `price_unknown boolean` (или `NULL` вместо `0`), заполняемая парсером
тем же правилом. Блокирует price-intent в поиске (пункт 12).
```

- [ ] **Шаг 6: Коммит**

```bash
git add README.md
git commit -m "docs: описать подсистему поиска и зафиксировать неоднозначность цены"
```

---

## Verification

**Автоматическая:**

```bash
cd web && npm test && npx tsc --noEmit && npm run lint && npm run build
```

Ожидается: все тесты зелёные, типы чистые, сборка проходит. `npm run build` обязателен — `tsconfig.json` включает `**/*.ts`, поэтому тестовые файлы типизируются вместе с приложением.

**Ручная, на dev-сервере (`/perm/`).** Запросы из исходной постановки, каждый должен вернуть осмысленную выдачу:

| Запрос | Ожидание |
|---|---|
| `стендап` | стендапы, включая те, где слова нет в названии |
| `квиз` | ≥ 15 квизов (по типу, а не только по названию) |
| `квизы` | та же выдача, что и «квиз» — морфология |
| `театр` | спектакли **и** события в Театре-Театре |
| `Пермская опера` | события театра оперы и балета наверху — фразовый бонус |
| `бесплатно` | ≥ 300 событий, включая те, у которых нет тега «бесплатно» |
| `для детей` | детские события; «для» отброшено как стоп-слово |
| `свидание` | события с тегом «для пары» — разворот намерения |
| `боулинг` | секция «Места» с боулинг-клубами |
| `куда сходить` | обычные секции дня — запрос из одних стоп-слов |
| `сте` | стендапы — typeahead с третьего символа |
| `ффф` | «По запросу «ффф» ничего не нашлось» |

**Проверки интеграции:**
- Снять чип «Концерт», ввести «филармония» → под выдачей появляется «Ещё N скрыто фильтрами · Сбросить»; кнопка возвращает результаты.
- При активном поиске секция «Постоянные места» внизу страницы исчезает; при очистке — возвращается.
- `/perm/?q=опера` в новой вкладке: запрос восстановлен, `EmptyState` не мелькает.
- Ширина 375px: поле поиска на всю строку, горизонтального скролла нет, выпадающие блоки открываются.

**Калибровка.** Веса почти наверняка потребуют подкрутки после первого прогона по живым данным. Менять константы в шапке `search.ts`, проверять чеклистом выше. Тесты Task 4 написаны на порядок результатов, а не на абсолютные значения, поэтому переживают калибровку.

---

## Follow-up (вне объёма)

1. **Парсер: колонка `price_unknown`** — устойчивое решение проблемы, которую `lib/price.ts` лечит заплаткой. Разблокирует price-intent фазы 2. Пункт 16 роадмапа.
2. **Фаза 2 — разбор намерения без LLM.** `parseIntent(query)` → `{ textTokens, constraints: { priceMax, when }, boosts: { tags }, recognized }`. Ключевые решения уже приняты: цена и дата — жёсткие ограничения, теги — бусты +40 (жёсткий AND по тегам даёт 3 события на запрос «вечером с девушкой до 1000» против 219 при мягком); распознанные фрагменты вырезаются из строки **до** токенизации; распознанное показывается снимаемыми чипами.
3. **Метрика поисковых запросов** — самые ценные входные данные для фазы 2, но это выгрузка пользовательского ввода наружу. По умолчанию выключено; включать отдельным решением с явной пометкой про PII.
4. **Наблюдение, не трогали.** `overflow-x-auto` на контейнере `FilterBar` создаёт скролл-контекст по обеим осям, из-за чего выпадающие блоки «Ещё N» и «Ещё фильтры» подрезаются снизу на десктопе. Существует до этих правок; чинить отдельно.
5. **Поиск по всем городам сразу** и **подсветка совпадений в карточках** — сознательно вне объёма.
