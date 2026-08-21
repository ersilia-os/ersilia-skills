#!/usr/bin/env python3
"""Render a one-page dossier on a single named partner target.

Used by the skill's `dossier` mode, when the target is already known and the question is
"what do we say to them, and how do we reach them" rather than "who should we approach".

Like render_sweep.py this emits no markdown pipe tables — see that file's docstring for
why (the Drive markdown-to-Doc conversion mangles them; verified 2026-08-20).

Input is a single JSON object, or a one-element array (so the same file can be piped
through filter_and_sort.py first if you want the contact policy applied).

Usage:
  python scripts/render_dossier.py --in target.json --out reports/26-08-20-dossier-name.md \
      --date 2026-08-20

Exit code 0 on success; 1 on unreadable input or an input array that is not one object.
"""

import argparse
import sys

from _common import cost_of, read_json

SECTIONS_REQUIRED = ("background", "pitch", "ask")


def esc(value):
    text = str(value or "").strip()
    return text if text else "—"


def bullets(values, empty="— none recorded"):
    """Render a list as markdown bullets, or a single placeholder line when empty."""
    items = [v for v in (values or []) if str(v).strip()]
    if not items:
        return [f"- {empty}"]
    return [f"- {str(v).strip()}" for v in items]


def render_recent_work(items):
    """Recent relevant work as bullets, each optionally a link with a date."""
    if not items:
        return ["- — none recorded. A dossier without recent work is a weak dossier: "
                "the hook depends on what they published or covered lately."]
    lines = []
    for item in items:
        if isinstance(item, dict):
            label = item.get("title") or item.get("url") or "untitled"
            url = item.get("url")
            dated = f" ({item['date']})" if item.get("date") else ""
            note = f" — {item['note']}" if item.get("note") else ""
            head = f"[{label}]({url})" if url else str(label)
            lines.append(f"- {head}{dated}{note}")
        else:
            lines.append(f"- {item}")
    return lines


def render(target, run_date):
    person = str(target.get("person") or "").strip()
    org = str(target.get("org") or "").strip()
    role = str(target.get("role") or "").strip()
    name = person or org or str(target.get("name") or "unnamed target").strip()
    dagger = "" if target.get("verified", True) else " †"

    out = [f"# Partner dossier — {name}{dagger}", ""]

    subtitle = " · ".join(t for t in (role, org) if t)
    if subtitle:
        out.append(f"**{subtitle}**")
    out.append(
        f"**Prepared:** {run_date} · **Class:** {esc(target.get('class'))} · "
        f"**Scope:** {esc(target.get('scope'))} · **Reach:** {esc(target.get('reach'))} · "
        f"**Warmth:** {esc(target.get('warmth'))} · **Recommended action:** "
        f"**{esc(target.get('action'))}**"
    )
    if target.get("priorities"):
        out.append(f"**Ersilia priorities served:** {', '.join(str(p) for p in target['priorities'])}")
    out.append("")

    if not target.get("verified", True):
        out.append("> **† Unverified.** No live page confirmed the details below. Resolve "
                   "this before anyone acts on the dossier.")
        out.append("")

    out.append("## Who they are")
    out.append("")
    out.append(esc(target.get("background")))
    out.append("")

    out.append("## What they cover")
    out.append("")
    out.append(esc(target.get("remit")))
    out.append("")

    out.append("## Audience and reach")
    out.append("")
    out.append(esc(target.get("audience")))
    out.append("")

    out.append("## Recent relevant work")
    out.append("")
    out.extend(render_recent_work(target.get("recent_work")))
    out.append("")

    out.append("## Ways in")
    out.append("")
    out.extend(bullets(target.get("warm_paths"),
                       empty="— no warm path found; this is a cold approach"))
    contacts = target.get("contacts") or []
    if contacts:
        out.append("")
        out.append("**Contact channels on file:**")
        out.append("")
        for contact in contacts:
            note = (" — published for scientific correspondence, **not** a pitch channel"
                    if contact.get("restricted") else "")
            out.append(f"- {contact.get('kind')}: {contact.get('value')}{note}")
    out.append("")

    if cost_of(target):
        out.append("## Cost")
        out.append("")
        out.append(esc(cost_of(target)))
        out.append("")

    out.append("## The pitch")
    out.append("")
    out.append(esc(target.get("pitch")))
    out.append("")

    out.append("## The ask")
    out.append("")
    out.append(esc(target.get("ask")))
    out.append("")

    out.append("## Risks and mismatches")
    out.append("")
    out.extend(bullets(target.get("risks"), empty="— none identified"))
    out.append("")

    out.append("## Sources consulted")
    out.append("")
    sources = target.get("sources") or []
    if not sources and target.get("url"):
        sources = [target["url"]]
    out.extend(bullets(sources, empty="— none recorded. Every claim above should trace to one."))
    out.append("")

    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a one-page partner dossier.")
    parser.add_argument("--in", dest="infile", required=True, help="target JSON (object or 1-element array)")
    parser.add_argument("--out", dest="outfile", required=True, help="output markdown path")
    parser.add_argument("--date", dest="run_date", required=True, help="preparation date YYYY-MM-DD")
    args = parser.parse_args(argv)

    data = read_json(args.infile)
    if isinstance(data, list):
        if len(data) != 1:
            print(f"ERROR: dossier input must be one target; got an array of {len(data)}",
                  file=sys.stderr)
            sys.exit(1)
        data = data[0]
    if not isinstance(data, dict):
        print("ERROR: dossier input must be a JSON object", file=sys.stderr)
        sys.exit(1)

    # Warn rather than fail: a half-filled dossier is still useful to iterate on, but the
    # gaps must be visible in the run output, not only discovered by a reader later.
    thin = [s for s in SECTIONS_REQUIRED if not str(data.get(s) or "").strip()]
    if thin:
        print(f"WARNING: dossier is missing {', '.join(thin)} — these carry the whole "
              "document; fill them before sharing", file=sys.stderr)

    lines = render(data, args.run_date)
    with open(args.outfile, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")

    label = data.get("person") or data.get("org") or data.get("name")
    print(f"rendered dossier for {label!r} -> {args.outfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
