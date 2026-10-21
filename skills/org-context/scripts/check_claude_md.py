"""Run the deterministic checks on the fetched CLAUDE.md files. Offline.

Reads ``targets.json`` and ``files/`` from the work directory and the policies in
``references/rules.json``; writes ``checks.json``, a list of findings:

    {"key": "org:CANON-black:1", "target": "org", "check": "CANON-black",
     "severity": "fix", "line": 64, "title": "...", "detail": "..."}

``key`` is stable for a given file and rule set, so the judgement step can attach an
edit to it or dismiss it. Prints a one-line count per file.

Usage:
    python check_claude_md.py [--work /tmp/org_context] [--rules path] [--today YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date
from itertools import combinations
from pathlib import Path

from _common import (
    HEADING_RE,
    finding_key,
    parse_month_year,
    LINK_RE,
    REFS,
    WORK_DIR,
    content_words,
    load_work,
    prose_lines,
    read_json,
    sections,
    units,
    write_json,
)

EMOJI_RE = re.compile("[\U0001f300-\U0001faff☀-➿⭐✅❌]")
MALFORMED_LINK_RE = re.compile(r"\[(https?://[^\]\s]+)\](?!\()")


class Findings:
    """Collects findings under stable keys (see ``_common.finding_key``)."""

    def __init__(self) -> None:
        self.items: list[dict] = []
        self.seen: Counter = Counter()

    def add(self, target, check, severity, line, title, detail=""):
        key = finding_key(target, check, title)
        self.seen[key] += 1
        if self.seen[key] > 1:  # same wording twice in one file
            key = f"{key}-{self.seen[key]}"
        self.items.append(
            {
                "key": key,
                "target": target,
                "check": check,
                "severity": severity,
                "line": line,
                "title": title,
                "detail": detail,
            }
        )


def check_length(f: Findings, t: dict, text: str, budget: dict) -> None:
    """Whole-file and per-section line budgets."""
    n = len(text.splitlines())
    if n > budget["max_lines"]:
        f.add(
            t["id"],
            "LEN-FILE",
            "trim",
            1,
            f"{n} lines, budget {budget['max_lines']}",
            "Every line is loaded into every session. Cut what an agent can find elsewhere "
            "(GitBook, the repo itself) or never acts on.",
        )
    for s in sections(text):
        size = s["end"] - s["start"] + 1
        if s["level"] in (1, 0) and s["title"] != "(preamble)":
            continue  # the H1 spans the whole file
        if s["level"] == 2 and size > budget["max_section_lines"]:
            f.add(
                t["id"],
                "LEN-SECTION",
                "trim",
                s["start"],
                f"Section '{s['title']}' is {size} lines, budget {budget['max_section_lines']}",
            )


def check_last_updated(f: Findings, t: dict, text: str, rule: dict, today: date):
    """A dated footer must exist (for the roles that need one) and be recent."""
    m = re.search(rule["pattern"], text)
    if not m:
        if t["role"] in rule["required_roles"]:
            f.add(t["id"], "DATE-MISSING", "fix", None, "No 'Last updated' line")
        return
    line = text[: m.start()].count("\n") + 1
    try:
        stamp = parse_month_year(m.group(1))
    except ValueError:
        f.add(t["id"], "DATE-UNPARSED", "fix", line, f"Unreadable date '{m.group(1)}'")
        return
    age = (today - stamp).days
    if age > rule["max_age_days"]:
        f.add(
            t["id"],
            "DATE-STALE",
            "consider",
            line,
            f"Last updated {m.group(1)} ({age} days ago, limit {rule['max_age_days']})",
            "Check what changed in practice since then; the date is bumped automatically "
            "when edits are applied.",
        )


def check_sections(f: Findings, t: dict, text: str, required: list[str]) -> None:
    """Required sections present; one H1; no skipped heading levels."""
    secs = [s for s in sections(text) if s["level"] > 0]
    titles = [s["title"].lower() for s in secs]
    for name in required:
        if not any(name.lower() in title for title in titles):
            f.add(t["id"], "SECTION-MISSING", "fix", None, f"No section on '{name}'")
    h1 = [s for s in secs if s["level"] == 1]
    if len(h1) != 1:
        f.add(
            t["id"],
            "HEADINGS",
            "fix",
            h1[1]["start"] if len(h1) > 1 else 1,
            f"{len(h1)} H1 headings; expected exactly one",
        )
    prev = 0
    for s in secs:
        if prev and s["level"] > prev + 1:
            f.add(
                t["id"],
                "HEADINGS",
                "trim",
                s["start"],
                f"Heading '{s['title']}' skips from H{prev} to H{s['level']}",
            )
        prev = s["level"]


def check_text(f: Findings, t: dict, text: str, rules: dict) -> None:
    """Placeholders, vague phrases, malformed links, decorative emoji."""
    for n, line in prose_lines(text):
        # Inline code is exempt: a template naming `src/my_package/` is an instruction.
        bare = re.sub(r"`[^`]*`", "", line)
        for ph in rules["placeholders"]:
            if re.search(rf"(?<!\w){re.escape(ph)}(?!\w)", bare):
                f.add(t["id"], "PLACEHOLDER", "fix", n, f"Placeholder text '{ph}'")
        low = line.lower()
        for phrase in rules["vague_phrases"]:
            if phrase in low:
                f.add(
                    t["id"],
                    "VAGUE",
                    "consider",
                    n,
                    f"Vague instruction: '{phrase}'",
                    "Say what to do concretely, or drop the sentence.",
                )
        for m in MALFORMED_LINK_RE.finditer(line):
            f.add(
                t["id"],
                "LINK-MALFORMED",
                "fix",
                n,
                f"Bracketed URL is not a link: [{m.group(1)}]",
                f"Write [text]({m.group(1)}) or the bare URL.",
            )
        for _, url in LINK_RE.findall(line):
            if not re.match(r"^(https?://|mailto:|#)", url):
                f.add(
                    t["id"],
                    "LINK-RELATIVE",
                    "consider",
                    n,
                    f"Relative link '{url}'",
                    "Fine in a repo, but it breaks wherever the file is copied as context.",
                )
        if EMOJI_RE.search(line) and not HEADING_RE.match(line):
            f.add(t["id"], "EMOJI", "trim", n, "Decorative emoji")
        elif EMOJI_RE.search(line):
            f.add(t["id"], "EMOJI", "trim", n, "Emoji in a heading")


def check_canon(f: Findings, t: dict, text: str, canon: list[dict]) -> None:
    """Canonical statements every file must agree with."""
    prose = "\n".join(line for _, line in prose_lines(text))
    for rule in canon:
        if t["role"] not in rule["roles"]:
            continue
        check = f"CANON-{rule['id']}"
        if "pattern" in rule:
            for n, line in prose_lines(text):
                if re.search(rule["pattern"], line, re.I):
                    f.add(t["id"], check, "fix", n, rule["message"])
        if "require" in rule:
            gate = rule.get("if")
            if gate and not re.search(gate, prose, re.I):
                continue
            if not re.search(rule["require"], prose, re.I):
                f.add(t["id"], check, "fix", None, rule["message"])


def check_bloat(f: Findings, t: dict, text: str, rule: dict) -> None:
    """Folder trees and 'this is a ... repository' overviews an agent can do without."""
    lines = text.splitlines()
    tree = [
        n
        for n, line in enumerate(lines, 1)
        if any(m in line for m in rule["tree_markers"])
    ]
    if tree:
        f.add(
            t["id"],
            "BLOAT-TREE",
            "trim",
            tree[0],
            f"Folder tree of {len(tree)} lines",
            "Replace it with the few folder rules an agent cannot infer by listing the "
            "repo. " + rule["why"],
        )
    # Only the preamble (before the first H2) is an overview; later text has a job.
    first_h2 = next(
        (s["start"] for s in sections(text) if s["level"] == 2), len(lines) + 1
    )
    for n in range(1, first_h2):
        line = lines[n - 1].strip()
        if re.match(rule["overview_pattern"], line, re.I):
            f.add(
                t["id"],
                "BLOAT-OVERVIEW",
                "consider",
                n,
                f"Overview sentence: '{short(line)}'",
                "Keep only what changes an agent's behaviour. " + rule["why"],
            )


def check_hooks(f: Findings, t: dict, text: str, rule: dict) -> None:
    """Prohibitions Claude Code could enforce instead of trusting the agent: one finding."""
    hits = []
    for n, line in prose_lines(text):
        if not re.search(rule["trigger"], line, re.I):
            continue
        for action in rule["actions"]:
            if re.search(action["pattern"], line, re.I):
                hits.append((n, action["suggest"]))
                break
    if hits:
        f.add(
            t["id"],
            "HOOK-CANDIDATE",
            "consider",
            hits[0][0],
            f"{len(hits)} prohibition(s) could be enforced, not just stated "
            f"(lines {', '.join(str(n) for n, _ in hits)})",
            "; ".join(f"line {n}: {s}" for n, s in hits) + ". " + rule["why"],
        )


def similar(a: dict, b: dict, rule: dict) -> bool:
    """True if two prose units say the same thing."""
    if rule["lead_match"] and a["lead"] and b["lead"]:
        if content_words(a["lead"]) and content_words(a["lead"]) == content_words(
            b["lead"]
        ):
            return True
    wa, wb = content_words(a["text"]), content_words(b["text"])
    if min(len(wa), len(wb)) < rule["min_words"]:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= rule["overlap"]


def word_count(text: str) -> int:
    """Words in ``text``, counting a Markdown link by its label only."""
    return len(re.findall(r"\w+", LINK_RE.sub(r"\1", text)))


def short(text: str, n: int = 70) -> str:
    """Trim ``text`` to ``n`` characters for a title."""
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def check_duplication(f: Findings, targets: list[dict], texts: dict, rule: dict):
    """Repeated instructions inside one file, and between the org file and a template."""
    by_id = {t["id"]: t for t in targets}
    parsed = {tid: units(text) for tid, text in texts.items()}
    for tid, us in parsed.items():
        for a, b in combinations(us, 2):
            if similar(a, b, rule):
                f.add(
                    tid,
                    "DUP-WITHIN",
                    rule["within_file"],
                    b["line"],
                    f"Repeats line {a['line']}: '{short(b['text'])}'",
                    "Say it once, in the section where an agent would look for it.",
                )
    pairs = {tuple(p) for p in rule["cross_file_pairs"]}
    for x, y in combinations(targets, 2):
        if (x["role"], y["role"]) not in pairs and (y["role"], x["role"]) not in pairs:
            continue
        # Report on the non-org side: that is where a trim would happen.
        org, other = (x, y) if x["role"] == "org" else (y, x)
        for a in parsed[org["id"]]:
            for b in parsed[other["id"]]:
                # A short template copy is the condensed, stand-alone version: fine.
                if word_count(b["text"]) < rule["cross_file_min_words"]:
                    continue
                if similar(a, b, rule):
                    f.add(
                        other["id"],
                        "DUP-ORG",
                        rule["cross_file"],
                        b["line"],
                        f"Also in {by_id[org['id']]['path']} line {a['line']}: "
                        f"'{short(b['text'])}'",
                        "Repos built from a template are used by people who may not "
                        "load the org file, so repetition can be deliberate. Keep it "
                        "only if it must stand alone.",
                    )


def main(argv: list[str] | None = None) -> int:
    """Run all checks and write checks.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--rules", default=str(REFS / "rules.json"))
    p.add_argument("--today", default=date.today().isoformat())
    args = p.parse_args(argv)
    rules = read_json(args.rules)
    today = date.fromisoformat(args.today)
    targets, texts = load_work(args.work)

    f = Findings()
    for t in targets:
        text = texts[t["id"]]
        check_length(f, t, text, rules["budgets"][t["role"]])
        check_last_updated(f, t, text, rules["last_updated"], today)
        check_sections(f, t, text, rules["required_sections"].get(t["role"], []))
        check_text(f, t, text, rules)
        check_canon(f, t, text, rules["canon"])
        check_bloat(f, t, text, rules["bloat"])
        check_hooks(f, t, text, rules["hooks"])
    check_duplication(f, targets, texts, rules["duplication"])

    write_json(Path(args.work) / "checks.json", f.items)
    for t in targets:
        c = Counter(i["severity"] for i in f.items if i["target"] == t["id"])
        print(f"{t['id']:4} fix {c['fix']}, trim {c['trim']}, consider {c['consider']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
