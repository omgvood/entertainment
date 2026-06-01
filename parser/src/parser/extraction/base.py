"""Абстракция LLM-экстрактора."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import ParsedEvent


class ExtractorError(RuntimeError):
    """LLM не вернул валидный ответ или поля не прошли валидацию."""


class LLMExtractor(ABC):
    """Универсальный интерфейс. Реализуется конкретным провайдером."""

    @abstractmethod
    async def extract(self, html: str, source_url: str) -> ParsedEvent:
        """Извлечь ОДНО событие из HTML страницы конкретного события."""

    @abstractmethod
    async def extract_many(self, html: str, source_url: str) -> list[ParsedEvent]:
        """Извлечь ВСЕ события из HTML листинг-страницы (расписание/афиша).

        Используется для источников, где детали всех событий уже доступны на
        одной странице — позволяет обойтись 1 LLM-вызовом вместо N.
        Возвращает [] если событий на странице нет.
        """
