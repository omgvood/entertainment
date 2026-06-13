"""Тесты Telegram: парсинг веб-превью t.me/s/ и конвертация даты (без сети)."""

from parser.sources.telegram import _iso_to_unix, parse_channel_html


# Урезанный фрагмент реальной разметки t.me/s/{channel}: два поста с текстом + один без.
_HTML = """
<html><body>
  <div class="tgme_widget_message">
    <div class="tgme_widget_message_text">Квиз 20 июня в 19:00, билеты на сайте</div>
    <a class="tgme_widget_message_date" href="https://t.me/standupperm/101">
      <time datetime="2026-06-13T12:00:00+00:00">12:00</time>
    </a>
  </div>
  <div class="tgme_widget_message">
    <div class="tgme_widget_message_text">Стендап-вечер уже завтра!</div>
    <a class="tgme_widget_message_date" href="https://t.me/standupperm/102">
      <time datetime="2026-06-14T09:30:00+00:00">09:30</time>
    </a>
  </div>
  <div class="tgme_widget_message">
    <a class="tgme_widget_message_date" href="https://t.me/standupperm/103">
      <time datetime="2026-06-15T08:00:00+00:00">08:00</time>
    </a>
  </div>
</body></html>
"""


def test_parse_channel_html_extracts_text_posts():
    posts = parse_channel_html(_HTML)
    # Пост без текста (только фото) пропускается → остаётся 2.
    assert len(posts) == 2
    first = posts[0]
    assert first["url"] == "https://t.me/standupperm/101"
    assert "Квиз 20 июня" in first["text"]
    assert first["date_unix"] == _iso_to_unix("2026-06-13T12:00:00+00:00")


def test_parse_channel_html_empty():
    assert parse_channel_html("<html><body></body></html>") == []


def test_iso_to_unix():
    assert _iso_to_unix("2026-06-13T12:00:00+00:00") == 1781352000.0
    assert _iso_to_unix(None) is None
    assert _iso_to_unix("not-a-date") is None
