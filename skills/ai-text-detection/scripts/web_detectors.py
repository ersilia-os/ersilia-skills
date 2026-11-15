"""Run web AI-text detectors chunk by chunk, through Claude in Chrome, and keep the results.

Many detectors (Pangram, GPTZero, ...) offer a free web checker but no free API. The user
used to paste chunks by hand. With Claude in Chrome connected (``/chrome`` in Claude Code),
Claude does it in the user's own browser session: this script prepares the chunks, records
what each site reports, and summarises it for grade.py and the report.

    prepare             cut the scored windows into chunks the sites accept (250-600
                        words), one file each in <work>/web/, and print the plan
    record --tool ID --chunk K --score 0.93 [--label "AI"] [--note "..."]
                        store one site's result for one chunk (score: AI likelihood 0-1)
    skip --tool ID --why "free limit reached"
                        note that a site could not be used, so the report says so
    summary             per tool: chunks and words flagged (score >= 0.5), mean score

Tools, their evidence and how to read their output: references/web_detectors.json.
Results: <work>/web_detectors.json.

Usage:
    python web_detectors.py prepare
    python web_detectors.py record --tool gptzero --chunk 2 --score 0.98 --label "AI"
    python web_detectors.py summary
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from _common import REFS, WORK_DIR, chunks, die, load_text, read_json, write_json


def registry() -> dict:
    """references/web_detectors.json."""
    return read_json(REFS / "web_detectors.json") or die(
        "missing references/web_detectors.json"
    )


def prepare(work: Path) -> dict:
    """Group consecutive windows (same section first) into chunks of 250-600 words."""
    reg = registry()
    lo, hi = reg["chunk_words"]
    doc = load_text(work)
    wins = chunks(doc)
    groups: list[list[dict]] = []
    for w in wins:
        cur = groups[-1] if groups else None
        n = sum(x["n_words"] for x in cur) if cur else 0
        if (
            cur
            and n < lo
            or (cur and n + w["n_words"] <= hi and cur[-1]["section"] == w["section"])
        ):
            cur.append(w)
        else:
            groups.append([w])
    # A short last chunk joins the previous one.
    if len(groups) > 1 and sum(x["n_words"] for x in groups[-1]) < lo:
        last = groups.pop()
        groups[-1] += last
    out = work / "web"
    out.mkdir(parents=True, exist_ok=True)
    plan = []
    for k, g in enumerate(groups, 1):
        a, b = g[0]["start"], g[-1]["end"]
        text = doc["text"][a:b].strip()
        (out / f"chunk_{k}.txt").write_text(text, encoding="utf-8")
        plan.append(
            {
                "chunk": k,
                "windows": [w["id"] for w in g],
                "start": a,
                "end": b,
                "n_words": sum(w["n_words"] for w in g),
                "sections": sorted({w["section"] for w in g}),
                "file": str(out / f"chunk_{k}.txt"),
            }
        )
    state = read_json(work / "web_detectors.json") or {}
    state.update(
        {
            "chunks": plan,
            "results": state.get("results", []),
            "skipped": state.get("skipped", []),
        }
    )
    write_json(work / "web_detectors.json", state)
    return state


def summary(state: dict) -> dict:
    """Per tool: chunks and words flagged, mean score, weight."""
    reg = {t["id"]: t for t in registry()["tools"]}
    size = {c["chunk"]: c["n_words"] for c in state.get("chunks", [])}
    out = {}
    for tool in sorted({r["tool"] for r in state.get("results", [])}):
        rs = {
            r["chunk"]: r for r in state["results"] if r["tool"] == tool
        }  # last result per chunk wins
        words = sum(size.get(k, 0) for k in rs)
        flagged = [k for k, r in rs.items() if r["score"] >= 0.5]
        out[tool] = {
            "name": reg.get(tool, {}).get("name", tool),
            "weight": reg.get(tool, {}).get("weight", "context"),
            "chunks": len(rs),
            "chunks_flagged": len(flagged),
            "share_words_flagged": round(
                sum(size.get(k, 0) for k in flagged) / words, 2
            )
            if words
            else 0,
            "mean_score": round(sum(r["score"] for r in rs.values()) / len(rs), 2)
            if rs
            else None,
            "coverage": round(words / sum(size.values()), 2) if size else 0,
            "by_chunk": {str(k): r["score"] for k, r in sorted(rs.items())},
        }
    return out


def is_ai_colour(css: str) -> bool:
    """Whether a highlight colour means 'AI'. Sites mark human sentences green (hue
    roughly 80-170 degrees) and AI sentences red, orange, yellow, pink or purple."""
    import colorsys

    nums = [float(x) for x in re.findall(r"[\d.]+", css or "")]
    if len(nums) < 3:
        return True
    r, g, b = (x / 255 for x in nums[:3])
    h, _light, sat = colorsys.rgb_to_hls(r, g, b)
    hue = h * 360
    return not (80 <= hue <= 170 and sat > 0.15)


def collect_highlights(work: Path, state: dict) -> list[dict]:
    """Sentences each site marked as AI, from browser_detect.py's per-chunk files, for
    tools and chunks that have a recorded result."""
    done = {(r["tool"], r["chunk"]) for r in state.get("results", [])}
    out = []
    for f in sorted((work / "web").glob("*_chunk*_highlights.json")):
        m = re.match(r"(.+)_chunk(\d+)_highlights\.json$", f.name)
        if not m or (m.group(1), int(m.group(2))) not in done:
            continue
        for h in read_json(f) or []:
            out.append(
                {"tool": m.group(1), "chunk": int(m.group(2)), "text": h["text"]}
            )
    return out


def consensus(summ: dict) -> dict | None:
    """How many tools ran and flag the text, and how far their mean scores spread."""
    if not summ:
        return None
    means = [x["mean_score"] for x in summ.values() if x["mean_score"] is not None]
    flag = [x for x in summ.values() if x["share_words_flagged"] >= 0.5]
    valid = [x for x in summ.values() if x["weight"] == "validated"]
    return {
        "ran": len(summ),
        "flagging": len(flag),
        "validated_ran": len(valid),
        "validated_flagging": sum(1 for x in valid if x["share_words_flagged"] >= 0.5),
        "min_mean": min(means) if means else None,
        "max_mean": max(means) if means else None,
    }


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
                f"chunk {c['chunk']}: {c['n_words']} words, windows {','.join(c['windows'])} ({', '.join(c['sections'])}) -> {c['file']}"
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
