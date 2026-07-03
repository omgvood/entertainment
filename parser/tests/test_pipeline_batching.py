"""Тесты _chunks_by_budget — батчинг VK/TG-постов по объёму текста.

Проверяем инварианты: полнота и порядок (каждый пост ровно в одной пачке), непустые пачки,
одиночный сверхдлинный пост уходит отдельной пачкой целиком, лимиты max_chars и max_count.
"""

from parser.pipeline import _chunks_by_budget


def _post(url: str, chars: int) -> tuple[str, str]:
    return (url, "x" * chars)


def _flatten(batches):
    return [item for batch in batches for item in batch]


def test_completeness_and_order_preserved():
    seq = [_post(f"u{i}", 100) for i in range(7)]
    batches = list(_chunks_by_budget(seq, max_chars=250, max_count=10))
    assert _flatten(batches) == seq  # каждый пост ровно раз, порядок сохранён


def test_no_empty_batches():
    seq = [_post(f"u{i}", 100) for i in range(5)]
    batches = list(_chunks_by_budget(seq, max_chars=250, max_count=10))
    assert all(batch for batch in batches)


def test_short_posts_packed_together():
    # Три коротких поста в бюджет max_chars=1000 → одна пачка.
    seq = [_post("a", 200), _post("b", 200), _post("c", 200)]
    batches = list(_chunks_by_budget(seq, max_chars=1000, max_count=10))
    assert len(batches) == 1


def test_oversized_post_gets_its_own_batch():
    # Пост длиннее max_chars не дробится и не отбрасывается — отдельная непустая пачка.
    seq = [_post("small", 100), _post("huge", 9000), _post("small2", 100)]
    batches = list(_chunks_by_budget(seq, max_chars=7000, max_count=10))
    assert _flatten(batches) == seq
    huge_batch = [b for b in batches if any(url == "huge" for url, _ in b)][0]
    assert huge_batch == [_post("huge", 9000)]  # один пост, изолирован


def test_char_budget_splits_batches():
    # Пять постов по 300 символов при max_chars=700 → пачки [2,2,1] (700 хватает на 2, не на 3).
    seq = [_post(f"u{i}", 300) for i in range(5)]
    batches = list(_chunks_by_budget(seq, max_chars=700, max_count=10))
    assert [len(b) for b in batches] == [2, 2, 1]


def test_max_count_caps_batch():
    # Короткие посты, бюджет символов большой — ограничивает max_count.
    seq = [_post(f"u{i}", 10) for i in range(7)]
    batches = list(_chunks_by_budget(seq, max_chars=100000, max_count=3))
    assert [len(b) for b in batches] == [3, 3, 1]


def test_empty_input_yields_nothing():
    assert list(_chunks_by_budget([], max_chars=7000, max_count=5)) == []
