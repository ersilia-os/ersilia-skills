#!/usr/bin/env python3
"""check_post.py — lint an announcement draft against the attribution rules.

    python check_post.py reports/2026-08-technology.md --context month-context.json

Extracts the round-up post from the report's ``## Draft LinkedIn round-up`` fenced block
and checks the rules
in references/attribution-rules.md that can be checked mechanically. Exits 1 if any
FAIL, 0 otherwise; warnings never fail the run.

Why a linter at all: "give the authors more prominence than ourselves" is the kind of
rule that holds in a careful draft and quietly erodes in a hurried one. The four rules
that carry that principle — an author named in the hook, no self-reference before the
authors, plumbing verbs only for Ersilia, the paper linked before the Hub — are all
decidable from the text, so they are enforced here rather than trusted.

Deterministic (no clock, no network) and standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import read_json, surname  # noqa: E402

# LinkedIn truncates the feed preview at roughly this many characters. Reported so the
# writer can see what shows before "…see more"; the house opener is an Ersilia
# announcement, so authors are not required this early.
HOOK_CHARS = 210

# A round-up covers a whole month, so per-model credit cannot all sit in the opening 400
# characters the way a single-model announcement's could. Instead every model the post
# names must carry its first author, wherever in the post that falls.
LENGTH_MIN, LENGTH_MAX = 900, 2500

# LinkedIn's hard ceiling; the house target is much shorter.
MAX_CHARS = 3000  # LinkedIn's hard ceiling

# Phrases that claim the authors' work for Ersilia. See references/attribution-rules.md.
# Phrases that claim the authors' science. Announcing an incorporation is not claiming
# authorship, so "excited to announce" is the house opener and is absent from this list —
# but "launch" and "present" make the model the object of the verb, and stay banned.
AUTHORSHIP_CLAIMS = (
    "we built", "we've built", "we have built",
    "we developed", "we've developed", "we have developed",
    "we trained", "we've trained", "we have trained",
    "we created", "we've created", "we designed",
    "we present", "we introduce", "introducing our",
    "our new model", "our latest model", "our model predicts",
    "we're excited to launch", "we are excited to launch",
    "proud to present our",
)

# Meta-commentary that narrates the credit arrangement, or hedges, instead of crediting.
# Each reads as generosity and spends a paragraph on us; see attribution-rules.md R10.
META_COMMENTARY = (
    "the whole of our contribution", "our part is the plumbing",
    "the science is theirs", "changed nothing",
    "we have not benchmarked", "we did not change",
)

BANNED_PHRASES = AUTHORSHIP_CLAIMS + META_COMMENTARY

# Verbs Ersilia may use about its own contribution.
PLUMBING_VERBS = (
    "packaged", "wrapped", "made available", "added", "standardised", "standardized",
    "integrated", "incorporated", "ported", "hosted", "serve", "serves", "distributed",
)

SELF_REFERENCE_RE = re.compile(r"\b(ersilia|we|we're|weve|we've|our|ours|us)\b", re.I)

ERSILIA_LINK_RE = re.compile(
    r"(ersilia\.io|github\.com/ersilia-os|hub\.docker\.com/r/ersiliaos|catalog\.ersilia\.io)", re.I
)
HASHTAG_RE = re.compile(r"(?<!\w)#(\w+)")
MD_BOLD_RE = re.compile(r"\*\*[^*]+\*\*|__[^_]+__")
MD_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
MENTION_RE = re.compile(r"@([A-Za-z][\w\-]*(?:\.[A-Za-z0-9_\-]+)*)")
MAX_ERSILIA_BLOCKS = 2

# A row still carrying one of these has not been looked up. The lookup is mandatory, so an
# unfinished worksheet is a failed draft rather than a to-do note.
PLACEHOLDERS = ("to look up", "to be looked up", "tbd", "todo", "xxx", "<name>", "<handle>")
HUB_PHRASE_RE = re.compile(r"Ersilia Model Hub", re.I)
URL_RE = re.compile(r"https?://\S+")
FETCH_CMD_RE = re.compile(r"\bersilia\s+(?:fetch|serve|run)\b[^\n]*")
METRIC_RE = re.compile(r"\b\d+(?:\.\d+)?\s?%|\b(?:auroc|auc|accuracy|f1|r2|rmse)\b", re.I)


class Report:
    """Collects PASS/WARN/FAIL lines and prints them in a stable order."""

    def __init__(self):
        self.rows = []

    def add(self, level, rule, message):
        self.rows.append((level, rule, message))

    def emit(self):
        order = {"FAIL": 0, "WARN": 1, "PASS": 2}
        for level, rule, message in sorted(self.rows, key=lambda r: (order[r[0]], r[1])):
            print(f"{level:4}  {rule:16}  {message}")
        fails = sum(1 for level, _, _ in self.rows if level == "FAIL")
        warns = sum(1 for level, _, _ in self.rows if level == "WARN")
        print(f"\n{fails} fail, {warns} warn, {len(self.rows) - fails - warns} pass")
        return fails


def extract_section(text, heading):
    """Return the body of a ``## <heading>`` section, up to the next ``## `` heading."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", re.M | re.S | re.I
    )
    match = pattern.search(text)
    return match.group(1) if match else None


POST_HEADINGS = ("Draft LinkedIn round-up", "Post", "Round-up")


def extract_post(text):
    """Pull the post body out of the first fenced block under a round-up heading."""
    section = None
    for heading in POST_HEADINGS:
        section = extract_section(text, heading)
        if section is not None:
            break
    if section is None:
        return None
    fence = re.search(r"```[a-zA-Z]*\n(.*?)```", section, re.S)
    if not fence:
        return None
    return fence.group(1).strip("\n")


def has_unicode_pseudo_bold(text):
    """Detect math-alphanumeric 'bold' letters, which screen readers do not read."""
    return any(0x1D400 <= ord(ch) <= 0x1D7FF for ch in text)


# Publishers deposit real typographic dashes and quotes in author names — OpenAlex
# returns "Harigua\u2010Souiai" with a U+2010 HYPHEN, which NFKD does not fold. A poster
# typing an ASCII hyphen must still match, or the author-credit checks fail on exactly the
# names most worth getting right.
PUNCTUATION_FOLD = str.maketrans(
    {
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
        "\u2015": "-", "\u2212": "-", "\u00ad": "-",
        "\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u201c": '"', "\u201d": '"',
    }
)


def strip_accents(text):
    """Fold accents, dashes and quotes so a surname matches however the poster typed it."""
    folded = str(text).translate(PUNCTUATION_FOLD)
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", folded) if not unicodedata.combining(ch)
    )


def check(post, draft_text, context, report):
    """Run every rule, adding a row per rule to ``report``."""
    # A month context carries a list of models; each contributes its own credit and its
    # own paper, and the rules below are written against that list rather than one model.
    entries = (context or {}).get("models", [])
    folded = strip_accents(post).lower()
    hook = post[:HOOK_CHARS]
    hook_folded = strip_accents(hook).lower()

    # Per model: the identifier, its first author's surname, and its DOI.
    per_model = []
    for record in entries:
        credit = record.get("credit", {})
        authors = [a.get("name") for a in credit.get("authors", []) if a.get("name")]
        per_model.append(
            {
                "identifier": record.get("identifier"),
                "title": (record.get("model") or {}).get("title") or "",
                "slug": (record.get("model") or {}).get("slug") or "",
                "first_author": authors[0] if authors else None,
                "first_surname": strip_accents(surname(authors[0])).lower() if authors else None,
                "doi": (record.get("publication") or {}).get("doi"),
            }
        )

    # Every author of every model, for the loose "is anyone credited" checks.
    surnames = []
    for record in entries:
        for author in record.get("credit", {}).get("authors", []):
            token = strip_accents(surname(author.get("name"))).lower()
            if len(token) > 2 and token not in surnames:
                surnames.append(token)

    # A model counts as "named in the post" if its identifier, slug or title appears.
    def is_named(entry):
        for token in (entry["identifier"], entry["slug"]):
            if token and token.lower() in folded:
                return True
        title = entry["title"]
        # Titles are long; the leading word is the model's name in Hub practice.
        lead = strip_accents(title.split()[0]).lower() if title.split() else ""
        return bool(lead) and len(lead) > 2 and lead in folded

    named = [e for e in per_model if is_named(e)]

    # R1 — every model the post names carries its own first author.
    if not per_model:
        report.add("WARN", "R1-CREDIT-EVERY-MODEL", "no models in context; cannot verify")
    elif not named:
        report.add(
            "FAIL", "R1-CREDIT-EVERY-MODEL",
            "the post names none of the month's models — a round-up that credits nobody "
            "in particular credits nobody",
        )
    else:
        uncredited = [
            e for e in named if not e["first_surname"] or e["first_surname"] not in folded
        ]
        unresolvable = [e for e in uncredited if not e["first_surname"]]
        missing = [e for e in uncredited if e["first_surname"]]
        if missing:
            report.add(
                "FAIL", "R1-CREDIT-EVERY-MODEL",
                "named without crediting its first author: "
                + ", ".join(f"{e['identifier']} ({e['first_author']})" for e in missing),
            )
        elif unresolvable:
            report.add(
                "WARN", "R1-CREDIT-EVERY-MODEL",
                "named but its author list never resolved, so credit cannot be checked: "
                + ", ".join(e["identifier"] for e in unresolvable)
                + " — get the names from the paper before posting",
            )
        else:
            report.add(
                "PASS", "R1-CREDIT-EVERY-MODEL",
                f"{len(named)} model(s) named, each with its first author",
            )

    # R2 — what Ersilia enables comes after who made it. The announcement may open the
    # post, but the packaging detail must not precede the credit.
    first_author_at = min((folded.find(s) for s in surnames if s in folded), default=-1)
    fetch_at = FETCH_CMD_RE.search(post)
    if not surnames:
        report.add("WARN", "R2-CREDIT-BEFORE-HUB", "no author list in context; cannot verify")
    elif first_author_at < 0:
        report.add("FAIL", "R2-CREDIT-BEFORE-HUB", "no author is named anywhere in the post")
    elif fetch_at and fetch_at.start() < first_author_at:
        report.add(
            "FAIL", "R2-CREDIT-BEFORE-HUB",
            f"the fetch command at char {fetch_at.start()} precedes the first author at "
            f"char {first_author_at}",
        )
    else:
        report.add("PASS", "R2-CREDIT-BEFORE-HUB", f"first author named at char {first_author_at}")

    # R3 — Ersilia does not use the authors' verbs, and does not narrate the credit.
    claims = [p for p in AUTHORSHIP_CLAIMS if p in folded]
    meta = [p for p in META_COMMENTARY if p in folded]
    problems = []
    if claims:
        problems.append(
            f"claims the authors' work: {', '.join(repr(h) for h in claims)} — use a "
            f"plumbing verb ({', '.join(PLUMBING_VERBS[:4])}…)"
        )
    if meta:
        problems.append(
            f"narrates the credit instead of crediting: {', '.join(repr(h) for h in meta)} — "
            f"delete the sentence, do not reword it (R10)"
        )
    if problems:
        report.add("FAIL", "R3-VERBS", "; ".join(problems))
    else:
        report.add("PASS", "R3-VERBS", "no work-claiming or credit-narrating phrasing")

    # R4 — every named model's paper is linked, and all of them before any Ersilia link.
    ersilia_link = ERSILIA_LINK_RE.search(post)
    dois = [(e["identifier"], e["doi"]) for e in named if e["doi"]]
    absent = [ident for ident, doi in dois if doi.lower() not in folded]
    if not named:
        report.add("WARN", "R4-LINK-ORDER", "no models named; nothing to check")
    elif absent:
        report.add(
            "FAIL", "R4-LINK-ORDER",
            f"named without linking its paper: {', '.join(absent)}",
        )
    else:
        positions = [folded.find(doi.lower()) for _, doi in dois]
        last_doi = max(positions) if positions else -1
        if ersilia_link and last_doi >= 0 and ersilia_link.start() < last_doi:
            report.add(
                "FAIL", "R4-LINK-ORDER",
                f"an Ersilia link at char {ersilia_link.start()} precedes a paper link at "
                f"char {last_doi} — every paper comes first",
            )
        else:
            report.add("PASS", "R4-LINK-ORDER", f"{len(dois)} paper link(s), all before any Ersilia link")

    # R5 — length.
    length = len(post)
    if length > MAX_CHARS:
        report.add("FAIL", "R5-LENGTH", f"{length} chars exceeds LinkedIn's {MAX_CHARS} limit")
    elif not LENGTH_MIN <= length <= LENGTH_MAX:
        report.add(
            "WARN", "R5-LENGTH",
            f"{length} chars is outside the {LENGTH_MIN}–{LENGTH_MAX} round-up target",
        )
    else:
        report.add("PASS", "R5-LENGTH", f"{length} chars")

    # R6 — hashtags: a few, at the end.
    tags = HASHTAG_RE.findall(post)
    tail = post[-260:]
    if not 3 <= len(tags) <= 5:
        report.add("WARN", "R6-HASHTAGS", f"{len(tags)} hashtags; the house range is 3–5")
    elif any(f"#{t}" not in tail for t in tags):
        stray = [t for t in tags if f"#{t}" not in tail]
        report.add("WARN", "R6-HASHTAGS", f"hashtags not grouped at the end: {stray}")
    else:
        report.add("PASS", "R6-HASHTAGS", f"{len(tags)} hashtags, grouped at the end")

    # R7 — no @-mention that has not been confirmed by a human.
    mentions = MENTION_RE.findall(post)
    profiles = extract_section(draft_text, "Profiles to tag") or ""
    # Confirmation is per row, not per section: one confirmed row must not launder the
    # unverified rows sitting next to it in the same table.
    confirmed = set()
    for row in profiles.splitlines():
        lowered = row.lower()
        taggable = any(word in lowered for word in ("confirmed", "corroborated"))
        blocked = any(word in lowered for word in ("unverified", "ambiguous"))
        if taggable and not blocked:
            confirmed.update(m.lower() for m in MENTION_RE.findall(row))
    unverified = [m for m in mentions if m.lower() not in confirmed]
    if not mentions:
        report.add("PASS", "R7-HANDLES", "no @-mentions to verify")
    elif unverified:
        report.add(
            "FAIL", "R7-HANDLES",
            f"@-mentions with no confirmed/corroborated row in 'Profiles to tag': "
            f"{unverified}",
        )
    else:
        report.add("PASS", "R7-HANDLES", f"{len(mentions)} @-mentions, all confirmed")

    # R12 — the profile lookup is mandatory for whoever the post names.
    required = [e["first_author"] for e in named if e["first_author"]]
    if not profiles.strip():
        report.add(
            "FAIL", "R12-PROFILES",
            "no 'Profiles to tag' section — the author lookup is not optional",
        )
    else:
        profiles_folded = strip_accents(profiles).lower()
        stale = [ph for ph in PLACEHOLDERS if ph in profiles_folded]
        absent = [
            name
            for name in required
            if strip_accents(surname(name)).lower() not in profiles_folded
        ]
        if stale:
            report.add(
                "FAIL", "R12-PROFILES",
                f"placeholder rows left in the worksheet: {', '.join(repr(x) for x in stale)}"
                f" — look the author up and record the result, even if it is 'unverified'",
            )
        elif absent:
            report.add(
                "FAIL", "R12-PROFILES",
                f"no row for {', '.join(absent)} — every author the post names needs one",
            )
        else:
            # Report what the rows actually say. This rule can confirm a row exists; it
            # cannot confirm anyone looked, so it must not claim they did.
            tally = {}
            for status in ("confirmed", "corroborated", "ambiguous", "unverified"):
                hits = sum(
                    1
                    for row in profiles.splitlines()
                    if row.strip().startswith("|") and status in row.lower()
                )
                if hits:
                    tally[status] = hits
            breakdown = ", ".join(f"{n} {k}" for k, n in tally.items()) or "no status recorded"
            level = "WARN" if not tally or set(tally) <= {"unverified"} else "PASS"
            report.add(
                level, "R12-PROFILES",
                f"{len(required)} named author(s), all with a row — {breakdown}"
                + ("; none is taggable yet" if level == "WARN" else ""),
            )

    # R8 — LinkedIn renders no markdown, and pseudo-bold breaks screen readers.
    problems = []
    if MD_BOLD_RE.search(post):
        problems.append("markdown bold (**…**) posts literally")
    if MD_LINK_RE.search(post):
        problems.append("markdown links ([x](y)) post literally")
    if "`" in post:
        problems.append("backticks post literally")
    if has_unicode_pseudo_bold(post):
        problems.append("unicode pseudo-bold is unreadable to screen readers")
    if problems:
        report.add("FAIL", "R8-PLAIN-TEXT", "; ".join(problems))
    else:
        report.add("PASS", "R8-PLAIN-TEXT", "plain text throughout")

    # R10 — Ersilia's role is stated once, then dropped.
    prose_blocks = []
    for block in re.split(r"\n\s*\n", post):
        prose = FETCH_CMD_RE.sub(" ", URL_RE.sub(" ", block)).strip()
        if prose and SELF_REFERENCE_RE.search(prose):
            prose_blocks.append(" ".join(prose.split())[:70])
    if len(prose_blocks) <= MAX_ERSILIA_BLOCKS:
        report.add(
            "PASS", "R10-TWO-BLOCKS",
            f"{len(prose_blocks)} paragraph(s) mention Ersilia's role",
        )
    else:
        report.add(
            "FAIL", "R10-TWO-BLOCKS",
            f"{len(prose_blocks)} paragraphs discuss Ersilia; at most "
            f"{MAX_ERSILIA_BLOCKS} (the title and the announcement) may: "
            + " | ".join(f"{b}…" for b in prose_blocks),
        )

    # R11 — the Hub is named once. The title, the announcement and the enablement block
    # otherwise say "Ersilia Model Hub" three times over.
    hub_hits = len(HUB_PHRASE_RE.findall(post))
    if hub_hits == 1:
        report.add("PASS", "R11-NO-ECHO", "\"Ersilia Model Hub\" appears once")
    elif hub_hits == 0:
        report.add("WARN", "R11-NO-ECHO", "the post never names the Ersilia Model Hub")
    else:
        report.add(
            "FAIL", "R11-NO-ECHO",
            f"\"Ersilia Model Hub\" appears {hub_hits} times — name it once, then make the "
            f"later block about what the model now does, not where it lives",
        )

    # R9 — numbers need a provenance the linter cannot see.
    metrics = METRIC_RE.findall(post)
    if metrics:
        report.add(
            "WARN", "R9-CLAIMS",
            "post quotes figures — confirm each comes from the paper and that "
            "/model-incorporation-reproduce returned PASS",
        )
    else:
        report.add("PASS", "R9-CLAIMS", "no performance figures quoted")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("draft", help="draft markdown file with a '## Post' fenced block")
    parser.add_argument("--context", help="context JSON from fetch_model_context.py")
    args = parser.parse_args(argv)

    draft_text = Path(args.draft).read_text(encoding="utf-8")
    post = extract_post(draft_text)
    if post is None:
        print(
            "ERROR: no '## Post' section with a fenced block found in the draft",
            file=sys.stderr,
        )
        return 1

    context = read_json(args.context) if args.context else None
    if context is None:
        print("WARNING: no --context given; R1, R2 and R4 degrade to warnings", file=sys.stderr)

    print(f"Hook (first {HOOK_CHARS} chars, all LinkedIn shows before “see more”):")
    print("  " + post[:HOOK_CHARS].replace("\n", " ") + ("…" if len(post) > HOOK_CHARS else ""))
    print()

    report = Report()
    check(post, draft_text, context, report)
    return 1 if report.emit() else 0


if __name__ == "__main__":
    raise SystemExit(main())
