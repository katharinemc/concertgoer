# Concert Discovery Agent — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Python:** 3.10+

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
The expression `1-7 * 1` means: day-of-month 1–7, any month, only on Mondays —
which selects exactly the first Monday of each month.

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
    │       Returns list[VenueShow]  (empty list on error — see error handling)
    │
    ├─► jamminjava_scraper.py
    │       GET jamminjava.com, parse upcoming shows
    │       Returns list[VenueShow]  (empty list on error — see error handling)
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
            Returns message ID (raises on failure — state not updated)
```

---

## Data Models

```python
@dataclass
class Show:
    artist: str
    date: datetime            # timezone-naive, Eastern time assumed
    venue_name: str
    city: str
    ticket_url: str | None
    show_id: str              # Bandsintown event ID, used for dedup

@dataclass
class VenueShow:
    act: str
    date: datetime            # timezone-naive, Eastern time assumed; parsed from HTML
    venue: str                # "The Birchmere" or "Jammin Java"
    url: str                  # Show page URL, used for dedup

@dataclass
class Pick:
    act: str
    date: datetime            # parsed from ISO 8601 string in Claude JSON response
    venue: str
    rationale: str
    url: str
```

**Date parsing notes:**
- `Show.date`: parsed from Bandsintown ISO 8601 datetime string in API response;
  missing, null, or malformed value → show skipped with a logged warning
- `VenueShow.date`: parsed from HTML date strings by each scraper; if a date cannot
  be parsed the show is skipped with a logged warning
- `Pick.date`: Claude is instructed to return dates as `YYYY-MM-DD`; parsed to
  `datetime` at midnight; unparseable value → show skipped with a logged warning

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
- **Scraping fallback:** Deferred to future work (see below)

---

## Venue Scraping

Two independent scrapers, one per venue. Each:
- GETs the venue's public calendar page with `requests`
- Parses with BeautifulSoup
- Returns `list[VenueShow]`
- Ships with a saved HTML fixture for offline testing

**Error handling:** Any HTTP error (network failure, 4xx/5xx) or parsing exception
→ log a warning including the venue name and error, return `[]`. The run continues
with an empty list for that venue. Zero-result parsing (no shows found in otherwise
valid HTML) is also logged as a warning but does not abort the run.

Venues:
- **The Birchmere** — `https://www.birchmere.com`
- **Jammin Java** — `https://www.jamminjava.com`

---

## Venue Picker (Anthropic API)

- **Model:** `claude-sonnet-4-20250514`
- **SDK call pattern:** Single `messages.create` call with one user-role message
  containing the serialized show list and taste profile. Claude is instructed in
  the message body to return a raw JSON array (no markdown fences). No tool_use
  or structured output feature is used; the response `.content[0].text` is parsed
  directly as JSON.
- **Prompt structure:** The user message contains: (1) the taste profile, (2) the
  full show list formatted as plain text (one show per line: act, date, venue),
  (3) explicit instruction to return a JSON array of up to 5 picks, each with
  fields `{act, date, venue, rationale, url}` where `date` is `YYYY-MM-DD`.
- **Max picks:** 5 (stated in the prompt; enforced by post-processing if Claude
  returns more)
- **Error handling:** Malformed JSON response → log warning, return `[]`; run
  continues and sends artist shows only. API call failure (network, auth) → log
  error and raise; run aborts.

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

**Failure cases:**
- `reported.json` missing at startup → treat as empty state (create fresh on next write)
- `reported.json` exists but contains malformed JSON → log warning, treat as empty state
- `.tmp` write fails (disk full, permissions) → log error, raise; state not updated
- Atomic rename fails → log error, raise; state not updated (`.tmp` left on disk for diagnosis)

---

## Email Format

**Subject:** `Concert Digest: April 2026`

**From address:** Derived automatically from the authenticated Gmail OAuth account;
no explicit `from_address` config is required.

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

- **Artist Tour Dates:** Artists sorted by their earliest upcoming show date;
  alphabetical as tiebreaker. Shows sorted by date within each artist.
- **Venue Picks:** Sorted by date; rationale word-wrapped at 68 chars
- Ticket/show URL on its own indented line
- If a section has no new shows: `  (no new shows this month)`
- If both sections are empty: no email sent, logged as info

**Email send error handling:** Gmail API exceptions are caught in `email_sender.py`,
logged as errors, and re-raised so `main.py` can exit with a non-zero code. No
retries are attempted. Because the exception propagates before `state_store.mark_reported`
is called, state is never updated on a failed send.

---

## CLI

```
python main.py run        # Fetch, filter, send digest email
python main.py preview    # Dry run: print email to stdout, no send, no state update
python main.py status     # Print state file summary (counts, most recent shows)

Global flags:
  --config PATH     Path to config.yaml (default: config.yaml)
  --verbose         Enable debug logging
```

`preview` is the canonical dry-run command. It is equivalent to `run` with all
external writes (send + state update) suppressed. There is no separate `--dry-run`
flag — use `preview` instead.

`status` reads `reported.json` and prints counts and the most recently reported
show IDs. If `reported.json` is missing or malformed, `status` prints zeros and
a note that no state has been recorded yet — it does not raise an error.

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
| `test_artist_tracker.py` | Mock `requests.get`; fixture JSON with VA, DC, MD, and out-of-region events; assert filter correctness, Show field population, and artist name URL-encoding (e.g., "Hootie & The Blowfish") |
| `test_birchmere_scraper.py` | Saved HTML fixture; assert expected acts, dates, URLs; assert HTTP error returns `[]` with no exception raised |
| `test_jamminjava_scraper.py` | Same approach as Birchmere; separate fixture and parser |
| `test_venue_picker.py` | Mock Anthropic SDK; assert prompt contains taste profile + show list + max-5 instruction; test malformed JSON → `[]`; test API exception propagates |
| `test_email_sender.py` | Test `format_digest_email()` in isolation (pure function); assert section headers, artist sort order, empty-section handling. Separately: mock Gmail API client; assert correct message structure is passed to `send`; assert Gmail exception is re-raised |
| `test_state_store.py` | `tmp_path` fixture; test filter, mark-reported, dedup across runs, atomic write, missing-file startup, malformed-JSON startup |
| `test_main.py` | Smoke-test `preview`: assert no state written, no email sent. Smoke-test `run`: assert correct module call order, state updated after successful send, state not updated when email raises. Smoke-test `status`: assert prints summary when state file exists and when it is missing. All sub-modules mocked. |

---

## Future Work (out of scope)

- **Bandsintown scraping fallback** — If the API becomes unavailable, fall back to
  scraping `bandsintown.com/{ARTIST_NAME}` pages with BeautifulSoup. Deferred
  until API viability is confirmed in practice.
- Refactor souschef to use `.env` for secrets (matching this agent's security posture)
- Add system cron entry for first-Monday-of-month automation (see Scheduling section)
- Add third venue (e.g., 9:30 Club) by adding a new `<venue>_scraper.py`
- `cities_exclude` config list to suppress noisy out-of-range VA cities
