# molecule-auditing — example output

The skill turns a compound CSV into a self-contained interactive **explorer**, not a markdown
report. Running it on `../assets/drugbank_head_example.csv` (E. coli activity from `eos4e40`
plus ADMET from `eos7m30`) produces, in a `<input_stem>_explorer/` folder:

- `selection_table.csv` — the condensed, filtered deliverable (CPD-XXX ids, chosen/renamed
  columns, consensus badge counts, optional `swot` column).
- `selection_visualizer.html` — a single self-contained page (opens in any browser):
  - **Compound Explorer** tab: a card per compound with the CoordGen 2D structure, consensus
    badges, rank-coloured / pass-outlined score cells, and (optionally) a one-line SWOT summary.
  - **Legend** tab: what each column/model means and how to read the encodings.
  - Live filters (min/max sliders, badge `≥` selectors, category checkboxes, SMILES search,
    sort) and a **selection bar**: tick compounds, **Export selected (CSV)**, **Import selection**
    to resume, and **Clear**.
- `config.json`, `viz_meta.json`, `swot_facts.csv`, `swot_lines.tsv` — intermediates.

Regenerate with:
```
python ../scripts/build_table.py   --config <dir>/config.json
python ../scripts/make_visualizer.py --output-dir <dir>
```
(See `../SKILL.md` for the full interactive workflow and `config.json` schema.)
