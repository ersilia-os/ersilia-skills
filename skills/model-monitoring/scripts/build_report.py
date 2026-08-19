"""Render the model-monitoring HTML report from the two data payloads.

Takes coverage.json (from fetch_coverage.py) and maintenance.json (from
fetch_maintenance.py) and writes one self-contained HTML file: no external
scripts, no stylesheets, images inlined as data URIs. That matters because the
report gets archived and passed around, and a file that silently loses its
charts a month later is worse than no file.

Design notes, so future edits stay coherent rather than accreting:

  * The signature element is the **coverage plate** — one cell per model laid out
    as a dense grid, coloured by coverage class. A microplate is native
    vernacular in drug discovery, and it is the only device that makes ~250
    models legible in a single glance. Everything else on the page is kept
    deliberately quiet so the plate carries the visual weight.
  * Type is set in IBM Plex (Sans for prose, Mono for every model id and count).
    Model ids and molecule counts are data to be scanned and compared, so they
    get tabular figures; prose does not.
  * Colour encodes coverage class and nothing else. Class colours are reused
    verbatim in the plate, the legend, the badges and the table so the reader
    learns the mapping once.

Usage:
    python build_report.py --coverage coverage.json \
        --maintenance maintenance.json --out report.html
"""

import argparse
import html
import json
from datetime import datetime, timezone

# Coverage classes in triage order, with the label and colour used everywhere.
# Colours are Ersilia brand values: Yellow, Orange, Purple and Mint. The mapping is
# semantic — Mint reads as healthy, Yellow as caution, Orange as the alarm (the
# palette has no true red), Purple as the odd case that sits outside the hub.
CLASSES = [
    ("partial", "Incomplete", "#FAD782",
     "Some predictions stored, but fewer than the full collection"),
    ("missing", "Not started", "#FAA08C",
     "The hub lists this model, isaura holds nothing for it"),
    ("orphan", "Orphaned", "#AA96FA",
     "isaura holds data for a model the hub search no longer returns"),
    ("complete", "Complete", "#BEE6B4",
     "Every reference molecule has a stored prediction"),
]
CLASS_COLOR = {k: c for k, _, c, _ in CLASSES}
CLASS_LABEL = {k: lbl for k, lbl, _, _ in CLASSES}

# Singularity image availability. Deliberately the same three brand hues as the
# isaura classes, in the same roles — Mint for "we have it", Orange for "we do
# not", Purple for "it sits outside the population" — so a reader who has learnt
# the colours in one section reads the other for free.
SIF_CLASSES = [
    ("missing", "No image", "#FAA08C",
     "The model is Ready, but no .sif image has been built"),
    ("extra", "Not in Ready list", "#AA96FA",
     "An image exists for a model that is not currently Ready"),
    ("available", "Available", "#BEE6B4",
     "A built .sif image is in the bucket"),
]
SIF_COLOR = {k: c for k, _, c, _ in SIF_CLASSES}
SIF_LABEL = {k: lbl for k, lbl, _, _ in SIF_CLASSES}

CSS = """
/* Ersilia brand palette, used verbatim. It is one dark plum plus a set of light
   pastels, which dictates how colour can be used here: the pastels are strong as
   *fills* and illegible as text on white, so every fill (wells, badges, bars,
   chips) is a pastel and every piece of text is plum. Emphasis that would
   normally be done by colouring a numeral is done with a pastel accent rule
   instead, so nothing important depends on reading pale text.
   Surfaces (--paper, --plate) are tints derived from brand Gray; every hue on the
   page is a brand value. */
:root{
  --plum:#50285A; --mint:#BEE6B4; --gray:#D2D2D0; --yellow:#FAD782;
  --blue:#8CC8FA; --pink:#DCA0DC; --orange:#FAA08C; --purple:#AA96FA;

  --ink:#50285A; --ink-soft:#6B4A73; --muted:#7C7080;
  --paper:#F7F7F5; --card:#FFFFFF; --rule:#D2D2D0; --plate:#EDEDEA;

  --complete:#BEE6B4; --partial:#FAD782; --missing:#FAA08C; --orphan:#AA96FA;
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"IBM Plex Sans","Segoe UI",Helvetica,Arial,sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.mono,code{font-family:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Consolas,monospace;
  font-variant-numeric:tabular-nums}
.wrap{max-width:1180px;margin:0 auto;padding:0 24px}
a{color:var(--plum);text-decoration-color:var(--purple);text-underline-offset:2px}
a:focus-visible,button:focus-visible,input:focus-visible{
  outline:2px solid var(--plum); outline-offset:2px}

/* ---- masthead ---- */
header.top{background:var(--plum);color:#F4EEF6;padding:38px 0 30px}
header.top .eyebrow{
  font-size:11px;letter-spacing:.20em;text-transform:uppercase;
  color:var(--mint);margin:0 0 10px}
header.top h1{
  margin:0;font-size:clamp(28px,4.2vw,44px);line-height:1.05;font-weight:600;
  letter-spacing:-.02em}
header.top .sub{margin:12px 0 0;color:#D8C6DE;max-width:62ch}
header.top .sub a{color:var(--mint);text-decoration-color:var(--mint)}
header.top .sub code{color:var(--yellow)}

/* ---- headline figures ---- */
/* Fixed column counts, not auto-fit: the headline set is 8 figures, and letting
   the browser fit 7 per row leaves a single stranded cell beside a dead gap. */
.figures{display:grid;grid-template-columns:repeat(4,1fr);
  gap:1px;background:var(--rule);border:1px solid var(--rule);margin:28px 0}
@media (max-width:820px){.figures{grid-template-columns:repeat(2,1fr)}}
.fig{background:var(--card);padding:16px 18px;border-top:3px solid transparent}
.fig .n{font-size:30px;font-weight:600;letter-spacing:-.02em;display:block}
.fig .k{font-size:11px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
/* Emphasis by accent rule rather than by colouring the numeral: the brand's
   alert hue is a pale salmon that would be hard to read as 30px text on white. */
.fig.alert{border-top-color:var(--orange);background:#FEF6F3}

/* ---- sections ---- */
section{margin:44px 0}
h2{font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--ink-soft);
  margin:0 0 4px;font-weight:600}
h2+.lede{margin:0 0 18px;color:var(--muted);max-width:70ch}
h3{font-size:16px;margin:26px 0 10px;font-weight:600}

/* ---- the coverage plate (signature) ---- */
.plate{display:flex;flex-wrap:wrap;gap:3px;padding:16px;background:var(--plate);
  border:1px solid var(--rule)}
.well{width:15px;height:15px;border-radius:2px;background:#fff;position:relative;
  box-shadow:inset 0 0 0 1px rgba(80,40,90,.10)}
.well[data-c=complete]{background:var(--complete)}
.well[data-c=partial]{background:var(--partial)}
.well[data-c=missing]{background:var(--missing)}
.well[data-c=orphan]{background:var(--orphan)}
.well[data-ready="0"]{opacity:.42}
.figures.six{grid-template-columns:repeat(3,1fr)}
@media (max-width:820px){.figures.six{grid-template-columns:repeat(2,1fr)}}
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));
  gap:8px 24px;margin:14px 0 0;font-size:13px}
.legend span.sw{width:11px;height:11px;border-radius:2px;display:inline-block;
  margin-right:7px;vertical-align:-1px;box-shadow:inset 0 0 0 1px rgba(80,40,90,.12)}
/* Deliberately not `.note`: that class is the yellow callout box, and reusing the
   name here wrapped every legend caption in a callout. */
.legend .dim{color:var(--muted)}
.legend .fade{grid-column:1/-1;color:var(--muted)}

/* ---- tables ---- */
.tablewrap{overflow-x:auto;border:1px solid var(--rule);background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--rule);
  vertical-align:top}
th{background:#F1EBF3;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-soft);position:sticky;top:0;cursor:pointer;white-space:nowrap}
th[aria-sort]{color:var(--ink)}
tbody tr:hover{background:#FAF6FB}
td.num{text-align:right}
/* Pastel fill, plum text — the palette has no saturated hue that would carry
   white text at this size. */
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;
  font-weight:600;color:var(--plum);white-space:nowrap}
.pill{display:inline-block;padding:1px 7px;border:1px solid var(--rule);
  border-radius:999px;font-size:11px;color:var(--ink-soft);background:#fff}

/* ---- controls ---- */
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0 0 12px}
.controls input[type=search]{padding:7px 11px;border:1px solid var(--rule);
  border-radius:4px;font:inherit;min-width:210px;background:#fff}
.chip{padding:5px 12px;border:1px solid var(--rule);background:#fff;border-radius:999px;
  font:inherit;font-size:12.5px;cursor:pointer;color:var(--ink-soft)}
.chip[aria-pressed=true]{background:var(--plum);border-color:var(--plum);color:#fff}
.count{color:var(--muted);font-size:12.5px;margin-left:auto}

/* ---- bars ---- */
.bar{height:7px;background:var(--plate);border-radius:99px;overflow:hidden;min-width:70px}
.bar>i{display:block;height:100%;background:var(--complete)}

/* ---- plots + notes ---- */
figure{margin:0 0 26px}
figure img{width:100%;height:auto;border:1px solid var(--rule);background:#fff}
figcaption{font-size:12.5px;color:var(--muted);margin-top:7px}
.note{border-left:3px solid var(--yellow);background:#FEF9EC;padding:12px 16px;
  margin:18px 0;font-size:13.5px}
.note strong{display:block;margin-bottom:2px}
footer{border-top:1px solid var(--rule);margin-top:56px;padding:22px 0 44px;
  color:var(--muted);font-size:12.5px}
footer ul{margin:8px 0 0;padding-left:18px}
.empty{padding:16px;color:var(--muted);background:var(--card);
  border:1px solid var(--rule)}
@media (prefers-reduced-motion:no-preference){
  .fig,.well{transition:opacity .15s ease}
}
@media print{
  header.top{background:#fff;color:#000}
  .controls{display:none}
}
"""

# Search, chip filtering and column sort, scoped per `.filterable` block so the
# page can carry several independent tables. Everything is found by class within
# the block rather than by id, because duplicate ids across two tables would be
# invalid HTML and the second table would silently stop responding.
JS = """
(function(){
  document.querySelectorAll('.filterable').forEach(function(block){
    var q=block.querySelector('.q'),
        tbody=block.querySelector('tbody'),
        out=block.querySelector('.count'),
        chips=Array.prototype.slice.call(block.querySelectorAll('.chip')),
        rows=Array.prototype.slice.call(tbody.querySelectorAll('tr')),
        noun=block.dataset.noun||'models',
        active='all';

    function apply(){
      var term=(q.value||'').toLowerCase().trim(), n=0;
      rows.forEach(function(tr){
        var okClass = active==='all' || tr.dataset.c===active ||
                      (active==='action' && tr.dataset.action==='1');
        var okTerm = !term || tr.dataset.search.indexOf(term)>-1;
        var show = okClass && okTerm;
        tr.hidden = !show;
        if(show) n++;
      });
      out.textContent = n + ' of ' + rows.length + ' ' + noun;
    }

    q.addEventListener('input', apply);
    chips.forEach(function(c){
      c.addEventListener('click', function(){
        active=c.dataset.f;
        chips.forEach(function(o){o.setAttribute('aria-pressed', o===c?'true':'false');});
        apply();
      });
    });

    // Numeric columns declare data-num so counts sort by value rather than by
    // their comma-formatted string; cells carry data-v with the raw value.
    var ths=Array.prototype.slice.call(block.querySelectorAll('th'));
    ths.forEach(function(th,i){
      th.addEventListener('click', function(){
        var desc = th.getAttribute('aria-sort')==='descending';
        ths.forEach(function(o){o.removeAttribute('aria-sort');});
        th.setAttribute('aria-sort', desc ? 'ascending':'descending');
        var num = th.dataset.num==='1';
        rows.sort(function(a,b){
          var x=a.children[i].dataset.v ?? a.children[i].textContent.trim();
          var y=b.children[i].dataset.v ?? b.children[i].textContent.trim();
          if(num){ x=parseFloat(x)||0; y=parseFloat(y)||0; return desc ? x-y : y-x; }
          return desc ? String(x).localeCompare(y) : String(y).localeCompare(x);
        });
        rows.forEach(function(r){tbody.appendChild(r);});
      });
    });

    apply();
  });
})();
"""


def esc(v):
    return html.escape(str(v if v is not None else ""))


def fmt(n):
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return esc(n)


def _hv(month_entry, *keys):
    """Read a monthly-history figure under whichever key name that month uses.

    The maintenance repository renamed these fields in 2026-06 (`healthy` became
    `ready_passing`, `failing` became `ready_failing`, and so on). Reading only
    the old names silently rendered recent months as zero, which looks like the
    hub collapsed rather than like a schema change — so try each known name and
    fall back to an em dash when the month truly has no such figure.
    """
    totals = month_entry.get("totals") or {}
    for k in keys:
        if k in totals:
            return fmt(totals[k])
    return "—"


def figure_grid(items, extra_class=""):
    """Render a row of headline figures.

    `items` is a list of (value, label, is_alert). Alert cells get an accent rule
    rather than coloured text — see the CSS note.
    """
    cells = "".join(
        f'<div class="fig{" alert" if alert else ""}">'
        f'<span class="n mono">{v}</span><span class="k">{esc(k)}</span></div>'
        for v, k, alert in items
    )
    return f'<div class="figures{extra_class}">{cells}</div>'


def filterable_block(headers, rows_html, chips, placeholder, noun="models"):
    """Wrap a table with its own search box, filter chips and result count.

    Scoped by class inside a `.filterable` container rather than by id, so the
    page can hold more than one of these without the second one going inert.
    """
    ths = "".join(
        f'<th{" data-num=\'1\'" if num else ""}>{esc(label)}</th>'
        for label, num in headers
    )
    chip_html = "".join(
        f'<button class="chip" data-f="{esc(key)}" '
        f'aria-pressed="{"true" if pressed else "false"}">{esc(label)}</button>'
        for key, label, pressed in chips
    )
    return (
        f'<div class="filterable" data-noun="{esc(noun)}">'
        "<div class='controls'>"
        f"<input type='search' class='q' placeholder='{esc(placeholder)}' "
        f"aria-label='{esc(placeholder)}'>"
        f"{chip_html}<span class='count'></span></div>"
        f"<div class='tablewrap'><table><thead><tr>{ths}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div></div>"
    )


def figures_block(cov, mnt, sif_summary=None):
    """The headline row: what a reader should take away in five seconds."""
    s = cov["summary"]
    c = s["counts"]
    w = mnt.get("weekly_summary") or {}
    sif = (sif_summary or {}).get("summary") or {}
    items = [
        (fmt(s["hub_models"]), "ready models", False),
        (f"{s['pct_hub_complete']}%", "precalculated", False),
        (f"{sif.get('pct_available', 0)}%", "with .sif image", False),
        (fmt(w.get("failed", 0)), "failed weekly test", w.get("failed", 0) > 0),
        (fmt(c.get("partial", 0)), "incomplete", c.get("partial", 0) > 0),
        (fmt(c.get("missing", 0)), "no precalculations", c.get("missing", 0) > 0),
        (fmt(sif.get("counts", {}).get("missing", 0)), "no .sif image",
         sif.get("counts", {}).get("missing", 0) > 0),
        (f"{s['stored_gb'] + sif.get('total_gb', 0):,.0f} GB", "stored", False),
    ]
    return figure_grid(items)


def plate_block(cov):
    """The signature: one well per model, ordered so problems cluster first."""
    order = {"partial": 0, "missing": 1, "orphan": 2, "complete": 3}
    models = sorted(
        cov["models"],
        key=lambda m: (order[m["coverage"]], m["status"] != "Ready", m["model_id"]),
    )
    wells = "".join(
        '<span class="well" data-c="{c}" data-ready="{r}" title="{t}"></span>'.format(
            c=m["coverage"],
            r=1 if m["status"] == "Ready" else 0,
            t=esc(
                f'{m["model_id"]} {m["slug"]} — {CLASS_LABEL[m["coverage"]]}'
                f' ({fmt(m["molecules"])} molecules, {m["status"]})'
            ),
        )
        for m in models
    )
    legend = "".join(
        f'<span><span class="sw" style="background:{col}"></span>{esc(lbl)} '
        f'<span class="dim">— {esc(desc)}</span></span>'
        for key, lbl, col, desc in CLASSES
        if cov["summary"]["counts"].get(key)
    )
    return (
        f'<div class="plate">{wells}</div>'
        f'<div class="legend">{legend}'
        f'<span class="fade">Faded wells are models that are not <code>Ready</code>.</span>'
        f"</div>"
    )


def attention_lede(n_gaps, n_failing):
    """Open the section with the counts themselves, not with how they were derived.

    The numbers are the message here. An earlier version opened with "the union of
    both signals", which described the assembly of the list rather than its
    contents and made a reader decode a sentence before learning anything. Saying
    what the rest of the report is for ("context") also tells them what they may
    skip, which matters in a document this long.
    """
    def models(n):
        return "model" if n == 1 else "models"

    gap_clause = (
        f"{fmt(n_gaps)} Ready {models(n_gaps)} "
        f"{'is' if n_gaps == 1 else 'are'} missing precalculations"
    )
    fail_clause = (
        f"{fmt(n_failing)} {models(n_failing)} "
        f"failed {'its' if n_failing == 1 else 'their'} last maintenance test"
    )

    if n_gaps and n_failing:
        # "26 Ready models ... and 2 failed ..." — the noun is already established
        # by the first clause, so repeating it just adds a word.
        body = (
            f"{gap_clause} and {fmt(n_failing)} failed "
            f"{'its' if n_failing == 1 else 'their'} last maintenance test."
        )
    elif n_gaps:
        body = f"{gap_clause}. Nothing failed its last maintenance test."
    elif n_failing:
        body = (
            f"{fail_clause[0].upper()}{fail_clause[1:]}. "
            "Every Ready model has a full set of precalculations."
        )
    else:
        return (
            "<p class='lede'>Nothing needs attention: every Ready model has a full "
            "set of precalculations, and none failed its last maintenance test.</p>"
        )
    return f"<p class='lede'>{body} Everything else in this report is context.</p>"


def attention_block(cov, mnt):
    """Everything a human might need to act on, gathered in one place.

    Monitoring reports fail when the reader has to assemble the to-do list
    themselves, so the two independent signals — a failing test and a coverage
    gap on a Ready model — are surfaced together above all the detail.

    Sub-headings keep the same wording whether or not there is anything to show,
    so the section has a stable shape from week to week; only the count in
    brackets appears or disappears.
    """
    failing = (mnt.get("reports", {}).get("failing_models") or {}).get("rows", [])
    gaps = [
        m for m in cov["models"]
        if m["status"] == "Ready" and m["coverage"] in ("missing", "partial")
    ]
    parts = [attention_lede(len(gaps), len(failing))]

    if failing:
        rows = "".join(
            "<tr><td class='mono'><a href='https://github.com/ersilia-os/{m}'>{m}</a></td>"
            "<td>{s}</td><td><span class='pill'>{st}</span></td>"
            "<td class='mono'>{d}</td></tr>".format(
                m=esc(r.get("model", "")), s=esc(r.get("slug", "")),
                st=esc(r.get("status", "")), d=esc(r.get("last_test_date", "")),
            )
            for r in failing
        )
        parts.append(
            f"<h3>Failed their last maintenance test ({len(failing)})</h3>"
            "<div class='tablewrap'><table><thead><tr><th>Model</th><th>Slug</th>"
            "<th>Status</th><th>Last test</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
            "<p class='lede'>To see which checks failed inside a model, run "
            "<code>/failing-models-check</code>, then <code>/model-fixing</code>.</p>"
        )
    else:
        parts.append(
            "<h3>Failed their last maintenance test</h3>"
            "<div class='empty'>Nothing failed its last maintenance test.</div>"
        )

    if gaps:
        rows = "".join(
            "<tr><td class='mono'><a href='https://github.com/ersilia-os/{m}'>{m}</a></td>"
            "<td>{s}</td><td><span class='badge' style='background:{col}'>{lbl}</span></td>"
            "<td class='num mono'>{mol}</td><td>{task}</td><td>{area}</td></tr>".format(
                m=esc(m["model_id"]), s=esc(m["slug"]),
                col=CLASS_COLOR[m["coverage"]], lbl=esc(CLASS_LABEL[m["coverage"]]),
                mol=fmt(m["molecules"]), task=esc(m["subtask"] or m["task"]),
                area=esc(m["biomedical_area"]),
            )
            for m in gaps
        )
        parts.append(
            f"<h3>No precalculations ({len(gaps)})</h3>"
            "<div class='tablewrap'><table><thead><tr><th>Model</th><th>Slug</th>"
            "<th>Coverage</th><th>Molecules</th><th>Subtask</th>"
            "<th>Biomedical area</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        )
    else:
        parts.append(
            "<h3>No precalculations</h3><div class='empty'>Every Ready model has a "
            "full set of precalculations.</div>"
        )
    return "".join(parts)


def weekly_block(mnt):
    rep = (mnt.get("reports", {}) or {}).get("weekly_model_testing")
    if not rep:
        return "<div class='empty'>The weekly testing report could not be fetched.</div>"
    w = mnt.get("weekly_summary", {})
    rows = "".join(
        "<tr><td class='mono'><a href='https://github.com/ersilia-os/{m}'>{m}</a></td>"
        "<td>{s}</td><td>{t}</td><td class='mono'>{d}</td></tr>".format(
            m=esc(r.get("repository_name", "")), s=esc(r.get("slug", "")),
            t=esc(r.get("test", "")), d=esc(r.get("test_date", "")),
        )
        for r in rep["rows"]
    )
    return (
        f"<p class='lede'>{w.get('tested', 0)} models were selected for the weekly "
        f"shallow test: {w.get('passed', 0)} passed, {w.get('failed', 0)} failed. "
        f"Report generated {esc(rep.get('generated'))}. "
        f"<a href='{esc(rep['url'])}'>Source</a></p>"
        "<div class='tablewrap'><table><thead><tr><th>Model</th><th>Slug</th>"
        "<th>Test</th><th>Tested at</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )


def updated_block(mnt):
    rep = (mnt.get("reports", {}) or {}).get("updated_models")
    if not rep or not rep["rows"]:
        return ""
    rows = "".join(
        "<tr><td class='mono'><a href='https://github.com/ersilia-os/{m}'>{m}</a></td>"
        "<td>{s}</td><td><span class='pill'>{st}</span></td><td class='mono'>{p}</td>"
        "<td>{o}</td><td class='mono'>{u}</td></tr>".format(
            m=esc(r.get("model", "")), s=esc(r.get("slug", "")),
            st=esc(r.get("status", "")), p=esc(r.get("last_packaging_date", "")),
            o=esc(r.get("last_test_outcome", "")), u=esc(r.get("source_updated_at", "")),
        )
        for r in rep["rows"]
    )
    return (
        f"<h3>Upstream source updated since packaging ({len(rep['rows'])})</h3>"
        "<p class='lede'>The original authors changed their code after we last "
        "packaged the model. Not a failure, but a signal the model may be behind "
        "upstream.</p>"
        "<div class='tablewrap'><table><thead><tr><th>Model</th><th>Slug</th>"
        "<th>Status</th><th>Packaged</th><th>Last test</th><th>Source updated</th>"
        f"</tr></thead><tbody>{rows}</tbody></table></div>"
    )


def monthly_block(mnt):
    snap = mnt.get("monthly_snapshot") or {}
    hist = mnt.get("monthly_history") or []
    parts = []
    if snap:
        month = snap.get("month", "")
        keys = [
            ("total_models", "total models"),
            ("ready_passing", "ready — passing"),
            ("ready_not_yet_tested", "ready — not tested"),
            ("ready_failing", "ready — failing"),
            ("archived", "archived"),
            ("non_archived_with_open_issues", "with open issues"),
        ]
        cells = "".join(
            f'<div class="fig"><span class="n mono">{fmt(snap[k])}</span>'
            f'<span class="k">{esc(lbl)}</span></div>'
            for k, lbl in keys if k in snap
        )
        parts.append(
            f"<h3>Snapshot — {esc(month)}</h3><div class='figures six'>{cells}</div>"
        )
    if hist:
        rows = "".join(
            "<tr><td class='mono'>{m}</td><td class='num mono'>{t}</td>"
            "<td class='num mono'>{p}</td><td class='num mono'>{f}</td>"
            "<td class='num mono'>{n}</td><td class='num mono'>{i}</td>"
            "<td class='num mono'>{a}</td></tr>".format(
                m=esc(h.get("month", "")),
                t=_hv(h, "total_models"),
                p=_hv(h, "ready_passing", "healthy"),
                f=_hv(h, "ready_failing", "failing"),
                n=_hv(h, "ready_not_tested", "never_tested"),
                i=_hv(h, "with_open_issues"),
                a=fmt(len(h.get("added_models") or [])),
            )
            for h in hist
        )
        parts.append(
            f"<h3>Month by month ({len(hist)} months on record)</h3>"
            "<p class='lede'>The maintenance repository renamed these fields part-way "
            "through the series, so both namings are read here. An em dash means the "
            "month genuinely does not record that figure, rather than a count of zero."
            "</p>"
            "<div class='tablewrap'><table><thead><tr><th>Month</th><th>Total</th>"
            "<th>Passing</th><th>Failing</th><th>Not tested</th><th>Open issues</th>"
            f"<th>Added</th></tr></thead><tbody>{rows}</tbody></table></div>"
        )
    return "".join(parts) or "<div class='empty'>No monthly data available.</div>"


def plots_block(mnt):
    plots = mnt.get("plots") or {}
    if not plots:
        return ""
    captions = {
        "health_and_testing": "Ready models over time: passing, not yet tested, failing.",
        "issues_and_added": "Open issues and newly packaged models per month.",
        "distributions_tasks_source": "Distribution of models by task and by source type.",
    }
    figs = "".join(
        f'<figure><img src="{p["data_uri"]}" alt="{esc(captions.get(name, name))}">'
        f'<figcaption>{esc(captions.get(name, name))} '
        f'<span class="mono">{name}.png</span></figcaption></figure>'
        for name, p in plots.items()
    )
    return (
        "<section><h2>Monthly trends</h2>"
        "<p class='lede'>Plots as published by the maintenance repository, "
        "embedded here so this file stands alone.</p>"
        f"{figs}</section>"
    )


def coverage_table(cov):
    rows = []
    for m in cov["models"]:
        action = 1 if (m["status"] == "Ready" and m["coverage"] in ("missing", "partial")) else 0
        search = " ".join(
            str(x).lower() for x in
            [m["model_id"], m["slug"], m["title"], m["status"], m["task"],
             m["subtask"], m["tag"], m["biomedical_area"], CLASS_LABEL[m["coverage"]]]
        )
        versions = ", ".join(v["version"] or "?" for v in m["versions"]) or "—"
        rows.append(
            "<tr data-c='{c}' data-action='{act}' data-search='{q}'>"
            "<td class='mono' data-v='{mid}'><a href='https://github.com/ersilia-os/{mid}'>{mid}</a></td>"
            "<td data-v='{slug}'>{slug}</td>"
            "<td data-v='{c}'><span class='badge' style='background:{col}'>{lbl}</span></td>"
            "<td class='num mono' data-v='{mol_raw}'>{mol}</td>"
            "<td data-v='{pct}'><div class='bar'><i style='width:{pct}%'></i></div></td>"
            "<td data-v='{st}'><span class='pill'>{st}</span></td>"
            "<td data-v='{sub}'>{sub}</td>"
            "<td class='mono' data-v='{ver}'>{ver}</td>"
            "<td class='num mono' data-v='{gb_raw}'>{gb}</td>"
            "</tr>".format(
                c=m["coverage"], act=action, q=esc(search), mid=esc(m["model_id"]),
                slug=esc(m["slug"] or "—"), col=CLASS_COLOR[m["coverage"]],
                lbl=esc(CLASS_LABEL[m["coverage"]]), mol=fmt(m["molecules"]),
                mol_raw=m["molecules"], pct=m["pct"], st=esc(m["status"] or "—"),
                sub=esc(m["subtask"] or m["task"] or "—"), ver=esc(versions),
                gb=f'{m["total_gb"]:,.1f}' if m["total_gb"] else "—",
                gb_raw=m["total_gb"],
            )
        )
    counts = cov["summary"]["counts"]
    chips = [("all", "All", True)]
    for key, lbl, _, _ in CLASSES:
        if counts.get(key):
            chips.append((key, f"{lbl} ({counts[key]})", False))
    headers = [
        ("Model", False), ("Slug", False), ("Coverage", False),
        ("Molecules", True), ("Of full set", True), ("Status", False),
        ("Subtask", False), ("Versions", False), ("GB", True),
    ]
    return filterable_block(
        headers, "".join(rows), chips,
        "Search model, slug, task, area…",
    )


def sif_section(sif):
    """The Singularity image section: summary figures, then the searchable list.

    Kept structurally parallel to the isaura section — same figure grid, same
    table controls, same colour roles — because the two answer the same shape of
    question about two different artefacts, and a reader should not have to learn
    the layout twice.
    """
    if not sif:
        return (
            "<section><h2>Singularity images</h2>"
            "<div class='empty'>No image inventory was collected. Run "
            "<code>fetch_sif.py</code> and pass <code>--sif</code> to include this "
            "section.</div></section>"
        )
    s = sif["summary"]
    c = s.get("counts", {})
    largest = s.get("largest") or {}
    items = [
        (fmt(s["hub_models"]), "ready models", False),
        (f"{s['pct_available']}%", "with an image", False),
        (fmt(c.get("available", 0)), "available", False),
        (fmt(c.get("missing", 0)), "no image", c.get("missing", 0) > 0),
        (fmt(s["images_total"]), "images in bucket", False),
        (f"{s['total_gb']:,.0f} GB", "stored", False),
        (fmt(s["multi_image_models"]), "multi-version", False),
        (fmt(c.get("extra", 0)), "not in ready list", False),
    ]

    rows = []
    for m in sif["models"]:
        search = " ".join(
            str(x).lower() for x in
            [m["model_id"], m["slug"], m["status"], m["task"], m["subtask"],
             m["biomedical_area"], SIF_LABEL[m["sif"]]]
        )
        versions = ", ".join(m["versions"]) or "—"
        rows.append(
            "<tr data-c='{c}' data-action='{act}' data-search='{q}'>"
            "<td class='mono' data-v='{mid}'>"
            "<a href='https://github.com/ersilia-os/{mid}'>{mid}</a></td>"
            "<td data-v='{slug}'>{slug}</td>"
            "<td data-v='{c}'><span class='badge' style='background:{col}'>{lbl}</span></td>"
            "<td class='mono' data-v='{ver}'>{ver}</td>"
            "<td class='num mono' data-v='{lgb_raw}'>{lgb}</td>"
            "<td class='mono' data-v='{lm}'>{lm}</td>"
            "<td data-v='{sub}'>{sub}</td>"
            "</tr>".format(
                c=m["sif"], act=1 if m["sif"] == "missing" else 0, q=esc(search),
                mid=esc(m["model_id"]), slug=esc(m["slug"] or "—"),
                col=SIF_COLOR[m["sif"]], lbl=esc(SIF_LABEL[m["sif"]]),
                ver=esc(versions),
                lgb=f'{m["latest_gb"]:,.2f}' if m["latest_gb"] else "—",
                lgb_raw=m["latest_gb"],
                lm=esc((m["last_modified"] or "—")[:10]),
                sub=esc(m["subtask"] or m["task"] or "—"),
            )
        )

    chips = [("all", "All", True)]
    for key, lbl, _, _ in SIF_CLASSES:
        if c.get(key):
            chips.append((key, f"{lbl} ({c[key]})", False))
    # No Total-GB column: it equals the latest image's size for all but the 19
    # multi-version models, and total storage is already in the figures above.
    headers = [
        ("Model", False), ("Slug", False), ("Image", False), ("Versions", False),
        ("Size GB", True), ("Built", False), ("Subtask", False),
    ]

    unexpected = s.get("unexpected_keys") or []
    warn = (
        "<div class='note'><strong>Unexpected keys in the bucket</strong>"
        + ", ".join(f"<code>{esc(k)}</code>" for k in unexpected[:8])
        + ". These do not match <code>&lt;model_id&gt;_&lt;version&gt;.sif</code>, so "
        "they are not counted — the naming convention may have changed.</div>"
        if unexpected else ""
    )
    biggest = (
        f" The largest single image is <code>{esc(largest.get('model_id'))}</code> at "
        f"{largest.get('gb', 0):,.1f} GB."
        if largest else ""
    )

    return (
        "<section><h2>Singularity images</h2>"
        f"<p class='lede'>Whether a built <code>.sif</code> image exists for each Ready "
        f"model in <code>s3://{esc(sif['bucket'])}</code>. Singularity is how a model "
        f"runs on HPC and on hosts without Docker, so a Ready model with no image cannot "
        f"be deployed there at all.{biggest}</p>"
        f"{figure_grid(items)}"
        f"{warn}"
        + filterable_block(
            headers, "".join(rows), chips, "Search model, slug, task, area…",
            noun="models",
        )
        + "</section>"
    )


def build(cov, mnt, title, sif=None):
    s = cov["summary"]
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    missing = mnt.get("missing_sources") or []
    miss_html = (
        "<div class='note'><strong>Some sources were unavailable</strong>"
        + ", ".join(f"<code>{esc(p)}</code>" for p in missing)
        + ". The sections that depend on them are incomplete.</div>"
        if missing else ""
    )
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head><body>

<header class="top"><div class="wrap">
  <p class="eyebrow">Ersilia Model Hub · monitoring</p>
  <h1>{esc(title)}</h1>
  <p class="sub">Maintenance test outcomes from
    <a href="{esc(mnt.get('repo_url', ''))}">ersilia-maintenance</a>,
    and precalculation coverage in the
    <code class="mono">{esc(cov.get('bucket'))}</code> isaura bucket measured against the
    full reference collection of <span class="mono">{fmt(s['full_count'])}</span> molecules.</p>
</div></header>

<div class="wrap">
  {figures_block(cov, mnt, sif)}
  {miss_html}

  <section>
    <h2>Needs attention</h2>
    {attention_block(cov, mnt)}
  </section>

  <section>
    <h2>Coverage plate</h2>
    <p class="lede">One well per model, problems first. Hover a well for its model id
      and molecule count.</p>
    {plate_block(cov)}
  </section>

  <section>
    <h2>Precalculation coverage</h2>
    <p class="lede">Every model the hub search returns, joined against what isaura
      actually stores. {fmt(s['isaura_unique_models'])} models hold data across
      {fmt(s['isaura_entries'])} stored versions
      ({s['multi_version_models']} models have more than one), totalling
      {s['stored_gb']:,.0f} GB.</p>
    {coverage_table(cov)}
  </section>

  {sif_section(sif)}

  <section>
    <h2>This week in maintenance</h2>
    {weekly_block(mnt)}
    {updated_block(mnt)}
  </section>

  <section>
    <h2>Monthly health</h2>
    {monthly_block(mnt)}
  </section>

  {plots_block(mnt)}

  <footer>
    <p>Generated {gen} by <code>model-monitoring</code>. Self-contained: no external
      data is loaded when this file is opened.</p>
    <ul>
      <li>Coverage measured {esc(cov.get('generated_at_utc'))}; isaura inventory
        taken {esc(cov.get('isaura_generated_at_utc'))}.</li>
      <li>Maintenance reports read from
        <a href="{esc(mnt.get('repo_url', ''))}">{esc(mnt.get('repo', ''))}</a>
        at {esc(mnt.get('generated_at_utc'))}.</li>
      <li>Full coverage is defined as {fmt(s['full_count'])} molecules — the size of the
        isaura reference collection.</li>
    </ul>
  </footer>
</div>
<script>{JS}</script>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--coverage", required=True)
    ap.add_argument("--maintenance", required=True)
    ap.add_argument("--sif", help="sif.json from fetch_sif.py. Omit to render the "
                                  "report without the Singularity section.")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="Model Hub monitoring report")
    args = ap.parse_args()

    cov = json.load(open(args.coverage))
    mnt = json.load(open(args.maintenance))
    sif = json.load(open(args.sif)) if args.sif else None
    html_text = build(cov, mnt, args.title, sif)
    with open(args.out, "w") as f:
        f.write(html_text)
    print(
        f"[report] wrote {args.out} ({len(html_text) / 1024:,.0f} KB)",
        flush=True,
    )


if __name__ == "__main__":
    main()
