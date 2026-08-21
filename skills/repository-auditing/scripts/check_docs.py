#!/usr/bin/env python3
"""Documentation checks: README, About-Ersilia footer, LICENSE, CLAUDE.md, links.

Covers the Tier 0 documentation checks plus the README-shape checks whose thresholds
depend on the repository type. Everything here is static text analysis — judgement calls
about verbosity and filler are left to the LLM pass, which reads the same README.

Exit codes
----------
0   ran to completion (findings are in the output document, not the exit code)
2   bad usage or unreadable target

Usage
-----
    python check_docs.py --target /tmp/repo_audit_target.json \\
                         [--type Package] [--out /tmp/repo_audit_docs.json]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import (
    emit,
    finding,
    first_line,
    is_template_repo,
    load_target,
    non_blank_lines,
    normalise_prose,
    plural,
    read_text,
    rollup,
    skipped,
    tracked_files,
    verb,
)

# --------------------------------------------------------------------------------------
# Canonical text
# --------------------------------------------------------------------------------------

CANONICAL_ABOUT = (
    "The [Ersilia Open Source Initiative](https://ersilia.io) is a tech-nonprofit "
    "organization fueling sustainable research in the Global South. Ersilia's main asset "
    "is the [Ersilia Model Hub](https://github.com/ersilia-os/ersilia), an open-source "
    "repository of AI/ML models for antimicrobial drug discovery."
)

FOOTER_HEADINGS = (
    "about the ersilia open source initiative",
    "about us",
    "about ersilia",
)
CANONICAL_HEADING = "About the Ersilia Open Source Initiative"

# README length ceilings, per the type profiles. Package: "a screen or two".
# Analysis: "~50 lines" — 60 leaves headroom.
README_MAX = {
    "Package": 250,
    "Analysis": 60,
    "Automation": 160,
    "App": 160,
    "Workshop": 200,
    "Documentation": 200,
    "Template": 120,
}

# Text that only exists because a template was never adapted.
PLACEHOLDERS = [
    ("my_package", "the templated package folder name"),
    ("my-package", "the templated distribution name"),
    ("Your Name", "the templated author name"),
    ("you@ersilia.io", "the templated author email"),
    ("A short description of my package", "the templated project description"),
    ("My Ersilia Python Package", "the templated README title"),
]

# Verbatim markers that mean a CLAUDE.md was inherited and never adapted.
CLAUDEMD_STALE_MARKERS = [
    "This is an Ersilia Python package template",
    "This is the developer guide for a Python package built from the Ersilia Open Source "
    "Initiative's package template",
    "src/my_package/",
    "# Ersilia Python Package — Developer Guide",
]

# Files that legitimately live at the repo root rather than in docs/.
ROOT_DOC_ALLOWLIST = {
    "README.md",
    # This skill's own output, when written to the repo root.
    "AUDIT.md",
    "CLAUDE.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "SECURITY.md",
    "SUMMARY.md",
    "LICENSE.md",
    "CITATION.md",
    "TODO.md",
}

MD_LINK_RE = re.compile(
    r"(?<!\\)!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)"
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
IMAGE_RE = re.compile(
    r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?[^)]*\)|<img[^>]+src=[\"']([^\"']+)[\"']"
)
HTML_HEADING_RE = re.compile(r"<(h[12])\b[^>]*>", re.IGNORECASE)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def headings(text: str) -> list[tuple[int, str, int]]:
    """Extract `(level, title, line_no)` for every ATX heading outside fenced code."""
    out: list[tuple[int, str, int]] = []
    fenced = False
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = HEADING_RE.match(line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip(), i))
    return out


def find_footer(text: str) -> tuple[int, str, int] | None:
    """Locate the About-Ersilia heading. Returns `(level, title, line_no)` or None."""
    for level, title, line_no in headings(text):
        cleaned = re.sub(r"[^a-z ]", "", title.lower()).strip()
        if cleaned in FOOTER_HEADINGS:
            return level, title, line_no
    return None


def section_body(text: str, start_line: int, level: int) -> str:
    """Text of the section starting at `start_line`, up to the next heading of <= level."""
    lines = text.splitlines()
    body: list[str] = []
    for line in lines[start_line:]:
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) <= level:
            break
        body.append(line)
    return "\n".join(body)


def looks_like_name(title: str, repo_name: str) -> bool:
    """True if a README H1 is just the repo or package name.

    The template rule is explicit: *"a package named `lazy-qsar` should not have
    `# lazy-qsar` at the top"*. Normalise separators and case so `Zaira Chem`,
    `zaira-chem` and `zairachem` all count as the same string.
    """

    def squash(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.lower())

    t, n = squash(title), squash(repo_name)
    if not t or not n:
        return False
    if t == n:
        return True
    # `# Ersilia Pack` for repo `ersilia-pack`, or a name plus one decorative word.
    return t.startswith(n) and len(t) - len(n) <= 3


def resolve_link(repo: Path, doc_path: Path, target: str) -> bool:
    """True if a relative Markdown link target exists on disk."""
    target = target.split("#", 1)[0].strip()
    if not target:
        return True  # pure anchor
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith(
        "//"
    ):
        return True  # external or protocol-relative
    base = repo if target.startswith("/") else doc_path.parent
    candidate = (base / target.lstrip("/")).resolve()
    try:
        candidate.relative_to(repo.resolve())
    except ValueError:
        return True  # escapes the repo; not ours to judge
    return candidate.exists()


# Vocabulary and constructions that mark LLM-generated prose. None is damning alone —
# the finding fires on accumulation, and the LLM judgement pass makes the real call. Kept
# narrow to words that are rare in human technical writing but near-ubiquitous in
# generated text.
AI_TONE_MARKERS = [
    r"\bdelve[sd]?\b",
    r"\bseamless(?:ly)?\b",
    r"\brobust(?:ness)?\b",
    r"\bleverag(?:e|es|ing|ed)\b",
    r"\bcomprehensive\b",
    r"\bcutting[- ]edge\b",
    r"\bstate[- ]of[- ]the[- ]art\b",
    r"\bharness(?:es|ing)?\b",
    r"\bempower(?:s|ing|ed)?\b",
    r"\bstreamlin(?:e|es|ing|ed)\b",
    r"\bunlock(?:s|ing)?\b",
    r"\bfoster(?:s|ing)?\b",
    r"\bpivotal\b",
    r"\bmyriad\b",
    r"\bplethora\b",
    r"\bintricate\b",
    r"\bnuanced\b",
    r"\bholistic\b",
    r"\bparadigm\b",
    r"\btestament to\b",
    r"\bin today's\b",
    r"\bit(?:'s| is) (?:important|worth) (?:to note|noting)\b",
    r"\bwhether you(?:'re| are)\b",
    r"\bdive into\b",
    r"\bat its core\b",
    r"\bunder the hood\b",
    r"\bgame[- ]chang(?:er|ing)\b",
    r"\brevolutioni[sz]e[sd]?\b",
    r"\bever[- ]evolving\b",
    r"\bworld of\b",
    r"\bjourney\b",
    r"\bembark\b",
    r"\bcrucial\b",
    r"\bvital role\b",
    r"\bwealth of\b",
]
AI_TONE_RE = [re.compile(p, re.IGNORECASE) for p in AI_TONE_MARKERS]

# `- **Bold lead-in:** explanation` repeated down a list is the single most recognisable
# generated-README shape.
BOLD_LEADIN_RE = re.compile(r"^\s*[-*]\s+\*\*[^*]{3,60}\*\*\s*[:—-]", re.MULTILINE)

# Links that say the repo is part of something bigger.
ECOSYSTEM_RE = re.compile(
    r"ersilia\.io|ersilia-os/|ersilia\.gitbook\.io|Ersilia Model Hub", re.IGNORECASE
)

# Emoji and pictographic ranges. Built as an explicit range list rather than a library so
# the module stays stdlib-only.
EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f600-\U0001f64f"  # emoticons
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f700-\U0001f77f"
    "\U0001f900-\U0001f9ff"  # supplemental symbols
    "\U0001fa70-\U0001faff"
    "☀-⛿"  # misc symbols
    "✀-➿"  # dingbats
    "⬀-⯿"
    "]"
)


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


def check_readme(repo: Path, name: str, rtype: str, findings: list, skips: list) -> str:
    """README presence, shape, headings and footer. Returns the README text."""
    readme_path = None
    for cand in ("README.md", "README.rst", "README.txt", "readme.md"):
        if (repo / cand).is_file():
            readme_path = repo / cand
            break

    if readme_path is None:
        findings.append(
            finding(
                "T0-README-MISSING",
                "T0",
                "Blocker",
                "The repository has no README.",
                "Add a README.md: a descriptive H1, what this is, how to use it, and the "
                "canonical About-Ersilia footer.",
            )
        )
        skips.append(skipped("T0-README-STUB", "no README to measure"))
        skips.append(skipped("T0-FOOTER-MISSING", "no README to read"))
        return ""

    text = read_text(readme_path)
    rel = readme_path.name
    lines = non_blank_lines(text)

    if lines < 10:
        findings.append(
            finding(
                "T0-README-STUB",
                "T0",
                "Blocker",
                f"The README is a {lines}-line stub.",
                "Write a real README: what this is, who it is for, how to run it, and the "
                "About-Ersilia footer.",
                file=rel,
                detail=f"first line: {first_line(text)}",
            )
        )

    ceiling = README_MAX.get(rtype, 250)
    if lines > ceiling:
        check_id = "ANA-README-VERBOSE" if rtype == "Analysis" else "PKG-README-VERBOSE"
        tier = "T1"
        findings.append(
            finding(
                check_id,
                tier,
                "Should-fix",
                f"The README is {lines} non-blank lines; the {rtype} ceiling is {ceiling}.",
                'Move long-form content into `docs/`. The rule is "be brutally brief" — '
                "the README answers what this is and how to use it, nothing else.",
                file=rel,
            )
        )

    hs = headings(text)
    h1s = [h for h in hs if h[0] == 1]
    if not h1s:
        # Several repos set the title with a centred HTML heading so it can be aligned
        # alongside a banner logo (`ersilia` uses `<h2 align="center">`). That is a real
        # title, so reporting "no H1" would be wrong.
        html_title = HTML_HEADING_RE.search("\n".join(text.splitlines()[:15]))
        if html_title:
            skips.append(
                skipped(
                    "T0-H1-MISSING",
                    f"the README title is a centred HTML heading (`<{html_title.group(1)}>`) "
                    "rather than Markdown — a deliberate layout choice, not a missing title",
                )
            )
        else:
            findings.append(
                finding(
                    "T0-H1-MISSING",
                    "T0",
                    "Should-fix",
                    "The README has no H1 title.",
                    "Open with a single descriptive H1.",
                    file=rel,
                )
            )
    else:
        title = h1s[0][1]
        clean_title = EMOJI_RE.sub("", title).strip()
        if looks_like_name(title, name):
            findings.append(
                finding(
                    "T0-H1-IS-NAME",
                    "T0",
                    "Should-fix",
                    f"The README H1 is the bare repo name (`# {title}`).",
                    "Write a self-explanatory title instead — `eosquality` becomes "
                    "`# Quality scoring for Ersilia model predictions`, `lazy-qsar` becomes "
                    "`# Lazy QSAR modelling for small molecules`. A reader who has never seen "
                    "the repo should learn what it is from the title alone.",
                    file=rel,
                    line=h1s[0][2],
                )
            )
        elif len(clean_title.split()) < 3:
            # Not the repo name, but still not telling anyone anything.
            findings.append(
                finding(
                    "T0-H1-NOT-DESCRIPTIVE",
                    "T0",
                    "Should-fix",
                    f"The README H1 (`# {title}`) is too terse to be self-explanatory.",
                    "Expand it into a phrase that states what the repository does. The title is "
                    "the one line every reader sees.",
                    file=rel,
                    line=h1s[0][2],
                )
            )
        # More than one H1 means sections were written at the wrong level, or a backlog
        # was appended (eosquality has a second `# TODO`).
        if len(h1s) > 1:
            extra = "; ".join(f"line {ln}: `# {t}`" for _, t, ln in h1s[1:4])
            findings.append(
                finding(
                    "T0-HEADING-LEVELS",
                    "T0",
                    "Should-fix",
                    f"The README has {len(h1s)} H1 headings; sections should be H2.",
                    "Demote every section heading below the title to `##`.",
                    file=rel,
                    detail=extra,
                )
            )

    if re.search(r"^#{1,3}\s*(?:\W*\s*)?TODO\b", text, re.MULTILINE | re.IGNORECASE):
        findings.append(
            finding(
                "PKG-README-TODO",
                "T1",
                "Should-fix",
                "The README carries a TODO/backlog section.",
                "Move the open items to GitHub issues; the README is not a task tracker.",
                file=rel,
            )
        )

    if rtype == "Analysis" and re.search(r"^\s*[├└│]", text, re.MULTILINE):
        findings.append(
            finding(
                "ANA-README-FOLDER-TREE",
                "T1",
                "Should-fix",
                "The README reproduces the folder tree.",
                "Delete it and link to the structure section in `CLAUDE.md` instead.",
                file=rel,
            )
        )

    check_ai_tone(text, rel, findings)
    check_purpose(text, rel, name, findings)
    check_footer(repo, text, rel, findings, skips)
    check_links(repo, findings)
    return text


def check_footer(repo: Path, text: str, rel: str, findings: list, skips: list) -> None:
    """The About-Ersilia footer: presence, position, wording, and a resolving logo."""
    found = find_footer(text)
    if found is None:
        findings.append(
            finding(
                "T0-FOOTER-MISSING",
                "T0",
                "Blocker",
                "The README has no About-Ersilia footer.",
                "Append the canonical block from `references/canonical-footer.md`, including "
                "the `![Ersilia Logo](assets/Ersilia_Brand.png)` line.",
                file=rel,
            )
        )
        for cid in ("T0-FOOTER-DRIFT", "T0-FOOTER-NOT-LAST", "T0-LOGO-MISSING"):
            skips.append(skipped(cid, "no footer to inspect"))
        return

    level, title, line_no = found
    body = section_body(text, line_no, level)

    if title != CANONICAL_HEADING:
        findings.append(
            finding(
                "T0-FOOTER-DRIFT",
                "T0",
                "Should-fix",
                f"The footer heading is `{title}`, not `{CANONICAL_HEADING}`.",
                f"Rename it to `## {CANONICAL_HEADING}`.",
                file=rel,
                line=line_no,
            )
        )

    # Compare the prose paragraph, ignoring rewrapping.
    paragraphs = [
        p
        for p in re.split(r"\n\s*\n", body)
        if p.strip() and not p.strip().startswith("!")
    ]
    prose = normalise_prose(paragraphs[0]) if paragraphs else ""
    if prose and prose != normalise_prose(CANONICAL_ABOUT):
        findings.append(
            finding(
                "T0-FOOTER-DRIFT",
                "T0",
                "Should-fix",
                "The About-Ersilia paragraph differs from the canonical wording.",
                "Replace it with the block in `references/canonical-footer.md`. Four "
                "variants are in circulation org-wide; the template wording is the one "
                "new repos start from.",
                file=rel,
                line=line_no,
                detail=f"found: {prose[:200]}{'…' if len(prose) > 200 else ''}",
            )
        )

    # Position: only the logo may follow. A `### Funding` subsection inside the About
    # section is legitimate (ersilia carries grant-required MICIU/AEI attribution).
    trailing = [
        (lv, t, ln)
        for lv, t, ln in headings(text)
        if ln > line_no
        and lv <= level
        and re.sub(r"[^a-z]", "", t.lower()) != "funding"
    ]
    if trailing:
        findings.append(
            finding(
                "T0-FOOTER-NOT-LAST",
                "T0",
                "Should-fix",
                "The About-Ersilia footer is not the last section of the README.",
                "Move it to the end. Only the logo line belongs after it.",
                file=rel,
                line=line_no,
                detail="follows: "
                + "; ".join(f"line {ln}: `{t}`" for _, t, ln in trailing[:3]),
            )
        )

    # Logo.
    images = [m.group(1) or m.group(2) for m in IMAGE_RE.finditer(body)]
    if not images:
        findings.append(
            finding(
                "T0-LOGO-MISSING",
                "T0",
                "Blocker",
                "The footer has no Ersilia logo image.",
                "Add `![Ersilia Logo](assets/Ersilia_Brand.png)` as the last line and commit "
                "the asset.",
                file=rel,
                line=line_no,
            )
        )
        return

    for src in images:
        if re.match(r"^[a-z][a-z0-9+.-]*:", src, re.IGNORECASE):
            continue  # remote URL — accepted alternative, reported as drift below
        if not (repo / src.lstrip("/")).exists():
            findings.append(
                finding(
                    "T0-LOGO-UNRESOLVED",
                    "T0",
                    "Blocker",
                    f"The footer logo `{src}` does not exist in the repository.",
                    f"Commit the asset at `{src}`, or point the image at "
                    "`https://raw.githubusercontent.com/ersilia-os/ersilia/master/assets/"
                    "Ersilia_Plum.png`.",
                    file=rel,
                    line=line_no,
                )
            )


def check_ai_tone(text: str, rel: str, findings: list) -> None:
    """Prose that reads as generated rather than written.

    Fires on accumulation, never on a single word: `robust` appears in plenty of honest
    technical writing. The LLM judgement pass makes the real call — this exists so the
    reader gets the specific words to look at rather than a vague impression.
    """
    # Strip fenced code and inline code so vocabulary in examples does not count.
    prose = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    prose = re.sub(r"`[^`]*`", " ", prose)

    hits: list[str] = []
    for pattern in AI_TONE_RE:
        for m in pattern.finditer(prose):
            hits.append(m.group(0).lower())
    unique = sorted(set(hits))

    leadins = len(BOLD_LEADIN_RE.findall(prose))
    words = max(len(prose.split()), 1)
    density = len(hits) * 1000.0 / words

    # Em-dashes and emoji are the two most recognisable surface tells. Both are fine in
    # moderation, so both are measured as a rate rather than a presence.
    em_dashes = prose.count("—") + prose.count(" -- ")
    em_rate = em_dashes * 1000.0 / words
    emoji = EMOJI_RE.findall(prose)

    signals: list[str] = []
    if len(unique) >= 4:
        signals.append(
            f"{plural(len(hits), 'instance')} of {plural(len(unique), 'LLM-favoured term')}: "
            + ", ".join(f"`{u}`" for u in unique[:40])
        )
    if density > 6:
        signals.append(f"{density:.1f} such terms per 1000 words")
    if leadins >= 5:
        signals.append(f"{leadins} `- **Bold lead-in:** …` bullets")
    if em_dashes >= 4 and em_rate > 4:
        signals.append(f"{em_dashes} em-dashes ({em_rate:.1f} per 1000 words)")

    if len(signals) >= 2 or len(unique) >= 7 or leadins >= 8:
        findings.append(
            finding(
                "T0-README-AI-TONE",
                "T0",
                "Should-fix",
                "The README reads as LLM-generated rather than written.",
                "Rewrite it in your own voice: say what the thing does, who it is for, and how "
                'to run it. Cut the adjectives. The rule is "No AI-style filler" — a README '
                "should feel like a colleague explaining their work.",
                file=rel,
                detail="; ".join(signals),
                confidence="medium",
            )
        )

    # Emoji get their own finding: they are a house-style question, not evidence of
    # generated text. One in a title is fine (`ersilia` has 💊); a wall of them is not.
    headings_with_emoji = [
        f"line {ln}: `{t[:50]}`" for _, t, ln in headings(text) if EMOJI_RE.search(t)
    ]
    if len(emoji) >= 6 or len(headings_with_emoji) >= 3:
        findings.append(
            finding(
                "T0-README-EMOJI",
                "T0",
                "Nice-to-have",
                f"The README uses {len(emoji)} emoji, "
                f"{len(headings_with_emoji)} of them in headings.",
                "Cut them back to at most one, in the title. Emoji-heavy headings read as "
                "generated and age badly; `ersilia-maintenance` is the example to avoid.",
                file=rel,
                detail=(
                    "; ".join(headings_with_emoji[:40]) if headings_with_emoji else None
                ),
            )
        )


def check_purpose(text: str, rel: str, name: str, findings: list) -> None:
    """Whether the README says what this is and how it fits Ersilia's wider work."""
    lines = text.splitlines()
    # The lead: everything between the H1 and the first H2, minus badges and images.
    lead: list[str] = []
    seen_h1 = False
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            if len(m.group(1)) == 1:
                seen_h1 = True
                continue
            if seen_h1 or lead:
                break
            continue
        s = line.strip()
        if not s or s.startswith(("![", "<", "[!", "|", "```")):
            continue
        lead.append(s)
    lead_text = " ".join(lead)

    if len(lead_text.split()) < 12:
        findings.append(
            finding(
                "T0-README-NO-PURPOSE",
                "T0",
                "Should-fix",
                "The README does not open by saying what this repository is for.",
                "Add one or two sentences straight after the title: what it does, who it is "
                "for, and why it exists. A reader should not have to infer the purpose from "
                "an Installation section.",
                file=rel,
            )
        )

    # Does anything outside the boilerplate footer situate this in Ersilia's work?
    footer = find_footer(text)
    body = "\n".join(lines[: footer[2] - 1]) if footer else text
    if not ECOSYSTEM_RE.search(body):
        findings.append(
            finding(
                "T0-README-NO-ECOSYSTEM",
                "T0",
                "Nice-to-have",
                "Nothing outside the About-Ersilia footer connects this repository to the rest "
                "of Ersilia's work.",
                "Say how it fits: which project it belongs to, which models or packages it "
                "depends on or feeds, and link them. `mtb-targeted-protein-degradation` does "
                'this well with a short "Related repositories" section.',
                file=rel,
            )
        )


def check_external_links(repo: Path, findings: list, skips: list) -> None:
    """HTTP-check external links in tracked Markdown. Opt-in: needs the network."""
    import urllib.error  # noqa: PLC0415 — only needed on this path
    import urllib.request

    urls: dict[str, str] = {}
    for rel in tracked_files(repo):
        if not rel.lower().endswith((".md", ".markdown")):
            continue
        text = read_text(repo / rel)
        for m in MD_LINK_RE.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://")):
                line_no = text[: m.start()].count("\n") + 1
                urls.setdefault(target, f"{rel}:{line_no}")

    if not urls:
        skips.append(skipped("T0-BROKEN-EXTERNAL-LINK", "no external links found"))
        return

    broken: list[str] = []
    checked = 0
    for url, where in sorted(urls.items()):
        # Shields.io badges and similar are generated endpoints; a transient failure there
        # says nothing about the repo.
        if re.search(r"img\.shields\.io|badge\.fury\.io|zenodo\.org/badge", url):
            continue
        checked += 1
        req = urllib.request.Request(
            url, method="HEAD", headers={"User-Agent": "ersilia-repository-auditing"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 400:
                    broken.append(f"`{where}` → {url} ({resp.status})")
        except urllib.error.HTTPError as e:
            # 403/405 usually means the host dislikes HEAD or bots, not a dead link.
            if e.code in (401, 403, 405, 429):
                continue
            broken.append(f"`{where}` → {url} ({e.code})")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            broken.append(f"`{where}` → {url} ({type(e).__name__})")

    if broken:
        findings.append(
            finding(
                "T0-BROKEN-EXTERNAL-LINK",
                "T0",
                "Should-fix",
                f"{plural(len(broken), 'external link')} of {checked} did not resolve.",
                "Fix or remove them. Verify each by hand before acting — a network blip or a "
                "bot-blocking host can produce a false failure here.",
                detail="; ".join(broken[:40])
                + (f" (+{len(broken) - 40} more)" if len(broken) > 40 else ""),
                confidence="medium",
            )
        )


def check_links(repo: Path, findings: list) -> None:
    """Every relative link and image target in tracked Markdown resolves on disk."""
    broken: list[str] = []
    for rel in tracked_files(repo):
        if not rel.lower().endswith((".md", ".markdown")):
            continue
        doc = repo / rel
        if not doc.is_file():
            continue
        text = read_text(doc)
        for m in MD_LINK_RE.finditer(text):
            target = m.group(1)
            if not resolve_link(repo, doc, target):
                line_no = text[: m.start()].count("\n") + 1
                broken.append(f"`{rel}:{line_no}` → `{target}`")
    if broken:
        findings.append(
            finding(
                "T0-BROKEN-LINK",
                "T0",
                "Should-fix",
                f"{plural(len(broken), 'relative link')} {verb(len(broken), 'points', 'point')} at "
                "files that do not exist.",
                "Fix the paths or remove the links.",
                detail="; ".join(broken[:40])
                + (f" (+{len(broken) - 40} more)" if len(broken) > 40 else ""),
            )
        )


def check_license(repo: Path, gh: dict, findings: list) -> None:
    """A LICENSE file exists; GPL-3.0 is the house default."""
    has_file = any(
        (repo / n).is_file()
        for n in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
    )
    if not has_file:
        findings.append(
            finding(
                "T0-LICENSE-MISSING",
                "T0",
                "Blocker",
                "The repository has no LICENSE file.",
                "Add the GPL-3.0 text as `LICENSE`, matching the rest of the org.",
            )
        )
        return
    spdx = (gh.get("license") or "").upper()
    if spdx and spdx not in (
        "GPL-3.0",
        "GPL-3.0-ONLY",
        "GPL-3.0-OR-LATER",
        "NOASSERTION",
    ):
        findings.append(
            finding(
                "T0-LICENSE-NOT-GPL",
                "T0",
                "Nice-to-have",
                f"The license is {spdx}, not GPL-3.0.",
                "Confirm this is deliberate. 14 of 16 surveyed repos are GPL-3.0; `isaura` "
                "is intentionally MIT.",
                file="LICENSE",
            )
        )


def check_claudemd(
    repo: Path, findings: list, skips: list, is_template: bool = False
) -> dict:
    """CLAUDE.md presence and staleness.

    Returns a dict the SKILL uses to decide whether the file may grant overrides: a
    template leftover grants none.
    """
    path = repo / "CLAUDE.md"
    if not path.is_file():
        alt = repo / "AGENTS.md"
        if alt.is_file():
            findings.append(
                finding(
                    "T0-CLAUDEMD-MISSING",
                    "T0",
                    "Blocker",
                    "There is no CLAUDE.md (only AGENTS.md).",
                    "Add a CLAUDE.md. The org convention is CLAUDE.md — no surveyed repo "
                    "uses AGENTS.md.",
                )
            )
            return {"present": False, "stale": False, "grants_overrides": False}
        findings.append(
            finding(
                "T0-CLAUDEMD-MISSING",
                "T0",
                "Blocker",
                "The repository has no CLAUDE.md.",
                "Add one, starting from the matching template "
                "(`eos-python-package`, `eos-analysis-template`) and adapting the Project "
                "Overview and layout sections to this repo.",
            )
        )
        return {"present": False, "stale": False, "grants_overrides": False}

    text = read_text(path)
    hits = [m for m in CLAUDEMD_STALE_MARKERS if m in text]
    if hits and is_template:
        # The template's CLAUDE.md is *supposed* to describe the template. It still grants
        # no overrides — there is nothing repo-specific in it to override with.
        skips.append(
            skipped(
                "T0-CLAUDEMD-STALE",
                "target is a template repository — its CLAUDE.md legitimately describes the "
                "template. It grants no overrides regardless.",
            )
        )
        return {
            "present": True,
            "stale": False,
            "grants_overrides": False,
            "is_template": True,
        }
    if hits:
        findings.append(
            finding(
                "T0-CLAUDEMD-STALE",
                "T0",
                "Blocker",
                "CLAUDE.md is an unadapted template leftover.",
                "Rewrite the Project Overview and any layout section to describe this "
                "repository. Until then it grants no overrides — the audit ignores its "
                "rules.",
                file="CLAUDE.md",
                detail="markers found: " + "; ".join(f'"{h}"' for h in hits),
            )
        )
        return {"present": True, "stale": True, "grants_overrides": False}
    return {"present": True, "stale": False, "grants_overrides": True}


def check_placeholders(repo: Path, findings: list) -> None:
    """Template placeholder text surviving in tracked files."""
    hits: list[str] = []
    for rel in tracked_files(repo):
        if rel.startswith(".git"):
            continue
        fp = repo / rel
        if not fp.is_file() or fp.stat().st_size > 512_000:
            continue
        if fp.suffix.lower() in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".pdf",
            ".ico",
            ".woff",
            ".woff2",
        ):
            continue
        text = read_text(fp)
        if not text:
            continue
        for needle, what in PLACEHOLDERS:
            if needle in text:
                line_no = text[: text.index(needle)].count("\n") + 1
                hits.append(f"`{rel}:{line_no}` — `{needle}` ({what})")
    if hits:
        findings.append(
            finding(
                "T0-PLACEHOLDER",
                "T0",
                "Blocker",
                f"Template placeholder text survives in {plural(len(hits), 'place')}.",
                "Replace every placeholder with the real value, and rename the package "
                "folder if it is still `my_package`.",
                detail="; ".join(hits[:40])
                + (f" (+{len(hits) - 40} more)" if len(hits) > 40 else ""),
            )
        )


def check_root_reports(repo: Path, findings: list) -> None:
    """Long-form Markdown sitting at the repo root instead of docs/."""
    strays: list[str] = []
    for rel in tracked_files(repo):
        if "/" in rel or not rel.lower().endswith(".md"):
            continue
        if rel in ROOT_DOC_ALLOWLIST:
            continue
        if non_blank_lines(read_text(repo / rel)) > 30:
            strays.append(rel)
    if strays:
        findings.append(
            finding(
                "ANA-REPORT-AT-ROOT",
                "T1",
                "Should-fix",
                f"{plural(len(strays), 'long-form document')} {verb(len(strays), 'sits', 'sit')} at "
                "the repo root.",
                "Move them into `docs/`, named `YYYY-MM-DD_topic.md` or `NN_topic.md`. "
                "AI-generated reports in particular belong there, not at the root.",
                detail=rollup(strays),
            )
        )


def main() -> int:
    """Run the documentation checks and write the findings document."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="/tmp/repo_audit_target.json")
    ap.add_argument("--type", default="", help="repository Type from Airtable")
    ap.add_argument(
        "--check-external",
        action="store_true",
        help="HTTP-check external links in tracked Markdown. Needs the network and is slow; "
        "opt-in per the SKILL's depth question.",
    )
    ap.add_argument(
        "--status",
        default="",
        help="comma-separated Airtable Status values; accepted for a uniform call shape "
        "across all checkers even where unused",
    )
    ap.add_argument("--out", default="/tmp/repo_audit_docs.json")
    args = ap.parse_args()

    target = load_target(args.target)
    repo = Path(target["path"])
    name = target["name"]
    rtype = args.type or "Package"
    gh = target.get("github") or {}

    findings: list[dict] = []
    skips: list[dict] = []

    # The templates are the source of the placeholder text, so those checks would fire on
    # every line of them. Suppress with a visible note rather than silently.
    template = is_template_repo(target)
    if template:
        skips.append(
            skipped(
                "T0-PLACEHOLDER",
                "target is a template repository — placeholder text is its purpose",
            )
        )
    else:
        check_placeholders(repo, findings)

    check_readme(repo, name, rtype, findings, skips)
    if args.check_external:
        check_external_links(repo, findings, skips)
    else:
        skips.append(
            skipped(
                "T0-BROKEN-EXTERNAL-LINK",
                "not requested — pass --check-external to HTTP-check external links",
            )
        )
    check_license(repo, gh, findings)
    claudemd = check_claudemd(repo, findings, skips, is_template=template)
    if rtype == "Analysis":
        check_root_reports(repo, findings)
    else:
        skips.append(
            skipped("ANA-REPORT-AT-ROOT", f"not an Analysis repo (type={rtype})")
        )

    emit(args.out, findings, skips, type=rtype, claudemd=claudemd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
