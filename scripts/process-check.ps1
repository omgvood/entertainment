# Проверки процесса. Правила — docs/agents/session-protocol.md,
# разбор инцидентов и счётчик повторов — журнал проблем в Obsidian.
#
# -Mode stop  R-04: ветка и worktree живут ровно до мерджа.
#
# Коды выхода: 0 — чисто, 2 — есть о чём сказать (Stop-хук показывает stderr).

param(
    [ValidateSet('stop')]
    [string]$Mode = 'stop'
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Stop-хук вызывается повторно после того, как сессия отреагировала на
# замечание. Без этой проверки получается цикл.
$stdin = [Console]::In.ReadToEnd()
if ($stdin -match '"stop_hook_active"\s*:\s*true') { exit 0 }

function Fail($text) {
    [Console]::Error.WriteLine($text)
    exit 2
}

$root = (git rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $root) {
    Fail "R-04 не проверен: git rev-parse не отработал. Проверка сломана — почини её, а не игнорируй."
}
$root = $root.Replace('\', '/').TrimEnd('/')

$raw = (git worktree list --porcelain 2>$null)
if ($LASTEXITCODE -ne 0) {
    Fail "R-04 не проверен: git worktree list не отработал. Проверка сломана — почини её, а не игнорируй."
}

# Разбор блоков: worktree <путь> / HEAD <sha> / branch refs/heads/<имя>
$trees = @()
$cur = $null
foreach ($line in ($raw -split "`r?`n")) {
    if ($line -like 'worktree *') {
        if ($cur) { $trees += $cur }
        $cur = [pscustomobject]@{ Path = $line.Substring(9).Replace('\', '/').TrimEnd('/'); Branch = $null }
    }
    elseif ($line -like 'branch refs/heads/*' -and $cur) {
        $cur.Branch = $line.Substring(18)
    }
}
if ($cur) { $trees += $cur }

if ($trees.Count -eq 0) {
    Fail "R-04 не проверен: git worktree list вернул пустой список. Это не «ноль нарушений», это сломанный разбор вывода."
}

$main = $trees[0].Path
$findings = @()

foreach ($t in $trees) {
    if ($t.Path -eq $main) { continue }   # основной чекаут
    if ($t.Path -eq $root) { continue }   # текущая сессия — она ещё работает
    if (-not $t.Branch)    { continue }   # detached HEAD, не наш случай

    $ahead = (git rev-list --count "master..$($t.Branch)" 2>$null)
    if ($LASTEXITCODE -ne 0) { continue }

    if ([int]$ahead -eq 0) {
        $findings += "  $($t.Branch) — ни одного коммита поверх master, работы в этом worktree нет"
        continue
    }

    git merge-base --is-ancestor $t.Branch origin/master 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        $findings += "  $($t.Branch) — уже в origin/master, ветка пережила свой мердж"
    }
}

$behind = (git rev-list --count "master..origin/master" 2>$null)
$mainBehind = ($LASTEXITCODE -eq 0 -and [int]$behind -gt 0)

if ($findings.Count -eq 0 -and -not $mainBehind) { exit 0 }

$msg = @("R-04: уборка после мерджа не сделана (docs/agents/session-protocol.md).")

if ($findings.Count -gt 0) {
    $msg += ""
    $msg += "Worktree, которым нечего здесь делать:"
    $msg += $findings
    $msg += ""
    $msg += "Порядок: сначала закрыть сессию, которая держит worktree — иначе"
    $msg += "git worktree remove падает с «Device or resource busy». Потом:"
    $msg += "  git worktree remove <путь>"
    $msg += "  git branch -d <ветка>"
}

if ($mainBehind) {
    $msg += ""
    $msg += "Основной чекаут отстаёт от origin/master на $behind коммит(ов) —"
    $msg += "мердж с GitHub сам сюда не приходит: git pull --ff-only"
}

$msg += ""
$msg += "Скажи об этом вслух. Если убирать сейчас нечего — так и скажи, и отметь"
$msg += "повтор R-04 в журнале: правило уже срабатывало вхолостую."

Fail ($msg -join "`n")
