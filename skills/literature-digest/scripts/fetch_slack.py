"""Normalise raw Slack messages into literature-digest item schema.

Slack data flow:
    Claude (via the Slack MCP) → raw JSON file → this script → canonical JSON file.

This script does NOT call Slack itself. The Slack MCP tools (`slack_search_channels`,
`slack_read_channel`, `slack_read_thread`, `slack_read_user_profile`) are only callable
from within Claude Code; SKILL.md tells Claude to collect messages, save them, then invoke
this script.

The expected `--raw` JSON file is a list of message dicts. Each message must have at
least `text` and `ts`. Recommended additional keys:
- `user_name` or `user_real_name` (for attribution)
- `permalink` (the Slack message permalink)
- `channel_name` (e.g. "#literature")

One Slack message can contain multiple URLs. We emit one canonical item per *URL* found
in the message text, attributing the sharer.

Usage:
    python fetch_slack.py --raw /tmp/slack_raw.json --out /tmp/slack.json
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from typing import Any

from _common import (
    extract_arxiv_ids,
    extract_dois,
    normalise_url,
    read_json,
    validate_item,
    warn,
    write_json,
)

URL_REGEX = re.compile(r"https?://[^\s\)\"<>|]+")
# Slack puts URLs as <url|label>; strip the label.
SLACK_LINK_REGEX = re.compile(r"<(?P<url>https?://[^|>]+)(?:\|[^>]*)?>")


def extract_urls(text: str) -> list[str]:
    """Pull every URL out of the message body. De-duplicate."""
    seen: set[str] = set()
    out: list[str] = []
    for m in SLACK_LINK_REGEX.finditer(text or ""):
        u = m.group("url")
        nu = normalise_url(u)
        if nu and nu not in seen:
            seen.add(nu)
            out.append(u)  # preserve original for the URL field
    for raw in URL_REGEX.findall(text or ""):
        nu = normalise_url(raw)
        if nu and nu not in seen:
            seen.add(nu)
            out.append(raw)
    return out


def guess_venue(url: str) -> str:
    """Cheap host-based venue tag. The ranker can override with proper journal detection."""
    u = url.lower()
    if "biorxiv.org" in u:
        return "bioRxiv"
    if "chemrxiv.org" in u:
        return "chemRxiv"
    if "medrxiv.org" in u:
        return "medRxiv"
    if "arxiv.org" in u:
        return "arXiv"
    if "doi.org" in u or "europepmc.org" in u or "pubmed.ncbi" in u:
        return "Peer-reviewed (resolve via DOI)"
    if "github.com" in u:
        return "GitHub"
    if "huggingface.co" in u:
        return "Hugging Face"
    if "ersilia.io" in u:
        return "Ersilia"
    return "Web link"


def slack_ts_to_date(ts: str) -> str:
    """Slack ts is a unix-epoch string like '1715760000.000200'."""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).date().isoformat()
    except (ValueError, OSError):
        return ""


def normalise_message(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """One message → zero or more canonical items (one per URL)."""
    text = msg.get("text") or ""
    urls = extract_urls(text)
    if not urls:
        return []

    sharer = (
        msg.get("user_real_name")
        or msg.get("user_name")
        or msg.get("user")
        or "unknown"
    )
    permalink = msg.get("permalink")
    channel_name = msg.get("channel_name") or "#literature"
    date = slack_ts_to_date(msg.get("ts", ""))

    items: list[dict[str, Any]] = []
    for url in urls:
        # Identifiers parsed from the URL or from the message text help dedup downstream.
        dois = extract_dois(url) + extract_dois(text)
        doi = dois[0] if dois else None
        arxiv_ids = extract_arxiv_ids(url) + extract_arxiv_ids(text)
        arxiv_id = arxiv_ids[0] if arxiv_ids else None

        # Slack text is the best available "title" for now; the ranker can resolve later.
        # Strip the URL itself out of the title to keep it readable.
        title = SLACK_LINK_REGEX.sub("", text)
        title = URL_REGEX.sub("", title).strip()
        title = re.sub(r"\s+", " ", title)
        if len(title) > 200:
            title = title[:197] + "..."
        if not title:
            title = f"Shared link from {channel_name}"

        item = {
            "title": title,
            "authors": [{"name": f"@{sharer}", "affiliation": "Ersilia (Slack)", "country": None}],
            "venue": guess_venue(url),
            "date": date or datetime.utcnow().date().isoformat(),
            "doi": doi,
            "arxiv_id": arxiv_id,
            "url": url,
            "abstract": None,
            "source": "slack",
            "source_subtype": channel_name,
            "raw": {
                "ts": msg.get("ts"),
                "user": msg.get("user"),
                "user_name": msg.get("user_name"),
                "user_real_name": msg.get("user_real_name"),
                "permalink": permalink,
                "channel_name": channel_name,
                "text": text,
            },
        }
        errs = validate_item(item)
        if errs:
            warn(f"slack item dropped: {'; '.join(errs)} — {title[:80]}")
            continue
        items.append(item)
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", required=True,
                   help="Path to JSON file with raw Slack messages collected via the MCP.")
    p.add_argument("--out", required=True, help="Output JSON path.")
    args = p.parse_args(argv)

    try:
        raw = read_json(args.raw)
    except (FileNotFoundError, ValueError) as e:
        warn(f"could not read raw slack file: {e}")
        write_json(args.out, [])
        return 0

    items: list[dict[str, Any]] = []
    for msg in raw:
        if not isinstance(msg, dict):
            continue
        items.extend(normalise_message(msg))

    write_json(args.out, items)
    print(f"slack: wrote {len(items)} items to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
