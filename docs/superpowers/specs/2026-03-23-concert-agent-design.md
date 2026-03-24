# Concert Discovery Agent — Design Spec

**Date:** 2026-03-23
**Status:** Approved

---

## Purpose

A monthly email digest with two sections:

1. **Artist Tour Dates** — upcoming shows by a tracked artist list near Washington DC and surrounding region
2. **Venue Picks** — recommended shows from The Birchmere and Jammin Java, filtered by taste profile via Claude

---

## Scheduling

The agent is invoked by CLI (`python main.py run`) and executes unconditionally. No internal scheduler.

Future automation: add a system cron entry using the first-Monday-of-month expression:
```
0 8 1-7 * 1   python /path/to/concertgoer/main.py run
```

---

## Module Structure (flat layout, matching souschef conventions)

```
concertgoer/
├── main.py                  # Entry point, argparse subcommands
├── artist_tracker.py        # Bandsintown API + geographic filter
├── birchmere_scraper.py     # Birchmere calendar scraper
├── jamminjava_scraper.py    # Jammin Java calendar scraper
├── venue_picker.py          # Anthropic API — taste-based recommendations
├── email_sender.py          # Email formatting + Gmail OAuth delivery
├── state_store.py           # reported.json read/write, dedup logic
├── config.yaml.template     # Non-secret config template
├── .env.template            # Secret credentials template
├── test_artist_tracker.py
├── test_birchmere_scraper.py
├── test_jamminjava_scraper.py
├── test_venue_picker.py
├── test_email_sender.py
├── test_state_store.py
└── test_main.py
```

---

## Data Flow

```
main.py run
    │
    ├─► artist_tracker.py
    │       GET bandsintown API per artist (all upcoming events)
    │       Filter: state codes (VA, DC) in venue.location
    │                + city names in venue.city / venue.location
    │       Returns list[Show]
    │
    ├─► birchmere_scraper.py
    │       GET birchmere.com, parse upcoming shows
    │       Returns list[VenueShow]
    │
    ├─► jamminjava_scraper.py
    │       GET jamminjava.com, parse upcoming shows
    │       Returns list[VenueShow]
    │
    ├─► venue_picker.py
    │       Takes combined list[VenueShow]
    │       Calls claude-sonnet-4-20250514 with taste profile + show list
    │       Parses JSON array response → list[Pick]
    │
    ├─► state_store.py
    │       Loads reported.json
    │       Filters already-reported IDs/URLs from both result sets
    │       After successful send: appends new IDs/URLs
    │
    └─► email_sender.py
            Formats two-section plain-text email
            Sends via Gmail OAuth
            Returns message ID
```

---

## Data Models

```python
@dataclass
class Show:
    artist: str
    date: datetime
    venue_name: str
    city: str
    ticket_url: str | None
    show_id: str          # Bandsintown event ID, used for dedup

@dataclass
class VenueShow:
    act: str
    date: datetime
    venue: str            # "The Birchmere" or "Jammin Java"
    url: str              # Show page URL, used for dedup

@dataclass
class Pick:
    act: str
    date: datetime
    venue: str
    rationale: str
    url: str
```

---

## Geographic Filter

Bandsintown returns all upcoming events globally per artist. City filtering is applied client-side using two tiers:

**States (match all cities in state):**
- `VA` — all of Virginia (captures NoVA, Richmond, Charlottesville, etc.)
- `DC` — Washington DC proper

**Additional cities (selective MD coverage + other):**
- Baltimore, Towson, Columbia, Bethesda, Silver Spring, Rockville, Hagerstown

Matching logic: case-insensitive check for state code in `venue.location`
(e.g., `", VA,"` in `"Richmond, VA, United States"`) and city name in
`venue.city` or `venue.location`.

Both the states list and cities list are configurable in `config.yaml`.

---

## Bandsintown API

- **Endpoint:** `GET https://rest.bandsintown.com/artists/{name}/events?app_id={id}`
- **app_id:** Any identifier string; set via `BANDSINTOWN_APP_ID` env var
- **Key acquisition:** No formal key required for personal/non-commercial use; registration available at artists.bandsintown.com
- **Free tier:** Fully supports this use case — returns all upcoming events per artist including venue, date, city, lat/lon, and ticket links
- **Rate limiting:** Undocumented; generous for personal scale (30 artists)
- **Scraping fallback:** If the API becomes unavailable, `artist_tracker.py` falls back to scraping `bandsintown.com/{ARTIST_NAME}` pages

---

## Venue Scraping

Two independent scrapers, one per venue. Each:
- GETs the venue's public calendar page
- Parses with BeautifulSoup
- Returns `list[VenueShow]`
- Ships with a saved HTML fixture for offline testing

Venues:
- **The Birchmere** — `https://www.birchmere.com`
- **Jammin Java** — `https://www.jamminjava.com`

---

## Venue Picker (Anthropic API)

- **Model:** `claude-sonnet-4-20250514`
- **Input:** Full `list[VenueShow]` serialized to text + taste profile (below)
- **Output:** JSON array; each element: `{act, date, venue, rationale, url}`
- **Error handling:** Malformed JSON response → log warning, return `[]`; run continues and sends artist shows only

**Taste profile used in prompt:**
> "I'm drawn to literate, emotionally honest songwriting — Americana, folk, and
> singer-songwriter work where the lyrics reward attention. Witty, self-aware
> writing is a strong positive signal even outside acoustic genres. I value
> intimacy over spectacle. At a small venue like the Birchmere or Jammin Java,
> I'll consider a less familiar act if they're a serious songwriter with a
> distinct voice, a cult following in the indie/alt world, or known for
> exceptional live performance. I'm less interested in pure nostalgia acts, jam
> bands, straight country, or high-energy performers where the experience is the
> show rather than the songs. Reference points: Lori McKenna, Aimee Mann, Mark
> Erelli, Jonathan Coulton, The Eels, Brandi Carlile."

---

## State Management

**File:** `reported.json` (path configurable in `config.yaml`)

```json
{
  "artist_shows": ["bandsintown-event-id-1", "bandsintown-event-id-2"],
  "venue_shows": ["https://birchmere.com/shows/xyz", "https://jamminjava.com/events/abc"]
}
```

- `state_store.py` wraps all reads and writes
- `filter_new(shows)` — returns only items whose ID/URL is not in the file
- `mark_reported(shows)` — appends IDs/URLs; uses atomic write (write to `.tmp`, rename)
- State is only updated after a successful email send; a failed send does not update state

---

## Email Format

**Subject:** `Concert Digest: April 2026`

**Body (plain text):**
```
CONCERT DIGEST: APRIL 2026

── ARTIST TOUR DATES ──────────────────────────────────

  Amy Speace
  Sat Apr 12    The Birchmere · Alexandria, VA
                https://ticketweb.com/...

  Brandi Carlile
  Fri Apr 25    Wolf Trap · Vienna, VA
                https://wolftrap.org/...

── VENUE PICKS ────────────────────────────────────────

  Anais Mitchell
  Thu Apr 10    The Birchmere · Alexandria, VA
  Hadestown playwright and folk storyteller — literate,
  theatrically sharp songwriting with a devoted cult following.
  https://birchmere.com/...

──────────────────────────────────────────────────────
```

- Artist Tour Dates: grouped by artist, sorted by date within each artist
- Venue Picks: sorted by date; rationale word-wrapped at 68 chars
- Ticket/show URL on its own indented line
- If a section has no new shows: `  (no new shows this month)`
- If both sections are empty: no email sent, logged as info

---

## Config & Credentials

### `.env` (secrets — never committed)
```
ANTHROPIC_API_KEY=sk-ant-...
BANDSINTOWN_APP_ID=concertgoer
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
```

### `config.yaml` (non-secret — committed)
```yaml
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

`main.py` loads both: `python-dotenv` reads `.env` into env vars at startup;
`config.yaml` is parsed with PyYAML. API keys are accessed via `os.environ`
within each module. No secrets ever enter the config dict passed between modules.

---

## CLI

```
python main.py run        # Fetch, filter, send digest email
python main.py preview    # Dry run — print email to stdout, no send, no state update
python main.py status     # Print state file summary (counts, most recent shows)

Global flags:
  --config PATH     Path to config.yaml (default: config.yaml)
  --dry-run         Alias for preview behaviour from within run command
  --verbose         Enable debug logging
```

---

## Dependencies

```
requests          # HTTP calls (Bandsintown API + venue scraping)
beautifulsoup4    # HTML parsing for venue scrapers
anthropic         # Claude API for venue picks
python-dotenv     # .env loading
pyyaml            # config.yaml parsing
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client  # Gmail OAuth
pytest            # Test runner
```

---

## Testing Strategy

One `test_<module>.py` per module, alongside the module (no `tests/` subdirectory).

| File | Approach |
|------|----------|
| `test_artist_tracker.py` | Mock `requests.get`; fixture JSON with VA, DC, MD, and out-of-region events; assert filter correctness and Show field population |
| `test_birchmere_scraper.py` | Saved HTML fixture; assert expected acts, dates, URLs |
| `test_jamminjava_scraper.py` | Saved HTML fixture; assert expected acts, dates, URLs |
| `test_venue_picker.py` | Mock Anthropic SDK; assert prompt contains taste profile + show list; test malformed JSON → `[]` |
| `test_email_sender.py` | Test `format_digest_email()` in isolation; assert section headers, grouping, empty-section handling |
| `test_state_store.py` | `tmp_path` fixture; test filter, mark-reported, dedup across runs, atomic write |
| `test_main.py` | Smoke-test `preview` subcommand with mocked sub-modules |

---

## Future Work (out of scope)

- Refactor souschef to use `.env` for secrets (matching this agent's security posture)
- Add system cron entry for first-Monday-of-month automation: `0 8 1-7 * 1`
- Add third venue (e.g., 9:30 Club) by adding a new `<venue>_scraper.py`
- `cities_exclude` config list to suppress noisy out-of-range VA cities
