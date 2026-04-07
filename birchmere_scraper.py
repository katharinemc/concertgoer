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
    containers = soup.select("article.tribe-events-calendar-list__event")
    for container in containers:
        show = _parse_container(container)
        if show:
            shows.append(show)
    return shows


def _parse_container(container) -> VenueShow | None:
    try:
        link_tag = container.select_one("a.tribe-events-calendar-list__event-title-link")
        time_tag = container.select_one("time[datetime]")

        if not link_tag or not time_tag:
            return None

        act = link_tag.get_text(strip=True)
        url = link_tag["href"]
        date_str = time_tag["datetime"]  # ISO format: "2026-04-08"
        date = _parse_date(date_str)
        if date is None:
            log.warning("Birchmere: unparseable date '%s' for act '%s' — skipping", date_str, act)
            return None

        return VenueShow(act=act, date=date, venue=_VENUE, url=url)
    except Exception as e:
        log.warning("Birchmere: failed to parse show container: %s", e)
        return None


def _parse_date(date_str: str) -> datetime | None:
    formats = [
        "%Y-%m-%d",         # "2026-04-08" — primary format from time[datetime]
        "%A, %B %d, %Y",   # "Saturday, April 12, 2026"
        "%B %d, %Y",        # "April 12, 2026"
        "%m/%d/%Y",         # "04/12/2026"
        "%a, %b %d, %Y",   # "Sat, Apr 12, 2026"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None
