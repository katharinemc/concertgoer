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
