"""Тесты fuzzy-скорера. Пары — реальные из БД Перми (см. спеку)."""

import pytest

from parser.fuzzy import PairScore, score_pair, stem, text_score, tokens
from parser.models import ParsedEvent
from parser.validator import to_event_row

MERGE = 0.95
CANDIDATE = 0.75


def _row(title, venue, time_start=None, source="vk-posts", date="2026-08-16"):
    p = ParsedEvent(
        title=title, type="other", date=date, time_start=time_start,
        price_min=0, price_max=0, price_text="уточняйте",
        address="ул. Тест, 1", venue_name=venue,
    )
    return to_event_row(p, "perm", "http://u", source)


def test_stem_collapses_russian_endings():
    assert stem("парка") == stem("парку") == "парк"
    assert stem("планета") == stem("планеты") == "планет"


def test_stem_keeps_consonant_ending():
    """«класс» и «классы» должны сойтись, но конечную согласную не отбрасываем."""
    assert stem("класс") == stem("классы") == "класс"


def test_stem_does_not_conflate_different_words():
    assert stem("программа") != stem("прогулка")


def test_tokens_drop_stopwords_and_short_words():
    assert tokens("День открытых дверей в Автопрестиж") == {
        stem("день"), stem("открытых"), stem("дверей"), stem("автопрестиж")
    }


@pytest.mark.parametrize(
    "title_a,title_b",
    [
        # посимвольное сходство: отличие ровно в пробеле
        ('«Галерея историй»: аудио спектакль-променад',
         '«Галерея историй»: аудиоспектакль-променад'),
        # вложенность токенов
        ('Акция "Собака Обнимака"',
         'АКЦИЯ "СОБАКА ОБНИМАКА": ОБНИМИ ПСА И ПОМОГИ ПРИЮТАМ!'),
        ('День открытых дверей в Автопрестиж',
         'День открытых дверей в Автопрестиж (Воскресенье)'),
        ('Обзорная экскурсия по текущим выставкам',
         'Обзорные экскурсии по текущим выставкам музея «ПЕРММ»'),
    ],
)
def test_text_score_real_duplicates(title_a, title_b):
    assert text_score(title_a, title_b) >= MERGE


def test_text_score_short_title_not_swallowed():
    """«Йога» ⊂ «Йога на набережной» — containment-guard не даёт засчитать вложенность."""
    assert text_score("Йога", "Йога на набережной") < MERGE


def test_text_score_sibling_masterclasses_stay_apart():
    """Разные МК одной программы: похожи, но не дубли."""
    assert text_score("Мастер-класс «Единорог»", "Мастер-класс «Планета»") < MERGE


def test_score_pair_time_mismatch_is_hard_guard():
    """Один бар, одна дата, разное время — это разные сеансы, а не разная формулировка."""
    a = _row("Квиз, плиз! PERM", "Gastro.Li", "15:00")
    b = _row("[ностальжи] PERM", "Gastro.Li", "18:00")
    assert score_pair(a, b) == PairScore(0.0, 0.0, 0.0, "time_mismatch")


def test_score_pair_merges_real_duplicate():
    a = _row('Акция "Собака Обнимака"', "Сквер театра оперы и балета", "14:00")
    b = _row('АКЦИЯ "СОБАКА ОБНИМАКА": ОБНИМИ ПСА И ПОМОГИ ПРИЮТАМ!',
             "Сквер театра оперы и балета", "14:00")
    assert score_pair(a, b).score >= MERGE


def test_score_pair_merges_across_sources():
    """Кросс-источниковый дубль ПЕРММ: telegram + vk, одно время."""
    a = _row("Обзорная экскурсия по текущим выставкам",
             "Музей современного искусства «ПЕРММ»", "18:30", source="telegram-posts")
    b = _row("Обзорные экскурсии по текущим выставкам музея «ПЕРММ»",
             "Музей современного искусства «ПЕРММ»", "18:30", source="vk-posts")
    assert score_pair(a, b).score >= MERGE


def test_score_pair_empty_venue_is_neutral_not_penalised():
    """У VK-постов площадка часто не извлекается — штрафовать за это нечестно."""
    a = _row('Акция "Собака Обнимака"', "", "14:00")
    b = _row('АКЦИЯ "СОБАКА ОБНИМАКА": ОБНИМИ ПСА И ПОМОГИ ПРИЮТАМ!', "", "14:00")
    assert score_pair(a, b).score >= MERGE


def test_score_pair_different_venue_cuts_score():
    """Одинаковое название на разных площадках — разные события."""
    a = _row("Стендап-концерт", "Бар Заря", "20:00")
    b = _row("Стендап-концерт", "Клуб Пилот", "20:00")
    assert score_pair(a, b).score < MERGE


def test_score_pair_without_any_supporting_signal_is_damped():
    """Ни площадки, ни времени — сливать по одному названию рискованно."""
    a = _row("Лекция о космосе", "")
    b = _row("Лекция о космосе", "")
    assert score_pair(a, b).score < MERGE


def test_score_pair_unrelated_events_score_low():
    a = _row("Парад планет", "Пермский планетарий", "10:30")
    b = _row("Где живёт Земля", "Пермский планетарий", "12:00")
    assert score_pair(a, b).score < CANDIDATE
