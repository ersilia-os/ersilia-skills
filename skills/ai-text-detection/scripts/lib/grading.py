"""Turn every check into one graded verdict and the statements the user can make.

The tier is the highest one whose rule (references/grading.json) is met:

    conclusive    a confirmed artefact of an AI tool's output (chatbot leftovers, citation
                  tokens, placeholders, leaked reasoning, interface leftovers)
    strong        two or more fabricated references; a strong close-reading finding
                  (a verified false claim or invented fact); markdown or unicode
                  artefacts; or two validated web detectors flagging the document plus a
                  non-statistical line of evidence
    moderate      one independent line: a fabricated reference; two close-reading
                  findings; the style score past its 1% threshold in most windows; one
                  validated web detector flagging the text; the calibrated combination of
                  detectors at its document or passage bar; or a shift from the author's
                  own earlier writing
    weak          context only
    none          nothing found

Prompt injections, tortured phrases and plain hidden text are reported separately: serious,
but not evidence that an AI wrote the text. Each line of evidence is one function below;
each adds to a Verdict: the rules met, the statements (what was found, where, how to
re-check it), the separate findings and the caveats.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from lib.common import REFS, TIERS, read_json
from lib.detectors import Detections, tool

# Rule labels that come from detectors or style statistics. They never count as the
# independent, non-statistical support that lifts two validated detectors to strong.
STATISTICAL = {
    "web",
    "web-context",
    "web-hotspots",
    "combined",
    "combined-passage",
    "style",
}

HEADLINE = {
    "conclusive": "Conclusive: text produced by an AI tool was pasted into this document.",
    "strong": "Strong evidence of unchecked AI use, based on problems anyone can verify.",
    "moderate": "Moderate evidence of AI use: one independent line of evidence points that way.",
    "weak": "Weak: only minor observations, none of which shows AI use on its own.",
    "none": "No evidence of AI use was found by these checks.",
}


def plural(n: int, word: str) -> str:
    """'1 reference' / '3 references'."""
    return f"{n} {word}{'' if n == 1 else 's'}"


@dataclass
class Inputs:
    """Everything grading reads, from the work folder and references/."""

    work: Path
    rules: dict
    doc: dict
    arts: dict
    refs: dict
    sty: dict
    jud: dict
    web: Detections
    evd: dict
    base: dict
    revs: dict

    @property
    def ja(self) -> dict:
        """Claude's decisions on artefact hits."""
        return self.jud.get("artifacts", {})

    @property
    def jr(self) -> dict:
        """Claude's decisions on suspect references."""
        return self.jud.get("references", {})

    @classmethod
    def load(cls, work: Path) -> Inputs:
        """Read the work folder (missing files read as empty)."""

        def rd(name: str, default: dict | None = None) -> dict:
            return read_json(work / name) or (default if default is not None else {})

        return cls(
            work=work,
            rules=read_json(REFS / "grading.json"),
            doc=rd("text.json"),
            arts=rd("artifacts.json", {"hits": [], "hidden": []}),
            refs=rd("references.json", {"references": []}),
            sty=rd("stylometry.json"),
            jud=rd("judgements.json"),
            web=Detections.load(work),
            evd=rd("evidence.json"),
            base=rd("baseline.json"),
            revs=rd("revisions.json"),
        )


@dataclass
class Verdict:
    """What the checks found so far."""

    met: dict[str, list[str]] = field(default_factory=lambda: {t: [] for t in TIERS})
    statements: list[dict] = field(default_factory=list)
    separate: list[dict] = field(default_factory=list)
    caveats_pre: list[str] = field(default_factory=list)

    def state(self, tier: str, text: str, evidence: list[str], check: str = "") -> None:
        """Add a statement the user can make: what was found and how to re-check it."""
        self.statements.append(
            {"tier": tier, "text": text, "evidence": evidence, "check": check}
        )


def _artefacts(inp: Inputs, out: Verdict) -> list:
    """Artefacts. A hit set aside in judgements.json (a quotation, an example) does not count; prompt injections and tortured phrases are reported separately. Returns the hits set aside."""
    confirmed = [
        h for h in inp.arts["hits"] if inp.ja.get(h["id"], {}).get("confirmed", True)
    ]
    dismissed = [
        h
        for h in inp.arts["hits"]
        if not inp.ja.get(h["id"], {}).get("confirmed", True)
    ]
    by_cat: dict[str, list[dict]] = {}
    for h in confirmed:
        by_cat.setdefault(h["category"], []).append(h)
    for cat, hits in by_cat.items():
        if cat in inp.rules["separate"]:
            out.separate.append(
                {
                    "kind": inp.rules["separate"][cat],
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
        # The category's strongest hit decides (hits come body first, then references,
        # then hidden text, so the first one is not necessarily the strongest).
        hits = sorted(hits, key=lambda h: TIERS.index(h["tier"]))
        tier = hits[0]["tier"]
        if cat in inp.rules["conclusive"]["categories"] and tier == "conclusive":
            out.met["conclusive"].append(cat)
        elif tier == "strong" or cat in inp.rules["strong"]["strong_categories"]:
            out.met["strong"].append(cat)
        elif tier == "moderate":
            out.met["moderate"].append(cat)
        else:
            out.met["weak"].append(cat)
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
        out.state(
            tier=tier,
            text=f"{ex['shows']} Found {plural(len(hits), 'time')}; first instance ({loc or 'body'}): “{ex['match']}”.",
            evidence=[h["id"] for h in hits],
            check="Search the document for the quoted text.",
        )
    hidden_plain = [h for h in inp.arts.get("hidden", []) if not h.get("matches")]
    if hidden_plain:
        out.separate.append(
            {
                "kind": "hidden-text",
                "text": f"The PDF/DOCX contains {plural(len(hidden_plain), 'passage')} of text invisible to a reader "
                "(white, tiny or off-page). It matched no known injection phrase; read it in the evidence table.",
                "evidence": [h["id"] for h in hidden_plain],
            }
        )
    return dismissed


def _references(inp: Inputs, out: Verdict) -> list:
    """References not found as cited (minus those cleared by hand); several real ones cited with wrong details are weak context. Returns the reference list."""
    bad_status = set(inp.rules["strong"]["fabricated_statuses"])
    rlist = inp.refs.get("references", [])
    suspect = [r for r in rlist if r["status"] in bad_status]
    fabricated = [
        r for r in suspect if inp.jr.get(str(r["n"]), {}).get("fabricated", True)
    ]
    hand_checked = all(str(r["n"]) in inp.jr for r in fabricated)
    if len(fabricated) >= inp.rules["strong"]["min_fabricated_refs"]:
        out.met["strong"].append("references")
    elif len(fabricated) >= inp.rules["moderate"]["min_fabricated_refs"]:
        out.met["moderate"].append("references")
    if fabricated:
        kinds = {}
        for r in fabricated:
            kinds[r["status"]] = kinds.get(r["status"], 0) + 1
        desc = {
            "not-found": "could not be found in Crossref or OpenAlex",
            "doi-not-registered": "cite a DOI that is not registered anywhere",
            "doi-points-elsewhere": "cite a DOI that belongs to a different paper",
        }
        out.state(
            tier="strong"
            if len(fabricated) >= inp.rules["strong"]["min_fabricated_refs"]
            else "moderate",
            text=f"{len(fabricated)} of {len(rlist)} references appear not to exist as cited: "
            + "; ".join(f"{v} {desc[k]}" for k, v in kinds.items())
            + (
                ". Each was also searched for by hand."
                if hand_checked
                else ". (Not yet confirmed by a manual search.)"
            )
            + " Fabricated references are a well-documented failure of language models (Walters & Wilder 2023: 18-55% of"
            " ChatGPT citations); whatever their origin, they must be corrected.",
            evidence=[f"ref{r['n']}" for r in fabricated],
            check="The lookups are linked under Evidence items; anyone can re-run them.",
        )
    mism = [r for r in rlist if r["status"] == "metadata-mismatch"]
    if len(mism) >= 3:
        out.state(
            tier="weak",
            text=f"{len(mism)} references exist but with a different year, first author or title than cited. Humans make such errors too.",
            evidence=[f"ref{r['n']}" for r in mism],
            check="Each reference's lookup is in references.json.",
        )
        out.met["weak"].append("ref-mismatch")
    return rlist


def _style(inp: Inputs, out: Verdict) -> None:
    """The calibrated style score, when enough windows were scored."""
    ss = inp.sty.get("summary") or {}
    wo = ss.get("windows_over") or {}
    nw = ss.get("n_windows", 0)
    if wo and nw >= inp.rules["moderate"]["style_min_windows"]:
        f1 = wo.get("1%", {}).get("fraction", 0)
        f5 = wo.get("5%", {}).get("fraction", 0)
        words_ = ", ".join(ss.get("marked_words", [])[:12])
        style_auroc = (
            (read_json(REFS / "calibration.json") or {}).get("stylometry") or {}
        ).get("auroc") or 0
        style_ok = style_auroc >= inp.rules["moderate"]["min_style_auroc"]
        if f1 >= inp.rules["moderate"]["style_fraction_over_1pct"] and style_ok:
            out.met["moderate"].append("style")
            tier = "moderate"
        elif f5 >= inp.rules["weak"]["style_fraction_over_5pct"]:
            out.met["weak"].append("style")
            tier = "weak"
        else:
            tier = None
        if tier:
            out.state(
                tier=tier,
                text=f"The vocabulary and phrasing match the profile of post-ChatGPT scientific text in {wo['1%']['count']} of "
                f"{nw} windows at a 1% false-positive threshold"
                + (f" (characteristic words used: {words_})" if words_ else "")
                + ". Many people now write like this, so this is context, not proof.",
                evidence=["stylometry"],
                check="Word lists: Kobak et al. 2025 (Science Advances); Liang et al. 2024.",
            )


def _web(inp: Inputs, out: Verdict) -> tuple:
    """Web detectors over the whole text: validated tools flagging it are moderate, others weak context. Returns the validated tools that flag and those that clear it, and the tools that covered enough of the text."""
    wsum = inp.web.summary()
    wr = inp.rules.get(
        "web", {"flag_share": 0.5, "validated_for_strong": 2, "min_coverage": 0.5}
    )
    # A tool that scanned too little of the text says nothing about the document.
    wsum = {
        k: v
        for k, v in wsum.items()
        if v.get("coverage", 1) >= wr.get("min_coverage", 0.5)
    }
    flagged_valid = [
        x
        for x in wsum.values()
        if x["weight"] == "validated" and x["share_words_flagged"] >= wr["flag_share"]
    ]
    clean_valid = [
        x
        for x in wsum.values()
        if x["weight"] == "validated" and x["share_words_flagged"] < wr["flag_share"]
    ]
    flagged_ctx = [
        x
        for x in wsum.values()
        if x["weight"] != "validated" and x["share_words_flagged"] >= wr["flag_share"]
    ]
    if flagged_valid:
        out.met["moderate"].append("web")
        out.state(
            tier="moderate",
            text="Commercial AI detectors with independent evidence of few false positives flag this text: "
            + "; ".join(
                f"{x['name']} flags {x['passages_flagged']} of {x['passages']} passages ({x['share_words_flagged']:.0%} of the words), mean AI score {x['mean_score']}"
                for x in flagged_valid
            )
            + ". A detector score is a statistical judgement, not proof.",
            evidence=["web"],
            check="Paste the same passages into the same sites; the passages are saved with the report.",
        )
    if flagged_ctx:
        out.met["weak"].append("web-context")
        out.state(
            tier="weak",
            text="Detectors without published independent validation flag it ("
            + ", ".join(x["name"] for x in flagged_ctx)
            + "). Their weight comes from the skill's own tests on known texts (see the calibrated combination), "
            "not from their scores alone.",
            evidence=["web"],
            check="",
        )
    return flagged_valid, clean_valid, wsum


def _hotspots(inp: Inputs, out: Verdict) -> None:
    """Passages where most of the tools that scored them say AI: where to read first."""
    sections = {u["chunk"]: ", ".join(u["sections"]) for u in inp.web.passages}
    hot = []
    for uid, scores in inp.web.passage_scores().items():
        n_flag = sum(v >= 0.5 for v in scores.values())
        if len(scores) >= 3 and n_flag >= 3 and n_flag / len(scores) > 0.5:
            hot.append((int(uid[1:]), sections[uid], n_flag, len(scores)))
    hot = [
        f"passage {k} ({secs}): {n_flag} of {n} tools"
        for k, secs, n_flag, n in sorted(hot)
    ]
    if hot:
        out.met["weak"].append("web-hotspots")
        out.state(
            tier="weak",
            text="Passages where most of the detectors that scored them say AI: "
            + "; ".join(hot)
            + ". These are the places to read most closely; the weighted combination above says how much the agreement is worth.",
            evidence=["web"],
            check="The side panel shows each detector's score for every passage.",
        )


def _combined(inp: Inputs, out: Verdict) -> None:
    """The calibrated combination across tools and splits (evidence.py): moderate for the document or, stricter, for one passage; counter-evidence when it leans human."""
    cr = inp.rules.get("combined", {})
    # From the log value at full precision: the rounded "times" can be 0.0.
    doc_ev = (inp.evd.get("document") or {}).get("evidence")
    times = None if doc_ev is None else math.exp(doc_ev)
    good = [
        t
        for t in inp.evd.get("used", [])
        if ((inp.evd.get("tools", {}).get(t) or {}).get("cal") or {}).get("auroc", 0)
        >= cr.get("good_auroc", 0.75)
    ]
    if times is not None and cr:
        names = ", ".join(tool(t).get("name", t) for t in inp.evd.get("used", []))
        if times >= cr["moderate_times"] and len(good) >= cr["min_good_tools"]:
            out.met["moderate"].append("combined")
            out.state(
                tier="moderate",
                text=f"Combining {len(inp.evd.get('used', []))} detectors ({names}), each weighted by how it did on known human and "
                f"AI scientific texts, and every way of splitting the text, the document is about {times:.1f} times as likely "
                "under AI-written text as under human text. The detectors' own error rates are built in; they may still share mistakes.",
                evidence=["combined"],
                check="The side panel shows each detector's record on known texts.",
            )
        elif cr.get("passage_times"):
            strong_p = [
                pa
                for pa in inp.evd.get("passages", [])
                if pa.get("evidence") is not None
                and math.exp(pa["evidence"]) >= cr["passage_times"]
            ]
            if strong_p and len(good) >= cr["min_good_tools"]:
                out.met["moderate"].append("combined-passage")
                secs = {u["chunk"]: " + ".join(u["sections"]) for u in inp.web.passages}
                out.state(
                    tier="moderate",
                    text="Localised: "
                    + "; ".join(
                        f"passage {pa['chunk'][1:]} ({secs.get(pa['chunk'], '')}) is about {math.exp(pa['evidence']):.0f} times as likely under AI-written text"
                        for pa in strong_p
                    )
                    + f", combining {len(inp.evd.get('used', []))} detectors weighted by their results on known texts and every way of "
                    f"splitting the text. For the whole document the figure is about {times:.1f}. "
                    "This points to AI involvement in part of the text, not in all of it.",
                    evidence=["combined"],
                    check="The side panel shows each detector's record on known texts.",
                )
        fired = {"combined", "combined-passage"} & set(out.met["moderate"])
        if times <= cr["counter_times"]:
            out.caveats_pre.append(
                f"Counter-evidence: the calibrated combination of detectors ({names}) leans human: about {1 / times:.0f} times as likely under human text."
            )
        elif not fired:
            out.state(
                tier="weak" if times > 1 else "none",
                text=f"Combining the calibrated detectors ({names}) across all splits gives no clear answer "
                f"(about {times:.1f} times as likely under AI as under human text).",
                evidence=["combined"],
                check="",
            )


def _baseline(inp: Inputs, out: Verdict) -> None:
    """A shift from the author's own pre-2023 writing (baseline.py), on the machine-like side."""
    # Style features outside the author's own earlier range, on the AI-typical side.
    machine_side = {"excess_rate": 1, "marked_rate": 1, "tells_rate": 1, "sent_cv": -1}
    shifted = [
        k
        for k, c in (inp.base.get("comparison") or {}).items()
        if k in machine_side
        and c["outside_range"]
        and (c["document_median"] - c["baseline_median"]) * machine_side[k] > 0
    ]
    if (
        len(shifted) >= inp.rules["moderate"].get("baseline_min_features", 2)
        and inp.base.get("n_texts", 0) >= inp.rules["moderate"]["baseline_min_texts"]
    ):
        out.met["moderate"].append("baseline")
        out.state(
            tier="moderate",
            text=f"Compared with {inp.base['n_texts']} texts the same author wrote before ChatGPT "
            f"({', '.join(str(y) for y in inp.base.get('years', [])[:1] + inp.base.get('years', [])[-1:])}), this document is "
            f"outside their own range, on the machine-like side, for {', '.join(x.replace('_', '-') for x in shifted)}. "
            "A change in one person's writing is more telling than a comparison with other people's.",
            evidence=["baseline"],
            check="Earlier texts and their scores are listed in baseline.json.",
        )


def _revisions(inp: Inputs, out: Verdict) -> None:
    """Google Doc revision history: text arriving in one block is weak context only."""
    if inp.revs.get("pasted_in_one_block"):
        out.met["weak"].append("pasted")
        big = inp.revs["largest_addition"]
        out.state(
            tier="weak",
            text=f"The Google Doc's revision history shows {big['added']} of its {inp.revs['final_words']} words arriving in "
            f"a single edit ({big.get('time')}). The text was written elsewhere and pasted in; that is also how people "
            "move their own drafts, so this is context only.",
            evidence=["revisions"],
            check="File > Version history in the Google Doc.",
        )


def _reading(inp: Inputs, out: Verdict) -> None:
    """Claude's close reading, each finding quoted and checkable."""
    reading = inp.jud.get("reading", [])
    for i, r in enumerate(reading, 1):
        tier = r.get("tier", "weak")
        if tier == "strong" and not inp.rules["strong"]["reading_strong_ok"]:
            tier = "moderate"
        out.state(
            tier=tier,
            text=r["claim"]
            + (f" (“{r['quote']}”, {r.get('where', '')})" if r.get("quote") else ""),
            evidence=[f"read{i}"],
            check=r.get("check", ""),
        )
        out.met[tier if tier in out.met else "weak"].append(f"reading{i}")
    if (
        sum(1 for r in reading if r.get("tier") in ("moderate", "strong"))
        >= inp.rules["moderate"]["min_reading_findings"]
    ):
        out.met["moderate"].append("reading")


def _caveats(
    inp: Inputs, out: Verdict, dismissed: list, rlist: list, web: tuple
) -> list[str]:
    """What the evidence does not show, and what could not be checked."""
    _flagged_valid, clean_valid, wsum = web
    caveats = list(out.caveats_pre)
    nwords = inp.doc.get("n_words", 0)
    if nwords < inp.rules["caveats"]["short_text_words"]:
        caveats.append(
            f"The text is short ({nwords} words): statistical checks are unreliable below ~300 words."
        )
    tracked = (inp.doc.get("metadata") or {}).get("tracked_changes_removed")
    if tracked:
        caveats.append(
            "The author's original text was tested: tracked changes by "
            + ", ".join(
                f"{a} ({n['ins']} insertions, {n['del']} deletions)"
                for a, n in tracked.items()
            )
            + " were set aside."
        )
    if clean_valid:
        caveats.append(
            "Counter-evidence: "
            + "; ".join(
                f"{x['name']} scored {x['passages'] - x['passages_flagged']} of {x['passages']} passages as human (mean AI score {x['mean_score']})"
                for x in clean_valid
            )
            + "."
        )
    caveats += [
        f"Web detector {sk['tool']} was not used: {sk['why']}."
        for sk in inp.web.skipped
    ]
    if not wsum:
        caveats.append(
            "No web detector was run (confidential text, or not run this time), so there is no detector score."
        )
    if not rlist:
        caveats.append("No reference list was found, so references were not checked.")
    if dismissed:
        caveats.append(
            f"{plural(len(dismissed), 'candidate artefact')} were set aside after reading them in context: "
            + "; ".join(inp.ja[h["id"]].get("why", "") for h in dismissed)
        )
    return [
        *caveats,
        (
            "Detector and style scores are lower for some human writing and higher for other human writing: non-native "
            "English, professional language editing, grammar tools, and formulaic sections all shift them (Liang et al. 2023)."
        ),
        (
            "Using an AI tool for language polishing is allowed by most journals and funders when disclosed; check the "
            "policy of the journal or funder concerned."
        ),
    ]


def grade(work: Path) -> dict:
    """The verdict: tier, headline, statements, separate findings, caveats."""
    inp, out = Inputs.load(work), Verdict()
    dismissed = _artefacts(inp, out)
    rlist = _references(inp, out)
    _style(inp, out)
    web = _web(inp, out)
    _hotspots(inp, out)
    _combined(inp, out)
    _baseline(inp, out)
    _revisions(inp, out)
    _reading(inp, out)

    # Two validated web detectors become strong only next to a non-statistical line
    # (artefacts, references, close reading, baseline).
    met = out.met
    non_stat = [
        x
        for x in met["moderate"] + met["strong"] + met["conclusive"]
        if x not in STATISTICAL
    ]
    if len(web[0]) >= inp.rules["web"]["validated_for_strong"] and non_stat:
        met["strong"].append("web+other")
    tier = next((t for t in TIERS[:-1] if met.get(t)), "none")

    rank = {t: i for i, t in enumerate(TIERS)}
    out.statements.sort(key=lambda s: rank.get(s["tier"], len(TIERS)))
    return {
        "tier": tier,
        "headline": HEADLINE[tier],
        "statements": out.statements,
        "separate": out.separate,
        "caveats": _caveats(inp, out, dismissed, rlist, web),
        "rules_met": {k: v for k, v in met.items() if v},
        "grading_version": inp.rules["version"],
    }
