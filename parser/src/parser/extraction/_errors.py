"""Классификация исключений LLM-SDK: rate-limit (429/503) vs остальное."""

from __future__ import annotations


def is_rate_limit(exc: BaseException) -> bool:
    """True, если ошибка провайдера — про лимит/перегрузку (429/503).

    Двойная проверка: статус-код (groq/openai .status_code, google.genai .code) и
    подстроки в тексте — на случай, если SDK обернул ошибку без структурного кода.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in (429, 503):
        return True
    s = str(exc).lower()
    return any(
        m in s
        for m in ("429", "503", "rate limit", "resource_exhausted", "unavailable", "overloaded")
    )


def is_request_too_large(exc: BaseException) -> bool:
    """True, если ошибка — 413 Request too large (вход превысил TPM-лимит модели).

    Отделён от rate-limit: 413 чинится разбиением входа пополам (см. GroqExtractor),
    а не ретраем/фолбэком. Duck-typing на .status_code — как в is_rate_limit.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 413:
        return True
    s = str(exc).lower()
    return "request too large" in s or "request entity too large" in s
