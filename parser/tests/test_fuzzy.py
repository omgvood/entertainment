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


def test_text_score_enumeration_is_not_a_duplicate():
    """Афиша-перечень трёх разных МК, а не переформулировка одного анонса."""
    assert text_score(
        "Мастер-класс «Единорог»", "Мастер-классы: «Единорог», «Планета», «Ёжик»"
    ) < MERGE


def test_text_score_enumeration_does_not_swallow_its_header():
    """«Анимационная программа» — отдельное событие, а не заголовок перечня."""
    assert text_score(
        "Анимационная программа",
        "Анимационная программа и мастер-классы: «Арт-терапия», «Подсолнухи»",
    ) < MERGE


def test_text_score_program_prefix_is_not_enumeration():
    """Тоже две пары кавычек, но список не образуют: «АРТ-парк» — цикл, а не соседний МК."""
    assert text_score(
        "«АРТ-парк»: Мастер-класс «Цветы из бумаги»", "Цветы из бумаги"
    ) >= MERGE


def test_text_score_nested_quotes_are_one_segment():
    """Вложенные кавычки — один сегмент: «Яблочный Спас в «Хохловке»» не перечень."""
    assert text_score(
        "Праздник «Яблочный Спас в «Хохловке»", "Яблочный Спас в «Хохловке»"
    ) >= MERGE


from parser.fuzzy import cluster_events


def _clusters_of(rows, merge_threshold=MERGE):
    clusters, _pairs = cluster_events(
        rows, merge_threshold=merge_threshold, report_threshold=CANDIDATE
    )
    return sorted((sorted(r.id for r in c) for c in clusters), key=len, reverse=True)


def test_cluster_transitivity():
    """A~B и B~C при A≁C должны дать один кластер: «парк Горького» приходит 4 формулировками."""
    a = _row("День открытых дверей в Автопрестиж", "Автопрестиж", "14:00")
    b = _row("День открытых дверей в Автопрестиж (Воскресенье)", "Автопрестиж", "14:00")
    c = _row("День открытых дверей в Автопрестиж (Спешилова 111/3)", "Автопрестиж", "14:00")
    assert len(_clusters_of([a, b, c])[0]) == 3


def test_cluster_different_dates_never_merge():
    """Блокировка по дате: один спектакль в разные дни — разные сеансы."""
    a = _row("Алиса в стране чудес", "Театр-Тятрик", "13:00", date="2026-08-16")
    b = _row("Алиса в стране чудес", "Театр-Тятрик", "13:00", date="2026-08-17")
    assert [len(c) for c in _clusters_of([a, b])] == [1, 1]


def test_cluster_singletons_are_returned():
    """Одиночки тоже возвращаются кластерами — вызывающий строит вывод по всем кластерам."""
    a = _row("Парад планет", "Пермский планетарий", "10:30")
    b = _row("Где живёт Земля", "Пермский планетарий", "12:00")
    clusters = _clusters_of([a, b])
    assert [len(c) for c in clusters] == [1, 1]
    assert {c[0] for c in clusters} == {a.id, b.id}


def test_cluster_skips_always():
    """date='always' (постоянные места) в fuzzy не участвует.

    Источник намеренно не vk-/telegram-/generic: для них to_event_row отбраковал бы
    'always' как spurious (см. validator.is_spurious_always) и вернул None.
    """
    a = _row("Боулинг-клуб Страйк", "Страйк", date="always", source="twogis-bowling")
    b = _row("Боулинг клуб Страйк", "Страйк", date="always", source="twogis-bowling")
    assert _clusters_of([a, b]) == []


def test_cluster_umbrella_program_keeps_its_parts():
    """«День Строгановых» — программа дня: её пункты не дубли ни ей, ни друг другу.

    Попарно «X» ⊂ «X: подсобытие» неотличимо от настоящего дубля, поэтому решает
    кластер: у зонтичного заголовка несколько детей, не похожих между собой.
    """
    day = _row("День Строгановых", "Пермская галерея", "12:00")
    book = _row("День Строгановых: книжная выставка", "Пермская галерея")
    film = _row("День Строгановых: показ фильма", "Пермская галерея")
    assert [len(c) for c in _clusters_of([day, book, film])] == [1, 1, 1]


def test_cluster_single_longer_variant_still_merges():
    """Один ребёнок — это уточнение, а не программа: слияние остаётся."""
    a = _row("Культурная среда", "ПЕРММ", "18:00")
    b = _row("Культурная среда: бесплатный вход для льготных категорий", "ПЕРММ", "18:00")
    assert len(_clusters_of([a, b])[0]) == 2


def test_cluster_similar_variants_are_not_an_umbrella():
    """Четыре формулировки одной экскурсии ПЕРММ: дети похожи между собой — не программа."""
    rows = [
        _row(t, "Музей современного искусства «ПЕРММ»", "18:30")
        for t in (
            "Обзорная экскурсия по текущим выставкам",
            "Обзорная экскурсия по текущим выставкам музея",
            "Обзорная экскурсия по текущим выставкам музея «ПЕРММ»",
            "Обзорные экскурсии по текущим выставкам музея «ПЕРММ»",
        )
    ]
    assert len(_clusters_of(rows)[0]) == 4


def test_cluster_reports_grey_zone_pairs():
    """Пара ниже порога слияния не сливается, но попадает в отчёт для dedup_candidates."""
    a = _row("Мастер-класс «Единорог»", "Парк «Счастье есть»", "12:00")
    b = _row("Мастер-класс «Планета»", "Парк «Счастье есть»", "12:00")
    clusters, pairs = cluster_events(
        [a, b], merge_threshold=MERGE, report_threshold=0.5
    )
    assert len(clusters) == 2
    assert len(pairs) == 1
    assert 0.5 <= pairs[0].score.score < MERGE


def test_score_pair_same_distinct_source_never_merges():
    """Две игры QuizPlease в одном зале в 19:30 — разные игры, а не переформулировка."""
    a = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="quizplease")
    b = _row("Квиз, плиз! [новички] PERM", "Ресторан Кама", "19:30", source="quizplease")
    assert score_pair(a, b, distinct_sources=frozenset({"quizplease"})) == PairScore(
        0.0, 0.0, 0.0, "same_distinct_source"
    )


def test_score_pair_distinct_guard_applies_only_within_one_source():
    """Флаг запрещает слияние внутри источника: кросс-источниковый дубль по-прежнему ловится."""
    a = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="quizplease")
    b = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="vk-posts")
    assert score_pair(a, b, distinct_sources=frozenset({"quizplease"})).score >= MERGE


def test_cluster_distinct_source_rows_stay_apart():
    a = _row("Квиз, плиз! PERM", "Ресторан Кама", "19:30", source="quizplease")
    b = _row("Квиз, плиз! [новички] PERM", "Ресторан Кама", "19:30", source="quizplease")
    clusters, _pairs = cluster_events(
        [a, b], merge_threshold=MERGE, report_threshold=CANDIDATE,
        distinct_sources=frozenset({"quizplease"}),
    )
    assert [len(c) for c in clusters] == [1, 1]


def test_cluster_same_source_without_flag_still_merges():
    """ПЕРММ отдаёт один экспонат двумя эндпоинтами — его самодубли настоящие."""
    a = _row("Выставка «Стечение обстоятельств»", "Музей современного искусства «ПЕРММ»",
             source="permm")
    b = _row("Стечение обстоятельств", "Музей современного искусства «ПЕРММ»", source="permm")
    assert len(_clusters_of([a, b])[0]) == 2
