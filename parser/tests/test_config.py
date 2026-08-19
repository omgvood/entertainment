"""Контракт seeds.yaml: флаги, от которых зависит поведение дедупа."""

from parser.config import load_seeds


def _source(city: str, name: str):
    return next(s for s in load_seeds()[city].sources if s.name == name)


def test_quizplease_marked_as_distinct_events():
    """Одна строка API QuizPlease = одна игра: слой 2 не должен склеивать их между собой."""
    assert _source("perm", "quizplease").distinct_events is True
    assert _source("sochi", "quizplease").distinct_events is True


def test_permm_not_marked_as_distinct_events():
    """У ПЕРММ два JSON-эндпоинта пересекаются — его самодубли настоящие, флаг не ставим."""
    assert _source("perm", "permm").distinct_events is False
