-- Шаг 7: coverage_stats — ежедневный снимок покрытия по категориям (Analytics)
-- Позволяет видеть тренды и замечать выпадение категорий (квизы упали с 25 до 2 → сломался источник).

CREATE TABLE IF NOT EXISTS coverage_stats (
    city          text,
    category      text,        -- EventType
    count         int,
    snapshot_date date DEFAULT current_date,
    PRIMARY KEY (city, category, snapshot_date)
);

-- Доступ только service_role (парсер). RLS без политик = закрыто для anon/authenticated.
ALTER TABLE coverage_stats ENABLE ROW LEVEL SECURITY;
