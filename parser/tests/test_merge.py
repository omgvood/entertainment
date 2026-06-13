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
