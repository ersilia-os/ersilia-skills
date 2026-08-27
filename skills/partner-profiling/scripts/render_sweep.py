#!/usr/bin/env python3
"""Render the cleaned partner pool as the sweep report.

Two layouts, one per destination. Keep both working — they are not two styles.

`--layout table` (the DEFAULT) is the local markdown report: one pipe table per class,
one row per partner, with columns chosen for that class. Scannable in a single pass.

`--layout detail` renders each partner as a subheading with labelled bullet lines and no
pipe tables at all. That is the layout for a Google Drive Doc: the connector converts
markdown to a Doc with headings and bullets intact, but **mangles pipe tables** — the
header row comes back empty and its cells are demoted into a body row with escaped
literal asterisks. Verified 2026-08-20.

A second, independent Drive problem is handled by a separate flag: `--markers text`
replaces the emoji ribbon with bracketed labels, because that same conversion corrupts
emoji **outside the Basic Multilingual Plane** (the 🏠🌍💻📣🤝 set, U+1F3xx-U+1F9xx),
while ⭐ (U+2B50) and ✉️ (U+2709) survive. Layout and markers are orthogonal: a Drive
rendition needs `--layout detail --markers text`, both.

Usage:
  python scripts/render_sweep.py --in clean.json --out reports/26-08-20-partner-sweep.md \
      --date 2026-08-20 --focus "science journalists, AMR" --sources 14

Exit code 0 on success; 1 on an unreadable input file.
"""

import argparse
import sys
from collections import Counter, defaultdict

from _common import CLASS_VALUES, COST_UNKNOWN, PRIORITY_VALUES, cost_of, read_json

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
            # The ellipsis goes on EVERY cut path, not just the word-boundary one. Cutting
            # at a sentence end produces a cell that reads as a complete thought, which is
            # the "truncated content looks complete" failure this skill exists to avoid —
            # and TRIM_NOTE tells the reader that a trimmed cell ends in an ellipsis, so an
            # unmarked cut makes the footnote a lie. Same suffix as the fallback below, so
            # there is exactly one ellipsis form in the file.
            return window[:idx + 1].rstrip() + " …"
    idx = window.rfind(" ")
    return (window[:idx] if idx > 0 else window).rstrip() + " …"


# Context fields (hook, amplification) are trimmed; `next_step` never is. It is the
# field the whole skill exists to produce, and a truncated instruction is worse than a
# long cell — a trimmed conditional ("only if X, otherwise drop") reads as an
# unconditional one.
TRIM_NOTE = ("*Cells ending in “…” are trimmed for context only — next steps and costs are "
             "never trimmed. A `—` in **Cost** means not established, **not** free. "
             "Full text is in the partner JSON, or re-render with `--layout detail`.*")


def _fmt_events(partner):
    """Creative rows: does the portfolio show event work? Distinguish no from unknown."""
    value = partner.get("does_events")
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def _fmt_portfolio(partner):
    return link("view", partner["portfolio_url"]) if partner.get("portfolio_url") else "—"


# Columns that differ **by class**, because the classes are not comparable on the same
# axes. You assess a photographer on rate, event experience and licensing; a journalist on
# reach. Forcing one shared table means every row carries the lowest common denominator
# and the class-specific fields — which are the ones that decide the commission — vanish.
#
# Keep this in sync with `references/classification.md`. A class missing here falls back to
# CLASS_COLUMNS_DEFAULT rather than erroring, so a new class value renders before anyone
# has decided what its useful columns are.
CLASS_COLUMNS = {
    "Media":       [("Reach", lambda p: cell(p.get("reach")))],
    "Open-source": [("Scope", lambda p: cell(p.get("scope")))],
    "Institution": [("Scope", lambda p: cell(p.get("scope")))],
    "Comms-team":  [("Scope", lambda p: cell(p.get("scope")))],
    "Community":   [("Reach", lambda p: cell(p.get("reach")))],
    # No Rate column here any more — `Cost` is shared across every class (see
    # render_class_table), so a Creative-only rate column would duplicate it.
    "Creative":    [("Covers events", _fmt_events),
                    ("Portfolio", _fmt_portfolio)],
}
CLASS_COLUMNS_DEFAULT = [("Scope", lambda p: cell(p.get("scope")))]


def partner_label(partner):
    """Linked display name plus the unverified dagger."""
    name = partner.get("person") or partner.get("org") or partner.get("name")
    dagger = "" if partner.get("verified", True) else " †"
    url = partner.get("url")
    label = f"[{cell(name)}]({url})" if url else cell(name)
    return f"{label}{dagger}"


def render_class_table(partners, class_name, marker_mode, mode="sweep",
                       context_header="Why them", context_field="hook",
                       leading=None):
    """One table for one class.

    ``leading`` is a list of (header, fn) prepended before the shared columns — campaign
    mode uses it for the contact-by date. ``context_field`` is the prose column, and
    ``next_step`` always comes last and is **never trimmed**.
    """
    cols = list(leading or [])
    cols.append(("Partner", partner_label))
    cols.append(("Markers", lambda p: render_markers(p.get("markers"), marker_mode) or "—"))
    if mode == "sweep":
        cols.append(("Pri", lambda p: cell(p.get("priority"))))
    cols.extend(CLASS_COLUMNS.get(class_name, CLASS_COLUMNS_DEFAULT))
    # Cost is NEVER trimmed, for the same reason next_step is not: it is a figure, not
    # prose. A cost note routinely carries a second, cheaper tier ("EUR 400-500 for events
    # under 2-4 hours") or a caveat ("no formal rate card") at the END of the string, so a
    # cut removes exactly the part a budget needs. It was previously trimmed at a bare 72 —
    # an undeclared second cell limit, 24 characters TIGHTER than CELL_LIMIT while its
    # comment called it "generous" — and it was truncating the live anniversary report.
    cols.append(("Cost", lambda p: cell(cost_of(p)) if cost_of(p) else COST_UNKNOWN))
    cols.append((context_header, lambda p: trim(p.get(context_field) or p.get("hook"))))
    cols.append(("Action", lambda p: f"**{cell(p.get('action'))}**"))
    cols.append(("Next step", lambda p: cell(p.get("next_step"))))

    out = [
        "| " + " | ".join(h for h, _ in cols) + " |",
        "|" + "---|" * len(cols),
    ]
    for partner in partners:
        out.append("| " + " | ".join(fn(partner) for _, fn in cols) + " |")
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
    if cost_of(partner):
        out.append(f"- **Cost:** {esc(cost_of(partner))}")
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

        # Warm rows still get their own strip. Splitting the report into per-class tables
        # scatters them, and they are the cheapest actions in it.
        warm_rows = [p for p in partners
                     if p.get("warmth") in ("Shared network", "Warm intro", "Existing contact")]
        if warm_rows:
            out.append("## 🤝 Start here — warm paths")
            out.append("")
            for partner in warm_rows:
                markers = render_markers(partner.get("markers"), marker_mode)
                label = str(partner.get("person") or partner.get("org")
                            or partner.get("name") or "").strip()
                out.append(f"- {markers} **{label}** · {esc(partner.get('class'))} — "
                           f"{esc(partner.get('next_step'))}")
            out.append("")

        for class_name in class_order:
            out.append(f"## {CLASS_HEADINGS.get(class_name, class_name)}")
            out.append("")
            out.extend(render_class_table(by_class[class_name], class_name, marker_mode,
                                          mode="sweep"))
        # The Counts section already said so when the pool is empty; repeating it here,
        # and printing a note about trimmed cells when there are no tables, both read as
        # a rendering fault rather than an empty result.
        if class_order:
            out.append(TRIM_NOTE)
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
