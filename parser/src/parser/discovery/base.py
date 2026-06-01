"""Абстракция для дискавери: «найти URL событий на источнике»."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DiscoveredUrl:
    """URL события, найденный на источнике."""

    url: str
    source: str
    """Имя источника (для трассировки и записи в БД)."""


class DiscoveryStrategy(ABC):
    """Базовый класс. Любая стратегия принимает HTTP-клиент и возвращает список URL."""

    name: str

    def __init__(self, client: httpx.AsyncClient, source_name: str) -> None:
        self.client = client
        self.source_name = source_name

    @abstractmethod
    async def discover(self) -> list[DiscoveredUrl]:
        """Вернуть список найденных URL событий."""
