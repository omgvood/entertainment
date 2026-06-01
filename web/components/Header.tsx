import type { City } from "@/lib/types";
import { CITY_CONFIG } from "@/lib/types";

export function Header({ city }: { city?: City }) {
  return (
    <header className="sticky top-0 z-10 bg-surface border-b border-border">
      <div className="mx-auto max-w-[1440px] px-4 py-3 flex items-center gap-4 flex-wrap">
        <a
          href="/"
          className="flex items-center gap-2 font-bold text-xl text-ink whitespace-nowrap"
        >
          <span className="text-2xl">🎟</span>
          <span>Афиша</span>
        </a>

        <nav className="flex gap-1" aria-label="Выбор города">
          {(Object.keys(CITY_CONFIG) as City[]).map((c) => (
            <a
              key={c}
              href={CITY_CONFIG[c].path}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                city === c
                  ? "border-accent text-accent bg-[#ede7ff]"
                  : "border-border text-ink hover:border-accent bg-surface"
              }`}
            >
              <span aria-hidden>📍</span>
              {CITY_CONFIG[c].label}
            </a>
          ))}
        </nav>

        <div className="flex-1 max-w-[540px] w-full order-3 sm:order-none">
          <input
            type="search"
            placeholder="Поиск по названию, площадке, организатору…"
            className="w-full px-3.5 py-2.5 border border-border rounded-lg text-sm bg-bg focus:bg-surface focus:border-accent focus:outline-none"
          />
        </div>
      </div>
    </header>
  );
}
