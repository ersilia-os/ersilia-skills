"""The web detectors: the registry (references/web_detectors.json), how to read their
result pages, what their highlight colours mean, and where scores are kept.

Scores are kept the same way for every text the detectors see:

* a **plan**: a JSON file whose ``units`` each have an id (``chunk``) and a text file.
  For the document it is ``<work>/plan.json`` (segments.py): sections S1.., passages
  P1.. and overlapping windows W1... For the known texts it is controls.json and its
  siblings (web_controls.py).
* its **results**: ``<plan>.results.jsonl`` next to it, one row per scan. A row with a
  ``score`` is a result, and the latest per tool and unit wins. A row with status
  ``skipped`` says a tool could not be used.
* its **pages**: what each site showed, in ``<work>/<plan name>/``.

``Scan`` is what the runners (browser_detect.py, api_detectors.py) write through;
``Detections`` is what grading, the report and the ledger read.
"""

from __future__ import annotations

import colorsys
import functools
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from lib.common import REFS, append_jsonl, die, read_json, read_jsonl


@functools.cache
def registry() -> dict:
    """references/web_detectors.json."""
    return read_json(REFS / "web_detectors.json") or die(
        "missing references/web_detectors.json"
    )


@functools.cache
def tools() -> dict[str, dict]:
    """Every detector in the registry, by id."""
    return {t["id"]: t for t in registry()["tools"]}


def unattended() -> list[str]:
    """The tools the skill runs by itself (``"use": "unattended"``), in the registry's
    order: no login, key or CAPTCHA."""
    return [
        t for t in registry()["default_order"] if tool(t).get("use") == "unattended"
    ]


def tool(tool_id: str) -> dict:
    """One detector's registry entry; {} when the id is unknown."""
    return tools().get(tool_id, {})


def results_path(plan: str | Path) -> Path:
    """Where a plan's results are kept: next to it, as <plan>.results.jsonl."""
    return Path(str(plan).removesuffix(".json") + ".results.jsonl")


def fits(unit: dict, limits: dict) -> bool:
    """Whether a unit is within a tool's size range (its registry entry)."""
    lo = limits.get("min_words") or 80
    hi = limits.get("max_words") or 2000
    return lo <= unit["n_words"] <= hi


@dataclass
class Scan:
    """What a runner sends to the detectors, and where the rows go."""

    work: Path
    plan: Path
    units: list[dict]  # each with "chunk" (its id) and "file" (its text)
    log: Path  # the JSONL that receives every row

    @classmethod
    def load(cls, work: Path, plan: str | None = None, log: str | None = None) -> Scan:
        """The units of ``plan`` (default: the document's plan)."""
        path = Path(plan) if plan else work / "plan.json"
        data = read_json(path) or die(
            f"cannot read {path}" if plan else "run `segments.py` first"
        )
        return cls(work, path, data["units"], Path(log) if log else results_path(path))

    @property
    def pages(self) -> Path:
        """The folder for the result pages the sites showed."""
        return self.work / self.plan.stem

    def select(self, chunks: str | None, limits: dict | None = None) -> list[dict]:
        """The units to scan. ``chunks`` is a comma-separated list of unit ids or of
        scales (``P``, ``S``, ``W``: every unit of that scale). By default the passages
        of the document's plan, and every unit of any other plan. With ``limits`` (a
        tool's registry entry), the document's units outside its size range are left out."""
        scaled = any("scale" in u for u in self.units)
        wanted = set(chunks.split(",")) if chunks else ({"P"} if scaled else None)
        return [
            u
            for u in self.units
            if (not wanted or u["chunk"] in wanted or u.get("scale") in wanted)
            and (not limits or "scale" not in u or fits(u, limits))
        ]

    def save(self, row: dict) -> None:
        """Keep one row."""
        append_jsonl(self.log, {**row, "date": time.strftime("%Y-%m-%d %H:%M")})


def report_left_out(scan: Scan, chunks: str | None, tool_id: str) -> None:
    """Print which of the requested units a tool will not get, being outside its size range."""
    kept = {u["chunk"] for u in scan.select(chunks, tool(tool_id))}
    left = [u["chunk"] for u in scan.select(chunks) if u["chunk"] not in kept]
    if left:
        print(
            json.dumps(
                {
                    "tool": tool_id,
                    "status": "left-out",
                    "chunks": left,
                    "why": "outside the tool's size range (min_words, max_words)",
                }
            ),
            flush=True,
        )


@dataclass
class Detections:
    """What the detectors said about the document."""

    work: Path
    plan: dict  # {"units": [...], "sentences": [...]}; empty when nothing was planned
    scores: dict[tuple[str, str], float]  # latest score per (tool, unit id)
    skipped: list[dict]  # tools that could not be used: {"tool", "why"}

    @classmethod
    def load(cls, work: Path) -> Detections:
        """Read the document's plan and its results (missing files read as empty)."""
        plan = read_json(work / "plan.json") or {"units": [], "sentences": []}
        rows = read_jsonl(results_path(work / "plan.json"))
        return cls(
            work,
            plan,
            {
                (r["tool"], str(r["chunk"])): float(r["score"])
                for r in rows
                if r.get("score") is not None
            },
            [r for r in rows if r.get("status") == "skipped"],
        )

    @property
    def passages(self) -> list[dict]:
        """The plan's passages (P units), in reading order."""
        return [u for u in self.plan["units"] if u.get("scale") == "P"]

    def passage_scores(self) -> dict[str, dict[str, float]]:
        """{passage id: {tool: score}} for the passages that were scored."""
        ids = {u["chunk"] for u in self.passages}
        out: dict[str, dict[str, float]] = {}
        for (tid, uid), score in self.scores.items():
            if uid in ids:
                out.setdefault(uid, {})[tid] = score
        return out

    def summary(self) -> dict:
        """Per tool, over the passages: how many it flags (score >= 0.5), the share of
        the words it scanned that are in flagged passages, its mean score, and how much
        of the text it covered."""
        size = {u["chunk"]: u["n_words"] for u in self.passages}
        by_tool: dict[str, dict[str, float]] = {}
        for uid, scores in self.passage_scores().items():
            for tid, score in scores.items():
                by_tool.setdefault(tid, {})[uid] = score
        out = {}
        for tid, rs in sorted(by_tool.items()):
            words = sum(size[k] for k in rs)
            flagged = [k for k, score in rs.items() if score >= 0.5]
            out[tid] = {
                "name": tool(tid).get("name", tid),
                "weight": tool(tid).get("weight", "context"),
                "passages": len(rs),
                "passages_flagged": len(flagged),
                "share_words_flagged": round(sum(size[k] for k in flagged) / words, 2)
                if words
                else 0,
                "mean_score": round(sum(rs.values()) / len(rs), 2),
                "coverage": round(words / sum(size.values()), 2),
                "by_passage": dict(sorted(rs.items(), key=lambda kv: int(kv[0][1:]))),
            }
        return out

    def site_marks(self) -> list[dict]:
        """Sentences the sites themselves highlighted as AI: {"tool", "chunk", "text"},
        from the saved pages of every scan that has a score."""
        out = []
        folder = self.work / "plan"
        for f in sorted(folder.glob("*_chunk*_highlights.json")):
            tid, _, rest = f.name.rpartition("_chunk")
            uid = rest.removesuffix("_highlights.json")
            if (tid, uid) not in self.scores:
                continue
            out += [
                {"tool": tid, "chunk": uid, "text": h["text"]}
                for h in read_json(f) or []
                if marks_ai(tid, h.get("bg", ""))
            ]
        return out


def parse_score(tool_id: str, result_text: str) -> tuple[float | None, str]:
    """(AI likelihood 0-1, site's verdict line) from a result page, using the site's
    parser in web_detectors.json; (None, "") when the page does not match."""
    rule = tool(tool_id).get("parse")
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
    return tool(tool_id).get("marks_ai", True) and is_ai_colour(css)


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
