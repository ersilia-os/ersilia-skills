"""The private case ledger: how the skill learns from the user's real documents.

Every analysis is recorded as a *case*. A case holds numbers and identifiers only: per-window
web-detector scores and stylometric features, which markers fired, the verdict, and later the
user's feedback. It never holds the document text, names, or titles, so it can stay on
this machine (~/.ai-text-detection/), outside the repository.

Feedback arrives at three moments, and each one is recorded here:

    finding   right after the evidence is shown: is this hit valid or a false alarm?
    verdict   after the report: did the overall tier feel right (too high / right / too low)?
    outcome   whenever the truth is known (author admits or denies, editor confirms, the
              user's own settled judgement): ai | human | mixed, and how it is known

``stats`` turns that into: precision of each marker, how verdict tiers matched outcomes,
markers that should be demoted, and whether enough labelled cases exist to re-calibrate
(``calibrate.py --with-local``). ``pending`` lists cases still waiting for an outcome, so
the skill can ask about them at the start of every run.

Usage:
    python ledger.py record --case 2026-11-review-r2 --kind review --context reviewer-of-my-paper
    python ledger.py finding --case ID --hit a3 --verdict valid|false-alarm [--note "..."]
    python ledger.py verdict --case ID --feel too-high|right|too-low [--note "..."]
    python ledger.py outcome --case ID --label ai|human|mixed --how "author confirmed by email"
    python ledger.py pending
    python ledger.py stats
"""

from __future__ import annotations

import argparse
import sys

from lib.common import (
    CONTEXTS,
    KINDS,
    LOCAL,
    WORK_DIR,
    die,
    read_json,
    read_jsonl,
    today,
    write_json,
    write_jsonl,
)
from lib.detectors import Detections
from lib.style import FEATURES

# One row per window (style features, and the label once the outcome is known), for
# calibrate.py --with-local.
CASES = LOCAL / "cases.jsonl"
# One entry per case: metadata, hits, verdict, feedback.
INDEX = LOCAL / "index.json"


def load_index() -> dict:
    """The case index."""
    return read_json(INDEX) or {"cases": {}}


def cmd_record(args: argparse.Namespace) -> None:
    """Snapshot the current work folder as a case (numbers only)."""
    work = WORK_DIR
    idx = load_index()
    if args.case in idx["cases"] and not args.force:
        die(f"case {args.case} exists; use --force to overwrite")
    grade = read_json(work / "grade.json") or {}
    arts = read_json(work / "artifacts.json") or {"hits": []}
    refs = read_json(work / "references.json") or {"counts": {}}
    sty = read_json(work / "stylometry.json") or {"windows": []}
    text = read_json(work / "text.json") or {}
    idx["cases"][args.case] = {
        "date": today(),
        "kind": args.kind,
        "context": args.context,
        "format": text.get("format"),
        "n_words": text.get("n_words"),
        "verdict": grade.get("tier"),
        "attribution": grade.get("attribution"),
        "hits": [
            {"id": h["id"], "marker": h["marker"], "tier": h["tier"]}
            for h in arts["hits"]
        ],
        "references": refs.get("counts"),
        "web": {
            k: {
                kk: v.get(kk)
                for kk in ("weight", "mean_score", "share_words_flagged", "coverage")
            }
            for k, v in Detections.load(work).summary().items()
        },
        "findings": {},
        "verdict_feedback": None,
        "outcome": None,
    }
    write_json(INDEX, idx)
    # Window rows for re-calibration; the label is filled in when the outcome is known.
    keep = [r for r in read_jsonl(CASES) if r.get("case") != args.case]
    for w in sty.get("windows", []):
        keep.append(
            {
                "case": args.case,
                "window": w["id"],
                "kind": args.kind,
                "label": None,
                **{k: w.get(k) for k in FEATURES},
            }
        )
    write_jsonl(CASES, keep)
    print(
        f"recorded case {args.case}: verdict {grade.get('tier')}, {len(arts['hits'])} marker hit(s), "
        f"{len(sty.get('windows', []))} window(s). Stored in {LOCAL} (numbers only, no text)."
    )


def need(idx: dict, case: str) -> dict:
    """The case entry, or exit."""
    if case not in idx["cases"]:
        die(f"no case {case}; `ledger.py pending` lists them")
    return idx["cases"][case]


def cmd_finding(args: argparse.Namespace) -> None:
    """Record whether one hit was valid."""
    idx = load_index()
    c = need(idx, args.case)
    if args.hit not in {h["id"] for h in c["hits"]}:
        die(f"case {args.case} has no hit {args.hit}")
    c["findings"][args.hit] = {
        "verdict": args.verdict,
        "note": args.note,
        "date": today(),
    }
    write_json(INDEX, idx)
    print(f"{args.case} {args.hit}: {args.verdict}")


def cmd_verdict(args: argparse.Namespace) -> None:
    """Record how the overall verdict felt."""
    idx = load_index()
    need(idx, args.case)["verdict_feedback"] = {
        "feel": args.feel,
        "note": args.note,
        "date": today(),
    }
    write_json(INDEX, idx)
    print(f"{args.case}: verdict felt {args.feel}")


def cmd_outcome(args: argparse.Namespace) -> None:
    """Record the ground truth and label the case's windows."""
    idx = load_index()
    need(idx, args.case)["outcome"] = {
        "label": args.label,
        "how": args.how,
        "date": today(),
    }
    write_json(INDEX, idx)
    # A mixed case stays unlabelled for calibration.
    label = {"ai": 1, "human": 0}.get(args.label)
    rows = read_jsonl(CASES)
    for r in rows:
        if r["case"] == args.case:
            r["label"] = label
    write_jsonl(CASES, rows)
    print(f"{args.case}: outcome {args.label} ({args.how})")


def cmd_pending(_: argparse.Namespace) -> None:
    """Cases still waiting for feedback."""
    idx = load_index()
    rows = [(k, c) for k, c in idx["cases"].items() if not c.get("outcome")]
    if not rows:
        print("no cases waiting for an outcome")
    for k, c in sorted(rows, key=lambda kc: kc[1]["date"]):
        missing = []
        unreviewed = [
            h["id"]
            for h in c["hits"]
            if h["tier"] in ("conclusive", "strong") and h["id"] not in c["findings"]
        ]
        if unreviewed:
            missing.append(f"findings {','.join(unreviewed)}")
        if not c.get("verdict_feedback"):
            missing.append("verdict feel")
        missing.append("outcome")
        print(
            f"{k} ({c['date']}, {c['kind']}, verdict {c['verdict']}): waiting for {'; '.join(missing)}"
        )


def cmd_stats(_: argparse.Namespace) -> None:
    """Marker precision, verdict accuracy, and what to change."""
    idx = load_index()
    cases = idx["cases"]
    print(
        f"{len(cases)} case(s); {sum(1 for c in cases.values() if c.get('outcome'))} with an outcome"
    )
    marker: dict[str, dict[str, int]] = {}
    for c in cases.values():
        out = (c.get("outcome") or {}).get("label")
        for h in c["hits"]:
            m = marker.setdefault(
                h["marker"],
                {"hits": 0, "valid": 0, "false_alarm": 0, "in_human_cases": 0},
            )
            m["hits"] += 1
            v = (c["findings"].get(h["id"]) or {}).get("verdict")
            if v == "valid":
                m["valid"] += 1
            elif v == "false-alarm":
                m["false_alarm"] += 1
            if out == "human":
                m["in_human_cases"] += 1
    if marker:
        print("\nmarker precision (user-reviewed hits):")
        for k, m in sorted(marker.items(), key=lambda kv: -kv[1]["hits"]):
            reviewed = m["valid"] + m["false_alarm"]
            prec = f"{m['valid'] / reviewed:.0%}" if reviewed else "n/a"
            print(
                f"  {k:<22} hits {m['hits']:>3}  reviewed {reviewed:>3}  precision {prec:>5}  in human-outcome cases {m['in_human_cases']}"
            )
            if m["false_alarm"] >= 2 or m["in_human_cases"] >= 2:
                print(
                    f"    -> SUGGEST: demote or narrow '{k}' in references/markers.json (add the false alarms as negative examples)"
                )
    tiers: dict[str, dict[str, int]] = {}
    for c in cases.values():
        out = (c.get("outcome") or {}).get("label")
        if out:
            t = tiers.setdefault(c["verdict"] or "?", {})
            t[out] = t.get(out, 0) + 1
    if tiers:
        print("\nverdict tier vs outcome:")
        for t, d in tiers.items():
            print(f"  {t:<14} " + ", ".join(f"{k} {v}" for k, v in d.items()))
            if t in ("conclusive", "strong") and d.get("human"):
                print(
                    f"    -> REVIEW: a '{t}' verdict on a human-written case; check grading.json and that case's hits"
                )
    feel: dict[str, int] = {}
    for c in cases.values():
        f = (c.get("verdict_feedback") or {}).get("feel")
        if f:
            feel[f] = feel.get(f, 0) + 1
    if feel:
        print("\nhow verdicts felt: " + ", ".join(f"{k} {v}" for k, v in feel.items()))
        if feel.get("too-high", 0) >= 2 or feel.get("too-low", 0) >= 2:
            print(
                "    -> SUGGEST: revisit references/grading.json; log the change with record_feedback.py"
            )
    labelled = {r["case"] for r in read_jsonl(CASES) if r.get("label") in (0, 1)}
    print(f"\nlabelled cases usable for re-calibration: {len(labelled)}")
    if len(labelled) >= 3:
        print(
            "    -> SUGGEST: python calibrate.py --with-local   (then compare validation.md before/after)"
        )


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument(
        "--case", required=True, help="a neutral label, never a person's name"
    )
    r.add_argument("--kind", required=True, choices=KINDS)
    r.add_argument("--context", default="other", choices=CONTEXTS)
    r.add_argument("--force", action="store_true")
    f = sub.add_parser("finding")
    f.add_argument("--case", required=True)
    f.add_argument("--hit", required=True)
    f.add_argument("--verdict", required=True, choices=["valid", "false-alarm"])
    f.add_argument("--note")
    v = sub.add_parser("verdict")
    v.add_argument("--case", required=True)
    v.add_argument("--feel", required=True, choices=["too-high", "right", "too-low"])
    v.add_argument("--note")
    o = sub.add_parser("outcome")
    o.add_argument("--case", required=True)
    o.add_argument("--label", required=True, choices=["ai", "human", "mixed"])
    o.add_argument("--how", required=True)
    sub.add_parser("pending")
    sub.add_parser("stats")
    args = p.parse_args(argv)
    {
        "record": cmd_record,
        "finding": cmd_finding,
        "verdict": cmd_verdict,
        "outcome": cmd_outcome,
        "pending": cmd_pending,
        "stats": cmd_stats,
    }[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
