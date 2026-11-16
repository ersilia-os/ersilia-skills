"""The report: plain HTML, organised by passage, readable top to bottom.

One unit throughout: the *passage* (whole prose paragraphs from one section, ~250-500
words; web_detectors.build_passages). Every score is given per passage.

    1. Headline         like web detectors: share of the prose that reads as AI (ring and
                        breakdown bar), the verdict tier, and the non-statistical checks
    2. Text + panel     the text with AI-like sentences highlighted (brighter = stronger,
                        human text left plain), beside a panel of per-passage combined
                        scores and each detector's per-passage scores and track record
    3. Scores by passage, trust in each detector, other evidence, details (below)

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
:root { --bg: #f6f7fb; --card: #ffffff; --ink: #14161f; --muted: #5d6275; --line: #e3e5ee;
        --ai: #ff5a36; --ai-soft: #ffe1d8; --amber: #ffb000; --amber-soft: #fff0c2; --hu: #12b76a; --hu-soft: #d9f7e8;
        --un: #c9ccd8; --accent: #5b4bdb;
        --h1: rgba(255, 214, 0, .28); --h2: rgba(255, 166, 0, .45); --h3: rgba(255, 84, 46, .42);
        --art: rgba(230, 0, 60, .35); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
        --bg: #0f1117; --card: #181b24; --ink: #eceef5; --muted: #a2a7b8; --line: #2a2e3b;
        --ai-soft: #4a2219; --amber-soft: #3f3311; --hu-soft: #12382a; --un: #3a3f50;
        --h1: rgba(255, 214, 0, .18); --h2: rgba(255, 166, 0, .32); --h3: rgba(255, 84, 46, .42); color-scheme: dark; } }
:root[data-theme="dark"] { --bg: #0f1117; --card: #181b24; --ink: #eceef5; --muted: #a2a7b8; --line: #2a2e3b;
        --ai-soft: #4a2219; --amber-soft: #3f3311; --hu-soft: #12382a; --un: #3a3f50;
        --h1: rgba(255, 214, 0, .18); --h2: rgba(255, 166, 0, .32); --h3: rgba(255, 84, 46, .42); color-scheme: dark; }
body { background: var(--bg); color: var(--ink); font: 15px/1.5 Inter, system-ui, -apple-system, sans-serif; }
.wrap { max-width: 1180px; margin: 0 auto; padding-block: 20px 56px;
        padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
h1 { font-size: 1.35rem; margin: 0; text-wrap: balance; }
.meta { color: var(--muted); font-size: .85rem; margin: .2rem 0 1rem; }
h2 { font-size: 1.05rem; margin: 2.2rem 0 .6rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px 20px; min-width: 0; }
a { color: var(--accent); }
/* headline */
.hero { display: grid; grid-template-columns: minmax(180px, 220px) 1fr minmax(220px, 300px); gap: 24px; align-items: center; }
.gauge { text-align: center; }
.ring { width: 160px; height: 160px; margin: 0 auto; border-radius: 50%; display: grid; place-items: center; }
.ring > div { width: 122px; height: 122px; border-radius: 50%; background: var(--card); display: grid; place-items: center; }
.big { font-size: 2.6rem; font-weight: 800; line-height: 1; }
.big small { font-size: 1.1rem; font-weight: 700; }
.cap { color: var(--muted); font-size: .8rem; margin-top: .6rem; }
.pill { display: inline-block; font-weight: 700; font-size: .8rem; letter-spacing: .04em; text-transform: uppercase;
        padding: 4px 10px; border-radius: 999px; }
.t-conclusive, .t-strong { background: var(--ai); color: #fff; }
.t-moderate { background: var(--amber); color: #2a1d00; }
.t-weak { background: var(--amber-soft); color: var(--ink); }
.t-none { background: var(--hu-soft); color: var(--ink); }
.headline { font-size: 1.15rem; font-weight: 650; margin: .6rem 0 .8rem; text-wrap: balance; }
.bar { display: flex; height: 14px; border-radius: 999px; overflow: hidden; background: var(--un); }
.bar span { display: block; height: 100%; }
.b-ai { background: var(--ai); } .b-un { background: var(--un); } .b-hu { background: var(--hu); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: .82rem; color: var(--muted); margin-top: .5rem; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; vertical-align: -1px; }
.where { margin: .8rem 0 0; font-size: .9rem; }
.checks { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; font-size: .88rem; }
.checks li { display: flex; gap: 8px; align-items: flex-start; }
.ok, .bad, .meh { flex: none; width: 20px; height: 20px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: 800; color: #fff; }
.ok { background: var(--hu); } .bad { background: var(--ai); } .meh { background: var(--amber); color: #2a1d00; }
/* two columns */
.cols { display: grid; grid-template-columns: minmax(0, 1fr) 330px; gap: 20px; margin-top: 20px; align-items: start; }
.side { position: sticky; top: env(safe-area-inset-top, 0px); display: grid; gap: 14px; }
.side h3 { font-size: .78rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); margin: 0 0 .6rem; }
.prow { display: grid; grid-template-columns: 2.2rem minmax(0, 1fr) 5.4rem; gap: 8px; align-items: center; font-size: .85rem;
        padding: 5px 0; text-decoration: none; color: var(--ink); }
.prow .nm { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prow .nm small { color: var(--muted); }
.mini { height: 6px; border-radius: 999px; background: var(--un); overflow: hidden; margin-top: 3px; }
.mini span { display: block; height: 100%; }
.tag { font-weight: 700; font-size: .78rem; text-align: center; border-radius: 6px; padding: 2px 4px; }
.tag.c-strong { background: var(--ai); color: #fff; } .tag.c-ai { background: var(--amber); color: #2a1d00; }
.tag.c-human { background: var(--hu-soft); } .tag.c-none, .tag.c-mid { background: var(--line); }
.drow { font-size: .85rem; padding: 6px 0; border-top: 1px solid var(--line); }
.drow:first-of-type { border-top: 0; }
.drow b { font-weight: 650; }
.drow .sub { color: var(--muted); font-size: .78rem; }
.chips { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 4px; }
.chip { font-size: .72rem; font-weight: 700; border-radius: 5px; padding: 1px 5px; }
.chip.ai { background: var(--ai); color: #fff; } .chip.hu { background: var(--hu-soft); } .chip.na { background: var(--line); color: var(--muted); }
/* the text */
.doc { font: 16.5px/1.75 "Source Serif 4", Georgia, serif; }
.doclegend { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 2; background: var(--card); font: .8rem/1.6 Inter, system-ui, sans-serif;
             color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 14px; padding: 8px 0 10px; border-bottom: 1px solid var(--line); margin-bottom: 8px; }
.doclegend span.sw { padding: 0 6px; border-radius: 4px; color: var(--ink); }
.psg { margin: 1.4rem 0; scroll-margin-top: 60px; }
.phead { font: 600 .82rem/1.4 Inter, system-ui, sans-serif; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
         border-top: 2px dashed var(--line); padding-top: .7rem; margin-bottom: .4rem; color: var(--muted); }
.phead .tag { font-size: .78rem; }
.psg p { margin: 0 0 .9rem; }
p.skip, .skip { color: var(--muted); font-size: .85rem; font-family: Inter, system-ui, sans-serif; }
.sec { font: 700 .95rem Inter, system-ui, sans-serif; margin: 1.6rem 0 .3rem; }
.h1 { background: var(--h1); } .h2 { background: var(--h2); } .h3 { background: var(--h3); }
.h1, .h2, .h3 { border-radius: 3px; box-decoration-break: clone; -webkit-box-decoration-break: clone; padding: 1px 0; }
.u2 { text-decoration: underline solid var(--ai); text-decoration-thickness: 2px; text-underline-offset: 4px; }
.m1 { background: var(--h1); } .m2 { background: var(--h2); }
mark.art { background: var(--art); color: inherit; outline: 2px solid var(--ai); border-radius: 3px; }
/* tables and folds */
.scroll { overflow-x: auto; }
.plain td, .plain th { background: none !important; text-align: right; white-space: nowrap; }
.plain td:first-child, .plain th:first-child, .plain td:last-child, .plain th:last-child { text-align: left; }
.plain th { white-space: normal; vertical-align: bottom; }
table { border-collapse: collapse; font-size: .82rem; width: 100%; }
th, td { border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: middle; }
th { color: var(--muted); font-weight: 600; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
td.c-human { background: var(--hu-soft); } td.c-ai, td.c-mixed { background: var(--amber-soft); } td.c-strong { background: var(--ai-soft); }
td.c-none { color: var(--muted); }
details { margin: .6rem 0; }
summary { cursor: pointer; font-weight: 650; }
.fold > summary { font-size: 1rem; padding: 4px 0; }
ul.facts li, .card ul li { margin: .3rem 0; }
@media (max-width: 980px) { .hero { grid-template-columns: 1fr; } .cols { grid-template-columns: minmax(0, 1fr); }
  .side { position: static; order: -1; } }
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
                    if heat_sents:  # the heat already carries it; hover names the sites
                        out.append(f'<span title="{e(lab)}">{e(text[s0:s1])}</span>')
                    else:
                        out.append(
                            f'<span class="{cls}" title="{e(lab)}">{e(text[s0:s1])}</span>'
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
        return ""

    def heat_title(x: dict) -> str:
        votes = "; ".join(
            f"{name(t)}: AI in {round(v['v'] * v['n'])} of {v['n']} splits"
            for t, v in sorted(x.get("tools", {}).items())
        )
        return f"combined: {math.exp(x['evidence']):.2g} times as likely AI as human · {votes}"

    def inline(a: int, b: int) -> str:
        """Text with the combined-evidence heat per sentence (when available) and marks."""
        out, pos, prev = [], a, ""
        for x in heat_sents:
            if x["start"] < a or x["end"] > b:
                continue
            cls = heat_class(x["evidence"])
            between = marks(pos, x["start"])
            if prev and cls == prev and not text[pos : x["start"]].strip():
                between = f'<span class="{cls}">{between}</span>'  # no gap inside a run
            out.append(between)
            prev = cls
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
        pev = comb_of.get(f"P{r['chunk']}")
        pcls = times_class(pev) if comb_of else r["cls"]
        sc_line = " · ".join(
            f"{e(name(t))} {pc(r['sc'][t])}" for t in tools if t in r["sc"]
        )
        blocks.append(
            f'<section class="psg" id="p{r["chunk"]}">'
            f'<div class="phead"><span class="tag {pcls or "c-mid"}">'
            f"{times_text(pev) if comb_of else e(agreement_words(r['n_ai'], r['n']))}</span>"
            f"<span>Passage {r['chunk']} · {e(' + '.join(r['sections']))} · {r['n_words']} words</span>"
            f'<span title="{e(sc_line)}">ⓘ</span></div>'
            f"{''.join(paras_html)}</section>"
        )
        pos = r["end"]
    if pos < len(text):
        blocks.append(gap(text, pos, len(text)))
    legend = (
        '<div class="doclegend"><span class="sw h3">10× or more AI</span><span class="sw h2">3× or more AI</span>'
        '<span class="sw h1">leans AI</span><span>plain = no signal, or human</span>'
        '<mark class="art">red box</mark><span>= leftover chatbot text</span><span>Hover a sentence for each site\'s verdict.</span></div>'
        if heat_sents
        else '<div class="doclegend"><span class="sw m1">one detector says AI</span><span class="sw m2">two or more</span>'
        '<mark class="art">red box</mark><span>= leftover chatbot text</span></div>'
    )
    text_html = legend + "".join(blocks)

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

    # Headline numbers, the way web detectors show them: share of the prose that reads as AI.
    tw = sum(x["n_words"] for x in heat_sents)
    if tw:
        ai_sh = (
            sum(x["n_words"] for x in heat_sents if x["evidence"] >= math.log(3)) / tw
        )
        hu_sh = (
            sum(x["n_words"] for x in heat_sents if x["evidence"] <= -math.log(3)) / tw
        )
        share_note = "of the checked prose is at least 3× more likely AI-written than human, combining the calibrated detectors"
    else:
        pw = sum(r["n_words"] for r in rows if r["n"]) or 1
        ai_sh = (
            sum(r["n_words"] for r in rows if r["n"] and r["n_ai"] / r["n"] > 0.5) / pw
        )
        hu_sh = sum(r["n_words"] for r in rows if r["n"] and r["n_ai"] == 0) / pw
        share_note = "of the checked prose is called AI by most detectors"
    un_sh = max(0.0, 1 - ai_sh - hu_sh)
    tier = g.get("tier", "none")
    tier_word = {
        "conclusive": "Conclusive evidence",
        "strong": "Strong evidence",
        "moderate": "Moderate evidence",
        "weak": "Weak evidence",
        "none": "No evidence",
    }.get(tier, tier)
    ring_col = (
        "var(--ai)"
        if ai_sh >= 0.5
        else ("var(--amber)" if ai_sh >= 0.15 else "var(--hu)")
    )
    deg = round(360 * ai_sh)
    where = ""
    if hotp:
        secs = {f"P{r['chunk']}": " + ".join(r["sections"]) for r in rows}
        where = (
            '<p class="where">Most AI-like: '
            + ", ".join(
                f'<a href="#p{pa["chunk"][1:]}">{e(secs.get(pa["chunk"], pa["chunk"]))}</a> ({math.exp(pa["evidence"]):.0f}×)'
                for pa in hotp[:3]
            )
            + "</p>"
        )
    doc_line = (
        f'<p class="where">Whole text: about <b>{dtimes:.1f}×</b> as likely AI-written as human '
        f"({len(evd.get('used', []))} calibrated detectors).</p>"
        if dtimes is not None and dtimes >= 1
        else (
            f'<p class="where">Whole text: about <b>{1 / dtimes:.1f}×</b> as likely human-written.</p>'
            if dtimes
            else ""
        )
    )

    def check(kind: str, txt: str) -> str:
        sym = {"ok": "✓", "bad": "!", "meh": "?"}[kind]
        return f'<li><span class="{kind}">{sym}</span><span>{txt}</span></li>'

    nread = len(jud.get("reading", []))
    checks = "".join(
        [
            check(
                "bad" if n_art else "ok",
                f"Leftover chatbot text: <b>{n_art} found</b>"
                if n_art
                else "No leftover chatbot text",
            ),
            check(
                "bad" if bad_refs else "ok",
                f"References: <b>{len(bad_refs)} of {len(rl)} not found</b>"
                if bad_refs
                else (
                    f"All {len(rl)} references are real" if rl else "No reference list"
                ),
            ),
            check(
                "meh" if style_flags else "ok",
                f"Style: AI-like in {style_flags} of {len(rows)} passages"
                if style_flags
                else "Style within the human range",
            ),
            check(
                "meh" if nread else "ok",
                f"Close reading: {nread} note(s)"
                if nread
                else "Close reading: nothing to note",
            ),
        ]
    )
    hero = (
        '<section class="card hero" id="verdict">'
        f'<div class="gauge"><div class="ring" style="background: conic-gradient({ring_col} {deg}deg, var(--un) 0)">'
        f'<div><div class="big">{round(100 * ai_sh)}<small>%</small></div></div></div>'
        f'<div class="cap">{e(share_note)}</div></div>'
        f'<div><span class="pill t-{e(tier)}">{e(tier_word)}</span><p class="headline">{e(g.get("headline", ""))}</p>'
        f'<div class="bar"><span class="b-ai" style="width:{100 * ai_sh:.1f}%"></span>'
        f'<span class="b-un" style="width:{100 * un_sh:.1f}%"></span><span class="b-hu" style="width:{100 * hu_sh:.1f}%"></span></div>'
        f'<div class="legend"><span><i class="dot b-ai"></i>Likely AI {pc(ai_sh)}</span>'
        f'<span><i class="dot b-un"></i>Unclear {pc(un_sh)}</span><span><i class="dot b-hu"></i>Likely human {pc(hu_sh)}</span></div>'
        f"{where}{doc_line}</div>"
        f'<ul class="checks">{checks}</ul></section>'
    )

    # Side panel: passages and detectors.
    prow = []
    for r in sorted(rows, key=lambda x: x["start"]):
        pev = comb_of.get(f"P{r['chunk']}")
        if comb_of:
            cls = times_class(pev) or "c-mid"
            w = 0 if pev is None else max(0, min(100, 50 + 50 * pev / math.log(30)))
            lab = times_text(pev).replace(" AI", "")
            colr = (
                "var(--ai)"
                if cls == "c-strong"
                else (
                    "var(--amber)"
                    if cls == "c-ai"
                    else ("var(--hu)" if cls == "c-human" else "var(--muted)")
                )
            )
        else:
            cls = r["cls"]
            w = 100 * r["n_ai"] / r["n"] if r["n"] else 0
            lab = f"{r['n_ai']}/{r['n']}"
            colr = (
                "var(--ai)" if r["n"] and r["n_ai"] / r["n"] > 0.5 else "var(--amber)"
            )
        prow.append(
            f'<a class="prow" href="#p{r["chunk"]}"><span class="tag {cls}">P{r["chunk"]}</span>'
            f'<span class="nm">{e(" + ".join(r["sections"]))} <small>{r["n_words"]}w</small>'
            f'<div class="mini"><span style="width:{w:.0f}%;background:{colr}"></span></div></span>'
            f'<span class="tag {cls}">{e(lab)}</span></a>'
        )
    drows = []
    for t in tools:
        c = (tcal.get(t) or {}).get("cal") or {}
        used = (tcal.get(t) or {}).get("used")
        chips = "".join(
            f'<span class="chip {"na" if r["sc"].get(t) is None else ("ai" if r["sc"][t] >= 0.5 else "hu")}" '
            f'title="passage {r["chunk"]}">{"–" if r["sc"].get(t) is None else pc(r["sc"][t])}</span>'
            for r in sorted(rows, key=lambda x: x["start"])
        )
        track = (
            f"on known texts: {round((c.get('fpr') or 0) * c.get('n_human', 0))}/{c.get('n_human')} false alarms, "
            f"caught {round((c.get('tpr') or 0) * c.get('n_ai', 0))}/{c.get('n_ai')} AI"
            if c
            else "not yet tested on known texts"
        )
        drows.append(
            f'<div class="drow"><b>{e(name(t))}</b>{" ✓" if reg.get(t, {}).get("weight") == "validated" else ""}'
            f"{'' if used else ' <span class=sub>(shown, not counted)</span>'}"
            f'<div class="sub">{e(track)}</div><div class="chips">{chips}</div></div>'
        )
    side = (
        '<aside class="side"><!-- section: glance -->'
        f'<div class="card"><h3>Passages {"· combined, calibrated" if comb_of else "· detectors saying AI"}</h3>{"".join(prow)}</div>'
        + (
            f'<div class="card"><h3>Detectors · score per passage</h3>{"".join(drows)}</div>'
            if drows
            else ""
        )
        + "</aside>"
    )

    return (
        f'<title>{e(case[:60])}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Source+Serif+4:wght@400;600&display=swap">\n'
        f"<style>{CSS}</style>\n"
        '<div class="wrap">'
        f'<h1>{e(case)}</h1><p class="meta">{e(kind)} · {e(context.replace("-", " "))} · {e(doc.get("n_words"))} words · '
        f"tested {e(tested)} · {len(rows)} passages</p>"
        f"<!-- section: answer -->{hero}"
        f'<div class="cols"><article class="card doc" id="text"><!-- section: text -->{text_html}</article>{side}</div>'
        f'<h2>Other evidence</h2><div class="card">{other}</div>'
        '<h2>Details</h2><div class="card">'
        f'<details class="fold"><summary>How much to trust each detector</summary><div class="plain">{trust}</div></details>'
        f'<details class="fold"><summary>Every check in one list</summary><ul class="facts">{"".join(f"<li>{x}</li>" for x in facts)}</ul></details>'
        f"{details}</div></div>"
    )
