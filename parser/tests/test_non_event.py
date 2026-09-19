"""Фильтр не-событий (новости/объявления/реклама) из social/generic-источников.

На /perm среди карточек type='other' около четверти оказались не событиями: новости
городского паблика permactive («Пермь Активная»), розыгрыши, промокоды, голосования,
open call. Причины: VK-префильтр всегда мягкий (SOCIAL, хватает одной даты в новости),
а batch-промпт требует «вернуть ВСЕ события» и не говорит, что не является событием.

Три слоя, как у spurious 'always': строгий префильтр для новостных групп (seeds),
правило в batch-промптах, постфильтр is_non_event по заголовку (guard в to_event_row).
Заголовки и тексты ниже реальные, из БД на 2026-09-18.
"""

import time

import pytest

from parser.classifiers import is_event_candidate
from parser.config import SourceConfig, SourceType, load_seeds
from parser.pipeline import _run_vk_posts_source


# --- слой 1: строгий префильтр для новостных VK-групп ---

PERMACTIVE_NEWS = [
    "🚔 В Перми до 8 октября оставили под арестом 44-летнего гражданина Мексики, которого "
    "проверяют на возможное участие в деятельности наркокартеля.",
    "🅿 Муниципальные парковки в Перми будут работать бесплатно с 18 по 20 сентября — на время "
    "проведения выборов платить за стоянку не потребуется.",
    # «🚢 На Каме появится новое судно стоимостью…» префильтр НЕ ловит («стоимостью» содержит
    # маркер «стоимость»). Его отсекает постфильтр по заголовку (слой 3).
    "📺 Выпуск с его участием покажут 17 сентября в 18:00 на канале «Ю».",
    "🎁 РАЗЫГРЫВАЕМ МЕТАЛЛИЧЕСКУЮ ДВЕРЬ! Участие бесплатное. Всего — 6 победителей. 📅 Итоги 9 ноября.",
]

PERMACTIVE_EVENT = (
    "Пермь, приглашаем на главное авто-мото шоу сезона!\n\nШоу каскадеров 2026\n\n"
    "с 18 по 20 сентября 2026\nСтадион \"Локомотив\"\n\nБилеты на сайте: bitvamashin.ru/perm"
)


def _perm_vk_source() -> SourceConfig:
    return next(s for s in load_seeds()["perm"].sources if s.name == "vk-posts")


def test_permactive_is_strict_in_seeds():
    """permactive («Пермь Активная») — городские новости, а не афиша: строгий префильтр."""
    assert _perm_vk_source().vk_source_types["permactive"] == SourceType.AGGREGATOR


def test_afisha_groups_stay_social():
    """Афиша-группы не трогаем: у них мало новостей, строгий порог срезал бы анонсы-переносы."""
    types = _perm_vk_source().vk_source_types
    for group in ("prmgo", "kudaperm", "permkudapoiti", "perm_where_to_go"):
        assert group not in types


@pytest.mark.parametrize("text", PERMACTIVE_NEWS)
def test_aggregator_threshold_rejects_permactive_news(text):
    assert is_event_candidate(text, SourceType.AGGREGATOR) is False


def test_aggregator_threshold_keeps_permactive_event_ad():
    assert is_event_candidate(PERMACTIVE_EVENT, SourceType.AGGREGATOR) is True


class _FakeVk:
    def __init__(self, walls: dict[str, list[str]]) -> None:
        self._walls = walls

    async def fetch_wall_posts(self, domain: str, *, count: int = 100):
        now = time.time()
        return [
            {"owner_id": -1, "id": i, "date": now, "text": t}
            for i, t in enumerate(self._walls[domain])
        ]


class _RecordingExtractor:
    """Запоминает, какие тексты дошли до LLM, и ничего не извлекает."""

    def __init__(self) -> None:
        self.docs: list[str] = []

    async def extract_many(self, html: str, source_url: str):
        self.docs.append(html)
        return []


async def test_vk_prefilter_uses_group_source_type(monkeypatch):
    """Группа с source_type=aggregator отсеивает новость с датой, обычная (social) пропускает."""
    news = PERMACTIVE_NEWS[1]
    walls = {"newsgroup": [news, PERMACTIVE_EVENT], "afisha": [news]}
    monkeypatch.setattr("parser.pipeline.VkClient", lambda client, key: _FakeVk(walls))
    extractor = _RecordingExtractor()
    source = SourceConfig(
        name="vk-posts",
        extraction_mode="vk_posts",
        vk_groups=["newsgroup", "afisha"],
        vk_source_types={"newsgroup": SourceType.AGGREGATOR},
    )

    await _run_vk_posts_source(None, source, extractor, None, "perm", "key", True, 5, 7000)

    newsgroup_doc, afisha_doc = extractor.docs
    assert "парковки" not in newsgroup_doc
    assert "Шоу каскадеров" in newsgroup_doc
    assert "парковки" in afisha_doc
