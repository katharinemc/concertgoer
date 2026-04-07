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
