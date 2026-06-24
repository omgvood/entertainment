-- Discovery: учёт источника кандидата (какой поисковик первым нашёл домен).
-- Нужно, чтобы со временем оценить вклад провайдеров (Serper/Brave/manual) и
-- понять, стоит ли держать резервный платный API:
--   SELECT first_provider, count(*) FROM candidate_sources GROUP BY first_provider;
-- first_query — по какому шаблону запроса домен впервые нашёлся (тюнинг QUERY_TEMPLATES).

ALTER TABLE candidate_sources
    ADD COLUMN IF NOT EXISTS first_provider text,
    ADD COLUMN IF NOT EXISTS first_query    text;

COMMENT ON COLUMN candidate_sources.first_provider IS 'serper | brave | duckduckgo | manual';
COMMENT ON COLUMN candidate_sources.first_query IS 'Поисковый запрос, по которому домен найден впервые';
