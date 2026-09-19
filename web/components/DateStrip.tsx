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
