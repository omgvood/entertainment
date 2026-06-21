"""Тесты Playwright-2ГИС: парсинг карточек заведений из фрагмента HTML (без сети, без браузера).

Фикстура воспроизводит структуру выдачи 2gis.ru/{city}/search/{query} по селекторам из
playwright_2gis (см. блок «СЕЛЕКТОРЫ 2ГИС — ЧИНИТЬ ТУТ»). Если селекторы поедут — обновить
здесь фикстуру вместе с константами в источнике.

Изменения вёрстки 2ГИС (2026-06):
  - Контейнер карточки: _1kqrd4hi → _1kf6gff
  - Имя: берём из a._1rehek (anchor), не из span с обфусцированным классом
  - Фото: <img src> → <div class="_1dk5lq4" style="background-image: ...">
  - Район: убран из карточки (district всегда None)
  - Адрес: _klarpw может содержать статус («Закрыто», «Закроется через...») — пропускаем
"""

from parser.sources.playwright_2gis import _extract_bg_image, parse_cards
from parser.validator import to_venue


# Карточки:
#  1. Космик — полная (с фото, адрес через _lvwrwt)
#  2. Боулинг без адреса — пропускается
#  3. Космик дубль — схлопывается дедупом
#  4. White Lanes — адрес с суффиксом «2 филиала»
#  5. Рокстар — альтернативный класс спана (_9r89aog) + статус перед адресом в _klarpw
_HTML = """
<html><body>
  <div class="_1kf6gff">
    <div class="_327aum">
      <div class="_1qim2i7"><div class="_15mwbsm">
        <div class="_fsrcjh">
          <div role="img" class="_1dk5lq4"
               style="background-image: image-set(url(&quot;https://i.2gis.com/cosmic_116.jpg&quot;) 1x, url(&quot;https://i.2gis.com/cosmic_232.jpg&quot;) 2x);">
          </div>
        </div>
      </div></div>
    </div>
    <div class="_zjunba">
      <a class="_1rehek" href="/perm/firm/123">
        <span class="_lvwrwt"><span>Космик</span></span>
      </a>
    </div>
    <div class="_klarpw"><span class="_3yxk2u">Пермь, ул. Спешилова, 114</span></div>
  </div>

  <div class="_1kf6gff">
    <div class="_zjunba">
      <a class="_1rehek"><span class="_lvwrwt"><span>Боулинг без адреса</span></span></a>
    </div>
  </div>

  <div class="_1kf6gff">
    <div class="_zjunba">
      <a class="_1rehek"><span class="_lvwrwt"><span>Космик</span></span></a>
    </div>
    <div class="_klarpw"><span class="_3yxk2u">Пермь, ул. Спешилова, 114</span></div>
  </div>

  <div class="_1kf6gff">
    <div class="_zjunba">
      <a class="_1rehek"><span class="_lvwrwt"><span>White Lanes</span></span></a>
    </div>
    <div class="_klarpw">
      <span class="_14quei">
        <span class="_sfdp8cg">Колизей Атриум, ул. Ленина, 60, Пермь</span>
        <span class="_sfdp8cg"><a href="/perm/branches/123">2&nbsp;филиала</a></span>
      </span>
    </div>
  </div>

  <!-- Рекламная карточка: контейнер _5b28jpo, спан _9r89aog, статус перед адресом -->
  <div class="_5b28jpo">
    <div class="_zjunba">
      <a class="_1rehek" href="/perm/firm/456">
        <span class="_9r89aog"><span>Рокстар</span></span>
      </a>
    </div>
    <div class="_klarpw">Закроется через 24 минуты</div>
    <div class="_klarpw"><span class="_3yxk2u">Морион, шоссе Космонавтов, 111а, Пермь</span></div>
  </div>
</body></html>
"""


def test_parse_cards_extracts_venues():
    venues = parse_cards(_HTML, "bowling")
    # Без адреса отброшена, дубль схлопнут → остаётся 3: Космик + White Lanes + Рокстар.
    assert len(venues) == 3

    cosmic = venues[0]
    assert cosmic.venue_name == "Космик"
    assert cosmic.title == "Космик"
    assert cosmic.date == "always"
    assert cosmic.type == "bowling"
    assert cosmic.address == "Пермь, ул. Спешилова, 114"
    assert cosmic.district is None           # район убран из вёрстки 2ГИС
    assert cosmic.image_url == "https://i.2gis.com/cosmic_232.jpg"  # 2x из image-set
    assert cosmic.price_min == 0 and cosmic.price_max == 0


def test_parse_cards_cleans_branch_suffix():
    venues = parse_cards(_HTML, "bowling")
    wl = venues[1]
    assert wl.venue_name == "White Lanes"
    assert wl.address == "Колизей Атриум, ул. Ленина, 60, Пермь"  # без «2 филиала»


def test_parse_cards_alt_name_class():
    """Карточки с _9r89aog вместо _lvwrwt должны находиться через anchor a._1rehek."""
    venues = parse_cards(_HTML, "sport")
    names = [v.venue_name for v in venues]
    assert "Рокстар" in names


def test_parse_cards_skips_status_address():
    """Когда первый _klarpw — статус, берётся следующий (с адресом)."""
    venues = parse_cards(_HTML, "sport")
    rockstar = next(v for v in venues if v.venue_name == "Рокстар")
    assert rockstar.address == "Морион, шоссе Космонавтов, 111а, Пермь"
    assert "Закроется" not in rockstar.address


def test_parse_cards_empty():
    assert parse_cards("<html><body></body></html>", "bowling") == []


def test_extract_bg_image_image_set():
    style = (
        'background-image: image-set(url("https://i.2gis.com/a_116.jpg") 1x,'
        ' url("https://i.2gis.com/a_232.jpg") 2x);'
    )
    assert _extract_bg_image(style) == "https://i.2gis.com/a_232.jpg"


def test_extract_bg_image_plain_url():
    style = 'background-image: url("https://cdn.2gis.com/logo.png");'
    assert _extract_bg_image(style) == "https://cdn.2gis.com/logo.png"


def test_extract_bg_image_none():
    assert _extract_bg_image(None) is None
    assert _extract_bg_image("color: red;") is None


def test_to_venue_maps_parsed_event():
    parsed = parse_cards(_HTML, "bowling")[0]
    venue = to_venue(parsed, "perm", "playwright")
    assert venue.id == "perm-kosmik"
    assert venue.city == "perm"
    assert venue.name == "Космик"
    assert venue.type == "bowling"
    assert venue.source == "playwright"
    assert venue.district is None
