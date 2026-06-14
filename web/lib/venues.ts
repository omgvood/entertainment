/**
 * Data layer для постоянных площадок (таблица public.venues).
 * Чтение через anon-ключ в Server Components при сборке (RLS: публичное чтение).
 * Площадки — отдельная сущность от events: нет даты/цены, меняются редко.
 */

import { supabase } from "./supabase";
import type { City, VenueItem } from "./types";

/** Сырая строка из таблицы public.venues (snake_case). */
interface VenueRow {
  id: string;
  city: string;
  name: string;
  type: string;
  address: string | null;
  district: string | null;
  image_url: string | null;
  source: string | null;
  updated_at: string;
}

function rowToVenue(r: VenueRow): VenueItem {
  const prefix = `${r.city}-`;
  return {
    id: r.id,
    city: r.city as City,
    // slug вычисляется только здесь; startsWith защищает от нестандартных id.
    slug: r.id.startsWith(prefix) ? r.id.slice(prefix.length) : r.id,
    name: r.name,
    type: r.type,
    address: r.address ?? undefined,
    district: r.district ?? undefined,
    imageUrl: r.image_url ?? undefined,
    updatedAt: r.updated_at,
    // source — внутренняя деталь БД, в UI-модель не пробрасывается.
  };
}

/** Все площадки города, сгруппированы по типу (затем по имени). */
export async function getVenuesByCity(city: City): Promise<VenueItem[]> {
  const { data, error } = await supabase
    .from("venues")
    .select("*")
    .eq("city", city)
    .order("type", { ascending: true })
    .order("name", { ascending: true });

  if (error) {
    throw new Error(`Не удалось загрузить площадки для ${city}: ${error.message}`);
  }

  return (data as VenueRow[]).map(rowToVenue);
}

export async function getVenueBySlug(
  city: City,
  slug: string,
): Promise<VenueItem | null> {
  const { data, error } = await supabase
    .from("venues")
    .select("*")
    .eq("id", `${city}-${slug}`)
    .maybeSingle();

  if (error) {
    throw new Error(`Не удалось загрузить площадку ${slug}: ${error.message}`);
  }

  return data ? rowToVenue(data as VenueRow) : null;
}
