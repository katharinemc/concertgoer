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
    return (
        f"You are helping filter upcoming shows at The Birchmere and Jammin Java "
        f"based on a personal taste profile.\n\n"
        f"Taste profile:\n{TASTE_PROFILE}\n\n"
        f"Upcoming shows:\n{show_lines}\n\n"
        f"Return ONLY a raw JSON array (no markdown fences, no explanation). "
        f"Each element must have exactly these fields:\n"
        f'- "act": string\n'
        f'- "date": string in YYYY-MM-DD format\n'
        f'- "venue": string\n'
        f'- "rationale": one sentence explaining why this show matches the taste profile\n'
        f'- "url": string (copied from the input)\n\n'
        f"If no shows match, return an empty array: []"
    )


def _parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
