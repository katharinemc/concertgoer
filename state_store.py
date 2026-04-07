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
