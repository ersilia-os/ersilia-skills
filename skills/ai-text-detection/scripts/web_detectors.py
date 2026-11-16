"""The per-document state of the web detectors: passages to scan and results.

The registry, parsers and colour rules live in lib/detectors.py; the passages in
lib/splits.py. This command keeps <work>/web_detectors.json:

    prepare             write the passages to <work>/web/chunk_k.txt and print the plan
    record --tool ID --chunk K --score 0.93 [--label "AI"] [--note "..."]
                        store a result read by eye (sites without a parser)
    skip --tool ID --why "free limit reached"
                        note that a site could not be used, so the report can say so
    summary             per tool: passages and words flagged (score >= 0.5), mean score;
                        the sentences each site marked as AI

Usage:
    python web_detectors.py prepare
    python web_detectors.py record --tool gptzero --chunk 2 --score 0.98 --label "AI"
    python web_detectors.py summary
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from lib.common import WORK_DIR, die, read_json, write_json
from lib.detectors import collect_highlights, consensus, registry, summary
from lib.splits import build_passages
from lib.text import chunks, load_text


def prepare(work: Path) -> dict:
    """Cut the document into passages (build_passages) and write one file per passage."""
    reg = registry()
    lo, hi = reg["chunk_words"]
    doc = load_text(work)
    text = doc["text"]
    passages = build_passages(doc, lo, hi)
    out = work / "web"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("chunk_*.txt"):
        old.unlink()
    plan = []
    for k, p in enumerate(passages, 1):
        body = "\n\n".join(text[a:b].strip() for a, b in p["paras"])
        (out / f"chunk_{k}.txt").write_text(body, encoding="utf-8")
        windows = [
            w["id"]
            for w in chunks(doc)
            if w["start"] < p["end"] and w["end"] > p["start"]
        ]
        plan.append(
            {
                "chunk": k,
                "windows": windows,
                "start": p["start"],
                "end": p["end"],
                "paras": p["paras"],
                "n_words": p["n_words"],
                "sections": p["sections"],
                "file": str(out / f"chunk_{k}.txt"),
            }
        )
    state = read_json(work / "web_detectors.json") or {}
    if state.get("chunks") and state["chunks"] != plan and state.get("results"):
        # New passage boundaries: earlier results no longer line up. Keep them aside.
        write_json(work / "web_detectors.previous.json", state)
        state = {}
    state.update(
        {
            "chunks": plan,
            "results": state.get("results", []),
            "skipped": state.get("skipped", []),
        }
    )
    write_json(work / "web_detectors.json", state)
    return state


def main(argv: list[str] | None = None) -> int:
    """Dispatch."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    r = sub.add_parser("record")
    r.add_argument("--tool", required=True)
    r.add_argument("--chunk", type=int, required=True)
    r.add_argument("--score", type=float, required=True, help="AI likelihood, 0-1")
    r.add_argument("--label", default="")
    r.add_argument("--note", default="")
    s = sub.add_parser("skip")
    s.add_argument("--tool", required=True)
    s.add_argument("--why", required=True)
    sub.add_parser("summary")
    args = p.parse_args(argv)
    work = Path(args.work)
    ids = {t["id"] for t in registry()["tools"]}

    if args.cmd == "prepare":
        st = prepare(work)
        for c in st["chunks"]:
            print(
                f"passage {c['chunk']}: {c['n_words']} words, windows {','.join(c['windows'])} ({', '.join(c['sections'])}) -> {c['file']}"
            )
        print("order: " + ", ".join(registry()["default_order"]))
        return 0
    st = read_json(work / "web_detectors.json") or die(
        "run `web_detectors.py prepare` first"
    )
    if args.cmd in ("record", "skip") and args.tool not in ids:
        die(f"unknown tool {args.tool}; add it to references/web_detectors.json first")
    if args.cmd == "record":
        if not 0 <= args.score <= 1:
            die("score must be between 0 and 1 (convert percentages)")
        if args.chunk not in {c["chunk"] for c in st["chunks"]}:
            die(f"no chunk {args.chunk}")
        st["results"].append(
            {
                "tool": args.tool,
                "chunk": args.chunk,
                "score": args.score,
                "label": args.label,
                "note": args.note,
                "date": date.today().isoformat(),
            }
        )
        write_json(work / "web_detectors.json", st)
        print(f"{args.tool} chunk {args.chunk}: {args.score:.2f} {args.label}")
    elif args.cmd == "skip":
        st["skipped"].append(
            {"tool": args.tool, "why": args.why, "date": date.today().isoformat()}
        )
        write_json(work / "web_detectors.json", st)
        print(f"{args.tool}: skipped ({args.why})")
    else:
        st["summary"] = summary(st)
        st["highlights"] = collect_highlights(work, st)
        st["consensus"] = consensus(st["summary"])
        write_json(work / "web_detectors.json", st)
        for s_ in st["summary"].values():
            print(
                f"{s_['name']:<16} [{s_['weight']}] flagged {s_['chunks_flagged']}/{s_['chunks']} chunks "
                f"({s_['share_words_flagged']:.0%} of words scanned; covered {s_.get('coverage', 0):.0%} of the text); mean {s_['mean_score']}"
            )
        c = st["consensus"]
        if c:
            print(
                f"consensus: {c['flagging']} of {c['ran']} tools flag the text ({c['validated_flagging']} of {c['validated_ran']} validated); mean scores {c['min_mean']}-{c['max_mean']}"
            )
        for s_ in st.get("skipped", []):
            print(f"{s_['tool']}: not run ({s_['why']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
