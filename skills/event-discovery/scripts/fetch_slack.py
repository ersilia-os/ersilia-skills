#!/usr/bin/env python3
"""Normalise raw Slack messages into event *candidates*.

Slack data flow:
    Claude (via the Slack MCP) → raw JSON file → this script → candidates JSON.

This script does NOT call Slack. The MCP tools (``slack_search_channels``,
``slack_read_channel``, ``slack_read_user_profile``) are only callable from inside
Claude Code; SKILL.md Step 2a tells Claude to collect messages, save them, then run
this script.

**It emits candidates, not events.** A Slack message gives a URL and a sharer —
never the `name`, `start_date` and `location` that `REQUIRED_EVENT_FIELDS`
demands. Trying to synthesise those here would mean inventing dates, which the
skill forbids outright. So each candidate carries what Slack actually knows, and
Step 3 fetches the official page to fill the rest. A candidate that cannot be
verified is still kept (see SKILL.md Step 2a) but marked, because silently
dropping a teammate's contribution is the worse failure.

Usage:
    python fetch_slack.py --raw /tmp/slack_raw.json --out /tmp/slack_candidates.json \
        [--exclude-user U0B1L56S3HS] [--channel "#networking"]
"""

import argparse
import re
import sys

from _common import read_json, warn, write_json

URL_REGEX = re.compile(r"https?://[^\s\)\"<>|]+")
# Slack renders links as <url|label>; capture the url and discard the label.
SLACK_LINK_REGEX = re.compile(r"<(?P<url>https?://[^|>]+)(?:\|[^>]*)?>")

# Phrases identifying this skill's OWN Step 9 alert. Both spellings are listed: the
# pre-rename "Event Discovery" and the current "Event Digest".
#
# THIS IS THE FEEDBACK-LOOP GUARD. Step 9 posts the alert *into* the same channel this
# step reads, so without it every run re-ingests its own previous alert as a fresh batch
# of candidate events, compounding monthly.
#
# Matched against NORMALISED text, never the raw string. Slack does not store a message
# the way it was sent: the 📅 emoji comes back as the shortcode `:date:`, and the MCP
# rewrites markdown emphasis (a sent `*bold*` is stored `_bold_`). A literal
# "📅 *Ersilia Event Digest" prefix match therefore never fires on a real message —
# verified against the alert posted to #networking on 2026-08-04, which sailed past this
# guard and was only stopped by the self-URL filter below.
ALERT_PHRASES = (
    "ersilia event digest",
    "ersilia event discovery",
)

# Self-referential URLs: links to our own published digests are never new events.
SELF_URL_MARKERS = (
    "ersilia-os.github.io/digests",
    "github.com/ersilia-os/digests",
)


def normalise_url(url):
    """Lowercase host + strip tracking noise, for de-duplication only.

    The original URL string is what gets emitted; this is just the dedup key.
    """
    u = str(url or "").strip()
    if not u:
        return ""
    u = re.sub(r"[?&](utm_[^=]+|fbclid|gclid)=[^&]*", "", u)
    u = u.rstrip("/.,);]>\"'")
    return u.lower()


def normalise_for_match(text):
    """Flatten a Slack message enough to recognise our own alert in it.

    Strips emoji shortcodes (`:date:`), any emphasis marks whichever flavour Slack
    stored, and remaining punctuation/emoji, then collapses whitespace and lowercases.
    """
    out = re.sub(r":[a-z0-9_+'-]+:", " ", str(text or ""))
    out = re.sub(r"[*_~`]", "", out)
    out = re.sub(r"[^\w\s]", " ", out)
    return re.sub(r"\s+", " ", out).strip().lower()


def is_own_alert(text):
    """True when the message is one of this skill's own published alerts.

    Prefix match on the normalised text: the alert always *opens* with the digest
    title. Deliberately not a substring match anywhere in the body — a teammate
    quoting or replying to the alert is a real message, and dropping it would be the
    worse failure (see SKILL.md Step 2a).
    """
    flat = normalise_for_match(text)
    return any(flat.startswith(phrase) for phrase in ALERT_PHRASES)


def extract_urls(text):
    """Every distinct URL in the message body, Slack-link form first."""
    seen = set()
    out = []
    for match in SLACK_LINK_REGEX.finditer(text or ""):
        url = match.group("url")
        key = normalise_url(url)
        if key and key not in seen:
            seen.add(key)
            out.append(url)
    for raw in URL_REGEX.findall(text or ""):
        key = normalise_url(raw)
        if key and key not in seen:
            seen.add(key)
            out.append(raw)
    return out


def clean_text(text):
    """Message text with URLs stripped, for the human-readable note."""
    out = SLACK_LINK_REGEX.sub("", text or "")
    out = URL_REGEX.sub("", out)
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > 300:
        out = out[:297] + "..."
    return out


def ts_to_date(ts):
    """Slack ts is a unix-epoch string like '1785849827.486669' -> 'YYYY-MM-DD'."""
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).date().isoformat()
    except (ValueError, OSError, TypeError):
        return ""


def normalise_message(msg, channel_default, exclude_users):
    """One raw message -> zero or more candidates (one per distinct URL)."""
    text = msg.get("text") or ""

    if is_own_alert(text):
        return []

    user_id = str(msg.get("user") or "").strip()
    if user_id and user_id in exclude_users:
        return []

    sharer = (
        msg.get("user_real_name")
        or msg.get("user_name")
        or user_id
        or "unknown"
    )
    channel = msg.get("channel_name") or channel_default
    shared_at = ts_to_date(msg.get("ts", ""))
    note = clean_text(text)

    candidates = []
    for url in extract_urls(text):
        key = normalise_url(url)
        if any(marker in key for marker in SELF_URL_MARKERS):
            continue
        candidates.append({
            "url": url,
            "shared_by": sharer,
            "shared_at": shared_at,
            "channel": channel,
            "permalink": msg.get("permalink"),
            "note": note,
            # Consumed by Step 5: sets `source`, the 💬 marker, and the
            # verify-or-mark (rather than verify-or-drop) path in Step 3.
            "human_sourced": True,
        })
    return candidates


def main(argv=None):
    parser = argparse.ArgumentParser(description="Normalise raw Slack messages into "
                                                 "event candidates.")
    parser.add_argument("--raw", required=True,
                        help="JSON file of raw Slack messages collected via the MCP")
    parser.add_argument("--out", required=True, help="output candidates JSON path")
    parser.add_argument("--channel", default="#networking",
                        help="channel name to record when a message omits it")
    parser.add_argument("--exclude-user", dest="exclude_user", default="",
                        help="comma-separated Slack user IDs whose messages to skip — "
                             "pass the identity that posts the Step 9 alert so the run "
                             "cannot re-ingest its own output")
    args = parser.parse_args(argv)

    exclude_users = {u.strip() for u in args.exclude_user.split(",") if u.strip()}

    raw = read_json(args.raw)
    if not isinstance(raw, list):
        print("ERROR: --raw must contain a JSON array of message objects", file=sys.stderr)
        sys.exit(1)

    candidates = []
    skipped_own = 0
    skipped_user = 0
    for msg in raw:
        if not isinstance(msg, dict):
            continue
        if is_own_alert(msg.get("text")):
            skipped_own += 1
            continue
        uid = str(msg.get("user") or "").strip()
        if uid and uid in exclude_users:
            skipped_user += 1
            continue
        candidates.extend(normalise_message(msg, args.channel, exclude_users))

    # De-duplicate across messages: two people sharing the same link is one candidate,
    # crediting whoever posted it first.
    deduped = []
    seen = set()
    for cand in candidates:
        key = normalise_url(cand["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cand)

    write_json(args.out, deduped)

    if skipped_own:
        warn(f"skipped {skipped_own} message(s) matching this skill's own alert "
             "(feedback-loop guard)")
    if skipped_user:
        warn(f"skipped {skipped_user} message(s) from excluded user IDs")
    if not exclude_users:
        warn("no --exclude-user given; relying on text-signature matching alone to avoid "
             "re-ingesting this skill's own alerts")
    dropped = len(candidates) - len(deduped)
    print(f"slack: {len(deduped)} candidate(s) from {len(raw)} message(s)"
          + (f", {dropped} duplicate URL(s) collapsed" if dropped else ""),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
