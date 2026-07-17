#!/usr/bin/env python3
"""Render the cleaned event JSON into the markdown report.

Deterministic: same input always yields the same layout, so the report format is
never re-invented by the model. Groups events by Theme (fixed order), one table per
group, then a Deadlines callout for events whose deadline falls within the window.

Usage:
  python scripts/render_report.py --in clean.json --out report.md \
      [--focus "AI drug discovery"] [--from 2026-07-11] [--to 2027-04-11] [--swept 18]

Prints the output path to stdout.
"""

import argparse
import sys

from _common import continent_of, parse_date, read_json

# Fixed theme order; only non-empty groups render.
THEME_ORDER = ["Science", "Training", "Community", "Philanthropy"]
# Continent order for --group-by continent (mission-first: Africa, then reachable Europe).
# Virtual/online events are NOT a continent — they get their own section at the end.
CONTINENT_ORDER = ["Africa", "Europe", "Asia", "South America", "North America", "Oceania"]


def is_virtual(event):
    """True for an online/virtual event (no physical continent)."""
    if str(event.get("format", "")).strip().lower() == "virtual":
        return True
    return continent_of(event) == "Global / Virtual"
# Human-readable labels for the typed deadlines in the Deadlines callout.
DEADLINE_LABELS = {
    "abstract": "abstract / CFP",
    "early_bird": "early-bird registration",
    "registration": "registration",
    "bursary": "bursary",
}
MARKER_LEGEND = (
    "**Markers:** ⭐ High-priority fit · 🌍 Global-South · 🎓 Training · "
    "💻 Open-source / AI methods · 💰 Bursary / travel support · 🗓️ Deadline in window"
)


def fmt_dates(event):
    start = event.get("start_date", "")
    end = event.get("end_date")
    if end and end != start:
        return f"{start} → {end}"
    return start or "—"


def esc(text):
    """Escape pipe characters so free text can't break a markdown table row."""
    return str(text or "").replace("|", "\\|").strip()


def event_row(event):
    name = esc(event.get("name"))
    url = event.get("url", "")
    link = f"[{name}]({url})" if url else name
    if not event.get("verified", True):
        link = f"{link} †"  # unverified — flagged in the footnote
    if event.get("seen_before"):
        link = f"{link} _(seen)_"  # surfaced in a prior run (from the ledger)
    markers = event.get("markers", "") or "—"
    dates = fmt_dates(event)
    location = esc(event.get("location"))
    fmt_type = f"{esc(event.get('format'))} · {esc(event.get('type'))}"
    cost = esc(event.get("cost")) or "—"
    bursary = esc(event.get("bursary")) or "—"
    priority = esc(event.get("priority"))
    engagement = esc(event.get("engagement")) or "—"
    why = esc(event.get("why_ersilia"))
    return (
        f"| {link} | {markers} | {dates} | {location} | {fmt_type} | "
        f"{cost} | {bursary} | {priority} | {engagement} | {why} |"
    )


# Deadlines this many days out (or nearer) count as "imminent" in the Act-now block.
IMMINENT_DAYS = 30


def countdown(deadline_date, today):
    """Human phrase for how far off a deadline is (e.g. 'in 9 days'). None if past."""
    days = (deadline_date - today).days
    if days < 0:
        return None
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def build_act_now(events, today):
    """The exec-summary block: imminent deadlines (with countdown) + top ⭐ picks."""
    lines = ["## ⏱️ Act now", ""]

    # Imminent deadlines — every in-window deadline within IMMINENT_DAYS of `today`.
    imminent = []
    for event in events:
        name = esc(event.get("name"))
        url = event.get("url", "")
        link = f"[{name}]({url})" if url else name
        for d in event.get("deadlines_in_window", []):
            parsed = parse_date(d["date"])
            if today is None or parsed is None:
                continue
            phrase = countdown(parsed, today)
            if phrase is None or (parsed - today).days > IMMINENT_DAYS:
                continue
            label = DEADLINE_LABELS.get(d["type"], d["type"])
            imminent.append((d["date"], f"- **{phrase}** ({d['date']}) — {link} · {label}"))
    if imminent:
        imminent.sort(key=lambda row: row[0])
        lines.append(f"**Deadlines in the next {IMMINENT_DAYS} days**")
        lines.extend(row for _, row in imminent)
        lines.append("")
    else:
        lines.append(f"_No deadlines in the next {IMMINENT_DAYS} days._")
        lines.append("")

    # Top picks — ⭐ high-priority events, soonest first, capped at 5.
    picks = [e for e in events if str(e.get("priority", "")).lower() == "high"]
    picks.sort(key=lambda e: str(e.get("start_date") or "9999"))
    if picks:
        lines.append("**Top picks**")
        for event in picks[:5]:
            name = esc(event.get("name"))
            url = event.get("url", "")
            link = f"[{name}]({url})" if url else name
            action = esc(event.get("action"))
            action_bit = f" · {action}" if action else ""
            lines.append(f"- ⭐ {link} — {fmt_dates(event)}, {esc(event.get('location'))}{action_bit}")
        if len(picks) > 5:
            lines.append(f"- …and {len(picks) - 5} more high-priority events below.")
        lines.append("")

    return lines


def render_theme_tables(lines, events, table_header, heading="##"):
    """Append one table per theme (fixed order, non-empty only) at the given heading level."""
    grouped = {theme: [] for theme in THEME_ORDER}
    other = []
    for event in events:
        theme = event.get("theme")
        (grouped[theme] if theme in grouped else other).append(event)
    for theme in THEME_ORDER + ["Other"]:
        bucket = other if theme == "Other" else grouped[theme]
        if not bucket:
            continue
        lines.append(f"{heading} {theme}")
        lines.append(table_header)
        for event in bucket:
            lines.append(event_row(event))
        lines.append("")


def registration_closed(event, today):
    """True for a still-upcoming event whose final registration deadline has passed."""
    if today is None:
        return False
    start = parse_date(event.get("start_date"))
    if start is None or start < today:
        return False  # only flag events that haven't happened yet
    reg = parse_date((event.get("deadlines") or {}).get("registration"))
    return reg is not None and reg < today


def render(events, focus, date_from, date_to, swept, today=None, group_by="theme",
           continents_searched=None):
    lines = []
    title_focus = focus.strip() if focus and focus.strip() else "broad sweep"
    lines.append(f"# Event Discovery for Ersilia — {title_focus}")
    lines.append("")

    header_bits = [f"Generated: {today or date_from or '—'}"]
    if date_from and date_to:
        header_bits.append(f"Window: {date_from} → {date_to}")
    header_bits.append(f"Events: {len(events)}")
    if swept is not None:
        header_bits.append(f"Sources swept: {swept}")
    lines.append(f"*{' | '.join(header_bits)}*")
    lines.append("")
    lines.append(MARKER_LEGEND)
    lines.append("")

    if not events:
        lines.append("_No events matched the focus and window. Reported honestly rather "
                     "than padded — widen the window or focus to see more._")
        lines.append("")
        return "\n".join(lines)

    today_date = parse_date(today) if today else parse_date(date_from)
    closed = {id(e): registration_closed(e, today_date) for e in events}
    actionable = [e for e in events if not closed[id(e)]]

    lines.extend(build_act_now(actionable, today_date))

    table_header = (
        "| Event | Markers | Dates | Location | Format · Type | Cost | Bursary | Priority | "
        "Engagement | Why it matters (priority · action) |\n"
        "|---|---|---|---|---|---|---|---|---|---|"
    )

    # Events whose date is beyond the window (kept only for an in-window deadline) and
    # events whose registration has closed each render in their own section, not mixed
    # into the grouped tables.
    in_window_events = [e for e in events if not e.get("beyond_window") and not closed[id(e)]]
    beyond_events = [e for e in events if e.get("beyond_window") and not closed[id(e)]]
    closed_events = [e for e in events if closed[id(e)]]

    # Virtual/online events are pulled out into their own section at the end (not a place).
    virtual_events = [e for e in in_window_events if is_virtual(e)]
    located_events = [e for e in in_window_events if not is_virtual(e)]

    if group_by == "continent":
        # Two-level: continent (##) → theme (###) within each continent.
        cont_buckets = {c: [] for c in CONTINENT_ORDER}
        cont_other = []
        for event in located_events:
            c = continent_of(event)
            (cont_buckets[c] if c in cont_buckets else cont_other).append(event)
        for cont in CONTINENT_ORDER:
            if not cont_buckets[cont]:
                continue
            lines.append(f"## {cont}")
            lines.append("")
            render_theme_tables(lines, cont_buckets[cont], table_header, heading="###")
        if cont_other:
            lines.append("## Other")
            lines.append("")
            render_theme_tables(lines, cont_other, table_header, heading="###")
    else:
        # Single level: theme.
        render_theme_tables(lines, located_events, table_header, heading="##")

    # Beyond-window events, soonest in-window deadline first.
    if beyond_events:
        beyond_events.sort(key=lambda e: (e.get("deadlines_in_window") or [{"date": "9999-99-99"}])[0]["date"])
        lines.append("## Beyond the window — event is later, but a deadline is open now")
        lines.append(table_header)
        for event in beyond_events:
            lines.append(event_row(event))
        lines.append("")

    # Registration-closed events: still upcoming, but the door has shut.
    if closed_events:
        closed_events.sort(key=lambda e: str(e.get("start_date") or "9999"))
        lines.append("## Registration closed — event still upcoming, but you can no longer register")
        lines.append(table_header)
        for event in closed_events:
            lines.append(event_row(event))
        lines.append("")

    # Virtual / online events — no physical location, so a single section at the end.
    if virtual_events:
        virtual_events.sort(key=lambda e: str(e.get("start_date") or "9999"))
        lines.append("## Virtual / online")
        lines.append(table_header)
        for event in virtual_events:
            lines.append(event_row(event))
        lines.append("")

    # Deadlines callout — every typed deadline inside the window, soonest first.
    # (Closed-registration events are excluded; their deadlines are no longer actionable.)
    deadline_rows = []
    for event in actionable:
        name = esc(event.get("name"))
        url = event.get("url", "")
        link = f"[{name}]({url})" if url else name
        for d in event.get("deadlines_in_window", []):
            label = DEADLINE_LABELS.get(d["type"], d["type"])
            deadline_rows.append((d["date"], f"- **{d['date']}** — {link} · {label}"))
    if deadline_rows:
        deadline_rows.sort(key=lambda row: row[0])
        lines.append("## Deadlines (within the window)")
        lines.extend(row for _, row in deadline_rows)
        lines.append("")

    # Coverage-by-continent footer — makes it explicit which continents were searched,
    # so an empty continent reads as "searched, none verified" rather than "forgotten".
    if continents_searched is not None:
        counts = {}
        for event in events:
            c = continent_of(event)
            counts[c] = counts.get(c, 0) + 1
        searched = {s.strip() for s in continents_searched.split(",") if s.strip()}
        lines.append("## Coverage by continent")
        for c in CONTINENT_ORDER:
            n = counts.get(c, 0)
            if n:
                note = f"{n} event{'s' if n != 1 else ''}"
            elif c in searched:
                note = "0 — searched, none verified"
            else:
                note = "0 — not searched"
            lines.append(f"- **{c}**: {note}")
        lines.append("")

    # Footnote for any events that could not be verified on their official page.
    if any(not e.get("verified", True) for e in events):
        lines.append("---")
        lines.append("† Not confirmed on the official page (details from secondary "
                     "sources) — verify before acting.")
        lines.append("")

    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the event report markdown.")
    parser.add_argument("--in", dest="infile", required=True, help="cleaned event JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="output markdown path")
    parser.add_argument("--focus", default="", help="focus string for the title")
    parser.add_argument("--from", dest="date_from", default="", help="window start YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", default="", help="window end YYYY-MM-DD")
    parser.add_argument("--swept", type=int, default=None, help="number of sources swept")
    parser.add_argument("--today", default="", help="reference date for the Act-now countdown "
                        "(YYYY-MM-DD); defaults to --from")
    parser.add_argument("--group-by", dest="group_by", choices=["theme", "continent"],
                        default="theme", help="section the report by theme (default) or by continent")
    parser.add_argument("--continents-searched", dest="continents_searched", default=None,
                        help="comma-separated continents you actually queried; adds a "
                             "'Coverage by continent' footer so empty continents read as "
                             "searched-but-empty, not forgotten")
    args = parser.parse_args(argv)

    events = read_json(args.infile)
    if not isinstance(events, list):
        print("ERROR: input JSON must be an array of event objects", file=sys.stderr)
        sys.exit(1)

    # Guard: a caller passing a still-dirty pool would produce a misleading report.
    for event in events:
        if parse_date(event.get("start_date")) is None:
            print(f"ERROR: event {event.get('name')!r} has no valid start_date; "
                  "run filter_and_sort.py first", file=sys.stderr)
            sys.exit(1)

    markdown = render(events, args.focus, args.date_from, args.date_to, args.swept,
                      today=args.today or args.date_from, group_by=args.group_by,
                      continents_searched=args.continents_searched)
    with open(args.outfile, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    print(args.outfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
