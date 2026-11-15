"""Run detectors that have an API, so no browser and no CAPTCHA are involved.

Results go into the same <work>/web_detectors.json as the browser route, under the same tool
ids, so grading and the report treat them alike. Each provider needs the user's own key in
an environment variable. The skill never creates accounts or keys.

    pangram       PANGRAM_API_KEY   validated. Free research credits on application
                  (https://pangram.com/solutions/api); otherwise $0.05 per 100 words.
    gptzero       GPTZERO_API_KEY   validated. Paid API; ask for research credits.
    sapling       SAPLING_API_KEY   context. Free key: 50,000 characters a day, 250,000 a month.
    binoculars    HF_TOKEN (optional)  context. The authors' hosted demo on Hugging Face
                  (tomg-group-umd/Binoculars); nothing is downloaded; free GPU quota.

Sending text to any of these uploads it. The same rules as the browser route apply
(SKILL.md, step 2b): never for a manuscript or grant the user is reviewing, and only after the
user has approved that service at least once (``--approved`` records it in the ledger dir).

Usage:
    python api_detectors.py --tools pangram,sapling [--chunks 1,2]
    python api_detectors.py --status          # which keys are set; sends nothing
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from _common import LOCAL, USER_AGENT, WORK_DIR, die, read_json, write_json

APPROVALS = LOCAL / "approved_services.json"
KEYS = {
    "pangram": "PANGRAM_API_KEY",
    "gptzero": "GPTZERO_API_KEY",
    "sapling": "SAPLING_API_KEY",
    "binoculars": "HF_TOKEN",
}


def post(url: str, body: dict, headers: dict, timeout: int = 120) -> dict:
    """POST JSON, return JSON (raises on HTTP errors with the body's message)."""
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            **headers,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
        ) from e


def pangram(text: str, key: str) -> tuple[float, str]:
    """AI fraction of the text (0-1) and a label."""
    d = post("https://text.api.pangram.com/v3", {"text": text}, {"x-api-key": key})
    frac = d.get("fraction_ai")
    if frac is None:
        raise RuntimeError(f"unexpected response: {str(d)[:200]}")
    frac = float(frac) + float(d.get("fraction_ai_assisted") or 0)
    return min(frac, 1.0), d.get("prediction") or d.get("headline") or ""


def gptzero(text: str, key: str) -> tuple[float, str]:
    """Probability the document is AI-generated (AI + mixed) and the classification."""
    d = post(
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
    d = post(
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
    ev = post(base, {"data": [text]}, headers)
    req = urllib.request.Request(
        f"{base}/{ev['event_id']}", headers={"User-Agent": USER_AGENT, **headers}
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        stream = r.read().decode()
    data = [ln[5:].strip() for ln in stream.splitlines() if ln.startswith("data:")]
    label = json.loads(data[-1])[0] if data else ""
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


def main(argv: list[str] | None = None) -> int:
    """Run the requested API detectors over the prepared chunks."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--tools", default="pangram,gptzero,sapling,binoculars")
    p.add_argument("--chunks")
    p.add_argument("--status", action="store_true")
    p.add_argument(
        "--approved",
        help="comma-separated services the user has just approved (recorded)",
    )
    args = p.parse_args(argv)
    approvals = read_json(APPROVALS) or {}
    if args.approved:
        for t in args.approved.split(","):
            approvals[t] = date.today().isoformat()
        write_json(APPROVALS, approvals)
    if args.status:
        for t, env in KEYS.items():
            print(
                f"{t:<11} key {'set' if os.environ.get(env) else 'missing'} ({env}); "
                f"approved by the user: {approvals.get(t, 'no')}"
            )
        return 0
    work = Path(args.work)
    st = read_json(work / "web_detectors.json") or die(
        "run `web_detectors.py prepare` first"
    )
    wanted = {int(x) for x in args.chunks.split(",")} if args.chunks else None
    for t in args.tools.split(","):
        if t not in PROVIDERS:
            die(f"unknown API tool {t}")
        if t not in approvals:
            print(
                json.dumps(
                    {
                        "tool": t,
                        "status": "not-approved",
                        "why": "ask the user before sending text to this service",
                    }
                )
            )
            continue
        key = os.environ.get(KEYS[t])
        if not key and t != "binoculars":
            print(json.dumps({"tool": t, "status": "no-key", "why": f"set {KEYS[t]}"}))
            continue
        for c in st["chunks"]:
            if wanted and c["chunk"] not in wanted:
                continue
            text = Path(c["file"]).read_text(encoding="utf-8")
            try:
                score, label = PROVIDERS[t](text, key)
            except Exception as ex:  # noqa: BLE001 - report and continue
                print(
                    json.dumps(
                        {
                            "tool": t,
                            "chunk": c["chunk"],
                            "status": "error",
                            "why": str(ex)[:200],
                        }
                    ),
                    flush=True,
                )
                if "402" in str(ex) or "429" in str(ex):
                    break  # quota reached: stop using this service
                continue
            st["results"].append(
                {
                    "tool": t,
                    "chunk": c["chunk"],
                    "score": round(score, 4),
                    "label": label,
                    "note": "api",
                    "date": date.today().isoformat(),
                }
            )
            write_json(work / "web_detectors.json", st)
            print(
                json.dumps(
                    {
                        "tool": t,
                        "chunk": c["chunk"],
                        "status": "done",
                        "score": round(score, 4),
                        "label": label,
                    }
                ),
                flush=True,
            )
            time.sleep(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
