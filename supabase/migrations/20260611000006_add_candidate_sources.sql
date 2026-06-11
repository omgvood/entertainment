-- Шаг 3: candidate_sources — кандидаты в источники (Discovery)
-- Поиск по типовым запросам → скоринг → ручная модерация (new → approved → seeds.yaml / rejected).

CREATE TABLE IF NOT EXISTS candidate_sources (
    domain           text PRIMARY KEY,
    city             text,
    queries          text[] DEFAULT '{}',
    score            int DEFAULT 0,
    has_jsonld_event boolean DEFAULT false,
    status           text DEFAULT 'new',   -- new | approved | rejected
    found_at         timestamptz DEFAULT now(),
    last_seen        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS candidate_sources_status_idx ON candidate_sources (city, status);

-- Доступ только service_role (парсер/модерация). RLS без политик = закрыто для anon/authenticated.
ALTER TABLE candidate_sources ENABLE ROW LEVEL SECURITY;

-- Очистка мусора (необработанные кандидаты, давно не встречавшиеся):
--   DELETE FROM candidate_sources
--   WHERE status = 'new' AND last_seen < now() - interval '90 days';
