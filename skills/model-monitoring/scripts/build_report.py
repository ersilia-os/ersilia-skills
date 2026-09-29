"""Render the model-monitoring report body from the data payloads.

Takes coverage.json (fetch_coverage.py), maintenance.json (fetch_maintenance.py)
and sif.json (fetch_sif.py) and writes the report as a `dashboard`-archetype page
built from the Ersilia design system's components.

**This script does not style the page.** It emits structure and content; the
`html-formatting` skill owns the look. Run its assembler afterwards to inline the
design tokens, set the favicon and append the credit footer:

    python build_report.py --coverage c.json --maintenance m.json --sif s.json \
        --out /tmp/body.html --title "Model Hub monitoring" \
        --snapshot "Snapshot 19 Aug 2026"

    python ~/.claude/skills/html-formatting/scripts/apply_theme.py \
        --mode retrofit /tmp/body.html --out report.html \
        --title "Model Hub monitoring" \
        --source-url "https://github.com/ersilia-os/ersilia-skills" --favicon auto

    python ~/.claude/skills/html-formatting/scripts/check_html.py report.html \
        --date YYYY-MM-DD

Design notes, so future edits stay coherent rather than accreting:

  * **No palette lives here.** Every colour, font and radius is a design-system
    token (`var(--…)`). A hard-coded hex is how a page quietly stops being
    Ersilia, and check_html.py flags it. Coverage classes map onto the semantic
    state tokens (--good/--warn/--bad) because coverage genuinely is a state.
  * The signature element is the **coverage plate** — one cell per model laid out
    as a dense grid, coloured by coverage class. A microplate is native
    vernacular in drug discovery, and it is the only device that makes ~220
    models legible in a single glance. Everything else stays quiet so the plate
    carries the visual weight.
  * Colour encodes coverage class and nothing else, and the Singularity section
    reuses the same three tokens in the same roles, so the mapping is learnt once.
  * **Check a new class name against ersilia.css before using it.** Three bugs
    here came from collisions (`.note`, `.sw`, `.lede`) where the page still
    rendered, just wrongly. Deliberate extensions of a house class are marked as
    such in CSS.
  * The output is self-contained with zero network requests, because these reports
    get archived and forwarded and one that loses its styling a month later is
    worse than no file.
"""

import argparse
import html
import json

# Coverage classes in triage order, each with its label and its design-system
# token. Coverage is a genuine *state*, which is exactly what --good/--warn/--bad
# are reserved for, so the mapping needs no invented colours. --purple is a data
# hue rather than a state token, used for the one class that is not a state at
# all: an artefact stored for a model outside the measured population.
CLASSES = [
    ("partial", "Incomplete", "var(--warn)",
     "Some predictions stored, but fewer than the full collection"),
    ("missing", "Not started", "var(--bad)",
     "The hub lists this model, isaura holds nothing for it"),
    ("orphan", "Not Ready", "var(--purple)",
     "isaura holds data for a model outside the Ready population"),
    ("complete", "Complete", "var(--good)",
     "Every reference molecule has a stored prediction"),
]
CLASS_COLOR = {k: c for k, _, c, _ in CLASSES}
CLASS_LABEL = {k: lbl for k, lbl, _, _ in CLASSES}

# Singularity availability, deliberately reusing the same three tokens in the same
# roles as the isaura classes, so a reader who has learnt the colours in one
# section reads the other for free.
SIF_CLASSES = [
    ("missing", "No image", "var(--bad)",
     "The model is Ready, but no .sif image has been built"),
    ("extra", "Not in Ready list", "var(--purple)",
     "An image exists for a model that is not currently Ready"),
    ("available", "Available", "var(--good)",
     "A built .sif image is in the bucket"),
]
SIF_COLOR = {k: c for k, _, c, _ in SIF_CLASSES}
SIF_LABEL = {k: lbl for k, lbl, _, _ in SIF_CLASSES}

# Page-specific structure only. Every colour, font and radius comes from the
# Ersilia design system (`html-formatting/assets/ersilia.css`, inlined by
# apply_theme.py), so there is deliberately no palette here: this skill owns the
# report's structure and content, html-formatting owns how it looks. If a colour
# is needed, reach for a token — never a hex, or check_html.py will flag it and
# the page will drift from the house style.
CSS = """
/* --- the coverage plate (the report's signature element) --------------- */
/* One well per model. Wells encode a state, so they take the semantic state
   tokens; --purple marks the one class that is not a state but a population
   mismatch (an artefact stored for a model that is no longer served). */
.plate{display:flex;flex-wrap:wrap;gap:3px}
.well{width:14px;height:14px;border-radius:3px;background:var(--surface-2);
  box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--plum) 12%, transparent)}
.well[data-c=complete]{background:var(--good)}
.well[data-c=partial]{background:var(--warn)}
.well[data-c=missing]{background:var(--bad)}
.well[data-c=orphan]{background:var(--purple)}
.well[data-ready="0"]{opacity:.4}
.legend{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
  gap:6px 24px;margin:14px 0 0;font-size:11.5px;color:var(--muted)}
/* `.swatch`, not `.sw`: the design system's `.sw` is the switch component — a
   34x19 pill with a white knob — so every legend key rendered as a tiny toggle.
   Check any new utility name against ersilia.css before using it. */
.legend .swatch{width:10px;height:10px;border-radius:3px;display:inline-block;
  margin-right:7px;vertical-align:-1px}
.legend .fade{grid-column:1/-1}

/* --- intro prose ------------------------------------------------------- */
/* The starters write this inline as `class="muted"` plus a max-width; naming it
   keeps the call sites clean. Measure is capped because a section intro running
   the full 1160px container is hard to read. */
.lede{color:var(--muted);max-width:78ch;margin:.4em 0 14px}
.brandhead .lede{max-width:62ch}

/* --- KPI row ----------------------------------------------------------- */
/* Fixed four columns rather than auto-fit: the headline set is eight tiles, and
   letting the browser fit seven per row strands the last one beside a gap. */
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:18px 0 0}
@media (max-width:860px){.stats{grid-template-columns:repeat(2,1fr)}}
.stats.six{grid-template-columns:repeat(3,1fr)}
@media (max-width:860px){.stats.six{grid-template-columns:repeat(2,1fr)}}
/* Emphasis by accent rule, not by colouring the numeral: a large figure in the
   alert hue is harder to read than an ink one, and the rule is louder anyway. */
.stat.alert{border-top:2px solid var(--bad)}

/* --- table extras not in the design system ----------------------------- */
/* Two-word status labels wrap inside a narrow cell, turning every badge into a
   two-line pill and padding the column out. Structure only — the tint and text
   colour still come from the design system's .badge. */
.badge{white-space:nowrap}
th[aria-sort]{color:var(--ink)}
table.data th{cursor:pointer;white-space:nowrap}
table.data td{vertical-align:top}
.meter{height:6px;border-radius:999px;background:var(--surface-2);
  overflow:hidden;min-width:64px}
.meter>i{display:block;height:100%;background:var(--good)}

/* --- controls ---------------------------------------------------------- */
.controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 12px}
.controls input[type=search]{font-family:var(--sans);font-size:12px;
  padding:6px 11px;border:1px solid var(--border);border-radius:var(--radius-sm);
  min-width:220px;background:var(--surface);color:var(--ink)}
.count{color:var(--faint);font-size:11.5px;margin-left:auto}

/* --- figures & notes --------------------------------------------------- */
figure{margin:0 0 20px}
figure img{width:100%;height:auto;border:1px solid var(--border);
  border-radius:var(--radius-sm);background:var(--surface)}
figcaption{font-size:11.5px;color:var(--muted);margin-top:6px}
.note{border-left:2px solid var(--warn);background:var(--surface);
  padding:10px 14px;margin:16px 0;font-size:12px;border-radius:var(--radius-sm)}
.note strong{display:block;margin-bottom:2px;color:var(--ink)}
.empty{padding:14px;color:var(--muted);font-size:12px;background:var(--surface);
  border:1px solid var(--border);border-radius:var(--radius-sm)}
.snap{display:inline-block;font-family:var(--mono);font-size:10.5px;
  padding:2px 9px;border-radius:999px;background:var(--surface-2);
  color:var(--muted);border:1px solid var(--border)}
details.methods{margin:18px 0 0;font-size:12px}
details.methods summary{cursor:pointer;color:var(--brand);font-weight:450}
details.methods div{margin-top:10px;color:var(--muted);max-width:80ch}
details.methods p{margin:0 0 8px}
@media print{.controls{display:none}}
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
    """Render a KPI row using the design system's `.stat` tiles.

    `items` is a list of (value, label, is_alert). Alert tiles get an accent rule
    rather than a coloured numeral — see the CSS note.
    """
    cells = "".join(
        f'<div class="stat{" alert" if alert else ""}">'
        f'<div class="k">{esc(k)}</div><div class="v">{v}</div></div>'
        for v, k, alert in items
    )
    return f'<div class="stats{extra_class}">{cells}</div>'


def badge(label, color, extra=""):
    """A design-system badge tinted by a token via the `--c` custom property."""
    return f'<span class="badge{extra}" style="--c:{color}">{esc(label)}</span>'


def filterable_block(headers, rows_html, chips, placeholder, noun="models"):
    """Wrap a `table.data` with its own search box, filter chips and result count.

    Scoped by class inside a `.filterable` container rather than by id, so the
    page can hold more than one of these without the second one going inert.
    Column headers carry `title=` so the meaning of a column is one hover away
    rather than spelled out in prose above the table.
    """
    ths = "".join(
        "<th{num}{tip}>{label}</th>".format(
            num=" data-num='1'" if num else "",
            tip=f" title='{esc(tip)}'" if tip else "",
            label=esc(label),
        )
        for label, num, tip in headers
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
        f"<div class='scrollwrap'><table class='data'><thead><tr>{ths}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div></div>"
    )


def data_table(headers, rows_html):
    """A plain house data table, for the short tables that need no controls."""
    ths = "".join(f"<th>{esc(h)}</th>" for h in headers)
    return (
        f"<div class='scrollwrap'><table class='data'><thead><tr>{ths}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table></div>"
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
        # Two different buckets, so the label says so: an unqualified "stored"
        # beside per-section GB figures invites the reader to match it to one of
        # them and find it does not add up.
        (f"{s['stored_gb'] + sif.get('total_gb', 0):,.0f} GB",
         "stored, both buckets", False),
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
        f'<span><span class="swatch" style="background:{col}"></span>{esc(lbl)} '
        f"— {esc(desc)}</span>"
        for key, lbl, col, desc in CLASSES
        if cov["summary"]["counts"].get(key)
    )
    return (
        f'<div class="plate">{wells}</div>'
        f'<div class="legend">{legend}'
        '<span class="fade">Faded wells sit outside the Ready population.</span>'
        "</div>"
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
                st=esc(r.get("status", "")), d=esc((r.get("last_test_date") or "")[:10]),
            )
            for r in failing
        )
        parts.append(
            f"<h3>Failed their last maintenance test ({len(failing)})</h3>"
            + data_table(["Model", "Slug", "Status", "Last test"], rows)
            + "<p class='lede'>To see which checks failed inside a model, run "
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
            "<td>{s}</td><td>{bdg}</td>"
            "<td class='num'>{mol}</td><td>{task}</td><td>{area}</td></tr>".format(
                m=esc(m["model_id"]), s=esc(m["slug"]),
                bdg=badge(CLASS_LABEL[m["coverage"]], CLASS_COLOR[m["coverage"]]),
                mol=fmt(m["molecules"]), task=esc(m["subtask"] or m["task"]),
                area=esc(m["biomedical_area"]),
            )
            for m in gaps
        )
        parts.append(
            f"<h3>No precalculations ({len(gaps)})</h3>"
            + data_table(
                ["Model", "Slug", "Coverage", "Molecules", "Subtask",
                 "Biomedical area"], rows)
        )
    else:
        parts.append(
            "<h3>No precalculations</h3><div class='empty'>Every Ready model has a "
            "full set of precalculations.</div>"
        )
    return "".join(parts)


def outcome_badge(raw):
    """Turn the maintenance reports' emoji outcome into a house badge.

    The upstream markdown encodes results as ✅ / 🚨 / ❓. Those are status markers
    rather than decoration, so they would be permissible — but a badge carries the
    same meaning in the page's own vocabulary, reads at a glance in a dense table,
    and says the word rather than relying on the reader knowing the icon.
    """
    text = raw or ""
    if "✅" in text:
        return badge("passed", "var(--good)")
    if "🚨" in text:
        return badge("failed", "var(--bad)")
    if "❓" in text or not text.strip():
        return badge("unknown", "var(--egray)")
    return esc(text)


def weekly_block(mnt):
    rep = (mnt.get("reports", {}) or {}).get("weekly_model_testing")
    if not rep:
        return "<div class='empty'>The weekly testing report could not be fetched.</div>"
    w = mnt.get("weekly_summary", {})
    rows = "".join(
        "<tr><td class='mono'><a href='https://github.com/ersilia-os/{m}'>{m}</a></td>"
        "<td>{s}</td><td>{t}</td><td class='mono'>{d}</td></tr>".format(
            m=esc(r.get("repository_name", "")), s=esc(r.get("slug", "")),
            t=outcome_badge(r.get("test", "")),
            d=esc((r.get("test_date") or "")[:10]),
        )
        for r in rep["rows"]
    )
    return (
        f"<p class='lede'>{w.get('tested', 0)} models were selected for the weekly "
        f"shallow test: {w.get('passed', 0)} passed, {w.get('failed', 0)} failed. "
        f"Reported {esc((rep.get('generated') or '')[:10])}. "
        f"<a href='{esc(rep['url'])}'>Source</a></p>"
        + data_table(["Model", "Slug", "Test", "Tested"], rows)
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
            st=esc(r.get("status", "")),
            p=esc((r.get("last_packaging_date") or "—")[:10]),
            o=outcome_badge(r.get("last_test_outcome", "")),
            u=esc((r.get("source_updated_at") or "")[:10]),
        )
        for r in rep["rows"]
    )
    return (
        f"<h3>Upstream source updated since packaging ({len(rep['rows'])})</h3>"
        "<p class='lede'>The original authors changed their code after we last "
        "packaged the model. Not a failure, but a signal the model may be behind "
        "upstream.</p>"
        + data_table(
            ["Model", "Slug", "Status", "Packaged", "Last test", "Source updated"],
            rows)
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
        parts.append(
            f"<h3>Snapshot — {esc(month)}</h3>"
            + figure_grid(
                [(fmt(snap[k]), lbl, False) for k, lbl in keys if k in snap],
                extra_class=" six",
            )
        )
    if hist:
        rows = "".join(
            "<tr><td class='mono'>{m}</td><td class='num'>{t}</td>"
            "<td class='num'>{p}</td><td class='num'>{f}</td>"
            "<td class='num'>{n}</td><td class='num'>{i}</td>"
            "<td class='num'>{a}</td></tr>".format(
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
            "<p class='lede'>An em dash means the month does not record that figure, "
            "rather than a count of zero.</p>"
            + data_table(
                ["Month", "Total", "Passing", "Failing", "Not tested",
                 "Open issues", "Added"], rows)
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
        "<section class='section'><h2>Monthly trends</h2>"
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
            "<td data-v='{c}'>{bdg}</td>"
            "<td class='num' data-v='{mol_raw}'>{mol}</td>"
            "<td data-v='{pct}'><div class='meter'><i style='width:{pct}%'></i></div></td>"
            "<td data-v='{sub}'>{sub}</td>"
            "<td class='mono' data-v='{ver}'>{ver}</td>"
            "<td class='num' data-v='{gb_raw}'>{gb}</td>"
            "</tr>".format(
                c=m["coverage"], act=action, q=esc(search), mid=esc(m["model_id"]),
                slug=esc(m["slug"] or "—"),
                bdg=badge(CLASS_LABEL[m["coverage"]], CLASS_COLOR[m["coverage"]]),
                mol=fmt(m["molecules"]), mol_raw=m["molecules"], pct=m["pct"],
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
    # Status is dropped as a column: the population is Ready by definition, so it
    # read the same on every row and carried no information.
    headers = [
        ("Model", False, "Ersilia model identifier; links to its GitHub repository"),
        ("Slug", False, "Human-readable model name"),
        ("Coverage", False, "Whether the full set of predictions is stored"),
        ("Molecules", True,
         f"Stored predictions, out of {fmt(cov['summary']['full_count'])}"),
        ("Of full set", True, "Share of the reference collection covered"),
        ("Subtask", False, "What the model does"),
        ("Versions", False, "Model versions stored in isaura"),
        ("GB", True, "Storage used across all stored versions"),
    ]
    return filterable_block(
        headers, "".join(rows), chips, "Search model, slug, task, area…",
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
            "<td data-v='{c}'>{bdg}</td>"
            "<td class='mono' data-v='{ver}'>{ver}</td>"
            "<td class='num' data-v='{lgb_raw}'>{lgb}</td>"
            "<td class='mono' data-v='{lm}'>{lm}</td>"
            "<td data-v='{sub}'>{sub}</td>"
            "</tr>".format(
                c=m["sif"], act=1 if m["sif"] == "missing" else 0, q=esc(search),
                mid=esc(m["model_id"]), slug=esc(m["slug"] or "—"),
                bdg=badge(SIF_LABEL[m["sif"]], SIF_COLOR[m["sif"]]),
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
        ("Model", False, "Ersilia model identifier; links to its GitHub repository"),
        ("Slug", False, "Human-readable model name"),
        ("Image", False, "Whether a built .sif image exists in the bucket"),
        ("Versions", False, "Image versions present in the bucket"),
        ("Size GB", True, "Size of the newest image"),
        ("Built", False, "When the newest image was uploaded"),
        ("Subtask", False, "What the model does"),
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
        "<section class='section'><h2>Singularity images</h2>"
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


def methods_block(cov, mnt, sif):
    """The derivations, one click deep.

    Every headline number here is derived rather than read off a source, and a few
    rest on conventions a reader could not guess (what counts as "full", which
    population the percentages divide by, that one upstream schema was renamed
    mid-series). The house style keeps that rigour on the page but off the surface,
    so it lives behind a disclosure rather than in the lede.
    """
    s = cov["summary"]
    sif_line = ""
    if sif:
        ss = sif["summary"]
        sif_line = (
            f"<p><strong>Singularity images.</strong> Objects in "
            f"<code>s3://{esc(sif['bucket'])}</code> named "
            f"<code>&lt;model_id&gt;_&lt;version&gt;.sif</code>, joined to the same "
            f"population. A model counts as covered if any image exists; size and date "
            f"are the newest one. {fmt(ss['images_total'])} images cover "
            f"{fmt(ss['models_with_images'])} models.</p>"
        )
    return (
        "<details class='methods'><summary>How these numbers are derived</summary><div>"
        f"<p><strong>Population.</strong> Every figure divides by the "
        f"{fmt(s['hub_models'])} models the hub search returns with status "
        f"<code>Ready</code>. Archived and in-progress models are excluded: they are not "
        f"served, so a missing artefact for them is not a gap. Artefacts we still store "
        f"for non-Ready models are counted separately and never folded into a coverage "
        f"percentage.</p>"
        f"<p><strong>Precalculation coverage.</strong> A model is complete when it has a "
        f"stored prediction for all {fmt(s['full_count'])} molecules in the isaura "
        f"reference collection — the size of that collection is the definition of "
        f"&ldquo;full&rdquo;. Where a model is stored at several versions, the version "
        f"with the most molecules is the one measured, since the question is whether the "
        f"predictions exist at all.</p>"
        f"{sif_line}"
        "<p><strong>Maintenance.</strong> Read from the published reports in "
        f"<a href='{esc(mnt.get('repo_url', ''))}'>{esc(mnt.get('repo', ''))}</a>, not "
        "recomputed here. The monthly series changed field names part-way through, so "
        "both namings are read; an em dash means a month does not record that figure, "
        "which is not the same as a zero.</p>"
        "<p><strong>Provenance.</strong> isaura inventory taken "
        f"{esc((cov.get('isaura_generated_at_utc') or '')[:19])}; coverage computed "
        f"{esc((cov.get('generated_at_utc') or '')[:19])}; maintenance reports read "
        f"{esc((mnt.get('generated_at_utc') or '')[:19])}. Counts are a snapshot and "
        "will drift as models are packaged and images are built.</p>"
        "</div></details>"
    )


def build(cov, mnt, title, sif=None, snapshot=""):
    """Assemble the report body.

    Emits a `dashboard` archetype page with the page's own structural CSS only —
    apply_theme.py swaps in the canonical Ersilia head (design tokens inlined, SVG
    favicon) and appends the credit footer, so nothing here defines a colour, a
    font or an attribution block.
    """
    s = cov["summary"]
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
<title>{esc(title)}</title>
<style>{CSS}</style>
</head><body>
<div class="dashboard">

  <header class="brandhead">
    <span class="eyebrow brand">Model monitoring · Ersilia Open Source Initiative</span>
    <h1 class="wordmark">Model Hub <em>monitoring</em></h1>
    <p class="lede">Precalculation coverage, Singularity images and maintenance test
      outcomes for the {fmt(s['hub_models'])} models the Hub currently serves.
      <span class="snap">{esc(snapshot)}</span></p>
  </header>

  {figures_block(cov, mnt, sif)}
  {miss_html}
  {methods_block(cov, mnt, sif)}

  <section class="section">
    <h2>Needs attention</h2>
    {attention_block(cov, mnt)}
  </section>

  <section class="section">
    <h2>Precalculation coverage</h2>
    <p class="lede">Every Ready model joined against what isaura actually stores.
      {fmt(s['isaura_unique_models'])} models hold data across
      {fmt(s['isaura_entries'])} stored versions
      ({s['multi_version_models']} have more than one), totalling
      {s['stored_gb']:,.0f} GB. One well per model below, problems first — hover for
      the model id and its molecule count.</p>
    {plate_block(cov)}
    {coverage_table(cov)}
  </section>

  {sif_section(sif)}

  <section class="section">
    <h2>This week in maintenance</h2>
    {weekly_block(mnt)}
    {updated_block(mnt)}
  </section>

  <section class="section">
    <h2>Monthly health</h2>
    {monthly_block(mnt)}
  </section>

  {plots_block(mnt)}

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
    ap.add_argument("--title", default="Model Hub monitoring")
    ap.add_argument("--snapshot", default="",
                    help="Snapshot label shown beside the lede, e.g. "
                         "'Snapshot 19 Aug 2026'. Passed in rather than derived: "
                         "these scripts never call datetime.now() so a rebuild of "
                         "the same data produces the same bytes (repo convention).")
    args = ap.parse_args()

    cov = json.load(open(args.coverage))
    mnt = json.load(open(args.maintenance))
    sif = json.load(open(args.sif)) if args.sif else None
    html_text = build(cov, mnt, args.title, sif, args.snapshot)
    with open(args.out, "w") as f:
        f.write(html_text)
    print(
        f"[report] wrote {args.out} ({len(html_text) / 1024:,.0f} KB)",
        flush=True,
    )


if __name__ == "__main__":
    main()
