#!/usr/bin/env python3
"""check_html.py — score an HTML page against the Ersilia house style.

Report-only. Parses one HTML file, runs the checks catalogued in references/checks.md,
and writes a severity-tiered Markdown report (and optional findings JSON). It never edits
the page — every finding carries a concrete fix for a later pass.

    python check_html.py page.html                       # Markdown report to stdout
    python check_html.py page.html --json /tmp/f.json     # + machine-readable findings
    python check_html.py page.html --date 2026-07-31      # stamp the report (no datetime.now)

Guiding rule (shared with repository-auditing): a skipped check is never a pass. Anything
that could not be evaluated is listed under "Checks not run", not silently dropped.

Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys

from _common import (
    SEVERITIES,
    all_css,
    finding,
    non_brand_hexes,
    parse_html,
    read_text,
    skipped,
    write_json,
    FOREIGN_FONT_HINTS,
    ERSILIA_FONT_HINTS,
)

# Thresholds — deliberately loose; the point is to catch "populated, not sleek", not to
# nitpick a dense-but-intentional data page.
MAX_TOP_HEADINGS = 8      # more than this many h2s reads as an over-stuffed page
WALL_OF_TEXT_CHARS = 6000  # prose past this with no disclosure device is a wall
MAX_FLAT_ACCENTS = 4       # distinct accent hues used flat before it looks noisy
MAX_UPPERCASE_RULES = 2    # more text-transform:uppercase rules than this reads as shouty

_IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
_ALT_RE = re.compile(r"\balt\s*=", re.I)
_FONT_FAMILY_RE = re.compile(r"font-family\s*:", re.I)


def run_checks(html: str) -> tuple[list[dict], list[dict]]:
    doc = parse_html(html)
    css = all_css(doc)
    findings: list[dict] = []
    skips: list[dict] = []

    # -- T0: self-containment (external refs break the Artifact CSP) -------
    if doc.external_refs:
        offenders = ", ".join(f"{k}:{u}" for k, u in doc.external_refs[:8])
        findings.append(finding(
            "T0-SELF-CONTAINED", "T0", "Blocker",
            f"{len(doc.external_refs)} external reference(s) — the page is not self-contained.",
            "Inline every asset (CSS/JS in <style>/<script>, images/fonts as data: URIs). "
            "Artifacts block all external hosts via CSP, so these will silently fail to load.",
            detail=offenders,
        ))

    # -- T0: Ersilia attribution ------------------------------------------
    if "ersilia.io" not in html.lower():
        findings.append(finding(
            "T0-ATTRIBUTION", "T0", "Should-fix",
            "No Ersilia attribution — the page does not link ersilia.io.",
            "Add the canonical credit footer (assets/footer.html): "
            "'Brought to you by the Ersilia Open Source Initiative' linking https://ersilia.io.",
        ))

    # -- T1: off-brand colours --------------------------------------------
    if css.strip():
        bad = non_brand_hexes(css)
        if bad:
            findings.append(finding(
                "T1-COLOR-OFFBRAND", "T1", "Should-fix",
                f"{len(bad)} colour(s) outside the Ersilia palette.",
                "Replace with the design tokens in assets/ersilia.css (var(--plum), var(--brand), "
                "var(--ink), the data hues …). Do not hard-code new hex values.",
                detail=", ".join(bad[:16]) + (" …" if len(bad) > 16 else ""),
            ))
    else:
        skips.append(skipped("T1-COLOR-OFFBRAND", "no CSS found in the document"))

    # -- T1: foreign font stack -------------------------------------------
    if _FONT_FAMILY_RE.search(css):
        low = css.lower()
        has_ersilia = any(h in low for h in ERSILIA_FONT_HINTS)
        has_foreign = any(h in low for h in FOREIGN_FONT_HINTS)
        if has_foreign and not has_ersilia:
            findings.append(finding(
                "T1-FONT-FOREIGN", "T1", "Should-fix",
                "Font stack is not the Ersilia one (no Inter / mono family).",
                "Use var(--sans) and var(--mono) from ersilia.css. Inter for text, "
                "the mono stack for every number and the uppercase micro-labels.",
            ))
    else:
        skips.append(skipped("T1-FONT-FOREIGN", "page sets no font-family (inherits the theme)"))

    # -- T1: favicon -------------------------------------------------------
    if not doc.has_favicon:
        findings.append(finding(
            "T1-FAVICON", "T1", "Nice-to-have",
            "No favicon — the browser tab has no Ersilia mark.",
            "Add the inline-SVG favicon from assets/head.html (a plain plum circle).",
        ))

    # -- T1: clutter — too many top-level sections ------------------------
    h1s = [t for lvl, t in doc.headings if lvl == 1]
    h2s = [t for lvl, t in doc.headings if lvl == 2]
    if len(h2s) > MAX_TOP_HEADINGS:
        findings.append(finding(
            "T1-CLUTTER-SECTIONS", "T1", "Should-fix",
            f"{len(h2s)} top-level sections — the page is over-populated.",
            "Sleek beats complete. Merge or drop sections, and push detail behind progressive "
            "disclosure (a <details>, a hovertip, or a Methods modal). Aim for a ~30s scan.",
            detail="; ".join(h2s[:12]) + (" …" if len(h2s) > 12 else ""),
            confidence="medium",
        ))
    if len(h1s) > 1:
        findings.append(finding(
            "T1-MULTI-H1", "T1", "Nice-to-have",
            f"{len(h1s)} <h1> elements — a page should have one wordmark heading.",
            "Keep a single <h1> (the wordmark); demote the rest to <h2>/<h3>.",
            detail="; ".join(h1s[:8]),
        ))

    # -- T2: decorative emoji in headings ---------------------------------
    if doc.emoji_headings:
        findings.append(finding(
            "T2-EMOJI-HEADINGS", "T2", "Nice-to-have",
            f"{len(doc.emoji_headings)} heading(s) carry decorative emoji.",
            "Drop decorative emoji. Emoji are for status markers only (🟢/🔴), never chrome — "
            "the mono eyebrow label is the Ersilia way to tag a section.",
            detail="; ".join(doc.emoji_headings[:8]),
        ))

    # -- T2: wall of text without progressive disclosure ------------------
    has_disclosure = bool(re.search(r"<details\b|data-tip|hovertip|class=[\"'][^\"']*modal", html, re.I))
    if doc.text_len > WALL_OF_TEXT_CHARS and not has_disclosure:
        findings.append(finding(
            "T2-WALL-OF-TEXT", "T2", "Nice-to-have",
            f"~{doc.text_len:,} chars of prose with no progressive disclosure.",
            "Layer the detail: terse surface copy, with the depth behind a <details>, a hovertip "
            "(data-tip), or a Methods modal. Don't dump everything on the main view.",
            confidence="medium",
        ))

    # -- T2: accent sprawl -------------------------------------------------
    if css.strip():
        # Count distinct Ersilia data-hue vars used as flat backgrounds (rough proxy).
        hues = set(re.findall(r"var\(--(crimson|tangerine|amber|lime|turquoise|cobalt|orchid|fuchsia|purple|mint|blue|yellow|pink|orange)\)", css))
        if len(hues) > MAX_FLAT_ACCENTS:
            findings.append(finding(
                "T2-ACCENT-SPRAWL", "T2", "Nice-to-have",
                f"{len(hues)} accent hues in play — one calm accent reads sleeker.",
                "Let periwinkle (--brand) carry the interaction; reserve the data hues for encoding "
                "an actual variable (per-axis colour), not decoration.",
                detail=", ".join(sorted(hues)),
                confidence="medium",
            ))

    # -- T2: uppercase abuse ----------------------------------------------
    upper = len(re.findall(r"text-transform\s*:\s*uppercase", css, re.I))
    if upper > MAX_UPPERCASE_RULES:
        findings.append(finding(
            "T2-UPPERCASE", "T2", "Nice-to-have",
            f"{upper} uppercase rules — stacked uppercase labels read techy, not neutral.",
            "Prefer quiet sentence-case sans labels (the Ersilia eyebrow/section/table style). "
            "Reserve any uppercase for a single deliberate accent, not every micro-label.",
            confidence="medium",
        ))

    # -- T2: images without alt text --------------------------------------
    imgs = _IMG_RE.findall(html)
    no_alt = [t for t in imgs if not _ALT_RE.search(t)]
    if no_alt:
        findings.append(finding(
            "T2-IMG-ALT", "T2", "Nice-to-have",
            f"{len(no_alt)} of {len(imgs)} <img> tag(s) have no alt text.",
            "Add descriptive alt= to every image (empty alt='' only for pure decoration).",
        ))

    # -- T2: doctype / lang ------------------------------------------------
    if not doc.has_doctype:
        findings.append(finding(
            "T2-DOCTYPE", "T2", "Nice-to-have",
            "No <!doctype html> — the page may render in quirks mode.",
            "Start the document with <!doctype html>. apply_theme.py adds it automatically.",
        ))

    return findings, skips


# --------------------------------------------------------------------------------------
# Markdown report
# --------------------------------------------------------------------------------------

_TIER_TITLE = {
    "T0": "T0 · Identity & self-containment",
    "T1": "T1 · House style",
    "T2": "T2 · Polish & accessibility",
}


def render_report(path: str, findings: list[dict], skips: list[dict], date: str) -> str:
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in SEVERITIES}
    lines = [
        f"# HTML style check — `{path}`",
        "",
        f"_Checked {date}. Report-only — no changes were made._",
        "",
    ]
    if not findings:
        lines.append("**Verdict:** clean — the page matches the Ersilia house style. ✅")
    else:
        verdict = " · ".join(f"{counts[s]} {s.lower()}" for s in SEVERITIES if counts[s])
        lines.append(f"**Verdict:** {verdict}.")
    lines.append("")

    for tier in ("T0", "T1", "T2"):
        tf = [f for f in findings if f["tier"] == tier]
        if not tf:
            continue
        lines.append(f"## {_TIER_TITLE[tier]}")
        lines.append("")
        for f in tf:
            conf = "" if f.get("confidence", "high") == "high" else f" _(confidence: {f['confidence']})_"
            lines.append(f"- **[{f['id']}]** {f['summary']}{conf}")
            lines.append(f"  - _Fix:_ {f['fix']}")
            if f.get("detail"):
                lines.append(f"  - _Detail:_ {f['detail']}")
        lines.append("")

    lines.append("## Checks not run")
    lines.append("")
    if skips:
        for s in skips:
            lines.append(f"- **{s['id']}** — {s['reason']}")
    else:
        lines.append("_All checks ran._")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("html_file", help="HTML file to check")
    p.add_argument("--json", dest="json_out", help="also write findings JSON here")
    p.add_argument("--out", help="write the Markdown report here (default: stdout)")
    p.add_argument("--date", default="unknown", help="date to stamp on the report (YYYY-MM-DD)")
    args = p.parse_args(argv)

    html = read_text(args.html_file)
    if not html.strip():
        print(f"ERROR: could not read {args.html_file}", file=sys.stderr)
        return 2

    findings, skips = run_checks(html)
    report = render_report(args.html_file, findings, skips, args.date)

    if args.out:
        from pathlib import Path
        Path(args.out).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report + "\n")

    if args.json_out:
        write_json(args.json_out, {"file": args.html_file, "findings": findings, "skipped": skips})

    blockers = sum(1 for f in findings if f["severity"] == "Blocker")
    print(f"{args.html_file}: {len(findings)} findings ({blockers} blockers), {len(skips)} skipped",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
