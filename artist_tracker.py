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
