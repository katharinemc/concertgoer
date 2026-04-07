"""jamminjava_scraper.py — scrape upcoming shows from Jammin Java."""
import logging
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

from models import VenueShow

log = logging.getLogger(__name__)

_URL = "https://www.jamminjava.com"
_VENUE = "Jammin Java"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Jammin Java's site has an SSL certificate issue with some Python builds.
_VERIFY_SSL = False


def scrape() -> list[VenueShow]:
    """Fetch and parse the Jammin Java show calendar. Returns [] on any error."""
    try:
        resp = requests.get(_URL, headers=_HEADERS, timeout=15, verify=_VERIFY_SSL)
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
    # All show items contain an .event-day element
    containers = [
        el for el in soup.select("div.w-dyn-item")
        if el.select_one(".event-day")
    ]
    for container in containers:
        show = _parse_container(container)
        if show:
            shows.append(show)
    return shows


def _parse_container(container) -> VenueShow | None:
    try:
        act_tag = container.select_one("h1") or container.select_one("h2") or container.select_one("h3")
        day_tag = container.select_one(".event-day")
        month_tag = container.select_one(".event-month")
        link_tag = container.select_one("a[href]")

        if not act_tag or not day_tag or not month_tag or not link_tag:
            return None

        act = act_tag.get_text(strip=True)
        month_str = month_tag.get_text(strip=True)
        day_str = day_tag.get_text(strip=True)
        date = _infer_date(month_str, day_str)
        if date is None:
            log.warning("Jammin Java: unparseable date '%s %s' for act '%s' — skipping", month_str, day_str, act)
            return None

        href = link_tag["href"]
        url = href if href.startswith("http") else f"{_URL.rstrip('/')}/{href.lstrip('/')}"

        return VenueShow(act=act, date=date, venue=_VENUE, url=url)
    except Exception as e:
        log.warning("Jammin Java: failed to parse show container: %s", e)
        return None


def _infer_date(month_str: str, day_str: str) -> datetime | None:
    """Parse month abbreviation + day number, inferring the year.

    Jammin Java does not include the year in show containers. We assume the
    current year; if the resulting date is more than 60 days in the past, we
    bump to the next year (handles year-end edge cases).
    """
    try:
        today = date.today()
        dt = datetime.strptime(f"{month_str} {day_str} {today.year}", "%b %d %Y")
        delta = (dt.date() - today).days
        if delta < -60:
            dt = dt.replace(year=today.year + 1)
        return dt
    except ValueError:
        return None
