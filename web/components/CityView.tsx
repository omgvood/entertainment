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
  // filters — в зависимостях: иначе клик по фильтру в первые 300 мс после набора
  // не отменяет уже запущенный таймер, и тот перезаписывает URL старым filters.
  useEffect(() => {
    if (!urlRead) return;
    const id = setTimeout(() => writeState(serializeState(filters, query)), 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- writeState воссоздаётся каждый рендер, но всегда читает актуальный city/window
  }, [query, filters, urlRead]);

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

/**
 * Выдача поиска. Секции «Сегодня / Завтра / Дальше» при активном запросе
 * схлопываются в один список: иначе карточка с релевантностью 160 в «Дальше»
 * оказывается визуально ниже карточки с 30 в «Сегодня», и ранжирование теряется.
 */
function SearchResults({
  views,
  venues,
  query,
  hiddenByFilters,
  onResetFilters,
  onClearQuery,
}: {
  views: SeriesView[];
  venues: VenueItem[];
  query: string;
  hiddenByFilters: number;
  onResetFilters: () => void;
  onClearQuery: () => void;
}) {
  if (views.length === 0 && venues.length === 0) {
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
      {views.length > 0 && (
        <section>
          <div className="flex items-baseline gap-3 mb-[18px]" aria-live="polite">
            <h2 className="text-[19px] font-extrabold m-0">Найдено</h2>
            <span className="text-[13px] text-muted">
              {views.length} {pluralEvents(views.length)}
            </span>
          </div>
          <SeriesGrid views={views} />
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

function pluralEvents(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return "событий";
  if (mod10 === 1) return "событие";
  if (mod10 >= 2 && mod10 <= 4) return "события";
  return "событий";
}
