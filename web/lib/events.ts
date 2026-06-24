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
  tags: string[] | null;
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
    tags: r.tags ?? [],
    sourceUrl: r.source_url,
    source: r.source,
    parsedAt: r.parsed_at,
    metaTitle: r.meta_title ?? undefined,
    metaDescription: r.meta_description ?? undefined,
  };
}

/** IANA-таймзона города — «сегодня» считается по местному времени, не по UTC сервера сборки. */
const CITY_TIMEZONES: Record<City, string> = {
  perm: "Asia/Yekaterinburg", // UTC+5
  sochi: "Europe/Moscow", // UTC+3
};

export async function getEventsByCity(city: City): Promise<EventItem[]> {
  const timezone = CITY_TIMEZONES[city] ?? "Europe/Moscow";
  // en-CA даёт YYYY-MM-DD; timeZone делает дату местной (билд идёт в 21:00 UTC).
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());

  // .neq('always') обязателен: в строковом сравнении Postgres 'always' >= 'YYYY-MM-DD' = TRUE,
  // т.е. .gte сам по себе always-строки НЕ отсекает. Площадки живут в таблице venues, не в сетке.
  const { data, error } = await supabase
    .from("events")
    .select("*")
    .eq("city", city)
    .neq("date", "always")
    .gte("date", today)
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
