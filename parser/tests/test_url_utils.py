"""Тесты resolve_event_url: прямая ссылка / относительная / мусорные домены / фолбэк."""

from parser.url_utils import resolve_event_url


_BASE = "https://vk.com/prmgo"


def test_absolute_event_url_kept():
    url = "https://vk.com/wall-80718152_8481"
    assert resolve_event_url(url, _BASE) == url


def test_relative_url_joined_with_base():
    base = "https://teatr-teatr.com/afisha/"
    assert resolve_event_url("/afisha/event-slug", base) == "https://teatr-teatr.com/afisha/event-slug"


def test_empty_and_junk_fall_back_to_base():
    assert resolve_event_url(None, _BASE) == _BASE
    assert resolve_event_url("", _BASE) == _BASE
    assert resolve_event_url("  ", _BASE) == _BASE
    assert resolve_event_url("#", _BASE) == _BASE
    assert resolve_event_url("javascript:void(0)", _BASE) == _BASE


def test_junk_domain_falls_back():
    assert resolve_event_url("https://clck.ru/3U8Ekm", _BASE) == _BASE
    assert resolve_event_url("https://vk.cc/abc", _BASE) == _BASE
    assert resolve_event_url("https://goodsbuy.by/redirect/cpa/o/x/", _BASE) == _BASE


def test_junk_subdomain_falls_back():
    # heartharmony.taplink.ws — поддомен мусорного агрегатора taplink.ws.
    assert resolve_event_url("https://heartharmony.taplink.ws/", _BASE) == _BASE


def test_non_junk_domain_kept():
    url = "https://perm.quizplease.ru/game/019ebb14-bb2e-70dc-b2e5-742cae5f37a0"
    assert resolve_event_url(url, _BASE) == url
