import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { VenuesCatalog } from "@/components/VenuesCatalog";
import { getVenuesByCity } from "@/lib/venues";

export const revalidate = 86400; // ISR 24ч: venues обновляются раз в 2 недели вне деплоя

export const metadata: Metadata = {
  title: "Постоянные места в Перми — боулинг, картинг, бильярд, квесты",
  description:
    "Каталог постоянных мест досуга в Перми: боулинг, бильярд, картинг и квесты. Адреса, районы, расположение на карте.",
};

export default async function PermVenuesPage() {
  const venues = await getVenuesByCity("perm");

  return (
    <>
      <Header city="perm" />
      <VenuesCatalog venues={venues} city="perm" />
      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша · 2026
      </footer>
    </>
  );
}
