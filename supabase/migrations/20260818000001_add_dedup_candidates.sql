-- dedup_candidates — пары похожих событий, найденные fuzzy-скорером (Dedup v2, слой 2).
-- Две задачи: аудит auto-merge («что и почему схлопнули») и материал для калибровки
-- порогов по серой зоне. Ежедневный пайплайн только пишет сюда, решений не принимает.
-- resolution/resolved_* заведены заранее и всегда NULL: когда появится разрешатель
-- кандидатов (LLM или человек), он не потребует миграции.

CREATE TABLE IF NOT EXISTS dedup_candidates (
    id            bigserial PRIMARY KEY,
    city          text        NOT NULL,
    event_date    text        NOT NULL,
    event_id_a    text        NOT NULL,   -- всегда лексикографически меньший из пары
    event_id_b    text        NOT NULL,
    title_a       text        NOT NULL,
    title_b       text        NOT NULL,
    source_a      text        NOT NULL,
    source_b      text        NOT NULL,
    venue_a       text,
    venue_b       text,
    time_a        text,
    time_b        text,
    score         numeric(4,3) NOT NULL,
    title_score   numeric(4,3) NOT NULL,
    venue_score   numeric(4,3) NOT NULL,
    reason        text        NOT NULL,   -- ok / time_mismatch / no_supporting_signals
    decision      text        NOT NULL,   -- auto_merge (схлопнули) / candidate (оставили врозь)
    resolution    text,                   -- duplicate / different — заполнит будущий разрешатель
    resolved_at   timestamptz,
    resolved_by   text,
    first_seen_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT dedup_candidates_pair_unique UNIQUE (event_id_a, event_id_b)
);

CREATE INDEX IF NOT EXISTS dedup_candidates_city_date_idx
    ON dedup_candidates (city, event_date);

-- Доступ только service_role (парсер). RLS без политик = закрыто для anon/authenticated.
ALTER TABLE dedup_candidates ENABLE ROW LEVEL SECURITY;
