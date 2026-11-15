"""Combine every check into one graded verdict and a list of defensible statements.

Reads from the work folder: artifacts.json, references.json, detectors.json,
stylometry.json, text.json, and judgements.json (Claude's own reading, plus its decisions
on candidate hits and on references it verified by hand). Rules come from
references/grading.json.

Tiers, highest first:

    conclusive    an AI tool's output was pasted in (a confirmed artefact)
    strong        verifiable problems typical of unchecked AI use (fabricated references),
                  or both calibrated detectors flag the document *and* something else does
    moderate      one independent line of evidence
    weak          only stylistic context
    none          nothing found

Each statement is phrased so the user can say it out loud and back it up: what was
found, where, and how anyone can re-check it. Statements never claim more than the
evidence (a detector flag is "at a 1% false-positive operating point", not "AI-written").

judgements.json (written by Claude, all keys optional):

    {"artifacts": {"a3": {"confirmed": false, "why": "quoted as an example in a paper on LLMs"}},
     "references": {"7": {"fabricated": true, "why": "searched Google Scholar and PubMed by title"}},
     "reading": [{"tier": "moderate", "claim": "...", "quote": "...", "where": "Review, point 3",
                  "check": "how to verify"}],
     "excluded_sections": ["Methods"]}

Writes ``<work>/grade.json``.

Usage:
    python grade.py [--work /tmp/ai_text_detection]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _common import REFS, TIERS, WORK_DIR, read_json, write_json


def plural(n: int, word: str) -> str:
    """'1 reference' / '3 references'."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def grade(work: Path) -> dict:
    """The verdict dictionary."""
    rules = read_json(REFS / "grading.json")
    doc = read_json(work / "text.json") or {}
    arts = read_json(work / "artifacts.json") or {"hits": [], "hidden": []}
    refs = read_json(work / "references.json") or {"references": []}
    det = read_json(work / "detectors.json") or {}
    sty = read_json(work / "stylometry.json") or {}
    jud = read_json(work / "judgements.json") or {}
    ja, jr = jud.get("artifacts", {}), jud.get("references", {})

    statements: list[dict] = []
    det_statement: dict = {}
    separate: list[dict] = []
    met = {t: [] for t in TIERS}

    # 1. Artefacts. A hit Claude marked unconfirmed (quotation, example) does not count.
    confirmed = [h for h in arts["hits"] if ja.get(h["id"], {}).get("confirmed", True)]
    dismissed = [
        h for h in arts["hits"] if not ja.get(h["id"], {}).get("confirmed", True)
    ]
    by_cat: dict[str, list[dict]] = {}
    for h in confirmed:
        by_cat.setdefault(h["category"], []).append(h)
    for cat, hits in by_cat.items():
        if cat in rules["separate"]:
            separate.append(
                {
                    "kind": rules["separate"][cat],
                    "text": (
                        f"The document contains {plural(len(hits), 'instruction')} aimed at AI reviewing tools"
                        + (
                            ", hidden from human readers"
                            if any(h["in"] == "hidden" for h in hits)
                            else ""
                        )
                        + ". This is an attempt to manipulate AI-assisted review, regardless of who wrote the text."
                        if cat == "prompt-injection"
                        else f"The document contains {plural(len(hits), 'tortured phrase')} (established terms replaced by odd "
                        "synonyms, e.g. "
                        + "; ".join(
                            f"'{h['match']}' for '{h.get('established_term')}'"
                            for h in hits[:3]
                        )
                        + "). This is the signature of paraphrasing software used to disguise copied text, which publishers treat as misconduct."
                    ),
                    "evidence": [h["id"] for h in hits],
                }
            )
            continue
        tier = hits[0]["tier"]
        if cat in rules["conclusive"]["categories"] and tier == "conclusive":
            met["conclusive"].append(cat)
        elif tier == "strong" or cat in rules["strong"]["strong_categories"]:
            met["strong"].append(cat)
        elif tier == "moderate":
            met["moderate"].append(cat)
        else:
            met["weak"].append(cat)
        ex = hits[0]
        loc = ", ".join(
            x
            for x in (
                ex.get("section"),
                f"p. {ex['page']}" if ex.get("page") else None,
                ex["in"] if ex["in"] != "body" else None,
            )
            if x
        )
        statements.append(
            {
                "tier": tier,
                "text": f"{ex['shows']} Found {plural(len(hits), 'time')}; first instance ({loc or 'body'}): “{ex['match']}”.",
                "evidence": [h["id"] for h in hits],
                "check": "Search the document for the quoted text.",
            }
        )
    hidden_plain = [h for h in arts.get("hidden", []) if not h.get("matches")]
    if hidden_plain:
        separate.append(
            {
                "kind": "hidden-text",
                "text": f"The PDF/DOCX contains {plural(len(hidden_plain), 'passage')} of text invisible to a reader "
                "(white, tiny or off-page). It matched no known injection phrase; read it in the evidence table.",
                "evidence": [h["id"] for h in hidden_plain],
            }
        )

    # 2. References.
    bad_status = set(rules["strong"]["fabricated_statuses"])
    rlist = refs.get("references", [])
    suspect = [r for r in rlist if r["status"] in bad_status]
    fabricated = [r for r in suspect if jr.get(str(r["n"]), {}).get("fabricated", True)]
    hand_checked = all(str(r["n"]) in jr for r in fabricated)
    if len(fabricated) >= rules["strong"]["min_fabricated_refs"]:
        met["strong"].append("references")
    elif len(fabricated) >= rules["moderate"]["min_fabricated_refs"]:
        met["moderate"].append("references")
    if fabricated:
        kinds = {}
        for r in fabricated:
            kinds[r["status"]] = kinds.get(r["status"], 0) + 1
        desc = {
            "not-found": "could not be found in Crossref or OpenAlex",
            "doi-not-registered": "cite a DOI that is not registered anywhere",
            "doi-points-elsewhere": "cite a DOI that belongs to a different paper",
        }
        statements.append(
            {
                "tier": "strong"
                if len(fabricated) >= rules["strong"]["min_fabricated_refs"]
                else "moderate",
                "text": f"{len(fabricated)} of {len(rlist)} references appear not to exist as cited: "
                + "; ".join(f"{v} {desc[k]}" for k, v in kinds.items())
                + (
                    ". Each was also searched for by hand."
                    if hand_checked
                    else ". (Not yet confirmed by a manual search.)"
                )
                + " Fabricated references are a well-documented failure of language models (Walters & Wilder 2023: 18-55% of"
                " ChatGPT citations); whatever their origin, they must be corrected.",
                "evidence": [f"ref{r['n']}" for r in fabricated],
                "check": "Every lookup URL is listed in the reference table; anyone can re-run them.",
            }
        )
    mism = [r for r in rlist if r["status"] == "metadata-mismatch"]
    if len(mism) >= 3:
        statements.append(
            {
                "tier": "weak",
                "text": f"{len(mism)} references exist but with a different year, first author or title than cited. Humans make such errors too.",
                "evidence": [f"ref{r['n']}" for r in mism],
                "check": "See the reference table.",
            }
        )
        met["weak"].append("ref-mismatch")

    # 3. Detectors. Both statistics come from one model pair, so they are one line of
    # evidence: 'both' only raises it to strong when something independent agrees.
    dsum = det.get("summary") or {}
    flags1 = [k for k, v in dsum.items() if v.get("document_flag") == "1%"]
    flags5 = [k for k, v in dsum.items() if v.get("document_flag") in ("1%", "5%")]
    det_level = None
    if len(flags1) >= rules["strong"]["detectors_required"]:
        det_level = "both-1"
    elif flags1:
        det_level = "one-1"
    elif flags5:
        det_level = "5"
    if det_level:
        parts = [
            f"{k.replace('_', '-')}: {v['over_1pct']} of {v['windows']} windows past the 1% threshold"
            for k, v in dsum.items()
        ]
        if det_level == "5":
            text = (
                "Detectors flag the document only at the looser 5% false-positive operating point "
                f"({'; '.join(parts)})."
            )
        else:
            text = (
                "Local AI-text detectors, calibrated so that only about 1% of human scientific text written "
                f"before ChatGPT is flagged, flag this document ({'; '.join(parts)}). This is a statistical "
                "signal about how predictable the text is to a language model, not proof of authorship."
            )
        det_statement = {
            "tier": "weak" if det_level == "5" else "moderate",
            "text": text,
            "evidence": ["detectors"],
            "check": "Method, thresholds and validation rates are in the report's methods section.",
        }
        statements.append(det_statement)
        if det_level == "5":
            met["weak"].append("detectors-5")
        else:
            met["moderate"].append("detectors")

    # 4. Stylometry.
    ss = sty.get("summary") or {}
    wo = ss.get("windows_over") or {}
    nw = ss.get("n_windows", 0)
    if wo and nw >= rules["moderate"]["style_min_windows"]:
        f1 = wo.get("1%", {}).get("fraction", 0)
        f5 = wo.get("5%", {}).get("fraction", 0)
        words_ = ", ".join(ss.get("marked_words", [])[:12])
        style_auroc = (
            (read_json(REFS / "calibration.json") or {}).get("stylometry") or {}
        ).get("auroc") or 0
        style_ok = style_auroc >= rules["moderate"]["min_style_auroc"]
        if f1 >= rules["moderate"]["style_fraction_over_1pct"] and style_ok:
            met["moderate"].append("style")
            tier = "moderate"
        elif f5 >= rules["weak"]["style_fraction_over_5pct"]:
            met["weak"].append("style")
            tier = "weak"
        else:
            tier = None
        if tier:
            statements.append(
                {
                    "tier": tier,
                    "text": f"The vocabulary and phrasing match the profile of post-ChatGPT scientific text in {wo['1%']['count']} of "
                    f"{nw} windows at a 1% false-positive threshold"
                    + (f" (characteristic words used: {words_})" if words_ else "")
                    + ". Many people now write like this, so this is context, not proof.",
                    "evidence": ["stylometry"],
                    "check": "Word lists: Kobak et al. 2025 (Science Advances); Liang et al. 2024.",
                }
            )

    # 4b. The author's own earlier writing (baseline.py), when available.
    base = read_json(work / "baseline.json") or {}
    machine_side = {"binoculars": -1, "fast_detectgpt": 1}
    shifted = [
        k
        for k, c in (base.get("comparison") or {}).items()
        if k in machine_side
        and c["outside_range"]
        and (c["document_median"] - c["baseline_median"]) * machine_side[k] > 0
    ]
    if shifted and base.get("n_texts", 0) >= rules["moderate"]["baseline_min_texts"]:
        met["moderate"].append("baseline")
        statements.append(
            {
                "tier": "moderate",
                "text": f"Compared with {base['n_texts']} texts the same author wrote before ChatGPT "
                f"({', '.join(str(y) for y in base.get('years', [])[:1] + base.get('years', [])[-1:])}), this document is "
                f"outside their own range, on the machine-like side, for {', '.join(x.replace('_', '-') for x in shifted)}. "
                "A change in one person's writing is more telling than a comparison with other people's.",
                "evidence": ["baseline"],
                "check": "Earlier texts and their scores are listed in baseline.json.",
            }
        )

    # 4c. Google Doc revision history (drive_intake.py revisions), weak context only.
    revs = read_json(work / "revisions.json") or {}
    if revs.get("pasted_in_one_block"):
        met["weak"].append("pasted")
        big = revs["largest_addition"]
        statements.append(
            {
                "tier": "weak",
                "text": f"The Google Doc's revision history shows {big['added']} of its {revs['final_words']} words arriving in "
                f"a single edit ({big.get('time')}). The text was written elsewhere and pasted in; that is also how people "
                "move their own drafts, so this is context only.",
                "evidence": ["revisions"],
                "check": "File > Version history in the Google Doc.",
            }
        )

    # 5. Claude's reading (each finding quoted and checkable).
    reading = jud.get("reading", [])
    for i, r in enumerate(reading, 1):
        tier = r.get("tier", "weak")
        if tier == "strong" and not rules["strong"]["reading_strong_ok"]:
            tier = "moderate"
        statements.append(
            {
                "tier": tier,
                "text": r["claim"]
                + (
                    f" (“{r['quote']}”, {r.get('where', '')})" if r.get("quote") else ""
                ),
                "evidence": [f"read{i}"],
                "check": r.get("check", ""),
            }
        )
        met[tier if tier in met else "weak"].append(f"reading{i}")
    if (
        sum(1 for r in reading if r.get("tier") in ("moderate", "strong"))
        >= rules["moderate"]["min_reading_findings"]
    ):
        met["moderate"].append("reading")

    # Decide the tier. Detectors at 1% FPR on both statistics become strong only next to
    # another independent line of moderate-or-higher evidence.
    independent = [
        x
        for x in met["moderate"] + met["strong"] + met["conclusive"]
        if x != "detectors"
    ]
    if (
        det_level == "both-1"
        and independent
        and rules["strong"]["detector_needs_one_moderate"]
    ):
        met["strong"].append("detectors+other")
        det_statement["tier"] = "strong"
    tier = next((t for t in TIERS[:-1] if met.get(t)), "none")

    caveats = []
    nwords = doc.get("n_words", 0)
    if nwords < rules["caveats"]["short_text_words"]:
        caveats.append(
            f"The text is short ({nwords} words): statistical checks are unreliable below ~300 words."
        )
    if (
        dsum
        and max(v["windows"] for v in dsum.values()) < rules["caveats"]["few_windows"]
    ):
        caveats.append(
            "Fewer than 3 windows were scored, so the document-level detector rule could not be applied."
        )
    if not dsum:
        caveats.append(
            "The model-based detectors were not run (environment missing or skipped)."
        )
    if not rlist:
        caveats.append("No reference list was found, so references were not checked.")
    if dismissed:
        caveats.append(
            f"{plural(len(dismissed), 'candidate artefact')} were set aside after reading them in context: "
            + "; ".join(ja[h["id"]].get("why", "") for h in dismissed)
        )
    caveats += [
        (
            "Detector and style scores are lower for some human writing and higher for other human writing: non-native "
            "English, professional language editing, grammar tools, and formulaic sections all shift them (Liang et al. 2023)."
        ),
        (
            "Using an AI tool for language polishing is allowed by most journals and funders when disclosed; the policies "
            "section lists what applies."
        ),
    ]
    order = {t: i for i, t in enumerate(TIERS)}
    statements.sort(key=lambda s: order.get(s["tier"], 9))
    headline = {
        "conclusive": "Conclusive: text produced by an AI tool was pasted into this document.",
        "strong": "Strong evidence of unchecked AI use, based on problems anyone can verify.",
        "moderate": "Moderate evidence of AI use: one independent line of evidence points that way.",
        "weak": "Weak signals only: the style resembles AI-assisted text, which proves nothing on its own.",
        "none": "No evidence of AI use was found by these checks.",
    }[tier]
    return {
        "tier": tier,
        "headline": headline,
        "statements": statements,
        "separate": separate,
        "caveats": caveats,
        "rules_met": {k: v for k, v in met.items() if v},
        "grading_version": rules["version"],
    }


def main(argv: list[str] | None = None) -> int:
    """Grade and write grade.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    args = p.parse_args(argv)
    work = Path(args.work)
    g = grade(work)
    write_json(work / "grade.json", g)
    print(f"verdict: {g['tier'].upper()}: {g['headline']}")
    for s in g["statements"]:
        print(f"  [{s['tier']}] {s['text'][:220]}")
    for s in g["separate"]:
        print(f"  [{s['kind']}] {s['text'][:220]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
