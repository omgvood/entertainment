"""Классификация исключений LLM-SDK: rate-limit (429/503) vs остальное."""

from __future__ import annotations


def is_rate_limit(exc: BaseException) -> bool:
    """True, если ошибка провайдера — про лимит/перегрузку (429/503/TPM).

    Двойная проверка: статус-код (groq/openai .status_code, google.genai .code) и
    подстроки в тексте — на случай, если SDK обернул ошибку без структурного кода.

    Сюда же относится Groq 413 «Request too large … tokens per minute (TPM)»: на free-tier
    фиксированный оверхед (system-промпт + max_tokens) сам по себе превышает TPM, поэтому
    батч не уменьшить разбиением — это лимит, который лечится ретраем/фолбэком на Gemini.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in (429, 503):
        return True
    s = str(exc).lower()
    return any(
        m in s
        for m in (
            "429", "503", "rate limit", "rate_limit_exceeded", "resource_exhausted",
            "unavailable", "overloaded", "request too large", "tokens per minute",
        )
    )


def is_daily_quota_exhausted(exc: BaseException) -> bool:
    """True, если rate-limit — это исчерпанная СУТОЧНАЯ квота, а не временная перегрузка.

    Отличие важно: временный 503/429 (модель перегружена, TPM) лечится ретраем через
    секунды; дневная квота (Gemini free-tier: 20 запросов/сутки на модель) до конца суток не
    восстановится — ретраить бессмысленно, надо сразу переходить к следующему провайдеру.

    Ограничение подхода: матчинг завязан на текущий текст ошибки Gemini SDK
    ('quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier' / 'per day'). Если провайдер
    изменит формат сообщения, паттерн потребует обновления — держать в уме при отладке.
    """
    s = str(exc).lower()
    return "generaterequestsperdayperprojectpermodel" in s or (
        "quota" in s and "per day" in s
    )
