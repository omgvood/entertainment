-- source_quality — ценность источника (Analytics), отдельно от source_health.
-- source_health  отвечает на «работает ли источник» (ошибки, success_rate).
-- source_quality отвечает на «стоит ли его держать»: сколько событий уникальны,
-- а сколько дублируют другие источники (проигрывают в кросс-источниковом merge).
-- Снимок по дням (как coverage_stats) — видно тренд ценности источника во времени.

CREATE TABLE IF NOT EXISTS source_quality (
    source              text,
    city                text,
    snapshot_date       date,
    events_found        int     DEFAULT 0,  -- извлечено в прогоне (до merge)
    unique_events       int     DEFAULT 0,  -- не проиграли merge другому источнику
    unique_events_ratio numeric,            -- unique_events / events_found
    PRIMARY KEY (source, city, snapshot_date)
);

-- Доступ только service_role (парсер). RLS без политик = закрыто для anon/authenticated.
ALTER TABLE source_quality ENABLE ROW LEVEL SECURITY;
