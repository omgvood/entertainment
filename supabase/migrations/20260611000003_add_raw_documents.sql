-- Шаг 4: raw_documents — сырьё (Ingestion)
-- Хранит сырой HTML/JSON/XML/RSS, чтобы менять промпты/модели/теги без повторного краулинга.
-- Заменяет parse_state как место хранения хеша для дедупа batch_listing.
-- Сжатие — на стороне Postgres TOAST (text), TTL — 90-180 дней (cleanup_old_raw_documents).

CREATE TABLE IF NOT EXISTS raw_documents (
    id           uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    source       text,
    url          text UNIQUE,
    content      text,
    content_type text DEFAULT 'html',   -- html | json | xml | rss
    hash         text,
    fetched_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS raw_documents_fetched_at_idx ON raw_documents (fetched_at);

-- Доступ только service_role (парсер). RLS без политик = закрыто для anon/authenticated.
ALTER TABLE raw_documents ENABLE ROW LEVEL SECURITY;

-- parse_state больше не используется парсером (хеш переехал в raw_documents).
-- Таблицу можно удалить вручную после первого успешного прогона на новой схеме:
--   DROP TABLE IF EXISTS parse_state;
