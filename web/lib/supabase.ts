import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY не заданы. " +
      "Скопируй .env.example в .env.local и подставь значения."
  );
}

/**
 * Публичный клиент: используется в Server Components при SSG-сборке.
 * Ключ — publishable (anon), безопасно отдавать в браузер.
 * Запись блокирована RLS-политикой; писать события будет парсер
 * через сервисный ключ (Спринт 3).
 */
export const supabase = createClient(url, anonKey);
