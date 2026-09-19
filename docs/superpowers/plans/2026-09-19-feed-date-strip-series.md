# Лента дат и серии событий — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (выбран режим Native: задачи выполняются в этой сессии, в конце — одно ревью всей ветки). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Главная города (`/perm`, `/sochi`) показывает ленту дат вместо «Сегодня / Завтра / Дальше», схлопывает повторы в одну карточку «ещё N дат», чинит чипы типов, хранит состояние в URL; страница события показывает «Другие даты» и возвращает к тем же фильтрам.

**Architecture:** Вся логика — чистые функции в `web/lib/` (серии, фильтры, лента дат, URL), покрытые Vitest. Компоненты только собирают их. Серии группируются на клиенте по ключу «нормализованное название | площадка» (подход A). Схема БД и парсер не меняются.

**Tech Stack:** Next.js 16 (App Router, SSG), React, Tailwind v4, Vitest 4. Supabase — только чтение при сборке.

**Spec:** `docs/superpowers/specs/2026-09-19-feed-date-strip-series-design.md` (создаётся в задаче 0 из согласованных в чате разделов 1–5).

## Context

UX-разбор `/perm` 2026-09-19 показал:
- клик по чипу «Концерт» **убирает** концерты: по умолчанию выбраны все типы (`DEFAULT_FILTERS.types = new Set(ALL_TYPES)`);
- 423 карточки на одной странице, из них одинаковые повторы (выставка «Пермская деревянная скульптура» — 13 раз);
- фильтры теряются при возврате со страницы события;
- дорогие события (>5000 ₽) молча скрыты фильтром цены.

Пользователь выбрал объём P0+P1 без мобильной вёрстки (она записана в README, пункт роадмапа 19) и подход A — группировку на фронте.

Замер: одно схлопывание серий даёт −19% (423 → 341). Главное сокращение даёт лента дат: по умолчанию показывается один день (20–60 серий).

## Global Constraints

- `web/AGENTS.md`: перед Next-специфичным кодом читать `web/node_modules/next/dist/docs/`. Нативный `history.replaceState` интегрирован с роутером — `01-app/01-getting-started/04-linking-and-navigating.md`, раздел «Native History API».
- Новых зависимостей нет. Тесты — только Vitest по чистым функциям (`lib/*.test.ts`, окружение node, jsdom нет). UI проверяется вручную в превью, тестовый фреймворк для компонентов не вводим.
- Даты — строки `YYYY-MM-DD`, арифметика только через `lib/dateUtil.ts` (UTC-компоненты). «Сейчас» превращается в дату только в `getCityToday`.
- Параметры URL: `date`, `type`, `pmin`, `pmax`, `q`. Значение по умолчанию в URL не пишется.
- Ключ `sessionStorage`: `afisha:list:{city}`. Каждое обращение — в `try/catch`.
- Тексты: «ещё N дат · до 30 сентября», «Все даты», «Поиск по всем датам», «Другие даты», «эта дата», «← Все события».
- Работа в ветке `feat/feed-date-strip`. Перед каждым `git add/commit` отдельным шагом `git branch --show-current`. `.gitignore` (правка пользователя) не стейджить. Сообщение коммита заканчивается строкой `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- После задачи 3 и до задачи 6b `npm run build` не собирается: `CityView` и `FilterBar` ссылаются на удалённые `applyFilters` / `when`. Это ожидаемо. До задачи 6b ветку не пушить.
- README правится в той же задаче, что и описываемый код (6b — главная, 7 — страница события). Ни один коммит после 6b не оставляет документ, описывающий удалённый слой.
- Вне объёма: мобильная вёрстка (README п. 19), группы типов и сценарии (P2), CTA / карта / календарь / «похожие» (P3), парсер.

## Review Focus

1. Ссылка с `date` в прошлом, несуществующей датой (`2026-02-30`) или мусором в `type` → страница открывается в состоянии по умолчанию, не падает. Тесты — задача 5.
2. Сегодня воскресенье → «Выходные» = только сегодня (сейчас функция захватывает следующую субботу). Тест — задача 3.
3. Два сеанса серии в один день → одна карточка, «ещё N дат» считает **различные** даты. Тест — задача 2.
4. У серии дешёвый будний и дорогой выходной сеанс, выставлен фильтр цены → показывается подходящий сеанс, а не первый по дате. Тест — задача 3 (`visibleSeries`).
5. Устаревшая сборка (`today` из пропа вчерашний) → прошедшие дни исчезают из ленты. Задача 6b: вживую не проверяется, покрыто тестом `getCityToday` (задача 1) и чтением кода.
6. Недоступный `sessionStorage` (приватный режим) → «← Все события» ведёт на `/{city}` без фильтров, страница не падает. Задача 7: проверка по коду (`try/catch` вокруг каждого обращения).
7. Клик по фильтру и сразу переход в событие → «← Все события» возвращает **последнее** состояние. Задача 6b: `sessionStorage` и URL после кликов по фильтрам пишутся синхронно, задержка — только для набора в поиске.

---

### Task 0: Ветка и документы

**Files:**
- Create: `docs/superpowers/specs/2026-09-19-feed-date-strip-series-design.md`
- Create: `docs/superpowers/plans/2026-09-19-feed-date-strip-series.md` (копия этого плана)
- Modify: `README.md` (пункт 19 уже добавлен в рабочей копии)

- [ ] **Step 1:** `git switch -c feat/feed-date-strip` (переключение ветки одобрено вместе с планом).
- [ ] **Step 2:** Записать спеку. Содержание — согласованные в чате разделы 1–5: модель серий, лента дат и фильтры, URL, «Другие даты», тестирование, плюс «Готово / вне объёма». В разделе 2 уточнить: независимость «Сегодня/Завтра» от «Когда» была задокументированным решением ([README.md:1925](README.md)), а не ошибкой. Лента дат заменяет эту схему целиком.
- [ ] **Step 3:** Скопировать этот план в `docs/superpowers/plans/2026-09-19-feed-date-strip-series.md`.
- [ ] **Step 4:** `git branch --show-current` → ожидается `feat/feed-date-strip`.
- [ ] **Step 5:** Commit.

```bash
git add README.md docs/superpowers/specs/2026-09-19-feed-date-strip-series-design.md docs/superpowers/plans/2026-09-19-feed-date-strip-series.md
git commit -m "docs: спека и план ленты дат и серий; мобильная вёрстка — в роадмап"
```

---

### Task 1: `getCityToday` и форматтеры дней в `dateUtil`

`getCityToday` нужен клиенту (пересчёт «сегодня» после монтирования). Импорт из `lib/events.ts` затянул бы в бандл Supabase-клиент, поэтому функция переезжает в `dateUtil.ts`. В `events.ts` остаётся ре-экспорт — шесть существующих импортов не трогаем.

**Files:**
- Modify: `web/lib/dateUtil.ts`
- Modify: `web/lib/events.ts:71-87` (перенос `CITY_TIMEZONES` + `getCityToday`)
- Test: `web/lib/dateUtil.test.ts` (новый)

**Interfaces:**
- Produces: `getCityToday(city: City): string`, `weekdayUTC(ymd: string): number` (0 = Вс), `formatStripDay(ymd): string` («Пн 21»), `formatWeekdayDayMonth(ymd): string` («Сб, 19 сентября»).

- [ ] **Step 1: Failing test** — `web/lib/dateUtil.test.ts`:

```ts
import { afterEach, describe, it, expect, vi } from "vitest";
import { formatStripDay, formatWeekdayDayMonth, getCityToday, weekdayUTC } from "./dateUtil";

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
```

- [ ] **Step 2:** `cd web && npx vitest run lib/dateUtil.test.ts` → FAIL (нет экспортов).
- [ ] **Step 3: Implementation** — в конец `web/lib/dateUtil.ts`:

```ts
import type { City } from "./types";

/** IANA-таймзона города — «сегодня» считается по местному времени, не по UTC сервера сборки. */
const CITY_TIMEZONES: Record<City, string> = {
  perm: "Asia/Yekaterinburg", // UTC+5
  sochi: "Europe/Moscow", // UTC+3
};

/** «Сегодня» в таймзоне города — единственное место в кодовой базе, где текущий момент превращается в календарную дату. */
export function getCityToday(city: City): string {
  const timezone = CITY_TIMEZONES[city] ?? "Europe/Moscow";
  // en-CA даёт YYYY-MM-DD; timeZone делает дату местной (билд идёт в 21:00 UTC).
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

const WEEKDAYS_SHORT = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

/** День недели календарной строки: 0 — воскресенье, 6 — суббота. */
export function weekdayUTC(ymd: string): number {
  return new Date(`${ymd}T00:00:00Z`).getUTCDay();
}

/** "Пн 21" — подпись дня в ленте дат. */
export function formatStripDay(ymd: string): string {
  return `${WEEKDAYS_SHORT[weekdayUTC(ymd)]} ${Number(ymd.slice(8))}`;
}

/** "Сб, 19 сентября" — заголовок дня в выдаче и в «Других датах». */
export function formatWeekdayDayMonth(ymd: string): string {
  return `${WEEKDAYS_SHORT[weekdayUTC(ymd)]}, ${formatDayMonth(ymd)}`;
}
```

`import type` поднять в начало файла, к остальным импортам (в файле их сейчас нет — просто первой строкой после шапки-комментария). В `web/lib/events.ts` удалить строки 71–87 (`CITY_TIMEZONES`, `getCityToday`) и добавить после импортов:

```ts
export { getCityToday } from "./dateUtil";
```

- [ ] **Step 4:** `npx vitest run` → все тесты PASS. `npx tsc --noEmit -p .` → без ошибок (сборка на этом шаге ещё цела).
- [ ] **Step 5:** `git branch --show-current` → `feat/feed-date-strip`. Commit:

```bash
git add web/lib/dateUtil.ts web/lib/dateUtil.test.ts web/lib/events.ts
git commit -m "refactor(web): getCityToday в dateUtil, форматтеры дня недели"
```

---

### Task 2: Модель серий `lib/series.ts`

**Files:**
- Create: `web/lib/series.ts`
- Test: `web/lib/series.test.ts`

**Interfaces:**
- Consumes: `normalize(s: string): string` из `web/lib/search.ts:16` (переиспользуем, своей нормализации не пишем).
- Produces:
  - `interface EventSeries { key: string; events: EventItem[] }`
  - `seriesKey(e: Pick<EventItem, "title" | "venueName">): string`
  - `compareByDateTime(a: EventItem, b: EventItem): number`
  - `groupSeries(events: EventItem[]): EventSeries[]` — порядок серий = порядок первого появления ключа во входе; события внутри отсортированы `compareByDateTime`
  - `otherDates(series: EventSeries, shown: EventItem): { count: number; lastDate: string } | null`
  - `groupByDate<T>(items: T[], dateOf: (item: T) => string): { date: string; items: T[] }[]` — группирует **подряд идущие**, вход должен быть отсортирован по дате

- [ ] **Step 1: Failing test** — `web/lib/series.test.ts`:

```ts
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
```

- [ ] **Step 2:** `npx vitest run lib/series.test.ts` → FAIL (модуля нет).
- [ ] **Step 3: Implementation** — `web/lib/series.ts`:

```ts
/**
 * Серии событий: одно и то же событие (выставка, регулярная экскурсия, цирк
 * на гастролях) лежит в БД отдельной строкой на каждую дату. Лента показывает
 * серию одной карточкой с пометкой «ещё N дат».
 *
 * Ключ консервативный — название + площадка. «Пермская галерея» и «Пермская
 * художественная галерея» не склеиваются: лишняя карточка безобиднее, чем
 * слияние разных событий (тот же выбор, что в fuzzy-дедупе парсера).
 */

import type { EventItem } from "./types";
import { normalize } from "./search";

export interface EventSeries {
  key: string;
  /** Все даты серии по возрастанию даты и времени начала. */
  events: EventItem[];
}

/** Возрастные метки «6+», «(12+)»: один спектакль приходит из разных источников с меткой и без. */
const AGE_MARK_RE = /\(?\b\d{1,2}\+\)?/g;

export function seriesKey(e: Pick<EventItem, "title" | "venueName">): string {
  return `${normalize(e.title.replace(AGE_MARK_RE, " "))}|${normalize(e.venueName)}`;
}

/** По дате, затем по времени начала; событие без времени — в конец своего дня. */
export function compareByDateTime(a: EventItem, b: EventItem): number {
  if (a.date !== b.date) return a.date < b.date ? -1 : 1;
  const ta = a.timeStart ?? "99:99";
  const tb = b.timeStart ?? "99:99";
  return ta < tb ? -1 : ta > tb ? 1 : 0;
}

/** Серии в порядке первого появления во входе — для поиска это порядок релевантности. */
export function groupSeries(events: EventItem[]): EventSeries[] {
  const byKey = new Map<string, EventSeries>();
  for (const event of events) {
    const key = seriesKey(event);
    const existing = byKey.get(key);
    if (existing) existing.events.push(event);
    else byKey.set(key, { key, events: [event] });
  }
  const result = [...byKey.values()];
  for (const series of result) series.events.sort(compareByDateTime);
  return result;
}

/** Сколько ещё различных дат у серии, кроме показанной, и до какой даты она идёт. */
export function otherDates(
  series: EventSeries,
  shown: EventItem,
): { count: number; lastDate: string } | null {
  const dates = new Set(series.events.map((e) => e.date));
  dates.delete(shown.date);
  if (dates.size === 0) return null;
  return { count: dates.size, lastDate: series.events[series.events.length - 1].date };
}

/** Группы подряд идущих элементов с одной датой; вход должен быть отсортирован по дате. */
export function groupByDate<T>(
  items: T[],
  dateOf: (item: T) => string,
): { date: string; items: T[] }[] {
  const groups: { date: string; items: T[] }[] = [];
  for (const item of items) {
    const date = dateOf(item);
    const last = groups[groups.length - 1];
    if (last && last.date === date) last.items.push(item);
    else groups.push({ date, items: [item] });
  }
  return groups;
}
```

- [ ] **Step 4:** `npx vitest run` → PASS. Если тест «Лекция 2» падает (`\b` перед цифрой в конце строки) — проверить, что regex требует `+`: `\d{1,2}\+`.
- [ ] **Step 5:** `git branch --show-current`, затем:

```bash
git add web/lib/series.ts web/lib/series.test.ts
git commit -m "feat(web): серии событий — группировка повторов по названию и площадке"
```

---

### Task 3: Новая модель фильтров `lib/filters.ts`

`when` и `applyFilters` заменяются на `date` + `matchesEvent` / `inDateSel` / `visibleSeries`. Пустой набор типов = все. `priceMax: null` = без потолка. Исправляется «Выходные» в воскресенье.

**Files:**
- Modify: `web/lib/filters.ts` (типы `Filters`, `DEFAULT_FILTERS`, `getWeekendDates`; `applyFilters` и `WhenFilter` удаляются)
- Test: `web/lib/filters.test.ts` (переписать)

**Interfaces:**
- Consumes: `EventSeries` (Task 2), `weekdayUTC`, `addDaysUTC` (Task 1).
- Produces:
  - `type DateSel = "today" | "tomorrow" | "weekend" | "all" | (string & {})` — последнее означает `YYYY-MM-DD`
  - `interface Filters { date: DateSel | null; types: ReadonlySet<EventType>; priceMin: number; priceMax: number | null }`
  - `DEFAULT_FILTERS = { date: null, types: new Set(), priceMin: 0, priceMax: null }`
  - `matchesEvent(event: EventItem, filters: Filters): boolean`
  - `inDateSel(date: string, sel: DateSel, today: string): boolean`
  - `interface SeriesView { series: EventSeries; shown: EventItem }`
  - `visibleSeries(series: EventSeries[], filters: Filters, sel: DateSel, today: string): SeriesView[]`
  - Без изменений: `ALL_TYPES`, `availableTypes`, `typesByFrequency`.

- [ ] **Step 1: Failing test** — заменить содержимое `web/lib/filters.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { DEFAULT_FILTERS, inDateSel, matchesEvent, visibleSeries } from "./filters";
import { groupSeries } from "./series";
import type { EventItem, EventType } from "./types";

const mk = (over: Partial<EventItem>): EventItem => ({
  id: `perm-${over.slug ?? "x"}`,
  city: "perm",
  slug: "x",
  title: "Событие",
  type: "concert",
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

describe("matchesEvent — тип", () => {
  it("пустой набор типов пропускает всё", () => {
    expect(matchesEvent(mk({ type: "theater" }), DEFAULT_FILTERS)).toBe(true);
  });

  it("выбранный тип оставляет только его (регрессия: клик по чипу убирал тип)", () => {
    const onlyConcerts = { ...DEFAULT_FILTERS, types: new Set<EventType>(["concert"]) };
    expect(matchesEvent(mk({ type: "concert" }), onlyConcerts)).toBe(true);
    expect(matchesEvent(mk({ type: "theater" }), onlyConcerts)).toBe(false);
  });
});

describe("matchesEvent — цена", () => {
  const narrow = { ...DEFAULT_FILTERS, priceMin: 500, priceMax: 5000 };

  it("показывает событие с неизвестной ценой даже при нижней границе", () => {
    expect(matchesEvent(mk({ priceText: "по билетам" }), narrow)).toBe(true);
  });

  it("прячет бесплатное событие при нижней границе", () => {
    expect(matchesEvent(mk({ priceText: "Бесплатно" }), narrow)).toBe(false);
  });

  it("оставляет обычную фильтрацию для событий с известной ценой", () => {
    const cheap = mk({ priceMin: 100, priceMax: 200, priceText: "200 ₽" });
    expect(matchesEvent(cheap, narrow)).toBe(false);
    expect(matchesEvent(cheap, DEFAULT_FILTERS)).toBe(true);
  });

  it("по умолчанию верхней границы нет (раньше молча прятало всё дороже 5000 ₽)", () => {
    const pricey = mk({ priceMin: 7000, priceMax: 12000, priceText: "от 7000 ₽" });
    expect(matchesEvent(pricey, DEFAULT_FILTERS)).toBe(true);
  });
});

describe("inDateSel", () => {
  const TUE = "2026-09-15";
  const SAT = "2026-09-19";
  const SUN = "2026-09-20";

  it("today / tomorrow / конкретный день / all", () => {
    expect(inDateSel(TUE, "today", TUE)).toBe(true);
    expect(inDateSel("2026-09-16", "tomorrow", TUE)).toBe(true);
    expect(inDateSel("2026-09-16", "today", TUE)).toBe(false);
    expect(inDateSel("2026-09-22", "2026-09-22", TUE)).toBe(true);
    expect(inDateSel("2026-10-30", "all", TUE)).toBe(true);
  });

  it("во вторник выходные — ближайшие суббота и воскресенье", () => {
    expect(inDateSel("2026-09-19", "weekend", TUE)).toBe(true);
    expect(inDateSel("2026-09-20", "weekend", TUE)).toBe(true);
    expect(inDateSel(TUE, "weekend", TUE)).toBe(false);
    expect(inDateSel("2026-09-21", "weekend", TUE)).toBe(false);
  });

  it("в субботу выходные — сегодня и завтра", () => {
    expect(inDateSel(SAT, "weekend", SAT)).toBe(true);
    expect(inDateSel(SUN, "weekend", SAT)).toBe(true);
  });

  it("в воскресенье выходные — только сегодня, не следующая суббота", () => {
    expect(inDateSel(SUN, "weekend", SUN)).toBe(true);
    expect(inDateSel("2026-09-26", "weekend", SUN)).toBe(false);
  });
});

describe("visibleSeries", () => {
  const series = groupSeries([
    mk({ slug: "sun-free", date: "2026-09-20", priceText: "Бесплатно" }),
    mk({ slug: "mon-paid", date: "2026-09-21", priceMin: 1000, priceMax: 1000, priceText: "1000 ₽" }),
  ]);

  it("показывает первый сеанс в окне дат", () => {
    const [view] = visibleSeries(series, DEFAULT_FILTERS, "all", "2026-09-19");
    expect(view.shown.slug).toBe("sun-free");
  });

  it("показывает сеанс, прошедший фильтр цены, а не просто первый по дате", () => {
    const paid = { ...DEFAULT_FILTERS, priceMin: 500 };
    const views = visibleSeries(series, paid, "all", "2026-09-19");
    expect(views.map((v) => v.shown.slug)).toEqual(["mon-paid"]);
  });

  it("серия не видна, если ни один сеанс не попал в окно и фильтры", () => {
    const paid = { ...DEFAULT_FILTERS, priceMin: 500 };
    expect(visibleSeries(series, paid, "2026-09-20", "2026-09-19")).toEqual([]);
  });
});
```

- [ ] **Step 2:** `npx vitest run lib/filters.test.ts` → FAIL (нет `matchesEvent` / `inDateSel` / `visibleSeries`).
- [ ] **Step 3: Implementation** — в `web/lib/filters.ts`:
  - обновить шапку-комментарий: фильтрация серий, SSR рендерит `DEFAULT_FILTERS`;
  - удалить `WhenFilter`, старые `Filters` / `DEFAULT_FILTERS`, `applyFilters`;
  - `ALL_TYPES`, `availableTypes`, `typesByFrequency` не трогать;
  - заменить импорты и добавить новые определения:

```ts
import type { EventItem, EventType } from "./types";
import type { EventSeries } from "./series";
import { addDaysUTC, weekdayUTC } from "./dateUtil";
import { priceKind } from "./price";

/** Выбор в ленте дат; кроме именованных — конкретный день `YYYY-MM-DD`. */
export type DateSel = "today" | "tomorrow" | "weekend" | "all" | (string & {});

export interface Filters {
  /** null — «по умолчанию»: сегодня, а если сегодня пусто — ближайший день с событиями. В URL не пишется. */
  date: DateSel | null;
  /** Пустой набор — все типы. */
  types: ReadonlySet<EventType>;
  priceMin: number;
  /** null — без верхней границы. */
  priceMax: number | null;
}

export const DEFAULT_FILTERS: Filters = {
  date: null,
  types: new Set(),
  priceMin: 0,
  priceMax: null,
};

/** Тип и цена — всё, что не про дату. */
export function matchesEvent(event: EventItem, filters: Filters): boolean {
  if (filters.types.size > 0 && !filters.types.has(event.type)) return false;

  // Событие с неизвестной ценой («по билетам», «Уточняйте») предикат
  // пропускает: в БД такая цена неотличима от нуля, и прятать карточку
  // из-за пробела в данных хуже, чем показать её. Подробнее — lib/price.ts.
  if (priceKind(event) !== "unknown") {
    if (event.priceMax < filters.priceMin) return false;
    if (filters.priceMax !== null && event.priceMin > filters.priceMax) return false;
  }
  return true;
}

/**
 * Даты «этих выходных»: ближайшие Сб и Вс, включая сегодня. В воскресенье это
 * только сегодня — следующая суббота относится уже к другим выходным.
 */
function getWeekendDates(today: string): Set<string> {
  const result = new Set<string>();
  for (let i = 0; i < 7; i++) {
    const ymd = addDaysUTC(today, i);
    const dow = weekdayUTC(ymd);
    if (dow === 6 || dow === 0) result.add(ymd);
    if (dow === 0) break;
  }
  return result;
}

export function inDateSel(date: string, sel: DateSel, today: string): boolean {
  switch (sel) {
    case "all":
      return true;
    case "today":
      return date === today;
    case "tomorrow":
      return date === addDaysUTC(today, 1);
    case "weekend":
      return getWeekendDates(today).has(date);
    default:
      return date === sel;
  }
}

export interface SeriesView {
  series: EventSeries;
  /** Сеанс, который показывает карточка: первый по дате среди прошедших фильтры и окно. */
  shown: EventItem;
}

export function visibleSeries(
  series: EventSeries[],
  filters: Filters,
  sel: DateSel,
  today: string,
): SeriesView[] {
  const views: SeriesView[] = [];
  for (const s of series) {
    const shown = s.events.find((e) => matchesEvent(e, filters) && inDateSel(e.date, sel, today));
    if (shown) views.push({ series: s, shown });
  }
  return views;
}
```

- [ ] **Step 4:** `npx vitest run` → PASS. `npx tsc --noEmit` **ожидаемо** падает в `components/CityView.tsx` и `components/FilterBar.tsx` — чинится в задаче 6.
- [ ] **Step 5:** `git branch --show-current`, затем:

```bash
git add web/lib/filters.ts web/lib/filters.test.ts
git commit -m "feat(web): фильтры по сериям — пустой выбор типов = все, цена без потолка, выходные в воскресенье"
```

---

### Task 4: Лента дат `lib/dateStrip.ts`

**Files:**
- Create: `web/lib/dateStrip.ts`
- Test: `web/lib/dateStrip.test.ts`

**Interfaces:**
- Consumes: `DateSel` (Task 3), `addDaysUTC`, `formatStripDay` (Task 1).
- Produces: `interface StripItem { sel: DateSel; label: string }`, `buildDateStrip(today: string): StripItem[]`, `firstNonEmptyDay(items: StripItem[], counts: ReadonlyMap<DateSel, number>): DateSel | null`.

- [ ] **Step 1: Failing test** — `web/lib/dateStrip.test.ts`:

```ts
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
```

- [ ] **Step 2:** `npx vitest run lib/dateStrip.test.ts` → FAIL.
- [ ] **Step 3: Implementation** — `web/lib/dateStrip.ts`:

```ts
/**
 * Лента дат над выдачей: Сегодня · Завтра · Выходные · отдельные дни · Все даты.
 * Дата — первое решение пользователя, поэтому она всегда на виду, а выдача
 * по умолчанию показывает один день, а не всю афишу на месяц.
 */

import type { DateSel } from "./filters";
import { addDaysUTC, formatStripDay } from "./dateUtil";

export interface StripItem {
  sel: DateSel;
  label: string;
}

/** Сколько дней вперёд показывать по отдельности, считая сегодня и завтра. */
const STRIP_DAYS = 14;

export function buildDateStrip(today: string): StripItem[] {
  const items: StripItem[] = [
    { sel: "today", label: "Сегодня" },
    { sel: "tomorrow", label: "Завтра" },
    { sel: "weekend", label: "Выходные" },
  ];
  for (let i = 2; i < STRIP_DAYS; i++) {
    const ymd = addDaysUTC(today, i);
    items.push({ sel: ymd, label: formatStripDay(ymd) });
  }
  items.push({ sel: "all", label: "Все даты" });
  return items;
}

/** Первый отдельный день ленты, где есть события; «Выходные» и «Все даты» не в счёт. */
export function firstNonEmptyDay(
  items: StripItem[],
  counts: ReadonlyMap<DateSel, number>,
): DateSel | null {
  for (const item of items) {
    if (item.sel === "weekend" || item.sel === "all") continue;
    if ((counts.get(item.sel) ?? 0) > 0) return item.sel;
  }
  return null;
}
```

- [ ] **Step 4:** `npx vitest run` → PASS.
- [ ] **Step 5:** `git branch --show-current`, затем:

```bash
git add web/lib/dateStrip.ts web/lib/dateStrip.test.ts
git commit -m "feat(web): лента дат — пункты и ближайший непустой день"
```

---

### Task 5: Состояние в URL `lib/urlState.ts`

**Files:**
- Create: `web/lib/urlState.ts`
- Test: `web/lib/urlState.test.ts`

**Interfaces:**
- Consumes: `ALL_TYPES`, `DEFAULT_FILTERS`, `DateSel`, `Filters` (Task 3), `addDaysUTC` (Task 1).
- Produces: `parseState(search: string, today: string): { filters: Filters; query: string }`, `serializeState(filters: Filters, query: string): string` (`""` или `"?…"`), `listStateKey(city: City): string`.

- [ ] **Step 1: Failing test** — `web/lib/urlState.test.ts`:

```ts
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
```

- [ ] **Step 2:** `npx vitest run lib/urlState.test.ts` → FAIL.
- [ ] **Step 3: Implementation** — `web/lib/urlState.ts`:

```ts
/**
 * Состояние главной города в URL: ?date=&type=&pmin=&pmax=&q=.
 * Нужно, чтобы подборкой можно было поделиться и чтобы возврат со страницы
 * события не сбрасывал фильтры. Значения по умолчанию в URL не пишутся.
 */

import type { City, EventType } from "./types";
import { ALL_TYPES, DEFAULT_FILTERS, type DateSel, type Filters } from "./filters";
import { addDaysUTC } from "./dateUtil";

const NAMED_DATES: readonly string[] = ["today", "tomorrow", "weekend", "all"];
const YMD_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Реальная календарная дата: Date молча переносит 30 февраля на 2 марта, ловим сверкой. */
function isRealYmd(s: string): boolean {
  return YMD_RE.test(s) && !Number.isNaN(Date.parse(`${s}T00:00:00Z`)) && addDaysUTC(s, 0) === s;
}

function parseDate(raw: string | null, today: string): DateSel | null {
  if (!raw) return null;
  if (NAMED_DATES.includes(raw)) return raw;
  // День из прошлого в старой ссылке уже не показать — открываем умолчание.
  if (isRealYmd(raw) && raw >= today) return raw;
  return null;
}

function parseNonNegInt(raw: string | null): number | null {
  if (raw === null || !/^\d+$/.test(raw)) return null;
  return Number(raw);
}

export function parseState(search: string, today: string): { filters: Filters; query: string } {
  const params = new URLSearchParams(search);
  const types = new Set(
    (params.get("type") ?? "")
      .split(",")
      .filter((t): t is EventType => (ALL_TYPES as readonly string[]).includes(t)),
  );
  return {
    filters: {
      date: parseDate(params.get("date"), today),
      types,
      priceMin: parseNonNegInt(params.get("pmin")) ?? DEFAULT_FILTERS.priceMin,
      priceMax: parseNonNegInt(params.get("pmax")),
    },
    query: params.get("q") ?? "",
  };
}

export function serializeState(filters: Filters, query: string): string {
  const params = new URLSearchParams();
  const q = query.trim();
  if (q) params.set("q", q);
  if (filters.date !== null) params.set("date", filters.date);
  if (filters.types.size > 0) {
    params.set("type", ALL_TYPES.filter((t) => filters.types.has(t)).join(","));
  }
  if (filters.priceMin > 0) params.set("pmin", String(filters.priceMin));
  if (filters.priceMax !== null) params.set("pmax", String(filters.priceMax));
  const s = params.toString();
  return s ? `?${s}` : "";
}

/** Ключ sessionStorage, где главная оставляет свою строку запроса для ссылки «← Все события». */
export function listStateKey(city: City): string {
  return `afisha:list:${city}`;
}
```

- [ ] **Step 4:** `npx vitest run` → PASS.
- [ ] **Step 5:** `git branch --show-current`, затем:

```bash
git add web/lib/urlState.ts web/lib/urlState.test.ts
git commit -m "feat(web): состояние главной в URL — разбор и сборка строки запроса"
```

---

### Task 6a: Новые кирпичи главной — карточка серии и лента дат

Только добавление кода, ни к чему не подключено. Цель — сохранить прогресс отдельным коммитом внутри окна сломанной сборки и сузить ревью 6b.

**Files:**
- Create: `web/components/DateStrip.tsx`
- Modify: `web/components/EventCard.tsx` (проп `moreDates`, по умолчанию отсутствует — текущее поведение не меняется)

**Interfaces:**
- Consumes: `DateSel` (Task 3), `StripItem` (Task 4), `formatDayMonth` (есть).
- Produces: `DateStrip({ items, counts, selected, onSelect, searchActive })`, `EventCard({ event, moreDates? })`.

**Критерий выхода:** `npx vitest run` зелёный; `npx eslint components/DateStrip.tsx components/EventCard.tsx` без ошибок. В превью не проверяется — компоненты ещё не подключены.

- [ ] **Step 1: `EventCard`** — добавить проп и строку под датой:

```tsx
interface EventCardProps {
  event: EventItem;
  /** Серия: сколько ещё дат и до какой — из lib/series.otherDates. */
  moreDates?: { count: number; lastDate: string } | null;
}

function pluralDates(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return "дат";
  if (mod10 === 1) return "дата";
  if (mod10 >= 2 && mod10 <= 4) return "даты";
  return "дат";
}

export function EventCard({ event, moreDates }: EventCardProps) {
```

Строку `<span>📅 {formatDate(event)}</span>` заменить на:

```tsx
<span>
  📅 {formatDate(event)}
  {moreDates && (
    <small className="ml-1 text-[11px] text-accent-cyan">
      · ещё {moreDates.count} {pluralDates(moreDates.count)} до {formatDayMonth(moreDates.lastDate)}
    </small>
  )}
</span>
```

- [ ] **Step 2: `DateStrip.tsx`**:

```tsx
import type { DateSel } from "@/lib/filters";
import type { StripItem } from "@/lib/dateStrip";

interface DateStripProps {
  items: StripItem[];
  counts: ReadonlyMap<DateSel, number>;
  /** null — ничего не подсвечено (идёт поиск по всем датам). */
  selected: DateSel | null;
  onSelect: (sel: DateSel) => void;
  searchActive: boolean;
}

export function DateStrip({ items, counts, selected, onSelect, searchActive }: DateStripProps) {
  return (
    <div className="flex items-center gap-3 mt-3">
      <div className="flex gap-2 overflow-x-auto [scrollbar-width:none] pb-1">
        {items.map((item) => {
          const count = counts.get(item.sel) ?? 0;
          const active = item.sel === selected;
          return (
            <button
              key={item.sel}
              type="button"
              aria-pressed={active}
              // Пустые дни остаются на месте, чтобы календарь не прыгал, но не нажимаются.
              disabled={count === 0 && !active}
              onClick={() => onSelect(item.sel)}
              className={`flex-none text-[12.5px] font-semibold px-3 py-[7px] rounded-lg border whitespace-nowrap transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                active ? "bg-accent border-transparent text-bg" : "bg-bg border-border text-muted"
              }`}
            >
              {item.label} <span className="opacity-70">{count}</span>
            </button>
          );
        })}
      </div>
      {searchActive && (
        <span className="flex-none text-[12.5px] text-muted whitespace-nowrap">Поиск по всем датам</span>
      )}
    </div>
  );
}
```

- [ ] **Step 3:** Проверки из критерия выхода, затем `git branch --show-current` и:

```bash
git add web/components/EventCard.tsx web/components/DateStrip.tsx
git commit -m "feat(web): карточка серии («ещё N дат») и компонент ленты дат"
```

---

### Task 6b: Главная — подключить ленту дат, серии, чипы, URL; восстановить сборку

**Files:**
- Modify: `web/components/CityView.tsx` (переписать логику состояния и выдачи)
- Modify: `web/components/FilterBar.tsx` (убрать «Когда» и «Район», «× Сбросить» у типов, цена без потолка, скрыть скроллбар)
- Delete: `web/lib/dayGroups.ts` (становится мусором после этой задачи)
- Modify: `README.md` — описания главной, ставшие неверными:
  - строки 246–247 и 261–263 («Структура репозитория»);
  - 1880–1889 (`lib/filters.ts`, `lib/dateUtil.ts`, `lib/dayGroups.ts`);
  - 1920–1934 (`CityView`, `FilterBar`, `EventCard`);
  - строка 132 (`lib/events.getCityToday` → `lib/dateUtil.getCityToday`, убрать `lib/dayGroups.ts`).

**Interfaces:**
- Consumes: всё из задач 1–6a.
- Produces: `CityView` пишет `sessionStorage[listStateKey(city)] = serializeState(...)` — это читает задача 7.

**Критерий выхода (обязателен до коммита):** `npx vitest run`, `npm run lint`, `npm run build` — все зелёные (сборка восстановлена). Ручные проверки шага 6 пройдены. Review Focus п. 5 и 7 — по коду.

- [ ] **Step 1: `FilterBar.tsx`**:
  - удалить `WhenFilter` из импорта, `WHEN_OPTIONS`, `setWhen` и блок сегментированного переключателя вместе с разделителем перед ним;
  - удалить блок «Район» с бейджем «скоро» (п. 14 роадмапа остаётся в README);
  - `setPrice` принимает `priceMax: number | null`;
  - поле максимальной цены:

```tsx
<input
  type="number"
  min={0}
  value={filters.priceMax ?? ""}
  placeholder="любая"
  onChange={(e) =>
    setPrice(
      filters.priceMin,
      e.target.value === "" ? null : Math.max(0, Number(e.target.value) || 0),
    )
  }
  className="w-[70px] px-2 py-1.5 bg-bg border border-border rounded-md text-[13px] text-ink"
/>
```

  - после кнопки «Ещё N» / поповера типов добавить сброс:

```tsx
{filters.types.size > 0 && (
  <button
    type="button"
    onClick={() => onChange({ ...filters, types: new Set() })}
    className="text-[12.5px] font-semibold px-2 py-[7px] text-muted hover:text-ink whitespace-nowrap"
  >
    × Сбросить
  </button>
)}
```

  - в `className` корневого `div` к `md:overflow-x-auto` добавить `[scrollbar-width:none]`.

  Логика `toggleType` не меняется: при пустом наборе по умолчанию клик как раз добавляет тип.

- [ ] **Step 2: `CityView.tsx`** — заменить импорты и тело компонента до `return` и сам `return`. `SearchResults` и `EmptyState` переписать под `SeriesView`. `pluralEvents` оставить.

```tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import type { City, EventItem, VenueItem } from "@/lib/types";
import { CITY_CONFIG } from "@/lib/types";
import {
  DEFAULT_FILTERS,
  typesByFrequency,
  visibleSeries,
  type DateSel,
  type Filters,
  type SeriesView,
} from "@/lib/filters";
import { compareByDateTime, groupByDate, groupSeries, otherDates } from "@/lib/series";
import { buildDateStrip, firstNonEmptyDay, type StripItem } from "@/lib/dateStrip";
import { listStateKey, parseState, serializeState } from "@/lib/urlState";
import { formatWeekdayDayMonth, getCityToday } from "@/lib/dateUtil";
import { FilterBar } from "./FilterBar";
import { DateStrip } from "./DateStrip";
import { EventCard } from "./EventCard";
import { VenuesSection } from "./VenuesSection";
import { VenueCard } from "./VenueCard";
import { buildEventDoc, buildVenueDoc, parseQuery, searchEvents, searchVenues } from "@/lib/search";

interface CityViewProps {
  events: EventItem[];
  /** Все площадки города: восемь идут в секцию «Постоянные места», остальные участвуют в поиске. */
  venues: VenueItem[];
  city: City;
  /** «Сегодня» на момент сборки (getCityToday). После монтирования пересчитывается — сборка могла не пройти. */
  today: string;
}

export function CityView({ events, venues, city, today: buildToday }: CityViewProps) {
  const [today, setToday] = useState(buildToday);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [query, setQuery] = useState("");
  // Статический HTML один на все query-строки, поэтому URL читается только
  // на клиенте. useSearchParams() из next/navigation не годится: он требует
  // <Suspense> и уводит страницу из чистого SSG.
  const [urlRead, setUrlRead] = useState(false);
  /** Выбор даты по умолчанию, зафиксированный при первом заходе; в URL не пишется. */
  const [autoDate, setAutoDate] = useState<DateSel | null>(null);

  /* eslint-disable react-hooks/set-state-in-effect -- единоразовое чтение часов и URL после монтирования, не подписка */
  useEffect(() => {
    // Сайт пересобирается раз в сутки; если сборка не прошла, today из пропа — вчерашний.
    const liveToday = getCityToday(city);
    const initial = parseState(window.location.search, liveToday);
    setToday(liveToday);
    setFilters(initial.filters);
    setQuery(initial.query);
    setUrlRead(true);
  }, [city]);
  /* eslint-enable react-hooks/set-state-in-effect */

  // Состояние сохраняется синхронно: клик по фильтру и сразу переход в событие
  // не должны терять последний клик. Откладывать на размонтирование нельзя —
  // к тому моменту роутер уже мог записать в историю URL страницы события.
  const writeState = (search: string) => {
    const url = new URL(window.location.href);
    url.search = search;
    // replaceState, а не pushState: иначе «Назад» отматывает каждый клик по фильтру.
    window.history.replaceState(null, "", url);
    try {
      sessionStorage.setItem(listStateKey(city), search);
    } catch {
      // Хранилище недоступно (приватный режим) — «← Все события» просто ведёт на главную.
    }
  };

  // Фильтры — дискретные клики, пишем сразу.
  useEffect(() => {
    if (!urlRead) return; // не затирать URL до того, как он прочитан
    writeState(serializeState(filters, query));
    // query здесь намеренно не в зависимостях: набор текста пишется ниже с задержкой.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, urlRead]);

  // Поиск — набор по буквам: задержка, чтобы не дёргать историю на каждый символ.
  // sessionStorage при этом отстаёт максимум на 300 мс только для текста запроса.
  useEffect(() => {
    if (!urlRead) return;
    const id = setTimeout(() => writeState(serializeState(filters, query)), 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, urlRead]);

  const liveEvents = useMemo(() => events.filter((e) => e.date >= today), [events, today]);
  const series = useMemo(() => groupSeries(liveEvents), [liveEvents]);
  const types = useMemo(() => typesByFrequency(liveEvents), [liveEvents]);
  const strip = useMemo(() => buildDateStrip(today), [today]);
  const counts = useMemo(
    () =>
      new Map<DateSel, number>(
        strip.map((item) => [item.sel, visibleSeries(series, filters, item.sel, today).length]),
      ),
    [strip, series, filters, today],
  );

  /* eslint-disable react-hooks/set-state-in-effect -- умолчание фиксируется один раз, иначе смена типа молча перескакивала бы на другой день */
  useEffect(() => {
    if (urlRead && autoDate === null) setAutoDate(firstNonEmptyDay(strip, counts) ?? "all");
  }, [urlRead, autoDate, strip, counts]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const selected: DateSel = filters.date ?? autoDate ?? "today";

  const days = useMemo(() => {
    const views = visibleSeries(series, filters, selected, today).sort((a, b) =>
      compareByDateTime(a.shown, b.shown),
    );
    return groupByDate(views, (v) => v.shown.date);
  }, [series, filters, selected, today]);

  // Порог в 2 символа плюс проверка на осмысленность: запрос «куда сходить»
  // состоит из одних стоп-слов, терминов не даёт, и показывать по нему
  // «ничего не нашлось» неправильно — это обычный просмотр афиши.
  const queryTerms = useMemo(() => parseQuery(query), [query]);
  const searchActive = query.trim().length >= 2 && queryTerms.length > 0;

  const eventDocs = useMemo(() => liveEvents.map(buildEventDoc), [liveEvents]);
  const venueDocs = useMemo(() => venues.map(buildVenueDoc), [venues]);

  // Попадания схлопываются в серии в порядке релевантности; дата поиск не сужает.
  // hitSeries — что нашёл поиск, searchViews — что осталось после фильтров;
  // разница показывается подсказкой «скрыто фильтрами».
  const hitSeries = useMemo(
    () => (searchActive ? groupSeries(searchEvents(eventDocs, query, today).map((h) => h.item)) : []),
    [searchActive, eventDocs, query, today],
  );
  const searchViews = useMemo(
    () => visibleSeries(hitSeries, filters, "all", today),
    [hitSeries, filters, today],
  );
  const venueHits = useMemo(
    () => (searchActive ? searchVenues(venueDocs, query) : []),
    [searchActive, venueDocs, query],
  );

  const totalCount = counts.get("all") ?? 0;
  const nearest = firstNonEmptyDay(strip, counts);
  const suggestion = nearest !== null && nearest !== selected ? strip.find((i) => i.sel === nearest) ?? null : null;
  const filtersChanged = filters.types.size > 0 || filters.priceMin > 0 || filters.priceMax !== null;
  const resetFilters = () => setFilters({ ...DEFAULT_FILTERS, date: filters.date });

  return (
    <div className="mx-auto max-w-[1440px] px-4 pt-6 pb-12 flex flex-col gap-8 flex-1 w-full">
      <div>
        <p className="text-[11.5px] font-bold uppercase tracking-[0.14em] text-accent-cyan mb-2">
          Куда сходить сегодня
        </p>
        <h1 className="text-[28px] sm:text-[40px] font-extrabold leading-tight tracking-tight mb-2">
          {CITY_CONFIG[city].heroPrefix} <span className="text-accent">{CITY_CONFIG[city].label}</span> ждёт
        </h1>
        <p className="text-sm text-muted mb-5">
          {totalCount} {pluralEvents(totalCount)} в афише
        </p>
        <FilterBar
          filters={filters}
          onChange={setFilters}
          availableTypes={types}
          query={query}
          onQueryChange={setQuery}
        />
        <DateStrip
          items={strip}
          counts={counts}
          selected={searchActive ? null : selected}
          onSelect={(sel) => {
            setQuery("");
            setFilters({ ...filters, date: sel });
          }}
          searchActive={searchActive}
        />
      </div>

      {searchActive ? (
        <SearchResults
          views={searchViews}
          venues={venueHits.map((h) => h.item)}
          query={query}
          hiddenByFilters={hitSeries.length - searchViews.length}
          onResetFilters={resetFilters}
          onClearQuery={() => setQuery("")}
        />
      ) : days.length === 0 ? (
        <EmptyState
          suggestion={suggestion}
          suggestionCount={suggestion ? counts.get(suggestion.sel) ?? 0 : 0}
          onPick={(sel) => setFilters({ ...filters, date: sel })}
          showReset={filtersChanged}
          onReset={resetFilters}
        />
      ) : (
        days.map((day) => (
          <DaySection key={day.date} date={day.date} views={day.items} />
        ))
      )}

      {!searchActive && venues.length > 0 && (
        <VenuesSection venues={venues.slice(0, 8)} city={city} totalCount={venues.length} />
      )}

      <section className="pt-8 border-t border-border">
        <h2 className="text-lg font-semibold mb-2 text-ink">
          Досуг в {CITY_CONFIG[city].label} — всё в одном месте
        </h2>
        <p className="text-sm text-muted leading-relaxed max-w-3xl">
          {CITY_CONFIG[city].description}
        </p>
      </section>
    </div>
  );
}

function SeriesGrid({ views }: { views: SeriesView[] }) {
  return (
    <div className="grid gap-5 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
      {views.map((v) => (
        <EventCard key={v.series.key} event={v.shown} moreDates={otherDates(v.series, v.shown)} />
      ))}
    </div>
  );
}

function DaySection({ date, views }: { date: string; views: SeriesView[] }) {
  return (
    <section>
      <div className="flex items-baseline gap-3 mb-[18px]">
        <h2 className="text-[19px] font-extrabold m-0">{formatWeekdayDayMonth(date)}</h2>
        <span className="ml-auto text-[11.5px] font-bold px-2.5 py-[3px] rounded-full text-accent-cyan bg-[color:var(--color-accent-cyan)]/[0.12] border border-[color:var(--color-accent-cyan)]/30">
          {views.length} {pluralEvents(views.length)}
        </span>
      </div>
      <SeriesGrid views={views} />
    </section>
  );
}

function EmptyState({
  suggestion,
  suggestionCount,
  onPick,
  showReset,
  onReset,
}: {
  suggestion: StripItem | null;
  suggestionCount: number;
  onPick: (sel: DateSel) => void;
  showReset: boolean;
  onReset: () => void;
}) {
  return (
    <div className="bg-surface border border-border rounded-xl p-10 text-center">
      <p className="text-lg font-semibold mb-2">На эту дату ничего не нашлось</p>
      <p className="text-sm text-muted mb-5">
        Выберите другой день в ленте выше{showReset ? " или сбросьте фильтры по типу и цене" : ""}.
      </p>
      <div className="flex gap-2 justify-center flex-wrap">
        {suggestion && (
          <button
            type="button"
            onClick={() => onPick(suggestion.sel)}
            className="px-4 py-2 bg-accent text-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Ближайшее — {suggestion.label} ({suggestionCount})
          </button>
        )}
        {showReset && (
          <button
            type="button"
            onClick={onReset}
            className="px-4 py-2 border border-border text-muted rounded-lg text-sm font-medium hover:text-ink transition-colors"
          >
            Сбросить фильтры
          </button>
        )}
      </div>
    </div>
  );
}
```

`SearchResults`: проп `events: EventItem[]` заменить на `views: SeriesView[]`. Во всех местах `events.length` → `views.length`. Сетку `events.map(<EventCard …/>)` заменить на `<SeriesGrid views={views} />`. Тексты и кнопки не менять.

Удалить `web/lib/dayGroups.ts` и импорты `groupByDay`, `addDaysUTC`, `formatDayMonth`, `applyFilters` из `CityView`.

Выбор дня в ленте очищает поиск (`setQuery("")`): пользователь нажал на дату — значит, хочет увидеть её, а не выдачу поиска.

- [ ] **Step 3: README** — обновить места из списка **Files**:
  - `CityView` — лента дат, серии, состояние в URL (фильтры пишутся сразу, поиск с задержкой), пересчёт «сегодня» на клиенте;
  - `FilterBar` — поиск, чипы типов (пустой выбор = все, «× Сбросить»), поповер цены;
  - `EventCard` — строка «ещё N дат»;
  - новые файлы: `DateStrip`, `lib/series.ts`, `lib/dateStrip.ts`, `lib/urlState.ts`;
  - `lib/filters.ts` и `lib/dateUtil.ts` — новые функции;
  - строку `dayGroups.ts` удалить.

- [ ] **Step 4: Проверки кода.**
  - `cd web && npx vitest run` → PASS;
  - `npm run lint` → без ошибок (если правило `react-hooks/set-state-in-effect` ругается несмотря на блочный disable — посмотреть сообщение и поставить `eslint-disable-next-line` над конкретными строками, как в исходном коде);
  - `npm run build` → успешно.
- [ ] **Step 5: Ручная проверка в превью.** `preview_start { name: "web" }`, десктоп, `/perm`:
  1. Ни один чип типа не подсвечен. Клик «Концерт» → в выдаче только бейджи «Концерт», чип подсвечен, есть «× Сбросить», URL содержит `?type=concert`.
  2. Лента: у «Сегодня» стоит число, оно равно числу карточек под заголовком дня. Пустые дни приглушены.
  3. «Все даты» → «Пермская деревянная скульптура» встречается одной карточкой с «ещё N дат до …» (`javascript_tool`: посчитать карточки с этим `h2`, ожидается 1).
  4. «Выходные» → заголовки двух дней.
  5. Поиск «скульптура» → одна карточка на серию, лента без подсветки, подпись «Поиск по всем датам».
  6. Скопировать URL с `?date=…&type=…` в новую вкладку → то же состояние.
  7. `/perm?date=2026-01-01` → состояние по умолчанию.
  8. Устаревшая сборка: `javascript_tool` + `vi`-подобной подмены часов в браузере нет. Проверяется косвенно: в исходнике `liveEvents` фильтрует по `today` из `getCityToday`, покрытого тестом задачи 1. Отметить в отчёте как непроверенное вживую.
  9. `/sochi` открывается без ошибок в консоли (`read_console_messages onlyErrors`).
  10. Скриншот главной — пруф.
- [ ] **Step 6:** `git branch --show-current`, затем:

```bash
git add web/components/CityView.tsx web/components/FilterBar.tsx web/lib/dayGroups.ts README.md
git commit -m "feat(web): лента дат и серии на главной, чипы типов выбирают, фильтры в URL"
```

(`git add` на удалённом файле стейджит удаление.)

---

### Task 7: Страница события — «Другие даты» и возврат к фильтрам

**Files:**
- Modify: `web/lib/events.ts` (добавить `getSeriesSiblings`)
- Create: `web/components/OtherDates.tsx`, `web/components/BackLink.tsx`
- Modify: `web/app/perm/events/[slug]/page.tsx`, `web/app/sochi/events/[slug]/page.tsx` (одинаковая правка; файлы отличаются только городом и типом `params`)
- Modify: `README.md` — описания `lib/events.ts` (`getSeriesSiblings`) и компонентов (`OtherDates`, `BackLink`); в таблицу «Что реализовано» после строки «Fuzzy-дедуп» — строка **«Лента дат и серии»**: что даёт (один день по умолчанию вместо 400+ карточек, повторы — одной карточкой, фильтры в URL, «Другие даты», возврат к фильтрам) и где лежит

**Interfaces:**
- Consumes: `seriesKey`, `compareByDateTime`, `groupByDate` (Task 2); `formatWeekdayDayMonth` (Task 1); `listStateKey` (Task 5).
- Produces: `getSeriesSiblings(city: City, event: EventItem, today: string): Promise<EventItem[]>`.

- [ ] **Step 1: `lib/events.ts`** — импорт и функция в конец файла:

```ts
import { seriesKey } from "./series";

/**
 * События города на время сборки: страниц событий ~400, и без мемоизации
 * каждая тянула бы весь город заново ради блока «Другие даты».
 */
const cityEventsMemo = new Map<string, Promise<EventItem[]>>();

function getEventsByCityMemo(city: City, today: string): Promise<EventItem[]> {
  const key = `${city}|${today}`;
  let pending = cityEventsMemo.get(key);
  if (!pending) {
    pending = getEventsByCity(city, today);
    cityEventsMemo.set(key, pending);
  }
  return pending;
}

/** Остальные сеансы той же серии — тем же ключом, что и карточка «ещё N дат» на главной. */
export async function getSeriesSiblings(city: City, event: EventItem, today: string): Promise<EventItem[]> {
  const key = seriesKey(event);
  const events = await getEventsByCityMemo(city, today);
  return events.filter((e) => e.id !== event.id && seriesKey(e) === key);
}
```

- [ ] **Step 2: `OtherDates.tsx`** (серверный компонент):

```tsx
import Link from "next/link";
import type { EventItem } from "@/lib/types";
import { compareByDateTime, groupByDate } from "@/lib/series";
import { formatWeekdayDayMonth } from "@/lib/dateUtil";

export function OtherDates({ current, siblings }: { current: EventItem; siblings: EventItem[] }) {
  if (siblings.length === 0) return null;

  const days = groupByDate([current, ...siblings].sort(compareByDateTime), (e) => e.date);

  return (
    <section className="mt-6">
      <h2 className="text-[13px] font-semibold text-muted uppercase tracking-wider mb-2.5">
        Другие даты
      </h2>
      <ul className="flex flex-col gap-1.5 text-[14px]">
        {days.map((day) => (
          <li key={day.date} className="flex flex-wrap items-baseline gap-x-2">
            <span className="font-semibold">{formatWeekdayDayMonth(day.date)}</span>
            {day.items.map((e) =>
              e.id === current.id ? (
                <span key={e.id} className="text-accent">
                  {e.timeStart ?? "время не указано"} · эта дата
                </span>
              ) : (
                <Link
                  key={e.id}
                  href={`/${e.city}/events/${e.slug}/`}
                  className="text-muted hover:text-accent hover:underline underline-offset-2"
                >
                  {e.timeStart ?? "время не указано"}
                </Link>
              ),
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 3: `BackLink.tsx`**:

```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { City } from "@/lib/types";
import { listStateKey } from "@/lib/urlState";

/** «← Все события» с фильтрами, которые были на главной перед переходом. */
export function BackLink({ city }: { city: City }) {
  const base = `/${city}`;
  const [href, setHref] = useState(base);

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(listStateKey(city));
      // eslint-disable-next-line react-hooks/set-state-in-effect -- единоразовое чтение хранилища после монтирования
      if (saved) setHref(base + saved);
    } catch {
      // Хранилище недоступно — остаётся ссылка на главную без фильтров.
    }
  }, [base, city]);

  return (
    <Link href={href} className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent mb-4">
      ← Все события
    </Link>
  );
}
```

- [ ] **Step 4: Обе страницы событий** (показано для `perm`; в `sochi` то же с `"sochi"`):
  - импорт `getSeriesSiblings` добавить к импорту из `@/lib/events`; добавить `import { BackLink } from "@/components/BackLink";` и `import { OtherDates } from "@/components/OtherDates";`;
  - после `if (!event) notFound();`:

```tsx
const siblings = await getSeriesSiblings("perm", event, getCityToday("perm"));
```

  - блок `<Link href="/perm" …>← Все события</Link>` заменить на `<BackLink city="perm" />`;
  - после `div` с ценой и кнопкой «Перейти к источнику» (последний элемент в `<article>`) вставить `<OtherDates current={event} siblings={siblings} />`;
  - если `Link` больше нигде в файле не используется — удалить `import Link from "next/link";`.
- [ ] **Step 5: README** — правки из списка **Files**.
- [ ] **Step 5a: Проверки кода.** `npx vitest run`, `npm run lint`, `npm run build` → успешно. Время сборки сравнить с задачей 6b: рост должен быть небольшим. Если сборка заметно дольше — значит, мемо не работает между страницами (допущение из спеки), зафиксировать в отчёте.
- [ ] **Step 6: Ручная проверка в превью:**
  1. `/perm`, «Все даты», открыть «Пермская деревянная скульптура» → блок «Другие даты». Число дат совпадает с «ещё N дат» + 1, текущая дата помечена «эта дата», ссылки ведут на другие даты.
  2. На главной выбрать «Концерт» и «Выходные», открыть событие, нажать «← Все события» → фильтры и дата на месте.
  3. Открыть событие по прямой ссылке в новой вкладке → «← Все события» ведёт на `/perm` без параметров.
  4. Кнопка «Назад» браузера после перехода с отфильтрованной главной → URL с параметрами, состояние восстановлено.
  5. Событие без повторов → блока нет.
  6. То же одной проверкой на `/sochi/events/...`.
  7. На главной кликнуть чип и сразу, без паузы, открыть карточку → «← Все события» → чип выбран (Review Focus п. 7).
- [ ] **Step 7:** `git branch --show-current`, затем:

```bash
git add web/lib/events.ts web/components/OtherDates.tsx web/components/BackLink.tsx "web/app/perm/events/[slug]/page.tsx" "web/app/sochi/events/[slug]/page.tsx" README.md
git commit -m "feat(web): «Другие даты» серии и возврат к фильтрам со страницы события"
```

---

### Task 8: Финальная проверка и ревью ветки

Кода и документации не добавляет: README обновлён в 6b и 7. Это ворота перед пушем.

- [ ] **Step 1:** Финальный прогон: `npx vitest run`, `npm run lint`, `npm run build` — всё зелёное. Вывод приложить к отчёту.
- [ ] **Step 2:** `grep -n "dayGroups\|Сегодня / Завтра / Дальше\|events.getCityToday" README.md` → совпадений в описаниях текущего кода нет.
- [ ] **Step 3:** Ревью всей ветки (`superpowers:requesting-code-review`) до пуша. Найденное чинится отдельными коммитами. Пуш и PR — только после согласия пользователя.

---

## Verification (сквозная)

- Юнит: `cd web && npx vitest run`. Новые файлы: `dateUtil`, `series`, `filters` (переписан), `dateStrip`, `urlState`. Существующие `search`, `price` должны остаться зелёными.
- Сборка: `npm run lint && npm run build`.
- Вживую: `preview_start { name: "web" }`, чек-листы задач 6b и 7, скриншот главной и страницы события с «Другими датами».
- Не проверяется вживую (фиксируется в отчёте):
  - поведение при устаревшей сборке — покрыто тестом `getCityToday` и чтением кода;
  - переиспользование мемо между страницами при `next build` — видно только косвенно, по времени сборки.
