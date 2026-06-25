"""Шлёт Telegram-алерт по файлу предупреждений парсера (parse_warnings_<city>.json).

Вызывается из GHA-шага «Send warning alert» после успешного прогона: сам прогон не падает,
если упал один источник из многих (напр. протух токен Timepad), поэтому предупреждения
пишутся в файл и доставляются отдельно — иначе сбой остаётся невидимым.

Использует только stdlib (urllib) — не требует зависимостей в окружении раннера.

 Env: TG_BOT_TOKEN, TG_CHAT_ID (если не заданы — тихо выходим), GITHUB_REPO, GITHUB_RUN_ID.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request


def _escape_md(s: str) -> str:
    """Telegram Markdown (не V2): экранируем спецсимволы ВНЕ бэктиков."""
    return s.replace("_", "\\_").replace("*", "\\*")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: notify_warnings.py <warnings.json>", file=sys.stderr)
        return 2

    bot_token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not bot_token or not chat_id:
        print("TG_BOT_TOKEN/TG_CHAT_ID не заданы — пропускаем алерт", file=sys.stderr)
        return 0

    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)

    repo = os.environ.get("GITHUB_REPO", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    logs = f"\n\nЛоги: https://github.com/{repo}/actions/runs/{run_id}" if repo else ""
    # Строки warnings уже обрезаны до 200 симв. в парсере → лимит Telegram (4096) недостижим.
    msg = (
        f"⚠️ Парсер ({_escape_md(data['city'])}) — есть предупреждения:\n"
        # строки ошибок в бэктиках — внутри них экранирование не требуется
        + "\n".join(f"`{w}`" for w in data["warnings"])
        + logs
    )

    payload = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage", data=payload
    )
    try:
        urllib.request.urlopen(req, timeout=10)  # без таймаута urlopen висит бесконечно
    except Exception as e:  # noqa: BLE001
        print(f"Failed to send TG alert: {e}", file=sys.stderr)
        return 0  # не валим шаг GHA из-за недоступности Telegram

    return 0


if __name__ == "__main__":
    sys.exit(main())
