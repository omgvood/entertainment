/**
 * Data layer.
 *
 * Спринт 1b: запрос в Postgres через Supabase publishable key.
 *            Чтение — в Server Components при сборке SSG.
 *            DB-строка снизу маппится из snake_case в camelCase TS-типа.
 */

import { supabase } from "./supabase";
import type { City, EventItem, EventType } from "./types";

/** Сырая строка из таблицы public.events (snake_case). */
interface EventRow {
  id: string;
  city: string;
  slug: string;
  title: string;
  type: string;
  category: string | null;
  date: string;
  time_start: string | null;
  time_end: string | null;
  price_min: number;
  price_max: number;
  price_text: string;
  price_note: string | null;
  address: string;
  venue_name: string;
  district: string | null;
  image_url: string | null;
  description: string | null;
  organizer: string | null;
  source_url: string;
  source: string;
  parsed_at: string;
  meta_title: string | null;
  meta_description: string | null;
}

function rowToEvent(r: EventRow): EventItem {
  return {
    id: r.id,
    city: r.city as City,
    slug: r.slug,
    title: r.title,
    type: r.type as EventType,
    category: r.category ?? undefined,
    date: r.date,
    timeStart: r.time_start ?? undefined,
    timeEnd: r.time_end ?? undefined,
    priceMin: r.price_min,
    priceMax: r.price_max,
    priceText: r.price_text,
    priceNote: r.price_note ?? undefined,
    address: r.address,
    venueName: r.venue_name,
    district: r.district ?? undefined,
    imageUrl: r.image_url ?? undefined,
    description: r.description ?? undefined,
    organizer: r.organizer ?? undefined,
    sourceUrl: r.source_url,
    source: r.source,
    parsedAt: r.parsed_at,
    metaTitle: r.meta_title ?? undefined,
    metaDescription: r.meta_description ?? undefined,
  };
}

export async function getEventsByCity(city: City): Promise<EventItem[]> {
  const { data, error } = await supabase
    .from("events")
    .select("*")
    .eq("city", city)
    .order("date", { ascending: true });

  if (error) {
    throw new Error(`Не удалось загрузить события для ${city}: ${error.message}`);
  }

  return (data as EventRow[]).map(rowToEvent);
}

export async function getEventBySlug(
  city: City,
  slug: string
): Promise<EventItem | null> {
  const { data, error } = await supabase
    .from("events")
    .select("*")
    .eq("city", city)
    .eq("slug", slug)
    .maybeSingle();

  if (error) {
    throw new Error(`Не удалось загрузить событие ${slug}: ${error.message}`);
  }

  return data ? rowToEvent(data as EventRow) : null;
}
