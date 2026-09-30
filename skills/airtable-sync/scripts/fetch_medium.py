"""Fetch the Medium posts the Blogposts table is checked against.

Reads the Ersilia publication feed and the personal feeds listed in
`references/sources.json`. Medium RSS returns only the latest 10 posts per feed, so
this sees recent posts only; older gaps are out of reach by design.

A post can appear in several feeds (written on a personal account, then added to the
publication). Posts are merged by Medium post id, keeping the earliest date and
preferring the publication URL. Writes

    {"posts": [{"post_id", "title", "date", "url", "in_publication", "author",
                "tags", "feeds"}], "errors": [...]}

Exit 1 only if every feed failed.

Usage:
    python fetch_medium.py [--sources references/sources.json] \
        [--out /tmp/airtable_sync/medium.json]
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from _common import (
    SKILL_DIR,
    WORK_DIR,
    clean_url,
    die,
    fetch,
    medium_post_id,
    read_json,
    write_json,
)

DC = "{http://purl.org/dc/elements/1.1/}"


def parse_feed(xml_text: str, feed: str) -> list[dict]:
    """Return the items of one Medium RSS feed as plain dicts."""
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        url = clean_url(it.findtext("link"))
        pub = it.findtext("pubDate")
        items.append(
            {
                "post_id": medium_post_id(url),
                "title": (it.findtext("title") or "").strip(),
                "date": parsedate_to_datetime(pub).date().isoformat() if pub else None,
                "url": url,
                "in_publication": "/ersiliaio/" in url,
                "author": (it.findtext(f"{DC}creator") or "").strip(),
                "tags": [c.text for c in it.findall("category") if c.text],
                "feeds": [feed],
            }
        )
    return items


def merge(items: list[dict]) -> list[dict]:
    """Merge the same post seen in several feeds: earliest date, publication URL wins."""
    by_id: dict[str, dict] = {}
    for it in items:
        key = it["post_id"] or it["url"]
        cur = by_id.get(key)
        if cur is None:
            by_id[key] = it
            continue
        cur["feeds"] = sorted(set(cur["feeds"]) | set(it["feeds"]))
        if it["date"] and (not cur["date"] or it["date"] < cur["date"]):
            cur["date"] = it["date"]
        if it["in_publication"] and not cur["in_publication"]:
            cur["url"], cur["in_publication"] = it["url"], True
        cur["tags"] = cur["tags"] or it["tags"]
    return sorted(by_id.values(), key=lambda x: x["date"] or "", reverse=True)


def main(argv: list[str] | None = None) -> int:
    """Write the merged Medium snapshot to the work directory."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--sources", default=str(SKILL_DIR / "references" / "sources.json"))
    p.add_argument("--out", default=f"{WORK_DIR}/medium.json")
    args = p.parse_args(argv)

    cfg = read_json(args.sources)["medium"]
    feeds = [cfg["publication_feed"], *cfg.get("personal_feeds", [])]
    items, errors = [], []
    for feed in feeds:
        body = fetch(feed)
        if body is None:
            errors.append(f"feed unavailable: {feed}")
            continue
        try:
            items.extend(parse_feed(body, feed))
        except ET.ParseError as exc:
            errors.append(f"feed not parseable: {feed}: {exc}")
    if len(errors) == len(feeds):
        die("every Medium feed failed")

    posts = merge(items)
    write_json(args.out, {"posts": posts, "errors": errors})
    print(
        f"medium: {len(posts)} posts from {len(feeds) - len(errors)}/{len(feeds)} feeds -> {args.out}"
    )
    for e in errors:
        print(f"  partial: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
