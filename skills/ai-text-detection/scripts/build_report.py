"""Render the evidence report as a self-contained HTML page (Ersilia look).

Reads everything in the work folder (grade.json is required; run grade.py first) and
writes ``<work>/report.html``, ready to publish as a private Artifact. The page is a
fragment as the Artifact tool expects: <title>, <meta>, <style>, then content.

The page puts the verdict and the defensible statements first, each linked to its
evidence row; then the evidence tables; then limitations, policies and the method, folded
away. Quotes from the document appear only where they are evidence.

Usage:
    python build_report.py --case "Reviewer 2, manuscript X" --kind review --context reviewer-of-my-paper
        [--work /tmp/ai_text_detection] [--out report.html]
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

from _common import REFS, SKILL_DIR, WORK_DIR, die, read_json

ERSILIA_CSS = SKILL_DIR.parent / "html-formatting" / "assets" / "ersilia.css"
SOURCE = (
    "https://github.com/ersilia-os/ersilia-skills/tree/main/skills/ai-text-detection"
)
TIER_ORDER = ["none", "weak", "moderate", "strong", "conclusive"]
TIER_LABEL = {
    "none": "No evidence",
    "weak": "Weak",
    "moderate": "Moderate",
    "strong": "Strong",
    "conclusive": "Conclusive",
}
STATUS_LABEL = {
    "ok": ("found", "good"),
    "metadata-mismatch": ("details differ", "warn"),
    "doi-points-elsewhere": ("DOI is another paper", "bad"),
    "doi-not-registered": ("DOI not registered", "bad"),
    "not-found": ("not found", "bad"),
    "unverifiable": ("not checkable", ""),
}
CONTEXT_LABEL = {
    "collaborator-draft": "a collaborator's draft",
    "reviewer-of-my-paper": "a review of your manuscript",
    "manuscript-i-review": "a manuscript you are reviewing",
    "grant-i-review": "a grant application you are reviewing",
    "other": "a document",
}

PAGE_CSS = """
:root { --tier-none: var(--faint); --tier-weak: var(--cobalt); --tier-moderate: var(--warn);
        --tier-strong: var(--tangerine); --tier-conclusive: var(--bad); }
html, body { background: var(--bg); color: var(--ink); }
main.document { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
                padding-block: 28px 12px; max-width: 920px; margin: 0 auto; box-sizing: border-box; }
.verdict { display: grid; gap: 14px; padding: 18px 20px; }
.scale { display: grid; grid-template-columns: repeat(5, 1fr); gap: 4px; }
.scale span { font-size: 11px; color: var(--muted); padding-top: 6px; border-top: 4px solid var(--surface-2); }
.scale span.on { color: var(--ink); font-weight: 600; border-top-color: var(--tc); }
.headline { font-size: 17px; font-weight: 600; line-height: 1.35; text-wrap: balance; margin: 0; }
ol.claims { margin: 0; padding-left: 20px; display: grid; gap: 10px; }
ol.claims li { line-height: 1.5; }
ol.claims .meta { display: block; font-size: 11.5px; color: var(--muted); margin-top: 2px; }
.tierdot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--tc); margin-right: 6px; vertical-align: 1px; }
.badge.tier { --c: var(--tc); }
.note { border-left: 3px solid var(--bad); background: color-mix(in srgb, var(--bad) 6%, var(--surface)); padding: 10px 14px; border-radius: var(--radius-sm); margin: 8px 0; }
.quote { font-family: var(--mono); font-size: 11.5px; color: var(--ink); word-break: break-word; }
.quote mark { background: color-mix(in srgb, var(--warn) 28%, var(--surface)); color: inherit; padding: 0 2px; border-radius: 3px; }
.tablewrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface); }
table.data td { vertical-align: top; }
table.data td.cited { min-width: 260px; }
.strip { display: grid; gap: 6px; }
.strip .row { display: grid; grid-template-columns: 140px 1fr; gap: 10px; align-items: center; font-size: 12px; }
.cells { display: flex; flex-wrap: wrap; gap: 3px; }
.cell { width: 16px; height: 16px; border-radius: 3px; background: var(--surface-2); border: 1px solid var(--border); }
.cell.f5 { background: color-mix(in srgb, var(--warn) 45%, var(--surface)); border-color: transparent; }
.cell.f1 { background: var(--tangerine); border-color: transparent; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 11.5px; color: var(--muted); align-items: center; }
.legend .cell { display: inline-block; vertical-align: -3px; margin-right: 4px; }
details { border-top: 1px solid var(--border); padding: 10px 0; }
details > summary { cursor: pointer; font-weight: 600; font-size: 13px; }
details > summary:focus-visible, button:focus-visible, a:focus-visible { outline: 2px solid var(--brand); outline-offset: 2px; }
details ul { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 6px; line-height: 1.5; }
.toolbar { display: flex; gap: 8px; align-items: center; margin: 0 0 8px; font-size: 12px; color: var(--muted); flex-wrap: wrap; }
.toolbar button { font: inherit; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface); color: var(--ink); cursor: pointer; }
.toolbar button[aria-pressed="true"] { border-color: var(--brand); color: var(--brand); background: color-mix(in srgb, var(--brand) 8%, var(--surface)); }
.kv { display: grid; grid-template-columns: max-content 1fr; gap: 4px 14px; font-size: 12px; }
.kv dt { color: var(--muted); } .kv dd { margin: 0; font-family: var(--mono); word-break: break-word; }
a { color: var(--brand); }
@media (max-width: 520px) { .strip .row { grid-template-columns: 1fr; } .scale span { font-size: 10px; } }
"""


def e(s: object) -> str:
    """HTML-escape."""
    return html.escape("" if s is None else str(s))


def tier_style(t: str) -> str:
    """Inline custom property naming the tier colour."""
    return f'style="--tc: var(--tier-{t})"'


def quote_html(h: dict) -> str:
    """The hit's context with the match highlighted."""
    q, m = h.get("quote", ""), h.get("match", "")
    i = q.find(m)
    if i < 0:
        return f'<span class="quote">{e(q)}</span>'
    return (
        f'<span class="quote">{e(q[:i])}<mark>{e(m)}</mark>{e(q[i + len(m) :])}</span>'
    )


def section(title: str, body: str, sid: str) -> str:
    """A report section."""
    return f'<section class="section" id="{sid}"><h2>{e(title)}</h2>{body}</section>'


def build(work: Path, case: str, kind: str, context: str) -> str:
    """The report fragment."""
    g = read_json(work / "grade.json") or die("missing grade.json; run grade.py")
    doc = read_json(work / "text.json") or {}
    arts = read_json(work / "artifacts.json") or {"hits": [], "hidden": []}
    refs = read_json(work / "references.json") or {"references": []}
    det: dict = {}  # local model detectors were removed; web detectors live in the raw report
    sty = read_json(work / "stylometry.json") or {}
    jud = read_json(work / "judgements.json") or {}
    cal = read_json(REFS / "calibration.json") or {}
    pol = read_json(REFS / "policies.json") or {"policies": []}
    t = g["tier"]

    # Verdict and statements.
    scale = "".join(
        f'<span class="{"on" if x == t else ""}" {tier_style(x)}>{TIER_LABEL[x]}</span>'
        for x in TIER_ORDER
    )
    claims = []
    for s in g["statements"]:
        links = ", ".join(f'<a href="#ev-{e(x)}">{e(x)}</a>' for x in s["evidence"][:8])
        claims.append(
            f'<li><span class="tierdot" {tier_style(s["tier"])}></span><b>{TIER_LABEL.get(s["tier"], s["tier"])}.</b> {e(s["text"])}'
            f'<span class="meta">Evidence: {links}{" · " + e(s["check"]) if s.get("check") else ""}</span></li>'
        )
    claims_html = (
        f'<ol class="claims">{"".join(claims)}</ol>'
        if claims
        else '<p class="muted">Nothing to report.</p>'
    )
    sep = "".join(
        f'<div class="note"><b>{e(s["kind"].replace("-", " ").capitalize())}.</b> {e(s["text"])} '
        f'<span class="muted">Evidence: {", ".join(f"<a href=#ev-{e(x)}>{e(x)}</a>" for x in s["evidence"])}</span></div>'
        for s in g["separate"]
    )
    verdict = (
        f'<div class="card verdict" {tier_style(t)}><div class="scale" aria-label="Evidence scale">{scale}</div>'
        f'<p class="headline">{e(g["headline"])}</p>{sep}'
        f'<div><div class="eyebrow">What you can say, with the evidence behind it</div>{claims_html}</div></div>'
    )

    # Artefacts table.
    ja = jud.get("artifacts", {})
    rows = []
    for h in arts["hits"]:
        dismissed = not ja.get(h["id"], {}).get("confirmed", True)
        loc = ", ".join(
            x
            for x in (
                h.get("section"),
                f"p. {h['page']}" if h.get("page") else None,
                None if h["in"] == "body" else h["in"],
            )
            if x
        )
        status = (
            f'<br><span class="badge">set aside: {e(ja[h["id"]].get("why"))}</span>'
            if dismissed
            else ""
        )
        rows.append(
            f'<tr id="ev-{e(h["id"])}"><td class="mono">{e(h["id"])}</td>'
            f'<td><span class="badge tier" {tier_style(h["tier"])}>{TIER_LABEL[h["tier"]]}</span>{status}</td>'
            f"<td>{e(h['shows'])}{(' Established term: <i>' + e(h['established_term']) + '</i>.') if h.get('established_term') else ''}</td>"
            f"<td>{quote_html(h)}</td><td>{e(loc or 'body')}</td></tr>"
        )
    for h in arts.get("hidden", []):
        rows.append(
            f'<tr id="ev-{e(h["id"])}"><td class="mono">{e(h["id"])}</td><td><span class="badge bad">hidden text</span></td>'
            f"<td>{e(h['why'])}{'; matches ' + e(', '.join(h['matches'])) if h.get('matches') else ''}</td>"
            f'<td><span class="quote">{e(h["text"][:600])}</span></td><td>{e("p. " + str(h["page"]) if h.get("page") else "")}</td></tr>'
        )
    art_html = (
        '<div class="tablewrap"><table class="data"><thead><tr><th>Id</th><th>Strength</th><th>What it shows</th>'
        f"<th>In context</th><th>Where</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        if rows
        else '<p class="muted">No chatbot leftovers, citation tokens, placeholders, hidden text or tortured phrases were found.</p>'
    )
    read_rows = "".join(
        f'<tr id="ev-read{i}"><td class="mono">read{i}</td><td><span class="badge tier" {tier_style(r.get("tier", "weak"))}>'
        f'{TIER_LABEL.get(r.get("tier", "weak"))}</span></td><td>{e(r["claim"])}</td><td><span class="quote">{e(r.get("quote", ""))}</span></td>'
        f'<td>{e(r.get("where", ""))}<br><span class="muted">{e(r.get("check", ""))}</span></td></tr>'
        for i, r in enumerate(jud.get("reading", []), 1)
    )
    if read_rows:
        art_html += (
            '<p class="muted" style="margin:14px 0 6px">Findings from a close reading (each quoted, each checkable):</p>'
            '<div class="tablewrap"><table class="data"><thead><tr><th>Id</th><th>Strength</th><th>Finding</th><th>Quote</th>'
            f"<th>Where / how to check</th></tr></thead><tbody>{read_rows}</tbody></table></div>"
        )

    # References table.
    rl = refs.get("references", [])
    jr = jud.get("references", {})
    rrows = []
    for r in rl:
        label, cls = STATUS_LABEL.get(r["status"], (r["status"], ""))
        found = r.get("found") or {}
        found_html = ""
        if found.get("title"):
            link = (
                f"https://doi.org/{found['doi']}"
                if found.get("doi")
                else found.get("openalex") or ""
            )
            found_html = (
                f'<a href="{e(link)}" target="_blank" rel="noopener">{e(found["title"])}</a>'
                if link
                else e(found["title"])
            )
            found_html += f'<br><span class="muted">{e(found.get("first_author") or "")} {e(found.get("year") or "")} · {e(found.get("registry"))}</span>'
        hand = jr.get(str(r["n"]))
        hand_html = (
            f'<br><span class="muted">Checked by hand: {e(hand.get("why"))}</span>'
            if hand
            else ""
        )
        q = " ".join(
            f'<a href="{e(u)}" target="_blank" rel="noopener">lookup {i}</a>'
            for i, u in enumerate(r.get("queried", []), 1)
        )
        rrows.append(
            f'<tr id="ev-ref{r["n"]}" data-ok="{1 if r["status"] in ("ok", "unverifiable") else 0}"><td class="num">{r["n"]}</td>'
            f'<td><span class="badge {cls}">{e(label)}</span></td><td class="cited">{e(r["raw"])}</td>'
            f"<td>{found_html}{'<br>' if found_html and r['issues'] else ''}{'<br>'.join(e(x) for x in r['issues'])}{hand_html}</td>"
            f"<td>{q}</td></tr>"
        )
    counts = refs.get("counts", {})
    ref_html = (
        '<div class="toolbar"><button type="button" id="refs-problems" aria-pressed="true">Problems only</button>'
        f"<span>{len(rl)} references: "
        + ", ".join(
            f"{v} {STATUS_LABEL.get(k, (k,))[0]}" for k, v in sorted(counts.items())
        )
        + "</span></div>"
        '<div class="tablewrap"><table class="data" id="refs"><thead><tr><th class="num">#</th><th>Status</th><th>As cited</th>'
        f"<th>Closest record / issue</th><th>Re-run</th></tr></thead><tbody>{''.join(rrows)}</tbody></table></div>"
        if rl
        else '<p class="muted">No reference list was found in the document.</p>'
    )

    # Statistical signals: one cell per window.
    det.get("windows", [])
    swin = sty.get("windows", [])
    strip_rows = []

    def cells(rows_: list[dict], key: str) -> str:
        out = []
        for w in rows_:
            f = w.get(key)
            cls = "f1" if f == "1%" else ("f5" if f == "5%" else "")
            out.append(
                f'<span class="cell {cls}" title="{e(w["id"])} · {e(w.get("section"))}"></span>'
            )
        return "".join(out)

    sthr = (cal.get("stylometry") or {}).get("thresholds") or {}
    if swin and sthr:
        for w in swin:
            s = w.get("style_score")
            w["style_flag"] = (
                None
                if s is None
                else ("1%" if s >= sthr["1%"] else ("5%" if s >= sthr["5%"] else None))
            )
        strip_rows.append(
            f'<div class="row"><span>Style score</span><div class="cells">{cells(swin, "style_flag")}</div></div>'
        )
    dsum = det.get("summary") or {}
    val_lines = []
    vmd = REFS / "validation.md"
    for k, v in dsum.items():
        val_lines.append(
            f"<tr><td>{e(k.replace('_', '-'))}</td><td class='num'>{v['over_1pct']}/{v['windows']}</td>"
            f"<td class='num'>{v['over_5pct']}/{v['windows']}</td><td>{e(v.get('document_flag') or 'not flagged')}</td></tr>"
        )
    ss = sty.get("summary") or {}
    stats_html = (
        '<p class="muted" style="margin:0 0 10px">The text is cut into windows of about 300 words. Each square is one window, '
        "in reading order. A window is coloured when its score is one that only 1% (dark) or 5% (light) of human scientific "
        "text written before ChatGPT reaches. Formulaic passages and non-native or heavily edited English can also colour a window.</p>"
        f'<div class="card" style="padding:14px 16px"><div class="strip">{"".join(strip_rows) or "<span class=muted>Detectors were not run.</span>"}</div>'
        '<div class="legend" style="margin-top:10px"><span><span class="cell f1"></span>past the 1% threshold</span>'
        '<span><span class="cell f5"></span>past the 5% threshold</span><span><span class="cell"></span>within the human range</span></div></div>'
    )
    if val_lines:
        stats_html += (
            '<div class="tablewrap" id="ev-detectors" style="margin-top:12px"><table class="data"><thead><tr><th>Detector</th>'
            '<th class="num">Windows past 1%</th><th class="num">Past 5%</th><th>Document flag</th></tr></thead>'
            f"<tbody>{''.join(val_lines)}</tbody></table></div>"
        )
    if ss:
        d = ss.get("document", {})
        mp = ss.get("median_percentiles", {})

        def pct(k: str) -> str:
            return f" (human percentile {mp[k]:.0f})" if mp.get(k) is not None else ""

        stats_html += (
            f'<dl class="kv" id="ev-stylometry" style="margin-top:12px">'
            f"<dt>Excess vocabulary</dt><dd>{d.get('excess_rate', 0):.1f} per 1,000 words{pct('excess_rate')}</dd>"
            f"<dt>Most typical AI words</dt><dd>{d.get('marked_rate', 0):.1f} per 1,000 words{pct('marked_rate')}: {e(', '.join(ss.get('marked_words', [])[:20]) or 'none')}</dd>"
            f"<dt>Stock phrasing</dt><dd>{d.get('tells_rate', 0):.1f} per 1,000 words{pct('tells_rate')}: {e(', '.join(f'{k} {v}' for k, v in (ss.get('tells') or {}).items()) or 'none')}</dd>"
            f"<dt>Em dashes</dt><dd>{d.get('em_dash_rate', 0):.1f} per 1,000 words{pct('em_dash_rate')}</dd>"
            f"<dt>Sentence-length variation</dt><dd>{d.get('sent_cv', 0):.2f}{pct('sent_cv')} (lower is more uniform)</dd></dl>"
        )

    base = read_json(work / "baseline.json") or {}
    if base.get("comparison"):
        brow = "".join(
            f"<tr><td>{e(k.replace('_', '-'))}</td><td class='num'>{c['document_median']:.3f}</td>"
            f"<td class='num'>{c['baseline_median']:.3f}</td><td class='num'>{c['baseline_min']:.3f} to {c['baseline_max']:.3f}</td>"
            f"<td>{'outside' if c['outside_range'] else 'within'}</td></tr>"
            for k, c in base["comparison"].items()
        )
        stats_html += (
            f'<p class="muted" style="margin:14px 0 6px" id="ev-baseline">Compared with {base["n_texts"]} texts by the same '
            f"author from before ChatGPT ({e(base['source'])}):</p>"
            '<div class="tablewrap"><table class="data"><thead><tr><th>Measure</th><th class="num">This document</th>'
            '<th class="num">Their earlier median</th><th class="num">Their earlier range</th><th>This document is</th></tr></thead>'
            f"<tbody>{brow}</tbody></table></div>"
        )

    # Limitations, policies, method.
    lim = "".join(f"<li>{e(c)}</li>" for c in g["caveats"])
    ctx_kind = {"grant-i-review": "grant-review", "manuscript-i-review": "review"}.get(
        context, kind
    )
    pols = [
        p for p in pol["policies"] if ctx_kind in p["applies"] or kind in p["applies"]
    ]
    pol_html = "".join(
        f'<li><b>{e(p["body"])}.</b> {e(p["summary"])} <a href="{e(p["url"])}" target="_blank" rel="noopener">Source</a>'
        f"{' (summary from secondary sources)' if p.get('secondary') else ''}</li>"
        for p in pols
    )
    method = (
        '<dl class="kv">'
        f"<dt>Analysed</dt><dd>{date.today().isoformat()} · {e(doc.get('format'))} · {e(doc.get('n_words'))} words · "
        f"{len(swin)} windows</dd>"
        f"<dt>Calibration</dt><dd>{e(cal.get('version', 'not calibrated'))} · {e((cal.get('corpus') or {}).get('human_windows'))} human windows, "
        f"{e((cal.get('corpus') or {}).get('ai_windows'))} AI windows (see references/validation.md)</dd>"
        f"<dt>Rules</dt><dd>markers.json v{e((read_json(REFS / 'markers.json') or {}).get('version'))} · grading.json v{e(g.get('grading_version'))}</dd>"
        f"<dt>Privacy</dt><dd>Analysis ran on this computer. Reference strings went to Crossref, DataCite, doi.org, OpenAlex and Semantic Scholar; text chunks went to web detectors only when the user's rules allowed it.</dd>"
        "</dl>"
        '<ul><li>Artefacts: regular expressions for chatbot and AI-tool leftovers, from Wikipedia\'s "Signs of AI writing", '
        "Retraction Watch and Academ-AI cases, and the tools' own citation and interface formats.</li>"
        "<li>References: every DOI resolved in Crossref, DataCite or doi.org; every other reference searched by title in Crossref and OpenAlex.</li>"
        "<li>Web detectors (Pangram, GPTZero and others), run chunk by chunk in Chrome; see the raw report for their scores.</li>"
        "<li>Style: excess vocabulary from Kobak et al. 2025 (Science Advances) and Liang et al. 2024, phrasing patterns from "
        "Wikipedia's list, blader/humanizer and stop-slop, combined in a logistic model fitted on the calibration corpus.</li></ul>"
    )
    _ = vmd
    folded = (
        f"<details open><summary>Limits and other explanations</summary><ul>{lim}</ul></details>"
        + (
            f"<details><summary>Policies that apply to {e(CONTEXT_LABEL.get(context, 'this document'))}</summary><ul>{pol_html}</ul></details>"
            if pol_html
            else ""
        )
        + f"<details><summary>Method and reproducibility</summary>{method}</details>"
    )

    css = (
        ERSILIA_CSS.read_text(encoding="utf-8")
        if ERSILIA_CSS.exists()
        else ":root{--bg:#FAFAFC;--surface:#fff;--surface-2:#F4F4F8;--border:#E6E6EE;--ink:#2C3E50;--muted:#6B6675;--faint:#9A93A6;--brand:#6C5CE7;--good:#3F9D6B;--warn:#C98A1E;--bad:#D9534F;--cobalt:#457B9D;--tangerine:#F4845F;--mono:ui-monospace,Menlo,monospace;--sans:system-ui,sans-serif;--radius:14px;--radius-sm:8px}"
    )
    script = """
<script>
(function () {
  var b = document.getElementById('refs-problems'), t = document.getElementById('refs');
  if (!b || !t) return;
  function apply() {
    var on = b.getAttribute('aria-pressed') === 'true', shown = 0;
    t.querySelectorAll('tbody tr').forEach(function (r) { var hide = on && r.dataset.ok === '1'; r.hidden = hide; if (!hide) shown++; });
    if (on && shown === 0) { b.setAttribute('aria-pressed', 'false'); apply(); }
  }
  b.addEventListener('click', function () { b.setAttribute('aria-pressed', b.getAttribute('aria-pressed') === 'true' ? 'false' : 'true'); apply(); });
  document.querySelectorAll('a[href^="#ev-ref"]').forEach(function (a) { a.addEventListener('click', function () { b.setAttribute('aria-pressed', 'false'); apply(); }); });
  apply();
})();
</script>"""
    title = case[:60]
    return (
        f'<title>{e(title)}</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
        f"<style>\n{css}\n{PAGE_CSS}\n</style>\n"
        '<main class="document">'
        '<header class="brandhead"><span class="eyebrow brand">AI text detection · Ersilia Open Source Initiative</span>'
        f'<h1 class="wordmark">{e(case)}</h1>'
        f'<p class="muted" style="margin:.4em 0 0;max-width:62ch">Evidence report on {e(CONTEXT_LABEL.get(context, "a document"))} '
        f"({e(kind)}, {e(doc.get('n_words'))} words). Every finding below is quoted and can be re-checked by anyone.</p></header>"
        + section("Verdict", verdict, "verdict")
        + section("Artefacts and close reading", art_html, "artefacts")
        + section("References", ref_html, "references")
        + section("Statistical signals", stats_html, "signals")
        + f'<section class="section">{folded}</section>'
        + '<footer class="credit">Brought to you by the <a href="https://ersilia.io" target="_blank" rel="noopener">Ersilia Open Source Initiative</a>'
        f' — a tech-nonprofit fueling sustainable research in the Global South.<br><a href="{SOURCE}" target="_blank" rel="noopener">Source code on GitHub</a></footer>'
        "</main>" + script
    )


def main(argv: list[str] | None = None) -> int:
    """Write report.html."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument(
        "--case",
        required=True,
        help="a neutral label for the document (shown as the page heading)",
    )
    p.add_argument("--kind", default="article")
    p.add_argument("--context", default="other")
    p.add_argument("--out")
    p.add_argument(
        "--style",
        choices=["raw", "ersilia"],
        default="raw",
        help="raw (default): scores, then the text with AI-looking passages highlighted; "
        "ersilia: the designed evidence page",
    )
    args = p.parse_args(argv)
    work = Path(args.work)
    out = Path(args.out) if args.out else work / "report.html"
    if args.style == "raw":
        from report_raw import build_raw

        page = build_raw(work, args.case, args.kind, args.context)
    else:
        page = build(work, args.case, args.kind, args.context)
    out.write_text(page, encoding="utf-8")
    print(f"report: {out}")
    _ = json
    return 0


if __name__ == "__main__":
    sys.exit(main())
