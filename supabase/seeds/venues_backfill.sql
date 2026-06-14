-- Одноразовый перенос постоянных мест из events в venues.
-- Контекст: таблица venues (миграция 20260613000002) была пуста, а постоянные места 2ГИС
-- лежали в events с date='always'. refresh_venues.yml (cron 1,15) ещё не отрабатывал — это его
-- работа в дальнейшем; здесь — первичное наполнение из уже собранных данных.
--
-- Берём только twogis-источники (реальные площадки). vk-posts с date='always' (concert/trip/other)
-- — это события, а не площадки, поэтому исключены фильтром source LIKE 'twogis-%'.
--
-- Идемпотентно: DO UPDATE перезаписывает строки при повторном применении, но НЕ трогает
-- source='manual' (тот же инвариант, что в db.upsert_venues — ручной ввод приоритетен).

INSERT INTO venues (id, city, name, type, address, district, image_url, source, updated_at)
SELECT id, city, venue_name, type, address, district, image_url, 'twogis', now()
FROM events
WHERE date = 'always' AND source LIKE 'twogis-%'
ON CONFLICT (id) DO UPDATE SET
  name       = EXCLUDED.name,
  type       = EXCLUDED.type,
  address    = EXCLUDED.address,
  district   = EXCLUDED.district,
  image_url  = EXCLUDED.image_url,
  source     = EXCLUDED.source,
  updated_at = EXCLUDED.updated_at
WHERE venues.source IS DISTINCT FROM 'manual';
