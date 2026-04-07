import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from models import Show, Pick


CONFIG = {
    "email": {"to_address": "user@example.com"},
    "bandsintown": {"artists": ["Amy Speace"], "states": ["VA"], "cities": []},
    "venues": [{"name": "The Birchmere", "url": "https://www.birchmere.com"}],
    "state": {"path": "/tmp/test_reported.json"},
    "anthropic": {"model": "claude-sonnet-4-20250514"},
}

SHOW = Show(
    artist="Amy Speace",
    date=datetime(2026, 4, 12),
    venue_name="Wolf Trap",
    city="Vienna",
    ticket_url="https://tickets.example.com",
    show_id="test-show-1",
)

PICK = Pick(
    act="Watchhouse",
    date=datetime(2026, 4, 10),
    venue="The Birchmere",
    rationale="Great songwriter.",
    url="https://birchmere.com/watchhouse",
)


# ── preview ───────────────────────────────────────────────────────────────────

def test_preview_prints_and_does_not_send(tmp_path, capsys):
    config = {**CONFIG, "state": {"path": str(tmp_path / "reported.json")}}
    import main as m
    with patch.object(m, "fetch_regional_shows", return_value=[SHOW]), \
         patch.object(m, "scrape_birchmere", return_value=[]), \
         patch.object(m, "scrape_jamminjava", return_value=[]), \
         patch.object(m, "pick_shows", return_value=[PICK]), \
         patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "preview"]):
        m.main()

    out = capsys.readouterr().out
    assert "Concert Digest" in out
    assert not (tmp_path / "reported.json").exists()


# ── run ───────────────────────────────────────────────────────────────────────

def test_run_updates_state_on_successful_send(tmp_path):
    config = {**CONFIG, "state": {"path": str(tmp_path / "reported.json")}}
    mock_sender = MagicMock()
    mock_sender.send.return_value = "msg-123"

    import main as m
    with patch.object(m, "fetch_regional_shows", return_value=[SHOW]), \
         patch.object(m, "scrape_birchmere", return_value=[]), \
         patch.object(m, "scrape_jamminjava", return_value=[]), \
         patch.object(m, "pick_shows", return_value=[PICK]), \
         patch.object(m, "EmailSender", return_value=mock_sender), \
         patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "run"]):
        m.main()

    mock_sender.send.assert_called_once()
    assert (tmp_path / "reported.json").exists()


def test_run_does_not_update_state_when_send_fails(tmp_path):
    config = {**CONFIG, "state": {"path": str(tmp_path / "reported.json")}}
    mock_sender = MagicMock()
    mock_sender.send.side_effect = Exception("Gmail down")

    import main as m
    with patch.object(m, "fetch_regional_shows", return_value=[SHOW]), \
         patch.object(m, "scrape_birchmere", return_value=[]), \
         patch.object(m, "scrape_jamminjava", return_value=[]), \
         patch.object(m, "pick_shows", return_value=[PICK]), \
         patch.object(m, "EmailSender", return_value=mock_sender), \
         patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "run"]):
        with pytest.raises(SystemExit):
            m.main()

    assert not (tmp_path / "reported.json").exists()


def test_run_skips_email_when_nothing_new(tmp_path):
    import json
    state_path = tmp_path / "reported.json"
    original_content = json.dumps({
        "artist_shows": [SHOW.show_id],
        "venue_shows": [PICK.url],
    })
    state_path.write_text(original_content)
    config = {**CONFIG, "state": {"path": str(state_path)}}
    mock_sender = MagicMock()

    import main as m
    with patch.object(m, "fetch_regional_shows", return_value=[SHOW]), \
         patch.object(m, "scrape_birchmere", return_value=[]), \
         patch.object(m, "scrape_jamminjava", return_value=[]), \
         patch.object(m, "pick_shows", return_value=[PICK]), \
         patch.object(m, "EmailSender", return_value=mock_sender), \
         patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "run"]):
        m.main()

    mock_sender.send.assert_not_called()
    assert state_path.read_text() == original_content


# ── status ────────────────────────────────────────────────────────────────────

def test_status_prints_summary(tmp_path, capsys):
    import json
    state_path = tmp_path / "reported.json"
    state_path.write_text(json.dumps({"artist_shows": ["a", "b"], "venue_shows": ["c"]}))
    config = {**CONFIG, "state": {"path": str(state_path)}}

    import main as m
    with patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "status"]):
        m.main()

    out = capsys.readouterr().out
    assert "2" in out
    assert "1" in out


def test_status_with_missing_state_file(tmp_path, capsys):
    config = {**CONFIG, "state": {"path": str(tmp_path / "missing.json")}}

    import main as m
    with patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "status"]):
        m.main()

    out = capsys.readouterr().out
    assert "0" in out
