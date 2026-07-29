#!/usr/bin/env python3
"""Merge the checker outputs into one tiered Markdown audit report.

Order is severity first (Blocker → Should-fix → Nice-to-have), because that is the order
someone will work in. Within a severity, findings group by tier so the aspirational Tier 2
items cannot be mistaken for actionable debt. Accepted deviations and skipped checks each
get their own section — a suppressed or unrun check is always visible, never silent.

Exit codes
----------
0   report written; no Blockers
1   report written; one or more Blockers
2   bad usage — no readable input documents

Usage
-----
    python render_report.py --target /tmp/repo_audit_target.json \\
        --findings /tmp/repo_audit_docs.json /tmp/repo_audit_code.json ... \\
        [--overrides /tmp/repo_audit_overrides.json] \\
        [--type Package] [--type-source airtable] [--date 2026-07-28] \\
        [--out <repo>/AUDIT.md]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import (
    SEVERITIES,
    SKILL_DIR,
    die,
    load_target,
    plural,
    read_json,
    read_text,
    warn,
    which_ruff,
)

# Checks a shell command can fix outright, mapped to that command. Only genuinely runnable
# commands belong here — an entry that is really prose ("replace the footer with …") would end
# up inside a ```bash block that fails when pasted, so those stay EDIT and keep their guidance
# in the finding's `fix` text.
#
# The ruff commands pass `--config $SKILL/...` deliberately. The findings were measured against
# the canonical config, so a bare `ruff check --fix .` would use the repo's own drifted config
# and fix something other than what the audit reported.
AUTOFIX = {
    "PKG-RUFF-CHECK-FAILS": "ruff check --fix --config $SKILL/references/canonical-ruff.toml .",
    "PKG-RUFF-FORMAT-DIRTY": "ruff format --config $SKILL/references/canonical-ruff.toml .",
    "PKG-UNUSED-IMPORT": (
        "ruff check --fix --select F401,F811 "
        "--config $SKILL/references/canonical-ruff.toml ."
    ),
    "PKG-UNUSED-VAR": (
        "ruff check --fix --select F841 --config $SKILL/references/canonical-ruff.toml ."
    ),
    "PKG-NO-RUFF-CONFIG": "cp $SKILL/references/canonical-ruff.toml ruff.toml",
    "PKG-RUFF-CONFIG-DRIFT": "cp $SKILL/references/canonical-ruff.toml ruff.toml",
    "T0-JUNK-TRACKED": "git rm --cached <paths>",
    "ANA-STALE-GITKEEP": "git rm <paths>",
    "PKG-UNTOUCHED-CORE": "git rm src/<package>/core.py",
}

# Checks nobody should action without a human deciding first: they change public API,
# rename things, throw work away, or need judgement about intent.
NEEDS_DECISION = {
    "T0-SECRETS",
    "T0-DATA-TRACKED",
    "T0-LARGE-FILE",
    "T0-REPO-NAME",
    "T0-DEFAULT-BRANCH",
    "PKG-DEAD-MODULE-NAME",
    "PKG-DEP-UNUSED",
    "PKG-DEP-UNDECLARED",
    "PKG-CLI-NOT-CLICK",
    "PKG-GOD-MODULE",
    "PKG-FLAT-NAMESPACE",
    "PKG-COMMENTED-CODE",
    "ANA-EXTRA-ROOT-DIR",
    "ANA-SCRIPT-NOT-NUMBERED",
    "T0-README-AI-TONE",
    "T0-H1-IS-NAME",
    "T0-H1-NOT-DESCRIPTIVE",
    "EOSVC-STALE-DECL",
}


def collect(paths: list[str]) -> tuple[list[dict], list[dict], dict]:
    """Read the checker documents. Returns (findings, skipped, meta)."""
    findings: list[dict] = []
    skips: list[dict] = []
    meta: dict = {}
    for p in paths:
        doc = read_json(p)
        if not isinstance(doc, dict):
            warn(f"could not read {p}; its checks are missing from this report")
            skips.append(
                {"id": Path(p).stem, "reason": f"checker output {p} unreadable"}
            )
            continue
        findings.extend(doc.get("findings") or [])
        skips.extend(doc.get("skipped") or [])
        for key in ("claudemd", "python_files", "ruff", "tracked_count"):
            if key in doc:
                meta[key] = doc[key]
    return findings, skips, meta


def apply_overrides(
    findings: list[dict], overrides: dict | None
) -> tuple[list[dict], list[dict]]:
    """Split findings into (reported, deviations) using the repo's own CLAUDE.md rules.

    An override needs a `check` id and a `quote` from the repo's CLAUDE.md justifying the
    divergence. Overrides without a quote are ignored — the whole point is that the
    suppression is traceable to something the repo actually wrote down.
    """
    if not overrides:
        return findings, []
    rules = overrides.get("overrides") or []
    by_check: dict[str, dict] = {}
    for rule in rules:
        cid = rule.get("check")
        quote = (rule.get("quote") or "").strip()
        if not cid or not quote:
            warn(f"ignoring override without a check id and a CLAUDE.md quote: {rule}")
            continue
        by_check[cid] = rule

    reported: list[dict] = []
    deviations: list[dict] = []
    for f in findings:
        rule = by_check.get(f["id"])
        if rule:
            deviations.append({**f, "_override": rule})
        else:
            reported.append(f)
    return reported, deviations


def sort_key(f: dict) -> tuple:
    """Severity, then tier, then check id — stable and readable."""
    return (
        SEVERITIES.index(f.get("severity", "Nice-to-have")),
        f.get("tier", "T2"),
        f.get("id", ""),
    )


MARKER = {
    "Blocker": "🔴",
    "Should-fix": "🟡",
    "Nice-to-have": "⚪",
}
APPENDIX_ITEMS = 15
PASS_MARKER = "✅"
NOTRUN_MARKER = "—"

# Check ID → area. Exact IDs, deliberately not prefix matching: a keyword mapper misfiled
# `PKG-DOCSTRING-*` under Documentation instead of Code quality, which is why this is a
# literal table. Anything unmapped lands in `Other` and warns, so a newly added check
# cannot silently vanish from the report.
AREA_OF = {
    # Template leftovers
    "T0-PLACEHOLDER": "Template leftovers",
    "PKG-PLACEHOLDER-PKG": "Template leftovers",
    "PKG-UNTOUCHED-CORE": "Template leftovers",
    # Hygiene & security
    "T0-SECRETS": "Hygiene & security",
    "T0-DATA-TRACKED": "Hygiene & security",
    "T0-LARGE-FILE": "Hygiene & security",
    "T0-JUNK-TRACKED": "Hygiene & security",
    "T0-GITIGNORE-MISSING": "Hygiene & security",
    "ANA-STALE-GITKEEP": "Hygiene & security",
    "ANA-DATA-NOT-IGNORED": "Hygiene & security",
    "ANA-NO-ACCESS-JSON": "Hygiene & security",
    "PKG-NO-ACCESS-JSON": "Hygiene & security",
    "ANA-ACCESS-JSON-MISMATCH": "Hygiene & security",
    "EOSVC-STALE-DECL": "Hygiene & security",
    "ANA-NOTEBOOK-OUTPUTS": "Hygiene & security",
    "AUT-HARDCODED-TOKEN": "Hygiene & security",
    # Documentation
    "T0-README-MISSING": "Documentation",
    "T0-README-STUB": "Documentation",
    "T0-LICENSE-MISSING": "Documentation",
    "T0-LICENSE-NOT-GPL": "Documentation",
    "T0-FOOTER-MISSING": "Documentation",
    "T0-FOOTER-DRIFT": "Documentation",
    "T0-FOOTER-NOT-LAST": "Documentation",
    "T0-LOGO-MISSING": "Documentation",
    "T0-LOGO-UNRESOLVED": "Documentation",
    "T0-CLAUDEMD-MISSING": "Documentation",
    "T0-CLAUDEMD-STALE": "Documentation",
    "T0-H1-IS-NAME": "Documentation",
    "T0-H1-MISSING": "Documentation",
    "T0-H1-NOT-DESCRIPTIVE": "Documentation",
    "T0-HEADING-LEVELS": "Documentation",
    "T0-BROKEN-LINK": "Documentation",
    "T0-BROKEN-EXTERNAL-LINK": "Documentation",
    "T0-README-AI-TONE": "Documentation",
    "T0-README-EMOJI": "Documentation",
    "T0-README-NO-PURPOSE": "Documentation",
    "T0-README-NO-ECOSYSTEM": "Documentation",
    "PKG-README-VERBOSE": "Documentation",
    "PKG-README-FILLER": "Documentation",
    "PKG-README-TODO": "Documentation",
    "PKG-DOCS-PROMISED-MISSING": "Documentation",
    "ANA-README-VERBOSE": "Documentation",
    "ANA-README-FOLDER-TREE": "Documentation",
    "ANA-REPORT-AT-ROOT": "Documentation",
    "ANA-DOC-NAMING": "Documentation",
    "ANA-EMPTY-DOC-DIR": "Documentation",
    "WSH-NO-AUDIENCE": "Documentation",
    "WSH-NO-DATE": "Documentation",
    "WSH-NO-LICENSE-STATEMENT": "Documentation",
    "DOC-BROKEN-NAV": "Documentation",
    "DOC-ORPHAN-PAGE": "Documentation",
    "T2-NO-CONTRIBUTING": "Documentation",
    "T2-NO-COC": "Documentation",
    "T2-NO-ISSUE-TEMPLATE": "Documentation",
    "T2-NO-PR-TEMPLATE": "Documentation",
    "T2-NO-CITATION": "Documentation",
    "T2-NO-CHANGELOG": "Documentation",
    "T2-NO-BANNER": "Documentation",
    "T2-NO-TOC": "Documentation",
    "T2-NO-DOCS-DIR": "Documentation",
    "T2-NO-DEPENDABOT": "Documentation",
    # Tests & CI
    "PKG-NO-TESTS": "Tests & CI",
    "PKG-NO-PYTEST-CONFIG": "Tests & CI",
    "PKG-NO-CI": "Tests & CI",
    "PKG-CI-NO-QUALITY": "Tests & CI",
    "AUT-NO-WORKFLOWS": "Tests & CI",
    # Code quality
    "PKG-RUFF-CHECK-FAILS": "Code quality",
    "PKG-RUFF-FORMAT-DIRTY": "Code quality",
    "PKG-SYNTAX-ERROR": "Code quality",
    "PKG-UNUSED-IMPORT": "Code quality",
    "PKG-UNUSED-VAR": "Code quality",
    "PKG-UNDEFINED-NAME": "Code quality",
    "PKG-DEAD-MODULE-NAME": "Code quality",
    "PKG-DOCSTRING-MISSING": "Code quality",
    "PKG-DOCSTRING-NOT-NUMPY": "Code quality",
    "PKG-NO-RUFF-CONFIG": "Code quality",
    "PKG-RUFF-CONFIG-DRIFT": "Code quality",
    "PKG-COMPETING-LINTERS": "Code quality",
    "PKG-NO-PRECOMMIT": "Code quality",
    "PKG-BARE-EXCEPT": "Code quality",
    "PKG-PRINT-IN-LIB": "Code quality",
    "PKG-ABSOLUTE-PATH": "Code quality",
    "PKG-SHELL-INJECTION": "Code quality",
    "PKG-WILDCARD-IMPORT": "Code quality",
    "PKG-MUTABLE-DEFAULT": "Code quality",
    "PKG-COMMENTED-CODE": "Code quality",
    "PKG-TODO-DENSITY": "Code quality",
    "PKG-BARE-LOGGER": "Code quality",
    "PKG-NO-LOGGER-SINGLETON": "Code quality",
    # Dependencies & packaging
    "PKG-NO-PYPROJECT": "Dependencies & packaging",
    "PKG-SETUP-PY": "Dependencies & packaging",
    "PKG-DEP-UNPINNED": "Dependencies & packaging",
    "PKG-DEV-DEP-UNPINNED": "Dependencies & packaging",
    "PKG-DEP-UNDECLARED": "Dependencies & packaging",
    "PKG-DEP-UNUSED": "Dependencies & packaging",
    "PKG-NO-REQUIRES-PYTHON": "Dependencies & packaging",
    "ANA-REQS-MISSING": "Dependencies & packaging",
    "ANA-REQS-EMPTY": "Dependencies & packaging",
    "ANA-REQS-UNPINNED": "Dependencies & packaging",
    # API & CLI
    "PKG-CLI-NOT-CLICK": "API & CLI",
    "PKG-CLI-NOT-TABLED": "API & CLI",
    "PKG-CLI-OPT-SEPARATOR": "API & CLI",
    "PKG-CLI-VERB-DIVERGENT": "API & CLI",
    "PKG-CLI-NO-SHORT-IO": "API & CLI",
    "PKG-CLI-IO-NAMING": "API & CLI",
    "PKG-CLI-INCONSISTENT": "API & CLI",
    # Modularity & structure
    "PKG-GOD-MODULE": "Modularity & structure",
    "PKG-LONG-FUNCTION": "Modularity & structure",
    "PKG-DEEP-NESTING": "Modularity & structure",
    "PKG-FLAT-NAMESPACE": "Modularity & structure",
    "T0-ROOT-CLUTTER": "Modularity & structure",
    "T0-NAMING-INCONSISTENT": "Modularity & structure",
    "ANA-EXTRA-ROOT-DIR": "Modularity & structure",
    # Releases
    "PKG-VERSION-MISMATCH": "Releases",
    "PKG-TAG-NOT-SEMVER": "Releases",
    "PKG-NO-RELEASE": "Releases",
    # Metadata & registry
    "T0-GH-DESC-MISSING": "Metadata & registry",
    "T0-GH-TOPICS-FEW": "Metadata & registry",
    "T0-DEFAULT-BRANCH": "Metadata & registry",
    "T0-REPO-NAME": "Metadata & registry",
    "T0-AIRTABLE-MISSING": "Metadata & registry",
    "T0-AIRTABLE-INCOMPLETE": "Metadata & registry",
    "T0-AIRTABLE-NO-PROJECT": "Metadata & registry",
    "T0-AIRTABLE-TYPE-MISMATCH": "Metadata & registry",
    # Analysis workflow
    "ANA-SCRIPT-NOT-NUMBERED": "Analysis workflow",
    "ANA-SCRIPT-NUMBER-GAP": "Analysis workflow",
    "ANA-OUTPUT-NUMBER-MISMATCH": "Analysis workflow",
    "ANA-BADGE-MISSING": "Analysis workflow",
    "ANA-BADGE-PENDING": "Analysis workflow",
    "ANA-NO-DEFAULT-PY": "Analysis workflow",
    "ANA-CONST-NOT-CAPS": "Analysis workflow",
    "ANA-NO-RANDOM-SEED": "Analysis workflow",
    "ANA-NO-SEED-SET": "Analysis workflow",
    "ANA-NO-SYSPATH-PREAMBLE": "Analysis workflow",
    "ANA-DIRS-IN-FUNCTION": "Analysis workflow",
    "ANA-NO-MAKEDIRS": "Analysis workflow",
    "ANA-MATPLOTLIB-NOT-STYLIA": "Analysis workflow",
    "ANA-NO-PROVENANCE": "Analysis workflow",
    # Automation & app
    "AUT-WORKFLOW-UNDOCUMENTED": "Automation & app",
    "AUT-ACTION-UNPINNED": "Automation & app",
    "AUT-SCHEDULE-UNDOCUMENTED": "Automation & app",
    "AUT-SECRETS-USED": "Automation & app",
    "APP-NO-ENTRYPOINT": "Automation & app",
    "APP-NO-RUN-DOCS": "Automation & app",
}

# Extra rows for the verdict table that are not areas: hand-run checks with no findings.
TRAIL_ROWS = [
    (
        "Airtable registry",
        (
            "T0-AIRTABLE-MISSING",
            "T0-AIRTABLE-INCOMPLETE",
            "T0-AIRTABLE-NO-PROJECT",
            "T0-AIRTABLE-TYPE-MISMATCH",
        ),
    ),
    ("External links", ("T0-BROKEN-EXTERNAL-LINK",)),
]


_WARNED_UNMAPPED: set[str] = set()


def area_of(check_id: str) -> str:
    """Area for a check ID, warning once when the ID is not in the table."""
    area = AREA_OF.get(check_id)
    if area is None:
        if check_id not in _WARNED_UNMAPPED:
            _WARNED_UNMAPPED.add(check_id)
            warn(f"{check_id} has no area in AREA_OF; filed under 'Other'")
        return "Other"
    return area


def area_state(findings: list[dict], skips: list[dict], area: str) -> tuple[str, str]:
    """The marker and a short state phrase for one area.

    The ✅ / — distinction is load-bearing and the easiest thing to get wrong in both
    directions. ✅ means *checks in this area ran and found nothing*. — means *nothing in
    this area was actually evaluated*. So — is only correct when **every** check the area
    owns appears in the skip list; an area with three skipped type-gated checks and eight
    that ran clean is ✅, not unchecked.

    Tier 2 findings are excluded, because the Findings section rolls them into one line
    rather than listing them per area — the table must count what the reader will see.
    """
    mine = [f for f in findings if area_of(f["id"]) == area and f.get("tier") != "T2"]
    if mine:
        worst = min(mine, key=_severity_rank)
        marker = MARKER[worst["severity"]]
        blockers = sum(1 for f in mine if f["severity"] == "Blocker")
        if blockers:
            others = len(mine) - blockers
            phrase = f"{blockers} blocker" + ("s" if blockers > 1 else "")
            if others:
                phrase += f", {others} other" + ("s" if others > 1 else "")
        else:
            phrase = f"{len(mine)} issue" + ("s" if len(mine) > 1 else "")
        return marker, phrase

    owned = {cid for cid, a in AREA_OF.items() if a == area}
    skipped_ids = {s.get("id", "") for s in skips}
    if owned and owned <= skipped_ids:
        return NOTRUN_MARKER, "not checked"
    if not owned:
        return NOTRUN_MARKER, "not checked"
    return PASS_MARKER, "clean"


def _severity_rank(f: dict) -> int:
    """Index of a finding's severity, for ordering."""
    return SEVERITIES.index(f.get("severity", "Nice-to-have"))


def _header(
    target: dict, rtype: str, type_source: str, date: str, meta: dict
) -> list[str]:
    """Title, provenance line, and the caveats that change how findings should be read."""
    name = target["name"]
    wt = target.get("worktree") or {}
    gh = target.get("github") or {}

    L = [f"# Audit — `{name}`", ""]
    L.append(
        f"{rtype} · {date} · `{wt.get('branch', '?')}@{wt.get('head', '?')}` · "
        f"{target.get('source', '?')} · type from {type_source}"
    )
    L.append("")

    caveats: list[str] = []
    if wt.get("dirty"):
        caveats.append(
            "Working tree has **uncommitted changes** — findings describe the tree on disk, "
            "not the default branch."
        )
    if wt.get("behind"):
        caveats.append(
            f"Checkout is **{wt['behind']} commit(s) behind** upstream; something here may "
            "already be fixed."
        )
    if gh.get("archived"):
        caveats.append(
            "Repository is **archived on GitHub** — weigh the effort accordingly."
        )
    if gh.get("is_template"):
        caveats.append(
            "**Template repository** — placeholder text is its purpose, so those checks are "
            "suppressed."
        )
    if meta.get("ruff") is False or (meta.get("ruff") is None and not which_ruff()):
        caveats.append(
            "**`ruff` was unavailable** — lint, formatting and docstring-presence checks did "
            "not run."
        )
    if (meta.get("claudemd") or {}).get("stale"):
        caveats.append(
            "`CLAUDE.md` is an inherited template, so it **grants no overrides**."
        )
    if caveats:
        L.append("> [!IMPORTANT]")
        L.extend(f"> {c}" for c in caveats)
        L.append("")
    return L


STAMP_RE = re.compile(r"<!-- checks-version: ([0-9-]+) -->")
PREV_ID_RE = re.compile(
    r"^- (?:🔴|🟡|⚪) (?:AUTO |EDIT |ASK )?`([A-Z0-9]+-[A-Z0-9-]+)`", re.M
)
PREV_DATE_RE = re.compile(r"^[A-Za-z]+ · (\d{4}-\d{2}-\d{2})", re.M)


def read_previous(path: Path) -> dict | None:
    """Parse the check IDs, date and checks-version out of an existing report.

    Only the Findings section is read: the Fix plan repeats the same IDs, and the audit trail
    lists IDs that were *not* findings, so scanning the whole file would count skipped checks
    as findings.
    """
    if not path.is_file():
        return None
    text = read_text(path)
    if "## Findings" not in text:
        return None
    body = text.split("## Findings", 1)[1].split("## Fix plan", 1)[0]
    stamp = STAMP_RE.search(text)
    date = PREV_DATE_RE.search(text)
    return {
        "ids": set(PREV_ID_RE.findall(body)),
        "stamp": stamp.group(1) if stamp else None,
        "date": date.group(1) if date else None,
    }


def checks_version() -> str:
    """The check set's version, from `references/_state.json`'s `last_refresh_date`."""
    state = read_json(str(SKILL_DIR / "references" / "_state.json")) or {}
    return str(state.get("last_refresh_date") or "unknown")


def _delta_line(
    previous: dict | None, findings: list[dict], skips: list[dict]
) -> str | None:
    """One line on what changed since the previous report, or None on a first run.

    Three buckets, not two, because "fixed" is a claim that is easy to get wrong:

    - **fixed** — the check ran again and no longer fires. Genuinely fixed.
    - **no longer checked** — it was skipped or gated this run, so its absence says nothing
      about the repo. Tier 2 was gated after the first reports were written, which alone would
      have shown 8 items as "fixed" when nothing had been fixed.
    - **new** — not in the previous report.

    When the previous report carries a different `checks-version`, or none at all, the check
    set itself may have moved and the word "fixed" is dropped entirely.
    """
    if not previous or not previous["ids"]:
        return None
    # Tier 2 is excluded on both sides. Its findings are rolled up into a single line with no
    # recoverable IDs, so the parser cannot see them in the previous report and every T2 item
    # would read as "new" on every run. It is also gated and aspirational, so churn there is
    # noise rather than progress.
    now = {f["id"] for f in findings if f.get("tier") != "T2"}
    gone = previous["ids"] - now
    skipped_now = {s.get("id", "") for s in skips}
    no_longer_checked = gone & skipped_now
    fixed = gone - no_longer_checked
    new = now - previous["ids"]
    unchanged = previous["ids"] & now

    same_checks = previous["stamp"] == checks_version()
    when = (
        f"the {previous['date']} audit"
        if previous.get("date")
        else "the previous audit"
    )

    parts: list[str] = []
    if same_checks:
        if fixed:
            parts.append(f"**{len(fixed)} fixed**")
    elif fixed:
        parts.append(f"**{len(fixed)} no longer reported**")
    if no_longer_checked:
        parts.append(f"{len(no_longer_checked)} no longer checked")
    if new:
        parts.append(f"{len(new)} new")
    if unchanged:
        parts.append(f"{len(unchanged)} unchanged")
    if not parts:
        return None

    caveat = "" if same_checks else " (different check set — comparison is indicative)"
    return f"Since {when}{caveat}: " + ", ".join(parts) + "."


def _verdict(
    verdict: str,
    start_here: list[str],
    findings: list[dict],
    skips: list[dict],
    verified: list[dict],
    fix_plan: list[tuple[str, dict]],
    rtype: str,
    delta: str | None = None,
) -> list[str]:
    """Prose verdict, the area status table, and the top three things to do."""
    L = ["## Verdict", ""]
    if delta:
        L.append(delta)
        L.append("")
    if verdict:
        L.append(verdict.strip())
        L.append("")

    # An area with findings is always shown — type gating decides only what happens to the
    # *empty* ones. Filtering a populated area out of the table would hide findings the
    # Findings section goes on to list, which is worse than either marker.
    with_findings = {area_of(f["id"]) for f in findings if f.get("tier") != "T2"}
    relevant = set(with_findings)
    skipped_ids = {s.get("id", "") for s in skips}
    for area in AREA_ORDER:
        if area in relevant or not area_applies(area, rtype):
            continue
        owned = {cid for cid, a in AREA_OF.items() if a == area}
        if owned and not (owned <= skipped_ids):
            relevant.add(area)  # something in here ran and found nothing
    ordered = [a for a in AREA_ORDER if a in relevant] + sorted(
        with_findings - set(AREA_ORDER)
    )

    rows = [(area, *area_state(findings, skips, area)) for area in ordered]

    # Hand-run checks with no findings: show them as verified rather than omitting them.
    verified_ids = {v.get("id") for v in verified}
    for label, ids in TRAIL_ROWS:
        if any(area_of(f["id"]) == label for f in findings):
            continue
        if verified_ids & set(ids):
            rows.append((label, PASS_MARKER, "verified"))
        elif any(s.get("id") in ids for s in skips):
            rows.append((label, NOTRUN_MARKER, "not checked"))

    if rows:
        width = max(len(r[0]) for r in rows)
        L.append(f"| {'Area'.ljust(width)} | State |")
        L.append(f"|{'-' * (width + 2)}|-------|")
        for area, marker, phrase in rows:
            text = f"{marker} {phrase}".strip()
            L.append(f"| {area.ljust(width)} | {text} |")
        L.append("")

    if not start_here:
        start_here = [f"`{f['id']}`" for _, f in fix_plan[:3]]
    if start_here:
        L.append(
            "**Start here:** "
            + " · ".join(f"{i}. {s}" for i, s in enumerate(start_here, start=1))
        )
        L.append("")
    return L


def evidence_items(f: dict) -> list[str]:
    """Split a finding's evidence into its individual items.

    Checkers build `detail` with `rollup()` (comma-joined) or by joining with `; `. Split on
    whichever separator the value actually uses, so items stay whole.
    """
    detail = (f.get("detail") or "").strip()
    if not detail:
        return []
    if ";" in detail:
        return [p.strip() for p in detail.split(";") if p.strip()]
    if "`, `" in detail:
        return [p.strip() for p in detail.split(", ") if p.strip()]
    return [detail]


def _finding_line(f: dict, tag: str = "") -> str:
    """One finding as a single line: what is wrong, where, and what kind of work it is.

    Carries no fix text — that is the Fix plan's job. Evidence is teased at most two items
    and always cut **at an item boundary**: an earlier version truncated on a character
    budget and produced `docs/api.md, docs/cli.md, docs/conc…`, silently discarding two
    filenames a fixer needed. Anything trimmed here is recoverable in full from the Evidence
    appendix.
    """
    summary = f["summary"].rstrip(".")
    bits = [MARKER[f.get("severity", "Nice-to-have")]]
    if tag:
        bits.append(tag)
    bits += [f"`{f['id']}`", summary]
    line = " ".join(bits)
    if f.get("file"):
        loc = f["file"] + (f":{f['line']}" if f.get("line") else "")
        line += f" — `{loc}`"

    items = evidence_items(f)
    if items:
        shown, rest = items[:2], len(items) - 2
        teaser = "; ".join(shown)
        if rest > 0:
            teaser += f" (+{rest} more, see Evidence)"
        # Only attach the teaser if the whole thing fits; a lone "(+5 more)" says nothing
        # the appendix does not say better.
        if len(line) + len(teaser) + 3 <= 168:
            line += f" — {teaser}"
        elif rest >= 0:
            # No number here. The summary usually carries its own count ("56 public classes
            # and methods…") and the evidence list is capped, so "40 items" beside "56" reads
            # as a contradiction rather than a detail.
            line += " — full list in Evidence"

    if f.get("confidence", "high") != "high":
        line += f" ({f['confidence']})"
    if f.get("downgraded_from"):
        line += f" [was {f['downgraded_from']}: {f.get('downgrade_reason', '?')}]"
    return f"- {line}"


# How each Tier 2 item reads inside an "add …" sentence. A literal table, for the same reason
# AREA_OF is one: deriving this by slicing the finding's summary produced "add a The README has
# no banner logo or badge row under the title" the first time a summary did not happen to start
# with "There is no".
TIER2_LABEL = {
    "T2-NO-CONTRIBUTING": "a `CONTRIBUTING.md`",
    "T2-NO-COC": "a `CODE_OF_CONDUCT.md`",
    "T2-NO-ISSUE-TEMPLATE": "an issue template",
    "T2-NO-PR-TEMPLATE": "a pull-request template",
    "T2-NO-DEPENDABOT": "a dependabot config",
    "T2-NO-CITATION": "a `CITATION.cff`",
    "T2-NO-CHANGELOG": "a `CHANGELOG.md`",
    "T2-NO-DOCS-DIR": "a `docs/` directory",
    "T2-NO-BANNER": "a banner or badge row",
    "T2-NO-TOC": "a table of contents",
}


def _tier2_name(f: dict) -> str:
    """Tier 2 item as it should read in an "add …" sentence."""
    label = TIER2_LABEL.get(f["id"])
    if label:
        return label
    warn(f"{f['id']} has no TIER2_LABEL; falling back to its summary")
    return f["summary"].removeprefix("There is no ").rstrip(".")


def _evidence_appendix(findings: list[dict]) -> list[str]:
    """Evidence for every finding that has more than fits on its line.

    Exists so the Findings section can stay scannable without the report losing information.
    Findings whose evidence fits inline are not repeated here. Where a checker capped its own
    list the cap is visible as a trailing `(+N more)`, so the section never implies it is
    showing everything when it is not.
    """
    withheld = [f for f in findings if len(evidence_items(f)) > 2]
    # Bounded on purpose. Uncapped, `ersilia` produced a 504-line AUDIT.md — 386 of it
    # appendix — which is a lot of file to leave in someone's repo root, from a skill that
    # flags verbose docs. Fifteen concrete examples plus an accurate total is enough to start
    # work, and saying "…and N more" keeps the loss explicit rather than silent, which was the
    # whole problem with the old mid-string truncation.
    if not withheld:
        return []
    L = [
        "## Evidence",
        "",
        f"<details><summary>evidence for {plural(len(withheld), 'finding')}</summary>",
        "",
    ]
    for f in sorted(withheld, key=lambda x: (_severity_rank(x), x["id"])):
        L.append(f"**{f['id']}** — {f['summary'].rstrip('.')}")
        L.append("")
        items = evidence_items(f)
        for item in items[:APPENDIX_ITEMS]:
            L.append(f"- {item}")
        if len(items) > APPENDIX_ITEMS:
            L.append(
                f"- …and {len(items) - APPENDIX_ITEMS} more — re-run the checker for the "
                "full list"
            )
        L.append("")
    L.append("</details>")
    L.append("")
    return L


def _findings_by_area(findings: list[dict], tags: dict[str, str]) -> list[str]:
    """Findings grouped by area, one line each, worst area first.

    `tags` comes from `build_fix_plan()` so the work tag shown here is the same one the Fix
    plan uses — they cannot drift apart.
    """
    if not findings:
        return ["## Findings", "", "None. Every check that ran passed.", ""]

    tier2 = [f for f in findings if f.get("tier") == "T2"]
    rest = [f for f in findings if f.get("tier") != "T2"]

    by_area: dict[str, list[dict]] = {}
    for f in rest:
        by_area.setdefault(area_of(f["id"]), []).append(f)

    def area_key(item: tuple[str, list[dict]]) -> tuple[int, int]:
        area, fs = item
        return (min(_severity_rank(f) for f in fs), -len(fs))

    L = ["## Findings", ""]
    for area, fs in sorted(by_area.items(), key=area_key):
        L.append(f"### {area} ({len(fs)})")
        for f in sorted(fs, key=lambda x: (_severity_rank(x), x["id"])):
            L.append(_finding_line(f, tags.get(f["id"], "")))
        L.append("")

    if tier2:
        missing = []
        for f in sorted(tier2, key=lambda x: x["id"]):
            # "There is no CONTRIBUTING.md." -> "CONTRIBUTING.md"
            missing.append(_tier2_name(f))
        L.append(
            f"{MARKER['Nice-to-have']} **Tier 2**, if you want the flagship bar: add "
            + ", ".join(missing)
            + "."
        )
        L.append("")
    return L


def build_fix_plan(findings: list[dict]) -> list[tuple[str, dict]]:
    """Order the actionable findings and tag each AUTO / EDIT / ASK.

    Blockers lead regardless of tag — burying the one must-fix item among twenty routine
    edits defeats the purpose. Within that, AUTO first (cheap and safe), then EDIT, then
    ASK.
    """
    actionable = [
        f
        for f in findings
        if f.get("severity") != "Nice-to-have" or f.get("tier") != "T2"
    ]

    def tag(f: dict) -> str:
        if f["id"] in AUTOFIX:
            return "AUTO"
        if f["id"] in NEEDS_DECISION:
            return "ASK"
        return "EDIT"

    order = {"AUTO": 0, "EDIT": 1, "ASK": 2}
    tagged = [(tag(f), f) for f in actionable]
    tagged.sort(
        key=lambda tf: (
            0 if tf[1].get("severity") == "Blocker" else 1,
            order[tf[0]],
            _severity_rank(tf[1]),
            tf[1]["id"],
        )
    )
    return tagged


def _short_fix(fix: str, budget: int = 105) -> str:
    """First actionable sentence of a fix, capped so checklist lines stay one line.

    The full rationale stays in `references/checks.md`; the checklist only needs the
    instruction. Without this the fix prose pushed lines past 260 characters.
    """
    first = fix.splitlines()[0].strip()
    # Cut at the first sentence break that leaves something useful behind. Skip breaks that
    # are really abbreviations — splitting on ". " alone produced the dangling
    # "Add topics so the repo is discoverable — e.g." in an earlier report.
    for stop in (". ", "; "):
        head = first.split(stop)[0]
        if not (20 <= len(head) < len(first)):
            continue
        if re.search(r"\b(e\.g|i\.e|etc|vs|cf|Dr|Mr|approx|no)$", head, re.IGNORECASE):
            continue
        first = head.rstrip(".") + "."
        break
    if len(first) > budget:
        first = _truncate_words(first, budget)
    return first


def _truncate_words(text: str, budget: int) -> str:
    """Truncate at a word boundary, never inside a backtick span.

    Two failure modes, both of which shipped before this existed. Cutting mid-word gave
    "mirroring `ersilia`'s `tests_and_c…". Cutting inside a code span gave "and `pytest…",
    an unbalanced backtick — which makes Markdown render the whole rest of the line as code.
    So after cutting on whitespace, if the backtick count is odd, fall back to before the
    span that was left open.
    """
    cut = text[:budget].rsplit(" ", 1)[0].rstrip(" ,;:—-")
    # An odd number of backticks means a code span was left open. Drop back to before the
    # opener. Never strip a *closing* backtick — doing that was itself the source of the
    # imbalance in an earlier attempt.
    if cut.count("`") % 2:
        cut = cut[: cut.rfind("`")].rstrip(" ,;:—-")
    return (cut or text[:budget]) + "…"


def _auto_block(fix_plan: list[tuple[str, dict]]) -> list[str]:
    """The AUTO fixes as one runnable `bash` block.

    The point of the report is to be the input to a fixing session, and the cheapest way to
    shrink it is to run the mechanical fixes first. Making that a single paste — rather than
    commands scattered as continuation lines under a checklist — is most of the value.

    `$SKILL` is declared once at the top of the block so the commands stay readable rather
    than carrying an absolute path each. Entries that still contain a `<placeholder>` are
    commented out with their check id, because pasting them unedited would do the wrong thing.
    """
    autos = [(tag, f) for tag, f in fix_plan if tag == "AUTO"]
    if not autos:
        return []
    lines: list[str] = []
    for _, f in autos:
        cmd = AUTOFIX[f["id"]]
        if "<" in cmd:
            lines.append(f"# {f['id']}: {cmd}   # fill in the placeholder first")
        else:
            lines.append(cmd)
    # Duplicate commands (two findings, one `ruff check --fix`) collapse to one.
    seen: set[str] = set()
    ordered = [c for c in lines if not (c in seen or seen.add(c))]
    needs_skill = any("$SKILL" in c for c in ordered)
    preamble = [f'SKILL="{SKILL_DIR}"', ""] if needs_skill else []
    return [
        "Mechanical first — safe, reviewable in one diff, and it shrinks the rest:",
        "",
        "```bash",
        *preamble,
        *ordered,
        "```",
        "",
    ]


def _fix_plan(fix_plan: list[tuple[str, dict]], tier2: list[dict]) -> list[str]:
    """The agent-facing checklist. Says what to do; assumes Findings said what is wrong."""
    if not fix_plan and not tier2:
        return []
    L = ["## Fix plan", ""]
    L += _auto_block(fix_plan)
    if any(tag != "AUTO" for tag, _ in fix_plan):
        L.append("Then, in order:")
        L.append("")
    for tag, f in fix_plan:
        loc = ""
        if f.get("file"):
            loc = f" `{f['file']}" + (f":{f['line']}" if f.get("line") else "") + "`"
        first = _short_fix(f["fix"])
        note = " **blocker**" if f.get("severity") == "Blocker" else ""
        L.append(f"- [ ] {tag} `{f['id']}`{loc}{note} — {first}")
    if tier2:
        names = ", ".join(_tier2_name(f) for f in sorted(tier2, key=lambda x: x["id"]))
        L.append(f"- [ ] OPT `Tier 2` only if you want the flagship bar — add {names}")
    L.append("")
    return L


def _audit_trail(
    deviations: list[dict], verified: list[dict], skips: list[dict]
) -> list[str]:
    """Everything a reader needs to trust the report, collapsed out of the way."""
    counts = " · ".join(
        [
            f"{len(verified)} verified by hand",
            f"{plural(len(deviations), 'accepted deviation')}",
            f"{plural(len(skips), 'check')} not run",
        ]
    )
    L = ["## Audit trail", "", f"<details><summary>{counts}</summary>", ""]

    if verified:
        L.append(
            "**Verified by hand** — checks with no script behind them, confirmed passing."
        )
        L.append("")
        for v in verified:
            note = v.get("note", "")
            L.append(f"- `{v.get('id', '?')}`" + (f" — {note}" if note else ""))
        L.append("")

    if deviations:
        L.append(
            "**Accepted deviations** — suppressed because this repository's own `CLAUDE.md` "
            "says otherwise. Listed so the suppression is auditable."
        )
        L.append("")
        for f in sorted(deviations, key=lambda x: x["id"]):
            rule = f.get("_override") or {}
            L.append(f"- `{f['id']}` {f['summary']}")
            L.append(f'  - CLAUDE.md says: "{rule.get("quote", "").strip()}"')
            if rule.get("note"):
                L.append(f"  - {rule['note']}")
        L.append("")

    if skips:
        L.append(
            "**Not run** — listed so an absent finding is never mistaken for a pass."
        )
        L.append("")
        # Group by reason, not by id. Five type-gated checks sharing one sentence produced
        # five identical lines; the reason is the information, the ids are the detail.
        by_reason: dict[str, list[str]] = {}
        for s in skips:
            reason = s.get("reason", "no reason recorded")
            cid = s.get("id", "?")
            if cid not in by_reason.setdefault(reason, []):
                by_reason[reason].append(cid)
        for reason, ids in sorted(
            by_reason.items(), key=lambda kv: (-len(kv[1]), kv[0])
        ):
            names = ", ".join(f"`{i}`" for i in sorted(ids))
            L.append(f"- {names} — {reason}")
        L.append("")

    L.append("</details>")
    L.append("")
    return L


AREA_ORDER = [
    "Template leftovers",
    "Hygiene & security",
    "Documentation",
    "Tests & CI",
    "Code quality",
    "Dependencies & packaging",
    "API & CLI",
    "Modularity & structure",
    "Releases",
    "Metadata & registry",
    "Analysis workflow",
    "Automation & app",
    "Other",
]

# Which repository types each area is actually evaluated for. This mirrors the type gating
# inside the checkers and exists because they emit a *representative* skip for a gated group
# rather than one skip per check — so "was every check in this area skipped?" cannot be
# answered from the skip list alone.
#
# Without this table an App repo showed "Tests & CI ✅ clean" when no test check had run at
# all: check_code only calls check_tests for Package and Template. That is precisely the
# false pass the ✅ marker must never produce, so an area that does not apply to the type is
# left out of the table entirely rather than marked either way.
ALL_TYPES = frozenset(
    {
        "Package",
        "Analysis",
        "Automation",
        "App",
        "Workshop",
        "Documentation",
        "Template",
    }
)
PYTHON_TYPES = frozenset({"Package", "Analysis", "Template"})
AREA_TYPES = {
    "Template leftovers": frozenset({"Package", "Template"}),
    "Hygiene & security": ALL_TYPES,
    "Documentation": ALL_TYPES,
    "Tests & CI": frozenset({"Package", "Automation"}),
    "Code quality": PYTHON_TYPES,
    "Dependencies & packaging": PYTHON_TYPES,
    "API & CLI": frozenset({"Package", "Template"}),
    "Modularity & structure": ALL_TYPES,
    "Releases": frozenset({"Package"}),
    "Metadata & registry": ALL_TYPES,
    "Analysis workflow": frozenset({"Analysis"}),
    "Automation & app": frozenset({"Automation", "App"}),
    "Other": ALL_TYPES,
}


def area_applies(area: str, rtype: str) -> bool:
    """True if `area` is meaningful for a repository of this type."""
    allowed = AREA_TYPES.get(area)
    return allowed is None or rtype in allowed


def render(
    target: dict,
    rtype: str,
    type_source: str,
    findings: list[dict],
    deviations: list[dict],
    skips: list[dict],
    verified: list[dict],
    meta: dict,
    date: str,
    verdict: str = "",
    start_here: list[str] | None = None,
    delta: str | None = None,
) -> tuple[str, dict]:
    """Build the report. Returns (markdown, counts_by_severity)."""
    counts = {s: sum(1 for f in findings if f.get("severity") == s) for s in SEVERITIES}
    tier2 = [f for f in findings if f.get("tier") == "T2"]
    plan = build_fix_plan(findings)

    L: list[str] = []
    L += _header(target, rtype, type_source, date, meta)
    L += _verdict(
        verdict, list(start_here or []), findings, skips, verified, plan, rtype, delta
    )
    tags = {f["id"]: tag for tag, f in plan}
    L += _findings_by_area(findings, tags)
    L += _fix_plan(plan, tier2)
    L += _evidence_appendix(findings)
    L += _audit_trail(deviations, verified, skips)

    L.append(
        f"Nothing in `{target['name']}` was changed. Findings say what is wrong; the fix plan "
        "says what to do. The standard is versioned in "
        "`skills/repository-auditing/references/`."
    )
    L.append("")
    # Lets the next run tell a genuine fix from a check that was removed or gated out.
    L.append(f"<!-- checks-version: {checks_version()} -->")
    L.append("")
    return "\n".join(L), counts


def main() -> int:
    """Merge the checker outputs and write the report."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="/tmp/repo_audit_target.json")
    ap.add_argument("--findings", nargs="+", required=True)
    ap.add_argument(
        "--overrides", default="", help="path to the accepted-deviations document"
    )
    ap.add_argument(
        "--verified",
        default="",
        help="path to a JSON document listing LLM-performed checks that passed, as "
        '{"verified": [{"id": ..., "note": ...}]}. Without it, a hand-run check that '
        "passes leaves no trace in the report.",
    )
    ap.add_argument("--type", default="Package")
    ap.add_argument("--type-source", default="inferred")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD, from the session date")
    ap.add_argument(
        "--verdict",
        default="",
        help="path to a file holding the 1-3 sentence verdict, or `-` to read stdin. Written "
        "by the LLM after reading the repo; omitted from the report if not supplied. Never "
        "synthesised.",
    )
    ap.add_argument(
        "--start-here",
        action="append",
        default=[],
        metavar="STEP",
        help="repeatable; the top things to do, in order. Falls back to the first three "
        "fix-plan entries.",
    )
    ap.add_argument(
        "--out",
        default="",
        help="report path; defaults to AUDIT.md at the root of the audited repository. "
        "Confirm the location with the user before running.",
    )
    args = ap.parse_args()

    target = load_target(args.target)
    findings, skips, meta = collect(args.findings)
    if not findings and not skips:
        die("no findings and no skipped checks were read; the checkers did not run")

    overrides = read_json(args.overrides) if args.overrides else None
    reported, deviations = apply_overrides(findings, overrides)

    verified_doc = read_json(args.verified) if args.verified else None
    verified = (verified_doc or {}).get("verified") or []

    verdict = ""
    if args.verdict == "-":
        verdict = sys.stdin.read()
    elif args.verdict:
        verdict = read_text(args.verdict)
        if not verdict.strip():
            warn(f"{args.verdict} is empty; the report will have no verdict prose")

    out_path = (
        Path(args.out).expanduser() if args.out else Path(target["path"]) / "AUDIT.md"
    )
    delta = _delta_line(read_previous(out_path), reported, skips)

    text, counts = render(
        target,
        args.type,
        args.type_source,
        reported,
        deviations,
        skips,
        verified,
        meta,
        args.date,
        verdict=verdict,
        start_here=args.start_here,
        delta=delta,
    )

    # Default is AUDIT.md at the root of the audited repository. The SKILL requires the
    # location to be confirmed with the user first, because this is the one file the skill
    # writes outside its own directory — it will show up in the repo's `git status`.
    out = out_path
    existed = out.exists()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    print(f"{out}{' (overwrote previous)' if existed else ''}")
    print(
        f"{counts['Blocker']} blocker(s), {counts['Should-fix']} should-fix, "
        f"{counts['Nice-to-have']} nice-to-have, {len(deviations)} accepted deviation(s), "
        f"{len(skips)} check(s) not run"
    )
    for f in sorted((f for f in reported if f["severity"] == "Blocker"), key=sort_key):
        where = f" ({f['file']})" if f.get("file") else ""
        print(f"  BLOCKER {f['id']}{where}: {f['summary']}")
    return 1 if counts["Blocker"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
