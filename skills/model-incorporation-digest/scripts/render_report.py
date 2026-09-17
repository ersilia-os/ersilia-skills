#!/usr/bin/env python3
"""render_report.py — turn a month context into the internal model-incorporation digest.

    python render_report.py month-context.json --out reports/2026-08-digest.md
    python render_report.py month-context.json --out /tmp/26-08-31-models-digest.md --public

Rendering is deterministic: everything factual comes straight out of the context JSON, so
two runs of the same month produce the same document and nothing drifts in the retelling.

The digest is internal and carries no announcement draft: what it reports is what went
into the Hub, who made it, and what the metadata scan flagged.

The one part that needs judgement is the per-model paragraph, and that is not invented
here. Each model record in the JSON may carry a ``"summary"`` string, written by whoever
runs the skill after reading the abstract; a model without one renders a visible TODO and
the script exits non-zero. That keeps the split honest — the script never writes prose
about a model, and an unfinished report cannot pass as a finished one.

Standard library only, and no clock unless --date is omitted.
"""

from __future__ import annotations

import argparse
import calendar
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_json, warn  # noqa: E402

TODO = "**TODO — no `summary` written for this model.**"


def author_phrase(credit):
    """Compact credit for a table cell: first author, et al., and the count.

    Rendered in the table as inline code, matching the identifier column, so the two
    data-ish columns read alike instead of one being prose.
    """
    authors = [a["name"] for a in credit.get("authors", []) if a.get("name")]
    if not authors:
        return "*unresolved*"
    if len(authors) == 1:
        return authors[0]
    return f"{authors[0]} et al. ({len(authors)})"


def full_credit(credit):
    """Every author for a paper with five or fewer; first, last and a count beyond."""
    authors = [a["name"] for a in credit.get("authors", []) if a.get("name")]
    if not authors:
        return "*authors unresolved — see the defects section*"
    if len(authors) == 1:
        return authors[0]
    if len(authors) <= 5:
        return ", ".join(authors[:-1]) + " and " + authors[-1]
    return f"{authors[0]}, {authors[-1]} and {len(authors) - 2} colleagues"


def institutions(credit, limit=3):
    """The leading institutions, in first-author-first order."""
    names = credit.get("lead_institutions") or []
    return " · ".join(names[:limit]) if names else None


def paper_link(publication):
    """A markdown link to the paper, falling back to whatever the metadata holds."""
    if publication.get("doi_url"):
        label = publication.get("doi") or publication["doi_url"]
        return f"[{label}]({publication['doi_url']})"
    raw = publication.get("raw_publication_field")
    return f"[{raw}]({raw})" if raw else "*none*"


def render(context, prepared_on, public=False):
    """Build the whole digest as one markdown string.

    ``public`` drops the metadata-defects section. That section lists repairs owed on
    models that are already live and is addressed to whoever can make them, so it is
    written for the team and does not belong on a public page. Everything else — the
    counts, the table, the per-model paragraphs and their author credit — is the same
    document either way, rendered from the same context.
    """
    models = context.get("models", [])
    lines = []

    label = context.get("month_label", context.get("month", "unknown month"))
    lines.append(f"# Ersilia model incorporation digest — {label}")
    lines.append("")

    tasks = ", ".join(f"{n} {task}" for task, n in (context.get("by_task") or {}).items())
    statuses = ", ".join(
        f"{n} {status}" for status, n in (context.get("by_status") or {}).items()
    )
    lines.append(f"**Models incorporated:** {context.get('n_models', 0)}" + (f" — {tasks}" if tasks else ""))
    lines.append(f"**Status:** {statuses or 'unknown'}")
    if context.get("n_global_south"):
        lines.append(
            f"**Global-South-led:** {context['n_global_south']} of "
            f"{context.get('n_models', 0)} have an author at an LMIC institution"
        )
    lines.append(
        f"**Prepared:** {prepared_on} from the Hub catalogue "
        f"({context.get('catalog_size', '?')} models)"
    )
    lines.append("")

    if not models:
        lines.append(f"No models were incorporated in {label}.")
        lines.append("")
        return "\n".join(lines)

    # ---- summary table ----
    lines.append("## Summary")
    lines.append("")
    # No paper column: every model's section below carries its DOI, and a second copy
    # here only crowded the four columns that answer "what shipped".
    lines.append("| Model | Title | Task | Authors |")
    lines.append("|---|---|---|---|")
    for record in models:
        model, credit = record["model"], record["credit"]
        lines.append(
            f"| [`{record['identifier']}`]({model.get('github')}) "
            f"| {model.get('title') or '—'} "
            f"| {model.get('subtask') or model.get('task') or '—'} "
            f"| `{author_phrase(credit)}` |"
        )
    lines.append("")

    # ---- one section per model ----
    lines.append("## The models")
    lines.append("")
    for record in models:
        model, credit, publication = record["model"], record["credit"], record["publication"]
        lines.append(f"### `{record['identifier']}` · {model.get('title') or model.get('slug')}")
        lines.append("")

        byline = full_credit(credit)
        where = institutions(credit)
        # Crossref deposits some journal names with embedded newlines, which would
        # otherwise break the byline across two lines.
        venue = " ".join(
            " ".join(str(p).split())
            for p in (publication.get("journal"), publication.get("year"))
            if p
        )
        if publication.get("type") == "Preprint" and not publication.get("journal"):
            venue = f"preprint {publication.get('year') or ''}".strip()
        lines.append(f"**{byline}**" + (f" — {where}" if where else "") + (f" · {venue}" if venue else ""))
        lines.append("")

        summary = (record.get("summary") or "").strip()
        lines.append(summary or TODO)
        lines.append("")

        facts = [
            f"Paper: {paper_link(publication)}",
            f"Authors' code: {model.get('source_code') or '—'}",
            f"Run it: `ersilia fetch {model.get('slug') or record['identifier']}`",
        ]
        if model.get("license"):
            facts.append(f"Licence: {model['license']}")
        lines.append(" · ".join(facts))
        lines.append("")

    # ---- defects (internal only) ----
    if public:
        return "\n".join(lines)

    flagged = [r for r in models if r.get("defects")]
    lines.append("## Metadata to fix")
    lines.append("")
    if not flagged:
        lines.append("Nothing flagged this month.")
    else:
        lines.append(
            "Each of these is a `/model-incorporation-metadata` gap in a model already "
            "marked live. They are listed here because whoever reads this digest can go "
            "and fix them."
        )
        lines.append("")
        for record in flagged:
            lines.append(f"- **`{record['identifier']}`** — " + "; ".join(record["defects"]))
    lines.append("")

    return "\n".join(lines)


def public_filename(context):
    """Canonical name for the published copy: YY-MM-DD-models-digest.md, month-end.

    The sibling digests date a file by the end of the window it covers, so a month's
    digest is dated the last day of that month.
    """
    year, month = (int(part) for part in str(context["month"]).split("-")[:2])
    last_day = calendar.monthrange(year, month)[1]
    return f"{year % 100:02d}-{month:02d}-{last_day:02d}-models-digest.md"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("context", help="month context JSON from fetch_month_models.py")
    parser.add_argument("--out", required=True, help="path to write the report markdown")
    parser.add_argument("--date", help="preparation date as YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--public",
        action="store_true",
        help="omit the metadata-defects section, for the copy published to the digests site",
    )
    args = parser.parse_args(argv)

    context = read_json(args.context)
    prepared = args.date or date.today().isoformat()
    body = render(context, prepared, public=args.public)

    missing = [r["identifier"] for r in context.get("models", []) if not (r.get("summary") or "").strip()]
    Path(args.out).write_text(body + "\n", encoding="utf-8")
    print(f"wrote {args.out}", file=sys.stderr)

    if args.public:
        # upload_digest.py enforces this name and refuses anything else, and a month-end
        # day computed by hand is exactly the kind of thing that is wrong every February.
        print(f"canonical public filename: {public_filename(context)}", file=sys.stderr)

    if missing:
        warn(f"no summary written for: {', '.join(missing)} — the report has TODO markers")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
