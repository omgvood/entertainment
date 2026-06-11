"""Доменные модели — то, что LLM возвращает и что пишется в Postgres.

Имена snake_case совпадают с колонками таблицы public.events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .taxonomy import TAGS_VERSION, filter_tags

# Узкая ниша MVP-1 (Пермь + Сочи) + широкая афиша MVP-2 (Timepad: тип по категории события).
EventType = Literal[
    "quiz", "standup", "bowling", "billiards", "karting",
    "concert", "theater", "exhibition", "festival", "quest", "party",
    "cinema", "sport", "education", "business", "art", "kids", "food", "trip", "hobby", "science",
    "other",
]


class ParsedEvent(BaseModel):
    """Извлечённое из HTML событие. То, что LLM обязан вернуть."""

    title: str = Field(min_length=3, max_length=300)
    type: EventType
    category: Optional[str] = None
    date: str = Field(description="YYYY-MM-DD или 'always'")
    time_start: Optional[str] = Field(default=None, description="HH:MM")
    time_end: Optional[str] = Field(default=None, description="HH:MM")
    price_min: int = Field(ge=0)
    price_max: int = Field(ge=0)
    price_text: str
    price_note: Optional[str] = None
    address: str
    venue_name: str
    district: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = Field(default=None, max_length=500)
    organizer: Optional[str] = None
    tags: list[str] = Field(
        default_factory=list,
        description="Теги из закрытого набора taxonomy.ALLOWED_TAGS (для подборок/рекомендаций)",
    )

    @field_validator("tags")
    @classmethod
    def _filter_tags(cls, v: list[str]) -> list[str]:
        return filter_tags(v)

    @field_validator("date")
    @classmethod
    def _date_format(cls, v: str) -> str:
        if v == "always":
            return v
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"date должен быть YYYY-MM-DD или 'always', получили {v!r}") from exc
        return v

    @field_validator("time_start", "time_end")
    @classmethod
    def _time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"time должен быть HH:MM, получили {v!r}") from exc
        return v

    @field_validator("price_max")
    @classmethod
    def _price_range(cls, v: int, info) -> int:
        price_min = info.data.get("price_min")
        if price_min is not None and v < price_min:
            raise ValueError(f"price_max ({v}) < price_min ({price_min})")
        return v


class EventRow(ParsedEvent):
    """ParsedEvent + сервисные поля, готов к записи в Postgres."""

    id: str
    city: str
    slug: str
    source_url: str
    source: str
    parsed_at: str
    tags_version: int = TAGS_VERSION
    fingerprint: str = ""
    """Хеш title+date+venue для кросс-источниковой дедупликации (без UNIQUE, см. validator)."""

    @staticmethod
    def make_parsed_at_now() -> str:
        return datetime.now(timezone.utc).isoformat()
