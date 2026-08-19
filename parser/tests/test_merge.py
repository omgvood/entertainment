"""Тесты кросс-источникового merge (чистые функции, без БД)."""

from parser.merge import merge_rows
from parser.models import ParsedEvent
from parser.validator import to_event_row


_PRI = {"timepad": 100, "vk-events": 80, "vk-posts": 40}


def _row(title, date, venue, source, **over):
    p = ParsedEvent(
        title=title,
        type=over.pop("type", "concert"),
        date=date,
        time_start=over.pop("time_start", None),
        price_min=over.pop("price_min", 0),
        price_max=over.pop("price_max", 0),
        price_text=over.pop("price_text", "уточняйте"),
        address=over.pop("address", "ул. Тест, 1"),
        venue_name=venue,
        image_url=over.pop("image_url", None),
        description=over.pop("description", None),
        organizer=over.pop("organizer", None),
    )
    return to_event_row(p, "perm", over.pop("source_url", "http://u"), source)


def test_priority_winner_and_count():
    """Один title+date из двух источников → побеждает timepad, vk-posts посчитан как merged."""
    a = _row("Концерт Икс", "2026-06-15", "Дом музыки", "timepad")
    b = _row("Концерт Икс", "2026-06-15", "Дом музыки", "vk-posts")
    res = merge_rows([b, a], [], _PRI)  # порядок не важен — решает priority
    assert len(res.rows_to_upsert) == 1
    assert res.rows_to_upsert[0].source == "timepad"
    assert res.merged == 1
    assert res.merged_by_source == {"vk-posts→timepad": 1}


def test_enrichment_fills_empty_fields():
    """Победитель добирает пустые поля и цену из проигравшего."""
    winner = _row("Шоу", "2026-07-01", "Арена", "timepad")  # без image/описания, цена 0/0
    loser = _row(
        "Шоу", "2026-07-01", "Арена", "vk-posts",
        image_url="http://img", description="Описание из VK",
        price_min=500, price_max=1500, price_text="от 500 до 1500 ₽",
    )
    res = merge_rows([winner, loser], [], _PRI)
    row = res.rows_to_upsert[0]
    assert row.source == "timepad"
    assert row.image_url == "http://img"
    assert row.description == "Описание из VK"
    assert row.price_min == 500 and row.price_max == 1500


def test_same_source_no_merge_count():
    """Две строки одного источника с одним id — схлоп без счётчика merged (не кросс-источник)."""
    a = _row("Квиз", "2026-06-20", "Бар", "vk-posts")
    b = _row("Квиз", "2026-06-20", "Бар", "vk-posts", description="дубль")
    res = merge_rows([a, b], [], _PRI)
    assert len(res.rows_to_upsert) == 1
    assert res.merged == 0


def test_existing_higher_priority_not_downgraded():
    """В БД лежит timepad-строка; сегодня тот же id принёс только vk-posts → timepad побеждает."""
    incoming = _row("Лекция", "2026-08-01", "Музей", "vk-posts")
    existing = _row("Лекция", "2026-08-01", "Музей", "timepad", description="из timepad")
    res = merge_rows([incoming], [existing], _PRI)
    assert len(res.rows_to_upsert) == 1
    assert res.rows_to_upsert[0].source == "timepad"


def test_different_dates_not_merged():
    """Разные даты → разные id → не сливаются."""
    a = _row("Спектакль", "2026-06-15", "Театр", "timepad")
    b = _row("Спектакль", "2026-06-16", "Театр", "vk-posts")
    res = merge_rows([a, b], [], _PRI)
    assert len(res.rows_to_upsert) == 2
    assert res.merged == 0


def test_near_miss_same_venue_date_different_title():
    """Та же площадка+дата, разные названия → near-miss (не схлоп)."""
    a = _row("Стендап Иванова", "2026-09-10", "Клуб Смех", "vk-posts")
    b = _row("Вечер юмора с Ивановым", "2026-09-10", "Клуб Смех", "timepad")
    res = merge_rows([a, b], [], _PRI)
    assert len(res.rows_to_upsert) == 2  # разные id — оба остаются
    assert res.near_misses == 1


from parser.merge import fuzzy_merge


def test_fuzzy_new_row_does_not_duplicate_persisted_card():
    """Главный сценарий: в БД уже есть карточка, источник принёс её же другими словами.

    Новая строка не пишется отдельной карточкой, её поля дозаполняют существующую.
    id/slug существующей не меняются — URL стабилен.
    """
    persisted = _row('Акция "Собака Обнимака"', "2026-08-16", "Сквер оперы", "vk-posts",
                     time_start="14:00")
    fresh = _row('АКЦИЯ "СОБАКА ОБНИМАКА": ОБНИМИ ПСА И ПОМОГИ ПРИЮТАМ!', "2026-08-16",
                 "Сквер оперы", "telegram-posts", time_start="14:00",
                 description="Из телеграма")
    res = fuzzy_merge([fresh, persisted], [persisted], _PRI)
    assert len(res.rows_to_upsert) == 1
    assert res.rows_to_upsert[0].id == persisted.id
    assert res.rows_to_upsert[0].description == "Из телеграма"
    assert res.fuzzy_merged == 1


def test_fuzzy_persisted_wins_over_higher_priority_newcomer():
    """Стабильность URL важнее приоритета: иначе slug уедет и страница выпадет из индекса."""
    persisted = _row("День открытых дверей в Автопрестиж", "2026-08-16", "Автопрестиж",
                     "vk-posts", time_start="14:00")
    fresh = _row("День открытых дверей в Автопрестиж (Воскресенье)", "2026-08-16",
                 "Автопрестиж", "timepad", time_start="14:00")
    res = fuzzy_merge([fresh, persisted], [persisted], _PRI)
    assert [r.id for r in res.rows_to_upsert] == [persisted.id]


def test_fuzzy_two_fresh_rows_resolved_by_priority():
    """Обе строки новые — решает priority источника."""
    a = _row("Обзорная экскурсия по текущим выставкам", "2026-08-18", "ПЕРММ",
             "vk-posts", time_start="18:30")
    b = _row("Обзорные экскурсии по текущим выставкам музея ПЕРММ", "2026-08-18", "ПЕРММ",
             "timepad", time_start="18:30")
    res = fuzzy_merge([a, b], [], _PRI)
    assert len(res.rows_to_upsert) == 1
    assert res.rows_to_upsert[0].source == "timepad"


def test_fuzzy_two_persisted_rows_are_left_alone():
    """Обе карточки уже в БД — ежедневный прогон их не сливает (это работа dedup-backfill).

    Выбрасывание строки из upsert её не удалит, только сделает данные несвежими.
    """
    a = _row('Акция "Собака Обнимака"', "2026-08-16", "Сквер", "vk-posts", time_start="14:00")
    b = _row('АКЦИЯ "СОБАКА ОБНИМАКА": ОБНИМИ ПСА', "2026-08-16", "Сквер", "vk-posts",
             time_start="14:00")
    res = fuzzy_merge([a, b], [a, b], _PRI)
    assert len(res.rows_to_upsert) == 2
    assert res.fuzzy_merged == 0
    assert len(res.candidates) == 1


def test_fuzzy_in_source_duplicates_counted_separately():
    """Дубль внутри одного источника не должен портить KPI unique_events_ratio."""
    a = _row("День рождения парка", "2026-08-16", "Парк", "vk-posts", time_start="13:00")
    b = _row("День рождения парка (концерт)", "2026-08-16", "Парк", "vk-posts",
             time_start="13:00")
    res = fuzzy_merge([a, b], [], _PRI)
    assert res.fuzzy_merged == 1
    assert res.fuzzy_merged_in_source == 1


def test_fuzzy_different_events_untouched():
    """Разные сеансы в одном планетарии — обе строки выживают."""
    a = _row("Парад планет", "2026-08-16", "Планетарий", "vk-posts", time_start="10:30")
    b = _row("Где живёт Земля", "2026-08-16", "Планетарий", "vk-posts", time_start="12:00")
    res = fuzzy_merge([a, b], [], _PRI)
    assert len(res.rows_to_upsert) == 2
    assert res.fuzzy_merged == 0


def test_fuzzy_db_pool_row_not_written_when_untouched():
    """Строки из пула БД, ни с чем не совпавшие, в upsert не попадают (не переписываем город)."""
    fresh = _row("Новый концерт", "2026-08-16", "Арена", "timepad", time_start="19:00")
    unrelated = _row("Старая лекция", "2026-08-16", "Музей", "vk-posts", time_start="12:00")
    res = fuzzy_merge([fresh], [unrelated], _PRI)
    assert [r.id for r in res.rows_to_upsert] == [fresh.id]


def test_fuzzy_distinct_source_rows_are_both_written():
    """Две игры QuizPlease в одном зале в одно время должны попасть в БД обе."""
    a = _row("Квиз, плиз! PERM", "2026-08-18", "Ресторан Кама", "quizplease",
             time_start="19:30")
    b = _row("Квиз, плиз! [новички] PERM", "2026-08-18", "Ресторан Кама", "quizplease",
             time_start="19:30")
    res = fuzzy_merge([a, b], [], _PRI, frozenset({"quizplease"}))
    assert len(res.rows_to_upsert) == 2
    assert res.fuzzy_merged == 0
