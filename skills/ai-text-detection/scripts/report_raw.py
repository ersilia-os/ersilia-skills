"""The report: plain HTML, organised by passage, readable top to bottom.

One unit throughout: the *passage* (whole prose paragraphs from one section, ~250-500
words; web_detectors.build_passages). Every score is given per passage.

    1. The answer       verdict in plain words, then the facts behind it
    2. At a glance      one row per passage, one coloured cell per detector, agreement
    3. The text         passage by passage, each headed and coloured by agreement;
                        sentences the detectors marked are shaded (darker = more tools),
                        hover names the tools; text not sent to detectors is greyed
    4. Other evidence   references, leftover chatbot text, close reading
    5. Details          the detectors and their evidence, what did not run, limits

Called by build_report.py (``--style raw``, the default).
"""

from __future__ import annotations

import html
import math
import re
from pathlib import Path

from _common import REFS, read_json, words
from stylometry import features, style_score
from web_detectors import build_passages, is_prose

CSS = """
:root { color-scheme: light; --human: #dff2da; --mixed: #fff1bd; --ai: #ffcfb8; --strong: #ff9f80;
        --s1: #ffe0c2; --s2: #ffb784; --grey: #8a8a8a; --line: #bbbbbb; --ink: #151515; --bg: #ffffff; }
body { background: var(--bg); color: var(--ink); }
main { max-width: 54em; margin: 0 auto; padding-block: 14px 48px;
       padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
       font: 15px/1.55 Georgia, "Times New Roman", serif; }
h1 { font-size: 1.5em; margin: 0 0 .2em; }
h2 { margin-top: 1.8em; border-bottom: 1px solid var(--line); }
.answer { font-size: 1.15em; font-weight: bold; margin: .6em 0; }
ul.facts { margin: .3em 0 0; padding-left: 1.2em; }
ul.facts li { margin: .3em 0; }
table { border-collapse: collapse; font: 13px/1.35 system-ui, sans-serif; }
th, td { border: 1px solid var(--line); padding: 3px 7px; text-align: left; vertical-align: middle; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
.scroll { overflow-x: auto; }
.c-human { background: var(--human); }
.c-mixed { background: var(--mixed); }
.c-ai { background: var(--ai); }
.c-strong { background: var(--strong); }
.c-none { color: var(--grey); }
.psg { border-left: 6px solid var(--line); padding: 2px 0 2px 12px; margin: 1.2em 0; background: none; }
.psg.c-human { border-color: #7cc576; background: none; }
.psg.c-mixed { border-color: #e2b72c; background: none; }
.psg.c-ai { border-color: #f08a5d; background: none; }
.psg.c-strong { border-color: #d9481f; background: none; }
.phead { font: 600 14px/1.4 system-ui, sans-serif; }
.pscores { font: 12.5px/1.4 system-ui, sans-serif; color: #333333; margin-bottom: .5em; }
.psg p { margin: 0 0 .7em; }
p.skip { color: var(--grey); font-size: .9em; }
.sec { font: 600 13px system-ui, sans-serif; color: #555555; margin: 1.4em 0 .2em; }
.m1 { background: var(--s1); }
.m2 { background: var(--s2); }
.u1 { text-decoration: underline dotted #c65a1e; text-underline-offset: 3px; }
.u2 { text-decoration: underline solid #c65a1e; text-decoration-thickness: 2px; text-underline-offset: 3px; }
.h1 { background: #ffeadb; } .h2 { background: #ffcfb0; } .h3 { background: #ff9f7a; }
.g1 { background: #eef8eb; } .g2 { background: #d6eecf; }
mark.art { background: #ff8a8a; }
details { margin: .6em 0; }
summary { cursor: pointer; font-weight: bold; }
summary.skip { color: var(--grey); font-weight: normal; font-size: .9em; }
"""


def e(x: object) -> str:
    """HTML-escape."""
    return html.escape("" if x is None else str(x))


def num(x: float | None, d: int = 2) -> str:
    """Rounded number or a dash."""
    return "—" if x is None else f"{x:.{d}f}"


def pc(x: float | None) -> str:
    """0.83 -> '83%'."""
    return "—" if x is None else f"{round(100 * x)}%"


def agreement_class(n_ai: int, n: int, validated_ai: bool) -> str:
    """Colour of a passage from how many detectors say AI."""
    if n == 0:
        return "c-none"
    if validated_ai:
        return "c-strong"
    if n_ai == 0:
        return "c-human"
    if n >= 3 and n_ai / n > 0.5:
        return "c-ai"
    return "c-mixed"


def agreement_words(n_ai: int, n: int) -> str:
    """'4 of 5 detectors say AI' in plain words."""
    if n == 0:
        return "no detector run"
    if n_ai == 0:
        return f"all {n} detectors say human" if n > 1 else "the detector says human"
    return f"{n_ai} of {n} detectors say AI"


def is_heading_like(par: str) -> bool:
    """A short line without a full stop: shown as a heading."""
    t = par.strip()
    return len(words(t)) <= 12 and not t.endswith(".")


def gap(text: str, a: int, b: int) -> str:
    """Text between passages: headings shown plainly, other text greyed (not checked)."""
    out = []
    for raw in re.split(r"\n\s*\n", text[a:b]):
        t = raw.strip()
        if not t:
            continue
        if is_heading_like(t):
            out.append(f'<div class="sec">{e(t)}</div>')
        else:
            short = t[:300] + ("…" if len(t) > 300 else "")
            why = "not checked" if is_prose(t) else "not prose; not checked"
            out.append(f'<p class="skip">{e(short)} <i>({why})</i></p>')
    return "".join(out)


def build_raw(work: Path, case: str, kind: str, context: str) -> str:
    """The report fragment."""
    doc = read_json(work / "text.json") or {}
    text = doc.get("text", "")
    g = read_json(work / "grade.json") or {}
    arts = read_json(work / "artifacts.json") or {"hits": [], "hidden": []}
    refs = read_json(work / "references.json") or {"references": [], "counts": {}}
    jud = read_json(work / "judgements.json") or {}
    web = read_json(work / "web_detectors.json") or {}
    evd = read_json(work / "evidence.json") or {}
    heat_sents = [x for x in evd.get("sentences", []) if x.get("evidence") is not None]
    cal = read_json(REFS / "calibration.json") or {}
    wreg = read_json(REFS / "web_detectors.json") or {}
    reg = {t["id"]: t for t in wreg.get("tools", [])}
    order = wreg.get("default_order", [])
    smodel = (cal.get("stylometry") or {}).get("model")
    sthr = (cal.get("stylometry") or {}).get("thresholds") or {}
    ja = jud.get("artifacts", {})

    # Passages: the ones the detectors saw, or the same cut when none ran.
    passages = web.get("chunks") or [
        {"chunk": k, **p} for k, p in enumerate(build_passages(doc), 1)
    ]
    scores: dict[int, dict[str, float]] = {}
    labels: dict[tuple[int, str], str] = {}
    for r in web.get("results", []):  # the latest result per tool and passage wins
        scores.setdefault(r["chunk"], {})[r["tool"]] = r["score"]
        labels[(r["chunk"], r["tool"])] = r.get("label", "")
    tools = sorted(
        {t for s in scores.values() for t in s},
        key=lambda t: (
            reg.get(t, {}).get("weight") != "validated",
            order.index(t) if t in order else 99,
        ),
    )

    def name(t: str) -> str:
        return reg.get(t, {}).get("name", t)

    tcal = evd.get("tools", {})
    comb_of = {
        pa["chunk"]: pa["evidence"]
        for pa in evd.get("passages", [])
        if pa.get("evidence") is not None
    }

    def times_text(ev: float | None) -> str:
        if ev is None:
            return "\u2014"
        x = math.exp(ev)
        return f"{x:.1f}\u00d7 AI" if x >= 1 else f"{1 / x:.1f}\u00d7 human"

    def times_class(ev: float | None) -> str:
        if ev is None:
            return "c-none"
        if ev >= math.log(10):
            return "c-strong"
        if ev >= math.log(3):
            return "c-ai"
        if ev <= -math.log(3):
            return "c-human"
        return ""

    def cal_text(t: str) -> str:
        c = (tcal.get(t) or {}).get("cal") or {}
        if not c:
            return "not yet tested on known texts"
        return (
            f"On known texts: said AI for {round((c.get('fpr') or 0) * c.get('n_human', 0))} of {c.get('n_human')} human, "
            f"{round((c.get('tpr') or 0) * c.get('n_ai', 0))} of {c.get('n_ai')} AI"
        )

    rows = []
    for p in passages:
        k = p["chunk"]
        ptext = "\n\n".join(
            text[a:b] for a, b in p.get("paras", [[p["start"], p["end"]]])
        )
        st = style_score(features(ptext), smodel) if smodel else None
        sflag = (
            None
            if st is None or not sthr
            else ("1%" if st >= sthr["1%"] else ("5%" if st >= sthr["5%"] else None))
        )
        sc = scores.get(k, {})
        n_ai = sum(1 for v in sc.values() if v >= 0.5)
        v_ai = any(
            v >= 0.5 and reg.get(t, {}).get("weight") == "validated"
            for t, v in sc.items()
        )
        rows.append(
            {
                **p,
                "style": st,
                "sflag": sflag,
                "sc": sc,
                "n": len(sc),
                "n_ai": n_ai,
                "cls": agreement_class(n_ai, len(sc), v_ai),
            }
        )

    # Sentences the detectors marked, located in the text and merged across tools.
    span_of = {p["chunk"]: (p["start"], p["end"]) for p in passages}
    marked: dict[tuple[int, int], set[str]] = {}
    # Sentence marks from every split: passages (web_detectors.json) and the multi-split runs.
    from web_detectors import is_ai_colour

    mplan = read_json(work / "multi" / "plan.json") or {"units": []}
    multi_marks = []
    for u in mplan["units"]:
        if u["scale"] == "P":
            continue
        for f in (work / "plan").glob(f"*_chunk{u['chunk']}_highlights.json"):
            tool = f.name.split("_chunk")[0]
            for h in read_json(f) or []:
                if is_ai_colour(h.get("bg", "")):
                    multi_marks.append(
                        {
                            "tool": tool,
                            "span": (u["start"], u["end"]),
                            "text": h["text"],
                        }
                    )
    for h in web.get("highlights", []) + multi_marks:
        if "span" in h:
            a0, b0 = h["span"]
            pat = r"\s+".join(re.escape(tok) for tok in h["text"].split())
            m = re.search(pat, text[a0:b0]) if pat else None
            if m:
                marked.setdefault((a0 + m.start(), a0 + m.end()), set()).add(
                    name(h["tool"])
                )
            continue
        a0, b0 = span_of.get(h["chunk"], (0, len(text)))
        pat = r"\s+".join(re.escape(tok) for tok in h["text"].split())
        m = re.search(pat, text[a0:b0]) if pat else None
        if m:
            marked.setdefault((a0 + m.start(), a0 + m.end()), set()).add(
                name(h["tool"])
            )
    events_all = [
        (
            s0,
            s1,
            "m2" if len(t) >= 2 else "m1",
            "marked as AI by " + ", ".join(sorted(t)),
        )
        for (s0, s1), t in marked.items()
    ] + [
        (
            h["offset"],
            h["offset"] + len(h["match"]),
            "art",
            f"leftover chatbot text: {h['marker']}",
        )
        for h in arts["hits"]
        if h["in"] == "body" and ja.get(h["id"], {}).get("confirmed", True)
    ]

    def marks(a: int, b: int) -> str:
        """Escaped text[a:b]: artefacts marked red; sentences the sites marked as AI underlined
        (dotted: one site, solid: two or more); without heat, those sentences are shaded."""
        evs = sorted(
            (x for x in events_all if x[0] < b and x[1] > a),
            key=lambda x: (x[0], x[2] != "art"),
        )
        out, pos = [], a
        for s0, s1, cls, lab in evs:
            s0, s1 = max(s0, a), min(s1, b)
            if s0 < pos:
                continue
            out.append(e(text[pos:s0]))
            if cls == "art":
                out.append(
                    f'<mark class="art" title="{e(lab)}">{e(text[s0:s1])}</mark>'
                )
            else:
                if heat_sents and cls == "m1":
                    out.append(
                        e(text[s0:s1])
                    )  # one site only: the heat already carries it
                else:
                    c = "u2" if heat_sents else cls
                    out.append(
                        f'<span class="{c}" title="{e(lab)}">{e(text[s0:s1])}</span>'
                    )
            pos = s1
        out.append(e(text[pos:b]))
        return "".join(out)

    def heat_class(ev: float) -> str:
        if ev >= math.log(10):
            return "h3"
        if ev >= math.log(3):
            return "h2"
        if ev > 0.4:
            return "h1"
        if ev <= -math.log(3):
            return "g2"
        if ev <= -0.4:
            return "g1"
        return ""

    def heat_title(x: dict) -> str:
        votes = "; ".join(
            f"{name(t)}: AI in {round(v['v'] * v['n'])} of {v['n']} splits"
            for t, v in sorted(x.get("tools", {}).items())
        )
        return f"combined: {math.exp(x['evidence']):.2g} times as likely AI as human · {votes}"

    def inline(a: int, b: int) -> str:
        """Text with the combined-evidence heat per sentence (when available) and marks."""
        out, pos = [], a
        for x in heat_sents:
            if x["start"] < a or x["end"] > b:
                continue
            out.append(marks(pos, x["start"]))
            cls = heat_class(x["evidence"])
            inner = marks(x["start"], x["end"])
            out.append(
                f'<span class="{cls}" title="{e(heat_title(x))}">{inner}</span>'
                if cls
                else f'<span title="{e(heat_title(x))}">{inner}</span>'
            )
            pos = x["end"]
        out.append(marks(pos, b))
        return "".join(out).replace("\n", "<br>")

    def plabel(r: dict) -> str:
        return f"{r['chunk']} ({' + '.join(r['sections'])})"

    # 1. The answer.
    rl = refs.get("references", [])
    bad_refs = [
        r
        for r in rl
        if r["status"] in ("not-found", "doi-not-registered", "doi-points-elsewhere")
    ]
    n_art = sum(
        1 for h in arts["hits"] if ja.get(h["id"], {}).get("confirmed", True)
    ) + len(arts.get("hidden", []))
    hot = [r for r in rows if r["cls"] in ("c-ai", "c-strong")]
    human = [r for r in rows if r["cls"] == "c-human"]
    mixed = [r for r in rows if r["cls"] == "c-mixed"]
    not_run_valid = [
        t["name"]
        for t in reg.values()
        if t.get("weight") == "validated" and t["id"] not in tools
    ]
    style_flags = sum(1 for r in rows if r["sflag"])
    facts = [
        "Leftover chatbot text or hidden instructions: "
        + (f"<b>{n_art} found</b> (see Other evidence)." if n_art else "none found."),
        "References: "
        + (
            f"<b>{len(bad_refs)} of {len(rl)} could not be found as cited</b>."
            if bad_refs
            else (
                f"all {len(rl)} found in the literature databases."
                if rl
                else "no reference list found."
            )
        ),
        (
            f"Detectors: {len(tools)} ran on {len(rows)} passages ({', '.join(name(t) for t in tools)}). "
            + (
                f"Most of them say AI in <b>{', '.join(plabel(r) for r in hot)}</b>. "
                if hot
                else "No passage where most of them say AI. "
            )
            + (
                f"They all say human in {len(human)} and disagree in {len(mixed)}. "
                if human
                else f"They disagree in {len(mixed)} of the {len(rows)} passages. "
            )
            + (
                "None of them has published independent validation; the skill measured each one on known texts (see How much to trust each detector)."
                if not any(reg.get(t, {}).get("weight") == "validated" for t in tools)
                else ""
            )
        )
        if tools
        else "Detectors: none ran (confidential text, or not run this time).",
        "Style (vocabulary, stock phrasing, sentence rhythm): "
        + (
            f"<b>past the threshold in {style_flags} of {len(rows)} passages</b>."
            if style_flags
            else "within the range of human scientific text in every passage."
        ),
        f"Close reading: {len(jud.get('reading', []))} observation(s), under Other evidence.",
    ]
    hotp = sorted(
        (
            pa
            for pa in evd.get("passages", [])
            if pa.get("evidence") is not None and math.exp(pa["evidence"]) >= 3
        ),
        key=lambda pa: -pa["evidence"],
    )
    if hotp:
        secs = {f"P{r['chunk']}": " + ".join(r["sections"]) for r in rows}
        facts.insert(
            0,
            "Where: "
            + "; ".join(
                f"<b>passage {pa['chunk'][1:]} ({e(secs.get(pa['chunk'], ''))}), about {math.exp(pa['evidence']):.0f}× as likely AI</b>"
                for pa in hotp[:3]
            )
            + ". Elsewhere the calibrated signal is weak or absent.",
        )
    dtimes = (evd.get("document") or {}).get("times")
    if dtimes is not None:
        facts.insert(
            3,
            "Combined, calibrated on known texts: the whole text is "
            + (
                f"<b>about {dtimes:.1f} times as likely if AI-written</b>"
                if dtimes >= 1
                else f"<b>about {1 / dtimes:.1f} times as likely if human-written</b>"
            )
            + f" (detectors counted: {', '.join(name(t) for t in evd.get('used', [])) or 'none'}).",
        )
    stab = {
        t: v
        for t, v in (evd.get("stability") or {}).items()
        if v is not None and t in tools
    }
    if stab:
        shaky = [
            f"{name(t)} ({pc(v)})"
            for t, v in sorted(stab.items(), key=lambda kv: -kv[1])
            if v >= 0.2
        ]
        facts.append(
            "Stability across splits: "
            + (
                f"verdicts change with how the text is cut for {', '.join(shaky)} of sentences, which lowers their weight in practice."
                if shaky
                else "every detector gives the same verdict on a sentence however the text is cut."
            )
        )
    if not_run_valid:
        facts.append(
            "Not run: "
            + ", ".join(not_run_valid)
            + ", the detectors with the best independent evidence (they need a CAPTCHA ticked or an API key)."
        )
    answer = f'<p class="answer">{e(g.get("headline", ""))}</p><ul class="facts">{"".join(f"<li>{x}</li>" for x in facts)}</ul>'

    # 2. At a glance.
    def cell(v: float | None, t: str, k: int) -> str:
        if v is None:
            return '<td class="c-none">—</td>'
        cls = (
            ("c-strong" if reg.get(t, {}).get("weight") == "validated" else "c-ai")
            if v >= 0.5
            else "c-human"
        )
        return f'<td class="n {cls}" title="{e(labels.get((k, t), ""))}">{pc(v)}</td>'

    head = "".join(
        f'<th title="{e(cal_text(t))}. {e(reg.get(t, {}).get("evidence", ""))}">{e(name(t))}'
        + (" ✓" if reg.get(t, {}).get("weight") == "validated" else "")
        + "</th>"
        for t in tools
    )
    trs = "".join(
        f'<tr><td class="n"><a href="#p{r["chunk"]}">{r["chunk"]}</a></td><td>{e(" + ".join(r["sections"]))}</td>'
        f'<td class="n">{r["n_words"]}</td><td class="n {"c-ai" if r["sflag"] else "c-human"}">{num(r["style"])}</td>'
        + "".join(cell(r["sc"].get(t), t, r["chunk"]) for t in tools)
        + f'<td class="{r["cls"]}">{e(agreement_words(r["n_ai"], r["n"]))}</td>'
        + (
            f'<td class="n {times_class(comb_of.get(f"P{r["chunk"]}"))}">{times_text(comb_of.get(f"P{r["chunk"]}"))}</td>'
            if comb_of
            else ""
        )
        + "</tr>"
        for r in rows
    )
    glance = (
        "<p>Each detector's number is its estimated chance that the passage is AI-written. "
        '<span class="c-human">&nbsp;Green&nbsp;</span> = says human, <span class="c-ai">&nbsp;orange&nbsp;</span> = says AI, '
        '<span class="c-strong">&nbsp;red&nbsp;</span> = a validated detector (✓) says AI. '
        "Style is this skill's own score (0–1), calibrated on human scientific text. "
        "Hover a detector's name for how it did on known texts; click a passage number to jump to it. "
        + (
            "<b>Combined</b> weighs every detector by its results on known human and AI texts and uses every way of "
            "splitting the text: \u201c5\u00d7 AI\u201d means five times as likely if AI-written.</p>"
            if comb_of
            else "</p>"
        )
        + f'<div class="scroll"><table><tr><th>#</th><th>Section</th><th>Words</th><th>Style</th>{head}<th>Agreement</th>{"<th>Combined (calibrated)</th>" if comb_of else ""}</tr>{trs}</table></div>'
    )

    # How much to trust each detector (known-text calibration and stability across splits).
    trust_rows = []
    for t in tools:
        c = (tcal.get(t) or {}).get("cal") or {}
        w = tcal.get(t) or {}
        stab = (evd.get("stability") or {}).get(t)
        counted = "yes" if w.get("used") else f"no: {w.get('why', 'not calibrated')}"
        fpr_cls = (
            "c-human"
            if c and (c.get("fpr") or 0) <= 0.1
            else ("c-ai" if c else "c-none")
        )
        trust_rows.append(
            f"<tr><td>{e(name(t))}</td>"
            f'<td class="n {fpr_cls}">{pc(c.get("fpr")) if c else "\u2014"}</td>'
            f'<td class="n {"c-human" if c and c.get("fpr_domain") is not None and c["fpr_domain"] <= 0.1 else ("c-ai" if c and c.get("fpr_domain") is not None else "c-none")}" '
            f'title="{e(", ".join(pc(x) for x in c.get("domain_scores", [])) if c else "")}">'
            f"{pc(c.get('fpr_domain')) if c and c.get('fpr_domain') is not None else '\u2014'}</td>"
            f'<td class="n {"c-human" if c and c.get("fpr_shuffled") is not None and c["fpr_shuffled"] <= 0.1 else ("c-ai" if c and c.get("fpr_shuffled") is not None else "c-none")}">'
            f"{pc(c.get('fpr_shuffled')) if c and c.get('fpr_shuffled') is not None else '\u2014'}</td>"
            f'<td class="n">{pc(c.get("tpr")) if c else "\u2014"}</td>'
            f'<td class="n">{pc(c.get("polished_flagged")) if c else "\u2014"}</td>'
            f'<td class="n">{num(c.get("auroc")) if c else "\u2014"}</td>'
            f'<td class="n">{pc(stab) if stab is not None else "\u2014"}</td><td>{e(counted)}</td></tr>'
        )
    ncal = next(
        (
            (tcal.get(t) or {}).get("cal") or {}
            for t in tools
            if (tcal.get(t) or {}).get("cal")
        ),
        {},
    )
    trust = (
        "<p>Before trusting a detector on this document, the skill ran it on texts whose origin is known: "
        f"{ncal.get('n_human', '?')} published human scientific texts from before ChatGPT "
        f"({ncal.get('n_domain', 0)} of them from this document's own field) and {ncal.get('n_ai', '?')} AI-written ones "
        "(Claude and GPT), plus AI-polished human texts. "
        "<b>Cries wolf</b> = share of the human texts it called AI (lower is better); <b>same field</b> = only the texts from this document's field. <b>Catches</b> = share of the AI texts it called AI. "
        "<b>Split-dependent</b> = share of this document's sentences whose verdict changed with how the text was split (lower is steadier).</p>"
        f"<p>Caveats: the samples are small ({ncal.get('n_human', '?')} human, {ncal.get('n_ai', '?')} AI), so on the AI side one more "
        f"miss moves a rate by {round(100 / max(ncal.get('n_ai') or 10, 1))} points. The human texts are "
        "published papers that the detectors may have been trained on; <b>Cries wolf, shuffled</b> repeats the test with the "
        "sentences of those texts in a random order, which keeps the style but defeats memorisation. The AI texts are "
        "Claude and GPT output written for this skill; other models and human-edited AI text can be harder to catch.</p>"
        '<div class="scroll"><table><tr><th>Detector</th><th>Cries wolf</th><th>Cries wolf, same field</th><th>Cries wolf, shuffled</th><th>Catches</th><th>Flags AI-polished</th>'
        f"<th>AUROC</th><th>Split-dependent</th><th>Counted in Combined</th></tr>{''.join(trust_rows)}</table></div>"
        if tools
        else "<p>No detector ran.</p>"
    )

    # 3. The text, passage by passage, in reading order.
    blocks, pos = [], 0
    for i, r in enumerate(sorted(rows, key=lambda x: x["start"])):
        if r["start"] > pos:
            if i == 0:
                front = gap(text, pos, r["start"])
                last_heading = re.findall(r'<div class="sec">([^<]*)</div>$', front)
                if (
                    last_heading
                ):  # keep the heading right before the first passage (e.g. "Abstract")
                    front = front[: front.rfind('<div class="sec">')]
                blocks.append(
                    f'<details><summary class="skip">Title page, authors and affiliations (not checked)</summary>{front}</details>'
                    + (
                        f'<div class="sec">{last_heading[0]}</div>'
                        if last_heading
                        else ""
                    )
                )
            else:
                blocks.append(gap(text, pos, r["start"]))
        sent_starts = {a for a, _ in r.get("paras", [[r["start"], r["end"]]])}
        paras_html, ppos = [], r["start"]
        for m in [*re.finditer(r"\n\s*\n", text[r["start"] : r["end"]]), None]:
            pend = r["start"] + m.start() if m else r["end"]
            raw = text[ppos:pend]
            a0 = ppos + (len(raw) - len(raw.lstrip()))
            if raw.strip():
                if a0 in sent_starts:
                    paras_html.append(f"<p>{inline(a0, pend)}</p>")
                elif is_heading_like(raw):
                    paras_html.append(f'<div class="sec">{e(raw.strip())}</div>')
                else:
                    paras_html.append(
                        f'<p class="skip">{e(raw.strip())} <i>(not sent to the detectors)</i></p>'
                    )
            ppos = r["start"] + m.end() if m else r["end"]
        sc_line = " · ".join(
            f"{e(name(t))} {pc(r['sc'][t])}" for t in tools if t in r["sc"]
        )
        style_line = f"style {num(r['style'])}" + (
            f" (past {r['sflag']})" if r["sflag"] else ""
        )
        blocks.append(
            f'<section class="psg {r["cls"]}" id="p{r["chunk"]}">'
            f'<div class="phead">Passage {r["chunk"]} · {e(" + ".join(r["sections"]))} · {r["n_words"]} words — '
            f"{e(agreement_words(r['n_ai'], r['n']))}</div>"
            f'<div class="pscores">{sc_line}{" · " if sc_line else ""}{style_line}</div>{"".join(paras_html)}</section>'
        )
        pos = r["end"]
    if pos < len(text):
        blocks.append(gap(text, pos, len(text)))
    text_html = (
        (
            "<p>The left bar of each passage has the colour of its agreement. Each sentence is shaded by the combined, "
            'calibrated evidence: <span class="g2">leans human</span> \u00b7 <span class="g1">slightly human</span> \u00b7 no shade = no signal \u00b7 '
            '<span class="h1">slightly AI</span> \u00b7 <span class="h2">3\u00d7 or more AI</span> \u00b7 <span class="h3">10\u00d7 or more AI</span>. '
            '<span class="u2">Underlined</span> = two or more sites marked this sentence as AI. '
            "Hover any sentence for the details. "
            if heat_sents
            else "<p>The left bar of each passage has the colour of its agreement. Inside, "
            '<span class="m1">sentences one detector marked as AI</span> and <span class="m2">sentences two or more marked</span> '
            "are shaded (hover to see which). "
        )
        + '<mark class="art">Red</mark> = leftover chatbot text. '
        "Grey text was not sent to the detectors (title page, captions, equations, references).</p>"
        + "".join(blocks)
    )

    # 4. Other evidence.
    ev = []
    for h in arts["hits"]:
        if ja.get(h["id"], {}).get("confirmed", True):
            ev.append(
                f"<li><b>Leftover text ({e(h['tier'])})</b>: “{e(h['match'])}” in {e(h.get('section') or h['in'])}. {e(h['shows'])}</li>"
            )
    for h in arts.get("hidden", []):
        ev.append(
            f"<li><b>Hidden text</b> ({e(h['why'])}): “{e(h['text'][:200])}”</li>"
        )
    for r in bad_refs:
        links = " ".join(
            f'<a href="{e(u)}">lookup</a>' for u in r.get("queried", [])[:2]
        )
        ev.append(
            f"<li><b>Reference {r['n']}: {e(r['status'])}</b>. {e(r['raw'][:200])} {links}</li>"
        )
    for x in jud.get("reading", []):
        ev.append(
            f"<li><b>Close reading ({e(x.get('tier'))})</b>: {e(x['claim'])} "
            f"<i>“{e(x.get('quote', ''))}”</i> ({e(x.get('where', ''))})</li>"
        )
    for s in g.get("separate", []):
        ev.append(f"<li><b>{e(s['kind'])}</b>: {e(s['text'])}</li>")
    other = f"<ul>{''.join(ev)}</ul>" if ev else "<p>Nothing else to report.</p>"

    # How the numbers were computed (folded).
    mp = read_json(work / "multi" / "plan.json") or {"units": [], "sentences": []}
    n_scale = {sc: sum(1 for u in mp["units"] if u["scale"] == sc) for sc in "SPW"}
    per_tool = {t: len(v) for t, v in (evd.get("units_scored") or {}).items()}
    method_html = (
        "<details><summary>How the scores were computed</summary><ul>"
        f"<li>The prose was split three ways: {n_scale.get('S', 0)} whole sections, {n_scale.get('P', 0)} passages of whole paragraphs, "
        f"and {n_scale.get('W', 0)} overlapping windows of about 350 words that move forward half a window at a time. "
        "Each detector received only the splits within the text length it handles well.</li>"
        + (
            f"<li>Scans per detector on this document: {', '.join(f'{name(t)} {n}' for t, n in sorted(per_tool.items()))}.</li>"
            if per_tool
            else ""
        )
        + "<li>Each detector was first run on texts of known origin (see How much to trust each detector). Its rate of "
        "calling human text AI, and of catching AI text, turns each of its verdicts into a likelihood ratio.</li>"
        "<li>For each sentence, every split that contains it and every detector that scored that split vote. The votes "
        "are weighted by those likelihood ratios and combined, allowing for the detectors sharing part of their mistakes "
        "(average evidence times the square root of the number of detectors). Passages and the whole text average their sentences, weighted by length.</li>"
        "<li>Only detectors that were tested on at least 5 human and 5 AI texts and did better than chance are counted.</li>"
        "</ul></details>"
    )

    # 5. Details.
    trows = []
    for tid, t in reg.items():
        done = sum(1 for k in scores if tid in scores[k])
        skip = next((s["why"] for s in web.get("skipped", []) if s["tool"] == tid), "")
        status = (
            f"ran on {done} of {len(rows)} passages"
            if done
            else (f"not run: {skip}" if skip else "not tried")
        )
        trows.append(
            f"<tr><td>{e(t['name'])}</td><td>{e(t['weight'])}</td><td>{e(status)}</td><td>{e(t.get('evidence', ''))}</td></tr>"
        )
    details = (
        method_html
        + "<details><summary>The detectors, their track record, and what did not run</summary>"
        f'<div class="scroll"><table><tr><th>Detector</th><th>Weight</th><th>This document</th><th>Independent evidence</th></tr>{"".join(trows)}</table></div>'
        "<p>Validated (\u2713) means published independent studies found few false positives. The others count only "
        "through the skill's own tests on known texts (the calibrated combination); their raw scores alone never raise the verdict.</p></details>"
        f"<details><summary>Limits</summary><ul>{''.join(f'<li>{e(c)}</li>' for c in g.get('caveats', []))}</ul></details>"
    )

    tracked = (doc.get("metadata") or {}).get("tracked_changes_removed")
    tested = (
        "the author's original text (tracked changes set aside)"
        if tracked
        else "the text as it stands"
    )
    return (
        f'<title>{e(case[:60])}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>{CSS}</style>\n'
        "<!-- Single light look on purpose: a plain working document. -->\n<main>"
        f"<h1>{e(case)}</h1><p>{e(kind)} · {e(context.replace('-', ' '))} · {e(doc.get('n_words'))} words · "
        f"tested {e(tested)} · {len(rows)} passages</p>"
        f"<h2>The answer</h2>{answer}"
        f"<h2>Passages at a glance</h2>{glance}"
        f"<h2>How much to trust each detector</h2>{trust}"
        f"<h2>The text</h2>{text_html}"
        f"<h2>Other evidence</h2>{other}"
        f"<h2>Details</h2>{details}</main>"
    )
