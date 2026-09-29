"""Изоляция предупреждений между источниками в run_city.

Гарантия: упавший источник (напр. HTTP 403 — протухший токен) пишет last_error в
source_health, а успешный сосед по тому же прогону получает last_error=None. Свойство
держится на том, что каждый источник работает со своим локальным sub=PipelineResult().

Любой сбой (errors > 0) оставляет причину в last_error, а не только HTTP 400/401/403.
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


async def _run_direct_api(sources, fetch_side_effects, *, to_event_row, spurious=False):
    """run_city без БД и сети: возвращает (result, {source: (errors, last_error)})."""
    city = CityConfig(slug="perm", sources=sources)
    captured: dict[str, tuple[int, str | None]] = {}

    def fake_record_health(client, source, city, *, events_found, errors,
                           duration_sec, last_error=None):
        captured[source] = (errors, last_error)

    empty_merge = types.SimpleNamespace(
        merged=0, near_misses=0, merged_by_source={}, rows_to_upsert=[]
    )

    with patch("parser.pipeline.record_source_health", side_effect=fake_record_health), \
         patch("parser.pipeline._fetch_direct_api_items",
               new=AsyncMock(side_effect=fetch_side_effects)), \
         patch("parser.pipeline.to_event_row", **to_event_row), \
         patch("parser.pipeline.is_spurious_always", return_value=spurious), \
         patch("parser.pipeline.fetch_events_for_dedup", return_value=[]), \
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
    return result, captured


def _item(title: str = "Событие"):
    return (MagicMock(date="2026-07-01", title=title), "https://example.com/event/1")


@pytest.mark.asyncio
async def test_warning_isolation_between_sources():
    """403 у source-1 не должен «заразить» last_error успешного source-2."""
    # source-1 → 403 (auth-ветка пишет warning); source-2 → один валидный item.
    fake_request = httpx.Request("GET", "https://api.timepad.ru")
    fake_response = httpx.Response(403, request=fake_request)
    result, captured = await _run_direct_api(
        [_direct_api_source("source-1"), _direct_api_source("source-2")],
        [
            httpx.HTTPStatusError("403 Forbidden", request=fake_request, response=fake_response),
            [_item()],
        ],
        to_event_row={"return_value": MagicMock(id="perm-evt-1", source="source-2")},
    )

    assert captured["source-1"][1] is not None  # ошибка зафиксирована
    assert "403" in captured["source-1"][1]
    assert captured["source-2"][1] is None      # сосед чист
    # На уровне города предупреждения агрегируются для GHA-алерта.
    assert any("403" in w for w in result.warnings)
    assert len(result.warnings) == 1


@pytest.mark.asyncio
async def test_non_http_failure_keeps_reason():
    """2ГИС отвечает HTTP 200 с meta.code=403 → общий except; причина всё равно в last_error."""
    result, captured = await _run_direct_api(
        [_direct_api_source("twogis-bowling")],
        [RuntimeError("2GIS API вернул meta.code=403: incorrect key")],
        to_event_row={"return_value": None},
    )

    errors, last_error = captured["twogis-bowling"]
    assert errors == 1
    assert last_error is not None
    assert last_error.startswith("twogis-bowling:")
    assert "meta.code=403" in last_error
    assert result.warnings == [last_error]


@pytest.mark.asyncio
async def test_failure_reason_wins_over_skipped_note():
    """Сбой строки + отброшенный 'always' в одном источнике: в last_error — сбой, не «Отброшено»."""
    _, captured = await _run_direct_api(
        [_direct_api_source("vk-posts")],
        [[_item("битая"), _item("always")]],
        to_event_row={"side_effect": [ValueError("bad date"), None]},
        spurious=True,
    )

    errors, last_error = captured["vk-posts"]
    assert errors == 1
    assert last_error is not None
    assert "bad date" in last_error
    assert "Отброшено" not in last_error


@pytest.mark.asyncio
async def test_many_failures_collapse_to_one_warning():
    """Три сбоя в одном источнике — одна строка в Telegram с числом остальных."""
    result, captured = await _run_direct_api(
        [_direct_api_source("src")],
        [[_item("a"), _item("b"), _item("c")]],
        to_event_row={"side_effect": ValueError("bad date")},
    )

    errors, last_error = captured["src"]
    assert errors == 3
    assert len(result.warnings) == 1
    assert "(+2)" in result.warnings[0]
    assert result.warnings[0] == last_error
