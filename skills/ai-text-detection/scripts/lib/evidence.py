"""Combine every detector, every split and the known-text tests into one picture.

For each sentence of the prose, every unit of the plan that contains it (section S,
passage P, window W) and every tool that scored that unit gives a vote: AI (score >= 0.5)
or human. A tool's votes on a sentence are averaged across splits (v = share of its units
that say AI) and turned into evidence with the tool's likelihood ratios measured on known
texts (references/web_calibration.json, from web_controls.py):

    tool evidence on a sentence = v * log(LR_flag) + (1 - v) * log(LR_clear)

A tool counts only with enough known texts and an AUROC above chance (grading.json
"combined": min_known_texts, min_auroc); otherwise it is shown but not counted.

Tools are combined by adding their evidence, each divided by how much of it the other
tools already carry:

    combined = sum_i ev_i / (1 + sum_{j != i} rho_ij * min(1, I_j / I_i))

rho_ij is how much tools i and j move together on known texts of the same class (human,
or AI), where shared mistakes show; 1 when there are too few shared texts (assume full
overlap). I_i = log(LR_flag) - log(LR_clear) is how informative tool i is. Independent
tools add up (Bayes); k copies of one tool count once; a tool that carries no
information changes nothing. ``validate`` runs the same combination on every known text.

Positive means more like the AI texts the tools were tested on, negative more like the
human ones; exp(combined) reads as "N times as likely". Passage and document values are
word-weighted means of their sentences. Stability: per tool, the share of sentences whose
verdict depends on the split.
"""

from __future__ import annotations

import math
from pathlib import Path

from lib.common import REFS, read_json, read_jsonl


def thresholds() -> tuple[int, float]:
    """(min known texts of each kind, min AUROC) for a tool to count."""
    c = (read_json(REFS / "grading.json") or {}).get("combined", {})
    return c.get("min_known_texts", 5), c.get("min_auroc", 0.6)


def load_results(work: Path) -> dict[tuple[str, str], float]:
    """Latest score per (tool, unit id): passages from web_detectors.json (chunk k is
    unit Pk), the other units from multi/plan.results.jsonl."""
    out: dict[tuple[str, str], float] = {}
    for r in (read_json(work / "web_detectors.json") or {}).get("results", []):
        out[(r["tool"], f"P{r['chunk']}")] = float(r["score"])
    for r in read_jsonl(work / "multi" / "plan.results.jsonl"):
        if r.get("score") is not None:
            out[(r["tool"], str(r["chunk"]))] = float(r["score"])
    return out


def tool_weights(cal: dict, tools: set[str]) -> dict[str, dict]:
    """Which tools count, with their log likelihood ratios, and why the others do not."""
    min_n, min_auroc = thresholds()
    out = {}
    for t in sorted(tools):
        c = (cal.get("tools") or {}).get(t)
        if not c:
            out[t] = {"used": False, "why": "not yet tested on known texts"}
        elif (c.get("n_human") or 0) < min_n or (c.get("n_ai") or 0) < min_n:
            out[t] = {
                "used": False,
                "why": f"tested on too few known texts ({c.get('n_human')} human, {c.get('n_ai')} AI)",
            }
        elif (c.get("auroc") or 0) < min_auroc:
            out[t] = {
                "used": False,
                "why": f"no better than chance on known scientific texts (AUROC {c.get('auroc')})",
            }
        else:
            out[t] = {
                "used": True,
                "log_flag": math.log(c["lr_flag"]),
                "log_clear": math.log(c["lr_clear"]),
            }
        out[t]["cal"] = c
    return out


def informativeness(w: dict) -> float:
    """How far apart a tool's two verdicts are, in log likelihood ratio."""
    return max(w["log_flag"] - w["log_clear"], 0.0)


def overlap(pairs: dict, a: str, b: str) -> float:
    """How much two tools move together on known texts (1: assume full overlap)."""
    return (pairs.get("|".join(sorted((a, b)))) or {}).get("rho", 1.0)


def combine_tools(ev: dict[str, float], weights: dict, pairs: dict) -> float:
    """Combine per-tool log evidence, discounting what other tools already carry."""
    total = 0.0
    for i, e in ev.items():
        ii = informativeness(weights[i])
        shared = (
            sum(
                overlap(pairs, i, j) * min(1.0, informativeness(weights[j]) / ii)
                for j in ev
                if j != i
            )
            if ii > 0
            else 0.0
        )
        total += e / (1 + shared)
    return total


def tool_evidence(w: dict, v: float) -> float:
    """A counted tool's log evidence from the share v of its units that say AI."""
    return v * w["log_flag"] + (1 - v) * w["log_clear"]


def validate(cal: dict) -> dict:
    """The combination run on every known text (each scored whole, as one unit): how many
    human and AI texts reach 3x, 10x and 20x. In-sample (the likelihood ratios come from
    the same texts), so it flatters the rule; a check of its behaviour, not a new rate."""
    known = cal.get("known_scores") or {}
    tools = {t for r in known.values() for t in r["scores"]}
    weights = tool_weights(cal, tools)
    out = {"human": [], "ai": []}
    for r in known.values():
        ev = {
            t: tool_evidence(weights[t], float(sc >= 0.5))
            for t, sc in r["scores"].items()
            if weights[t]["used"]
        }
        if ev:
            cls = "ai" if r["label"] == "ai" else "human"
            out[cls].append(
                math.exp(combine_tools(ev, weights, cal.get("pairs") or {}))
            )
    return {
        cls: {
            "n": len(xs),
            **{f">={b}x": sum(x >= b for x in xs) for b in (3, 10, 20)},
            "max": round(max(xs), 1) if xs else None,
        }
        for cls, xs in out.items()
    }


def _contains(unit: dict, s: dict) -> bool:
    return any(a <= s["start"] and s["end"] <= b for a, b in unit["spans"])


def _wmean(rows: list[dict]) -> float | None:
    rows = [r for r in rows if r["evidence"] is not None]
    tot = sum(r["n_words"] for r in rows)
    return (
        round(sum(r["evidence"] * r["n_words"] for r in rows) / tot, 3) if tot else None
    )


def combine(work: Path) -> dict | None:
    """The contents of evidence.json, or None when there is no plan (segments.py)."""
    plan = read_json(work / "multi" / "plan.json")
    if not plan:
        return None
    units = {u["chunk"]: u for u in plan["units"]}
    res = {k: v for k, v in load_results(work).items() if k[1] in units}
    tools = sorted({t for t, _ in res})
    cal = read_json(REFS / "web_calibration.json") or {}
    weights = tool_weights(cal, set(tools))
    pairs = cal.get("pairs") or {}
    used = [t for t in tools if weights[t]["used"]]
    sentences, unstable = [], {t: [0, 0] for t in tools}
    for s in plan["sentences"]:
        cover = [uid for uid, u in units.items() if _contains(u, s)]
        per_tool, ev = {}, {}
        for t in tools:
            votes = [res[(t, uid)] >= 0.5 for uid in cover if (t, uid) in res]
            if not votes:
                continue
            v = sum(votes) / len(votes)
            per_tool[t] = {"v": round(v, 3), "n": len(votes)}
            unstable[t][1] += 1
            unstable[t][0] += 0 < v < 1
            if t in used:
                ev[t] = tool_evidence(weights[t], v)
        comb = combine_tools(ev, weights, pairs) if ev else None
        sentences.append(
            {
                **s,
                "tools": per_tool,
                "evidence": None if comb is None else round(comb, 3),
                "n_tools": len(ev),
            }
        )
    passages = [
        {
            "chunk": uid,
            "evidence": _wmean([r for r in sentences if _contains(u, r)]),
            "n_sentences": sum(1 for r in sentences if _contains(u, r)),
        }
        for uid, u in units.items()
        if u["scale"] == "P"
    ]
    doc_ev = _wmean(sentences)
    return {
        "tools": weights,
        "used": used,
        "document": {
            "evidence": doc_ev,
            "times": None if doc_ev is None else round(math.exp(doc_ev), 2),
        },
        "passages": passages,
        "sentences": sentences,
        "stability": {
            t: (round(a / b, 3) if b else None) for t, (a, b) in unstable.items()
        },
        "units_scored": {t: sorted(uid for (tt, uid) in res if tt == t) for t in tools},
    }
