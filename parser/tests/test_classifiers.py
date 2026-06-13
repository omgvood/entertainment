"""Тесты общего префильтра is_event_candidate (порог зависит от SourceType)."""

from parser.classifiers import is_event_candidate
from parser.config import SourceType


def test_default_accepts_any_single_signal():
    # SOCIAL (дефолт): достаточно одного сигнала — дата ИЛИ маркер ИЛИ билеты.
    assert is_event_candidate("Концерт 15 июня, билеты на сайте") is True
    assert is_event_candidate("Начало в 19:00, вход свободный") is True
    assert is_event_candidate("Регистрация: https://org.timepad.ru/event/1/") is True
    assert is_event_candidate("Спасибо всем за прекрасный вечер! 🥳") is False
    assert is_event_candidate("") is False


def test_organizer_is_lenient():
    # У организатора мало шума — одного сигнала (только дата) достаточно.
    assert is_event_candidate("Ждём вас 20 июля", SourceType.ORGANIZER) is True


def test_aggregator_is_strict():
    # У агрегатора много шума — нужна дата И (маркер ИЛИ билеты).
    # Только дата без событийного контекста — отсекаем.
    assert is_event_candidate("Фото дня 15 июня 📸", SourceType.AGGREGATOR) is False
    # Дата + маркер — проходит.
    assert is_event_candidate("Концерт 15 июня, билеты уже в продаже", SourceType.AGGREGATOR) is True
    # Маркер без даты — у агрегатора недостаточно.
    assert is_event_candidate("Приглашаем на встречу", SourceType.AGGREGATOR) is False
