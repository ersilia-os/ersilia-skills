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
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_json, warn  # noqa: E402

TODO = "**TODO — no `summary` written for this model.**"

# The Hub's task families, in the order the digest presents them. `Task` is the category
# over `Subtask`: Annotation covers activity and property prediction, Representation covers
# featurization and projection, Sampling covers generation. Anything unrecognised sorts
# after these, alphabetically, so a new family shows up rather than vanishing into a group
# it does not belong to.
TASK_ORDER = ("Annotation", "Representation", "Sampling")

# The literature digest's own task vocabulary, reused verbatim: a reader who knows one
# digest should not have to learn a second set of symbols for the same six things.
SUBTASK_EMOJI = {
    "Property calculation or prediction": "🧪",
    "Activity prediction": "🎯",
    "Featurization": "🧩",
    "Projection": "🗺️",
    "Similarity search": "🔍",
    "Generation": "🎨",
}

def first_author(credit):
    """``First Author et al.`` — the first author's full name, marked when there are more.

    The table names one person per model; a cell carrying eleven names is a cell nobody
    reads, and the full list lives in the paper one click away. "et al." is the convention
    that says the list continues. There is deliberately no author count after it: that was
    ours alone and matches no citation style.

    The given name is kept, unlike the literature digest's bare surnames. Its author string
    sits inside a citation-style link, where a surname is right; this is a credit field,
    and a credit carries the whole name.
    """
    names = [a["name"] for a in credit.get("authors", []) if a.get("name")]
    if not names:
        return "*authors unresolved*"
    return names[0] if len(names) == 1 else f"{names[0]} et al."


# Sub-units, legal suffixes and parenthetical cities make an institution unreadable in a
# narrow cell. Trimming them is structural — nothing is abbreviated or invented, so the
# name that survives is still the institution's own.
_LEGAL_SUFFIX = re.compile(r"[,\s]+(?:Inc\.?|Ltd\.?|LLC|GmbH|S\.A\.|PLC)\b", re.I)


def concise_institution(credit):
    """The lead institution, trimmed to something that fits a table cell."""
    names = credit.get("lead_institutions") or []
    if not names:
        return None
    name = str(names[0])
    name = re.sub(r"\s*\([^)]*\)", "", name)     # trailing "(Yerevan)", "(United States)"
    name = _LEGAL_SUFFIX.sub("", name)
    name = name.split(",")[0]                      # drop the sub-unit after the comma
    return " ".join(name.split()).strip(" .,")


def cell(text):
    """Flatten a value into a markdown table cell.

    Newlines end a table row and an unescaped pipe starts a new column, so both have to
    go before a paragraph can live inside a cell.
    """
    return " ".join(str(text or "").split()).replace("|", "\\|")


def task_of(record):
    """The model's task category, falling back to a visible placeholder."""
    return (record.get("model") or {}).get("task") or "Uncategorised"


def task_rank(task):
    """Sort key putting the known families in TASK_ORDER, then the rest alphabetically."""
    return (TASK_ORDER.index(task), "") if task in TASK_ORDER else (len(TASK_ORDER), task)


def ordered_models(models):
    """Every model, grouped by task category and stably ordered inside each group.

    One ordering is used for both the summary and the per-model sections, so a reader
    moving between them finds the models in the same sequence.
    """
    return sorted(
        models,
        key=lambda r: (
            task_rank(task_of(r)),
            (r.get("model") or {}).get("subtask") or "",
            r.get("identifier") or "",
        ),
    )


def task_groups(models):
    """``[(task, [records])]`` in presentation order — the digest's task categories."""
    groups = {}
    for record in ordered_models(models):
        groups.setdefault(task_of(record), []).append(record)
    return sorted(groups.items(), key=lambda kv: task_rank(kv[0]))


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


def code_link(url):
    """A clickable link to the authors' repository, labelled without the scheme.

    Written out as an explicit markdown link rather than left bare: the digests site
    renders with kramdown, which does not autolink a plain URL, so a bare address came
    out as unclickable text on the published page.
    """
    if not url:
        return "—"
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        return url
    label = url.split("://", 1)[1].rstrip("/")
    return f"[{label}]({url})"


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
    # One paragraph of short lines directly under the H1 — the site styles that block
    # specially. Markdown needs two trailing spaces to keep them as separate lines.
    header = [
        f"**Models incorporated:** {context.get('n_models', 0)}" + (f" — {tasks}" if tasks else ""),
        f"**Status:** {statuses or 'unknown'}",
    ]
    if context.get("n_global_south"):
        header.append(
            f"**Global-South-led:** {context['n_global_south']} of "
            f"{context.get('n_models', 0)} have an author at an LMIC institution"
        )
    # Not len(catalogue): that counts models still in progress, and it is a snapshot of
    # whenever the fetch ran, so the same month re-rendered later reports a different Hub.
    # The digest reports on a month, so its total is the month's.
    hub = context.get("hub_size_at_month_end")
    if hub:
        header.append(
            f"**Hub total:** {hub} models incorporated by {context.get('month_last_day')}"
        )
    header.append(f"**Prepared:** {prepared_on} from the Hub catalogue")
    lines.extend(line + "  " for line in header[:-1])
    lines.append(header[-1])
    lines.append("")

    if not models:
        lines.append(f"No models were incorporated in {label}.")
        lines.append("")
        return "\n".join(lines)

    # ---- one table per task category ----
    lines.append("## The models")
    lines.append("")
    for task, records in task_groups(models):
        lines.append(f"### {task} — {len(records)} model{'s' if len(records) != 1 else ''}")
        lines.append("")
        lines.append("| Model | Tag | Author | What it does | Links |")
        lines.append("|---|---|---|---|---|")
        for record in records:
            model, credit, publication = record["model"], record["credit"], record["publication"]

            ident = f"[`{record['identifier']}`]({model.get('github')})"
            first = f"{ident}<br>{cell(model.get('title') or model.get('slug'))}"

            subtask = model.get("subtask") or model.get("task") or "—"
            emoji = SUBTASK_EMOJI.get(subtask, "")
            tag = f"{emoji} {cell(subtask)}".strip()

            venue = " ".join(
                " ".join(str(part).split())
                for part in (publication.get("journal"), publication.get("year"))
                if part
            )
            if not publication.get("journal"):
                # No container title means no journal version was deposited. Keyed on the
                # record rather than on `Publication Type`, which is itself a field the
                # scan flags as unreliable — eos5g6m declares "Peer reviewed" over an
                # arXiv DOI, and a bare year told the reader nothing.
                venue = f"preprint {publication.get('year') or ''}".strip()
            who = [f"**{cell(first_author(credit))}**"]
            where = concise_institution(credit)
            if where:
                who.append(cell(where))
            if venue:
                who.append(f"*{cell(venue)}*")
            author = "<br>".join(who)

            what = cell(record.get("summary")) or TODO

            # Fall back to whatever Publication holds. A record with no DOI — eos5mnx's
            # OpenReview URL — otherwise published with a Code link and no paper at all,
            # which is the one case where the paper is hardest to find by other means.
            paper = publication.get("doi_url") or publication.get("raw_publication_field")
            links = [f"[Paper]({paper})"] if paper else []
            if model.get("source_code"):
                links.append(f"[Code]({model['source_code']})")
            joined = "<br>".join(links) or "—"

            lines.append(f"| {first} | {tag} | {author} | {what} | {joined} |")
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
