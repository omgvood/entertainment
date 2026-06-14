import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { Header } from "@/components/Header";
import { VenueDetail } from "@/components/VenueDetail";
import { getVenueBySlug, getVenuesByCity } from "@/lib/venues";
import { buildVenueMetadata } from "@/lib/venue-meta";

export const dynamicParams = true; // площадки, добавленные после билда, рендерятся on-demand
export const revalidate = 86400; // ISR 24ч: venues обновляются вне деплоя

export async function generateStaticParams() {
  const venues = await getVenuesByCity("sochi");
  return venues.map((v) => ({ slug: v.slug }));
}

export async function generateMetadata(
  { params }: PageProps<"/sochi/venues/[slug]">,
): Promise<Metadata> {
  const { slug } = await params;
  const venue = await getVenueBySlug("sochi", slug);
  if (!venue) return { title: "Площадка не найдена" };
  return buildVenueMetadata(venue, "sochi");
}

export default async function SochiVenuePage(
  { params }: PageProps<"/sochi/venues/[slug]">,
) {
  const { slug } = await params;
  const venue = await getVenueBySlug("sochi", slug);
  if (!venue) notFound();

  return (
    <>
      <Header city="sochi" />
      <VenueDetail venue={venue} city="sochi" />
      <footer className="bg-surface border-t border-border py-5 text-center text-[13px] text-muted">
        Афиша Сочи · 2026
      </footer>
    </>
  );
}
