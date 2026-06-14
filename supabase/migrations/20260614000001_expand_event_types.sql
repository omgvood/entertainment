-- Расширяем events_type_check: добавляем типы MVP-2 (concert, theater, exhibition,
-- festival, quest, party, cinema, sport, education, business, art, kids, food, trip,
-- hobby, science, other), которые уже есть в Python EventType в models.py.
-- Текущий constraint допускал только: quiz, standup, bowling, billiards, karting.
ALTER TABLE events
  DROP CONSTRAINT IF EXISTS events_type_check;

ALTER TABLE events
  ADD CONSTRAINT events_type_check CHECK (type IN (
    'quiz', 'standup', 'bowling', 'billiards', 'karting',
    'concert', 'theater', 'exhibition', 'festival', 'quest', 'party',
    'cinema', 'sport', 'education', 'business', 'art', 'kids', 'food', 'trip', 'hobby', 'science',
    'other'
  ));
