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

from _common import continent_of, focus_continent_of, parse_date, read_json

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
    "💻 Open-source / AI methods · 💰 Bursary / travel support · 🗓️ Deadline in window · "
    "💬 Shared by the team"
)

# Connector labels for the `**Connectors:**` header line, in fixed display order.
# Status comes from --connectors "web:ok,slack:down"; anything not "ok" renders 🔴.
CONNECTOR_LABELS = {"web": "Web hunt", "slack": "Slack"}
CONNECTOR_ORDER = ("web", "slack")


def render_connectors(spec):
    """Build the `**Connectors:**` line from a "web:ok,slack:down" spec.

    Returns None when no spec was passed, so the line is omitted entirely rather
    than rendering a misleading all-green row for connectors nobody reported on.
    """
    if not spec:
        return None
    statuses = {}
    for chunk in str(spec).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, state = chunk.partition(":")
        statuses[name.strip().lower()] = state.strip().lower()
    if not statuses:
        return None
    bits = []
    for key in CONNECTOR_ORDER:
        if key in statuses:
            label = CONNECTOR_LABELS.get(key, key)
            bits.append(f"{label} {'🟢' if statuses[key] == 'ok' else '🔴'}")
    # Anything unrecognised still renders, so a new connector isn't silently dropped.
    for key, state in statuses.items():
        if key not in CONNECTOR_ORDER:
            bits.append(f"{key} {'🟢' if state == 'ok' else '🔴'}")
    return "**Connectors:** " + " · ".join(bits) if bits else None


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
    # When an event is *about* a different region than the one it is *held* in, show
    # both: "London, United Kingdom → Africa". The arrow is the cue that focus and
    # location diverge. Deliberately not an emoji marker — the ribbon is already seven
    # glyphs deep, and this belongs next to the place it qualifies.
    focus_continent = focus_continent_of(event)
    if focus_continent and focus_continent != continent_of(event):
        location = f"{location} → {esc(event.get('focus_region')) or focus_continent}"
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
        lines.append("")
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
           continents_searched=None, connectors=None):
    lines = []
    # Title mirrors the sibling digests' `# Ersilia X Digest — <date>` form. The focus
    # moves into the Scope line: it is a run parameter, not part of the digest's identity.
    lines.append(f"# Ersilia Event Digest — {today or date_from or '—'}")
    lines.append("")

    # Scope / Connectors / Markers, each a bold line with `·` separators.
    #
    # NEVER build this from pipe-delimited text. The previous
    # `*Generated: … | Window: … | Events: …*` single line was parsed by kramdown as a
    # one-row TABLE on the published page, and the italic asterisks leaked through as
    # literal `*Generated:` / `37*`. Pipes in a lone line are a table waiting to happen.
    #
    # The event count is a DELTA, not a standing total: Step 6 drops already-seen
    # events, so `len(events)` is what is new since the last digest. No "tracked in
    # window" figure is carried — it would mean computing a pre-suppression count here
    # and threading it through the Slack template as a second number to keep consistent.
    n = len(events)
    scope_bits = [f"{n} new event{'s' if n != 1 else ''}"]
    if date_from and date_to:
        scope_bits.append(f"window {date_from} → {date_to}")
    if swept is not None:
        scope_bits.append(f"{swept} source{'s' if swept != 1 else ''} swept")
    if focus and focus.strip():
        scope_bits.append(f"focus: {focus.strip()}")
    # These lines form ONE markdown paragraph, so every line but the last needs a
    # two-space hard break or they render as a single run-on line. This is the idiom
    # `literature-digest` uses; `github-digest` omits it and its Connectors and Markers
    # lines are visibly joined on the published page. Trailing whitespace here is
    # load-bearing — do not let an editor or linter strip it.
    header_lines = ["**Scope:** " + " · ".join(scope_bits)]
    connector_line = render_connectors(connectors)
    if connector_line:
        header_lines.append(connector_line)
    header_lines.append(MARKER_LEGEND)
    lines.extend(line + "  " for line in header_lines[:-1])
    lines.append(header_lines[-1])
    lines.append("")

    if not events:
        # Under the monthly cadence this is a normal outcome, not a failure: everything
        # in the window was already reported in an earlier digest. Say so, so an empty
        # report is not mistaken for a broken sweep. Whether to publish it at all is the
        # user's call at Step 7a.
        lines.append("_No new events this cycle — everything found in the window was "
                     "already covered by an earlier digest. Reported honestly rather than "
                     "padded._")
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
    undated_events = [e for e in events if e.get("undated")]
    dated = [e for e in events if not e.get("undated")]
    in_window_events = [e for e in dated if not e.get("beyond_window") and not closed[id(e)]]
    beyond_events = [e for e in dated if e.get("beyond_window") and not closed[id(e)]]
    closed_events = [e for e in dated if closed[id(e)]]

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
        lines.append("")
        lines.append(table_header)
        for event in beyond_events:
            lines.append(event_row(event))
        lines.append("")

    # Registration-closed events: still upcoming, but the door has shut.
    if closed_events:
        closed_events.sort(key=lambda e: str(e.get("start_date") or "9999"))
        lines.append("## Registration closed — event still upcoming, but you can no longer register")
        lines.append("")
        lines.append(table_header)
        for event in closed_events:
            lines.append(event_row(event))
        lines.append("")

    # Team-shared events whose official page has not announced dates yet. They cannot be
    # date-sorted or window-filtered, so they get their own section rather than being
    # dropped (SKILL.md Step 2a) or given an invented date.
    if undated_events:
        undated_events.sort(key=lambda e: str(e.get("name", "")).lower())
        lines.append("## Shared by the team — dates not yet announced")
        lines.append("")
        lines.append("_Posted in `#networking` and kept on a colleague's recommendation; the "
                     "official page has no dates yet, so these are unverified by "
                     "construction. Watch rather than plan around._")
        lines.append("")
        lines.append(table_header)
        for event in undated_events:
            lines.append(event_row(event))
        lines.append("")

    # Virtual / online events — no physical location, so a single section at the end.
    if virtual_events:
        virtual_events.sort(key=lambda e: str(e.get("start_date") or "9999"))
        lines.append("## Virtual / online")
        lines.append("")
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

    # Coverage footer — makes it explicit which regions were searched, so an empty
    # region reads as "searched, nothing in report" rather than "forgotten".
    #
    # These counts are by REGION FOCUS, not by physical location, so they intentionally
    # will NOT match the continent section counts above: an Africa-focused event held in
    # Berlin sits in the Europe section but counts toward Africa here. The heading and
    # the note below exist so that divergence reads as designed rather than as a bug.
    if continents_searched is not None:
        counts = {}
        for event in events:
            c = focus_continent_of(event)
            counts[c] = counts.get(c, 0) + 1
        searched = {s.strip() for s in continents_searched.split(",") if s.strip()}
        lines.append("## Coverage by region focus")
        lines.append("")
        lines.append("_Counted by what each event is **about**, not where it is held — so "
                     "these totals can differ from the continent sections above._")
        lines.append("")
        for c in CONTINENT_ORDER:
            n = counts.get(c, 0)
            if n:
                note = f"{n} event{'s' if n != 1 else ''}"
            elif c in searched:
                note = "0 — searched, none in report"
            else:
                note = "0 — not searched"
            lines.append(f"- **{c}**: {note}")
        lines.append("")

    # Footer notes. Both are content-gated, so a clean report ends without a rule.
    #
    # Attribution lives here rather than in the table: the row is already ten columns
    # wide, and crediting a colleague is a footnote-shaped fact, not a sortable field.
    footer = []
    if any(not e.get("verified", True) for e in events):
        footer.append("† Not confirmed on the official page — details come from secondary "
                      "sources, or, for a team-shared event, could not be verified at all. "
                      "Verify before acting.")
    shared = [e for e in events if e.get("shared_by")]
    if shared:
        if footer:
            footer.append("")
        footer.append("💬 Shared by the team rather than found by the automated sweep:")
        for event in sorted(shared, key=lambda e: str(e.get("start_date") or "9999")):
            footer.append(f"- {esc(event.get('name'))} — @{esc(event.get('shared_by'))}")
    if footer:
        lines.append("---")
        lines.extend(footer)
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
                        default="continent", help="section the report by continent (default) or by theme")
    parser.add_argument("--continents-searched", dest="continents_searched", default=None,
                        help="comma-separated continents you actually queried; adds a "
                             "'Coverage by region focus' footer so empty regions read as "
                             "searched-but-empty, not forgotten")
    parser.add_argument("--connectors", default=None,
                        help='connector status for the header line, e.g. "web:ok,slack:down". '
                             "Omit to leave the Connectors line out entirely rather than "
                             "implying every connector was healthy.")
    args = parser.parse_args(argv)

    events = read_json(args.infile)
    if not isinstance(events, list):
        print("ERROR: input JSON must be an array of event objects", file=sys.stderr)
        sys.exit(1)

    # Guard: a caller passing a still-dirty pool would produce a misleading report.
    # Events flagged `undated` are the one legitimate exception — team-shared entries
    # whose official page has published no dates yet (SKILL.md Step 2a). filter_and_sort
    # sets that flag deliberately, so it means "checked and genuinely dateless", not
    # "unprocessed".
    for event in events:
        if event.get("undated"):
            continue
        if parse_date(event.get("start_date")) is None:
            print(f"ERROR: event {event.get('name')!r} has no valid start_date; "
                  "run filter_and_sort.py first", file=sys.stderr)
            sys.exit(1)

    markdown = render(events, args.focus, args.date_from, args.date_to, args.swept,
                      today=args.today or args.date_from, group_by=args.group_by,
                      continents_searched=args.continents_searched,
                      connectors=args.connectors)
    with open(args.outfile, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    print(args.outfile)
    return 0


if __name__ == "__main__":
    sys.exit(main())
