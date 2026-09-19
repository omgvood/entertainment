-- Чистка накопленных не-событий (новости/объявления/промо/розыгрыши) от social-источников.
--
-- Контекст. На /perm около четверти карточек type='other' оказались не событиями: новости
-- городского паблика permactive («Пермь Активная»), розыгрыши, промокоды, голосования, open call.
-- VK-префильтр был всегда мягким (SOCIAL), batch-промпт требовал «вернуть ВСЕ события».
-- Приток перекрыт в коде: vk_source_types (permactive → aggregator), NON_EVENT_INSTRUCTIONS
-- в batch-промптах, постфильтр validator.is_non_event (guard в to_event_row).
--
-- Удаление по явному списку id, подтверждённому пользователем по dry-run 2026-09-18:
--   A — строки, которые ловит предикат validator._NON_EVENT_TITLE_RE (тот же набор маркеров);
--   B — разовая дочистка известных не-событий, которые постфильтр намеренно не ловит
--       (широкие маркеры «парковк»/«появится»): их приток закрывают префильтр и промпт.
-- Список A не ограничен городом/типом — предикат поймал и одну строку из Сочи (розыгрыш массажа),
-- подтверждена пользователем к удалению вместе с остальными.
DELETE FROM events
WHERE id IN (
  -- A: предикат постфильтра
  'perm-open-call-na-13-sezon-rezidentsii-maxart-x-permm-2026-10-14',  -- Open call на 13 сезон резиденции MaxArt x ПЕРММ
  'perm-v-gosdume-predlozhili-otkryvat-v-detsadah-vechernie-gruppy-po-prosbe-roditeley-2027-01-01',  -- В Госдуме предложили открывать в детсадах вечерние группы по просьбе родителей
  'perm-v-permi-dvizhenie-po-vtoroy-ocheredi-sredney-damby-planiruyut-otkryt-18-oktyabry-2026-10-18',  -- В Перми движение по второй очереди Средней дамбы планируют открыть 18 октября
  'perm-golosovanie-za-nominantov-natsionalnoy-turisticheskoy-premii-russian-traveler-aw-2026-10-30',  -- Голосование за номинантов Национальной туристической премии Russian Traveler Awards 2026
  'perm-grazhdanin-meksiki-pod-arestom-po-delu-o-narkotikah-2026-10-08',  -- Гражданин Мексики под арестом по делу о наркотиках
  'perm-kapitalnyy-remont-puteprovoda-na-ulitse-promyshlennoy-127-2026-09-20',  -- Капитальный ремонт путепровода на улице Промышленной, 127
  'perm-maksim-iz-krasnokamska-v-teleproekte-zhduli-2026-09-17',  -- Максим из Краснокамска в телепроекте «Ждули»
  'perm-otslezhivanie-tsen-na-produkty-2027-01-01',  -- Отслеживание цен на продукты
  'perm-rozygrysh-metallicheskoy-dveri-arkan-206-2026-11-09',  -- Розыгрыш металлической двери Аркан 206
  'perm-spetsialnoe-predlozhenie-ot-seti-pitstseriy-pitstsburg-2026-09-30',  -- Специальное предложение от сети пиццерий «Пиццбург»
  'sochi-rozygrysh-avtorskiy-massazh-litsa-na-ispanskoy-kosmetike-ot-premium-klinike-epil-2026-09-25',  -- РОЗЫГРЫШ! Авторский массаж лица на испанской косметике от премиум-клинике Epilate Me!
  -- B: дочистка вне предиката
  'perm-besplatnye-parkovki-na-vremya-vyborov-2026-09-18',  -- Бесплатные парковки на время выборов
  'perm-besplatnye-parkovki-na-vremya-vyborov-2026-09-19',  -- Бесплатные парковки на время выборов
  'perm-besplatnye-parkovki-na-vremya-vyborov-2026-09-20',  -- Бесплатные парковки на время выборов
  'perm-na-kame-poyavitsya-novoe-passazhirskoe-sudno-2028-07-01'   -- На Каме появится новое пассажирское судно
)
RETURNING id, title, source, city, type;

-- Проверка после применения: SELECT по этому же списку id должен вернуть 0 строк.
