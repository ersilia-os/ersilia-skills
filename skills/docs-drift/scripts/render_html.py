"""Render the numbered findings as a self-contained HTML page to share with the team.

Reads `render_report.py` output (`findings_final.json`) and writes one page in the
Ersilia house style: a summary row, filters (severity, where, search) and one table per
Book page or README. The page is complete without JavaScript; the script only filters.

The theme comes from the sibling `html-formatting` skill (`apply_theme.py`, document
archetype). If that skill is not next to this one, the page falls back to a minimal style.

Exit codes: 0 on success, 2 on bad input.

Usage:
    python render_html.py --input /tmp/docs-drift/findings_final.json --out /tmp/docs-drift/docs-drift.html
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from _common import ORG, read_json

THEME = (
    Path(__file__).resolve().parents[2]
    / "html-formatting"
    / "scripts"
    / "apply_theme.py"
)
SOURCE_URL = "https://github.com/ersilia-os/ersilia-skills/tree/main/skills/docs-drift"
RANK = {"high": 0, "medium": 1, "low": 2}
BADGE = {"high": "bad", "medium": "warn", "low": ""}

# Plain names for the checks, as a reader outside the team would describe them.
LABELS = {
    "cli-command": "Command no longer exists",
    "cli-flag": "Option no longer exists",
    "repo-missing": "Repository not found",
    "repo-file-missing": "Linked file moved or deleted",
    "repo-branch-missing": "Linked branch deleted",
    "repo-renamed": "Repository renamed",
    "repo-archived": "Repository archived",
    "python-version": "Python version out of range",
    "summary-missing": "Sidebar entry points nowhere",
    "orphan-page": "Page not in the sidebar",
    "hidden-in-summary": "Hidden page in the sidebar",
    "broken-placeholder": "Broken GitBook link",
    "relative-link": "Broken link between pages",
    "external-link": "Web link broken",
    "judgement": "Text contradicts the code",
}

STYLE = """
<style>
.dd-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:20px 0 8px}
.dd-filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:16px 0 4px}
.dd-filters .group{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.dd-filters .lbl{color:var(--muted);font-size:12px;margin-right:2px}
.dd-filters input[type=search]{flex:1 1 220px;min-width:0;padding:7px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);color:var(--ink);font:inherit}
.dd-chip{font:inherit;font-size:12px;font-weight:450;padding:4px 10px;border-radius:999px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer}
.dd-chip[aria-pressed=true]{color:var(--brand);border-color:color-mix(in srgb,var(--brand) 45%,var(--border));background:color-mix(in srgb,var(--brand) 8%,var(--surface))}
.dd-chip:focus-visible,.dd-filters input:focus-visible{outline:2px solid var(--brand);outline-offset:2px}
.dd-count{color:var(--faint);font-size:12px;margin:6px 0 0}
.dd-group{margin:18px 0 0}
.dd-group h3{font-size:14px;font-weight:600;margin:0 0 6px;display:flex;flex-wrap:wrap;gap:6px;align-items:baseline}
.dd-group h3 a{font-weight:400;font-size:12px;color:var(--muted)}
.dd-table td{vertical-align:top}
.dd-table td.id{white-space:nowrap;font-family:var(--mono);font-size:12px;color:var(--muted)}
.dd-table code{font-family:var(--mono);font-size:11.5px;word-break:break-word;background:var(--surface-2);padding:1px 4px;border-radius:4px}
.dd-table .what{font-weight:500;color:var(--ink);display:block;margin-bottom:2px}
.dd-table .ev{color:var(--muted);display:block;margin-top:3px}
.dd-table .fix{color:var(--ink)}
.dd-table ul{margin:4px 0 0;padding-left:18px;color:var(--muted);font-size:12px}
.dd-empty{color:var(--faint);font-style:italic}
details.dd-method{margin-top:28px}
details.dd-method summary{cursor:pointer;color:var(--brand)}
details.dd-method li{margin:3px 0}
</style>
"""

SCRIPT = """
<script>
(function(){
  var state={sev:new Set(['high','medium','low']),src:new Set(['book','readme']),q:''};
  var rows=[].slice.call(document.querySelectorAll('tr[data-sev]'));
  var groups=[].slice.call(document.querySelectorAll('.dd-group'));
  var count=document.getElementById('dd-count');
  function apply(){
    var shown=0;
    rows.forEach(function(r){
      var ok=state.sev.has(r.dataset.sev)&&state.src.has(r.dataset.src)&&
        (!state.q||r.textContent.toLowerCase().indexOf(state.q)>=0||
         (r.closest('.dd-group').dataset.name||'').indexOf(state.q)>=0);
      r.hidden=!ok; if(ok) shown++;
    });
    groups.forEach(function(g){g.hidden=!g.querySelector('tr[data-sev]:not([hidden])');});
    document.querySelectorAll('.dd-section').forEach(function(s){
      var any=s.querySelector('.dd-group:not([hidden])');
      s.querySelector('.dd-none').hidden=!!any;
    });
    count.textContent='Showing '+shown+' of '+rows.length+' findings';
  }
  document.querySelectorAll('.dd-chip').forEach(function(b){
    b.addEventListener('click',function(){
      var set=state[b.dataset.kind], v=b.dataset.value;
      var on=b.getAttribute('aria-pressed')==='true';
      if(on&&set.size===1) return;  /* keep at least one selected */
      on?set.delete(v):set.add(v); b.setAttribute('aria-pressed',String(!on)); apply();
    });
  });
  document.getElementById('dd-q').addEventListener('input',function(e){
    state.q=e.target.value.trim().toLowerCase(); apply();
  });
  apply();
})();
</script>
"""


def line_url(f: dict) -> str:
    return f"https://github.com/{ORG}/{f['repo']}/blob/HEAD/{f['path']}#L{f['line']}"


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def row(f: dict) -> str:
    sev = f["severity"]
    badge = f'<span class="badge {BADGE[sev]}">{sev.capitalize()}</span>'
    where = f'<a href="{escape(line_url(f))}" target="_blank" rel="noopener">line {f["line"]}</a>'
    if f.get("more_lines"):
        where += (
            f'<br><span class="ev">also {", ".join(map(str, f["more_lines"]))}</span>'
        )
    folded = ""
    if f.get("folded"):
        items = "".join(f"<li>{escape(x)}</li>" for x in f["folded"])
        folded = f"<ul>{items}</ul>"
    return (
        f'<tr data-sev="{sev}" data-src="{f["source"]}">'
        f'<td class="id">{f["id"]}</td><td>{badge}</td><td>{where}</td>'
        f'<td><span class="what">{escape(LABELS.get(f["check"], f["check"]))}</span>'
        f"<code>{escape(f['claim'])}</code>"
        f'<span class="ev">{escape(cap(f["evidence"]))}.</span>{folded}</td>'
        f'<td class="fix">{escape(f["suggestion"])}</td></tr>'
    )


def group_html(source: str, key: str, fs: list[dict]) -> str:
    f0 = fs[0]
    if source == "book":
        title = f0["page"] if f0["page"] not in (f0["path"],) else f0["path"]
        title = title.removeprefix("book/")
        # Sidebar titles carry emoji (e.g. "🤗 Welcome"); keep headings plain.
        title = re.sub(r"^[^\w(]+", "", title)
    else:
        title = f0["repo"]
    file_url = f"https://github.com/{ORG}/{f0['repo']}/blob/HEAD/{f0['path']}"
    fs = sorted(fs, key=lambda f: (RANK[f["severity"]], f["line"]))
    return (
        f'<div class="dd-group" data-name="{escape(key.lower())}">'
        f"<h3>{escape(title)} "
        f'<a href="{escape(file_url)}" target="_blank" rel="noopener">{escape(f0["path"])}</a></h3>'
        '<div class="scrollwrap"><table class="data dd-table"><thead><tr>'
        "<th>ID</th><th>Severity</th><th>Where</th><th>What is wrong</th><th>Suggested fix</th>"
        "</tr></thead><tbody>"
        + "".join(row(f) for f in fs)
        + "</tbody></table></div></div>"
    )


def section(source: str, heading: str, findings: list[dict]) -> str:
    groups: dict[str, list[dict]] = {}
    for f in findings:
        if f["source"] == source:
            key = f["path"] if source == "book" else f["repo"]
            groups.setdefault(key, []).append(f)
    # Pages with the most serious problems first, then the most problems.
    order = sorted(
        groups,
        key=lambda k: (
            min(RANK[f["severity"]] for f in groups[k]),
            -len(groups[k]),
            k,
        ),
    )
    body = "".join(group_html(source, k, groups[k]) for k in order)
    return (
        f'<section class="section dd-section"><h2>{heading}</h2>'
        f'<p class="dd-empty dd-none" hidden>No findings match the filters.</p>'
        f"{body or '<p class=dd-empty>No drift found.</p>'}</section>"
    )


def body(findings: list[dict], checked_on: str) -> str:
    sev = {s: sum(f["severity"] == s for f in findings) for s in RANK}
    pages = len({(f["repo"], f["path"]) for f in findings})
    stats = "".join(
        f'<div class="stat"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="d">{d}</div></div>'
        for k, v, d in (
            ("Findings", len(findings), f"on {pages} pages and READMEs"),
            ("High", sev["high"], "a reader who follows the text fails"),
            ("Medium", sev["medium"], "wrong or unreachable, nothing breaks"),
            ("Low", sev["low"], "still works; fix with other changes"),
        )
    )
    chips = (
        '<div class="group"><span class="lbl">Severity</span>'
        + "".join(
            f'<button class="dd-chip" data-kind="sev" data-value="{s}" aria-pressed="true">'
            f"{s.capitalize()} · {sev[s]}</button>"
            for s in RANK
        )
        + '</div><div class="group"><span class="lbl">Where</span>'
        '<button class="dd-chip" data-kind="src" data-value="book" aria-pressed="true">Ersilia Book</button>'
        '<button class="dd-chip" data-kind="src" data-value="readme" aria-pressed="true">READMEs</button>'
        "</div>"
        '<input type="search" id="dd-q" placeholder="Search a page, repo, command or link" '
        'aria-label="Search findings">'
    )
    checks = "".join(
        f"<li><strong>{escape(v)}</strong> (<code>{k}</code>)</li>"
        for k, v in LABELS.items()
    )
    return f"""
<main class="document">
  <header class="brandhead">
    <span class="eyebrow brand">Docs drift · Ersilia Open Source Initiative</span>
    <h1 class="wordmark">Docs <em>drift</em></h1>
    <p class="muted" style="margin:.4em 0 0;max-width:62ch">Places where the Ersilia Book and
    our repository READMEs no longer match the code or the GitHub organisation. Checked on
    {escape(checked_on)}. Each finding links to the exact line.</p>
  </header>
  <div class="dd-stats">{stats}</div>
  <div class="dd-filters">{chips}</div>
  <p class="dd-count" id="dd-count">Showing {len(findings)} of {len(findings)} findings</p>
  {section("book", "Ersilia Book", findings)}
  {section("readme", "READMEs", findings)}
  <details class="dd-method"><summary>How this was checked</summary>
    <p>The <code>docs-drift</code> skill compares every Book page and the README of every
    active, non-model repository with live sources: the <code>ersilia</code> command-line
    tool's source code, the list of repositories in the organisation, each package's
    <code>pyproject.toml</code>, the Book's sidebar (<code>SUMMARY.md</code>), and web links
    (a link counts as broken only on "not found" or a domain that does not resolve). Model
    repositories and workshop material are out of scope. Findings of the kind "text
    contradicts the code" come from a person or Claude reading a page next to its code.</p>
    <ul>{checks}</ul>
  </details>
</main>
{STYLE}
{SCRIPT}
"""


def theme(fragment: str, out: Path) -> bool:
    if not THEME.exists():
        return False
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as tmp:
        tmp.write(fragment)
    proc = subprocess.run(
        [
            sys.executable,
            str(THEME),
            "--mode",
            "retrofit",
            tmp.name,
            "--out",
            str(out),
            "--title",
            "Docs drift",
            "--source-url",
            SOURCE_URL,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    Path(tmp.name).unlink(missing_ok=True)
    return proc.returncode == 0


def as_artifact(html: str) -> str:
    """Drop the document wrapper tags; the Artifact host adds its own skeleton."""
    html = re.sub(
        r"(?is)<!doctype[^>]*>|</?html[^>]*>|</?head[^>]*>|</?body[^>]*>", "", html
    )
    return html.strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", default="/tmp/docs-drift/findings_final.json")
    p.add_argument("--out", default=None)
    p.add_argument(
        "--artifact", action="store_true", help="omit <html>/<head>/<body> wrappers"
    )
    args = p.parse_args(argv)

    data = read_json(args.input)
    if not isinstance(data, dict) or "findings" not in data:
        print(f"ERROR: {args.input} is not render_report.py output", file=sys.stderr)
        return 2
    out = Path(args.out or Path(args.input).parent / "docs-drift.html")
    checked_on = datetime.now(timezone.utc).strftime("%-d %B %Y")
    fragment = body(data["findings"], checked_on)
    if not theme(fragment, out):
        out.write_text("<title>Docs drift</title>\n" + fragment, encoding="utf-8")
        print(
            "WARN: html-formatting theme not found; wrote an unstyled page",
            file=sys.stderr,
        )
    if args.artifact:
        out.write_text(as_artifact(out.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"{len(data['findings'])} findings → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
