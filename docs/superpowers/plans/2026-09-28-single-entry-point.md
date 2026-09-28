# Единая точка входа в сессию — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** любая сессия entertainment открывается одним файлом `_next-session.md`, у каждого факта процесса один источник в репозитории.

**Architecture:** постоянный протокол входа — новый раздел в `docs/agents/session-protocol.md`; изменчивое — `_next-session.md` из четырёх блоков; `CLAUDE.md` получает одну строку-указатель. Obsidian и память агента (вне git) сводятся к указателям.

**Tech Stack:** Markdown, git, `gh`, bash (Git Bash на Windows).

**Spec:** `docs/superpowers/specs/2026-09-28-single-entry-point-design.md`

## Global Constraints

- Источник истины — только репозиторий; Obsidian — указатель и архив.
- В Obsidian ничего не удаляется: только новая заметка и строка «АРХИВ» первой строкой.
- В PR не попадает `docs/research/2026-09-24-site-audit.md`.
- Ветка `docs/single-entry-point`; `git branch --show-current` отдельным шагом перед каждым `git add`.
- Пуш и PR — только с явного согласия пользователя.
- Коммиты заканчиваются строкой `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Пользователь пишет внеплановое не дословно «вместо этого: …», а «сначала глянь баг X» — ожидается внеплановая ветка. Правило формулируется как «любой текст сверх файла, меняющий задачу», проверка — шаг 1.4.
2. Пользователь не приложил файл вовсе («продолжаем») — агент читает `_next-session.md` сам. Проверка — шаг 3.4.
3. Две параллельные ветки правят `_next-session.md` — конфликт. Протокол прямо запрещает правку внутри ветки тикета. Проверка — шаг 1.4.
4. `master` получил коммит мимо PR (INC-14) — «Базовая линия» расходится с `git log`. Протокол предписывает стоп. Проверка — шаг 1.4.
5. OneDrive синхронизирует vault во время правки — правка Obsidian только дописывает строку в начало, содержимое не переписывается. Проверка — шаг 5.5.

---

### Task 1: Раздел «Вход в сессию» в `session-protocol.md`

**Files:**
- Modify: `docs/agents/session-protocol.md` (вставка после строки 7, удаление раздела `## Шаблон открытия чата по тикету`, строки 115–132; висящая правка шага 7 уже в рабочей копии)
- Commit also: `docs/superpowers/specs/2026-09-28-single-entry-point-design.md` (правка спека про копии шаблона), этот план

**Interfaces:**
- Produces: заголовок `## Вход в сессию` и подзаголовок `### Шаблон открытия чата по тикету` — на них ссылаются Task 2 (`_next-session.md`), Task 3 (`CLAUDE.md`, `skills-routing.md`), Task 5–6 (Obsidian, память).

- [ ] **Шаг 1.1: Базовая линия проверок (до правки)**

```bash
cd /c/Python/entertainment
grep -rl "Отметь, какую ветку" docs/agents docs/superpowers/wayfinder CLAUDE.md
grep -n "Сценарий 1\|HANDOFF\|(temp)" docs/agents/session-protocol.md docs/agents/skills-routing.md
grep -c "^## Вход в сессию" docs/agents/session-protocol.md
```

Ожидается: первая — `docs/agents/session-protocol.md`; вторая — `skills-routing.md:10` (это и чиним в Task 3); третья — `0`.

- [ ] **Шаг 1.2: Вставить раздел после вводного абзаца (после строки 7 «…почему правило такое».)**

Вставить ровно этот текст (пустая строка до и после):

````markdown
## Вход в сессию

Сессия открывается одним файлом — `docs/superpowers/wayfinder/_next-session.md`. В нём только изменчивое: базовая линия, следующий шаг, стоп-условия этого шага, отложенное. Всё постоянное — здесь.

1. **Сверка.** Команды R-01 (ниже) и сравнение с «Базовой линией» `_next-session.md`: коммит `master`, числа тестов. Расхождение — стоп и вопрос, до всего остального.
2. **Развилка.**
   - На входе только файл → выполняется его «Следующий шаг».
   - Файл и любой текст, меняющий задачу («вместо этого: <симптом>», «сначала глянь баг…») → **внеплановая ветка**: локализация по R-02 (`CLAUDE.md`), ни одной правки кода. Результат — тикет со `Status: backlog` в подходящей карте по `docs/superpowers/wayfinder/_ticket-template.md`: root cause, неудачные попытки и варианты решения — в `Question`, `Контекст`, `Кто зависит`. Отдельного handoff-файла нет. Подходящей карты нет — вопрос пользователю, новая карта только с его согласия. Затем вопрос: брать тикет сейчас (тогда «Следующий шаг» уходит в «Отложено» `_next-session.md`) или оставить до сведения.
3. **Сценарий** определяет скилл и то, чем сессия заканчивается:

| Сценарий | Когда | Скилл | Чем заканчивается |
|---|---|---|---|
| Тикет из волны | «Следующий шаг» — тикет со `Status: open` | строка `Скилл:` тикета | `## Answer`, строка в Decisions so far карты, PR |
| Внеплановое | текст сверх файла меняет задачу | по `skills-routing.md`; до тикета — без правок кода | тикет `Status: backlog` и решение пользователя, брать ли сейчас |
| Исследование → сведение | «Следующий шаг» — сведение или аудит волны | `mattpocock-skills:research` или `brainstorming`; само сведение — без скилла | отчёт в `docs/research/`, экран сведения, волна по выбору пользователя, тикеты только этой волны |

4. **Выход.** `## Answer` в тикете → строка в карте → PR (пуш только с согласия) → после мерджа уборка R-04 → переписать `_next-session.md` отдельным docs-коммитом в `master` (шаг 7 последовательности). Внутри ветки тикета `_next-session.md` не правится: параллельные ветки дадут конфликт.

### Шаблон открытия чата по тикету

Когда «Следующий шаг» — тикет, `_next-session.md` называет его путь; сессия действует так, как если бы получила этот промпт:

```
Возьми тикет docs/superpowers/wayfinder/<эффорт>/issues/<файл>.md
Карта: docs/superpowers/wayfinder/<эффорт>/map.md
Порядок работы: docs/agents/session-protocol.md, локализация — по CLAUDE.md.

Скилл в шапке тикета: <имя>.
До первой правки сделай собственный греп по символу и по значению,
результат запиши строкой «Локализация: <команда>, найдено N мест» в ## Answer.

В конце: ## Answer в тикет и строка в Decisions so far карты.
Без моего согласия не пушить.

Отметь, какую ветку ты получил.
```

Обновлено после волны 1 — это промпт, которым реально открывалась сессия тикета 02. Прежняя версия не называла ни скилл, ни локализацию, а R-02 проверяется самоотчётом: если промпт о нём не напоминает, правило держится только на том, вспомнит ли сессия строку из `CLAUDE.md`. Строка «отметь, какую ветку ты получил» — дешёвый способ увидеть в первом же ответе, завёл ли харнесс свою `claude/*` ветку (Q6).
````

- [ ] **Шаг 1.3: Удалить старый раздел `## Шаблон открытия чата по тикету`** (от заголовка до строки перед `## Аудит в конце волны`, включительно с абзацем «Обновлено после волны 1…»). Текст уже перенесён шагом 1.2.

- [ ] **Шаг 1.4: Проверить**

```bash
grep -c "^## Вход в сессию" docs/agents/session-protocol.md          # 1
grep -c "^## Шаблон открытия чата" docs/agents/session-protocol.md   # 0
grep -c "Отметь, какую ветку" docs/agents/session-protocol.md        # 1
grep -n "любой текст, меняющий задачу" docs/agents/session-protocol.md   # Review Focus 1
grep -n "Внутри ветки тикета \`_next-session.md\` не правится" docs/agents/session-protocol.md  # Review Focus 3
grep -n "Расхождение — стоп и вопрос" docs/agents/session-protocol.md    # Review Focus 4
grep -n "_next-session.md\` под следующую задачу" docs/agents/session-protocol.md  # правка шага 7 на месте
```

Каждая строка даёт ровно одно совпадение (или число из комментария).

- [ ] **Шаг 1.5: Коммит**

```bash
git branch --show-current   # docs/single-entry-point
git add docs/agents/session-protocol.md docs/superpowers/specs/2026-09-28-single-entry-point-design.md docs/superpowers/plans/2026-09-28-single-entry-point.md
git commit -m "docs(agents): раздел «Вход в сессию» — развилка план/внеплан, сценарии, шаблон

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `_next-session.md` в четыре блока

**Files:**
- Modify (сейчас не трекается): `docs/superpowers/wayfinder/_next-session.md` — полная замена содержимого

**Interfaces:**
- Consumes: `session-protocol.md` §«Вход в сессию» (Task 1).
- Produces: блоки `## Базовая линия`, `## Следующий шаг`, `## Стоп-условия`, `## Отложено` — их форму повторяет каждое следующее переписывание на шаге 7.

- [ ] **Шаг 2.1: Записать файл целиком**

````markdown
# Следующая сессия

Обновлено: 2026-09-28 — после спека единой точки входа (`docs/superpowers/specs/2026-09-28-single-entry-point-design.md`).
Протокол входа: `docs/agents/session-protocol.md` §«Вход в сессию». Этот файл содержит только изменчивое; переписывается на шаге 7 отдельным docs-коммитом в `master`, старую версию хранит git log.

## Базовая линия

- `master` = коммит мерджа PR `docs/single-entry-point` (до него — `55d341f`). Новее — перечислить новые коммиты и учесть их в сведении.
- `cd parser && python -m pytest -q` → 298 passed.
- `cd web && npx vitest run` → 115 passed (8 файлов).
- `docs/research/2026-09-24-site-audit.md` не отслеживается в git — спросить, коммитить ли его, до ссылок на него из карт.

## Следующий шаг

**Сведение** (шаг 3 последовательности). Код не правим, тикеты без выбора пользователя не пишем.

1. Прочитать целиком все `map.md` со `Status: активен` (p4–p8) и `docs/research/2026-09-24-site-audit.md` (особенно §5 «Связь с картами» и §6 «Сведение»).
2. Проверить 11 open-тикетов: p4/01–03, p5/01, p6/01–02, p7/01–03, p8/02–03. По каждому одна строка: актуален / уже сделан в `master` / перекрыт находкой аудита. Цифры аудита — снимок 2026-09-23/24; перепроверить хотя бы две: домен в `/sitemap.xml` живого сайта (1.1) и Timepad 403 в `source_health` (4.1). БД — только чтение через Supabase MCP.
3. Экран сведения: 3–7 проблем из open-тикетов и находок A–G аудита, у каждой строка «что не так» и метка (блокирует остальное / дёшево и независимо / дорого и спорно). Предложить волну из 1–3 задач и какие open-тикеты вернуть в backlog, чтобы открытых по всем картам стало не больше трёх (R-05).
4. После выбора пользователя — тикеты только выбранной волны по `_ticket-template.md`; новая карта — только с согласия. Затем переписать этот файл под первый тикет волны. Коммит docs — с согласия, без пуша.

**Готово когда:** пользователь выбрал волну; открытых тикетов ≤ 3; этот файл указывает на первый тикет волны. Отдельной строкой в итоге сессии: сработал ли вход одним файлом (первый ответ начался со сверки R-01 — да/нет).

## Стоп-условия

- Решение за пользователем: волна, новая карта, трактовка находки аудита.
- Цифры аудита не сходятся с БД или сайтом больше чем в одном пункте.
- Запись в БД, миграция, новая зависимость.

Вопросы — одним списком с рекомендацией по каждому.

## Отложено

—
````

- [ ] **Шаг 2.2: Проверить**

```bash
grep -c "^## \(Базовая линия\|Следующий шаг\|Стоп-условия\|Отложено\)$" docs/superpowers/wayfinder/_next-session.md   # 4
grep -c "git log --oneline origin/master..master\|Отметь, какую ветку" docs/superpowers/wayfinder/_next-session.md       # 0 — постоянное не дублируется
```

- [ ] **Шаг 2.3: Коммит**

```bash
git branch --show-current   # docs/single-entry-point
git add docs/superpowers/wayfinder/_next-session.md
git commit -m "docs(wayfinder): _next-session.md — четыре блока, вход в сведение

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `CLAUDE.md` и `skills-routing.md`

**Files:**
- Modify: `CLAUDE.md:19-21`
- Modify: `docs/agents/skills-routing.md:10`

**Interfaces:**
- Consumes: `## Вход в сессию` (Task 1), `_next-session.md` (Task 2).

- [ ] **Шаг 3.1: `CLAUDE.md`, раздел «Порядок работы» — строка перед существующим абзацем**

Было:

```markdown
## Порядок работы

Сверка состояния репозитория до старта, …
```

Стало:

```markdown
## Порядок работы

Вход в сессию — `docs/superpowers/wayfinder/_next-session.md`. Если пользователь его не приложил, прочитай сам до ответа.

Сверка состояния репозитория до старта, …
```

- [ ] **Шаг 3.2: `skills-routing.md:10` — заменить строку таблицы целиком**

Было:

```markdown
| Самопроизвольно найденный баг (UI, данные, архитектура) | локализация + исследование → handoff → откатить → завести тикет → Сценарий 1 | `HANDOFF_<название>.md` (temp) + тикет в wayfinder |
```

Стало:

```markdown
| Самопроизвольно найденный баг (UI, данные, архитектура) | внеплановая ветка `session-protocol.md` §«Вход в сессию»: локализация по R-02 без правок кода → тикет `Status: backlog` → решение пользователя, брать ли сейчас | тикет в `docs/superpowers/wayfinder/<эффорт>/issues/` |
```

- [ ] **Шаг 3.3: Проверить**

```bash
grep -n "Сценарий 1\|HANDOFF\|(temp)" docs/agents/session-protocol.md docs/agents/skills-routing.md   # пусто
grep -c "_next-session.md" CLAUDE.md                                                                  # 1
```

- [ ] **Шаг 3.4: Review Focus 2** — строка в `CLAUDE.md` содержит «Если пользователь его не приложил, прочитай сам»:

```bash
grep -c "Если пользователь его не приложил, прочитай сам" CLAUDE.md   # 1
```

- [ ] **Шаг 3.5: Коммит**

```bash
git branch --show-current   # docs/single-entry-point
git add CLAUDE.md docs/agents/skills-routing.md
git commit -m "docs: CLAUDE.md указывает на _next-session.md; внеплановое — тикет вместо handoff

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Проверка путей R-06

**Files:** только чтение. Правка — лишь если проверка найдёт путь, **введённый этой веткой**.

- [ ] **Шаг 4.1: Прогнать**

```bash
cd /c/Python/entertainment
for f in CLAUDE.md docs/agents/skills-routing.md docs/agents/session-protocol.md docs/superpowers/wayfinder/_next-session.md; do
  grep -oE '`[^` <>]+/[^` <>]*`|`[A-Za-z_.-]+\.(md|ps1|json)`' "$f" | tr -d '`' | grep -v '\*\|\.\.' | sort -u | while read -r p; do
    [ -e "$p" ] || [ -e "docs/agents/$p" ] || [ -e "docs/superpowers/wayfinder/$p" ] || echo "MISSING [$f] $p"
  done
done
```

Ожидается: пусто. Пути с `<…>`, `*` и `..` (шаблоны, git-диапазоны) отфильтрованы.

- [ ] **Шаг 4.2: Разобрать вывод.** `MISSING`, появившийся из-за правок Tasks 1–3, — исправить путь и закоммитить (`docs: R-06 — <путь>`). `MISSING` в строках, которые эта ветка не трогала (`git diff master -- <файл>` не содержит строку), — не чинить, выписать пользователю отдельным списком. Внешние пути (Obsidian) в этих файлах появиться не должны: если есть — это ошибка Tasks 1–3.

---

### Task 5: Obsidian — сверка, указатель, архив (вне git)

**Files (вне git, vault `C:\Users\DerendyaevRA\OneDrive\Документы\Obsidian Vault\Projects\entertainment\`):**
- Create: `entertainment — вход.md`
- Modify: `Журнал проблем.md` (строка в начало)
- Modify: `Сценарии работы.md` (строка в начало)

- [ ] **Шаг 5.1: Журнал в репо полнее Obsidian-копии (до любой правки)**

```bash
V="/c/Users/DerendyaevRA/OneDrive/Документы/Obsidian Vault/Projects/entertainment"
grep -oE "INC-[0-9]+|R-[0-9]+" "$V/Журнал проблем.md" | sort -u | while read -r id; do
  grep -q "$id" /c/Python/entertainment/docs/agents/process-journal.md || echo "НЕТ В РЕПО: $id"
done
```

Ожидается: пусто. Есть строки — **стоп**, показать пользователю, дальше не идти.

Снять число строк до правки (нужно в шаге 5.5):

```bash
wc -l "$V/Журнал проблем.md" "$V/Сценарии работы.md"
```

- [ ] **Шаг 5.2: Содержание `Сценариев` покрыто протоколом.** Проверить глазами: сценарии 1–3 есть в таблице §«Вход в сессию»; handoff заменён тикетом; блок «Справка: что делать, если…» покрыт — «волна переполнена» → R-05, «закончил тикет» → пункт «Выход», «в какой effort» → развилка («подходящей карты нет — вопрос»). Непокрытый пункт — показать пользователю до архивации.

- [ ] **Шаг 5.3: Создать `entertainment — вход.md`**

```markdown
# entertainment — вход

Источник истины — репозиторий `C:\Python\entertainment`. Здесь только указатели (с 2026-09-28).

- Вход в сессию: `docs/superpowers/wayfinder/_next-session.md` — подать в чат; своё — дописать «вместо этого: <симптом>».
- Правила и сценарии: `docs/agents/session-protocol.md` §«Вход в сессию».
- Инциденты и реестр правил: `docs/agents/process-journal.md`.

Архив: [[Журнал проблем]], [[Сценарии работы]] — не обновляются.
```

- [ ] **Шаг 5.4: Дописать первой строкой (содержимое ниже не трогать)**

`Журнал проблем.md`:

```markdown
> **АРХИВ 2026-09-28.** Действующая версия: `C:\Python\entertainment\docs\agents\process-journal.md`. Этот файл не обновляется.

```

`Сценарии работы.md`:

```markdown
> **АРХИВ 2026-09-28.** Действующая версия: `C:\Python\entertainment\docs\agents\session-protocol.md` §«Вход в сессию». Этот файл не обновляется.

```

Правка — через Edit по первой строке файла (`**Как пользоваться.**…` и `## Сценарий 1: …` соответственно), не перезаписью целиком.

- [ ] **Шаг 5.5: Проверить (Review Focus 5)**

```bash
V="/c/Users/DerendyaevRA/OneDrive/Документы/Obsidian Vault/Projects/entertainment"
head -1 "$V/Журнал проблем.md" "$V/Сценарии работы.md"   # обе — «> **АРХИВ 2026-09-28.**…»
wc -l "$V/Журнал проблем.md" "$V/Сценарии работы.md"     # ровно на 2 строки больше, чем до правки (снять wc -l в шаге 5.1)
ls "$V"                                                    # три файла
```

---

### Task 6: Память агента (вне git)

**Files (`C:\Users\DerendyaevRA\.claude\projects\C--Python-entertainment\memory\`):**
- Create: `session-entry.md`
- Delete: `wave2-plan.md`, `wave-rule.md`, `wayfinder-ticket-workflow.md`, `process-journal.md`
- Modify: `plan-before-edits-even-with-ticket.md:15`, `MEMORY.md`

- [ ] **Шаг 6.1: Создать `session-entry.md`**

```markdown
---
name: session-entry
description: Вход в сессию entertainment — _next-session.md; правила процесса только в docs/agents/, память и Obsidian их не дублируют
metadata:
  type: feedback
---

Вход в любую сессию — `docs/superpowers/wayfinder/_next-session.md` (изменчивое: базовая линия, следующий шаг, стоп-условия, отложенное). Постоянный протокол — `docs/agents/session-protocol.md` §«Вход в сессию»; инциденты и реестр правил — `docs/agents/process-journal.md`; выбор скилла — `docs/agents/skills-routing.md`. Внеплановое пользователь дописывает к тому же файлу («вместо этого: <симптом>»).

Правила процесса (волна ≤ 3, сведение, тикет = сессия = ветка = PR, `## Answer` + строка в карте) в памяти не хранятся — читаются из репозитория. Obsidian `Projects/entertainment/` с 2026-09-28 — указатель и архив.

**Why:** до 2026-09-28 процесс жил в пяти местах и расходился: журнал в Obsidian застыл на INC-08 при INC-15 в репо, память держала давно закрытую волну. Спек — `docs/superpowers/specs/2026-09-28-single-entry-point-design.md`.

**How to apply:** новое правило или сценарий процесса → в `docs/agents/`, не в память и не в Obsidian. Если пользователь не приложил `_next-session.md` — прочитать его самому. Связано с [[plan-before-edits-even-with-ticket]], [[git-verify-branch-before-commit]].
```

- [ ] **Шаг 6.2: Удалить четыре файла**

```bash
M="/c/Users/DerendyaevRA/.claude/projects/C--Python-entertainment/memory"
rm "$M/wave2-plan.md" "$M/wave-rule.md" "$M/wayfinder-ticket-workflow.md" "$M/process-journal.md"
```

- [ ] **Шаг 6.3: `plan-before-edits-even-with-ticket.md:15`** — заменить хвост строки `Связано с [[wayfinder-ticket-workflow]] и [[wave-rule]].` на `Связано с [[session-entry]].`

- [ ] **Шаг 6.4: `MEMORY.md`** — удалить четыре строки (`Wave 2 plan`, `Wayfinder: работа по тикетам`, `Журнал инцидентов процесса`, `Правило волны`) и добавить:

```markdown
- [Вход в сессию](session-entry.md) — _next-session.md = вход; правила процесса только в docs/agents/, память и Obsidian их не дублируют
```

- [ ] **Шаг 6.5: Проверить**

```bash
M="/c/Users/DerendyaevRA/.claude/projects/C--Python-entertainment/memory"
grep -ln "\[\[wave-rule\]\]\|\[\[wayfinder-ticket-workflow\]\]\|\[\[process-journal\]\]\|\[\[wave2-plan\]\]" "$M"/*.md   # пусто
grep -oE "\(([a-z0-9-]+\.md)\)" "$M/MEMORY.md" | tr -d '()' | while read -r f; do [ -e "$M/$f" ] || echo "MISSING $f"; done  # пусто
```

---

### Task 7: PR

- [ ] **Шаг 7.1: Итоговая сводка проверок** — повторить 1.4, 2.2, 3.3, 4.1 одним прогоном, показать вывод пользователю.
- [ ] **Шаг 7.2: `git status --short`** — в рабочей копии остаётся только `?? docs/research/2026-09-24-site-audit.md`.
- [ ] **Шаг 7.3: Спросить пользователя про пуш.** Только после «да»:

```bash
git push -u origin docs/single-entry-point
gh pr create --base master --title "docs: единая точка входа в сессию" --body "$(cat <<'EOF'
Спек: docs/superpowers/specs/2026-09-28-single-entry-point-design.md
План: docs/superpowers/plans/2026-09-28-single-entry-point.md

- session-protocol.md: раздел «Вход в сессию» (сверка, развилка план/внеплан, сценарии, шаблон), шаг 7 переписывает _next-session.md
- _next-session.md: четыре блока, следующий шаг — сведение
- CLAUDE.md: строка-указатель на _next-session.md
- skills-routing.md: внеплановое — тикет вместо handoff в temp
- вне git: Obsidian → указатель + архив, память → session-entry

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Шаг 7.4:** привязать PR (`ccd_pr` `get_status` / `bind_pr`). Мердж — решение пользователя; после мерджа — уборка R-04 (`git switch master && git pull --ff-only && git branch -d docs/single-entry-point`).
