-- Шаг 5: source_health — мониторинг источников (Analytics)
-- source_health     — лог каждого запуска источника
-- source_health_agg — агрегат на источник для быстрого дашборда «что сломалось»

CREATE TABLE IF NOT EXISTS source_health (
    source       text,
    city         text,
    run_at       timestamptz DEFAULT now(),
    events_found int  DEFAULT 0,
    errors       int  DEFAULT 0,
    duration_sec numeric,
    last_error   text,
    PRIMARY KEY (source, city, run_at)
);

CREATE TABLE IF NOT EXISTS source_health_agg (
    source       text,
    city         text,
    last_success timestamptz,
    last_run     timestamptz,
    avg_events   numeric,
    success_rate numeric,        -- доля успешных запусков (errors = 0)
    total_errors int,
    PRIMARY KEY (source, city)
);

-- Доступ только service_role (парсер). RLS без политик = закрыто для anon/authenticated.
ALTER TABLE source_health ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_health_agg ENABLE ROW LEVEL SECURITY;
