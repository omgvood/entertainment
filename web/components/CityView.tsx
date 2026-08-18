"use client";

import { useMemo, useState } from "react";
import type { City, EventItem, VenueItem } from "@/lib/types";
import { CITY_CONFIG } from "@/lib/types";
import { applyFilters, DEFAULT_FILTERS, typesByFrequency, type Filters } from "@/lib/filters";
import { groupByDay } from "@/lib/dayGroups";
import { addDaysUTC, formatDayMonth } from "@/lib/dateUtil";
import { FilterBar } from "./FilterBar";
import { EventCard } from "./EventCard";
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
  const types = useMemo(() => typesByFrequency(events), [events]);
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const tomorrow = useMemo(() => addDaysUTC(today, 1), [today]);

  // Сегодня/Завтра не зависят от вкладки "Когда" — фильтруем только по типу/цене.
  const byTypeAndPrice = useMemo(
    () => applyFilters(events, { ...filters, when: "any" }, today),
    [events, filters, today],
  );
  const groups = useMemo(() => groupByDay(byTypeAndPrice, today), [byTypeAndPrice, today]);

  // "Дальше" — то же самое множество, доп. отфильтрованное по вкладке "Когда".
  const later = useMemo(
    () => (filters.when === "any" ? groups.later : applyFilters(groups.later, filters, today)),
    [groups.later, filters, today],
  );

  const totalFound = groups.today.length + groups.tomorrow.length + later.length;

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
          {totalFound} {pluralEvents(totalFound)} на ближайшие две недели
        </p>
        <FilterBar filters={filters} onChange={setFilters} availableTypes={types} />
      </div>

      {totalFound === 0 ? (
        <EmptyState onReset={() => setFilters(DEFAULT_FILTERS)} />
      ) : (
        <>
          <DaySection title="Сегодня" date={today} events={groups.today} />
          <DaySection title="Завтра" date={tomorrow} events={groups.tomorrow} />
          <DaySection title="Дальше" events={later} />
        </>
      )}

      {venues.length > 0 && (
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

function DaySection({
  title,
  date,
  events,
}: {
  title: string;
  date?: string;
  events: EventItem[];
}) {
  if (events.length === 0) return null;

  return (
    <section>
      <div className="flex items-baseline gap-3 mb-[18px]">
        <h2 className="text-[19px] font-extrabold m-0">{title}</h2>
        {date && <span className="text-[13px] text-muted">{formatDayMonth(date)}</span>}
        <span className="ml-auto text-[11.5px] font-bold px-2.5 py-[3px] rounded-full text-accent-cyan bg-[color:var(--color-accent-cyan)]/[0.12] border border-[color:var(--color-accent-cyan)]/30">
          {events.length} {pluralEvents(events.length)}
        </span>
      </div>
      <div className="grid gap-5 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {events.map((event) => (
          <EventCard key={event.id} event={event} />
        ))}
      </div>
    </section>
  );
}

function EmptyState({ onReset }: { onReset: () => void }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-10 text-center">
      <p className="text-lg font-semibold mb-2">Ничего не нашлось</p>
      <p className="text-sm text-muted mb-5">
        Попробуйте расширить диапазон цен, отключить чекбокс «только с фиксированной
        датой» или выбрать «Любая дата».
      </p>
      <button
        type="button"
        onClick={onReset}
        className="px-4 py-2 bg-accent text-bg rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
      >
        Сбросить фильтры
      </button>
    </div>
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
