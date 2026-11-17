"""Run detectors that have an API, so no browser and no CAPTCHA are involved.

Results go into the same plan results as the browser route (lib/detectors.py), under the
same tool ids, so grading and the report treat them alike. Each provider needs the user's own key in
an environment variable. The skill never creates accounts or keys.

    pangram       PANGRAM_API_KEY   validated. Free research credits on application
                  (https://pangram.com/solutions/api); otherwise $0.05 per 100 words.
    gptzero       GPTZERO_API_KEY   validated. Paid API; ask for research credits.
    sapling       SAPLING_API_KEY   context. Free key: 50,000 characters a day, 250,000 a month.
    binoculars    HF_TOKEN (optional)  context. The authors' hosted demo on Hugging Face
                  (tomg-group-umd/Binoculars); nothing is downloaded; free GPU quota.

Sending text to any of these uploads it. The same rules as the browser route apply
(references/web_detectors_guide.md, section 1): never for a manuscript or grant the user is reviewing, and only after the
user has approved that service at least once (``--approved`` records it in the ledger dir).

Usage:
    python api_detectors.py --tools pangram,sapling [--chunks P1,P2 | S,W]
    python api_detectors.py --status          # which keys are set; sends nothing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from lib.common import LOCAL, WORK_DIR, die, read_json, today, write_json
from lib.detectors import Scan, report_left_out, tool
from lib.http import post_json, request

APPROVALS = LOCAL / "approved_services.json"
KEYS = {
    "pangram": "PANGRAM_API_KEY",
    "gptzero": "GPTZERO_API_KEY",
    "sapling": "SAPLING_API_KEY",
    "binoculars": "HF_TOKEN",
}


def pangram(text: str, key: str) -> tuple[float, str]:
    """AI fraction of the text (0-1) and a label."""
    d = post_json("https://text.api.pangram.com/v3", {"text": text}, {"x-api-key": key})
    frac = d.get("fraction_ai")
    if frac is None:
        raise RuntimeError(f"unexpected response: {str(d)[:200]}")
    frac = float(frac) + float(d.get("fraction_ai_assisted") or 0)
    return min(frac, 1.0), d.get("prediction") or d.get("headline") or ""


def gptzero(text: str, key: str) -> tuple[float, str]:
    """Probability the document is AI-generated (AI + mixed) and the classification."""
    d = post_json(
        "https://api.gptzero.me/v2/predict/text", {"document": text}, {"x-api-key": key}
    )
    doc = (d.get("documents") or [{}])[0]
    probs = doc.get("class_probabilities") or {}
    if probs:
        return float(probs.get("ai", 0)) + float(probs.get("mixed", 0)), doc.get(
            "document_classification", ""
        )
    return float(doc.get("completely_generated_prob", 0)), doc.get(
        "document_classification", ""
    )


def sapling(text: str, key: str) -> tuple[float, str]:
    """Sapling's document score (0-1, higher is more AI) and verdict."""
    d = post_json(
        "https://api.sapling.ai/api/v1/aidetect",
        {"key": key, "text": text, "zero_retention": True},
        {},
    )
    return float(d["score"]), d.get("verdict", "")


def binoculars(text: str, token: str | None) -> tuple[float, str]:
    """The Binoculars authors' hosted demo (Gradio). Returns 1.0 for 'AI' and 0.0 for 'human',
    with the demo's own label, since the demo reports a decision rather than a probability."""
    base = "https://tomg-group-umd-binoculars.hf.space/call/run_detector"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    ev = post_json(base, {"data": [text]}, headers)
    stream = request(f"{base}/{ev['event_id']}", headers=headers, timeout=180)
    data = [ln[5:].strip() for ln in stream.splitlines() if ln.startswith("data:")]
    result = json.loads(data[-1]) if data else None
    if not result:
        raise RuntimeError(
            "the demo returned no result (busy, or its free GPU quota is used up)"
        )
    label = result[0]
    ai = bool(
        re.search(r"\b(AI|machine)\b", str(label), re.IGNORECASE)
    ) and not re.search(r"human", str(label), re.IGNORECASE)
    return (1.0 if ai else 0.0), str(label)


PROVIDERS = {
    "pangram": pangram,
    "gptzero": gptzero,
    "sapling": sapling,
    "binoculars": binoculars,
}


def status(approvals: dict) -> None:
    """Print which keys are set and which services the user approved; sends nothing."""
    for t, env in KEYS.items():
        print(
            f"{t:<11} key {'set' if os.environ.get(env) else 'missing'} ({env}); "
            f"approved by the user: {approvals.get(t, 'no')}"
        )


def say(**row: object) -> None:
    """Print one JSON status line."""
    print(json.dumps(row), flush=True)


def run_tool(tool_id: str, scan: Scan, units: list[dict]) -> None:
    """Send each unit to one service; stop using it when its quota is reached."""
    key = os.environ.get(KEYS[tool_id])
    if not key and tool_id != "binoculars":
        say(tool=tool_id, status="no-key", why=f"set {KEYS[tool_id]}")
        return
    for u in units:
        text = Path(u["file"]).read_text(encoding="utf-8")
        try:
            score, label = PROVIDERS[tool_id](text, key)
        except Exception as ex:  # noqa: BLE001 - report and continue
            say(tool=tool_id, chunk=u["chunk"], status="error", why=str(ex)[:200])
            if "402" in str(ex) or "429" in str(ex):
                return  # quota reached
            continue
        row = {
            "tool": tool_id,
            "chunk": u["chunk"],
            "status": "done",
            "score": round(score, 4),
            "label": label,
        }
        scan.save({**row, "note": "api"})
        say(**row)
        time.sleep(1)


def main(argv: list[str] | None = None) -> int:
    """Run the requested API detectors over the prepared units."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--tools", default="pangram,gptzero,sapling,binoculars")
    p.add_argument(
        "--chunks",
        help="comma-separated unit ids or scales (P, S, W); default: the passages",
    )
    p.add_argument(
        "--plan",
        help="JSON {units: [{chunk, file}]} to scan instead of the document's plan",
    )
    p.add_argument(
        "--log", help="JSONL to append results to (default: <plan>.results.jsonl)"
    )
    p.add_argument("--status", action="store_true")
    p.add_argument(
        "--approved",
        help="comma-separated services the user has just approved (recorded)",
    )
    args = p.parse_args(argv)
    approvals = read_json(APPROVALS) or {}
    if args.approved:
        for t in args.approved.split(","):
            approvals[t] = today()
        write_json(APPROVALS, approvals)
    if args.status:
        status(approvals)
        return 0
    scan = Scan.load(Path(args.work), args.plan, args.log)
    for t in args.tools.split(","):
        if t not in PROVIDERS:
            die(f"unknown API tool {t}")
        if t not in approvals:
            say(
                tool=t,
                status="not-approved",
                why="ask the user before sending text to this service",
            )
            continue
        report_left_out(scan, args.chunks, t)
        run_tool(t, scan, scan.select(args.chunks, tool(t)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
