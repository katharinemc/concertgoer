import json
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from models import VenueShow, Pick
from venue_picker import pick_shows, _build_prompt, TASTE_PROFILE


def make_venue_show(act: str, url: str) -> VenueShow:
    return VenueShow(
        act=act,
        date=datetime(2026, 4, 10),
        venue="The Birchmere",
        url=url,
    )


# ── Prompt construction ──────────────────────────────────────────────────────

def test_prompt_contains_taste_profile():
    shows = [make_venue_show("Test Act", "http://x.com")]
    prompt = _build_prompt(shows)
    assert "literate, emotionally honest" in prompt
    assert "Lori McKenna" in prompt


def test_prompt_contains_show_list():
    shows = [make_venue_show("Amy Speace", "http://x.com/amy")]
    prompt = _build_prompt(shows)
    assert "Amy Speace" in prompt
    assert "http://x.com/amy" in prompt


def test_prompt_instructs_json_output():
    shows = [make_venue_show("Test Act", "http://x.com")]
    prompt = _build_prompt(shows)
    assert "JSON" in prompt
    assert "rationale" in prompt


# ── API call and response parsing ────────────────────────────────────────────

GOOD_RESPONSE = json.dumps([
    {
        "act": "Amy Speace",
        "date": "2026-04-10",
        "venue": "The Birchmere",
        "rationale": "Literate Americana songwriter with a devoted following.",
        "url": "http://birchmere.com/amy",
    }
])


def mock_anthropic_client(response_text: str):
    client = MagicMock()
    message = MagicMock()
    message.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = message
    return client


def test_pick_shows_returns_picks(monkeypatch):
    monkeypatch.setattr("venue_picker.anthropic.Anthropic", lambda: mock_anthropic_client(GOOD_RESPONSE))
    shows = [make_venue_show("Amy Speace", "http://birchmere.com/amy")]
    picks = pick_shows(shows, "claude-sonnet-4-20250514")
    assert len(picks) == 1
    assert picks[0].act == "Amy Speace"
    assert picks[0].date == datetime(2026, 4, 10)
    assert "Americana" in picks[0].rationale


def test_pick_shows_empty_input_returns_empty():
    picks = pick_shows([], "claude-sonnet-4-20250514")
    assert picks == []


def test_malformed_json_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        "venue_picker.anthropic.Anthropic",
        lambda: mock_anthropic_client("not valid json at all"),
    )
    shows = [make_venue_show("Test Act", "http://x.com")]
    picks = pick_shows(shows, "claude-sonnet-4-20250514")
    assert picks == []


def test_unparseable_date_in_pick_is_skipped(monkeypatch):
    bad_response = json.dumps([
        {"act": "A", "date": "not-a-date", "venue": "V", "rationale": "R", "url": "http://x.com"},
        {"act": "B", "date": "2026-04-10", "venue": "V", "rationale": "R", "url": "http://y.com"},
    ])
    monkeypatch.setattr("venue_picker.anthropic.Anthropic", lambda: mock_anthropic_client(bad_response))
    shows = [make_venue_show("Test", "http://x.com")]
    picks = pick_shows(shows, "claude-sonnet-4-20250514")
    assert len(picks) == 1
    assert picks[0].act == "B"


def test_api_exception_propagates(monkeypatch):
    import anthropic as anthropic_module
    client = MagicMock()
    client.messages.create.side_effect = anthropic_module.APIError(
        message="auth error", request=MagicMock(), body=None
    )
    monkeypatch.setattr("venue_picker.anthropic.Anthropic", lambda: client)
    shows = [make_venue_show("Test", "http://x.com")]
    with pytest.raises(anthropic_module.APIError):
        pick_shows(shows, "claude-sonnet-4-20250514")
