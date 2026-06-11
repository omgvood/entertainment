-- Шаг 6: fingerprint для кросс-источниковой дедупликации
-- НЕ UNIQUE намеренно: сначала собираем статистику дублей (duplicate_candidates),
-- constraint вводим позже, когда увидим реальные коллизии.
-- Хеш считается из normalize(title)+date+normalize(venue) в parser/src/parser/validator.py

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS fingerprint text;

CREATE INDEX IF NOT EXISTS events_fingerprint_idx ON events (fingerprint);
