import type { City } from "@/lib/types";
import { CITY_CONFIG } from "@/lib/types";

export function Header({ city }: { city?: City }) {
  return (
    <header className="sticky top-0 z-10 bg-surface border-b border-border">
      <div className="mx-auto max-w-[1440px] px-4 py-3.5 flex items-center gap-4 flex-wrap">
        <a
          href="/"
          className="flex items-baseline gap-[2px] font-extrabold text-xl tracking-tight text-ink whitespace-nowrap"
        >
          Афиша
          <span className="bg-gradient-to-r from-accent to-[#8b5cf6] bg-clip-text text-transparent">
            .PRM
          </span>
        </a>

        <nav className="flex gap-1" aria-label="Выбор города">
          {(Object.keys(CITY_CONFIG) as City[]).map((c) => (
            <a
              key={c}
              href={CITY_CONFIG[c].path}
              className={`px-4 py-[7px] rounded-lg text-[13px] font-semibold border transition-colors ${
                city === c
                  ? "border-transparent text-bg bg-accent"
                  : "border-border text-muted bg-surface hover:text-ink"
              }`}
            >
              {CITY_CONFIG[c].label}
            </a>
          ))}
        </nav>
      </div>
    </header>
  );
}
