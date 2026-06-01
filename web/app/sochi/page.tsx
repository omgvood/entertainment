import type { Metadata } from "next";
import { CityView } from "@/components/CityView";
import { Header } from "@/components/Header";
import { getEventsByCity } from "@/lib/events";
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
  const events = await getEventsByCity("sochi");

  return (
    <>
      <Header city="sochi" />
      <CityView events={events} cityTitle="Куда сходить в Сочи" city="sochi" />
      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша · 2026
      </footer>
    </>
  );
}
