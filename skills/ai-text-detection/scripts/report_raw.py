"""The raw, text-first report: scores first, then the document with only its AI-looking
parts highlighted. Plain HTML on purpose: a few colours, no theme, no scripts.

Called by build_report.py (``--style raw``, the default).
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from _common import REFS, read_json
from stylometry import DIRECTION

WORD_SHADE = {"1%": "w1", "5%": "w5", "0": "w0"}
PRIORITY = {"art": 3, "phrase": 2, "word": 1}

CSS = """
:root { color-scheme: light; }
body { background: #fff; color: #111; }
main { max-width: 52em; margin: 0 auto; padding-block: 12px 40px;
       padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
table { border-collapse: collapse; font-size: 13px; }
th, td { border: 1px solid #aaa; padding: 2px 6px; text-align: left; vertical-align: top; }
.scroll { overflow-x: auto; }
.w0 { background: #fffbe6; }
.w5 { background: #fff4c2; }
.w1 { background: #ffd2bd; }
mark.word { background: #ffe066; }
mark.phrase { background: #cfe5ff; }
mark.art { background: #ff9b9b; }
.lab { font: 12px monospace; color: #444; }
.ok { background: #e4f4e1; }
.bad { background: #ff9b9b; }
.text p { margin: 0 0 .8em; }
.ws { background: #ffcf9e; border-bottom: 2px solid #e8833a; }
.ws1 { background: #ffb98a; border-bottom: 2px solid #c8501a; }
"""


def e(x: object) -> str:
    """HTML-escape."""
    return html.escape("" if x is None else str(x))


def pct(x: float | None) -> str:
    """0.0123 -> '1.2%'."""
    return "n/a" if x is None else f"{100 * x:.1f}%"


def num(x: float | None, d: int = 2) -> str:
    """Rounded number or 'n/a'."""
    return "n/a" if x is None else f"{x:.{d}f}"


def web_cell(v: float | None, weight: str = "context") -> str:
    """A passages-table cell for one web detector's score on this window's chunk.

    A flag from a validated tool is coloured like 'past 1%'; from a context-only tool,
    never stronger than 'past 5%'."""
    cls = (
        ""
        if v is None
        else (("w1" if weight == "validated" else "w5") if v >= 0.5 else "ok")
    )
    return f'<td class="{cls}">{num(v)}</td>'


def _inline(text: str, a: int, b: int, spans: list[dict]) -> str:
    """HTML for text[a:b] with non-overlapping <mark>s (no paragraph handling)."""
    inside = sorted(
        (s for s in spans if s["start"] >= a and s["end"] <= b),
        key=lambda s: (s["start"], -PRIORITY[s["kind"]]),
    )
    chosen, last_end = [], a
    for s in inside:
        if s["start"] < last_end:
            if (
                chosen
                and PRIORITY[s["kind"]] > PRIORITY[chosen[-1]["kind"]]
                and s["start"] < chosen[-1]["end"]
            ):
                chosen[-1] = s
                last_end = s["end"]
            continue
        chosen.append(s)
        last_end = s["end"]
    out, pos = [], a
    for s in chosen:
        out.append(e(text[pos : s["start"]]))
        ref = f"<sup>[{s['ref']}]</sup>" if s.get("ref") else ""
        out.append(
            f'<mark class="{s["kind"]}" title="{e(s["label"])}">{e(text[s["start"] : s["end"]])}</mark>{ref}'
        )
        pos = s["end"]
    out.append(e(text[pos:b]))
    return "".join(out).replace("\n", "<br>")


def render_segment(
    text: str, a: int, b: int, spans: list[dict], sentences: list[dict] | None = None
) -> str:
    """HTML for text[a:b]: paragraphs, sentences flagged by web detectors (shaded, with
    the tools named on hover), and word/phrase/artefact marks inside them."""
    sentences = sorted(
        (x for x in (sentences or []) if x["start"] < b and x["end"] > a),
        key=lambda x: x["start"],
    )
    html_paras = []
    pa = a
    for m in [*re.finditer(r"\n\s*\n", text[a:b]), None]:
        pb = a + m.start() if m else b
        pieces, pos = [], pa
        for sn in sentences:
            s0, s1 = max(sn["start"], pa), min(sn["end"], pb)
            if s1 <= s0 or s0 < pos:
                continue
            pieces.append(_inline(text, pos, s0, spans))
            cls = "ws1" if sn.get("strong") else "ws"
            pieces.append(
                f'<span class="{cls}" title="{e(sn["label"])}">{_inline(text, s0, s1, spans)}</span>'
            )
            pos = s1
        pieces.append(_inline(text, pos, pb, spans))
        body = "".join(pieces).strip()
        if body:
            html_paras.append(f"<p>{body}</p>")
        if m:
            pa = a + m.end()
    return "".join(html_paras)


def build_raw(work: Path, case: str, kind: str, context: str) -> str:
    """The raw report fragment."""
    doc = read_json(work / "text.json") or {}
    text = doc.get("text", "")
    g = read_json(work / "grade.json") or {}
    arts = read_json(work / "artifacts.json") or {"hits": [], "hidden": []}
    refs = read_json(work / "references.json") or {"references": [], "counts": {}}
    sty = read_json(work / "stylometry.json") or {}
    jud = read_json(work / "judgements.json") or {}
    cal = read_json(REFS / "calibration.json") or {}
    ja = jud.get("artifacts", {})
    scal = cal.get("stylometry") or {}
    sthr = scal.get("thresholds") or {}
    ss = sty.get("summary") or {}
    swin = sty.get("windows") or []
    web = read_json(work / "web_detectors.json") or {}
    wsum = web.get("summary") or {}
    wreg = {
        t["id"]: t
        for t in (read_json(REFS / "web_detectors.json") or {}).get("tools", [])
    }
    chunk_of = {
        w_id: str(c["chunk"]) for c in web.get("chunks", []) for w_id in c["windows"]
    }

    # Per-window flag: the style score's threshold, raised to "1%"-strength shading when a
    # validated web detector flags the chunk the window belongs to.
    for w in swin:
        sc = w.get("style_score")
        w["flag"] = (
            None
            if sc is None or not sthr
            else ("1%" if sc >= sthr["1%"] else ("5%" if sc >= sthr["5%"] else None))
        )
        w["web_hits"] = [
            ws["name"]
            for ws in wsum.values()
            if ws["weight"] == "validated"
            and (ws["by_chunk"].get(chunk_of.get(w["id"], "")) or 0) >= 0.5
        ]
        w["web_any"] = [
            ws["name"]
            for ws in wsum.values()
            if (ws["by_chunk"].get(chunk_of.get(w["id"], "")) or 0) >= 0.5
        ]
        # Shade: strongest when the style score is past 1% or a validated tool flags it;
        # then when the style score is past 5% or two or more tools agree; lightest when a
        # single unvalidated tool flags it.
        if w["flag"] == "1%" or w["web_hits"]:
            w["shade"] = "1%"
        elif w["flag"] == "5%" or len(w["web_any"]) >= 2:
            w["shade"] = "5%"
        elif w["web_any"]:
            w["shade"] = "0"
        else:
            w["shade"] = None

    # Sentences the web detectors marked as AI, located in the document text.
    weight_of = {k: v["weight"] for k, v in wsum.items()}
    name_of = {k: v["name"] for k, v in wsum.items()}
    span_of = {c["chunk"]: (c["start"], c["end"]) for c in web.get("chunks", [])}
    merged: dict[tuple[int, int], set[str]] = {}
    for h in web.get("highlights", []):
        a0, b0 = span_of.get(h["chunk"], (0, len(text)))
        pat = r"\s+".join(re.escape(tok) for tok in h["text"].split())
        m = re.search(pat, text[a0:b0]) if pat else None
        if m:
            merged.setdefault((a0 + m.start(), a0 + m.end()), set()).add(h["tool"])
    web_sentences = [
        {
            "start": k[0],
            "end": k[1],
            "label": "marked as AI by "
            + ", ".join(sorted(name_of.get(t, t) for t in tools)),
            "strong": len(tools) >= 2
            or any(weight_of.get(t) == "validated" for t in tools),
        }
        for k, tools in sorted(merged.items())
    ]

    # Findings list (numbered) and the artefact spans that point to it.
    findings, spans = [], []
    for h in arts["hits"]:
        if not ja.get(h["id"], {}).get("confirmed", True):
            continue
        findings.append(
            f"<b>{e(h['tier'])}</b> {e(h['marker'])}: “{e(h['match'])}” ({e(h.get('section') or h['in'])}). {e(h['shows'])}"
        )
        if h["in"] == "body":
            spans.append(
                {
                    "start": h["offset"],
                    "end": h["offset"] + len(h["match"]),
                    "kind": "art",
                    "label": f"{h['marker']} ({h['tier']})",
                    "ref": len(findings),
                }
            )
    for h in arts.get("hidden", []):
        findings.append(
            f"<b>hidden text</b> ({e(h['why'])}, p. {e(h.get('page'))}): “{e(h['text'][:300])}”"
        )
    bad = [
        r
        for r in refs.get("references", [])
        if r["status"] not in ("ok", "unverifiable")
    ]
    for r in bad:
        links = " ".join(
            f'<a href="{e(u)}">lookup</a>' for u in r.get("queried", [])[:3]
        )
        findings.append(
            f"<b>reference {r['n']}: {e(r['status'])}</b>. {e(r['raw'][:220])} {e('; '.join(r.get('issues', [])))} {links}"
        )
    for r in jud.get("reading", []):
        findings.append(
            f"<b>reading ({e(r.get('tier'))})</b>: {e(r['claim'])} “{e(r.get('quote', ''))}” ({e(r.get('where', ''))})"
        )
    spans += sty.get("spans") or []

    # Scores table.
    d = ss.get("document") or {}
    mp = ss.get("median_percentiles") or {}
    wo = ss.get("windows_over") or {}
    nw = ss.get("n_windows", 0)
    held = scal.get("heldout") or {}

    def row(name: str, value: str, ref: str, cls: str = "") -> str:
        c = f' class="{cls}"' if cls else ""
        return f"<tr><td>{e(name)}</td><td{c}>{value}</td><td>{ref}</td></tr>"

    def p_(k: str) -> str:
        return f" (human percentile {mp[k]:.0f})" if mp.get(k) is not None else ""

    def p_cls(k: str) -> str:
        """Colour by how unusual the median percentile is, in the AI-like direction."""
        v = mp.get(k)
        if v is None:
            return ""
        v = v if DIRECTION.get(k, 1) > 0 else 100 - v
        return "w1" if v >= 99 else ("w5" if v >= 95 else "ok")

    def flag_cls(flag: str | None) -> str:
        return {"1%": "w1", "5%": "w5"}.get(flag or "", "ok")

    tier_cls = {"conclusive": "bad", "strong": "w1", "moderate": "w5"}.get(
        g.get("tier"), "ok"
    )
    n1, n5 = wo.get("1%", {}).get("count", 0), wo.get("5%", {}).get("count", 0)
    style_cls = "w1" if n1 else ("w5" if n5 else "ok")
    n_bad_refs = sum(
        v
        for k, v in (refs.get("counts") or {}).items()
        if k not in ("ok", "unverifiable")
    )
    n_arts = sum(
        1 for h in arts["hits"] if ja.get(h["id"], {}).get("confirmed", True)
    ) + len(arts.get("hidden", []))

    rows = [
        row(
            "Verdict",
            f"<b>{e(g.get('tier', 'n/a'))}</b>",
            e(g.get("headline", "")),
            tier_cls,
        ),
        row(
            "Style score, median over windows",
            f"{num(ss.get('style_score_median'))}; past 1%: {wo.get('1%', {}).get('count', 0)}/{nw}; past 5%: {wo.get('5%', {}).get('count', 0)}/{nw}",
            f"thresholds {num(sthr.get('1%'))} (1%) / {num(sthr.get('5%'))} (5%); held-out human windows flagged: "
            f"{pct((held.get('human (held out)') or {}).get('past_1pct'))} / {pct((held.get('human (held out)') or {}).get('past_5pct'))}; "
            f"AI windows flagged: {pct((held.get('AI (held out)') or {}).get('past_1pct'))} / {pct((held.get('AI (held out)') or {}).get('past_5pct'))}; AUROC {num(scal.get('auroc'))}",
            style_cls,
        ),
    ]
    rows += [
        row(
            "Excess vocabulary per 1,000 words",
            f"{num(d.get('excess_rate'), 1)}{p_('excess_rate')}",
            "Kobak et al. 2025 word list",
            p_cls("excess_rate"),
        ),
        row(
            "AI-typical words per 1,000 words",
            f"{num(d.get('marked_rate'), 1)}{p_('marked_rate')}: {e(', '.join(ss.get('marked_words', [])) or 'none')}",
            "delve, underscore, meticulous, …",
            p_cls("marked_rate"),
        ),
        row(
            "Stock phrasing per 1,000 words",
            f"{num(d.get('tells_rate'), 1)}{p_('tells_rate')}: {e(', '.join(f'{k} {v}' for k, v in (ss.get('tells') or {}).items()) or 'none')}",
            "Wikipedia 'Signs of AI writing', humanizer, stop-slop",
            p_cls("tells_rate"),
        ),
        row(
            "Em dashes per 1,000 words",
            f"{num(d.get('em_dash_rate'), 1)}{p_('em_dash_rate')}",
            "",
            p_cls("em_dash_rate"),
        ),
        row(
            "Sentence-length variation (CV)",
            f"{num(d.get('sent_cv'))}{p_('sent_cv')}",
            "lower = more uniform",
            p_cls("sent_cv"),
        ),
        row(
            "References",
            e(
                ", ".join(
                    f"{v} {k}" for k, v in sorted((refs.get("counts") or {}).items())
                )
                or "none found"
            ),
            "Crossref, DataCite, doi.org, OpenAlex, Semantic Scholar",
            ("w1" if n_bad_refs >= 2 else "w5")
            if n_bad_refs
            else ("ok" if refs.get("references") else ""),
        ),
        row(
            "Artefacts (leftover chatbot text, tokens, hidden text)",
            str(
                sum(
                    1
                    for h in arts["hits"]
                    if ja.get(h["id"], {}).get("confirmed", True)
                )
                + len(arts.get("hidden", []))
            ),
            "conclusive when confirmed in context",
            "bad" if n_arts else "ok",
        ),
        row(
            "Close-reading findings",
            str(len(jud.get("reading", []))),
            "listed below",
            "w1"
            if any(
                r.get("tier") in ("strong", "conclusive")
                for r in jud.get("reading", [])
            )
            else (
                "w5"
                if any(r.get("tier") == "moderate" for r in jud.get("reading", []))
                else ""
            ),
        ),
    ]

    # Web detectors: one row per tool, then the consensus, right after the style score.
    web_rows = []
    for tid, ws in wsum.items():
        share = ws["share_words_flagged"]
        cls = ("w1" if share >= 0.5 else "w5") if share > 0 else "ok"
        if ws["weight"] != "validated" and cls == "w1":
            cls = "w5"  # unvalidated tools never colour stronger than 'past 5%'
        web_rows.append(
            row(
                f"{ws['name']} (web, {ws['weight']})",
                f"mean AI score {num(ws['mean_score'])}; chunks flagged {ws['chunks_flagged']}/{ws['chunks']} "
                f"({share:.0%} of words scanned; covered {ws.get('coverage', 1):.0%} of the text)",
                e(wreg.get(tid, {}).get("evidence", "")),
                cls,
            )
        )
    for sk in web.get("skipped", []):
        web_rows.append(row(f"{sk['tool']} (web)", "not run", e(sk["why"])))
    cons = web.get("consensus")
    if cons:
        web_rows.append(
            row(
                "Web detectors, consensus",
                f"{cons['flagging']} of {cons['ran']} tools flag the text ({cons['validated_flagging']} of {cons['validated_ran']} validated); "
                f"mean AI scores range {num(cons['min_mean'])}–{num(cons['max_mean'])}",
                "agreement between independent tools; validated ones weigh more",
                "w1"
                if cons["validated_flagging"] >= 2
                else ("w5" if cons["flagging"] else "ok"),
            )
        )
    if not wsum and not web.get("skipped"):
        web_rows.append(
            row("Web detectors", "not run", "confidential text, or not run this time")
        )
    rows[2:2] = web_rows

    # Per-window table.
    wrows = []
    for w in swin:
        sc = w.get("style_score")
        s_flag = (
            None
            if sc is None or not sthr
            else ("1%" if sc >= sthr["1%"] else ("5%" if sc >= sthr["5%"] else None))
        )
        rc = WORD_SHADE.get(w.get("shade"), "")
        wrows.append(
            f'<tr class="{rc}"><td><a href="#{w["id"]}">{w["id"]}</a></td><td>{e(w.get("section"))}</td><td>{w.get("n_words")}</td>'
            f'<td class="{flag_cls(s_flag)}">{num(sc)}</td>'
            + "".join(
                web_cell(ws["by_chunk"].get(chunk_of.get(w["id"], "")), ws["weight"])
                for ws in wsum.values()
            )
            + f"<td>{e(w.get('flag') or '')}</td><td>{e(', '.join(w.get('_marked_words') or []))}</td></tr>"
        )

    # The text, window by window, with gaps (headings, skipped sections) as plain text.
    parts, pos = [], 0
    for w in sorted(swin, key=lambda x: x.get("start", 0)):
        a, b = w.get("start"), w.get("end")
        if a is None:
            continue
        if a > pos:
            parts.append(render_segment(text, pos, a, spans, web_sentences))
        shade = WORD_SHADE.get(w.get("shade"), "")
        web_scores = " · ".join(
            f"{ws['name']} {num(ws['by_chunk'].get(chunk_of.get(w['id'], '')))}"
            for ws in wsum.values()
            if ws["by_chunk"].get(chunk_of.get(w["id"], "")) is not None
        )
        lab = (
            f"[{w['id']} · style {num(w.get('style_score'))}"
            + (f" · {web_scores}" if web_scores else "")
            + (f" · style past {w['flag']}" if w.get("flag") else "")
            + (f" · flagged by {', '.join(w['web_hits'])}" if w.get("web_hits") else "")
            + "]"
        )
        parts.append(
            f'<div id="{w["id"]}" class="{shade}"><span class="lab">{e(lab)}</span>{render_segment(text, a, b, spans, web_sentences)}</div>'
        )
        pos = b
    if pos < len(text):
        parts.append(render_segment(text, pos, len(text), spans, web_sentences))

    tracked = (doc.get("metadata") or {}).get("tracked_changes_removed")
    tested = (
        "author's original text (tracked changes set aside)"
        if tracked
        else "text as it stands"
    )
    ran = [
        "artefacts",
        "references" if refs.get("references") else None,
        "style",
        "web detectors" if wsum else None,
        "close reading" if jud.get("reading") else None,
    ]
    lims = "".join(f"<li>{e(c)}</li>" for c in g.get("caveats", []))
    return (
        f'<title>{e(case[:60])}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n<style>{CSS}</style>\n'
        "<!-- Single light look on purpose: a plain working document. -->\n<main>"
        f"<h1>{e(case)}</h1>"
        f"<p>{e(kind)}, {e(context)} · {e(doc.get('n_words'))} words · tested: {e(tested)} · checks: {e(', '.join(x for x in ran if x))}</p>"
        "<h2>Scores</h2>"
        f'<div class="scroll"><table><tr><th>Measure</th><th>This document</th><th>Compared with</th></tr>{"".join(rows)}</table></div>'
        '<p>Colours: <span class="ok">within the human range</span> · <span class="w5">past the 5% threshold (or above the human 95th percentile)</span> · <span class="w1">past the 1% threshold (or above the 99th)</span> · <span class="bad">artefact found</span>.</p>'
        "<p>A window is ~300 words. “Past 1%” means a score that only 1% of human scientific text written before ChatGPT reaches; "
        "the held-out rates show how often that happened on human and on AI text in calibration.</p>"
        "<h2>Passages</h2>"
        '<div class="scroll"><table><tr><th>Window</th><th>Section</th><th>Words</th><th>Style score</th>'
        f"{''.join(f'<th>{e(ws["name"])}</th>' for ws in wsum.values())}<th>Flag</th><th>AI-typical words</th></tr>{''.join(wrows)}</table></div>"
        '<h2>Text</h2><p>Passages (~300 words): <span class="w0">flagged by one unvalidated tool</span> · <span class="w5">flagged by two or more tools, or style past 5%</span> · <span class="w1">flagged by a validated tool, or style past 1%</span>. '
        'Sentences: <span class="ws">marked as AI by one tool</span> · <span class="ws1">by two or more, or by a validated tool</span> (hover to see which). Words: '
        '<mark class="word">AI-typical word</mark> · <mark class="phrase">stock phrasing</mark> · <mark class="art">artefact</mark>. '
        "Everything else is plain.</p>"
        f'<div class="text">{"".join(parts)}</div>'
        "<h2>Findings</h2>"
        + (
            f"<ol>{''.join(f'<li>{x}</li>' for x in findings)}</ol>"
            if findings
            else "<p>None.</p>"
        )
        + f"<h2>Limits</h2><ul>{lims}</ul></main>"
    )
