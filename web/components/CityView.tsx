"use client";

import { useMemo, useState } from "react";
import type { City, EventItem } from "@/lib/types";
import { CITY_CONFIG } from "@/lib/types";
import { applyFilters, DEFAULT_FILTERS, type Filters } from "@/lib/filters";
import { Sidebar } from "./Sidebar";
import { EventCard } from "./EventCard";

interface CityViewProps {
  events: EventItem[];
  cityTitle: string;
  city: City;
}

export function CityView({ events, cityTitle, city }: CityViewProps) {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);

  const filtered = useMemo(
    () => applyFilters(events, filters),
    [events, filters],
  );

  return (
    <div className="mx-auto max-w-[1440px] px-4 pt-6 pb-12 grid gap-6 lg:grid-cols-[240px_1fr] flex-1 w-full">
      <Sidebar filters={filters} onChange={setFilters} />

      <main>
        <div className="flex items-baseline justify-between gap-4 flex-wrap mb-5">
          <h1 className="text-[22px] sm:text-[28px] font-bold leading-tight">
            {cityTitle}
          </h1>
          <p className="text-sm text-muted">
            Найдено:{" "}
            <strong className="text-ink">{filtered.length}</strong>{" "}
            {pluralEvents(filtered.length)}
          </p>
        </div>

        {filtered.length === 0 ? (
          <EmptyState onReset={() => setFilters(DEFAULT_FILTERS)} />
        ) : (
          <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
            {filtered.map((event) => (
              <EventCard key={event.id} event={event} />
            ))}
          </div>
        )}

        <section className="mt-12 pt-8 border-t border-border">
          <h2 className="text-lg font-semibold mb-2 text-ink">
            Досуг в {CITY_CONFIG[city].label} — всё в одном месте
          </h2>
          <p className="text-sm text-muted leading-relaxed max-w-3xl">
            {CITY_CONFIG[city].description}
          </p>
        </section>
      </main>
    </div>
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
        className="px-4 py-2 bg-accent text-white rounded-lg text-sm font-medium hover:bg-accent-hover transition-colors"
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
