import Image from "next/image";
import Link from "next/link";
import type { VenueItem } from "@/lib/types";
import { getVenueTypeLabel } from "@/lib/types";
import { isUsableImage, venueBadgeStyle, venuePlaceholder } from "@/lib/venue-styles";

export function VenueCard({ venue }: { venue: VenueItem }) {
  const placeholder = venuePlaceholder(venue.type);

  return (
    <Link
      href={`/${venue.city}/venues/${venue.slug}/`}
      className="group bg-surface border border-border rounded-xl overflow-hidden shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-150 flex flex-col"
    >
      <div className="relative aspect-[4/3] bg-[#ddd]">
        {isUsableImage(venue.imageUrl) ? (
          <Image
            src={venue.imageUrl!}
            alt={`${venue.name} — ${getVenueTypeLabel(venue.type)}`}
            fill
            sizes="(min-width: 1200px) 25vw, (min-width: 768px) 33vw, 50vw"
            className="object-cover"
            unoptimized
          />
        ) : (
          <div
            className={`absolute inset-0 bg-gradient-to-br ${placeholder.gradient} flex items-center justify-center text-6xl`}
            aria-hidden
          >
            {placeholder.emoji}
          </div>
        )}
      </div>

      <div className="p-3 pb-4 flex flex-col gap-2 flex-1">
        <span
          className={`inline-block self-start text-[11px] font-semibold px-2 py-[3px] rounded-full uppercase tracking-wider ${venueBadgeStyle(venue.type)}`}
        >
          {getVenueTypeLabel(venue.type)}
        </span>

        <h2 className="text-[15px] font-semibold leading-tight line-clamp-2">
          {venue.name}
        </h2>

        <div className="flex flex-col gap-1 text-[13px] text-muted mt-auto">
          {venue.address && <span>📍 {venue.address}</span>}
          {venue.district && <span>🗺️ {venue.district}</span>}
        </div>
      </div>
    </Link>
  );
}
