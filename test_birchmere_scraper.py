from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from birchmere_scraper import scrape, _parse_shows

_FIXTURE_PATH = Path("fixtures/birchmere.html")

pytestmark = pytest.mark.skipif(
    not _FIXTURE_PATH.exists(),
    reason="fixtures/birchmere.html not yet downloaded — run Task 4 Step 1 first",
)


@pytest.fixture
def fixture_html():
    return _FIXTURE_PATH.read_text()


def test_returns_list_of_venue_shows(fixture_html):
    shows = _parse_shows(fixture_html)
    assert isinstance(shows, list)
    assert len(shows) > 0


def test_show_fields_are_populated(fixture_html):
    shows = _parse_shows(fixture_html)
    show = shows[0]
    assert show.act != ""
    assert show.venue == "The Birchmere"
    assert show.url.startswith("http")
    from datetime import datetime
    assert isinstance(show.date, datetime)


def test_known_show_present(fixture_html):
    shows = _parse_shows(fixture_html)
    acts = [s.act for s in shows]
    assert any("LUNA" in act.upper() for act in acts)


def test_http_error_returns_empty_list(monkeypatch):
    import requests
    def mock_get(*args, **kwargs):
        m = MagicMock()
        m.raise_for_status.side_effect = requests.HTTPError("404")
        return m
    monkeypatch.setattr("birchmere_scraper.requests.get", mock_get)
    assert scrape() == []


def test_network_error_returns_empty_list(monkeypatch):
    import requests
    monkeypatch.setattr(
        "birchmere_scraper.requests.get",
        lambda *a, **kw: (_ for _ in ()).throw(requests.ConnectionError("timeout"))
    )
    assert scrape() == []
