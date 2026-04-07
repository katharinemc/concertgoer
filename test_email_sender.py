from datetime import datetime
from models import Show, Pick
from email_sender import format_digest_email, _wrap, _divider


def make_show(artist: str, date: datetime, city: str = "Richmond", show_id: str = "1") -> Show:
    return Show(
        artist=artist,
        date=date,
        venue_name="Wolf Trap",
        city=city,
        ticket_url="https://tickets.example.com",
        show_id=show_id,
    )


def make_pick(act: str, date: datetime) -> Pick:
    return Pick(
        act=act,
        date=date,
        venue="The Birchmere",
        rationale="Literate Americana songwriter with a powerful stage presence.",
        url="https://birchmere.com/show",
    )


# ── Helper functions ─────────────────────────────────────────────────────────

def test_divider_with_label():
    d = _divider("ARTIST TOUR DATES")
    assert d.startswith("──")
    assert "ARTIST TOUR DATES" in d


def test_divider_without_label():
    d = _divider()
    assert "─" in d
    assert "─" * 10 in d


def test_wrap_short_text_unchanged():
    lines = _wrap("Short text.", width=68)
    assert lines == ["Short text."]


def test_wrap_long_text_splits():
    long = "This is a longer rationale that should definitely wrap because it exceeds the width limit set."
    lines = _wrap(long, width=50)
    assert len(lines) > 1
    for line in lines:
        assert len(line) <= 50


# ── format_digest_email ──────────────────────────────────────────────────────

def test_returns_empty_strings_when_nothing_to_report():
    subject, body = format_digest_email([], [], "April 2026")
    assert subject == ""
    assert body == ""


def test_subject_contains_month():
    shows = [make_show("Amy Speace", datetime(2026, 4, 12))]
    subject, _ = format_digest_email(shows, [], "April 2026")
    assert "April 2026" in subject
    assert "Concert Digest" in subject


def test_body_contains_artist_section_header():
    shows = [make_show("Amy Speace", datetime(2026, 4, 12))]
    _, body = format_digest_email(shows, [], "April 2026")
    assert "ARTIST TOUR DATES" in body


def test_body_contains_venue_picks_section_header():
    picks = [make_pick("Watchhouse", datetime(2026, 4, 10))]
    _, body = format_digest_email([], picks, "April 2026")
    assert "VENUE PICKS" in body


def test_artist_name_appears_in_body():
    shows = [make_show("Amy Speace", datetime(2026, 4, 12))]
    _, body = format_digest_email(shows, [], "April 2026")
    assert "Amy Speace" in body


def test_pick_act_and_rationale_in_body():
    picks = [make_pick("Watchhouse", datetime(2026, 4, 10))]
    _, body = format_digest_email([], picks, "April 2026")
    assert "Watchhouse" in body
    assert "Literate Americana" in body


def test_empty_artist_section_shows_placeholder():
    picks = [make_pick("Watchhouse", datetime(2026, 4, 10))]
    _, body = format_digest_email([], picks, "April 2026")
    assert "no new shows this month" in body


def test_empty_picks_section_shows_placeholder():
    shows = [make_show("Amy Speace", datetime(2026, 4, 12))]
    _, body = format_digest_email(shows, [], "April 2026")
    assert "no new shows this month" in body


def test_artists_sorted_by_earliest_show_date():
    shows = [
        make_show("Brandi Carlile", datetime(2026, 4, 20), show_id="2"),
        make_show("Amy Speace", datetime(2026, 4, 10), show_id="1"),
    ]
    _, body = format_digest_email(shows, [], "April 2026")
    amy_pos = body.index("Amy Speace")
    brandi_pos = body.index("Brandi Carlile")
    assert amy_pos < brandi_pos


def test_ticket_url_appears_in_body():
    shows = [make_show("Amy Speace", datetime(2026, 4, 12))]
    _, body = format_digest_email(shows, [], "April 2026")
    assert "https://tickets.example.com" in body


def test_picks_sorted_by_date():
    picks = [
        make_pick("Act B", datetime(2026, 4, 20)),
        make_pick("Act A", datetime(2026, 4, 10)),
    ]
    _, body = format_digest_email([], picks, "April 2026")
    a_pos = body.index("Act A")
    b_pos = body.index("Act B")
    assert a_pos < b_pos


# --- Gmail send tests ---

from unittest.mock import MagicMock, patch
import pytest
from email_sender import EmailSender


def make_config(to_address: str = "user@example.com") -> dict:
    return {"email": {"to_address": to_address}}


def make_mock_gmail_service():
    service = MagicMock()
    send_result = MagicMock()
    send_result.execute.return_value = {"id": "msg-123"}
    service.users.return_value.messages.return_value.send.return_value = send_result
    return service


def test_send_calls_gmail_api(monkeypatch, tmp_path):
    service = make_mock_gmail_service()
    sender = EmailSender(make_config())
    sender._service = service

    msg_id = sender.send("Test Subject", "Test body.")
    assert msg_id == "msg-123"
    service.users().messages().send.assert_called_once()


def test_send_message_structure(monkeypatch):
    service = make_mock_gmail_service()
    sender = EmailSender(make_config(to_address="dest@example.com"))
    sender._service = service

    sender.send("My Subject", "My body.")

    call_kwargs = service.users().messages().send.call_args
    body_arg = call_kwargs[1]["body"] if "body" in call_kwargs[1] else call_kwargs[0][1]
    assert "raw" in body_arg


def test_send_raises_on_gmail_exception(monkeypatch):
    service = MagicMock()
    service.users.return_value.messages.return_value.send.return_value.execute.side_effect = Exception("API down")
    sender = EmailSender(make_config())
    sender._service = service

    with pytest.raises(Exception, match="API down"):
        sender.send("Subject", "Body.")
