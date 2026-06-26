-- Чистка накопленных spurious date='always' от social/generic-источников.
--
-- Контекст. Миграция 20260624000001 удалила 'always' только у twogis-% (это площадки → venues),
-- намеренно оставив vk-posts / telegram-posts «до отдельного разбора». Разбор показал: LLM ставит
-- 'always' постам VK/Telegram/generic без явной даты (анонсы выставок/фестивалей/«каждую пятницу»).
-- Это не площадки, а галлюцинация даты — фронт их скрывает, в БД они копятся.
--
-- Теперь приток перекрыт в коде (промпт-правило + постфильтр pipeline + guard в validator), а здесь
-- вычищаем уже накопленное. Площадки (bowling/billiards/karting/quest) исключаем — у generic-домена
-- постоянного места 'always' легитимен. Свежие записи (< 1 дня) не трогаем — защита от гонки с
-- параллельным прогоном парсера. parsed_at кастуем в timestamptz (колонка хранит ISO-строку).
DELETE FROM events
WHERE date = 'always'
  AND (
    source LIKE 'vk-%'
    OR source LIKE 'telegram-%'
    OR source LIKE 'generic:%'
    OR source = 'generic'
  )
  AND type NOT IN ('bowling', 'billiards', 'karting', 'quest')
  AND parsed_at::timestamptz < NOW() - INTERVAL '1 day'
RETURNING id, title, source, type, parsed_at;

-- Проверка после применения (ожидаем только twogis-venues, если что-то осталось):
--   SELECT COUNT(*), source FROM events WHERE date = 'always' GROUP BY source;
