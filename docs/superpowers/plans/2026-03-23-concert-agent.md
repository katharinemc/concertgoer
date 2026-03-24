# Concert Discovery Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI agent that sends a monthly email digest of upcoming shows by tracked artists near DC and recommended picks from The Birchmere and Jammin Java.

**Architecture:** Flat module layout matching the souschef project. Each module has a single responsibility and communicates via typed dataclasses defined in `models.py`. `main.py` orchestrates the pipeline: fetch → scrape → pick → dedup → send → record.

**Tech Stack:** Python 3.10+, requests, BeautifulSoup4, Anthropic SDK, python-dotenv, PyYAML, Google API client (Gmail OAuth), pytest

---

## File Map

| File | Responsibility |
|------|---------------|
| `models.py` | Shared dataclasses: `Show`, `VenueShow`, `Pick` — **intentional addition to the spec's flat layout.** All three models are imported by multiple modules (`email_sender`, `state_store`, `venue_picker`, scrapers); putting them in a shared file avoids circular imports and keeps each module's imports clean. The spec did not list `models.py` explicitly but the data model section implies a shared location. |
| `state_store.py` | `reported.json` read/write/dedup; atomic writes |
| `artist_tracker.py` | Bandsintown API calls + two-tier geographic filter |
| `birchmere_scraper.py` | Birchmere.com HTML scraper → `list[VenueShow]` |
| `jamminjava_scraper.py` | JamminJava.com HTML scraper → `list[VenueShow]` |
| `venue_picker.py` | Anthropic API call with taste profile → `list[Pick]` |
| `email_sender.py` | `format_digest_email()` (pure) + `EmailSender` (Gmail OAuth) |
| `main.py` | CLI entry point: `run`, `preview`, `status` subcommands |
| `fixtures/birchmere.html` | Saved HTML page for offline scraper tests |
| `fixtures/jamminjava.html` | Saved HTML page for offline scraper tests |
| `test_state_store.py` | Tests for state store |
| `test_artist_tracker.py` | Tests for Bandsintown API + filter |
| `test_birchmere_scraper.py` | Tests against HTML fixture |
| `test_jamminjava_scraper.py` | Tests against HTML fixture |
| `test_venue_picker.py` | Tests with mocked Anthropic SDK |
| `test_email_sender.py` | Tests for formatter (pure) + mocked Gmail send |
| `test_main.py` | Smoke tests for all three subcommands |
| `requirements.txt` | Pinned dependencies |
| `config.yaml.template` | Non-secret config template |
| `.env.template` | Secrets template |
| `.gitignore` | Ignore `.env`, `reported.json`, `token.json`, etc. |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml.template`
- Create: `.env.template`
- Create: `.gitignore`
- Create: `models.py`

- [ ] **Step 1: Create `requirements.txt`**

```
requests>=2.31
beautifulsoup4>=4.12
anthropic>=0.25
python-dotenv>=1.0
pyyaml>=6.0
google-auth>=2.28
google-auth-oauthlib>=1.2
google-auth-httplib2>=0.2
google-api-python-client>=2.120
pytest>=8.0
```

- [ ] **Step 2: Create `config.yaml.template`**

```yaml
# Copy this file to config.yaml and fill in your values.
# config.yaml is committed. Never put secrets here — use .env.

email:
  to_address: your@email.com

bandsintown:
  states:
    - VA
    - DC
  cities:
    - Baltimore
    - Towson
    - Columbia
    - Bethesda
    - Silver Spring
    - Rockville
    - Hagerstown
  artists:
    - Amy Speace
    - Amy Rigby
    - Aimee Mann
    - Mark Erelli
    - Lori McKenna
    - Patty Griffin
    - Robbie Fulks
    - Mike Doughty
    - Mike Viola
    - Ben Sollee
    - Sean Nelson
    - The Long Winters
    - John Roderick
    - Harvey Danger
    - The Red Clay Strays
    - Emerson Woolf & The Whits
    - Grace Potter
    - Nicki Bluhm
    - Weird Al
    - Jonathan Coulton
    - CAKE
    - Hootie & The Blowfish
    - Nathaniel Ratliff
    - Sierra Ferrell
    - Marcy Playground
    - Barenaked Ladies
    - Ray Lamontagne
    - Eels
    - Brandi Carlile
    - Taylor McCall
    - Jim Lauderdale

venues:
  - name: The Birchmere
    url: https://www.birchmere.com
  - name: Jammin Java
    url: https://www.jamminjava.com

state:
  path: reported.json

anthropic:
  model: claude-sonnet-4-20250514
```

- [ ] **Step 3: Create `.env.template`**

```
# Copy this file to .env and fill in real values.
# .env is never committed.

ANTHROPIC_API_KEY=sk-ant-...
BANDSINTOWN_APP_ID=concertgoer
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
```

- [ ] **Step 4: Create `.gitignore`**

```
.env
config.yaml
reported.json
token.json
credentials.json
__pycache__/
*.pyc
.pytest_cache/
fixtures/*.html
```

> **Note:** `fixtures/*.html` are gitignored because they contain scraped
> third-party content. Regenerate them locally when scraper tests need updating
> (see Tasks 4 and 5).

- [ ] **Step 5: Create `models.py`**

```python
"""models.py — shared dataclasses for the concert agent."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Show:
    """An upcoming show by a tracked artist in the configured region."""
    artist: str
    date: datetime          # timezone-naive, Eastern time assumed
    venue_name: str
    city: str
    ticket_url: str | None
    show_id: str            # Bandsintown event ID — used for dedup


@dataclass
class VenueShow:
    """An upcoming show at one of the tracked local venues."""
    act: str
    date: datetime          # timezone-naive, Eastern time assumed
    venue: str              # "The Birchmere" or "Jammin Java"
    url: str                # Show page URL — used for dedup


@dataclass
class Pick:
    """A venue show recommended by the Claude taste-profile filter."""
    act: str
    date: datetime          # parsed from YYYY-MM-DD in Claude JSON response
    venue: str
    rationale: str
    url: str
```

- [ ] **Step 6: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 7: Smoke-test models import**

```bash
python -c "from models import Show, VenueShow, Pick; print('models ok')"
```

Expected: `models ok`

- [ ] **Step 8: Commit**

```bash
git add requirements.txt config.yaml.template .env.template .gitignore models.py
# Note: no test_models.py — models.py is verified by the smoke test in Step 7
# and exercised thoroughly by every other module's tests
git commit -m "feat: project scaffolding and shared data models"
```

---

## Task 2: state_store.py

**Files:**
- Create: `state_store.py`
- Create: `test_state_store.py`

- [ ] **Step 1: Write failing tests**

```python
# test_state_store.py
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

    # Load fresh instance and verify dedup
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

    assert not p.exists()                        # final file was never written
    assert (tmp_path / "reported.tmp").exists()  # .tmp left for diagnosis


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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest test_state_store.py -v
```

Expected: `ImportError: No module named 'state_store'`

- [ ] **Step 3: Implement `state_store.py`**

```python
"""state_store.py — tracks which shows have already been reported."""
import json
import logging
from pathlib import Path

from models import Show, Pick

log = logging.getLogger(__name__)


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._state = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"artist_shows": [], "venue_shows": []}
        try:
            return json.loads(self.path.read_text())
        except json.JSONDecodeError:
            log.warning("reported.json is malformed — treating as empty state")
            return {"artist_shows": [], "venue_shows": []}

    def filter_new_artist_shows(self, shows: list[Show]) -> list[Show]:
        reported = set(self._state.get("artist_shows", []))
        return [s for s in shows if s.show_id not in reported]

    def filter_new_venue_shows(self, shows: list[Pick]) -> list[Pick]:
        reported = set(self._state.get("venue_shows", []))
        return [s for s in shows if s.url not in reported]

    def mark_reported(self, artist_shows: list[Show], venue_shows: list[Pick]) -> None:
        new_state = {
            "artist_shows": list(
                set(self._state.get("artist_shows", [])) | {s.show_id for s in artist_shows}
            ),
            "venue_shows": list(
                set(self._state.get("venue_shows", [])) | {s.url for s in venue_shows}
            ),
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(new_state, indent=2))
        except OSError as e:
            log.error("Failed to write state temp file: %s", e)
            raise
        try:
            tmp.rename(self.path)
        except OSError as e:
            log.error("Failed to rename state temp file: %s", e)
            raise
        self._state = new_state

    def summary(self) -> dict:
        return {
            "artist_shows": len(self._state.get("artist_shows", [])),
            "venue_shows": len(self._state.get("venue_shows", [])),
        }
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest test_state_store.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add state_store.py test_state_store.py
git commit -m "feat: state store with atomic JSON write and dedup"
```

---

## Task 3: artist_tracker.py

**Files:**
- Create: `artist_tracker.py`
- Create: `test_artist_tracker.py`

- [ ] **Step 1: Write failing tests**

```python
# test_artist_tracker.py
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest test_artist_tracker.py -v
```

Expected: `ImportError: No module named 'artist_tracker'`

- [ ] **Step 3: Implement `artist_tracker.py`**

```python
"""artist_tracker.py — fetch upcoming shows from Bandsintown API."""
import logging
import os
import urllib.parse
from datetime import datetime

import requests

from models import Show

log = logging.getLogger(__name__)

_EVENTS_URL = "https://rest.bandsintown.com/artists/{name}/events"


def fetch_regional_shows(config: dict) -> list[Show]:
    """Fetch all upcoming shows for configured artists, filtered to the region."""
    app_id = os.environ["BANDSINTOWN_APP_ID"]
    artists: list[str] = config["bandsintown"]["artists"]
    states: list[str] = config["bandsintown"]["states"]
    cities: list[str] = config["bandsintown"]["cities"]

    all_shows: list[Show] = []
    for artist in artists:
        events = _fetch_events(artist, app_id)
        for event in events:
            if not _matches_region(event, states, cities):
                continue
            show = _event_to_show(artist, event)
            if show is not None:
                all_shows.append(show)
    return all_shows


def _fetch_events(artist: str, app_id: str) -> list[dict]:
    name = urllib.parse.quote(artist, safe="")
    url = _EVENTS_URL.format(name=name)
    try:
        resp = requests.get(url, params={"app_id": app_id}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        log.warning("Bandsintown API error for '%s': %s", artist, e)
        return []


def _matches_region(event: dict, states: list[str], cities: list[str]) -> bool:
    venue = event.get("venue", {})
    location = venue.get("location", "")  # e.g. "Richmond, VA, United States"
    city = venue.get("city", "")

    location_upper = location.upper()
    for state in states:
        if f", {state.upper()}," in location_upper:
            return True

    city_lower = city.lower()
    location_lower = location.lower()
    for c in cities:
        cl = c.lower()
        if cl == city_lower or cl in location_lower:
            return True

    return False


def _event_to_show(artist: str, event: dict) -> Show | None:
    raw_date = event.get("datetime")
    if not raw_date:
        log.warning("Skipping event with missing date for artist '%s'", artist)
        return None
    try:
        date = datetime.fromisoformat(raw_date.rstrip("Z"))
    except ValueError:
        log.warning("Unparseable date '%s' for artist '%s' — skipping", raw_date, artist)
        return None

    venue = event.get("venue", {})
    return Show(
        artist=artist,
        date=date,
        venue_name=venue.get("name", ""),
        city=venue.get("city", ""),
        ticket_url=_extract_ticket_url(event),
        show_id=str(event.get("id", "")),
    )


def _extract_ticket_url(event: dict) -> str | None:
    for offer in event.get("offers", []):
        if offer.get("type") == "Tickets":
            return offer.get("url")
    return event.get("url")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest test_artist_tracker.py -v
```

Expected: all 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add artist_tracker.py test_artist_tracker.py
git commit -m "feat: Bandsintown artist tracker with two-tier geographic filter"
```

---

## Task 4: birchmere_scraper.py

**Files:**
- Create: `fixtures/birchmere.html` (downloaded in step 1)
- Create: `birchmere_scraper.py`
- Create: `test_birchmere_scraper.py`

> **Note:** Birchmere.com renders show listings in static HTML. If fetching the
> page returns empty results (JavaScript-rendered content), you will need to add
> `selenium` or `playwright` to the dependencies. Check the fetched HTML first.

- [ ] **Step 1: Fetch and save the HTML fixture**

```bash
mkdir -p fixtures
python -c "
import requests
r = requests.get('https://www.birchmere.com', headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
r.raise_for_status()
open('fixtures/birchmere.html', 'w').write(r.text)
print('Saved', len(r.text), 'chars')
"
```

- [ ] **Step 2: Inspect the HTML structure to find show elements**

```bash
python -c "
from bs4 import BeautifulSoup
html = open('fixtures/birchmere.html').read()
soup = BeautifulSoup(html, 'html.parser')

# Look for show listings — try common patterns
for tag in ['article', 'li', 'div']:
    candidates = soup.find_all(tag, class_=True)
    show_like = [c for c in candidates if any(
        word in ' '.join(c.get('class', [])).lower()
        for word in ['event', 'show', 'concert', 'listing', 'performance']
    )]
    if show_like:
        print(f'--- Found {len(show_like)} {tag} elements with show-like classes ---')
        print(show_like[0].prettify()[:800])
        break
"
```

Examine the output. Note the CSS selectors for: show container, act name, date, URL.

- [ ] **Step 3: Write failing tests using real data from the fixture**

> Replace the placeholder values below with actual act name, date string, and URL
> from what you observed in Step 2.

```python
# test_birchmere_scraper.py
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from birchmere_scraper import scrape, _parse_shows

_FIXTURE_PATH = Path("fixtures/birchmere.html")

# Skip all fixture-dependent tests if the HTML file has not been downloaded yet.
# Run Task 4 Step 1 to create it.
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
    """Replace with an actual show you can see in the fixture HTML."""
    shows = _parse_shows(fixture_html)
    acts = [s.act for s in shows]
    # TODO: replace "PLACEHOLDER ACT" with a real act from the fixture
    # assert any("PLACEHOLDER ACT" in act for act in acts)
    assert len(acts) > 0  # at minimum, something came back


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
```

- [ ] **Step 4: Run tests — verify they fail**

```bash
pytest test_birchmere_scraper.py -v
```

Expected: `ImportError: No module named 'birchmere_scraper'`
(If fixtures/birchmere.html exists, the fixture-dependent tests will be collected
but the import error fires first. If the fixture does not exist yet, those tests
will be reported as SKIPPED — that is expected and correct.)

- [ ] **Step 5: Implement `birchmere_scraper.py`**

> The CSS selectors below are placeholders. Replace them with what you found
> in Step 2. The structure of this implementation is correct; only the selectors change.

```python
"""birchmere_scraper.py — scrape upcoming shows from The Birchmere."""
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from models import VenueShow

log = logging.getLogger(__name__)

_URL = "https://www.birchmere.com"
_VENUE = "The Birchmere"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; concertgoer/1.0)"}


def scrape() -> list[VenueShow]:
    """Fetch and parse the Birchmere show calendar. Returns [] on any error."""
    try:
        resp = requests.get(_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Birchmere fetch failed: %s", e)
        return []
    shows = _parse_shows(resp.text)
    if not shows:
        log.warning("Birchmere: parsed 0 shows from valid HTML — selector may need updating")
    return shows


def _parse_shows(html: str) -> list[VenueShow]:
    soup = BeautifulSoup(html, "html.parser")
    shows: list[VenueShow] = []

    # TODO: replace this selector with the real container found in Step 2.
    # Example: containers = soup.select("li.event-listing")
    containers = soup.select("REPLACE_WITH_REAL_SELECTOR")

    for container in containers:
        show = _parse_container(container)
        if show:
            shows.append(show)
    return shows


def _parse_container(container) -> VenueShow | None:
    """Extract a VenueShow from one show container. Return None on parse failure."""
    try:
        # TODO: adapt these selectors to match the real HTML structure.
        act_tag = container.select_one("REPLACE_ACT_SELECTOR")
        date_tag = container.select_one("REPLACE_DATE_SELECTOR")
        link_tag = container.select_one("a[href]")

        if not act_tag or not date_tag or not link_tag:
            return None

        act = act_tag.get_text(strip=True)
        date = _parse_date(date_tag.get_text(strip=True))
        if date is None:
            log.warning("Birchmere: unparseable date for act '%s' — skipping", act)
            return None

        href = link_tag["href"]
        url = href if href.startswith("http") else f"{_URL.rstrip('/')}/{href.lstrip('/')}"

        return VenueShow(act=act, date=date, venue=_VENUE, url=url)
    except Exception as e:
        log.warning("Birchmere: failed to parse show container: %s", e)
        return None


def _parse_date(date_str: str) -> datetime | None:
    """Try common date formats. Add more formats as needed for Birchmere's HTML."""
    formats = [
        "%A, %B %d, %Y",   # "Saturday, April 12, 2026"
        "%B %d, %Y",        # "April 12, 2026"
        "%m/%d/%Y",         # "04/12/2026"
        "%Y-%m-%d",         # "2026-04-12"
        "%a, %b %d, %Y",    # "Sat, Apr 12, 2026"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
```

- [ ] **Step 6: Update selectors to match the real HTML**

Edit `_parse_shows` and `_parse_container` in `birchmere_scraper.py` to use the
selectors you identified in Step 2. Run `python -c "from birchmere_scraper import _parse_shows; import pathlib; shows = _parse_shows(pathlib.Path('fixtures/birchmere.html').read_text()); print(len(shows), 'shows'); [print(s) for s in shows[:3]]"` to verify.

- [ ] **Step 7: Update test assertions with real data**

In `test_birchmere_scraper.py`, uncomment and fill in `test_known_show_present` with an actual act name from the fixture.

- [ ] **Step 8: Run tests — verify they pass**

```bash
pytest test_birchmere_scraper.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 9: Commit**

```bash
git add birchmere_scraper.py test_birchmere_scraper.py
git commit -m "feat: Birchmere calendar scraper"
```

---

## Task 5: jamminjava_scraper.py

**Files:**
- Create: `fixtures/jamminjava.html` (downloaded in step 1)
- Create: `jamminjava_scraper.py`
- Create: `test_jamminjava_scraper.py`

Follow the same process as Task 4 for Jammin Java. The steps are identical; only the URL, venue name, and HTML selectors differ.

- [ ] **Step 1: Fetch and save the HTML fixture**

```bash
python -c "
import requests
r = requests.get('https://www.jamminjava.com', headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
r.raise_for_status()
open('fixtures/jamminjava.html', 'w').write(r.text)
print('Saved', len(r.text), 'chars')
"
```

- [ ] **Step 2: Inspect the HTML structure**

```bash
python -c "
from bs4 import BeautifulSoup
html = open('fixtures/jamminjava.html').read()
soup = BeautifulSoup(html, 'html.parser')
for tag in ['article', 'li', 'div']:
    candidates = soup.find_all(tag, class_=True)
    show_like = [c for c in candidates if any(
        word in ' '.join(c.get('class', [])).lower()
        for word in ['event', 'show', 'concert', 'listing', 'performance']
    )]
    if show_like:
        print(f'--- {len(show_like)} {tag} elements ---')
        print(show_like[0].prettify()[:800])
        break
"
```

- [ ] **Step 3: Write failing tests**

```python
# test_jamminjava_scraper.py
from pathlib import Path
import pytest
from unittest.mock import MagicMock
from jamminjava_scraper import scrape, _parse_shows

_FIXTURE_PATH = Path("fixtures/jamminjava.html")

pytestmark = pytest.mark.skipif(
    not _FIXTURE_PATH.exists(),
    reason="fixtures/jamminjava.html not yet downloaded — run Task 5 Step 1 first",
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
    assert show.venue == "Jammin Java"
    assert show.url.startswith("http")
    from datetime import datetime
    assert isinstance(show.date, datetime)


def test_known_show_present(fixture_html):
    shows = _parse_shows(fixture_html)
    # TODO: replace with a real act name from the fixture
    assert len(shows) > 0


def test_http_error_returns_empty_list(monkeypatch):
    import requests
    def mock_get(*args, **kwargs):
        m = MagicMock()
        m.raise_for_status.side_effect = requests.HTTPError("404")
        return m
    monkeypatch.setattr("jamminjava_scraper.requests.get", mock_get)
    assert scrape() == []


def test_network_error_returns_empty_list(monkeypatch):
    import requests
    monkeypatch.setattr(
        "jamminjava_scraper.requests.get",
        lambda *a, **kw: (_ for _ in ()).throw(requests.ConnectionError())
    )
    assert scrape() == []
```

- [ ] **Step 4: Run tests — verify they fail**

```bash
pytest test_jamminjava_scraper.py -v
```

- [ ] **Step 5: Implement `jamminjava_scraper.py`**

```python
"""jamminjava_scraper.py — scrape upcoming shows from Jammin Java."""
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from models import VenueShow

log = logging.getLogger(__name__)

_URL = "https://www.jamminjava.com"
_VENUE = "Jammin Java"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; concertgoer/1.0)"}


def scrape() -> list[VenueShow]:
    """Fetch and parse the Jammin Java show calendar. Returns [] on any error."""
    try:
        resp = requests.get(_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning("Jammin Java fetch failed: %s", e)
        return []
    shows = _parse_shows(resp.text)
    if not shows:
        log.warning("Jammin Java: parsed 0 shows from valid HTML — selector may need updating")
    return shows


def _parse_shows(html: str) -> list[VenueShow]:
    soup = BeautifulSoup(html, "html.parser")
    shows: list[VenueShow] = []

    # TODO: replace with selectors found in Step 2
    containers = soup.select("REPLACE_WITH_REAL_SELECTOR")

    for container in containers:
        show = _parse_container(container)
        if show:
            shows.append(show)
    return shows


def _parse_container(container) -> VenueShow | None:
    try:
        act_tag = container.select_one("REPLACE_ACT_SELECTOR")
        date_tag = container.select_one("REPLACE_DATE_SELECTOR")
        link_tag = container.select_one("a[href]")

        if not act_tag or not date_tag or not link_tag:
            return None

        act = act_tag.get_text(strip=True)
        date = _parse_date(date_tag.get_text(strip=True))
        if date is None:
            log.warning("Jammin Java: unparseable date for act '%s' — skipping", act)
            return None

        href = link_tag["href"]
        url = href if href.startswith("http") else f"{_URL.rstrip('/')}/{href.lstrip('/')}"

        return VenueShow(act=act, date=date, venue=_VENUE, url=url)
    except Exception as e:
        log.warning("Jammin Java: failed to parse show container: %s", e)
        return None


def _parse_date(date_str: str) -> datetime | None:
    formats = [
        "%A, %B %d, %Y",
        "%B %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%a, %b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
```

- [ ] **Step 6: Update selectors, verify against fixture, update test assertions**

Same process as Task 4, Step 6–7.

- [ ] **Step 7: Run tests — verify they pass**

```bash
pytest test_jamminjava_scraper.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 8: Commit**

```bash
git add jamminjava_scraper.py test_jamminjava_scraper.py
git commit -m "feat: Jammin Java calendar scraper"
```

---

## Task 6: venue_picker.py

**Files:**
- Create: `venue_picker.py`
- Create: `test_venue_picker.py`

- [ ] **Step 1: Write failing tests**

```python
# test_venue_picker.py
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
    # Note: anthropic.APIError constructor signature is version-sensitive
    # (requires request= kwarg in some versions). If this test fails at setup,
    # use anthropic_module.AnthropicError or Exception as the side_effect instead.
    client.messages.create.side_effect = anthropic_module.APIError(
        message="auth error", request=MagicMock(), body=None
    )
    monkeypatch.setattr("venue_picker.anthropic.Anthropic", lambda: client)
    shows = [make_venue_show("Test", "http://x.com")]
    with pytest.raises(anthropic_module.APIError):
        pick_shows(shows, "claude-sonnet-4-20250514")
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest test_venue_picker.py -v
```

Expected: `ImportError: No module named 'venue_picker'`

- [ ] **Step 3: Implement `venue_picker.py`**

```python
"""venue_picker.py — recommend venue shows using Claude taste-profile filtering."""
import json
import logging
from datetime import datetime

import anthropic

from models import VenueShow, Pick

log = logging.getLogger(__name__)

TASTE_PROFILE = (
    "I'm drawn to literate, emotionally honest songwriting — Americana, folk, and "
    "singer-songwriter work where the lyrics reward attention. Witty, self-aware "
    "writing is a strong positive signal even outside acoustic genres. I value "
    "intimacy over spectacle. At a small venue like the Birchmere or Jammin Java, "
    "I'll consider a less familiar act if they're a serious songwriter with a "
    "distinct voice, a cult following in the indie/alt world, or known for "
    "exceptional live performance. I'm less interested in pure nostalgia acts, jam "
    "bands, straight country, or high-energy performers where the experience is the "
    "show rather than the songs. Reference points: Lori McKenna, Aimee Mann, Mark "
    "Erelli, Jonathan Coulton, The Eels, Brandi Carlile."
)


def pick_shows(venue_shows: list[VenueShow], model: str) -> list[Pick]:
    """Ask Claude to recommend shows matching the taste profile."""
    if not venue_shows:
        return []

    client = anthropic.Anthropic()
    prompt = _build_prompt(venue_shows)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        log.error("Anthropic API error: %s", e)
        raise

    raw = response.content[0].text
    try:
        picks_data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Claude returned non-JSON; no picks returned. Preview: %s", raw[:200])
        return []

    picks: list[Pick] = []
    for item in picks_data:
        date = _parse_date(item.get("date", ""))
        if date is None:
            log.warning("Skipping pick with unparseable date: %s", item)
            continue
        picks.append(Pick(
            act=item.get("act", ""),
            date=date,
            venue=item.get("venue", ""),
            rationale=item.get("rationale", ""),
            url=item.get("url", ""),
        ))
    return picks


def _build_prompt(venue_shows: list[VenueShow]) -> str:
    show_lines = "\n".join(
        f"- {s.act} | {s.date.strftime('%Y-%m-%d')} | {s.venue} | {s.url}"
        for s in venue_shows
    )
    return f"""You are helping filter upcoming shows at The Birchmere and Jammin Java \
based on a personal taste profile.

Taste profile:
{TASTE_PROFILE}

Upcoming shows:
{show_lines}

Return ONLY a raw JSON array (no markdown fences, no explanation). Each element must \
have exactly these fields:
- "act": string
- "date": string in YYYY-MM-DD format
- "venue": string
- "rationale": one sentence explaining why this show matches the taste profile
- "url": string (copied from the input)

If no shows match, return an empty array: []"""


def _parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest test_venue_picker.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add venue_picker.py test_venue_picker.py
git commit -m "feat: venue picker with Claude taste-profile filtering"
```

---

## Task 7: email_sender.py (formatting)

**Files:**
- Create: `email_sender.py`
- Create: `test_email_sender.py` (formatting tests only — Gmail tests added in Task 8)

- [ ] **Step 1: Write failing tests for the formatter**

```python
# test_email_sender.py
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
    """Artist with show on Apr 10 should appear before artist with show on Apr 20."""
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
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest test_email_sender.py -v
```

Expected: `ImportError: No module named 'email_sender'`

- [ ] **Step 3: Implement `email_sender.py` (formatting only — no Gmail class yet)**

```python
"""email_sender.py — format and send the monthly concert digest via Gmail."""
import base64
import logging
import os
from datetime import datetime
from email.mime.text import MIMEText

from models import Show, Pick

log = logging.getLogger(__name__)

_DIVIDER_WIDTH = 52
_WRAP_WIDTH = 68

ALL_SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


# ── Formatting helpers ────────────────────────────────────────────────────────

def _divider(label: str = "", width: int = _DIVIDER_WIDTH) -> str:
    if label:
        pad = width - len(label) - 4
        return f"── {label} {'─' * max(pad, 2)}"
    return "─" * width


def _wrap(text: str, width: int = _WRAP_WIDTH, indent: str = "  ") -> list[str]:
    if len(text) <= width:
        return [text]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        sep = " " if current else ""
        candidate = current + sep + word
        if len(candidate) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = indent + word
    if current:
        lines.append(current)
    return lines


# ── Email formatter (pure function) ──────────────────────────────────────────

def format_digest_email(
    artist_shows: list[Show],
    picks: list[Pick],
    month_label: str,
) -> tuple[str, str]:
    """
    Format the digest into (subject, body).
    Returns ("", "") if there is nothing to report.
    """
    if not artist_shows and not picks:
        return "", ""

    subject = f"Concert Digest: {month_label}"
    lines: list[str] = []

    lines.append(f"CONCERT DIGEST: {month_label.upper()}")
    lines.append("")

    # ── Artist Tour Dates ──────────────────────────────────────────
    lines.append(_divider("ARTIST TOUR DATES"))
    lines.append("")

    if artist_shows:
        by_artist: dict[str, list[Show]] = {}
        for show in artist_shows:
            by_artist.setdefault(show.artist, []).append(show)

        sorted_artists = sorted(
            by_artist.keys(),
            key=lambda a: (min(s.date for s in by_artist[a]), a),
        )

        for artist in sorted_artists:
            lines.append(f"  {artist}")
            for show in sorted(by_artist[artist], key=lambda s: s.date):
                date_str = show.date.strftime("%a %b %-d")
                venue_city = f"{show.venue_name} · {show.city}"
                lines.append(f"  {date_str:<14}{venue_city}")
                if show.ticket_url:
                    lines.append(f"  {'':14}{show.ticket_url}")
            lines.append("")
    else:
        lines.append("  (no new shows this month)")
        lines.append("")

    # ── Venue Picks ───────────────────────────────────────────────
    lines.append(_divider("VENUE PICKS"))
    lines.append("")

    if picks:
        for pick in sorted(picks, key=lambda p: p.date):
            lines.append(f"  {pick.act}")
            date_str = pick.date.strftime("%a %b %-d")
            lines.append(f"  {date_str:<14}{pick.venue}")
            for wrapped_line in _wrap(f"  {pick.rationale}"):
                lines.append(wrapped_line)
            lines.append(f"  {pick.url}")
            lines.append("")
    else:
        lines.append("  (no new shows this month)")
        lines.append("")

    lines.append(_divider())

    return subject, "\n".join(lines)
```

- [ ] **Step 4: Run formatting tests — verify they pass**

```bash
pytest test_email_sender.py -v
```

Expected: all 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add email_sender.py test_email_sender.py
git commit -m "feat: email formatter with two-section digest layout"
```

---

## Task 8: email_sender.py — Gmail send

**Files:**
- Modify: `email_sender.py` (add `EmailSender` class)
- Modify: `test_email_sender.py` (add Gmail tests)

- [ ] **Step 1: Add Gmail send tests to `test_email_sender.py`**

Append these tests to the existing file:

```python
# --- Gmail send tests (append to test_email_sender.py) ---

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
    sender._service = service  # inject mock service directly

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
```

- [ ] **Step 2: Run new tests — verify they fail**

```bash
pytest test_email_sender.py::test_send_calls_gmail_api -v
```

Expected: `AttributeError: EmailSender` has no `send` method

- [ ] **Step 3: Add `EmailSender` class to `email_sender.py`**

Append to the end of `email_sender.py`:

```python
# ── Gmail sender ──────────────────────────────────────────────────────────────

class EmailSender:
    """Sends the digest email via the Gmail API using OAuth credentials."""

    def __init__(self, config: dict):
        self.to_address: str = config["email"]["to_address"]
        self.credentials_path: str = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
        self.token_path: str = os.environ.get("GMAIL_TOKEN_PATH", "token.json")
        self._service = None

    def _get_service(self):
        if self._service:
            return self._service
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "Google API libraries not installed.\n"
                "Run: pip install google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )

        creds = None
        if os.path.exists(self.token_path):
            from google.oauth2.credentials import Credentials
            creds = Credentials.from_authorized_user_file(self.token_path, ALL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Gmail OAuth credentials not found: {self.credentials_path}\n"
                        "Download credentials.json from Google Cloud Console.\n"
                        "See: https://developers.google.com/gmail/api/quickstart/python"
                    )
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, ALL_SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        from googleapiclient.discovery import build
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def send(self, subject: str, body: str) -> str:
        """Send the email. Returns the Gmail message ID. Raises on failure."""
        msg = MIMEText(body, "plain", "utf-8")
        msg["To"] = self.to_address
        msg["Subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        try:
            service = self._get_service()
            result = service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            log.info("Email sent. Message ID: %s", result.get("id"))
            return result["id"]
        except Exception as e:
            log.error("Gmail send failed: %s", e)
            raise
```

- [ ] **Step 4: Run all email tests — verify they pass**

```bash
pytest test_email_sender.py -v
```

Expected: all 17 tests PASS

- [ ] **Step 5: Commit**

```bash
git add email_sender.py test_email_sender.py
git commit -m "feat: Gmail OAuth sender"
```

---

## Task 9: main.py

**Files:**
- Create: `main.py`
- Create: `test_main.py`

- [ ] **Step 1: Write failing tests**

```python
# test_main.py
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


def run_main(args: list[str], config=CONFIG):
    """Helper: call main() with mocked config loader."""
    import main as m
    with patch.object(m, "load_config", return_value=config):
        with patch("sys.argv", ["main.py"] + args):
            m.main()


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
    # State file must not be modified when there is nothing to send
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
    assert "2" in out  # artist_shows count
    assert "1" in out  # venue_shows count


def test_status_with_missing_state_file(tmp_path, capsys):
    config = {**CONFIG, "state": {"path": str(tmp_path / "missing.json")}}

    import main as m
    with patch.object(m, "load_config", return_value=config), \
         patch("sys.argv", ["main.py", "status"]):
        m.main()

    out = capsys.readouterr().out
    assert "0" in out
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest test_main.py -v
```

Expected: `ImportError: No module named 'main'`

- [ ] **Step 3: Implement `main.py`**

```python
"""main.py — Concert Discovery Agent entry point.

Commands:
  python main.py run        Fetch, filter, and send the monthly digest email.
  python main.py preview    Dry run — print email to stdout without sending.
  python main.py status     Print state file summary (reported show counts).

Global flags:
  --config PATH    Path to config.yaml (default: config.yaml)
  --verbose        Enable debug logging

Future automation (first Monday of each month):
  0 8 1-7 * 1   python /path/to/concertgoer/main.py run
"""
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from artist_tracker import fetch_regional_shows
from birchmere_scraper import scrape as scrape_birchmere
from jamminjava_scraper import scrape as scrape_jamminjava
from venue_picker import pick_shows
from email_sender import EmailSender, format_digest_email
from state_store import StateStore


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("urllib3", "google.auth", "googleapiclient", "httplib2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


log = logging.getLogger("main")


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        log.error("Config not found: %s. Copy config.yaml.template to config.yaml.", path)
        sys.exit(1)
    with open(p) as f:
        return yaml.safe_load(f) or {}


def cmd_run(args, config: dict, dry_run: bool = False) -> None:
    store = StateStore(config["state"]["path"])

    log.info("Fetching artist shows from Bandsintown...")
    artist_shows = fetch_regional_shows(config)
    log.info("%d regional shows found", len(artist_shows))

    log.info("Scraping Birchmere...")
    birchmere_shows = scrape_birchmere()
    log.info("%d Birchmere shows found", len(birchmere_shows))

    log.info("Scraping Jammin Java...")
    jamminjava_shows = scrape_jamminjava()
    log.info("%d Jammin Java shows found", len(jamminjava_shows))

    venue_shows = birchmere_shows + jamminjava_shows

    log.info("Filtering venue shows through taste profile...")
    picks = pick_shows(venue_shows, config["anthropic"]["model"])
    log.info("Claude recommended %d venue picks", len(picks))

    new_artist_shows = store.filter_new_artist_shows(artist_shows)
    new_picks = store.filter_new_venue_shows(picks)
    log.info("New: %d artist shows, %d venue picks", len(new_artist_shows), len(new_picks))

    if not new_artist_shows and not new_picks:
        log.info("Nothing new to report — skipping email.")
        return

    month_label = datetime.now().strftime("%B %Y")
    subject, body = format_digest_email(new_artist_shows, new_picks, month_label)

    if dry_run:
        print("=" * 60)
        print(f"TO:      {config['email']['to_address']}")
        print(f"SUBJECT: {subject}")
        print("=" * 60)
        print(body)
        print("=" * 60)
        return

    sender = EmailSender(config)
    sender.send(subject, body)
    store.mark_reported(new_artist_shows, new_picks)
    log.info("Done. Digest sent and state updated.")


def cmd_preview(args, config: dict) -> None:
    cmd_run(args, config, dry_run=True)


def cmd_status(args, config: dict) -> None:
    store = StateStore(config["state"]["path"])
    summary = store.summary()
    print("\nConcert Agent Status")
    print("─" * 40)
    print(f"  Artist shows reported: {summary['artist_shows']}")
    print(f"  Venue shows reported:  {summary['venue_shows']}")
    print(f"  State file:            {config['state']['path']}")
    if summary["artist_shows"] == 0 and summary["venue_shows"] == 0:
        print("  (no state recorded yet)")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="concertgoer",
        description="Monthly concert discovery digest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config.yaml (default: config.yaml)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    sub.add_parser("run", help="Fetch and send the monthly digest").set_defaults(func=cmd_run)
    sub.add_parser("preview", help="Dry run — print email without sending").set_defaults(func=cmd_preview)
    sub.add_parser("status", help="Print state file summary").set_defaults(func=cmd_status)

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.verbose)
    config = load_config(args.config)

    try:
        args.func(args, config)
    except KeyboardInterrupt:
        log.info("Interrupted.")
        sys.exit(0)
    except Exception as e:
        log.error("Unexpected error: %s", e, exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

```bash
pytest test_main.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS across all modules

- [ ] **Step 6: Commit**

```bash
git add main.py test_main.py
git commit -m "feat: main CLI entry point with run/preview/status subcommands"
```

---

## Task 10: Final wiring and smoke test

**Files:**
- Create: `config.yaml` (from template — not committed)
- Create: `.env` (from template — not committed)

- [ ] **Step 1: Copy templates and fill in values**

```bash
cp config.yaml.template config.yaml
cp .env.template .env
```

Edit `config.yaml`: set `email.to_address` to your email address.
Edit `.env`: set `BANDSINTOWN_APP_ID=concertgoer` and your `ANTHROPIC_API_KEY`.

- [ ] **Step 2: Run preview to verify the pipeline end-to-end**

```bash
python main.py --verbose preview
```

Expected: email body printed to stdout with both sections. If venue scrapers
return empty lists, check that the HTML selectors in Tasks 4–5 were correctly updated.

- [ ] **Step 3: Run the full test suite one final time**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "chore: project complete — all tests passing"
```

---

## Gmail OAuth setup (one-time, manual)

Before `python main.py run` will send email for the first time:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop app type) → Download as `credentials.json`
4. Run `python main.py preview` — it will open a browser to authorize; `token.json` is created automatically
5. Subsequent runs use `token.json` silently

The same credentials work as-is if you already have them from souschef. Just copy
`credentials.json` and `token.json` into the `concertgoer/` directory and add the
Gmail send scope if not already present.
