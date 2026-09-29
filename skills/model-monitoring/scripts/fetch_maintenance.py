"""Fetch and parse the ersilia-maintenance reports into a single JSON payload.

`ersilia-os/ersilia-maintenance` publishes the outcome of the automated weekly
and monthly model checks as markdown reports plus a few PNG trend plots. This
script pulls them over plain HTTPS and turns the markdown tables into structured
rows, so the report builder never has to scrape prose.

The GitHub CLI is deliberately not used: it is not installed in this
environment, and every file needed here is public, so an unauthenticated raw
fetch is both sufficient and one less dependency. Set GITHUB_TOKEN to raise the
API rate limit if a run ever hits it.

Usage:
    python fetch_maintenance.py --out maintenance.json
    python fetch_maintenance.py --out maintenance.json --plots
"""

import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "ersilia-os/ersilia-maintenance"
RAW = f"https://raw.githubusercontent.com/{REPO}/main"

# Markdown reports worth parsing, mapped to how they are consumed downstream.
REPORTS = {
    "weekly_model_testing": "reports/weekly_model_testing.md",
    "failing_models": "reports/failing_models.md",
    "updated_models": "reports/updated_models.md",
    "monthly_health_report": "reports/monthly_health_report.md",
}

# The monthly trend plots. Only fetched with --plots, because the user usually
# wants the weekly numbers and the images add ~270 KB of base64 to the report.
PLOTS = {
    "health_and_testing": "reports/health_and_testing.png",
    "issues_and_added": "reports/issues_and_added.png",
    "distributions_tasks_source": "reports/distributions_tasks_source.png",
}

HISTORY = "reports/monthly_health_history.json"


def fetch(path, binary=False, timeout=60):
    """Fetch one file from the maintenance repo. Returns None when absent.

    A missing report is not fatal: the maintenance automation adds and renames
    files over time, and a partial report that names what it could not find is
    far more useful than a crash.
    """
    url = f"{RAW}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "ersilia-model-monitoring"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return raw if binary else raw.decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"[maintenance] WARNING: {path} -> HTTP {e.code}", file=sys.stderr)
        return None
    except Exception as e:  # network, DNS, timeout
        print(f"[maintenance] WARNING: {path} -> {e}", file=sys.stderr)
        return None


def parse_md_table(text):
    """Extract the first pipe-delimited markdown table as a list of dicts.

    The maintenance reports decorate their headers with emoji (`🧬 repository_name`),
    so header cells are stripped of everything but word characters to give stable
    keys regardless of which emoji the generator picked this week.
    """
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines()]
    rows, header = [], None
    for ln in lines:
        if not ln.startswith("|"):
            if header:
                break  # table ended
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        if all(set(c) <= set("-: ") and c for c in cells):
            continue  # separator row
        if header is None:
            header = [_clean_key(c) for c in cells]
            continue
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _clean_key(cell):
    """Turn a decorated header cell into a snake_case key."""
    cell = re.sub(r"[^\w\s]", " ", cell, flags=re.UNICODE)
    cell = re.sub(r"[^\x00-\x7F]", " ", cell)  # drop emoji
    return "_".join(cell.lower().split())


def parse_generated(text):
    """Pull the report's own generation timestamp out of its header."""
    if not text:
        return None
    m = re.search(r"\*\*(?:Generated|Generated at|🗓️ Date|Date)[:\*\s]*\**\s*([^\n*]+)", text)
    return m.group(1).strip() if m else None


def parse_monthly_snapshot(text):
    """Read the `- **Label:** N` bullets out of the monthly health report.

    The trailing `(?![\\d\\-:.])` guard keeps dates out of the snapshot: without
    it, `**Generated at:** 2026-08-01` is read as the integer 2026 and lands in
    the counts alongside the real model tallies.
    """
    snapshot = {}
    if not text:
        return snapshot
    for label, value in re.findall(r"\*\*([^*]+?):\*\*\s*(\d+)(?![\d\-:.])", text):
        key = _clean_key(label)
        if key:
            snapshot[key] = int(value)
    m = re.search(r"\*\*Month:\*\*\s*([\d-]+)", text)
    if m:
        snapshot["month"] = m.group(1)
    return snapshot


def summarise_weekly(rows):
    """Count pass / fail in the weekly test table.

    The report marks outcomes with emoji rather than words, so we look for the
    icons directly: 🚨 for a failure, ✅ for a pass.
    """
    passed = [r for r in rows if "✅" in r.get("test", "")]
    failed = [r for r in rows if "🚨" in r.get("test", "")]
    other = [r for r in rows if r not in passed and r not in failed]
    return {
        "tested": len(rows),
        "passed": len(passed),
        "failed": len(failed),
        "inconclusive": len(other),
        "failed_models": [
            {"model_id": r.get("repository_name", ""), "slug": r.get("slug", ""),
             "test_date": r.get("test_date", "")}
            for r in failed
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Path for the maintenance JSON output")
    ap.add_argument("--plots", action="store_true",
                    help="Also embed the monthly trend PNGs as data URIs")
    args = ap.parse_args()

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo": REPO,
        "repo_url": f"https://github.com/{REPO}",
        "missing_sources": [],
        "reports": {},
        "plots": {},
    }

    raw_texts = {}
    for name, path in REPORTS.items():
        text = fetch(path)
        raw_texts[name] = text
        if text is None:
            payload["missing_sources"].append(path)
            continue
        payload["reports"][name] = {
            "path": path,
            "url": f"https://github.com/{REPO}/blob/main/{path}",
            "generated": parse_generated(text),
            "rows": parse_md_table(text),
        }

    if "weekly_model_testing" in payload["reports"]:
        payload["weekly_summary"] = summarise_weekly(
            payload["reports"]["weekly_model_testing"]["rows"]
        )

    if "monthly_health_report" in payload["reports"]:
        payload["monthly_snapshot"] = parse_monthly_snapshot(
            raw_texts["monthly_health_report"]
        )

    history_text = fetch(HISTORY)
    if history_text:
        try:
            history = json.loads(history_text)
            payload["monthly_history"] = history
            payload["monthly_history_months"] = [h.get("month") for h in history]
        except json.JSONDecodeError as e:
            print(f"[maintenance] WARNING: history not valid JSON: {e}", file=sys.stderr)
            payload["missing_sources"].append(HISTORY)
    else:
        payload["missing_sources"].append(HISTORY)

    if args.plots:
        for name, path in PLOTS.items():
            blob = fetch(path, binary=True)
            if blob is None:
                payload["missing_sources"].append(path)
                continue
            payload["plots"][name] = {
                "path": path,
                "bytes": len(blob),
                # Inlined as a data URI so the finished HTML report is a single
                # self-contained file the team can email or archive.
                "data_uri": "data:image/png;base64," + base64.b64encode(blob).decode(),
            }

    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    w = payload.get("weekly_summary", {})
    print(
        f"[maintenance] wrote {args.out}\n"
        f"              weekly: {w.get('tested', 0)} tested, "
        f"{w.get('passed', 0)} passed, {w.get('failed', 0)} failed\n"
        f"              failing report rows: "
        f"{len(payload['reports'].get('failing_models', {}).get('rows', []))}\n"
        f"              plots embedded: {len(payload['plots'])}"
        + (f"\n              MISSING: {payload['missing_sources']}"
           if payload["missing_sources"] else ""),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
