"""
make_visualizer.py — build a self-contained interactive HTML explorer from a condensed
selection_table.csv + viz_meta.json (both produced by build_table.py). Config-driven,
no hardcoded columns. No matplotlib dependency (rank colour is a pure-Python interpolation).

Usage:
    python make_visualizer.py --output-dir <dir>

Reads <dir>/selection_table.csv and <dir>/viz_meta.json, writes <dir>/selection_visualizer.html.
Features: CoordGen 2D structures, two tabs (Compound Explorer + Legend), filterable consensus
badges, min/max sliders, per-cell rank-colouring + pass shading, category checkboxes, SMILES
search, sort, CPD-XXX ids, and a bottom SWOT one-liner. Neutral (GitHub-style) palette.

The HTML template below uses SINGLE braces and is assembled with str.replace on __TOKENS__
(never str.format), so the embedded JSON is left untouched.
"""
import os
import re
import json
import argparse
import datetime
import pandas as pd
from rdkit import Chem
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem import rdCoordGen


def rank_hex(p):
    """blue(low) -> white -> red(high), ColorBrewer RdBu, pure python."""
    if p is None:
        return None
    if p <= 0.5:
        t = p / 0.5; c0, c1 = (33, 102, 172), (247, 247, 247)
    else:
        t = (p - 0.5) / 0.5; c0, c1 = (247, 247, 247), (178, 24, 43)
    return "#%02x%02x%02x" % tuple(int(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))


def svg_for(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    rdCoordGen.AddCoords(mol)
    d = rdMolDraw2D.MolDraw2DSVG(250, 180)
    o = d.drawOptions(); o.clearBackground = False; o.bondLineWidth = 1
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
    d.FinishDrawing()
    s = d.GetDrawingText()
    return s[s.find("<svg"):]


HTML = """<!doctype html><html><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
 :root { --bg:#f6f8fa; --card:#fff; --ink:#1f2328; --muted:#656d76; --border:#d0d7de; --accent:#0969da; }
 body { font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; margin:0; background:var(--bg); color:var(--ink); }
 input,select { accent-color:var(--accent); }
 #tabbar { position:sticky; top:0; z-index:20; background:#f0f0f0; border-bottom:1px solid #dcdcdc; display:flex; align-items:center; gap:2px; padding:0 16px; }
 #tabbar .brand { font-size:11px; color:#9a9a9a; margin-right:24px; letter-spacing:.6px; text-transform:uppercase; }
 #tabbar button { background:none; border:none; border-bottom:2px solid transparent; color:#777; font-size:13px; padding:12px 14px; cursor:pointer; }
 #tabbar button.active { color:#222; border-bottom-color:var(--accent); }
 header { position:sticky; top:43px; background:#fff; border-bottom:1px solid var(--border); padding:10px 16px; z-index:10; }
 h1 { font-size:14px; font-weight:400; color:#555; margin:0 0 8px 0; }
 #count { font-weight:600; color:var(--accent); }
 .controls { display:flex; flex-wrap:wrap; gap:14px 22px; align-items:flex-end; }
 .ctl { display:flex; flex-direction:column; font-size:11px; color:var(--muted); }
 .ctl input[type=range] { width:150px; } .ctl .val { color:var(--ink); font-weight:bold; }
 input[type=text],select { font-size:12px; padding:3px 5px; }
 #grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:12px; padding:16px; }
 .card { background:var(--card); border:1px solid #e2e2e2; border-radius:8px; padding:8px; position:relative; }
 .card svg { display:block; margin:0 auto; }
 .badge { display:inline-block; padding:1px 6px; border-radius:10px; color:#fff; font-size:10px; margin-left:6px; }
 .badge8 { display:inline-block; padding:0 6px; border-radius:10px; font-size:10px; margin-left:4px; border:1px solid var(--accent); color:var(--accent); background:#fff; }
 table.props { width:100%; border-collapse:collapse; font-size:11px; margin-top:4px; }
 table.props td { padding:1px 3px; } table.props td:nth-child(odd){ color:var(--muted); }
 table.props td:nth-child(even){ text-align:right; font-variant-numeric:tabular-nums; }
 .smiles { font-size:9px; color:#999; word-break:break-all; margin-top:4px; }
 .swot { font-size:10.5px; font-style:italic; color:#444; line-height:1.35; margin:6px 0 0; padding-top:5px; border-top:1px solid #eee; }
 #selbar { margin-top:6px; font-size:11px; color:var(--muted); display:flex; align-items:center; gap:8px; }
 #selbar button { font-size:11px; padding:3px 9px; border:1px solid var(--border); border-radius:6px; background:#fff; cursor:pointer; }
 #selbar button#exportbtn { background:var(--accent); color:#fff; border-color:var(--accent); }
 #selcount { font-weight:600; color:var(--ink); }
 .selchk { position:absolute; top:8px; right:8px; width:17px; height:17px; margin:0; cursor:pointer;
           accent-color:var(--accent); z-index:2; background:#fff; border-radius:4px;
           box-shadow:0 0 0 3px #fff; }
 .card:has(.selchk:checked) { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
 .report { max-width:980px; margin:0 auto; padding:24px 28px 80px; line-height:1.5; font-size:14px; }
 .report h1 { font-size:24px; color:#1f2328; font-weight:600; } .report h2 { font-size:18px; margin-top:26px; border-bottom:1px solid var(--border); padding-bottom:5px; }
 .report table { border-collapse:collapse; width:100%; margin:12px 0; font-size:12px; }
 .report th,.report td { border:1px solid var(--border); padding:5px 8px; text-align:left; }
 .report th { background:#f6f8fa; } .report code { background:#eff1f3; padding:1px 4px; border-radius:3px; }
 #footer { text-align:center; color:#9a9a9a; font-size:11px; padding:18px; border-top:1px solid var(--border); }
 #footer a { color:var(--accent); text-decoration:none; }
</style></head><body>
<div id="tabbar"><span class="brand">Ersilia molecule explorer</span>
 <button data-tab="explorer" class="active">Compound Explorer</button>
 <button data-tab="report">Legend</button></div>
<div id="tab-explorer">
 <header><h1>__TITLE__ &mdash; <span id="count"></span> compounds shown</h1><div class="controls" id="controls"></div>
  <div id="selbar"><span id="selcount">0</span> selected
   <button id="exportbtn">Export selected (CSV)</button>
   <button id="importbtn">Import selection</button><button id="selallbtn">Select all</button><button id="clearbtn">Clear</button>
   <input type="file" id="importfile" accept=".csv,.tsv" style="display:none"></div></header>
 <div id="grid"></div></div>
<div id="tab-report" style="display:none"><div class="report">
 <h1>How to read this explorer</h1>
 <p>Each card is one compound: a CPD id, consensus badges, an optional category, the 2D structure,
 the model scores, and a one-line SWOT summary. Badges:</p><ul>__BADGE_LEGEND__</ul>
 <p><b>Cell shading:</b> score cells that pass their cutoff are highlighted &mdash; rank-coloured cells
 shade by within-set rank (blue = low to red = high); outlined cells simply passed. Plain cells did not pass or are context.</p>
 <h2>Columns</h2>
 <table><thead><tr><th>Column</th><th>Model</th><th>Meaning</th><th>Direction</th></tr></thead><tbody>__LEG_ROWS__</tbody></table>
 <h2>Controls</h2>
 <p>Min/max sliders, badge &ge; selectors, category checkboxes and sort all filter the grid live; the count by the title updates. Tick compounds to build a selection, then Export / Import to save or resume it.</p>
</div></div>
<div id="footer">Created on __DATE__ &middot; Brought to you by the <a href="https://ersilia.io" target="_blank">Ersilia Open Source Initiative</a></div>
<script>
const DATA=__DATA__, META=__META__;
document.querySelectorAll("#tabbar button").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll("#tabbar button").forEach(x=>x.classList.remove("active")); b.classList.add("active");
  document.getElementById("tab-explorer").style.display=b.dataset.tab==="explorer"?"":"none";
  document.getElementById("tab-report").style.display=b.dataset.tab==="report"?"":"none";
}));
const state={minv:{},maxv:{},badge:{},cats:new Set(META.cats),sort:META.sort_default,desc:true,selected:new Set()};
function fmt(v){ return v===null||v===undefined?"&ndash;":(typeof v==="number"?(Number.isInteger(v)?v:(""+v.toFixed(3)).replace(/0+$/,"").replace(/\\.$/,"")):v); }
function textOn(hex){const r=parseInt(hex.substr(1,2),16),g=parseInt(hex.substr(3,2),16),b=parseInt(hex.substr(5,2),16);return (0.299*r+0.587*g+0.114*b)>150?"#000":"#fff";}
function badgeColor(c,t){const r=c/t; return r>=1?"#1a7f37":r>=0.5?"#0969da":"#8c959f";}
function buildControls(){
 const c=document.getElementById("controls");
 META.slider_min.forEach(k=>{const lo=META.ranges[k][0],hi=META.ranges[k][1]; state.minv[k]=lo; const step=(hi-lo)/100||1;
  const d=document.createElement("div"); d.className="ctl";
  d.innerHTML=`<label>${k} &ge; <span class="val" id="v_${k}">${lo.toFixed(2)}</span></label><input type="range" min="${lo}" max="${hi}" step="${step}" value="${lo}">`;
  c.appendChild(d); d.querySelector("input").addEventListener("input",e=>{state.minv[k]=+e.target.value; document.getElementById("v_"+k).textContent=(+e.target.value).toFixed(2); render();});});
 META.slider_max.forEach(k=>{const lo=META.ranges[k][0],hi=META.ranges[k][1]; state.maxv[k]=hi; const step=(hi-lo)/100||1;
  const d=document.createElement("div"); d.className="ctl";
  d.innerHTML=`<label>${k} &le; <span class="val" id="vx_${k}">${hi.toFixed(2)}</span></label><input type="range" min="${lo}" max="${hi}" step="${step}" value="${hi}">`;
  c.appendChild(d); d.querySelector("input").addEventListener("input",e=>{state.maxv[k]=+e.target.value; document.getElementById("vx_"+k).textContent=(+e.target.value).toFixed(2); render();});});
 META.badges.forEach(b=>{state.badge[b.name]=0; const d=document.createElement("div"); d.className="ctl";
  let opts='<option value="0">any</option>'; for(let v=1;v<=b.total;v++) opts+=`<option value="${v}">${v}</option>`;
  d.innerHTML=`<label>${b.label} &ge; (n/${b.total})</label><select>${opts}</select>`;
  c.appendChild(d); d.querySelector("select").addEventListener("change",e=>{state.badge[b.name]=+e.target.value; render();});});
 if(META.cat_col){const d=document.createElement("div"); d.className="ctl"; d.innerHTML=`<label>${META.cat_col}</label><div id='cats'></div>`; c.appendChild(d);
  META.cats.forEach(l=>{const lab=document.createElement("label"); lab.style.cssText="font-size:11px;color:#222"; lab.innerHTML=`<input type=checkbox checked> ${l} `;
   d.querySelector("#cats").appendChild(lab); lab.querySelector("input").addEventListener("change",e=>{e.target.checked?state.cats.add(l):state.cats.delete(l); render();});});}
 let d=document.createElement("div"); d.className="ctl";
 let so=META.display_cols.map(f=>`<option value="${f}">${f}</option>`).join("");
 d.innerHTML=`<label>sort by</label><div style="display:flex;align-items:center;gap:10px"><select id=sort>${so}</select>
  <label style="display:flex;gap:3px;align-items:center"><input type=radio name=dir checked> desc</label>
  <label style="display:flex;gap:3px;align-items:center"><input type=radio name=dir> asc</label></div>`;
 c.appendChild(d); d.querySelector("#sort").value=state.sort;
 d.querySelector("#sort").addEventListener("change",e=>{state.sort=e.target.value; render();});
 const radios=d.querySelectorAll("input[type=radio]"); radios[0].addEventListener("change",()=>{state.desc=true; render();}); radios[1].addEventListener("change",()=>{state.desc=false; render();});
}
function passes(r){
 for(const k of META.slider_min){const v=r.fields[k]; if(v!=null && v<state.minv[k]) return false;}
 for(const k of META.slider_max){const v=r.fields[k]; if(v!=null && v>state.maxv[k]) return false;}
 for(const b of META.badges){ if((r.badges[b.name]||0) < state.badge[b.name]) return false; }
 if(META.cat_col && r.cat && !state.cats.has(r.cat)) return false;
 return true;
}
function render(){
 let rows=DATA.filter(passes); const s=state.sort, sg=state.desc?-1:1;
 rows.sort((a,b)=>{const x=a.fields[s]==null?-Infinity:a.fields[s],y=b.fields[s]==null?-Infinity:b.fields[s]; return x<y?-sg:x>y?sg:0;});
 document.getElementById("count").textContent=rows.length;
 document.getElementById("grid").innerHTML=rows.map(r=>{
  const props=META.display_cols.map(k=>{
   let style=""; const cc=META.cell_cutoffs[k];
   if(cc && r.fields[k]!=null){ const pass=(cc.op==="<="?r.fields[k]<=cc.cutoff:r.fields[k]>=cc.cutoff);
    if(pass){ if(cc.style==="box"){ style=` style="box-shadow:inset 0 0 0 1px var(--accent);border-radius:3px"`; }
     else { const col=r.colors[k]||"#0969da"; style=` style="background:${col};color:${textOn(col)};border-radius:3px"`; } } }
   return `<td>${k}</td><td${style}>${fmt(r.fields[k])}</td>`;
  });
  let cells=""; for(let i=0;i<props.length;i+=2) cells+="<tr>"+props[i]+(props[i+1]||"<td></td><td></td>")+"</tr>";
  let bhtml=META.badges.map((b,idx)=>{ const v=r.badges[b.name]||0;
   return idx===0?`<span class="badge" style="background:${badgeColor(v,b.total)}">${v}/${b.total}</span>`
                 :`<span class="badge8">${v}/${b.total}</span>`; }).join("");
  return `<div class="card"><input type="checkbox" class="selchk" title="select" data-cpd="${r.cpd_id}" ${state.selected.has(r.cpd_id)?"checked":""}>
   ${r.svg||"<div style='height:180px;color:#bbb;text-align:center;line-height:180px'>no structure</div>"}
   <div style="font-size:11px"><b>${r.cpd_id}</b>${bhtml}${r.key?` <span style="color:var(--muted)" title="source id">${r.key}</span>`:""}${r.cat?` <span style="color:var(--muted)">${r.cat}</span>`:""}</div>
   <div class="smiles">${r.smiles}</div><table class="props">${cells}</table>
   ${r.swot?`<div class="swot">${r.swot}</div>`:""}</div>`;
 }).join("");
}
// ---- selection: checkbox + export/import/clear ----
function updateSel(){ document.getElementById("selcount").textContent=state.selected.size; }
function csvCell(v){ v=(v==null?"":String(v)); return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v; }
function exportSel(){
 let cols=["cpd_id"]; if(DATA.some(r=>r.key)) cols.push("source_key");
 cols=cols.concat(["smiles"],META.display_cols,META.badges.map(b=>b.name));
 if(DATA.some(r=>r.swot)) cols.push("swot");
 const sel=DATA.filter(r=>state.selected.has(r.cpd_id));
 if(!sel.length){ alert("No compounds selected."); return; }
 const lines=[cols.join(",")];
 sel.forEach(r=>lines.push(cols.map(c=> c==="cpd_id"?csvCell(r.cpd_id):c==="source_key"?csvCell(r.key):c==="smiles"?csvCell(r.smiles):c==="swot"?csvCell(r.swot):(c in r.fields?csvCell(r.fields[c]):(r.badges[c]!=null?csvCell(r.badges[c]):""))).join(",")));
 const a=document.createElement("a"); a.href=URL.createObjectURL(new Blob([lines.join("\\n")],{type:"text/csv"}));
 a.download="selection_export.csv"; a.click();
}
function importSel(text){
 const rows=text.split(/\\r?\\n/).filter(x=>x.length); if(!rows.length) return;
 const hdr=rows[0].split(/[\\t,]/).map(s=>s.replace(/^"|"$/g,"").trim());
 let idx=hdr.indexOf("cpd_id"); if(idx<0) idx=0;
 let added=0;
 for(let i=1;i<rows.length;i++){ const id=(rows[i].split(/[\\t,]/)[idx]||"").replace(/^"|"$/g,"").trim();
  if(id && DATA.some(r=>r.cpd_id===id)){ state.selected.add(id); added++; } }
 updateSel(); render(); alert("Imported "+added+" selected compounds.");
}
document.getElementById("grid").addEventListener("change",e=>{
 if(e.target.classList.contains("selchk")){ const id=e.target.dataset.cpd;
  e.target.checked?state.selected.add(id):state.selected.delete(id); updateSel(); }});
document.getElementById("exportbtn").addEventListener("click",exportSel);
document.getElementById("selallbtn").addEventListener("click",()=>{ DATA.filter(passes).forEach(r=>state.selected.add(r.cpd_id)); updateSel(); render(); });
document.getElementById("clearbtn").addEventListener("click",()=>{state.selected.clear(); updateSel(); render();});
document.getElementById("importbtn").addEventListener("click",()=>document.getElementById("importfile").click());
document.getElementById("importfile").addEventListener("change",e=>{ const f=e.target.files[0]; if(!f) return;
 const rd=new FileReader(); rd.onload=()=>importSel(rd.result); rd.readAsText(f); e.target.value=""; });
buildControls(); render(); updateSel();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()
    d = args.output_dir
    df = pd.read_csv(os.path.join(d, "selection_table.csv"))
    meta = json.load(open(os.path.join(d, "viz_meta.json")))

    display_cols = [c for c in meta["display_cols"] if c in df.columns]
    badges = meta["badges"]
    rank_cols = [c for c in meta.get("rank_color_cols", []) if c in df.columns]
    cat_col = meta.get("category_col")
    has_swot = "swot" in df.columns

    rcolors = {}
    for c in rank_cols:
        pct = pd.to_numeric(df[c], errors="coerce").rank(pct=True)
        rcolors[c] = [rank_hex(None if pd.isna(p) else float(p)) for p in pct]

    records = []
    for i, r in df.iterrows():
        records.append({
            "cpd_id": r["cpd_id"], "smiles": r["smiles"], "svg": svg_for(r["smiles"]),
            "key": (str(r["source_key"]) if "source_key" in df.columns and pd.notna(r["source_key"]) else ""),
            "cat": (str(r[cat_col]) if cat_col and cat_col in df.columns and pd.notna(r[cat_col]) else ""),
            "swot": ("" if not has_swot or pd.isna(r["swot"]) else str(r["swot"])),
            "fields": {c: (None if pd.isna(r[c]) else (float(r[c]) if isinstance(r[c], float) else r[c])) for c in display_cols},
            "badges": {b["name"]: int(r[b["name"]]) for b in badges if b["name"] in df.columns},
            "colors": {c: rcolors[c][i] for c in rank_cols},
        })

    def rng(col):
        s = pd.to_numeric(df[col], errors="coerce")
        return [float(s.min()), float(s.max())]
    slider_min = [c for c in meta.get("slider_min", []) if c in df.columns]
    slider_max = [c for c in meta.get("slider_max", []) if c in df.columns]
    ranges = {c: rng(c) for c in set(slider_min) | set(slider_max)}
    cats = sorted(df[cat_col].dropna().astype(str).unique().tolist()) if (cat_col and cat_col in df.columns) else []

    leg = meta.get("legend", {})

    def model_cell(m):
        m = str(m or "")
        if re.fullmatch(r"eos[0-9a-z]{4}", m):
            return f'<a href="https://github.com/ersilia-os/{m}" target="_blank">{m}</a>'
        return m
    leg_rows = "".join(
        f"<tr><td><code>{c}</code></td><td>{model_cell(leg.get(c, {}).get('model', ''))}</td>"
        f"<td>{leg.get(c, {}).get('meaning', '')}</td>"
        f"<td>{('higher = better' if leg.get(c, {}).get('higher_better', True) else 'lower = better') if c in leg else ''}</td></tr>"
        for c in display_cols)
    badge_legend = "".join(
        f"<li><b>{b['label']} ({b['name']})</b> &mdash; consensus over {b['total']} signals "
        f"(badge shows how many pass)</li>" for b in badges)

    DATA = json.dumps(records)
    META = json.dumps({"display_cols": display_cols, "badges": badges,
                       "cell_cutoffs": meta.get("cell_cutoffs", {}), "rank_cols": rank_cols,
                       "slider_min": slider_min, "slider_max": slider_max, "ranges": ranges,
                       "cat_col": cat_col or "", "cats": cats,
                       "sort_default": meta.get("sort_default", display_cols[0] if display_cols else "")})

    page = (HTML.replace("__TITLE__", meta.get("title", "Molecule explorer"))
                .replace("__DATE__", datetime.date.today().isoformat())
                .replace("__BADGE_LEGEND__", badge_legend)
                .replace("__LEG_ROWS__", leg_rows)
                .replace("__DATA__", DATA).replace("__META__", META))
    out = os.path.join(d, "selection_visualizer.html")
    with open(out, "w") as f:
        f.write(page)
    print(f"Wrote {out}: {len(records)} compounds, {sum(1 for r in records if r['svg'])} structures, "
          f"{os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
