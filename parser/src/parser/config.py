"""Загрузка env-переменных и seeds.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
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
    vk_service_key: Optional[str] = None
    """Сервисный ключ VK mini-app. Нужен для источников vk-events / vk-posts."""
    search_providers: str = "serper"
    """Поисковики Discovery через запятую, порядок = приоритет: 'serper,brave,duckduckgo'."""
    serper_api_key: Optional[str] = None
    """Ключ Serper API (google.serper.dev). Основной провайдер discover-sources."""
    brave_api_key: Optional[str] = None
    """Ключ Brave Search API. Резервный провайдер discover-sources."""
    search_timeout_seconds: float = 20.0
    """Таймаут HTTP-запроса к поисковику в discover-sources."""
    search_query_limit: Optional[int] = None
    """Лимит числа поисковых запросов за прогон (защита квоты). None = по числу шаблонов."""
    generic_llm_budget: int = 10
    """Макс. число LLM-вызовов на прогон в generic-источнике (защита расходов)."""
    generic_domain_budget: int = 20
    """Макс. число доменов на прогон в generic-источнике (защита времени прогона)."""
    post_batch_size: int = 5
    """Сколько VK/TG-постов склеивать в один LLM-вызов (баланс квоты и точности атрибуции)."""
    llm_provider: LlmProvider = "gemini"
    llm_fallback_providers: str = "gemini,groq"
    """Цепочка провайдеров через запятую (порядок = приоритет). При 429/503 переключаемся на
    следующего из тех, у кого есть ключ. deepseek по умолчанию не включён (OpenRouter 402)."""
    llm_retry_attempts: int = 3
    """Число попыток на провайдера при rate-limit (429/503) перед переходом к следующему."""
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
            vk_service_key=os.environ.get("VK_SERVICE_KEY"),
            search_providers=os.environ.get("SEARCH_PROVIDERS", "serper"),
            serper_api_key=os.environ.get("SERPER_API_KEY"),
            brave_api_key=os.environ.get("BRAVE_API_KEY"),
            search_timeout_seconds=float(os.environ.get("SEARCH_TIMEOUT_SECONDS", "20")),
            search_query_limit=(
                int(os.environ["SEARCH_QUERY_LIMIT"])
                if os.environ.get("SEARCH_QUERY_LIMIT")
                else None
            ),
            generic_llm_budget=int(os.environ.get("GENERIC_LLM_BUDGET", "10")),
            generic_domain_budget=int(os.environ.get("GENERIC_DOMAIN_BUDGET", "20")),
            post_batch_size=int(os.environ.get("POST_BATCH_SIZE", "5")),
            llm_provider=provider_raw,  # type: ignore[arg-type]
            llm_fallback_providers=os.environ.get("LLM_FALLBACK_PROVIDERS", "gemini,groq"),
            llm_retry_attempts=int(os.environ.get("LLM_RETRY_ATTEMPTS", "3")),
            gemini_model=os.environ.get("GEMINI_MODEL"),
            groq_model=os.environ.get("GROQ_MODEL"),
            deepseek_model=os.environ.get("DEEPSEEK_MODEL"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


DiscoveryKind = Literal["sitemap", "listing"]
ExtractionMode = Literal[
    "per_url", "batch_listing", "direct_api",
    "vk_events", "vk_posts", "telegram_posts", "generic",
    "playwright_listing",  # batch_listing, но fetch через Playwright (Nuxt/React/Vue SPA)
]


class SourceType(str, Enum):
    """Природа источника. Влияет на строгость префильтра (classifiers) и осмысление метрик.

    Источники принципиально разные: API отдаёт чистые структурированные данные, агрегатор —
    много шума (реклама/мемы/новости), организатор — почти чистые анонсы. От типа зависит
    порог отсечения постов перед LLM и интерпретация unique_events_ratio.
    """

    API = "api"                # Timepad, 2ГИС — структурированные данные
    AGGREGATOR = "aggregator"  # афиша-паблики (много шума)
    ORGANIZER = "organizer"    # сайт/канал конкретного организатора (мало шума)
    VENUE = "venue"            # площадка
    SOCIAL = "social"          # VK posts и прочие соцсети по умолчанию


@dataclass(frozen=True)
class TelegramChannelConfig:
    """Один Telegram-канал для режима telegram_posts.

    Объект, а не строка — чтобы отключать канал, менять приоритет и тип без правок кода.
    """

    channel: str
    """Screen-name канала без https://t.me/ (например 'standupperm')."""
    source_type: SourceType = SourceType.SOCIAL
    priority: int = 40
    enabled: bool = True


@dataclass(frozen=True)
class SourceConfig:
    """Один источник: «откуда брать события»."""

    name: str
    extraction_mode: ExtractionMode = "per_url"
    priority: int = 0
    enabled: bool = True
    """Приоритет источника при кросс-источниковой дедупликации (выше — побеждает). Шаг 6."""
    full_snapshot: bool = False
    # True = один вызов возвращает ВСЕ будущие события источника для города.
    # Включает автоматическое удаление событий, пропавших из источника (синхронизация отмен).
    # НЕ включать для batch_listing с пагинацией/lazy-loading, vk_posts, telegram, generic.

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

    # Для direct_api / quizplease:
    quizplease_city_id: Optional[int] = None
    """ID города в QuizPlease API (api.quizplease.ru/api/games/schedule/{id})."""

    # Для vk_events / vk_posts:
    vk_city_id: Optional[int] = None
    """ID города VK для groups.search (опц.; если None — поиск только по названию города)."""
    vk_groups: list[str] = field(default_factory=list)
    """Список screen names кураторских VK-сообществ для vk_posts."""

    # Для telegram_posts:
    telegram_sources: list[TelegramChannelConfig] = field(default_factory=list)
    """Telegram-каналы (объекты с channel/source_type/priority/enabled)."""

    """
    per_url:        дискавер N URL событий → N LLM-вызовов (по одному на страницу).
    batch_listing:  игнорируем дискавер, скачиваем url целиком и одним LLM-вызовом
                    извлекаем массив всех событий со страницы.
    direct_api:     вызываем API провайдера (provider + api_query) и маппим JSON → ParsedEvent
                    напрямую, без LLM. Используется для 2ГИС/Я.Карт.
    vk_events:      VK-сообщества типа «событие» → ParsedEvent напрямую (без LLM).
    vk_posts:       посты со стен vk_groups → префильтр → LLM extract_many (1 вызов на группу).
    telegram_posts: посты публичных каналов (t.me/s/) → префильтр → LLM extract_many (1 вызов/канал).
    generic:        одобренные в candidate_sources домены → JSON-LD / LLM (длинный хвост).
    playwright_listing: то же что batch_listing, но страница рендерится headless-браузером
                    (Playwright) — для SPA на Nuxt/Next/React, где httpx видит пустой скелет.
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
                priority=s.get("priority", 0),
                enabled=s.get("enabled", True),
                kind=s.get("kind"),
                url=s.get("url"),
                url_pattern=s.get("url_pattern"),
                provider=s.get("provider"),
                api_query=s.get("api_query"),
                event_type=s.get("event_type"),
                quizplease_city_id=s.get("quizplease_city_id"),
                full_snapshot=s.get("full_snapshot", False),
                vk_city_id=s.get("vk_city_id"),
                vk_groups=s.get("vk_groups") or [],
                telegram_sources=[
                    TelegramChannelConfig(
                        channel=t["channel"],
                        source_type=SourceType(t.get("source_type", "social")),
                        priority=t.get("priority", 40),
                        enabled=t.get("enabled", True),
                    )
                    for t in (s.get("telegram_sources") or [])
                ],
            )
            for s in city_raw["sources"]
        ]
        cities[city_slug] = CityConfig(slug=city_slug, sources=sources)
    return cities
