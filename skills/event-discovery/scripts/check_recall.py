#!/usr/bin/env python3
"""Grade a sweep against the recall fixture (SKILL.md Step 6a).

A regression net for **discovery**. Every change to `event-sources.md` or to Step 2's
axis pass is otherwise unverifiable: a sweep that quietly gets worse produces a thin
report, and a thin report looks exactly like a quiet month.

**Warns, never blocks — always exits 0.** This is the deliberate opposite of the
sweep-completeness gate in ``render_report.py``, which *does* block. A missing query is
always the operator's fault and always fixable by running it; a fixture miss may just
mean the event moved, was renamed, or stopped existing. A check that fails on legitimate
misses is a check people learn to bypass.

Usage:
    python check_recall.py --fixture references/recall-fixture.md \
        --pool /tmp/events_pool.json [--clean /tmp/events_clean.json] [--today YYYY-MM-DD]
"""

import argparse
import re
import sys
from datetime import date

from _common import parse_date, read_json, warn
from filter_and_sort import normalise_series_key

SECTIONS = {
    "must find": "find",
    "must exclude": "exclude",
    "must never become an event": "never",
}


def name_tokens(name):
    """Normalised, year-stripped name as a token set.

    Built on ``filter_and_sort.normalise_series_key`` so the fixture cannot drift from the
    skill's own notion of event identity, then split into tokens because **exact equality
    is too strict for a fixture**. Fixture rows abbreviate — "EMBO Workshop — mycobacterial
    infections" for an event the sweep records as "EMBO Workshop — The complexity of
    mycobacterial infections: from research to real-world impact". Requiring the full
    title would produce false misses and force the fixture to be re-copied verbatim every
    time an organiser rewords a subtitle, which is exactly the rot this file must avoid.
    """
    return set(normalise_series_key({"name": name, "location": ""})[0].split())


def find_match(fixture_name, indexed):
    """Best pool event whose tokens are a superset of the fixture entry's.

    Subset rather than substring: the extra words often sit *inside* the real title
    ("AI4DD — AI for Drug Discovery: Bridging the Translation Gap"), which a substring
    test would miss. Ties break on the smallest event — the tightest match. Fixture rows
    need >=2 tokens so a one-word entry cannot match half the report.
    """
    want = name_tokens(fixture_name)
    if len(want) < 2:
        warn(f"fixture entry too short to match safely: {fixture_name!r}")
        return None
    hits = [(len(toks), ev) for toks, ev in indexed if want <= toks]
    return min(hits, key=lambda h: h[0])[1] if hits else None


def parse_fixture(path):
    """Parse the fixture markdown into {section: [row dicts]}.

    Markdown rather than JSON so the file stays reviewable in a PR and each entry can
    carry its rationale next to it — the reason an entry exists is the most perishable
    part of a fixture.
    """
    out = {"find": [], "exclude": [], "never": []}
    current = None
    for line in open(path, encoding="utf-8"):
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            current = next((v for k, v in SECTIONS.items() if heading.startswith(k)), None)
            continue
        if current is None or not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0].lower() in ("event", "link or title") or set(cells[0]) <= {"-", ":"}:
            continue
        if current in ("find", "exclude"):
            if len(cells) < 4:
                continue
            out[current].append({"name": cells[0], "location": cells[1],
                                 "date": cells[2], "lever": cells[3]})
        else:
            if len(cells) < 3:
                continue
            out[current].append({"needle": cells[0], "sharer": cells[1], "rule": cells[2]})
    return out


def index_events(events):
    """[(token set, event)] for whatever set is being graded."""
    return [(name_tokens(e.get("name", "")), e) for e in events if e.get("name")]


def haystack(events):
    """Lowercased name+url text for substring matching the negatives."""
    return [(e, f"{e.get('name','')} {e.get('url','')}".lower()) for e in events]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Grade a sweep against the recall fixture.")
    ap.add_argument("--fixture", required=True, help="path to references/recall-fixture.md")
    ap.add_argument("--pool", required=True,
                    help="candidate pool JSON (Step 5) — graded for 'must find' and "
                         "'must never'. The POOL, not the report: the report has already "
                         "had the window filter and the seen-ledger applied to it.")
    ap.add_argument("--clean", default=None,
                    help="cleaned JSON (Step 6) — graded for 'must exclude', which tests "
                         "rules that run after the pool is written")
    ap.add_argument("--today", default="", help="reference date for expiry (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    today = parse_date(args.today) or date.today()
    fixture = parse_fixture(args.fixture)
    pool = read_json(args.pool) or []
    if not isinstance(pool, list):
        print("ERROR: --pool must be a JSON array of events", file=sys.stderr)
        return 0  # still non-blocking
    pool_idx, pool_hay = index_events(pool), haystack(pool)

    found, missed, expired, wrong, moved = [], [], [], [], []

    for row in fixture["find"]:
        when = parse_date(row["date"])
        if when is not None and when < today:
            expired.append(row)
            continue
        hit = find_match(row["name"], pool_idx)
        if hit is None:
            missed.append(row)
        else:
            found.append(row)
            got = str(hit.get("location", "")).strip().lower()
            want = row["location"].strip().lower()
            if got and want and got != want:
                moved.append((row, hit.get("location")))

    for row in fixture["never"]:
        needle = row["needle"].strip().lower()
        for event, text in pool_hay:
            if needle and needle in text:
                wrong.append((row, event.get("name")))
                break

    excluded_bad = []
    if args.clean:
        clean_idx = index_events(read_json(args.clean) or [])
        for row in fixture["exclude"]:
            when = parse_date(row["date"])
            if when is not None and when < today:
                expired.append(row)
                continue
            if find_match(row["name"], clean_idx) is not None:
                excluded_bad.append(row)

    total = len(fixture["find"]) - sum(1 for r in expired if r in fixture["find"])
    print(f"recall fixture: {len(found)}/{total} found"
          + (f", {len(missed)} MISSED" if missed else "")
          + (f", {len(wrong)} wrongly included" if wrong else "")
          + (f", {len(excluded_bad)} should have been excluded" if excluded_bad else "")
          + (f", {len(expired)} expired" if expired else ""))

    for row in missed:
        warn(f"MISSED: {row['name']} — should be found by: {row['lever']}")
    for row, got in wrong:
        warn(f"WRONGLY INCLUDED: '{row['needle']}' appeared as '{got}' "
             f"(rule: {row['rule']})")
    for row in excluded_bad:
        warn(f"SHOULD HAVE BEEN EXCLUDED: {row['name']} (rule: {row['lever']})")
    for row, got in moved:
        warn(f"location differs for {row['name']}: fixture '{row['location']}' vs "
             f"found '{got}' — not a miss; update the fixture if the venue really moved")
    for row in expired:
        warn(f"EXPIRED, needs replacing: {row['name']} ({row['date']}) — add the next "
             "edition or another event exercising: " + row.get("lever", "—"))
    if not args.clean and fixture["exclude"]:
        warn(f"--clean not given; skipped {len(fixture['exclude'])} 'must exclude' check(s)")

    # Always 0: informational by design. See the module docstring.
    return 0


if __name__ == "__main__":
    sys.exit(main())
