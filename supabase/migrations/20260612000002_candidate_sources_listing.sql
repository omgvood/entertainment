-- Шаг 7: generic-парсер одобренных кандидатов.
-- Чтобы парсить домен из candidate_sources без ручного кода, нужны примеры URL (для выбора
-- страницы-листинга) и кэш найденного listing_url с датой проверки.

ALTER TABLE candidate_sources
    ADD COLUMN IF NOT EXISTS sample_urls   text[] DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS listing_url   text,
    ADD COLUMN IF NOT EXISTS last_verified timestamptz;

-- status: new | approved | rejected | broken
--   new      — ждёт модерации
--   approved — generic-парсер забирает домен в работу
--   rejected — пропустить навсегда
--   broken   — ручная демоция хронически падающего домена (по данным source_health_agg)
COMMENT ON COLUMN candidate_sources.status IS 'new | approved | rejected | broken';
