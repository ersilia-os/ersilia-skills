"""Render the evidence report as one self-contained HTML fragment (build_report.py).

The layout follows the web detectors people already know:

    Headline     share of the checked prose that reads as AI-written (ring and breakdown
                 bar), the verdict tier and headline from grade.json, the most AI-like
                 passages, and the non-statistical checks (leftover chatbot text,
                 references, style, close reading)
    Text         the document, passage by passage; sentences shaded by the combined,
                 calibrated evidence (evidence.py), human-leaning text left plain;
                 leftover chatbot text boxed in red; close-reading notes as tags beside
                 the words they quote; title page, captions and tables folded or greyed
    Side panel   each passage's combined score, then each detector's score per passage
                 and its record on known texts
    Other        the findings to quote from: leftover chatbot text, hidden text,
                 references not found, notes whose quote could not be placed

A passage is whole prose paragraphs from one section, ~250-500 words
(web_detectors.build_passages): the unit the reader sees. The scores themselves come from
every split (segments.py) through evidence.py.

Styles live in ``assets/report.css``.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from _common import REFS, SKILL_DIR, read_json, words
from stylometry import features, style_score
from web_detectors import build_passages, is_ai_colour, is_prose

CSS_FILE = SKILL_DIR / "assets" / "report.css"
FONTS = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800"
    "&family=Source+Serif+4:wght@400;600&display=swap"
)
LN3, LN10 = math.log(3), math.log(10)
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
    """Log evidence -> '5.3× AI' or '1.5× human'."""
    if ev is None:
        return "—"
    x = math.exp(ev)
    return f"{x:.1f}× AI" if x >= 1 else f"{1 / x:.1f}× human"


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
    cells = [[c.strip() for c in r.split(" | ")] for r in rows]
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
        if " | " in t:  # table rows, plus one-cell group labels between rows
            rows = []
            while i < len(paras) and (
                " | " in paras[i]
                or (
                    i + 1 < len(paras)
                    and " | " in paras[i + 1]
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
            short = t[:300] + ("…" if len(t) > 300 else "")
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
    web: dict
    evd: dict
    reg: dict[str, dict]
    style_model: dict | None
    style_thr: dict
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
        web=read_json(work / "web_detectors.json") or {},
        evd=read_json(work / "evidence.json") or {},
        reg={t["id"]: t for t in wreg.get("tools", [])},
        style_model=cal.get("model"),
        style_thr=cal.get("thresholds") or {},
    )
    order = wreg.get("default_order", [])
    ran = (
        {r["tool"] for r in inp.web.get("results", [])}
        | set(inp.web.get("summary") or {})
        | set(inp.evd.get("used") or [])
    )
    inp.tools = sorted(
        ran,
        key=lambda t: (
            inp.reg.get(t, {}).get("weight") != "validated",
            order.index(t) if t in order else 99,
        ),
    )
    return inp


def passage_rows(inp: Inputs) -> list[dict]:
    """The passages in reading order, with each detector's score and the style score."""
    passages = inp.web.get("chunks") or [
        {"chunk": k, **p} for k, p in enumerate(build_passages(inp.doc), 1)
    ]
    scores: dict[int, dict[str, float]] = {}
    for r in inp.web.get("results", []):  # the latest result per tool and passage wins
        scores.setdefault(r["chunk"], {})[r["tool"]] = r["score"]
    rows = []
    for p in passages:
        body = "\n\n".join(
            inp.text[a:b] for a, b in p.get("paras", [[p["start"], p["end"]]])
        )
        st = style_score(features(body), inp.style_model) if inp.style_model else None
        flagged = bool(st is not None and inp.style_thr and st >= inp.style_thr["5%"])
        sc = scores.get(p["chunk"], {})
        rows.append(
            {
                **p,
                "id": f"P{p['chunk']}",
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

    def __init__(self, inp: Inputs, rows: list[dict]) -> None:
        self.inp, self.text, self.heat = inp, inp.text, inp.heat
        self.events = self._site_marks(rows) + self._artefacts() + self._notes()
        self.notes_placed: set[int] = set()

    def _locate(self, chunk_text: str, a0: int, b0: int) -> tuple[int, int] | None:
        pat = r"\s+".join(re.escape(tok) for tok in chunk_text.split())
        m = re.search(pat, self.text[a0:b0]) if pat else None
        return (a0 + m.start(), a0 + m.end()) if m else None

    def _site_marks(self, rows: list[dict]) -> list[tuple]:
        """Sentences the sites highlighted as AI, from every split, merged across tools."""
        span_of = {r["chunk"]: (r["start"], r["end"]) for r in rows}
        found: list[tuple[str, tuple[int, int], str]] = [
            (h["tool"], span_of.get(h["chunk"], (0, len(self.text))), h["text"])
            for h in self.inp.web.get("highlights", [])
        ]
        plan = read_json(self.inp.work / "multi" / "plan.json") or {"units": []}
        for u in plan["units"]:
            if u["scale"] == "P":
                continue
            for f in (self.inp.work / "plan").glob(
                f"*_chunk{u['chunk']}_highlights.json"
            ):
                for h in read_json(f) or []:
                    if is_ai_colour(h.get("bg", "")):
                        found.append(
                            (
                                f.name.split("_chunk")[0],
                                (u["start"], u["end"]),
                                h["text"],
                            )
                        )
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
            if h["in"] == "body" and self.inp.confirmed(h)
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
                    f'<span class="noted">{seg}</span>'
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
        text, starts = (
            self.text,
            {a for a, _ in r.get("paras", [[r["start"], r["end"]]])},
        )
        parts, pos, held = [], r["start"], None
        for m in [*re.finditer(r"\n\s*\n", text[r["start"] : r["end"]]), None]:
            end = r["start"] + m.start() if m else r["end"]
            raw = text[pos:end]
            a0 = pos + (len(raw) - len(raw.lstrip()))
            if raw.strip():
                if a0 in starts:
                    if held is not None:
                        parts.append(unchecked_html(text, held, a0))
                        held = None
                    parts.append(f"<p>{self.paragraph(a0, end)}</p>")
                elif held is None:
                    held = a0
            pos = r["start"] + m.end() if m else r["end"]
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
        return (
            f'<section class="psg" id="p{r["chunk"]}"><div class="phead">'
            f'<span class="tag {times_class(ev)}">{e(tag)}</span>'
            f"<span>Passage {r['chunk']} · {e(r['label'])} · {r['n_words']} words</span>{info}</div>"
            f"{''.join(parts)}</section>"
        )

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
            '<span class="sw h1">leans AI</span><span>plain = no signal, or human</span>'
            if self.heat
            else '<span class="sw m1">one detector says AI</span><span class="sw m2">two or more</span>'
            if self.inp.tools
            else ""
        )
        legend += (
            '<mark class="art">red box</mark><span>= leftover chatbot text</span>'
            '<span class="note">note</span><span>= close-reading note</span>'
            '<span class="hover-only">Hover or tap a note to read it'
            + ("; hover a sentence for each site's verdict." if self.heat else ".")
            + "</span>"
        )
        return f'<div class="doclegend">{legend}</div>' + "".join(blocks)


# ---------------------------------------------------------------- headline and panel


def headline(inp: Inputs, rows: list[dict]) -> str:
    """Ring with the share of AI-like prose, verdict, breakdown bar, checks."""
    heat = inp.heat
    tw = sum(x["n_words"] for x in heat)
    scanned = [r for r in rows if r["sc"]]
    if tw:
        ai = sum(x["n_words"] for x in heat if x["evidence"] >= LN3) / tw
        hu = sum(x["n_words"] for x in heat if x["evidence"] <= -LN3) / tw
        note = "of the checked prose is at least 3× more likely AI-written than human, combining the calibrated detectors"
    elif scanned:
        pw = sum(r["n_words"] for r in scanned)
        ai = sum(r["n_words"] for r in scanned if r["n_ai"] / len(r["sc"]) > 0.5) / pw
        hu = sum(r["n_words"] for r in scanned if r["n_ai"] == 0) / pw
        note = (
            "of the checked prose is called AI by most detectors (not yet calibrated)"
        )
    else:
        ai = hu = None
        note = "no detector was run (confidential text, or not run this time)"
    if ai is None:
        ring = '<div class="ring" style="background: var(--un)"><div><div class="big">—</div></div></div>'
        bar = ""
    else:
        un = max(0.0, 1 - ai - hu)
        col = (
            "var(--ai)"
            if ai >= 0.5
            else ("var(--amber)" if ai >= 0.15 else "var(--hu)")
        )
        ring = (
            f'<div class="ring" style="background: conic-gradient({col} {round(360 * ai)}deg, var(--un) 0)">'
            f'<div><div class="big">{round(100 * ai)}<small>%</small></div></div></div>'
        )
        bar = (
            f'<div class="bar"><span class="b-ai" style="width:{100 * ai:.1f}%"></span>'
            f'<span class="b-un" style="width:{100 * un:.1f}%"></span><span class="b-hu" style="width:{100 * hu:.1f}%"></span></div>'
            f'<div class="legend"><span><i class="dot b-ai"></i>Likely AI {pc(ai)}</span>'
            f'<span><i class="dot b-un"></i>Unclear {pc(un)}</span><span><i class="dot b-hu"></i>Likely human {pc(hu)}</span></div>'
        )
    hot = sorted(
        ((pid, ev) for pid, ev in inp.combined.items() if ev >= LN3),
        key=lambda x: -x[1],
    )
    label = {r["id"]: r["label"] for r in rows}
    where = (
        '<p class="where">Most AI-like: '
        + ", ".join(
            f'<a href="#p{pid[1:]}">{e(label.get(pid, pid))}</a> ({math.exp(ev):.0f}×)'
            for pid, ev in hot[:3]
        )
        + "</p>"
        if hot
        else ""
    )
    dt = (inp.evd.get("document") or {}).get("times")
    whole = (
        ""
        if dt is None
        else f'<p class="where">Whole text: about <b>{dt:.1f}×</b> as likely AI-written as human '
        f"({len(inp.evd.get('used', []))} calibrated detectors).</p>"
        if dt >= 1
        else f'<p class="where">Whole text: about <b>{1 / dt:.1f}×</b> as likely human-written.</p>'
    )
    tier = inp.grade.get("tier", "none")
    return (
        '<section class="card hero" id="verdict">'
        f'<div class="gauge">{ring}<div class="cap">{e(note)}</div></div>'
        f'<div><span class="pill t-{e(tier)}">{e(TIER_WORD.get(tier, tier))}</span>'
        f'<p class="headline">{e(inp.grade.get("headline", ""))}</p>{bar}{where}{whole}</div>'
        f'<ul class="checks">{checks(inp, rows)}</ul></section>'
    )


def checks(inp: Inputs, rows: list[dict]) -> str:
    """The non-statistical checks, one line each."""

    def li(kind: str, txt: str) -> str:
        sym = {"ok": "✓", "bad": "!", "meh": "?"}[kind]
        return f'<li><span class="{kind}">{sym}</span><span>{txt}</span></li>'

    n_art = sum(1 for h in inp.arts["hits"] if inp.confirmed(h)) + len(
        inp.arts.get("hidden", [])
    )
    bad = [r for r in inp.refs if r["status"] in BAD_REF]
    n_style = sum(1 for r in rows if r["style_flag"])
    n_read = len(inp.jud.get("reading", []))
    return "".join(
        [
            li("bad", f"Leftover chatbot text: <b>{n_art} found</b>")
            if n_art
            else li("ok", "No leftover chatbot text"),
            li("bad", f"References: <b>{len(bad)} of {len(inp.refs)} not found</b>")
            if bad
            else li(
                "ok",
                f"All {len(inp.refs)} references are real"
                if inp.refs
                else "No reference list",
            ),
            li("meh", f"Style: AI-like in {n_style} of {len(rows)} passages")
            if n_style
            else li("ok", "Style within the human range"),
            li("meh", f"Close reading: {n_read} note(s)")
            if n_read
            else li("ok", "Close reading: nothing to note"),
        ]
    )


def side_panel(inp: Inputs, rows: list[dict]) -> str:
    """Passages with their combined value; detectors with their per-passage scores."""
    comb = inp.combined
    colour = {"c-strong": "var(--ai)", "c-ai": "var(--amber)", "c-human": "var(--hu)"}
    prow = []
    for r in rows:
        if comb:
            ev = comb.get(r["id"])
            cls = times_class(ev)
            width = 0 if ev is None else max(0, min(100, 50 + 50 * ev / math.log(30)))
            lab = times_text(ev).replace(" AI", "")
        else:
            n = len(r["sc"])
            cls = "c-ai" if n and r["n_ai"] / n > 0.5 else "c-mid"
            width = 100 * r["n_ai"] / n if n else 0
            lab = f"{r['n_ai']}/{n}" if n else "—"
        prow.append(
            f'<a class="prow" href="#p{r["chunk"]}"><span class="tag {cls}">{r["id"]}</span>'
            f'<span class="nm">{e(r["label"])} <small>{r["n_words"]}w</small>'
            f'<div class="mini"><span style="width:{width:.0f}%;background:{colour.get(cls, "var(--muted)")}"></span></div></span>'
            f'<span class="tag {cls}">{e(lab)}</span></a>'
        )
    drows = []
    for t in inp.tools:
        w = inp.evd.get("tools", {}).get(t) or {}
        c = w.get("cal") or {}
        chips = "".join(
            f'<span class="chip {"na" if r["sc"].get(t) is None else ("ai" if r["sc"][t] >= 0.5 else "hu")}" '
            f'title="passage {r["chunk"]}">{"–" if r["sc"].get(t) is None else pc(r["sc"][t])}</span>'
            for r in rows
        )
        record = (
            f"on known texts: {round((c.get('fpr') or 0) * c.get('n_human', 0))}/{c.get('n_human')} false alarms, "
            f"caught {round((c.get('tpr') or 0) * c.get('n_ai', 0))}/{c.get('n_ai')} AI"
            if c
            else "not yet tested on known texts"
        )
        drows.append(
            f'<div class="drow"><b>{e(inp.name(t))}</b>'
            f"{' ✓' if inp.reg.get(t, {}).get('weight') == 'validated' else ''}"
            f"{'' if w.get('used') else ' <span class=sub>(shown, not counted)</span>'}"
            f'<div class="sub">{e(record)}</div><div class="chips">{chips}</div></div>'
        )
    if not inp.tools and not comb:
        return ""
    title = (
        "Passages · combined, calibrated" if comb else "Passages · detectors saying AI"
    )
    return (
        '<aside class="side"><!-- section: glance -->'
        f'<div class="card"><h3>{title}</h3>{"".join(prow)}</div>'
        + (
            f'<div class="card"><h3>Detectors · score per passage</h3>{"".join(drows)}</div>'
            if drows
            else ""
        )
        + "</aside>"
    )


def other_evidence(inp: Inputs, placed: set[int]) -> str:
    """The list of findings to quote from: leftover chatbot text (also boxed in the text),
    hidden text, references not found, notes whose quote was not located, grade's extras."""
    items = [
        f"<li><b>Leftover text ({e(h['tier'])})</b>: “{e(h['match'])}” in "
        f"{e(h.get('section') or h['in'])}. {e(h['shows'])}</li>"
        for h in inp.arts["hits"]
        if inp.confirmed(h)
    ]
    items += [
        f"<li><b>Hidden text</b> ({e(h['why'])}): “{e(h['text'][:200])}”</li>"
        for h in inp.arts.get("hidden", [])
    ]
    for r in (r for r in inp.refs if r["status"] in BAD_REF):
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
    items += [
        f"<li><b>{e(s['kind'])}</b>: {e(s['text'])}</li>"
        for s in inp.grade.get("separate", [])
    ]
    return (
        f'<h2>Other evidence</h2><div class="card"><ul>{"".join(items)}</ul></div>'
        if items
        else ""
    )


# ---------------------------------------------------------------- the page


def render(work: Path, case: str, kind: str, context: str) -> str:
    """The report fragment: <title>, fonts, <style>, then the page."""
    inp = load(work)
    rows = passage_rows(inp)
    tr = TextRenderer(inp, rows)
    text_html = tr.document(rows)  # first: it records which notes found their place
    side = side_panel(inp, rows)
    tested = (
        "the author's original text (tracked changes set aside)"
        if (inp.doc.get("metadata") or {}).get("tracked_changes_removed")
        else "the text as it stands"
    )
    return (
        f'<title>{e(case[:60])}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        f'<link rel="stylesheet" href="{FONTS}">\n'
        f"<style>{CSS_FILE.read_text(encoding='utf-8')}</style>\n"
        '<div class="wrap">'
        f'<h1>{e(case)}</h1><p class="meta">{e(kind.replace("-", " ").capitalize())} · '
        f"{e(CONTEXT.get(context, context))} · {e(inp.doc.get('n_words'))} words · tested {e(tested)} · "
        f"{len(rows)} passage{'s' if len(rows) != 1 else ''}</p>"
        f"<!-- section: answer -->{headline(inp, rows)}"
        f'<div class="cols{"" if side else " single"}"><article class="card doc" id="text">'
        f"<!-- section: text -->{text_html}</article>{side}</div>"
        f"{other_evidence(inp, tr.notes_placed)}</div>"
    )
