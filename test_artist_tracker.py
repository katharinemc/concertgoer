import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from models import Show
from artist_tracker import fetch_regional_shows, _matches_region, _event_to_show


# ── Region filter ────────────────────────────────────────────────────────────

STATES = ["VA", "DC"]
CITIES = ["Baltimore", "Bethesda", "Silver Spring"]


def test_matches_virginia_by_state_code():
    event = {"venue": {"location": "Richmond, VA, United States", "city": "Richmond"}}
    assert _matches_region(event, STATES, CITIES) is True


def test_matches_dc_by_state_code():
    event = {"venue": {"location": "Washington, DC, United States", "city": "Washington"}}
    assert _matches_region(event, STATES, CITIES) is True


def test_matches_nova_by_state_code():
    event = {"venue": {"location": "Vienna, VA, United States", "city": "Vienna"}}
    assert _matches_region(event, STATES, CITIES) is True


def test_matches_baltimore_by_city():
    event = {"venue": {"location": "Baltimore, MD, United States", "city": "Baltimore"}}
    assert _matches_region(event, STATES, CITIES) is True


def test_matches_bethesda_by_city():
    event = {"venue": {"location": "Bethesda, MD, United States", "city": "Bethesda"}}
    assert _matches_region(event, STATES, CITIES) is True


def test_rejects_new_york():
    event = {"venue": {"location": "New York, NY, United States", "city": "New York"}}
    assert _matches_region(event, STATES, CITIES) is False


def test_rejects_chicago():
    event = {"venue": {"location": "Chicago, IL, United States", "city": "Chicago"}}
    assert _matches_region(event, STATES, CITIES) is False


def test_case_insensitive_state_match():
    event = {"venue": {"location": "Norfolk, va, United States", "city": "Norfolk"}}
    assert _matches_region(event, STATES, CITIES) is True


def test_case_insensitive_city_match():
    event = {"venue": {"location": "baltimore, MD, United States", "city": "baltimore"}}
    assert _matches_region(event, ["VA", "DC"], ["Baltimore"]) is True


def test_va_substring_in_city_name_does_not_false_positive():
    """'Savannah, GA' contains 'va' but must NOT match the VA state filter."""
    event = {"venue": {"location": "Savannah, GA, United States", "city": "Savannah"}}
    assert _matches_region(event, ["VA", "DC"], []) is False


# ── Event → Show conversion ──────────────────────────────────────────────────

def test_event_to_show_valid():
    event = {
        "id": "12345",
        "datetime": "2026-04-12T20:00:00",
        "venue": {"name": "The Birchmere", "city": "Alexandria"},
        "offers": [{"type": "Tickets", "url": "https://tickets.example.com"}],
    }
    show = _event_to_show("Amy Speace", event)
    assert show is not None
    assert show.artist == "Amy Speace"
    assert show.date == datetime(2026, 4, 12, 20, 0, 0)
    assert show.venue_name == "The Birchmere"
    assert show.city == "Alexandria"
    assert show.ticket_url == "https://tickets.example.com"
    assert show.show_id == "12345"


def test_event_to_show_missing_date_returns_none():
    event = {"id": "1", "venue": {"name": "V", "city": "C"}}
    assert _event_to_show("Artist", event) is None


def test_event_to_show_malformed_date_returns_none():
    event = {"id": "1", "datetime": "not-a-date", "venue": {"name": "V", "city": "C"}}
    assert _event_to_show("Artist", event) is None


def test_event_to_show_no_offers_uses_event_url():
    event = {
        "id": "1",
        "datetime": "2026-04-12T20:00:00",
        "venue": {"name": "V", "city": "C"},
        "url": "https://fallback.example.com",
        "offers": [],
    }
    show = _event_to_show("Artist", event)
    assert show.ticket_url == "https://fallback.example.com"


def test_event_to_show_no_offers_and_no_url_gives_none():
    event = {
        "id": "1",
        "datetime": "2026-04-12T20:00:00",
        "venue": {"name": "V", "city": "C"},
        "offers": [],
    }
    show = _event_to_show("Artist", event)
    assert show is not None
    assert show.ticket_url is None


def test_artist_name_url_encoding(monkeypatch):
    """Artist names with special chars (& +) must be URL-encoded."""
    import artist_tracker
    calls = []

    def mock_get(url, params=None, timeout=None):
        calls.append(url)
        mock = MagicMock()
        mock.raise_for_status.return_value = None
        mock.json.return_value = []
        return mock

    monkeypatch.setattr("artist_tracker.requests.get", mock_get)
    monkeypatch.setenv("BANDSINTOWN_APP_ID", "test")

    config = {
        "bandsintown": {
            "artists": ["Hootie & The Blowfish"],
            "states": ["VA"],
            "cities": [],
        }
    }
    fetch_regional_shows(config)
    assert len(calls) == 1
    assert "&" not in calls[0].split("?")[0]  # & must be encoded in path
    assert "Hootie" in calls[0]


def test_fetch_regional_shows_filters_correctly(monkeypatch):
    """Integration: only VA/DC/city events returned."""
    fixture = [
        {
            "id": "1", "datetime": "2026-04-12T20:00:00",
            "venue": {"name": "Wolf Trap", "city": "Vienna", "location": "Vienna, VA, United States"},
            "offers": [],
        },
        {
            "id": "2", "datetime": "2026-04-15T20:00:00",
            "venue": {"name": "MSG", "city": "New York", "location": "New York, NY, United States"},
            "offers": [],
        },
    ]

    def mock_get(url, params=None, timeout=None):
        m = MagicMock()
        m.raise_for_status.return_value = None
        m.json.return_value = fixture
        return m

    monkeypatch.setattr("artist_tracker.requests.get", mock_get)
    monkeypatch.setenv("BANDSINTOWN_APP_ID", "test")

    config = {
        "bandsintown": {
            "artists": ["Amy Speace"],
            "states": ["VA", "DC"],
            "cities": ["Baltimore"],
        }
    }
    shows = fetch_regional_shows(config)
    assert len(shows) == 1
    assert shows[0].city == "Vienna"
