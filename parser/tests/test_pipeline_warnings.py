"""Изоляция предупреждений между источниками в run_city.

Гарантия: упавший источник (напр. HTTP 403 — протухший токен) пишет last_error в
source_health, а успешный сосед по тому же прогону получает last_error=None. Свойство
держится на том, что каждый источник работает со своим локальным sub=PipelineResult().
"""

import types
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from parser.config import CityConfig, SourceConfig
from parser.pipeline import run_city


def _direct_api_source(name: str) -> SourceConfig:
    return SourceConfig(
        name=name, extraction_mode="direct_api", provider="timepad", priority=10
    )


@pytest.mark.asyncio
async def test_warning_isolation_between_sources():
    """403 у source-1 не должен «заразить» last_error успешного source-2."""
    city = CityConfig(
        slug="perm",
        sources=[_direct_api_source("source-1"), _direct_api_source("source-2")],
    )

    captured: dict[str, str | None] = {}

    def fake_record_health(client, source, city, *, events_found, errors,
                           duration_sec, last_error=None):
        captured[source] = last_error

    # source-1 → 403 (auth-ветка пишет warning); source-2 → один валидный item.
    fake_request = httpx.Request("GET", "https://api.timepad.ru")
    fake_response = httpx.Response(403, request=fake_request)
    fetch_side_effects = [
        httpx.HTTPStatusError("403 Forbidden", request=fake_request, response=fake_response),
        [(MagicMock(date="2026-07-01"), "https://example.com/event/1")],
    ]

    empty_merge = types.SimpleNamespace(
        merged=0, near_misses=0, merged_by_source={}, rows_to_upsert=[]
    )

    with patch("parser.pipeline.record_source_health", side_effect=fake_record_health), \
         patch("parser.pipeline._fetch_direct_api_items",
               new=AsyncMock(side_effect=fetch_side_effects)), \
         patch("parser.pipeline.to_event_row",
               return_value=MagicMock(id="perm-evt-1", source="source-2")), \
         patch("parser.pipeline.fetch_events_by_ids", return_value=[]), \
         patch("parser.pipeline.merge_rows", return_value=empty_merge), \
         patch("parser.pipeline.upsert_events",
               return_value=types.SimpleNamespace(inserted=0)), \
         patch("parser.pipeline.cleanup_old_events"), \
         patch("parser.pipeline.cleanup_old_raw_documents"), \
         patch("parser.pipeline.record_coverage"), \
         patch("parser.pipeline.record_source_quality"):

        result = await run_city(
            city,
            extractor=MagicMock(),
            supabase=MagicMock(),  # не None → record_source_health вызывается
            timepad_token="dummy",
        )

    assert captured["source-1"] is not None  # ошибка зафиксирована
    assert "403" in captured["source-1"]
    assert captured["source-2"] is None      # сосед чист
    # На уровне города предупреждения агрегируются для GHA-алерта.
    assert any("403" in w for w in result.warnings)
    assert len(result.warnings) == 1
