#!/usr/bin/env python3
"""Render the cleaned partner pool as a campaign amplification plan.

Campaign mode answers a different question from `sweep`: not "who should Ersilia know"
but "we have a thing happening on a date — who helps it land, and who must we contact
first". The report is therefore led by a **contact schedule** ordered by `contact_by`,
with the per-partner detail grouped by class underneath.

Feed it output from `filter_and_sort.py --order deadline`, which sorts by `contact_by`
and sets the ⏱️ marker.

Like the other renderers this emits **no markdown pipe tables** — the Drive Doc
conversion mangles them (see render_sweep.py's docstring). It also reuses that file's
`--markers text` mode for the same reason: emoji above U+1FFFF corrupt in the same
conversion, while ⏱️ (U+23F1) and ⭐ (U+2B50) survive.

Usage:
  python scripts/render_campaign.py --in clean.json --out reports/26-08-21-campaign-anniversary.md \
      --date 2026-08-21 --occasion "Ersilia 5th anniversary" --occasion-date 2026-11-15

Exit code 0 on success; 1 on an unreadable input file.
"""

import argparse
import sys
from collections import defaultdict

from _common import CLASS_VALUES, REACHLESS_CLASSES, parse_date, read_json
from render_sweep import (
    CLASS_HEADINGS,
    contact_label,
    esc,
    link,
    render_markers,
    title_of,
)

# Buckets for the contact schedule, as (label, inclusive upper bound in days from today).
# `None` upper bound is the catch-all for anything further out.
BUCKETS = (
    ("Overdue — contact-by has passed", -1),
    ("This week — contact within 7 days", 7),
    ("This month — contact within 30 days", 30),
    ("Later", None),
)

CAMPAIGN_LEGEND = (
    "⏱️ Contact within 14 days · ⭐ High fit · 🏠 Barcelona / Catalonia · 🌍 Global-South · "
    "💻 Open-source · 📣 Broad reach · 🤝 Warm path · ✉️ Contact channel on file"
)
CAMPAIGN_LEGEND_TEXT = (
    "[Urgent] Contact within 14 days · [High] High fit · [Local] Barcelona / Catalonia · "
    "[Global-South] Global-South · [OSS] Open-source · [Broad reach] Broad reach · "
    "[Warm] Warm path · [Contact] Contact channel on file"
)

CLASS_HEADINGS_CAMPAIGN = dict(CLASS_HEADINGS)
CLASS_HEADINGS_CAMPAIGN.update({
    "Comms-team": "Institutional communications teams",
    "Community": "Community and network amplifiers",
    "Creative": "Creatives to commission",
})


def days_until(value, today):
    """Whole days from ``today`` to the ISO date ``value``; None if unparseable."""
    parsed = parse_date(value)
    if parsed is None or today is None:
        return None
    return (parsed - today).days


def human_delta(days):
    """'in 11 days' / 'today' / '3 days ago', for a signed day count."""
    if days is None:
        return "no date set"
    if days == 0:
        return "today"
    if days > 0:
        return f"in {days} day{'s' if days != 1 else ''}"
    return f"{-days} day{'s' if days != -1 else ''} ago"


def bucket_of(days):
    """Which schedule bucket a day-count belongs to. No date -> the trailing bucket."""
    if days is None:
        return "No contact-by date set"
    for label, bound in BUCKETS:
        if bound is None:
            return label
        if label.startswith("Overdue"):
            if days < 0:
                return label
            continue
        if days <= bound:
            return label
    return BUCKETS[-1][0]


def render_partner(partner, today, marker_mode):
    """Per-partner detail block. Mirrors render_sweep but leads with the deadline."""
    out = [f"### {title_of(partner, marker_mode)}", ""]

    days = days_until(partner.get("contact_by"), today)
    if partner.get("contact_by"):
        out.append(f"- **Contact by:** {partner['contact_by']} ({human_delta(days)})")
    else:
        out.append("- **Contact by:** — not set. Without it this row cannot be scheduled.")
    if partner.get("lead_time_note"):
        out.append(f"- **Why that date:** {esc(partner['lead_time_note'])}")
    if partner.get("amplification"):
        out.append(f"- **What we're hoping for:** {esc(partner['amplification'])}")

    out.append(f"- **Why them:** {esc(partner.get('hook'))}")
    out.append(f"- **Next step:** {esc(partner.get('next_step'))}")

    # `reach` is omitted for classes where it is not a meaningful axis — printing
    # "reach Niche" for a photographer states something the sweep never assessed.
    axes = [esc(partner.get("class")), esc(partner.get("scope"))]
    if partner.get("class") not in REACHLESS_CLASSES and partner.get("reach"):
        axes.append(f"reach {partner['reach']}")
    axes.append(f"warmth {esc(partner.get('warmth'))}")
    axes.append(f"priority {esc(partner.get('priority'))}")
    axes.append(f"action **{esc(partner.get('action'))}**")
    out.append(f"- **Axes:** {' · '.join(axes)}")

    if partner.get("class") == "Creative":
        if partner.get("portfolio_url"):
            out.append(f"- **Portfolio:** {link('portfolio', partner['portfolio_url'])}")
        if partner.get("does_events") is not None:
            out.append(f"- **Covers events:** {'yes' if partner['does_events'] else 'no / unknown'}")
        if partner.get("rate_note"):
            out.append(f"- **Rate:** {esc(partner['rate_note'])}")

    recent = partner.get("recent_work") or []
    if recent:
        items = []
        for item in recent:
            if isinstance(item, dict):
                label = item.get("title") or item.get("url")
                dated = f" ({item['date']})" if item.get("date") else ""
                # The note carries the caveat — "no recent piece could be confirmed", "this
                # page only shows the previous edition". Dropping it, as these renderers
                # first did, silently turns a hedged citation into a confident one.
                note = f" — {item['note']}" if item.get("note") else ""
                items.append(f"{link(label, item.get('url'))}{dated}{note}")
            else:
                items.append(esc(item))
        out.append(f"- **Recent relevant work:** {' · '.join(items)}")

    paths = partner.get("warm_paths") or []
    if paths:
        out.append(f"- **Warm paths:** {'; '.join(esc(p) for p in paths)}")

    contacts = partner.get("contacts") or []
    if contacts:
        rendered = []
        for contact in contacts:
            note = " (scientific correspondence — not a pitch channel)" if contact.get("restricted") else ""
            rendered.append(f"{contact_label(contact.get('kind'))}: {contact.get('value')}{note}")
        out.append(f"- **Contact:** {'; '.join(rendered)}")

    links = [link("profile", partner.get("url"))]
    if partner.get("org_url"):
        links.append(link("organisation", partner["org_url"]))
    out.append(f"- **Links:** {' · '.join(links)}")
    out.append(f"- **Source:** {esc(partner.get('source'))}")
    if not partner.get("verified", True):
        out.append("- **† Unverified** — no live page confirmed this; verify or drop before acting")
    out.append("")
    return out


def render(partners, run_date, occasion, occasion_date, marker_mode="emoji"):
    today = parse_date(run_date)
    occasion_days = days_until(occasion_date, today)

    out = [f"# Ersilia Campaign Partners — {occasion or 'unnamed occasion'}", ""]
    header = f"**Occasion:** {occasion or '—'}"
    if occasion_date:
        header += f" · {occasion_date} ({human_delta(occasion_days)})"
    out.append(header)
    out.append(f"**Prepared:** {run_date} · {len(partners)} partner(s) to contact")
    legend = CAMPAIGN_LEGEND_TEXT if marker_mode == "text" else CAMPAIGN_LEGEND
    out.append(f"**Markers:** {legend}")
    out.append("")

    if occasion_days is not None and occasion_days < 0:
        out.append("> **The occasion date has passed.** This plan is retrospective; check "
                   "the date before acting on it.")
        out.append("")

    # --- The contact schedule: the point of campaign mode. -----------------------
    out.append("## Contact schedule")
    out.append("")
    if not partners:
        out.append("- Nothing to schedule — no partner survived screening.")
        out.append("")
    else:
        grouped = defaultdict(list)
        for partner in partners:
            grouped[bucket_of(days_until(partner.get("contact_by"), today))].append(partner)
        bucket_names = [label for label, _ in BUCKETS] + ["No contact-by date set"]
        for label in bucket_names:
            rows = grouped.get(label)
            if not rows:
                continue
            out.append(f"**{label}**")
            out.append("")
            for partner in rows:
                markers = render_markers(partner.get("markers"), marker_mode)
                name = str(partner.get("person") or partner.get("org")
                           or partner.get("name") or "").strip()
                days = days_until(partner.get("contact_by"), today)
                when = f"{partner['contact_by']} ({human_delta(days)})" if partner.get("contact_by") else "no date"
                prefix = f"{markers} " if markers else ""
                out.append(f"- {prefix}**{name}** · {esc(partner.get('class'))} · "
                           f"{when} — {esc(partner.get('next_step'))}")
            out.append("")

    # --- Detail, grouped by class. ----------------------------------------------
    by_class = defaultdict(list)
    for partner in partners:
        by_class[partner.get("class") or "Other"].append(partner)
    class_order = [c for c in CLASS_VALUES if by_class.get(c)]
    class_order += [c for c in sorted(by_class) if c not in CLASS_VALUES]

    for class_name in class_order:
        out.append(f"## {CLASS_HEADINGS_CAMPAIGN.get(class_name, class_name)}")
        out.append("")
        for partner in by_class[class_name]:
            out.extend(render_partner(partner, today, marker_mode))

    unverified = [p for p in partners if not p.get("verified", True)]
    if unverified:
        out.append("## † Unverified — resolve before acting")
        out.append("")
        for partner in unverified:
            out.append(f"- {esc(partner.get('name'))} — {esc(partner.get('source'))}")
        out.append("")

    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a campaign amplification plan.")
    parser.add_argument("--in", dest="infile", required=True, help="cleaned partner JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="output markdown path")
    parser.add_argument("--date", dest="run_date", required=True, help="run date YYYY-MM-DD")
    parser.add_argument("--occasion", default="", help="what is being amplified")
    parser.add_argument("--occasion-date", dest="occasion_date", default="",
                        help="the occasion's date YYYY-MM-DD")
    parser.add_argument("--markers", choices=("emoji", "text"), default="emoji",
                        help="emoji ribbon (default) or bracketed text labels for a Drive Doc")
    args = parser.parse_args(argv)

    partners = read_json(args.infile)
    if not isinstance(partners, list):
        print("ERROR: input JSON must be an array of partner objects", file=sys.stderr)
        sys.exit(1)

    if not args.occasion:
        print("WARNING: no --occasion given; the report will not say what it is for",
              file=sys.stderr)
    missing_dates = sum(1 for p in partners if not p.get("contact_by"))
    if missing_dates:
        print(f"WARNING: {missing_dates} partner(s) have no contact_by date and cannot be "
              "scheduled — they render in a trailing bucket", file=sys.stderr)

    lines = render(partners, args.run_date, args.occasion, args.occasion_date, args.markers)
    with open(args.outfile, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")

    print(f"rendered campaign plan for {len(partners)} partner(s) -> {args.outfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
