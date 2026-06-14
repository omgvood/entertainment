import Link from "next/link";
import type { City, VenueItem } from "@/lib/types";
import { CITY_CONFIG } from "@/lib/types";
import { cityGenitive } from "@/lib/venue-meta";
import { VenueCard } from "./VenueCard";

/** Каталог всех площадок города (страница /{city}/venues). */
export function VenuesCatalog({ venues, city }: { venues: VenueItem[]; city: City }) {
  return (
    <main className="mx-auto max-w-[1440px] px-4 pt-6 pb-12 flex-1 w-full">
      <Link
        href={`/${city}/`}
        className="inline-flex items-center gap-1 text-sm text-muted hover:text-accent mb-4"
      >
        ← Афиша {cityGenitive(city)}
      </Link>

      <h1 className="text-[22px] sm:text-[28px] font-bold leading-tight mb-5">
        Постоянные места в {cityGenitive(city)}
      </h1>

      {venues.length === 0 ? (
        <p className="text-muted">Площадки пока не добавлены.</p>
      ) : (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
          {venues.map((venue) => (
            <VenueCard key={venue.id} venue={venue} />
          ))}
        </div>
      )}

      <section className="mt-12 pt-8 border-t border-border">
        <h2 className="text-lg font-semibold mb-2 text-ink">
          Куда сходить в {CITY_CONFIG[city].label}
        </h2>
        <p className="text-sm text-muted leading-relaxed max-w-3xl">
          Боулинг, бильярд, картинг и квесты {CITY_CONFIG[city].label} — постоянные
          места для досуга с друзьями и семьёй. Адреса, районы и расположение на карте.
        </p>
      </section>
    </main>
  );
}
