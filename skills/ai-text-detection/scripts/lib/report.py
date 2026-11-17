"""Render the evidence report as one self-contained HTML fragment (build_report.py).

The verdict comes first and the detector statistics never speak louder than it:

    Verdict      the tier and headline from grade.json; one sentence and one bar on
                 what the combined detectors say; the non-statistical checks (leftover
                 chatbot text, references, style, close reading)
    Text         the document, passage by passage; sentences shaded by the combined,
                 calibrated evidence (evidence.py), human-leaning text left plain;
                 leftover chatbot text boxed; close-reading notes as tags beside the
                 words they quote; title page, captions and tables folded or greyed
    Side panel   each passage's combined value, then a grid of each detector's score per
                 passage with its record on known texts
    Findings     what the user can say, one line each (grade.json's statements; how to
                 re-check it; close-reading ones link to their place in the text), next
                 to this case's limits when there are any (grade.json's caveats).
                 Folded in the same card, every item to quote from: leftover chatbot
                 text, hidden text, references not found, notes whose quote could not
                 be placed

A passage is whole prose paragraphs from one section, 250-600 words
(lib.splits.build_passages): the unit the reader sees. The scores themselves come from
every split (segments.py) through evidence.py.

Styles live in ``assets/report.css``.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from lib.common import ASSETS, REFS, read_json
from lib.detectors import Detections
from lib.splits import build_plan
from lib.style import features, style_score
from lib.text import first_sentence, is_prose, paragraph_spans, words

CSS_FILE = ASSETS / "report.css"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800"
    "&family=Source+Serif+4:wght@400;600&display=swap"
)
LN3, LN10 = math.log(3), math.log(10)
EVEN = math.log(1.2)  # closer to 1 than this either way reads as no signal
TIER_WORD = {
    "conclusive": "Conclusive evidence",
    "strong": "Strong evidence",
    "moderate": "Moderate evidence",
    "weak": "Weak evidence",
    "none": "No evidence",
}
BAD_REF = {
    "not-found": "not found in any literature database",
    "doi-not-registered": "its DOI is not registered",
    "doi-points-elsewhere": "its DOI belongs to a different paper",
}
CONTEXT = {
    "collaborator-draft": "a collaborator's draft",
    "reviewer-of-my-paper": "a review of your manuscript",
    "manuscript-i-review": "a manuscript you are reviewing",
    "grant-i-review": "a grant application you are reviewing",
    "other": "a document",
}


# ---------------------------------------------------------------- small formatters


def e(x: object) -> str:
    """HTML-escape."""
    return html.escape("" if x is None else str(x))


def pc(x: float | None) -> str:
    """0.83 -> '83%'."""
    return "—" if x is None else f"{round(100 * x)}%"


def times_text(ev: float | None) -> str:
    """Log evidence -> '5.3× AI', '1.5× human', or 'even' within 1.2× either way."""
    if ev is None:
        return "—"
    if abs(ev) < EVEN:
        return "even"
    x = math.exp(ev)
    return f"{x:.1f}× AI" if x >= 1 else f"{1 / x:.1f}× human"


def plural(n: int, word: str) -> str:
    """'1 note' / '3 notes'."""
    return f"{n} {word}{'' if n == 1 else 's'}"


def times_class(ev: float | None) -> str:
    """Colour class for a combined value: 10x AI, 3x AI, 3x human, or neutral."""
    if ev is None:
        return "c-none"
    if ev >= LN10:
        return "c-strong"
    if ev >= LN3:
        return "c-ai"
    if ev <= -LN3:
        return "c-human"
    return "c-mid"


def heat_class(ev: float) -> str:
    """Sentence shading: 10x AI, 3x AI, leaning AI; human-leaning stays plain."""
    if ev >= LN10:
        return "h3"
    if ev >= LN3:
        return "h2"
    if ev > 0.4:
        return "h1"
    return ""


def is_heading_like(par: str) -> bool:
    """A short line without a full stop: shown as a heading."""
    t = par.strip()
    return len(words(t)) <= 12 and not t.endswith(".")


# ---------------------------------------------------------------- unchecked text


def table_html(rows: list[str]) -> str:
    """A document table (cells separated by " | ") as a plain table; a one-cell row is a
    group label spanning the table."""
    cells = [[c.strip() for c in r.split("|") if c.strip()] for r in rows]
    cells = [c for c in cells if c]
    n = max(len(c) for c in cells)
    out = []
    for i, c in enumerate(cells):
        if len(c) == 1:
            out.append(f'<tr class="grp"><td colspan="{n}">{e(c[0])}</td></tr>')
        else:
            tag = "th" if i == 0 else "td"
            out.append("<tr>" + "".join(f"<{tag}>{e(x)}</{tag}>" for x in c) + "</tr>")
    return f'<div class="scroll"><table class="doctable">{"".join(out)}</table></div>'


def unchecked_html(text: str, a: int, b: int) -> str:
    """Text the detectors did not see: headings plain, document tables folded under their
    caption, everything else greyed."""
    paras = [t.strip() for t in re.split(r"\n\s*\n", text[a:b]) if t.strip()]
    out: list[str] = []
    i = 0
    while i < len(paras):
        t = paras[i]
        if "|" in t:  # table rows, plus one-cell group labels between rows
            rows = []
            while i < len(paras) and (
                "|" in paras[i]
                or (
                    i + 1 < len(paras)
                    and "|" in paras[i + 1]
                    and len(words(paras[i])) <= 8
                )
            ):
                rows.append(paras[i])
                i += 1
            caption = "Table"
            if out and out[-1].startswith('<div class="sec">Table'):
                caption = html.unescape(re.sub(r"<[^>]+>", "", out.pop()))
            out.append(
                f'<details class="tbl"><summary class="skip">{e(caption)} '
                f"<i>(table, {len(rows)} rows; not checked)</i></summary>{table_html(rows)}</details>"
            )
            continue
        if is_heading_like(t):
            out.append(f'<div class="sec">{e(t)}</div>')
        else:
            short = t[:120] + ("…" if len(t) > 120 else "")
            why = "not checked" if is_prose(t) else "not prose; not checked"
            out.append(f'<p class="skip">{e(short)} <i>({why})</i></p>')
        i += 1
    return "".join(out)


# ---------------------------------------------------------------- inputs


@dataclass
class Inputs:
    """Everything the page shows, read once from the work folder and references/."""

    work: Path
    doc: dict
    grade: dict
    arts: dict
    refs: list[dict]
    jud: dict
    web: Detections
    evd: dict
    reg: dict[str, dict]
    style_model: dict | None
    style_thr: dict
    rules: dict
    tools: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """The document text."""
        return self.doc.get("text", "")

    @property
    def heat(self) -> list[dict]:
        """Sentences with a combined value (evidence.py)."""
        return [
            x for x in self.evd.get("sentences", []) if x.get("evidence") is not None
        ]

    @property
    def combined(self) -> dict[str, float]:
        """Combined value per passage id ('P1' ...)."""
        return {
            p["chunk"]: p["evidence"]
            for p in self.evd.get("passages", [])
            if p.get("evidence") is not None
        }

    def name(self, tool: str) -> str:
        """A detector's display name."""
        return self.reg.get(tool, {}).get("name", tool)

    def confirmed(self, hit: dict) -> bool:
        """An artefact hit not set aside in judgements.json."""
        return self.jud.get("artifacts", {}).get(hit["id"], {}).get("confirmed", True)

    def is_leftover(self, hit: dict) -> bool:
        """A confirmed hit that is leftover AI-tool output: a conclusive or strong marker in
        a category grading.json treats as such (not tortured phrases, prompt injections,
        weak typography quirks or stock phrasing)."""
        cats = set(self.rules.get("conclusive", {}).get("categories", [])) | set(
            self.rules.get("strong", {}).get("strong_categories", [])
        )
        return (
            self.confirmed(hit)
            and hit["category"] in cats
            and hit["tier"] in ("conclusive", "strong")
        )

    def bad_refs(self) -> list[dict]:
        """References not found as cited, minus those Claude cleared by hand."""
        cleared = {
            k
            for k, v in (self.jud.get("references") or {}).items()
            if v.get("fabricated") is False
        }
        return [
            r
            for r in self.refs
            if r["status"] in BAD_REF and str(r["n"]) not in cleared
        ]


def load(work: Path) -> Inputs:
    """Read the work folder."""
    cal = (read_json(REFS / "calibration.json") or {}).get("stylometry") or {}
    wreg = read_json(REFS / "web_detectors.json") or {}
    inp = Inputs(
        work=work,
        doc=read_json(work / "text.json") or {},
        grade=read_json(work / "grade.json") or {},
        arts=read_json(work / "artifacts.json") or {"hits": [], "hidden": []},
        refs=(read_json(work / "references.json") or {}).get("references", []),
        jud=read_json(work / "judgements.json") or {},
        web=Detections.load(work),
        evd=read_json(work / "evidence.json") or {},
        reg={t["id"]: t for t in wreg.get("tools", [])},
        style_model=cal.get("model"),
        style_thr=cal.get("thresholds") or {},
        rules=read_json(REFS / "grading.json") or {},
    )
    order = wreg.get("default_order", [])
    ran = set(inp.web.summary()) | set(inp.evd.get("used") or [])
    inp.tools = sorted(
        ran,
        key=lambda t: (
            inp.reg.get(t, {}).get("weight") != "validated",
            order.index(t) if t in order else len(order),
            t,
        ),
    )
    return inp


def passage_rows(inp: Inputs) -> list[dict]:
    """The passages in reading order, with each detector's score and the style score.
    Without a plan (no detector was run) the passages are cut from the document here."""
    passages = inp.web.passages or [
        u for u in build_plan(inp.doc)["units"] if u["scale"] == "P"
    ]
    scores = inp.web.passage_scores()
    rows = []
    for p in passages:
        body = "\n\n".join(inp.text[a:b] for a, b in p["spans"])
        st = style_score(features(body), inp.style_model) if inp.style_model else None
        flagged = bool(st is not None and inp.style_thr and st >= inp.style_thr["5%"])
        sc = scores.get(p["chunk"], {})
        rows.append(
            {
                **p,
                "id": p["chunk"],
                "n": int(p["chunk"][1:]),
                "label": " + ".join(p["sections"]),
                "style_flag": flagged,
                "sc": sc,
                "n_ai": sum(1 for v in sc.values() if v >= 0.5),
            }
        )
    return sorted(rows, key=lambda r: r["start"])


# ---------------------------------------------------------------- the text column


class TextRenderer:
    """The document with sentence heat, site marks (hover), artefacts and notes."""

    def __init__(self, inp: Inputs) -> None:
        self.inp, self.text, self.heat = inp, inp.text, inp.heat
        self.events = self._site_marks() + self._artefacts() + self._notes()
        self.notes_placed: set[int] = set()

    def _locate(self, chunk_text: str, a0: int, b0: int) -> tuple[int, int] | None:
        pat = r"\s+".join(re.escape(tok) for tok in chunk_text.split())
        m = re.search(pat, self.text[a0:b0]) if pat else None
        return (a0 + m.start(), a0 + m.end()) if m else None

    def _site_marks(self) -> list[tuple]:
        """Sentences the sites highlighted as AI, from every split, merged across tools."""
        span_of = {
            u["chunk"]: (u["start"], u["end"]) for u in self.inp.web.plan["units"]
        }
        found = [
            (h["tool"], span_of[h["chunk"]], h["text"])
            for h in self.inp.web.site_marks()
            if h["chunk"] in span_of
        ]
        marked: dict[tuple[int, int], set[str]] = {}
        for tool, (a0, b0), t in found:
            loc = self._locate(t, a0, b0)
            if loc:
                marked.setdefault(loc, set()).add(self.inp.name(tool))
        return [
            (
                s0,
                s1,
                "m2" if len(t) >= 2 else "m1",
                "marked as AI by " + ", ".join(sorted(t)),
            )
            for (s0, s1), t in marked.items()
        ]

    def _artefacts(self) -> list[tuple]:
        return [
            (
                h["offset"],
                h["offset"] + len(h["match"]),
                "art",
                f"leftover chatbot text ({h['marker']}): {h.get('shows', '')}",
            )
            for h in self.inp.arts["hits"]
            if h["in"] == "body" and self.inp.is_leftover(h)
        ]

    def _find_quote(self, q: str) -> tuple[int, int] | None:
        """A close-reading quote's first locatable fragment (quotes may elide with '…' or
        join two places with ' / ')."""
        for frag in re.split(r"\s*(?:…|\.\.\.|\s/\s)\s*", q or ""):
            toks = frag.strip(" “”\"'").split()
            if len(toks) < 3:
                continue
            pat = r"\s+".join(
                re.sub(r"\\[‘’'\"“”]", "[‘’'\"“”]", re.escape(t)) for t in toks
            )
            m = re.search(pat, self.text)
            if m:
                return m.start(), m.end()
        return None

    def _notes(self) -> list[tuple]:
        out = []
        for i, x in enumerate(self.inp.jud.get("reading", [])):
            loc = self._find_quote(x.get("quote", ""))
            if loc:
                out.append((loc[0], loc[1], f"note{i}", x["claim"]))
        return out

    def marks(self, a: int, b: int) -> str:
        """Escaped text[a:b] with artefacts boxed and notes tagged. The sites' own sentence
        marks are shaded only when there is no combined heat (which already includes them)."""
        here = [x for x in self.events if x[0] < b and x[1] > a]
        keep = [x for x in here if x[2] == "art" or x[2].startswith("note")]
        here = keep + [  # site marks give way to notes and artefacts
            x
            for x in here
            if x not in keep and not any(k[0] < x[1] and k[1] > x[0] for k in keep)
        ]
        out, pos = [], a
        for s0, s1, cls, lab in sorted(here, key=lambda x: (x[0], x[2] != "art")):
            s0, s1 = max(s0, a), min(s1, b)
            if s0 < pos:
                continue
            out.append(e(self.text[pos:s0]))
            seg = e(self.text[s0:s1])
            if cls == "art":
                out.append(f'<mark class="art" title="{e(lab)}">{seg}</mark>')
            elif cls.startswith("note"):
                self.notes_placed.add(int(cls[4:]))
                out.append(
                    f'<span class="noted" id="note{cls[4:]}">{seg}</span>'
                    f'<span class="note" tabindex="0" data-note="{e(lab)}">note</span>'
                )
            elif self.heat:  # the sentence's hover already lists every site's verdict
                out.append(seg)
            else:
                out.append(f'<span class="{cls}" title="{e(lab)}">{seg}</span>')
            pos = s1
        out.append(e(self.text[pos:b]))
        return "".join(out)

    def _heat_title(self, x: dict) -> str:
        votes = "; ".join(
            f"{self.inp.name(t)}: AI in {round(v['v'] * v['n'])} of {v['n']} splits"
            for t, v in sorted(x.get("tools", {}).items())
        )
        sites = sorted(
            {
                site
                for s0, s1, cls, lab in self.events
                if cls in ("m1", "m2") and s0 < x["end"] and s1 > x["start"]
                for site in lab.removeprefix("marked as AI by ").split(", ")
            }
        )
        marked = f" · highlighted as AI by {', '.join(sites)}" if sites else ""
        return (
            f"combined: {math.exp(x['evidence']):.2g} times as likely AI as human · "
            f"{votes}{marked}"
        )

    def paragraph(self, a: int, b: int) -> str:
        """One checked paragraph, sentence by sentence."""
        out, pos, prev = [], a, ""
        for x in self.heat:
            if x["start"] < a or x["end"] > b:
                continue
            cls = heat_class(x["evidence"])
            between = self.marks(pos, x["start"])
            if prev and cls == prev and not self.text[pos : x["start"]].strip():
                between = f'<span class="{cls}">{between}</span>'  # no gap inside a run
            out.append(between)
            inner = self.marks(x["start"], x["end"])
            attr = f' class="{cls}"' if cls else ""
            out.append(f'<span{attr} title="{e(self._heat_title(x))}">{inner}</span>')
            prev, pos = cls, x["end"]
        out.append(self.marks(pos, b))
        return "".join(out).replace("\n", "<br>")

    def passage(self, r: dict) -> str:
        """A passage: header with its combined value, then its paragraphs; unchecked text
        inside it (headings, captions, tables) rendered as such."""
        text = self.text
        starts = {a for a, _ in r["spans"]}
        parts, held = [], None
        for pos, end in paragraph_spans(text, r["start"], r["end"]):
            raw = text[pos:end]
            a0 = pos + (len(raw) - len(raw.lstrip()))
            if not raw.strip():
                continue
            if a0 in starts:
                if held is not None:
                    parts.append(unchecked_html(text, held, a0))
                    held = None
                parts.append(f"<p>{self.paragraph(a0, end)}</p>")
            elif held is None:
                held = a0
        if held is not None:
            parts.append(unchecked_html(text, held, r["end"]))
        ev = self.inp.combined.get(r["id"])
        tag = (
            times_text(ev)
            if self.inp.combined
            else f"{r['n_ai']} of {len(r['sc'])} say AI"
            if r["sc"]
            else "not scanned"
        )
        scores = " · ".join(
            f"{self.inp.name(t)} {pc(r['sc'][t])}"
            for t in self.inp.tools
            if t in r["sc"]
        )
        info = f'<span title="{e(scores)}">ⓘ</span>' if scores else ""
        head = (
            f'<span class="tag {times_class(ev)}">{e(tag)}</span>'
            f"<span>Passage {r['n']} · {e(r['label'])} · {r['n_words']} words</span>{info}"
        )
        if self.quiet(r):
            return (
                f'<details class="psg" id="p{r["n"]}"><summary class="phead">{head}'
                f'<span class="fold">{"style AI-like, " if r["style_flag"] else ""}no sentence flagged</span></summary>{"".join(parts)}</details>'
            )
        return (
            f'<section class="psg" id="p{r["n"]}"><div class="phead">{head}</div>'
            f"{''.join(parts)}</section>"
        )

    def quiet(self, r: dict) -> bool:
        """True when the detectors scored the passage and there is nothing to look at in
        it: no AI-like sentence, no leftover text, no note, and it does not lean AI as a
        whole. Such a passage folds."""
        a, b = r["start"], r["end"]
        if not r["sc"]:
            return False
        if any(
            x[0] < b and x[1] > a
            for x in self.events
            if not self.heat or x[2] == "art" or x[2].startswith("note")
        ):
            return False
        if self.inp.combined:
            ev = self.inp.combined.get(r["id"])
            return (
                ev is not None
                and ev < LN3
                and not any(
                    heat_class(x["evidence"])
                    for x in self.heat
                    if x["start"] >= a and x["end"] <= b
                )
            )
        return r["n_ai"] == 0

    def document(self, rows: list[dict]) -> str:
        """The whole text in reading order, with the legend on top."""
        text, blocks, pos = self.text, [], 0
        for i, r in enumerate(rows):
            if r["start"] > pos:
                if i == 0:  # the title page folds; the heading just before stays
                    front = unchecked_html(text, pos, r["start"])
                    last = re.findall(r'<div class="sec">([^<]*)</div>$', front)
                    if last:
                        front = front[: front.rfind('<div class="sec">')]
                    blocks.append(
                        '<details><summary class="skip">Title page, authors and affiliations '
                        f"(not checked)</summary>{front}</details>"
                        + (f'<div class="sec">{last[0]}</div>' if last else "")
                    )
                else:
                    blocks.append(unchecked_html(text, pos, r["start"]))
            blocks.append(self.passage(r))
            pos = r["end"]
        if pos < len(text):
            blocks.append(unchecked_html(text, pos, len(text)))
        legend = (
            '<span class="sw h3">10× or more AI</span><span class="sw h2">3× or more AI</span>'
            '<span class="sw h1">leans AI</span>'
            if self.heat
            else '<span class="sw m1">one detector says AI</span><span class="sw m2">two or more</span>'
            if self.inp.tools
            else ""
        )
        legend += (
            '<span><mark class="art">boxed</mark> leftover chatbot text</span>'
            '<span><span class="note">note</span> close-reading note</span>'
            + (
                '<span class="hover-only">Hover a sentence for each detector\'s verdict.</span>'
                if self.heat
                else ""
            )
        )
        n_quiet = sum(1 for r in rows if self.quiet(r))
        if n_quiet:
            legend += f"<span>{plural(n_quiet, 'passage')} with no sentence flagged are folded.</span>"
        return f'<div class="doclegend">{legend}</div>' + "".join(blocks)


# ---------------------------------------------------------------- headline and panel


def share_bar(parts: list[tuple[str, str, float]], basis: str) -> str:
    """A stacked bar of shares of the checked prose (by words) with its legend. Each part
    is (css class, label, share)."""
    bar = "".join(
        f'<span class="{cls}" style="width:{100 * share:.1f}%"></span>'
        for cls, _, share in parts
    )
    legend = "".join(
        f'<span><i class="dot {cls}"></i>{e(label)} <b class="num">{pc(share)}</b></span>'
        for cls, label, share in parts
    )
    return (
        f'<div class="bar" role="img" aria-label="{e(basis)}">{bar}</div>'
        f'<div class="legend" title="{e(basis)}">{legend}</div>'
    )


def detector_line(inp: Inputs, rows: list[dict]) -> str:
    """What the detectors say, in one sentence and one bar: never louder than the tier."""
    heat = inp.heat
    words_ = sum(x["n_words"] for x in heat)
    scanned = [r for r in rows if r["sc"]]
    if words_:

        def share(lo: float, hi: float) -> float:
            return sum(x["n_words"] for x in heat if lo <= x["evidence"] < hi) / words_

        strong, some, human = (
            share(LN10, math.inf),
            share(LN3, LN10),
            share(-math.inf, -LN3 + 1e-12),
        )
        bar = share_bar(
            [
                ("b-ai", "10× or more AI", strong),
                ("b-some", "3× to 10× AI", some),
                ("b-un", "no clear signal", max(0.0, 1 - strong - some - human)),
                ("b-hu", "3× or more human", human),
            ],
            "Share of the checked prose, by words, at each level of the combined detectors.",
        )
    elif scanned:
        pw = sum(r["n_words"] for r in scanned)
        ai = sum(r["n_words"] for r in scanned if r["n_ai"] / len(r["sc"]) > 0.5) / pw
        hu = sum(r["n_words"] for r in scanned if r["n_ai"] == 0) / pw
        bar = share_bar(
            [
                ("b-some", "most detectors say AI", ai),
                ("b-un", "detectors disagree", max(0.0, 1 - ai - hu)),
                ("b-hu", "no detector says AI", hu),
            ],
            "Share of the scanned prose, by words. These detectors are not yet tested on known texts.",
        )
    else:
        return '<p class="where">Detectors: no detector was run (confidential text, or not run this time).</p>'
    doc_ev = (inp.evd.get("document") or {}).get("evidence")
    whole = ""
    if doc_ev is not None:
        times = math.exp(
            doc_ev
        )  # not the rounded "times" in evidence.json (can be 0.0)
        n = plural(len(inp.evd.get("used", [])), "detector")
        if abs(doc_ev) < EVEN:
            said = "the whole text is about as likely AI-written as human"
        elif times >= 1:
            said = f"the whole text is about <b>{times:.1f}×</b> as likely AI-written as human"
        else:
            said = f"the whole text is about <b>{1 / times:.1f}×</b> as likely human-written as AI"
        whole = f'<p class="where">{n} combined: {said}.</p>'
    label = {r["id"]: (r["n"], r["label"]) for r in rows}
    hot = sorted(
        ((pid, ev) for pid, ev in inp.combined.items() if ev >= LN3 and pid in label),
        key=lambda x: -x[1],
    )
    where = (
        '<p class="where">Most AI-like passages: '
        + ", ".join(
            f'<a href="#p{label[pid][0]}">{e(label[pid][1])}</a> ({math.exp(ev):.0f}×)'
            for pid, ev in hot[:3]
        )
        + ".</p>"
        if hot
        else ""
    )
    return whole + bar + where


def headline(inp: Inputs, rows: list[dict]) -> str:
    """The verdict first: tier and headline, then the detectors' line, then the checks."""
    tier = inp.grade.get("tier", "none")
    return (
        '<section class="card hero" id="verdict"><div>'
        f'<span class="pill t-{e(tier)}">{e(TIER_WORD.get(tier, tier))}</span>'
        f'<p class="headline">{e(inp.grade.get("headline", ""))}</p>'
        f"{detector_line(inp, rows)}</div>"
        f'<ul class="checks">{checks(inp, rows)}</ul></section>'
    )


NOT_RUN = "Web detector "


def findings(inp: Inputs, placed: set[int]) -> str:
    """What the user can say, each statement with how to re-check it, next to what the
    case's evidence is limited by, when anything is. A close-reading statement links to its place in the text."""
    items, weak = [], []
    for st in inp.grade.get("statements", []):
        ev = st.get("evidence") or [""]
        note = int(ev[0][4:]) - 1 if ev[0].startswith("read") else None
        link = (
            f' <a href="#note{note}">in the text</a>'
            if note is not None and note in placed
            else ""
        )
        check = (
            f'<span class="check">To re-check: {e(st["check"])}</span>'
            if st.get("check")
            else ""
        )
        title = st.get("title") or first_sentence(st["text"])
        (weak if st["tier"] in ("weak", "none") else items).append(
            f'<li><span class="tag t-{e(st["tier"])}">{e(st["tier"])}</span>'
            f"<details><summary>{e(title)}{link}</summary>{e(st['text'])}{check}</details></li>"
        )
    items += [
        f'<li><span class="tag t-sep">{e(s["kind"])}</span>'
        f"<details><summary>{e(s.get('title') or first_sentence(s['text']))}</summary>"
        f"{e(s['text'])}</details></li>"
        for s in inp.grade.get("separate", [])
    ]
    if weak:
        items.append(
            f'<li class="more"><details><summary>{plural(len(weak), "weaker observation")}'
            f'</summary><ul class="said">{"".join(weak)}</ul></details></li>'
        )
    caveats = inp.grade.get("caveats", [])
    not_run = [c for c in caveats if c.startswith(NOT_RUN)]
    limits = "".join(f"<li>{e(c)}</li>" for c in caveats if c not in not_run)
    if not_run:
        limits += (
            f"<li><details><summary>{plural(len(not_run), 'detector')} could not be run</summary><ul>"
            + "".join(f"<li>{e(c.removeprefix(NOT_RUN))}</li>" for c in not_run)
            + "</ul></details></li>"
        )
    quotes = other_evidence(inp, placed)
    if quotes:
        items.append(quotes)
    if not items and not limits:
        return ""
    said = (
        f'<ul class="said">{"".join(items)}</ul>'
        if items
        else '<p class="skip">Nothing was found that supports a statement.</p>'
    )
    side = (
        f'<div><h2>Limits of this check</h2><ul class="limits">{limits}</ul></div>'
        if limits
        else ""
    )
    return (
        f'<!-- section: findings --><section class="card findings{"" if side else " single"}">'
        f"<div><h2>What you can say</h2>{said}</div>{side}</section>"
    )


def checks(inp: Inputs, rows: list[dict]) -> str:
    """The non-statistical checks, one line each."""

    def li(kind: str, txt: str) -> str:
        sym = {"ok": "✓", "bad": "!", "meh": "?"}[kind]
        return f'<li><span class="{kind}">{sym}</span><span>{txt}</span></li>'

    n_art = sum(1 for h in inp.arts["hits"] if inp.is_leftover(h))
    n_hidden = len(inp.arts.get("hidden", []))
    bad = inp.bad_refs()
    n_ok = sum(1 for r in inp.refs if r["status"] == "ok")
    n_unsure = len(inp.refs) - n_ok - sum(1 for r in inp.refs if r["status"] in BAD_REF)
    if bad:
        refs_line = li(
            "bad", f"References: <b>{len(bad)} of {len(inp.refs)} not found</b>"
        )
    elif not inp.refs:
        refs_line = li("ok", "No reference list")
    elif n_unsure:
        refs_line = li(
            "meh",
            f"References: {len(inp.refs) - n_unsure} of {len(inp.refs)} found; "
            f"{n_unsure} with details that differ or not checkable",
        )
    else:
        refs_line = li("ok", f"All {len(inp.refs)} references are real")
    n_style = sum(1 for r in rows if r["style_flag"])
    n_read = len(inp.jud.get("reading", []))
    hidden_line = (
        li("bad", f"Hidden text: <b>{plural(n_hidden, 'passage')}</b>")
        if n_hidden
        else ""
    )
    return "".join(
        [
            li("bad", f"Leftover chatbot text: <b>{n_art} found</b>")
            if n_art
            else li("ok", "No leftover chatbot text"),
            hidden_line,
            refs_line,
            li("meh", f"Style: AI-like in {n_style} of {len(rows)} passages")
            if n_style
            else li("ok", "Style within the human range"),
            li("meh", f"Close reading: {plural(n_read, 'note')}")
            if n_read
            else li("ok", "Close reading: nothing to note"),
        ]
    )


def side_panel(inp: Inputs, rows: list[dict]) -> str:
    """Passages with their combined value; detectors with their per-passage scores."""
    comb = inp.combined
    colour = {"c-strong": "var(--ai)", "c-ai": "var(--some)", "c-human": "var(--hu)"}
    prow = []
    for r in rows:
        if comb:
            ev = comb.get(r["id"])
            cls = times_class(ev)
            width = 0 if ev is None else max(0, min(100, 50 + 50 * ev / math.log(30)))
            lab = times_text(ev)
        else:
            n = len(r["sc"])
            cls = "c-ai" if n and r["n_ai"] / n > 0.5 else "c-mid"
            width = 100 * r["n_ai"] / n if n else 0
            lab = f"{r['n_ai']}/{n}" if n else "—"
        prow.append(
            f'<a class="prow" href="#p{r["n"]}"><span class="tag {cls}">{r["id"]}</span>'
            f'<span class="nm">{e(r["label"])} <small>{r["n_words"]}w</small>'
            f'<div class="mini"><span style="width:{width:.0f}%;background:{colour.get(cls, "var(--muted)")}"></span></div></span>'
            f'<span class="tag {cls}">{e(lab)}</span></a>'
        )
    head = "".join(f"<th>{r['id']}</th>" for r in rows)
    drows = []
    for t in inp.tools:
        w = inp.evd.get("tools", {}).get(t) or {}
        c = w.get("cal") or {}
        cells = "".join(
            f'<td class="na" title="{e(inp.name(t))}, passage {r["n"]}: not scanned">–</td>'
            if r["sc"].get(t) is None
            else f'<td class="{"ai" if r["sc"][t] >= 0.5 else "hu"}" '
            f'title="{e(inp.name(t))}, passage {r["n"]}: {pc(r["sc"][t])} AI">{round(100 * r["sc"][t])}</td>'
            for r in rows
        )
        record = (
            f"Known texts: {round((c.get('fpr') or 0) * c.get('n_human', 0))}/{c.get('n_human')} human flagged, "
            f"{round((c.get('tpr') or 0) * c.get('n_ai', 0))}/{c.get('n_ai')} AI caught"
            if c
            else "Not yet tested on known texts"
        )
        badge = (
            ' <span class="sub">independently validated</span>'
            if inp.reg.get(t, {}).get("weight") == "validated"
            else ""
        ) + ("" if w.get("used") else ' <span class="sub">shown, not counted</span>')
        drows.append(
            f'<tr class="who"><th colspan="{len(rows)}">{e(inp.name(t))}{badge}'
            f'<div class="sub">{e(record)}</div></th></tr><tr class="scores">{cells}</tr>'
        )
    if not inp.tools and not comb:
        return ""
    title = "Passages, detectors combined" if comb else "Passages, detectors saying AI"
    return (
        '<aside class="side"><!-- section: glance -->'
        f'<div class="card"><h3>{title}</h3>{"".join(prow)}</div>'
        + (
            '<div class="card"><h3>Each detector, AI score per passage (%)</h3>'
            f'<div class="scroll"><table class="dgrid"><thead><tr>{head}</tr></thead>'
            f"<tbody>{''.join(drows)}</tbody></table></div></div>"
            if drows
            else ""
        )
        + "</aside>"
    )


def other_evidence(inp: Inputs, placed: set[int]) -> str:
    """A fold, for the findings card, with the items to quote from: leftover chatbot text (also boxed in the text),
    hidden text, references not found, notes whose quote was not located, grade's extras."""
    items = [
        f"<li><b>{'Leftover chatbot text' if inp.is_leftover(h) else 'Marker'} ({e(h['tier'])}, "
        f"{e(h['category'])})</b>: “{e(h['match'])}” in "
        f"{e(h.get('section') or h['in'])}. {e(h['shows'])}</li>"
        for h in inp.arts["hits"]
        if inp.confirmed(h)
    ]
    items += [
        f"<li><b>Hidden text</b> ({e(h['why'])}): “{e(h['text'][:200])}”</li>"
        for h in inp.arts.get("hidden", [])
    ]
    for r in inp.bad_refs():
        links = " ".join(
            f'<a href="{e(u)}">lookup</a>' for u in r.get("queried", [])[:2]
        )
        items.append(
            f"<li><b>Reference {r['n']}: {e(BAD_REF[r['status']])}</b>. {e(r['raw'][:200])} {links}</li>"
        )
    items += [
        f"<li><b>Close reading ({e(x.get('tier'))})</b>: {e(x['claim'])} "
        f"<i>“{e(x.get('quote', ''))}”</i> ({e(x.get('where', ''))})</li>"
        for i, x in enumerate(inp.jud.get("reading", []))
        if i not in placed
    ]
    return (
        f'<li class="more"><details><summary>Evidence items ({len(items)})</summary>'
        f'<ul class="limits">{"".join(items)}</ul></details></li>'
        if items
        else ""
    )


# ---------------------------------------------------------------- the page


def render(work: Path, case: str, kind: str, context: str) -> str:
    """The report fragment: <title>, fonts, <style>, then the page."""
    inp = load(work)
    rows = passage_rows(inp)
    tr = TextRenderer(inp)
    text_html = tr.document(rows)  # first: it records which notes found their place
    side = side_panel(inp, rows)
    meta = [kind.replace("-", " ").capitalize()]
    if context != "other":
        meta.append(CONTEXT.get(context, context))
    meta += [f"{inp.doc.get('n_words')} words", plural(len(rows), "passage")]
    if (inp.doc.get("metadata") or {}).get("tracked_changes_removed"):
        meta.append("tested the author's original text (tracked changes set aside)")
    return (
        f'<title>{e(case[:60])}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        f'<link rel="stylesheet" href="{FONTS}">\n'
        f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>\n"
        '<div class="wrap"><header>'
        f'<h1>{e(case)}</h1><p class="meta">{e(" · ".join(meta))}</p></header>'
        f"<!-- section: answer -->{headline(inp, rows)}"
        f'<div class="cols{"" if side else " single"}"><article class="card doc" id="text">'
        f"<!-- section: text -->{text_html}</article>{side}</div>"
        f"{findings(inp, tr.notes_placed)}</div>"
    )
