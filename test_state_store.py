import json
import pytest
from datetime import datetime
from models import Show, Pick
from state_store import StateStore


def make_show(show_id: str) -> Show:
    return Show(
        artist="Test Artist",
        date=datetime(2026, 4, 1),
        venue_name="Test Venue",
        city="Richmond",
        ticket_url=None,
        show_id=show_id,
    )


def make_pick(url: str) -> Pick:
    return Pick(
        act="Test Act",
        date=datetime(2026, 4, 1),
        venue="The Birchmere",
        rationale="Great songwriter.",
        url=url,
    )


def test_empty_state_when_file_missing(tmp_path):
    store = StateStore(tmp_path / "reported.json")
    assert store.filter_new_artist_shows([make_show("abc")]) == [make_show("abc")]
    assert store.filter_new_venue_shows([make_pick("http://x.com")]) == [make_pick("http://x.com")]


def test_empty_state_when_file_malformed(tmp_path):
    p = tmp_path / "reported.json"
    p.write_text("not json")
    store = StateStore(p)
    assert store.filter_new_artist_shows([make_show("abc")]) == [make_show("abc")]


def test_filter_removes_already_reported_artist_show(tmp_path):
    p = tmp_path / "reported.json"
    p.write_text(json.dumps({"artist_shows": ["known-id"], "venue_shows": []}))
    store = StateStore(p)
    shows = [make_show("known-id"), make_show("new-id")]
    result = store.filter_new_artist_shows(shows)
    assert len(result) == 1
    assert result[0].show_id == "new-id"


def test_filter_removes_already_reported_venue_show(tmp_path):
    p = tmp_path / "reported.json"
    p.write_text(json.dumps({"artist_shows": [], "venue_shows": ["http://known.com"]}))
    store = StateStore(p)
    picks = [make_pick("http://known.com"), make_pick("http://new.com")]
    result = store.filter_new_venue_shows(picks)
    assert len(result) == 1
    assert result[0].url == "http://new.com"


def test_mark_reported_persists_and_dedups_on_next_load(tmp_path):
    p = tmp_path / "reported.json"
    store = StateStore(p)
    shows = [make_show("id-1"), make_show("id-2")]
    picks = [make_pick("http://a.com")]
    store.mark_reported(shows, picks)

    store2 = StateStore(p)
    assert store2.filter_new_artist_shows([make_show("id-1")]) == []
    assert store2.filter_new_artist_shows([make_show("id-3")]) == [make_show("id-3")]
    assert store2.filter_new_venue_shows([make_pick("http://a.com")]) == []
    assert store2.filter_new_venue_shows([make_pick("http://b.com")]) == [make_pick("http://b.com")]


def test_mark_reported_is_additive(tmp_path):
    p = tmp_path / "reported.json"
    store = StateStore(p)
    store.mark_reported([make_show("id-1")], [])
    store.mark_reported([make_show("id-2")], [])

    store2 = StateStore(p)
    assert store2.filter_new_artist_shows([make_show("id-1")]) == []
    assert store2.filter_new_artist_shows([make_show("id-2")]) == []


def test_atomic_write_leaves_no_tmp_file_on_success(tmp_path):
    p = tmp_path / "reported.json"
    store = StateStore(p)
    store.mark_reported([make_show("id-1")], [])
    assert p.exists()
    assert not (tmp_path / "reported.tmp").exists()


def test_atomic_write_rename_failure_raises_and_leaves_tmp(tmp_path, monkeypatch):
    """If the rename fails, mark_reported raises and .tmp is left on disk."""
    p = tmp_path / "reported.json"
    store = StateStore(p)

    original_rename = p.with_suffix(".tmp").__class__.rename

    def fail_rename(self, *args, **kwargs):
        raise OSError("rename failed")

    monkeypatch.setattr(p.with_suffix(".tmp").__class__, "rename", fail_rename)

    with pytest.raises(OSError, match="rename failed"):
        store.mark_reported([make_show("id-1")], [])

    assert not p.exists()
    assert (tmp_path / "reported.tmp").exists()


def test_summary_returns_counts(tmp_path):
    p = tmp_path / "reported.json"
    store = StateStore(p)
    store.mark_reported([make_show("id-1"), make_show("id-2")], [make_pick("http://x.com")])
    s = store.summary()
    assert s["artist_shows"] == 2
    assert s["venue_shows"] == 1


def test_summary_with_missing_file(tmp_path):
    store = StateStore(tmp_path / "reported.json")
    s = store.summary()
    assert s["artist_shows"] == 0
    assert s["venue_shows"] == 0
