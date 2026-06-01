"use client";

import type { EventType } from "@/lib/types";
import { EVENT_TYPE_LABELS } from "@/lib/types";
import type { Filters, WhenFilter } from "@/lib/filters";
import { ALL_TYPES } from "@/lib/filters";

interface SidebarProps {
  filters: Filters;
  onChange: (next: Filters) => void;
}

export function Sidebar({ filters, onChange }: SidebarProps) {
  const toggleType = (t: EventType) => {
    const next = new Set(filters.types);
    if (next.has(t)) next.delete(t);
    else next.add(t);
    onChange({ ...filters, types: next });
  };

  const setWhen = (when: WhenFilter) => onChange({ ...filters, when });

  const setPrice = (priceMin: number, priceMax: number) =>
    onChange({ ...filters, priceMin, priceMax });

  const setOnlyFixed = (onlyFixedDate: boolean) =>
    onChange({ ...filters, onlyFixedDate });

  return (
    <aside className="bg-surface border border-border rounded-xl p-5 shadow-sm lg:sticky lg:top-[76px] self-start">
      <FilterBlock title="Тип">
        {ALL_TYPES.map((t) => (
          <CheckboxRow
            key={t}
            label={EVENT_TYPE_LABELS[t]}
            checked={filters.types.has(t)}
            onChange={() => toggleType(t)}
          />
        ))}
      </FilterBlock>

      <FilterBlock title="Когда">
        <RadioRow
          label="Сегодня"
          checked={filters.when === "today"}
          onChange={() => setWhen("today")}
        />
        <RadioRow
          label="Завтра"
          checked={filters.when === "tomorrow"}
          onChange={() => setWhen("tomorrow")}
        />
        <RadioRow
          label="Эти выходные"
          checked={filters.when === "weekend"}
          onChange={() => setWhen("weekend")}
        />
        <RadioRow
          label="Любая дата"
          checked={filters.when === "any"}
          onChange={() => setWhen("any")}
        />
      </FilterBlock>

      <FilterBlock title="Цена">
        <div className="flex items-center gap-1.5 text-sm">
          <input
            type="number"
            min={0}
            value={filters.priceMin}
            onChange={(e) =>
              setPrice(Math.max(0, Number(e.target.value) || 0), filters.priceMax)
            }
            className="w-[70px] px-2 py-1.5 border border-border rounded-md text-[13px]"
          />
          <span>—</span>
          <input
            type="number"
            min={0}
            value={filters.priceMax}
            onChange={(e) =>
              setPrice(filters.priceMin, Math.max(0, Number(e.target.value) || 0))
            }
            className="w-[70px] px-2 py-1.5 border border-border rounded-md text-[13px]"
          />
          <span>₽</span>
        </div>
      </FilterBlock>

      <FilterBlock title="Район" badge="скоро">
        <CheckboxRow label="Центр" disabled />
        <CheckboxRow label="Мотовилиха" disabled />
        <CheckboxRow label="Индустриальный" disabled />
      </FilterBlock>

      <div>
        <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
          <input
            type="checkbox"
            checked={filters.onlyFixedDate}
            onChange={(e) => setOnlyFixed(e.target.checked)}
          />
          Только с фиксированной датой
        </label>
        <p className="mt-1.5 ml-6 text-xs text-muted">
          Скрыть боулинг/бильярд/картинг при поиске «сегодня вечером»
        </p>
      </div>
    </aside>
  );
}

function FilterBlock({
  title,
  badge,
  children,
}: {
  title: string;
  badge?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="pb-4 mb-4 border-b border-border last:border-b-0 last:mb-0 last:pb-0">
      <h3 className="mb-2.5 text-[13px] font-semibold text-muted uppercase tracking-wider flex items-center gap-2">
        {title}
        {badge && (
          <span className="text-[10px] bg-border text-muted px-1.5 py-[2px] rounded-full normal-case tracking-normal font-medium">
            {badge}
          </span>
        )}
      </h3>
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

function CheckboxRow({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked?: boolean;
  onChange?: () => void;
  disabled?: boolean;
}) {
  return (
    <label
      className={`flex items-center gap-2 py-1 text-sm ${
        disabled ? "text-muted cursor-not-allowed" : "cursor-pointer"
      }`}
    >
      <input
        type="checkbox"
        checked={checked ?? false}
        onChange={onChange}
        disabled={disabled}
      />
      {label}
    </label>
  );
}

function RadioRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className="flex items-center gap-2 py-1 text-sm cursor-pointer">
      <input type="radio" checked={checked} onChange={onChange} />
      {label}
    </label>
  );
}
