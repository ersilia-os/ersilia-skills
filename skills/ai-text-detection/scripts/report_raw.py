"""The raw, text-first report: scores first, then the document with only its AI-looking
parts highlighted. Plain HTML on purpose: a few colours, no theme, no scripts.

Called by build_report.py (``--style raw``, the default).
"""

from __future__ import annotations

import html
from pathlib import Path

from _common import REFS, read_json

WORD_SHADE = {"1%": "w1", "5%": "w5"}
PRIORITY = {"art": 3, "phrase": 2, "word": 1}

CSS = """
:root { color-scheme: light; }
body { background: #fff; color: #111; }
main { max-width: 52em; margin: 0 auto; padding-block: 12px 40px;
       padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
table { border-collapse: collapse; font-size: 13px; }
th, td { border: 1px solid #aaa; padding: 2px 6px; text-align: left; vertical-align: top; }
.scroll { overflow-x: auto; }
.w5 { background: #fff4c2; }
.w1 { background: #ffd2bd; }
mark.word { background: #ffe066; }
mark.phrase { background: #cfe5ff; }
mark.art { background: #ff9b9b; }
.lab { font: 12px monospace; color: #444; }
.text p { margin: 0 0 .8em; }
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


def render_segment(text: str, a: int, b: int, spans: list[dict]) -> str:
    """HTML for text[a:b] with non-overlapping <mark>s; paragraphs kept."""
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
    body = "".join(out).strip()
    paras = [p.replace("\n", "<br>") for p in body.split("\n\n") if p.strip()]
    return "".join(f"<p>{p}</p>" for p in paras)


def build_raw(work: Path, case: str, kind: str, context: str) -> str:
    """The raw report fragment."""
    doc = read_json(work / "text.json") or {}
    text = doc.get("text", "")
    g = read_json(work / "grade.json") or {}
    arts = read_json(work / "artifacts.json") or {"hits": [], "hidden": []}
    refs = read_json(work / "references.json") or {"references": [], "counts": {}}
    det = read_json(work / "detectors.json") or {}
    sty = read_json(work / "stylometry.json") or {}
    jud = read_json(work / "judgements.json") or {}
    cal = read_json(REFS / "calibration.json") or {}
    ja = jud.get("artifacts", {})
    scal = cal.get("stylometry") or {}
    sthr = scal.get("thresholds") or {}
    ss = sty.get("summary") or {}
    swin = sty.get("windows") or []
    dwin = {w["id"]: w for w in det.get("windows") or []}
    dsum = det.get("summary") or {}

    # Per-window flag: the strictest of style score and detectors.
    for w in swin:
        flags = []
        sc = w.get("style_score")
        if sc is not None and sthr:
            flags.append(
                "1%" if sc >= sthr["1%"] else ("5%" if sc >= sthr["5%"] else None)
            )
        d = dwin.get(w["id"], {})
        flags += [d.get("binoculars_flag"), d.get("fast_detectgpt_flag")]
        w["flag"] = "1%" if "1%" in flags else ("5%" if "5%" in flags else None)

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

    def row(name: str, value: str, ref: str) -> str:
        return f"<tr><td>{e(name)}</td><td>{value}</td><td>{ref}</td></tr>"

    def p_(k: str) -> str:
        return f" (human percentile {mp[k]:.0f})" if mp.get(k) is not None else ""

    rows = [
        row("Verdict", f"<b>{e(g.get('tier', 'n/a'))}</b>", e(g.get("headline", ""))),
        row(
            "Style score, median over windows",
            f"{num(ss.get('style_score_median'))}; past 1%: {wo.get('1%', {}).get('count', 0)}/{nw}; past 5%: {wo.get('5%', {}).get('count', 0)}/{nw}",
            f"thresholds {num(sthr.get('1%'))} (1%) / {num(sthr.get('5%'))} (5%); held-out human windows flagged: "
            f"{pct((held.get('human (held out)') or {}).get('past_1pct'))} / {pct((held.get('human (held out)') or {}).get('past_5pct'))}; "
            f"AI windows flagged: {pct((held.get('AI (held out)') or {}).get('past_1pct'))} / {pct((held.get('AI (held out)') or {}).get('past_5pct'))}; AUROC {num(scal.get('auroc'))}",
        ),
    ]
    for k, label in (
        ("binoculars", "Binoculars"),
        ("fast_detectgpt", "Fast-DetectGPT"),
    ):
        s = dsum.get(k)
        if s:
            t = (cal.get("detectors") or {}).get(k) or {}
            h = (t.get("heldout") or {}).get("human (held out)") or {}
            rows.append(
                row(
                    label,
                    f"median {num(s['median'], 3)}; past 1%: {s['over_1pct']}/{s['windows']}; past 5%: {s['over_5pct']}/{s['windows']}; document flag: {e(s.get('document_flag') or 'none')}",
                    f"thresholds {num(t.get('thr_1'), 3)} / {num(t.get('thr_5'), 3)} ({e(t.get('direction'))} = machine-like); held-out human flagged {pct(h.get('past_1pct'))} / {pct(h.get('past_5pct'))}; AUROC {num(t.get('auroc'))}",
                )
            )
        else:
            rows.append(row(label, "not run", "models not installed or skipped"))
    rows += [
        row(
            "Excess vocabulary per 1,000 words",
            f"{num(d.get('excess_rate'), 1)}{p_('excess_rate')}",
            "Kobak et al. 2025 word list",
        ),
        row(
            "AI-typical words per 1,000 words",
            f"{num(d.get('marked_rate'), 1)}{p_('marked_rate')}: {e(', '.join(ss.get('marked_words', [])) or 'none')}",
            "delve, underscore, meticulous, …",
        ),
        row(
            "Stock phrasing per 1,000 words",
            f"{num(d.get('tells_rate'), 1)}{p_('tells_rate')}: {e(', '.join(f'{k} {v}' for k, v in (ss.get('tells') or {}).items()) or 'none')}",
            "Wikipedia 'Signs of AI writing', humanizer, stop-slop",
        ),
        row(
            "Em dashes per 1,000 words",
            f"{num(d.get('em_dash_rate'), 1)}{p_('em_dash_rate')}",
            "",
        ),
        row(
            "Sentence-length variation (CV)",
            f"{num(d.get('sent_cv'))}{p_('sent_cv')}",
            "lower = more uniform",
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
        ),
        row("Close-reading findings", str(len(jud.get("reading", []))), "listed below"),
    ]

    # Per-window table.
    wrows = []
    for w in swin:
        dd = dwin.get(w["id"], {})
        wrows.append(
            f'<tr><td><a href="#{w["id"]}">{w["id"]}</a></td><td>{e(w.get("section"))}</td><td>{w.get("n_words")}</td>'
            f"<td>{num(w.get('style_score'))}</td><td>{num(dd.get('binoculars'), 3)}</td><td>{num(dd.get('fast_detectgpt'))}</td>"
            f"<td>{e(w.get('flag') or '')}</td><td>{e(', '.join(w.get('_marked_words') or []))}</td></tr>"
        )

    # The text, window by window, with gaps (headings, skipped sections) as plain text.
    parts, pos = [], 0
    for w in sorted(swin, key=lambda x: x.get("start", 0)):
        a, b = w.get("start"), w.get("end")
        if a is None:
            continue
        if a > pos:
            parts.append(render_segment(text, pos, a, spans))
        shade = WORD_SHADE.get(w.get("flag"), "")
        dd = dwin.get(w["id"], {})
        lab = (
            f"[{w['id']} · style {num(w.get('style_score'))}"
            + (
                f" · bino {num(dd.get('binoculars'), 3)} · fdg {num(dd.get('fast_detectgpt'))}"
                if dd
                else ""
            )
            + (f" · past {w['flag']}" if w.get("flag") else "")
            + "]"
        )
        parts.append(
            f'<div id="{w["id"]}" class="{shade}"><span class="lab">{e(lab)}</span>{render_segment(text, a, b, spans)}</div>'
        )
        pos = b
    if pos < len(text):
        parts.append(render_segment(text, pos, len(text), spans))

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
        "detectors" if dsum else None,
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
        "<p>A window is ~300 words. “Past 1%” means a score that only 1% of human scientific text written before ChatGPT reaches; "
        "the held-out rates show how often that happened on human and on AI text in calibration.</p>"
        "<h2>Passages</h2>"
        '<div class="scroll"><table><tr><th>Window</th><th>Section</th><th>Words</th><th>Style score</th><th>Binoculars</th>'
        f"<th>Fast-DetectGPT</th><th>Flag</th><th>AI-typical words</th></tr>{''.join(wrows)}</table></div>"
        '<h2>Text</h2><p>Highlights: <span class="w5">window past 5%</span> · <span class="w1">window past 1%</span> · '
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
