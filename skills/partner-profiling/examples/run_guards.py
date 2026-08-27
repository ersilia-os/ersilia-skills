#!/usr/bin/env python3
"""Assert that partner-profiling's guards actually reject what they claim to reject.

Run from anywhere:

    python3 examples/run_guards.py

Exits 0 and prints "N guards OK" when every assertion holds; exits 1 naming the guard
that broke. No network, no real people — `examples/guards.json` uses invented entities on
`.test` domains (a reserved TLD that can never resolve), which is what makes it safe to
commit to a public repository. Real sweep output cannot serve this purpose: it names
journalists and carries contact addresses, which is why `reports/` is gitignored.

The guards here are the *rejection* rules — the deterministic half of the skill. The
discovery half needs live web searches and is not assertable; that is what the review gate
in SKILL.md is for.

Each check states what it asserts and why it exists, because a failing test whose purpose
nobody remembers gets deleted rather than fixed.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
FIXTURE = HERE / "guards.json"
KNOWN = HERE / "known-partners-fixture.md"

# Fixed dates so a run is reproducible and never depends on the wall clock.
TODAY = "2026-08-27"
OCCASION = "2026-11-10"

failures = []
checks = 0


def check(label, condition, detail=""):
    global checks
    checks += 1
    if condition:
        print(f"  ok    {label}")
    else:
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ""))
        failures.append(label)


def run(args):
    """Run a skill script, returning (stdout, stderr). Fails loudly on a crash."""
    proc = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=SKILL)
    if proc.returncode != 0:
        print(f"  FAIL  script exited {proc.returncode}: {' '.join(str(a) for a in args)}")
        print(proc.stderr[-2000:])
        failures.append("script crashed")
    return proc.stdout, proc.stderr


def by_prefix(rows, prefix):
    """Find a kept row by its Gnn prefix, or None if the guard dropped it."""
    for row in rows:
        if row.get("name", "").startswith(prefix):
            return row
    return None


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pp-guards-"))
    clean = tmp / "clean.json"
    ledger = tmp / "ledger.json"

    print("\npartner-profiling — guard assertions")
    print(f"fixture: {FIXTURE.relative_to(SKILL)}  ·  reference date {TODAY}\n")

    # --- Pass 1: screening, contacts, dedup, known-partners, link years -----------
    _, err = run([SCRIPTS / "filter_and_sort.py", "--in", FIXTURE, "--out", clean,
                  "--known", KNOWN, "--order", "deadline",
                  "--today", TODAY, "--occasion-date", OCCASION])
    rows = json.loads(clean.read_text(encoding="utf-8"))

    check("G01 a row with no hook is dropped — the relevance gate",
          by_prefix(rows, "G01") is None)
    check("G02 an out-of-vocabulary class is rejected, not coerced",
          by_prefix(rows, "G02") is None)

    g03 = by_prefix(rows, "G03")
    kinds = {c["kind"] for c in (g03 or {}).get("contacts", [])}
    check("G03 the row survives while its forbidden contact is stripped",
          g03 is not None and kinds == {"institutional"},
          f"kinds kept: {sorted(kinds)}")
    check("G03 an unrecognised contact kind is stripped — the policy fails closed",
          "linkedin_dm" not in kinds)

    g04 = by_prefix(rows, "G04")
    check("G04 a scientific_correspondence address is kept but marked restricted",
          g04 is not None and g04["contacts"][0]["restricted"] is True)
    check("G04 …and earns no envelope marker, because it is not a pitch channel",
          g04 is not None and "✉" not in g04.get("markers", ""))

    merged = by_prefix(rows, "G05")
    check("G05 duplicates merge to ONE row",
          sum(1 for r in rows if r.get("name", "").startswith("G05")) == 1)
    check("G05 the RICHER copy wins even though it arrived second",
          merged is not None and "RICH" in merged.get("next_step", ""),
          f"next_step kept: {merged.get('next_step') if merged else None}")

    check("G06 a known partner is suppressed by domain", by_prefix(rows, "G06") is None)
    check("G07 a known partner is suppressed by organisation name", by_prefix(rows, "G07") is None)

    g08 = by_prefix(rows, "G08")
    check("G08 a stale link year is flagged and forces verified=false",
          g08 is not None and g08.get("stale_link") is True and g08.get("verified") is False)
    g09 = by_prefix(rows, "G09")
    check("G09 a FUTURE link year is not flagged — forward planning, not staleness",
          g09 is not None and not g09.get("stale_link", False) and g09.get("verified") is True)
    g10 = by_prefix(rows, "G10")
    check("G10 an old item in recent_work is not flagged — it is the evidence",
          g10 is not None and not g10.get("stale_link", False))

    check("G11 a contact_by falling after the occasion warns",
          "falls AFTER the occasion" in err)
    check("G12 a missing contact_by warns", "has no contact_by date" in err)
    check("G12 …and sorts last", rows[-1].get("name", "").startswith("G12"),
          f"last row is {rows[-1].get('name')}")

    g13 = by_prefix(rows, "G13")
    check("G13 a Creative row carries cost and portfolio with reach left empty",
          g13 is not None and not g13.get("reach") and g13.get("cost")
          and g13.get("portfolio_url"))

    # Variation-selector regression: ⏱️ and ✉️ both end U+FE0F, and a character-level
    # dedup used to strip the second one, rendering a bare "✉".
    ribbons = [r.get("markers", "") for r in rows]
    check("marker ribbons keep their variation selectors (no bare ✉ or ⏱)",
          all(("✉" not in m or "✉️" in m) and ("⏱" not in m or "⏱️" in m) for m in ribbons))

    # --- The shipped known-partners file must contain no live entries -------------
    sys.path.insert(0, str(SCRIPTS))
    from filter_and_sort import load_known  # noqa: E402
    names, domains = load_known(str(SKILL / "references" / "known-partners.md"))
    check("the SHIPPED known-partners.md parses to zero entries (prose is not data)",
          not names and not domains, f"names={names} domains={domains}")
    fx_names, fx_domains = load_known(str(KNOWN))
    check("a fenced example and stray prose are not parsed as entries",
          fx_domains == {"example-institute.test"} and fx_names == {"testwire foundation"},
          f"names={fx_names} domains={fx_domains}")

    # --- Ledger: a second run with --hide-seen keeps nothing ----------------------
    run([SCRIPTS / "filter_and_sort.py", "--in", FIXTURE, "--out", tmp / "l1.json",
         "--known", KNOWN, "--ledger", ledger, "--today", TODAY])
    run([SCRIPTS / "filter_and_sort.py", "--in", FIXTURE, "--out", tmp / "l2.json",
         "--known", KNOWN, "--ledger", ledger, "--hide-seen", "--today", TODAY])
    check("the ledger suppresses everything on a second --hide-seen run",
          json.loads((tmp / "l2.json").read_text()) == [])

    # --- Renderers ----------------------------------------------------------------
    sweep_md = tmp / "sweep.md"
    camp_md = tmp / "campaign.md"
    run([SCRIPTS / "render_sweep.py", "--in", clean, "--out", sweep_md, "--date", TODAY])
    run([SCRIPTS / "render_campaign.py", "--in", clean, "--out", camp_md, "--date", TODAY,
         "--occasion", "Guard fixture", "--occasion-date", OCCASION])
    sweep = sweep_md.read_text(encoding="utf-8")
    camp = camp_md.read_text(encoding="utf-8")

    check("G14 a pipe inside a hook is escaped, not treated as a column break",
          r"a \| pipe" in sweep)

    import re
    def tables_consistent(text):
        block, ok = [], True
        for line in text.splitlines():
            if line.startswith("|"):
                block.append(len(re.findall(r"(?<!\\)\|", line)))
            elif block:
                ok = ok and len(set(block)) == 1
                block = []
        return ok and (not block or len(set(block)) == 1)

    check("every rendered table has a consistent column count", tables_consistent(sweep))
    check("…in the campaign layout too", tables_consistent(camp))
    check("next_step is never trimmed in table layout",
          "RICH next step, must be the one that survives the merge." in sweep)
    check("a Creative table omits the reach column", "| Reach |" not in
          camp.split("Creatives to commission")[1].split("##")[0])

    # --- Drive-safe rendition ------------------------------------------------------
    drive_md = tmp / "drive.md"
    run([SCRIPTS / "render_campaign.py", "--in", clean, "--out", drive_md, "--date", TODAY,
         "--occasion", "Guard fixture", "--occasion-date", OCCASION,
         "--layout", "detail", "--markers", "text"])
    drive = drive_md.read_text(encoding="utf-8")
    check("the Drive-safe rendition has no pipe tables",
          not any(l.startswith("|") for l in drive.splitlines()))
    check("…and no emoji above U+1FFFF, which that conversion corrupts",
          not re.search(r"[\U0001F300-\U0001FAFF]", drive))

    # --- Empty pool ----------------------------------------------------------------
    empty = tmp / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    run([SCRIPTS / "filter_and_sort.py", "--in", empty, "--out", tmp / "ec.json"])
    run([SCRIPTS / "render_sweep.py", "--in", tmp / "ec.json", "--out", tmp / "e1.md",
         "--date", TODAY])
    e1 = (tmp / "e1.md").read_text(encoding="utf-8")
    check("an empty pool renders without crashing",
          "Nothing survived screening" in e1)
    check("…and says so exactly once, with no trim note and no empty tables",
          e1.count("Nothing survived screening") == 1 and "…" not in e1)

    print()
    if failures:
        print(f"{len(failures)} of {checks} guards FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"{checks} guards OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
