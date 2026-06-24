-- Постоянные места 2ГИС (date='always', source twogis-*) переезжают из events в venues.
-- Парсер 2ГИС (direct_api) теперь пишет площадки напрямую в venues — это и было дублированием:
-- те же 27 (Пермь) / 40 (Сочи) карточек лежали и в events, и в venues.
-- venues — source of truth для фронта (VenuesSection + /venues/).
--
-- НАМЕРЕННО НЕ трогаем date='always' из vk-posts / telegram-posts: это НЕ площадки, а анонсы
-- событий без конкретной даты (выставки/фестивали/концерты). Их судьба — отдельный разбор
-- (почему экстрактор ставит 'always'); до этого они просто скрыты из грида фронтом.
DELETE FROM events WHERE date = 'always' AND source LIKE 'twogis-%';
