-- Шаг 1: теги событий + версия таксономии
-- tags     — закрытый набор тегов для подборок/рекомендаций (см. parser/src/parser/taxonomy.py)
-- tags_version — версия таксономии, с которой событие извлечено (для перепарса при смене набора)

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS tags         text[] NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS tags_version int    NOT NULL DEFAULT 1;

-- GIN-индекс для будущих подборок «события с тегом X»
CREATE INDEX IF NOT EXISTS events_tags_idx ON events USING gin (tags);
