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


NON_PROSE = re.compile(
    r"^(?:fig(?:ure)?\.?\s*\d|table\s*\d|eq\.?\s*\d|eq\d|supplementary|orcid|\*?corresponding author|keywords?:)",
    re.IGNORECASE,
)


def is_prose(par: str) -> bool:
    """Whether a paragraph is running prose worth sending to a detector.

    Excluded: headings, author lists and affiliations, ORCIDs and e-mails, figure and
    table captions, equation labels, table rows, and anything mostly numbers.
    """
    from _common import words

    t = par.strip()
    w = words(t)
    if len(w) < 12 or NON_PROSE.match(t):
        return False
    if re.search(
        r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b|@|\|", t
    ):  # ORCID, e-mail, table row
        return False
    if t.count(",") > 4 and len(re.findall(r"\d", t)) > len(
        w
    ):  # author list with affiliation numbers
        return False
    if (
        len(w) < 60
        and t.count(",") >= 2
        and re.search(
            r"\b(University|Institute|Department|Centre|Center|Faculty|School of|Laboratory|Hospital)\b",
            t,
        )
    ):  # affiliation
        return False
    tokens = t.split()
    alpha = sum(1 for x in tokens if re.search(r"[A-Za-z]{3,}", x))
    return (
        alpha / max(len(tokens), 1) >= 0.6 and t[-1:] in '.?!)\u201d"' or len(w) >= 40
    )


def build_passages(doc: dict, lo: int = 250, hi: int = 600) -> list[dict]:
    """Passages a detector can judge: runs of whole prose paragraphs from one section,
    aiming at (lo+hi)/2 words. Paragraphs that are not prose (is_prose) are left out; the
    title page is never included; a section under ~150 words joins the previous passage
    when the result stays under ``hi`` words, and the label names both sections."""
    from _common import SKIP_SECTIONS, words

    text = doc["text"]
    passages: list[dict] = []
    for sec in doc.get("sections") or [
        {"title": "(whole text)", "start": 0, "end": len(text)}
    ]:
        if sec["title"].lower() in SKIP_SECTIONS:
            continue
        cur: dict | None = None
        pos = sec["start"]
        for m in [*re.finditer(r"\n\s*\n", text[sec["start"] : sec["end"]]), None]:
            end = sec["start"] + m.start() if m else sec["end"]
            par = text[pos:end]
            p0 = pos + (len(par) - len(par.lstrip()))
            pos = sec["start"] + m.end() if m else sec["end"]
            if not is_prose(par):
                continue
            n = len(words(par))
            if cur and cur["n_words"] + n > (lo + hi) // 2 and cur["n_words"] >= lo:
                passages.append(cur)
                cur = None
            if cur is None:
                cur = {
                    "sections": [sec["title"]],
                    "start": p0,
                    "end": end,
                    "n_words": 0,
                    "paras": [],
                }
            cur["paras"].append([p0, end])
            cur["end"] = end
            cur["n_words"] += n
        if cur:
            if sec["title"] == "(start)" and cur["n_words"] < 150:
                continue  # front matter (title page): never sent
            if (
                cur["n_words"] < 150
                and passages
                and passages[-1]["n_words"] + cur["n_words"] <= hi
            ):
                prev = passages[-1]
                prev["paras"] += cur["paras"]
                prev["end"] = cur["end"]
                prev["n_words"] += cur["n_words"]
                if cur["sections"][0] not in prev["sections"]:
                    prev["sections"].append(cur["sections"][0])
            else:
                passages.append(cur)
    return passages


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


def record_result(
    work: Path, tool: str, chunk, score: float, label: str, note: str = "parsed"
) -> None:
    """Append one result to the draft's web_detectors.json (the latest per tool and passage wins)."""
    st = read_json(work / "web_detectors.json") or {
        "chunks": [],
        "results": [],
        "skipped": [],
    }
    st.setdefault("results", []).append(
        {
            "tool": tool,
            "chunk": chunk,
            "score": round(score, 4),
            "label": label,
            "note": note,
            "date": date.today().isoformat(),
        }
    )
    write_json(work / "web_detectors.json", st)


def parse_score(tool_id: str, result_text: str) -> tuple[float | None, str]:
    """(AI likelihood 0-1, site's verdict line) from a result page, using the site's
    parser in web_detectors.json; (None, "") when the page does not match."""
    tool = next((t for t in registry()["tools"] if t["id"] == tool_id), {})
    rule = tool.get("parse")
    if not rule:
        return None, ""
    m = re.search(rule["score"], result_text or "")
    if not m:
        return None, ""
    v = float(m.group(1)) / float(rule.get("scale", 1))
    if rule.get("invert"):
        v = 1 - v
    lab = re.search(rule.get("label", r"$^"), result_text or "")
    return max(0.0, min(1.0, v)), (lab.group(1).strip() if lab else "")


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
