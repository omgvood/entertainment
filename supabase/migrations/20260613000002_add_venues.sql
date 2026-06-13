-- venues — постоянные заведения (боулинг/картинг/бильярд/квесты) как отдельная сущность.
-- Площадка — не событие: у неё нет даты, она меняется редко, обновляется вручную (<100 на город).
-- Primary source of truth = эта таблица (правится через Supabase Table Editor). Бекап —
-- периодический снимок в git через `parser-cli export-venues` (см. backup_venues.yml).
--
-- ВНИМАНИЕ: фронтенд пока читает постоянные места из events (date='always', источник 2ГИС).
-- Эта таблица — инфраструктура под будущий перенос; 2ГИС из пайплайна НЕ удалён, чтобы
-- боулинг/картинг не пропали с сайта до подключения фронтенда к venues.

CREATE TABLE IF NOT EXISTS venues (
    id         text PRIMARY KEY,   -- {city}-{slug}
    city       text NOT NULL,
    name       text NOT NULL,
    type       text NOT NULL,      -- bowling / billiards / karting / quest / ...
    address    text,
    district   text,
    image_url  text,
    source     text,               -- 'manual' / 'twogis' / 'playwright'
    updated_at timestamptz DEFAULT now()
);

-- Сайт (anon) должен уметь читать площадки для будущих страниц.
ALTER TABLE venues ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "venues public read" ON venues;
CREATE POLICY "venues public read" ON venues FOR SELECT USING (true);
