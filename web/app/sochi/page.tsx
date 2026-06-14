import type { Metadata } from "next";
import { CityView } from "@/components/CityView";
import { Header } from "@/components/Header";
import { VenuesSection } from "@/components/VenuesSection";
import { getEventsByCity } from "@/lib/events";
import { getVenuesByCity } from "@/lib/venues";
import { CITY_CONFIG } from "@/lib/types";

export const metadata: Metadata = {
  title: CITY_CONFIG.sochi.metaTitle,
  description: CITY_CONFIG.sochi.metaDescription,
  openGraph: {
    title: CITY_CONFIG.sochi.metaTitle,
    description: CITY_CONFIG.sochi.metaDescription,
  },
};

export default async function SochiPage() {
  const [events, venues] = await Promise.all([
    getEventsByCity("sochi"),
    getVenuesByCity("sochi"),
  ]);

  return (
    <>
      <Header city="sochi" />
      <CityView events={events} cityTitle="Куда сходить в Сочи" city="sochi" />
      {venues.length > 0 && (
        <VenuesSection
          venues={venues.slice(0, 8)}
          city="sochi"
          totalCount={venues.length}
        />
      )}
      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша · 2026
      </footer>
    </>
  );
}
