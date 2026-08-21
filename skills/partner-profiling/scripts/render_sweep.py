#!/usr/bin/env python3
"""Render the cleaned partner pool as the sweep report.

Deliberately emits **no markdown pipe tables**. The Google Drive connector converts
markdown to a Doc with headings and bullets intact, but mangles pipe tables — the
header row comes back empty and its cells are demoted into a body row with escaped
literal asterisks. Verified 2026-08-20. Every partner is therefore a subheading with
labelled bullet lines, which survives conversion and is what you want in a Doc the team
comments on anyway.

Usage:
  python scripts/render_sweep.py --in clean.json --out reports/26-08-20-partner-sweep.md \
      --date 2026-08-20 --focus "science journalists, AMR" --sources 14

Exit code 0 on success; 1 on an unreadable input file.
"""

import argparse
import sys
from collections import Counter, defaultdict

from _common import CLASS_VALUES, PRIORITY_VALUES, read_json

MARKER_LEGEND = (
    "⭐ High fit · 🏠 Barcelona / Catalonia · 🌍 Global-South · 💻 Open-source · "
    "📣 Broad reach · 🤝 Warm path · ✉️ Contact channel on file"
)

# --- Marker rendering modes -----------------------------------------------------
# The emoji ribbon is the default and is what the local markdown report uses.
#
# `--markers text` exists for one specific reason: the Google Drive markdown-to-Doc
# conversion **corrupts emoji outside the Basic Multilingual Plane**. Verified
# 2026-08-20 by round-tripping this exact report — 🏠🌍💻📣🤝 (all U+1F300 and above)
# came back as mojibake (`ð `, `ð`, `ð»`, `ð£`, `ð¤`), while ⭐ (U+2B50) and
# ✉️ (U+2709) survived because they are BMP characters. Rather than degrade the ribbon
# to the handful of semantically-poor BMP symbols, the Drive rendition drops emoji for
# short bracketed labels. Keep this flag in mind if the "Future work" Drive step is built.
MARKER_TEXT = {
    # ⏱️ is campaign-mode only, but it lives here because render_campaign imports this map.
    "⏱️": "Urgent",
    "⭐": "High",
    "🏠": "Local",
    "🌍": "Global-South",
    "💻": "OSS",
    "📣": "Broad reach",
    "🤝": "Warm",
    "✉️": "Contact",
}
MARKER_LEGEND_TEXT = (
    "[High] High fit · [Local] Barcelona / Catalonia · [Global-South] Global-South · "
    "[OSS] Open-source · [Broad reach] Broad reach · [Warm] Warm path · "
    "[Contact] Contact channel on file"
)

# Human labels for contact kinds. The raw keys contain underscores, which the Drive
# conversion escapes into a visible backslash (`outlet\_pitch`) — and which read as
# code in a document meant for people.
CONTACT_LABELS = {
    "outlet_pitch": "outlet pitch desk",
    "press_office": "press office",
    "institutional": "institutional address",
    "public_form": "contact form",
    "scientific_correspondence": "corresponding author",
}


def render_markers(markers, mode):
    """Render the ribbon either as emoji (default) or as bracketed text labels."""
    text = str(markers or "").strip()
    if mode != "text" or not text:
        return text
    labels = [f"[{MARKER_TEXT[m]}]" for m in MARKER_TEXT if m in text]
    return " ".join(labels)


def contact_label(kind):
    """A human-readable label for a contact kind."""
    return CONTACT_LABELS.get(str(kind or ""), str(kind or "").replace("_", " "))

# Sections are emitted in this order; anything with an unexpected class is appended
# under "Other" rather than dropped.
CLASS_HEADINGS = {
    "Media": "Media and science communication",
    "Open-source": "Open-source and open-science organisations",
    "Institution": "Institutions — Barcelona, Catalonia and Spain",
}


# --- Table layout ---------------------------------------------------------------
# `--layout table` is the default for the local markdown report: one row per partner,
# scannable at a glance. `--layout detail` keeps the heading-per-partner prose form and
# is what a Google Drive Doc needs, because that conversion mangles pipe tables — see
# the module docstring. Keep both working; they serve different destinations.

# How much of a prose field survives in a table cell. Trimmed cells end in "…" so a
# reader can always tell something was cut rather than silently reading a half-sentence
# as the whole instruction.
CELL_LIMIT = 96


def cell(value):
    """Make a value safe for a markdown table cell.

    Escapes pipes — an unescaped `|` in a hook or a URL silently splits the row into the
    wrong number of columns and corrupts every cell after it — and collapses newlines,
    which would end the table early.
    """
    text = str(value or "").strip()
    if not text:
        return "—"
    text = " ".join(text.split())
    return text.replace("|", "\\|")


def trim(value, limit=CELL_LIMIT):
    """Shorten a prose field for a table cell, preferring a sentence boundary.

    Returns the whole string when it already fits. Otherwise cuts at the last sentence
    end inside the limit, falling back to the last word boundary, and marks the cut with
    an ellipsis. Never cuts mid-word.
    """
    text = cell(value)
    if text == "—" or len(text) <= limit:
        return text
    window = text[:limit]
    for stop in (". ", "; ", " — "):
        idx = window.rfind(stop)
        if idx > limit // 2:
            return window[:idx + 1].rstrip()
    idx = window.rfind(" ")
    return (window[:idx] if idx > 0 else window).rstrip() + " …"


# Context fields (hook, amplification) are trimmed; `next_step` never is. It is the
# field the whole skill exists to produce, and a truncated instruction is worse than a
# long cell — a trimmed conditional ("only if X, otherwise drop") reads as an
# unconditional one.
TRIM_NOTE = ("*Cells ending in “…” are trimmed for context only — next steps are never "
             "trimmed. Full text is in the partner JSON, or re-render with `--layout detail`.*")


def render_table(partners, marker_mode):
    """One master table for the whole report, one row per partner."""
    out = [
        "| Partner | Class · Scope | Markers | Pri | Action | Why them | Next step |",
        "|---|---|---|---|---|---|---|",
    ]
    for partner in partners:
        name = partner.get("person") or partner.get("org") or partner.get("name")
        dagger = "" if partner.get("verified", True) else " †"
        url = partner.get("url")
        label = f"[{cell(name)}]({url})" if url else cell(name)
        scope = f"{cell(partner.get('class'))} · {cell(partner.get('scope'))}"
        out.append(
            f"| {label}{dagger} | {scope} | {render_markers(partner.get('markers'), marker_mode) or '—'} "
            f"| {cell(partner.get('priority'))} | **{cell(partner.get('action'))}** "
            f"| {trim(partner.get('hook'))} | {cell(partner.get('next_step'))} |"
        )
    out.append("")
    out.append(TRIM_NOTE)
    out.append("")
    return out

def esc(value):
    """Return a display string, collapsing None to an em dash."""
    text = str(value or "").strip()
    return text if text else "—"


def link(label, url):
    """A markdown link, or just the label when there is no URL."""
    if url:
        return f"[{esc(label)}]({url})"
    return esc(label)


def title_of(partner, marker_mode="emoji"):
    """The subheading for one partner: markers, person, role and organisation.

    A partner may be an organisation with no named individual (an outlet's tips desk,
    an open-source foundation), so the person is optional and the organisation carries
    the line on its own in that case.
    """
    markers = render_markers(partner.get("markers"), marker_mode)
    dagger = "" if partner.get("verified", True) else " †"
    person = str(partner.get("person") or "").strip()
    role = str(partner.get("role") or "").strip()
    org = str(partner.get("org") or "").strip()
    name = str(partner.get("name") or "").strip()

    if person:
        head = person
        # Comma, not another em dash: "Name — Role — Org" reads as three peers, while
        # "Name — Role, Org" reads as a person and their affiliation.
        tail = ", ".join(t for t in (role, org) if t)
    else:
        head = org or name
        tail = role
    heading = f"{head} — {tail}" if tail else head
    prefix = f"{markers} " if markers else ""
    return f"{prefix}{heading}{dagger}"


def render_partner(partner, marker_mode="emoji"):
    """Render one partner as a subheading plus labelled bullet lines."""
    out = [f"### {title_of(partner, marker_mode)}", ""]

    out.append(f"- **Why them:** {esc(partner.get('hook'))}")
    out.append(f"- **Next step:** {esc(partner.get('next_step'))}")
    out.append(
        f"- **Axes:** {esc(partner.get('class'))} · {esc(partner.get('scope'))} · "
        f"reach {esc(partner.get('reach'))} · warmth {esc(partner.get('warmth'))} · "
        f"priority {esc(partner.get('priority'))} · action **{esc(partner.get('action'))}**"
    )
    if partner.get("priorities"):
        mapped = ", ".join(str(p) for p in partner["priorities"])
        out.append(f"- **Ersilia priorities served:** {mapped}")

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
    if partner.get("seen_before"):
        out.append("- **Note:** surfaced in an earlier sweep (seen)")
    if partner.get("known_partner"):
        out.append("- **Note:** already an existing relationship (known partner)")
    if not partner.get("verified", True):
        out.append("- **† Unverified** — no live page confirmed this; verify or drop before sharing")
    out.append("")
    return out


def render(partners, run_date, focus, sources, marker_mode="emoji", layout="table"):
    """Build the whole report as a list of lines."""
    by_class = defaultdict(list)
    for partner in partners:
        by_class[partner.get("class") or "Other"].append(partner)

    class_order = [c for c in CLASS_VALUES if by_class.get(c)]
    class_order += [c for c in sorted(by_class) if c not in CLASS_VALUES]

    out = [f"# Ersilia Partner Sweep — {run_date}", ""]
    present = ", ".join(class_order) if class_order else "none"
    out.append(
        f"**Scope:** {len(partners)} new candidate partner(s) · classes: {present} · "
        f"focus: {focus or 'broad sweep'} · {sources} source(s) swept"
    )
    legend = MARKER_LEGEND_TEXT if marker_mode == "text" else MARKER_LEGEND
    out.append(f"**Markers:** {legend}")
    out.append("")

    if layout == "table":
        # The table is sorted by priority already, and 🤝 marks the warm rows, so the
        # separate "start here" list and the per-class sections would just restate it.
        out.append("## Counts")
        out.append("")
        for class_name in class_order:
            group = by_class[class_name]
            tally = Counter(p.get("priority") for p in group)
            breakdown = " · ".join(f"{p} {tally[p]}" for p in PRIORITY_VALUES if tally[p])
            out.append(f"- **{class_name}:** {len(group)}" + (f" ({breakdown})" if breakdown else ""))
        if not class_order:
            out.append("- Nothing survived screening this sweep.")
        out.append("")
        out.append("## Partners")
        out.append("")
        if partners:
            out.extend(render_table(partners, marker_mode))
        else:
            out.append("Nothing survived screening this sweep.")
            out.append("")
        unverified_rows = [p for p in partners if not p.get("verified", True)]
        if unverified_rows:
            out.append("## † Unverified — resolve before sharing")
            out.append("")
            for partner in unverified_rows:
                out.append(f"- {esc(partner.get('name'))} — {esc(partner.get('source'))}")
            out.append("")
        return out

    # Warm paths first — the cheapest actions in the report, and the ones most likely
    # to be dropped if a reader stops halfway down a long list.
    warm = [p for p in partners if p.get("warmth") in ("Shared network", "Warm intro", "Existing contact")]
    warm_heading = "Start here — warm paths" if marker_mode == "text" else "🤝 Start here — warm paths"
    out.append(f"## {warm_heading}")
    out.append("")
    if warm:
        for partner in warm:
            markers = render_markers(partner.get("markers"), marker_mode)
            label = str(partner.get("person") or partner.get("org") or partner.get("name") or "").strip()
            out.append(f"- {markers} **{label}** — {esc(partner.get('next_step'))}")
    else:
        out.append("- None this sweep — every candidate is a cold approach.")
    out.append("")

    out.append("## Counts")
    out.append("")
    for class_name in class_order:
        group = by_class[class_name]
        tally = Counter(p.get("priority") for p in group)
        breakdown = " · ".join(f"{p} {tally[p]}" for p in PRIORITY_VALUES if tally[p])
        out.append(f"- **{class_name}:** {len(group)}" + (f" ({breakdown})" if breakdown else ""))
    if not class_order:
        out.append("- Nothing survived screening this sweep.")
    out.append("")

    for class_name in class_order:
        out.append(f"## {CLASS_HEADINGS.get(class_name, class_name)}")
        out.append("")
        for partner in by_class[class_name]:
            out.extend(render_partner(partner, marker_mode))

    unverified = [p for p in partners if not p.get("verified", True)]
    if unverified:
        out.append("## † Unverified — resolve before sharing")
        out.append("")
        for partner in unverified:
            out.append(f"- {esc(partner.get('name'))} — {esc(partner.get('source'))}")
        out.append("")

    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the partner sweep report.")
    parser.add_argument("--in", dest="infile", required=True, help="cleaned partner JSON")
    parser.add_argument("--out", dest="outfile", required=True, help="output markdown path")
    parser.add_argument("--date", dest="run_date", required=True, help="run date YYYY-MM-DD")
    parser.add_argument("--focus", default="", help="the focus lens for this sweep")
    parser.add_argument("--sources", type=int, default=0, help="how many sources were swept")
    parser.add_argument("--layout", choices=("table", "detail"), default="table",
                        help="'table' (default) is one master table, one row per partner; "
                             "'detail' is a heading and labelled bullets per partner, which "
                             "is what a Google Drive Doc needs")
    parser.add_argument("--markers", choices=("emoji", "text"), default="emoji",
                        help="emoji ribbon (default, for the local report) or bracketed "
                             "text labels (for a Google Drive Doc, whose markdown "
                             "conversion corrupts non-BMP emoji)")
    args = parser.parse_args(argv)

    partners = read_json(args.infile)
    if not isinstance(partners, list):
        print("ERROR: input JSON must be an array of partner objects", file=sys.stderr)
        sys.exit(1)

    lines = render(partners, args.run_date, args.focus, args.sources, args.markers, args.layout)
    with open(args.outfile, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")

    print(f"rendered {len(partners)} partner(s) -> {args.outfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
