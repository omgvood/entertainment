# Skills routing

Бэкбон в этом репозитории — `superpowers` (`brainstorming` → `writing-plans` → `subagent-driven-development`/`executing-plans`, TDD и verification уже зашиты в план). Из `mattpocock-skills` точечно заимствуются `wayfinder` и `research` — под задачи, которых в superpowers нет. Остальной конвейер mattpocock (`grill-with-docs`, `/to-spec`, `/to-tickets`, `/implement`, `/triage`) в этом репозитории не используется.

Перед началом задачи: определи строку по таблице, назови скилл и путь для артефактов вслух, с обоснованием. Неочевидно, какая строка — спроси, не выбирай сам.

| Тип задачи | Скилл | Куда сохраняется |
|---|---|---|
| Известный баг, «чтобы работало» | `systematic-debugging` → `test-driven-development` → фикс → `verification-before-completion` | код + тест, без отдельного файла |
| Самопроизвольно найденный баг (UI, данные, архитектура) | локализация + исследование → handoff → откатить → завести тикет → Сценарий 1 | `HANDOFF_<название>.md` (temp) + тикет в wayfinder |
| Полировка / рефакторинг без смены поведения | есть развилка → `brainstorming` (bounded); дальше `simplify` | код |
| Фича, границы ясны, одна сессия | `brainstorming` bounded (дизайн в чате) → реализация с TDD | код |
| Фича, нужен спек и план, несколько сессий | `brainstorming` architectural → `writing-plans` → `subagent-driven-development`/`executing-plans` | `docs/superpowers/specs/`, `docs/superpowers/plans/` |
| Туманная задача, много связанных проблем | `mattpocock-skills:wayfinder` → сведение (3–7 проблем, одна волна) → дальше по строке выше | `docs/superpowers/wayfinder/<эффорт>/map.md` + `issues/` — `map.md` начинается со строки `Status: активен`/`закрыт`, чтобы отличать открытые эффорты от завершённых; тикеты пишутся по `docs/superpowers/wayfinder/_ticket-template.md` |
| Исследование области с целью собрать факты | `mattpocock-skills:research` или `brainstorming` | `docs/research/` |
| Нужны факты из внешнего источника (API, условия использования, формат стороннего сервиса) | `mattpocock-skills:research` | `docs/research/` |
| Ревью ветки/PR перед мерджем | `code-review` | — |
| Конфликт merge/rebase | `resolving-merge-conflicts` | — |
| Проблема про способ работы, а не про код: «с чего начать», «что дальше», аудит закрытой волны, разбор выполненной сессии, выявление нарушений R-01…R-06 | `process-review` — **вне git**, пользовательский скилл в `~/.claude/skills/`: обслуживает процессы за пределами этого репозитория; используется после рабочей сессии (ревью PR) или при выявлении нарушений | — (вердикт текстом, скилл только читает) |

## docs/ в этом репозитории

- `docs/agents/` — правила для агента и разбор, откуда они взялись (этот файл,
  `session-protocol.md`, `process-journal.md`). Трекается.
- `docs/superpowers/` — результаты работы скиллов (specs, plans, wayfinder). Трекается.
- `docs/research/` — выкладки `research` с цитатами первоисточника. Трекается.
- `docs/personal/` — личные заметки и черновики, не относящиеся к работе агента. Не трекается (`.gitignore`).

Всё, что попадает в `docs/` мимо этих четырёх папок, в git не увидит никто — это сигнал класть файл в `docs/personal/`, а не в корень `docs/`.

Любой путь, названный в этом файле или в `CLAUDE.md`, обязан существовать на диске: `CLAUDE.md` месяцами ссылался на `.scratch/`, которого никогда не было, и расхождение было молчаливым. Путь наружу репозитория допустим только с пометкой «вне git» и причиной рядом — R-06 в `session-protocol.md`.

Порядок работы сессии — `docs/agents/session-protocol.md`: сверка состояния, уборка веток и
worktree, размер волны, проверка путей, последовательность из девяти шагов, таблица сигналов
и шаблон открытия чата по тикету. Разбор инцидентов, из которых правила выросли, —
`docs/agents/process-journal.md`.
