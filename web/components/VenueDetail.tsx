import Image from "next/image";
import Link from "next/link";
import type { City, VenueItem } from "@/lib/types";
import { getVenueTypeLabel } from "@/lib/types";
import { cityGenitive, venueJsonLd } from "@/lib/venue-meta";
import { isUsableImage, venueBadgeStyle, venuePlaceholder } from "@/lib/venue-styles";

const MONTHS_RU = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

function formatUpdated(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS_RU[d.getMonth()]} ${d.getFullYear()}`;
}

function mapUrl(venue: VenueItem): string {
  const query = `${venue.name} ${venue.address ?? ""}`.trim();
  return `https://2gis.ru/search/${encodeURIComponent(query)}`;
}

export function VenueDetail({ venue, city }: { venue: VenueItem; city: City }) {
  const placeholder = venuePlaceholder(venue.type);
  const typeLabel = getVenueTypeLabel(venue.type);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(venueJsonLd(venue, city)) }}
      />

      <article className="mx-auto max-w-3xl px-4 pt-6 pb-12 flex-1 w-full">
        <nav className="text-[13px] text-muted mb-4 flex flex-wrap items-center gap-1" aria-label="Хлебные крошки">
          <Link href={`/${city}/`} className="hover:text-accent">
            Афиша {cityGenitive(city)}
          </Link>
          <span aria-hidden>›</span>
          <Link href={`/${city}/venues/`} className="hover:text-accent">
            Площадки
          </Link>
          <span aria-hidden>›</span>
          <span className="text-ink">{venue.name}</span>
        </nav>

        <div className="relative aspect-[16/9] bg-[#ddd] rounded-xl overflow-hidden mb-5">
          {isUsableImage(venue.imageUrl) ? (
            <Image
              src={venue.imageUrl!}
              alt={`${venue.name} — ${typeLabel}`}
              fill
              sizes="(min-width: 1024px) 768px, 100vw"
              className="object-cover"
              unoptimized
              priority
            />
          ) : (
            <div
              className={`absolute inset-0 bg-gradient-to-br ${placeholder.gradient} flex items-center justify-center text-9xl`}
              aria-hidden
            >
              {placeholder.emoji}
            </div>
          )}
        </div>

        <span
          className={`inline-block text-[11px] font-semibold px-2 py-[3px] rounded-full uppercase tracking-wider mb-3 ${venueBadgeStyle(venue.type)}`}
        >
          {typeLabel}
        </span>

        <h1 className="text-2xl sm:text-3xl font-bold leading-tight mb-4">
          {venue.name}
        </h1>

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[15px] mb-6">
          {venue.address && (
            <>
              <dt className="text-muted">Адрес:</dt>
              <dd>{venue.address}</dd>
            </>
          )}
          {venue.district && (
            <>
              <dt className="text-muted">Район:</dt>
              <dd>{venue.district}</dd>
            </>
          )}
        </dl>

        <a
          href={mapUrl(venue)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-5 py-3 bg-accent text-white rounded-lg font-medium hover:bg-accent-hover transition-colors"
        >
          Показать на карте →
        </a>

        <p className="text-[13px] text-muted mt-6">
          Информация обновлена: {formatUpdated(venue.updatedAt)}
        </p>
      </article>
    </>
  );
}
