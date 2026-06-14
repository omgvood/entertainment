import Link from "next/link";
import type { City, VenueItem } from "@/lib/types";
import { VenueCard } from "./VenueCard";

interface VenuesSectionProps {
  venues: VenueItem[];
  city: City;
  totalCount: number;
}

/** Секция «Постоянные места» на главной города: до 8 карточек + ссылка на каталог. */
export function VenuesSection({ venues, city, totalCount }: VenuesSectionProps) {
  return (
    <section className="mx-auto max-w-[1440px] px-4 pb-12 w-full">
      <div className="flex items-baseline justify-between gap-4 flex-wrap mb-5">
        <h2 className="text-[22px] sm:text-[28px] font-bold leading-tight">
          Постоянные места
        </h2>
        {totalCount > venues.length && (
          <Link
            href={`/${city}/venues/`}
            className="text-sm font-medium text-accent hover:text-accent-hover"
          >
            Все площадки →
          </Link>
        )}
      </div>

      <div className="grid gap-4 grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {venues.map((venue) => (
          <VenueCard key={venue.id} venue={venue} />
        ))}
      </div>
    </section>
  );
}
