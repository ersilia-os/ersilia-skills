"""The web detectors: the registry (references/web_detectors.json), how to read their
result pages, what their highlight colours mean, and the per-document results state
(<work>/web_detectors.json)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from lib.common import REFS, die, read_json, write_json


def registry() -> dict:
    """references/web_detectors.json."""
    return read_json(REFS / "web_detectors.json") or die(
        "missing references/web_detectors.json"
    )


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


def marks_ai(tool_id: str, css: str) -> bool:
    """Whether a site's highlight on a sentence means 'AI': the site must use its colours
    for that (``"marks_ai": false`` in the registry when its shading carries no verdict),
    and the colour must not be a human green."""
    tool = next((t for t in registry()["tools"] if t["id"] == tool_id), {})
    return tool.get("marks_ai", True) and is_ai_colour(css)


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
            if marks_ai(m.group(1), h.get("bg", "")):
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
