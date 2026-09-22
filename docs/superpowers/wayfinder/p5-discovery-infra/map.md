# Карта: инфраструктура Discovery — DuckDuckGo

Label: wayfinder:map
Status: активен
Эффорт: p5-discovery-infra · Трекер: локальный markdown (`docs/superpowers/wayfinder/p5-discovery-infra/`)
Заведена 2026-09-22 по итогам вопроса «какие нужны доработки по бэкенду» — известный, но не заведённый баг Discovery.

## Destination

DuckDuckGo как поисковый провайдер Discovery либо снова работает (находит кандидатов, `discovery-health` видит приток от него), либо явно и осознанно выведен из `SEARCH_PROVIDERS`/кода — в любом случае решение зафиксировано, а не остаётся молчаливым обходом через ручное наполнение `candidate_sources`.

## Текущая волна

| Тикет | Тип | Статус |
|---|---|---|
| [DuckDuckGo Discovery сломан (202-ответы)](issues/01-duckduckgo-discovery-broken.md) | task | open |

Один тикет — сразу вся волна: причина уже известна (202-ответы), это доводка через `systematic-debugging`, а не многошаговая разведка, поэтому карта минимальна.

## Decisions so far

<!-- заполняется после закрытия тикета -->

## Not yet specified

- Если DuckDuckGo решено чинить — конкретный способ (заголовки/retry/другой эндпоинт) станет ясен только внутри тикета 01, туман не расписывается заранее.

## Out of scope

- Остальные поисковые провайдеры (`serper`, `brave`) — не сломаны, в эту карту не входят.

## Notes

- **Домен:** Discovery-пайплайн парсера (`parser/src/parser/discovery/`, `candidate_sources.py`), не связан с покрытием категорий из [p4-coverage-expansion](../p4-coverage-expansion/map.md).
- **Источник:** известная проблема, зафиксированная в памяти сессий («DuckDuckGo Discovery сломан (202), candidate_sources наполняется вручную»), впервые оформлена как тикет 2026-09-22.
- Локализация обязательна до первой правки (`CLAUDE.md`) — грепом по символу (`duckduckgo`/имя клиента) и по значению (строка провайдера в `SEARCH_PROVIDERS`), результат в `## Answer`.
