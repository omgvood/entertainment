"use client";

import { useState } from "react";
import type { EventType } from "@/lib/types";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import type { Filters, WhenFilter } from "@/lib/filters";

interface FilterBarProps {
  filters: Filters;
  onChange: (next: Filters) => void;
  availableTypes: readonly EventType[];
}

const WHEN_OPTIONS: { value: WhenFilter; label: string }[] = [
  { value: "today", label: "Сегодня" },
  { value: "tomorrow", label: "Завтра" },
  { value: "weekend", label: "Выходные" },
  { value: "any", label: "Любая" },
];

export function FilterBar({ filters, onChange, availableTypes }: FilterBarProps) {
  const [moreOpen, setMoreOpen] = useState(false);
  const [moreTypesOpen, setMoreTypesOpen] = useState(false);

  const toggleType = (t: EventType) => {
    const next = new Set(filters.types);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    onChange({ ...filters, types: next });
  };

  const setWhen = (when: WhenFilter) => onChange({ ...filters, when });

  const setPrice = (priceMin: number, priceMax: number) =>
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
    <div className="relative flex items-center gap-[14px] p-3 bg-surface border border-border rounded-2xl overflow-x-auto">
      <div className="relative flex-none w-[240px]">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-[13px]">⌕</span>
        <input
          type="search"
          placeholder="Название, площадка, организатор…"
          className="w-full bg-bg border border-border rounded-full text-[13px] text-ink pl-8 pr-3.5 py-2 focus:outline-none focus:border-accent"
        />
      </div>

      <div className="w-px self-stretch bg-border flex-shrink-0" />

      <div className="flex gap-2 flex-none relative">
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
      </div>

      <div className="w-px self-stretch bg-border flex-shrink-0" />

      <div className="flex gap-[3px] bg-bg border border-border rounded-[10px] p-[3px] flex-none">
        {WHEN_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setWhen(opt.value)}
            className={`text-[12.5px] font-semibold px-3 py-[6px] rounded-[7px] whitespace-nowrap ${
              filters.when === opt.value ? "bg-surface text-ink" : "text-muted"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setMoreOpen((v) => !v)}
        className="ml-auto flex-none text-[12.5px] font-semibold px-3.5 py-[7px] rounded-lg border border-border text-muted bg-bg whitespace-nowrap"
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
              value={filters.priceMax}
              onChange={(e) =>
                setPrice(filters.priceMin, Math.max(0, Number(e.target.value) || 0))
              }
              className="w-[70px] px-2 py-1.5 bg-bg border border-border rounded-md text-[13px] text-ink"
            />
            <span className="text-muted">₽</span>
          </div>

          <h3 className="mb-2.5 text-[13px] font-semibold text-muted uppercase tracking-wider flex items-center gap-2">
            Район
            <span className="text-[10px] bg-border text-muted px-1.5 py-[2px] rounded-full normal-case tracking-normal font-medium">
              скоро
            </span>
          </h3>
          <div className="flex flex-col gap-1 text-sm text-muted">
            <label className="flex items-center gap-2 cursor-not-allowed">
              <input type="checkbox" disabled /> Центр
            </label>
            <label className="flex items-center gap-2 cursor-not-allowed">
              <input type="checkbox" disabled /> Мотовилиха
            </label>
            <label className="flex items-center gap-2 cursor-not-allowed">
              <input type="checkbox" disabled /> Индустриальный
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
