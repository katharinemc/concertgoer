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
