"""Загрузка env-переменных и seeds.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()


LlmProvider = Literal["gemini", "groq", "deepseek"]

DEFAULT_MODELS: dict[str, str] = {
    "gemini": "gemini-2.5-flash-lite",
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek/deepseek-v4-flash",
}


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    gemini_api_key: Optional[str] = None
    """Нужен если llm_provider='gemini' либо если планируется переключение через --provider."""
    groq_api_key: Optional[str] = None
    """Нужен если llm_provider='groq'."""
    deepseek_api_key: Optional[str] = None
    """Нужен если llm_provider='deepseek' либо если планируется переключение через --provider."""
    twogis_api_key: Optional[str] = None
    """Нужен если в seeds.yaml есть direct_api источники с provider=twogis."""
    timepad_token: Optional[str] = None
    """Нужен если в seeds.yaml есть direct_api источники с provider=timepad."""
    llm_provider: LlmProvider = "gemini"
    gemini_model: Optional[str] = None
    """Override от env GEMINI_MODEL. Если None — DEFAULT_MODELS['gemini']."""
    groq_model: Optional[str] = None
    """Override от env GROQ_MODEL. Если None — DEFAULT_MODELS['groq']."""
    deepseek_model: Optional[str] = None
    """Override от env DEEPSEEK_MODEL. Если None — DEFAULT_MODELS['deepseek']."""
    log_level: str = "INFO"

    def model_for(self, provider: LlmProvider) -> str:
        override = {
            "gemini": self.gemini_model,
            "groq": self.groq_model,
            "deepseek": self.deepseek_model,
        }[provider]
        return override or DEFAULT_MODELS[provider]

    @classmethod
    def from_env(cls) -> "Settings":
        missing = []
        supabase_url = os.environ.get("SUPABASE_URL") or missing.append("SUPABASE_URL")
        supabase_service_key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or missing.append("SUPABASE_SERVICE_ROLE_KEY")
        )
        if missing:
            raise RuntimeError(
                f"Не заданы env-переменные: {', '.join(m for m in missing if m)}. "
                "Скопируй .env.example в .env и подставь значения."
            )

        provider_raw = os.environ.get("LLM_PROVIDER", "gemini").lower()
        if provider_raw not in ("gemini", "groq", "deepseek"):
            raise RuntimeError(
                f"LLM_PROVIDER={provider_raw!r} не поддерживается. Допустимо: gemini, groq, deepseek."
            )

        return cls(
            supabase_url=supabase_url,  # type: ignore[arg-type]
            supabase_service_key=supabase_service_key,  # type: ignore[arg-type]
            gemini_api_key=os.environ.get("GEMINI_API_KEY"),
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
            twogis_api_key=os.environ.get("TWOGIS_API_KEY"),
            timepad_token=os.environ.get("TIMEPAD_TOKEN"),
            llm_provider=provider_raw,  # type: ignore[arg-type]
            gemini_model=os.environ.get("GEMINI_MODEL"),
            groq_model=os.environ.get("GROQ_MODEL"),
            deepseek_model=os.environ.get("DEEPSEEK_MODEL"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


DiscoveryKind = Literal["sitemap", "listing"]
ExtractionMode = Literal["per_url", "batch_listing", "direct_api"]


@dataclass(frozen=True)
class SourceConfig:
    """Один источник: «откуда брать события»."""

    name: str
    extraction_mode: ExtractionMode = "per_url"

    # Для per_url и batch_listing:
    kind: Optional[DiscoveryKind] = None
    url: Optional[str] = None
    """Базовый URL: sitemap.xml или страница-листинг."""
    url_pattern: Optional[str] = None
    """Регексп для фильтрации URL событий (например, /events/\\d+). Только для per_url + listing."""

    # Для direct_api (2ГИС, Я.Карты и т.п.):
    provider: Optional[str] = None
    """Идентификатор провайдера: 'twogis', 'yandex_maps', etc."""
    api_query: Optional[str] = None
    """Поисковый запрос: 'боулинг Пермь'."""
    event_type: Optional[str] = None
    """Тип, который присваивается всем событиям из этого источника."""

    """
    per_url:        дискавер N URL событий → N LLM-вызовов (по одному на страницу).
    batch_listing:  игнорируем дискавер, скачиваем url целиком и одним LLM-вызовом
                    извлекаем массив всех событий со страницы.
    direct_api:     вызываем API провайдера (provider + api_query) и маппим JSON → ParsedEvent
                    напрямую, без LLM. Используется для 2ГИС/Я.Карт.
    """


@dataclass(frozen=True)
class CityConfig:
    slug: str
    sources: list[SourceConfig]


def load_seeds(path: Path | None = None) -> dict[str, CityConfig]:
    """Грузит config/seeds.yaml → словарь {city_slug: CityConfig}."""
    if path is None:
        path = Path(__file__).resolve().parents[2] / "config" / "seeds.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cities: dict[str, CityConfig] = {}
    for city_slug, city_raw in raw["cities"].items():
        sources = [
            SourceConfig(
                name=s["name"],
                extraction_mode=s.get("extraction_mode", "per_url"),
                kind=s.get("kind"),
                url=s.get("url"),
                url_pattern=s.get("url_pattern"),
                provider=s.get("provider"),
                api_query=s.get("api_query"),
                event_type=s.get("event_type"),
            )
            for s in city_raw["sources"]
        ]
        cities[city_slug] = CityConfig(slug=city_slug, sources=sources)
    return cities
