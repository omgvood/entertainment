-- Тестовые события для Сочи
-- Выполнить в Supabase SQL Editor или через CLI:
--   supabase db push

INSERT INTO events (city, slug, title, type, date, time_start, price_min, price_max, price_text, price_note, address, venue_name, source_url, source, parsed_at, meta_title, meta_description) VALUES

('sochi', 'quizplease-klassika-sochi-2026-06-07', 'QuizPlease «Классика» в Сочи', 'quiz', '2026-06-07', '19:00', 800, 1500, 'от 800 до 1 500 ₽', 'за команду', 'ул. Навагинская, 16, Сочи', 'Бар «Нулевой меридиан»', 'https://quizplease.ru', 'manual', NOW(), 'QuizPlease Классика в Сочи — квиз 7 июня', 'Квиз QuizPlease Классика в Сочи 7 июня. от 800 до 1 500 ₽ за команду. ул. Навагинская, 16.'),

('sochi', 'mozgo-igry-razuma-sochi-2026-06-10', 'Мозгобойня «Игры разума» в Сочи', 'quiz', '2026-06-10', '19:30', 500, 700, 'от 500 до 700 ₽', NULL, 'ул. Горького, 32, Сочи', 'Лофт «Портовый»', 'https://mozgoboynya.ru', 'manual', NOW(), 'Мозгобойня в Сочи — квиз 10 июня', 'Квиз Мозгобойня Игры разума в Сочи 10 июня. от 500 до 700 ₽.'),

('sochi', 'standup-otkrytyj-mikrofon-sochi-2026-06-05', 'Открытый микрофон в Sochi Comedy Club', 'standup', '2026-06-05', '20:00', 400, 600, 'от 400 до 600 ₽', NULL, 'ул. Советская, 22, Сочи', 'Sochi Comedy Club', 'https://afisha.yandex.ru', 'manual', NOW(), 'Стендап открытый микрофон Сочи — 5 июня', 'Открытый микрофон стендап в Сочи 5 июня. от 400 до 600 ₽.'),

('sochi', 'bowling-sochi-park-always', 'Боулинг «Sochi Park»', 'bowling', 'always', NULL, 400, 800, 'от 400 до 800 ₽', 'за дорожку/час', 'Олимпийский проспект, 21, Сочи', 'Sochi Park', 'https://sochipark.ru', 'manual', NOW(), 'Боулинг в Сочи — Sochi Park', 'Боулинг в Сочи в Sochi Park. от 400 до 800 ₽ за дорожку/час. Олимпийский проспект, 21.'),

('sochi', 'billiard-master-sochi-always', 'Бильярдный клуб «Master»', 'billiards', 'always', NULL, 300, 500, 'от 300 до 500 ₽', 'за стол/час', 'ул. Орджоникидзе, 10, Сочи', 'Master Billiards', 'https://2gis.ru', 'manual', NOW(), 'Бильярд в Сочи — клуб Master', 'Бильярд в Сочи клуб Master. от 300 до 500 ₽ за стол/час. ул. Орджоникидзе, 10.'),

('sochi', 'karting-formula-sochi-always', 'Картинг «Formula Sochi»', 'karting', 'always', NULL, 600, 1200, 'от 600 до 1 200 ₽', 'за заезд', 'ул. Ленина, 100, Сочи', 'Formula Sochi Karting', 'https://2gis.ru', 'manual', NOW(), 'Картинг в Сочи — Formula Sochi', 'Картинг в Сочи Formula Sochi. от 600 до 1 200 ₽ за заезд. ул. Ленина, 100.')

ON CONFLICT (slug) DO UPDATE SET
  title = EXCLUDED.title,
  parsed_at = EXCLUDED.parsed_at;
