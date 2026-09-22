# endDate филармонии: шаблон или факт

Type: research
Скилл: mattpocock-skills:research — ответ на страницах сайта, а не в коде
Status: resolved
Blocked by: —
Ветка: `research/filarmonia-endtime`

## Question

У всех 31 события `generic:filarmonia.online` длительность ровно 180 минут (15:00–18:00, 19:00–22:00). Это реальное время окончания или шаблон в разметке сайта?

## Контекст

- `time_end` приходит из JSON-LD: `extract_jsonld_events` берёт `endDate` (`parser/src/parser/extraction/jsonld.py:130`).
- Настоящий `time_end` есть только у 41 события VK; филармония удваивает покрытие — или портит его.
- От ответа зависит политика «идёт сейчас» (тикет 06): с филармонией покрытие 20%, без неё 11%.

## Как перевести в белое

Открыть 3–5 страниц событий filarmonia.online, посмотреть JSON-LD (`startDate` / `endDate`) и сверить с тем, что написано на странице для человека. Заодно проверить `teatr-teatr.com` и `permm`, раз они ходят тем же путём.

## Готово когда

В ответе тикета — вердикт «шаблон» или «реальные данные» со ссылками на проверенные страницы и рекомендация: использовать `time_end` этого источника, игнорировать его или помечать как ненадёжный.

## Answer

Локализация: `grep -r "endDate|extract_jsonld_events" parser/` → 5 мест (`parser/src/parser/pipeline.py`, `sources/generic.py`, `extraction/jsonld.py`, `extraction/__init__.py`, `tests/test_jsonld.py`); `grep -r "filarmonia|teatr-teatr|permm" .` → 25 мест, найдено N=30.

**Вердикт: шаблон.** `generic:filarmonia.online` парсит только страницу-листинг (`https://filarmonia.online/afisha`, читает её `parser/src/parser/sources/generic.py:161-182` через `resolve_listing_url`/`extract_jsonld_events`, на страницы отдельных событий не заходит). JSON-LD листинга отдаёт `endDate` строго `startDate + 180 минут` (15:00→18:00 либо 19:00→22:00) для всех событий без исключения — без поля `duration`.

Прямое доказательство на одном и том же событии («Экскурсия «Органное закулисье»», 2026-09-24, 19:00):
- листинг (`/afisha`): `endDate = 2026-09-24T22:00:00+05:00` (шаблонные +3ч), поля `duration` нет;
- страница самого события (`/afisha/jekskursija-organnoe-zakulise-24-09-2026.html`): `endDate = 2026-09-24T20:30:00+05:00`, `duration = "PT1H30M"` — реальные полтора часа.

То же самое расхождение на других проверенных событиях (страница события, реальная длительность из явного `duration`):
- «Мультконцерт» (20.09, 15:00): `duration = PT2H` → 17:00, а не 18:00 из листинга.
- «Вечер при свечах» (20.09, 19:00): `duration = PT1H30M` → 20:30, а не 22:00 из листинга.

`teatr-teatr.com` — вопрос неприменим: `candidate_sources.has_jsonld_event = false`, извлечение идёт через LLM, JSON-LD `Event`/`@type` на странице листинга (`/afisha/`) нет вообще (`document.querySelectorAll('script[type="application/ld+json"]')` → `[]`). В БД у всех 14 событий этого источника `time_end IS NULL` — шаблона нет, потому что нет и `endDate` как такового.

`permm` — вопрос неприменим по коду: `parser/src/parser/sources/permm.py` вообще не читает и не пишет `time_start`/`time_end` (в `_map_item` их нет среди полей `ParsedEvent`), источник — открытые JSON-эндпоинты (`/json/exhibitions/active`, `/json/events/sub/home`), не JSON-LD.

**Рекомендация:** `time_end` источника `generic:filarmonia.online`, полученный с листинга, — шаблонный артефакт разметки, не факт. Использовать его для «идёт сейчас» (тикет 06) нельзя. Дешёвый вариант — не читать `endDate` для этого домена (оставлять `time_end = None`), дорогой — добавить отдельный fetch страницы события ради поля `duration`/`endDate` (доп. запрос на каждое событие, вне generic-модели «одна страница на домен»). Для teatr-teatr и permm действие не требуется — у них `time_end` уже отсутствует по факту, а не по шаблону.
