"use client";

import { useState } from "react";
import type { EventType } from "@/lib/types";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import type { Filters } from "@/lib/filters";

interface FilterBarProps {
  filters: Filters;
  onChange: (next: Filters) => void;
  availableTypes: readonly EventType[];
  query: string;
  onQueryChange: (value: string) => void;
}

export function FilterBar({ filters, onChange, availableTypes, query, onQueryChange }: FilterBarProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const [moreTypesOpen, setMoreTypesOpen] = useState(false);

  const toggleType = (t: EventType) => {
    const next = new Set(filters.types);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    onChange({ ...filters, types: next });
  };

  const setPrice = (priceMin: number, priceMax: number | null) =>
    onChange({ ...filters, priceMin, priceMax });

  const visibleTypes = availableTypes.slice(0, 4);
  const overflowTypes = availableTypes.slice(4);

  const typeChipClass = (active: boolean) =>
    `text-[12.5px] font-semibold px-3.5 py-[7px] rounded-lg border whitespace-nowrap transition-colors ${
      active
        ? "bg-accent border-transparent text-bg"
        : "bg-bg border-border text-muted hover:border-[color:var(--color-border)]"
    }`;

  return (
    <div className="relative flex flex-col md:flex-row md:items-center gap-3 md:gap-[14px] p-3 bg-surface border border-border rounded-2xl md:overflow-x-auto [scrollbar-width:none]">
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

      <div className="hidden md:block w-px self-stretch bg-border flex-shrink-0" />

      <div className="flex gap-2 flex-wrap md:flex-nowrap md:flex-none relative">
        {visibleTypes.map((t) => {
          const active = filters.types.has(t);
          return (
            <button
              key={t}
              type="button"
              onClick={() => toggleType(t)}
              className={typeChipClass(active)}
            >
              {EVENT_TYPE_LABELS[t]}
            </button>
          );
        })}

        {overflowTypes.length > 0 && (
          <>
            <button
              type="button"
              onClick={() => setMoreTypesOpen((v) => !v)}
              className="text-[12.5px] font-semibold px-3.5 py-[7px] rounded-lg border border-border text-muted bg-bg whitespace-nowrap"
              aria-expanded={moreTypesOpen}
            >
              Ещё {overflowTypes.length} {moreTypesOpen ? "▴" : "▾"}
            </button>

            {moreTypesOpen && (
              <div className="absolute left-0 top-[calc(100%+8px)] z-20 w-[220px] bg-surface border border-border rounded-xl p-3 shadow-[0_20px_50px_-30px_rgba(139,92,246,0.5)] flex flex-wrap gap-2">
                {overflowTypes.map((t) => {
                  const active = filters.types.has(t);
                  return (
                    <button
                      key={t}
                      type="button"
                      onClick={() => toggleType(t)}
                      className={typeChipClass(active)}
                    >
                      {EVENT_TYPE_LABELS[t]}
                    </button>
                  );
                })}
              </div>
            )}
          </>
        )}

        {filters.types.size > 0 && (
          <button
            type="button"
            onClick={() => onChange({ ...filters, types: new Set() })}
            className="text-[12.5px] font-semibold px-2 py-[7px] text-muted hover:text-ink whitespace-nowrap"
          >
            × Сбросить
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => setMoreOpen((v) => !v)}
        className="md:ml-auto flex-none self-start md:self-auto text-[12.5px] font-semibold px-3.5 py-[7px] rounded-lg border border-border text-muted bg-bg whitespace-nowrap"
        aria-expanded={moreOpen}
      >
        Ещё фильтры {moreOpen ? "▴" : "▾"}
      </button>

      {moreOpen && (
        <div className="absolute right-0 top-[calc(100%+8px)] z-20 w-[260px] bg-surface border border-border rounded-xl p-4 shadow-[0_20px_50px_-30px_rgba(139,92,246,0.5)]">
          <h3 className="mb-2.5 text-[13px] font-semibold text-muted uppercase tracking-wider">
            Цена
          </h3>
          <div className="flex items-center gap-1.5 text-sm mb-4">
            <input
              type="number"
              min={0}
              value={filters.priceMin}
              onChange={(e) =>
                setPrice(Math.max(0, Number(e.target.value) || 0), filters.priceMax)
              }
              className="w-[70px] px-2 py-1.5 bg-bg border border-border rounded-md text-[13px] text-ink"
            />
            <span className="text-muted">—</span>
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
            <span className="text-muted">₽</span>
          </div>
        </div>
      )}
    </div>
  );
}
