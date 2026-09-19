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
from parser.models import ParsedEvent
from parser.pipeline import PipelineResult, _run_vk_posts_source, _safe_to_event_row
from parser.validator import is_non_event, to_event_row


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


# --- слой 2: правило в batch-промптах ---


def test_batch_prompts_exclude_non_events():
    """Посты идут через extract_many → правило обязано быть в BATCH-промпте каждого экстрактора."""
    from parser.extraction import deepseek_extractor, gemini_extractor, groq_extractor

    phrase = "НЕ являются событиями"
    for mod in (deepseek_extractor, gemini_extractor, groq_extractor):
        assert phrase in mod._SYSTEM_PROMPT_BATCH, mod.__name__


# --- слой 3: постфильтр по заголовку ---

# Реальные не-события, попавшие на сайт, которые постфильтр ловит узкими маркерами.
NON_EVENT_TITLES = [
    "Гражданин Мексики под арестом по делу о наркотиках",
    "В Госдуме предложили открывать в детсадах вечерние группы по просьбе родителей",
    "В Перми движение по второй очереди Средней дамбы планируют открыть 18 октября",
    "Капитальный ремонт путепровода на улице Промышленной, 127",
    "Розыгрыш металлической двери Аркан 206",
    "Розыгрыш персональной фотосессии в «ПЕРММ»",
    "Отслеживание цен на продукты",
    "Специальное предложение от сети пиццерий «Пиццбург»",
    "Open call на 13 сезон резиденции MaxArt x ПЕРММ",
    "Голосование за номинантов Национальной туристической премии Russian Traveler Awards 2026",
    "Максим из Краснокамска в телепроекте «Ждули»",
]

# Не-события, которые постфильтр НАМЕРЕННО не ловит: нужный маркер слишком широкий
# («парковк» бывает в названиях событий: «Автокинотеатр на парковке ТРЦ»; «появится» — в
# анонсах). Их закрывают другие слои:
#   «Бесплатные парковки на время выборов» — префильтр (permactive → aggregator) + промпт;
#   «На Каме появится новое пассажирское судно» — промпт (префильтр пропускает: «стоимостью»).
# Накопленные в БД экземпляры удаляются миграцией по явному списку id (Task 4).

# Настоящие события type='other' с того же сайта, должны остаться. Сюда же слова-ловушки:
# «конкурса», «акция», «ярмарка».
REAL_EVENT_TITLES = [
    "Толкучка",
    "ТОЛКУЧКА",
    "Толкучка во дворе соцгородка “Рабочий поселок\"",
    "Шоу каскадёров",
    "Шоу каскадеров 2026",
    "Осенняя ярмарка",
    "Ярмарка и вечер Народного караоке",
    'Цирк "Империя мастеров" в Перми!',
    "Благотворительная акция «Давай дружить!»",
    "Выставка-пристройство собак из приюта «Доброе сердце»",
    "Торжественная церемония награждения победителей конкурса «Музейный Олимп»",
    "Праздничный вечер для ветеранов",
    "Музейная программа «Соль-вода» в музее «Хохловка»",
    "«Полировка ГАЗ‑13 „Чайка“ — вживую в музее: приходите увидеть процесс»",
    "Премьерный показ фильма о Романовых на фестивале «Флаэртиана»",
    "Релакс - Ретрит «Левада»",
    "Видеопрогулка \"Моя любимая книга\"",
]


def _parsed(title: str, date: str = "2026-09-20") -> ParsedEvent:
    return ParsedEvent(
        title=title,
        type="other",
        date=date,
        price_min=0,
        price_max=0,
        price_text="бесплатно",
        address="Пермь",
        venue_name="Пермь",
    )


@pytest.mark.parametrize("title", NON_EVENT_TITLES)
def test_non_event_titles_detected(title):
    assert is_non_event(title, "vk-posts") is True


@pytest.mark.parametrize("title", REAL_EVENT_TITLES)
def test_real_event_titles_kept(title):
    assert is_non_event(title, "vk-posts") is False


@pytest.mark.parametrize("source", ["telegram-posts", "generic:domain.ru", "generic"])
def test_non_event_applies_to_all_social_sources(source):
    assert is_non_event("Розыгрыш металлической двери Аркан 206", source) is True


@pytest.mark.parametrize("source", ["timepad", "quizplease", "permm", "twogis-bowling"])
def test_structured_sources_not_filtered(source):
    """API-источники отдают только события, их заголовки не трогаем."""
    assert is_non_event("Голосование за лучший квиз сезона", source) is False


def test_to_event_row_drops_non_event():
    row = to_event_row(
        _parsed("Розыгрыш металлической двери Аркан 206"), "perm", "https://vk.com/w", "vk-posts"
    )
    assert row is None


def test_to_event_row_keeps_real_event():
    row = to_event_row(_parsed("Осенняя ярмарка"), "perm", "https://vk.com/w", "vk-posts")
    assert row is not None


def test_safe_to_event_row_counts_non_event_separately():
    """Не-событие считается в skipped_non_event, а не в skipped_always."""
    sub = PipelineResult()
    row = _safe_to_event_row(
        _parsed("Гражданин Мексики под арестом по делу о наркотиках"), "perm", "https://vk.com/w", "vk-posts", sub
    )
    assert row is None
    assert sub.skipped_non_event == 1
    assert sub.skipped_always == 0


def test_safe_to_event_row_always_still_counted_as_always():
    sub = PipelineResult()
    _safe_to_event_row(_parsed("Выставка", date="always"), "perm", "https://vk.com/w", "vk-posts", sub)
    assert sub.skipped_always == 1
    assert sub.skipped_non_event == 0
