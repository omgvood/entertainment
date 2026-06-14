import type { Metadata } from "next";
import { CityView } from "@/components/CityView";
import { Header } from "@/components/Header";
import { VenuesSection } from "@/components/VenuesSection";
import { getEventsByCity } from "@/lib/events";
import { getVenuesByCity } from "@/lib/venues";
import { CITY_CONFIG } from "@/lib/types";

export const metadata: Metadata = {
  title: CITY_CONFIG.perm.metaTitle,
  description: CITY_CONFIG.perm.metaDescription,
  openGraph: {
    title: CITY_CONFIG.perm.metaTitle,
    description: CITY_CONFIG.perm.metaDescription,
  },
};

export default async function PermPage() {
  const [events, venues] = await Promise.all([
    getEventsByCity("perm"),
    getVenuesByCity("perm"),
  ]);

  return (
    <>
      <Header city="perm" />
      <CityView events={events} cityTitle="Куда сходить в Перми" city="perm" />
      {venues.length > 0 && (
        <VenuesSection
          venues={venues.slice(0, 8)}
          city="perm"
          totalCount={venues.length}
        />
      )}
      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша · 2026
      </footer>
    </>
  );
}
