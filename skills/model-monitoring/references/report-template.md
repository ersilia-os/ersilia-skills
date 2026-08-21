# Report structure and design

The report is one self-contained HTML file produced by `scripts/build_report.py`. This file
records what goes in it, in what order, and why — so that changes stay coherent instead of
accreting.

## Contents

- [Section order](#section-order)
- [The design system](#the-design-system)
- [Coverage classes](#coverage-classes)
- [Editing the report](#editing-the-report)

---

## Section order

The order encodes a priority: **act, then orient, then browse, then review history.**

| # | Section | Job | Source |
|---|---|---|---|
| 1 | Masthead + headline figures | Eight numbers that answer "is anything wrong?" in five seconds | both |
| 2 | Note box | Unavailable sources — surfaced, not buried | maintenance |
| 3 | **Needs attention** | The only section that asks the reader to do something | both |
| 4 | **Coverage plate** | Make ~220 models legible at a glance | coverage |
| 5 | Precalculation coverage | The full searchable, sortable, filterable table | coverage |
| 6 | Singularity images | Figure grid + matching searchable table | sif |
| 7 | This week in maintenance | Weekly test results + upstream-moved-on models | maintenance |
| 8 | Monthly health | Current snapshot + month-by-month series | maintenance |
| 9 | Monthly trends | The three published plots (only with `--plots`) | maintenance |
| 10 | Footer | Provenance: when each source was read, what "full" means | all |

The **Singularity section deliberately mirrors the isaura section**: same figure grid, same
table controls, same colour roles. The two answer the same shape of question — "does this
artefact exist for each Ready model?" — about different artefacts, so a reader who has learnt
one layout reads the other for free. If you restyle one, restyle both.

**Needs attention comes before the totals tables** because it is the union of the report's
two independent signals — a failing maintenance test and a `Ready` model with no stored
predictions. A monitoring report fails when the reader has to assemble the to-do list
themselves from two separate tables, so the report assembles it for them.

Empty states are written as reassurance, not as blanks: "No model is currently failing its
last maintenance test" is information, whereas an absent section is ambiguous.

---

## Design

The report is styled by the **`html-formatting`** skill, which owns the Ersilia look and feel.
This skill owns the report's structure, content and semantics. Keep that split: anything about
colour, type or chrome belongs in `html-formatting`, and duplicating it here guarantees drift.

The page is a **`dashboard`** archetype (wide centred container, wordmark header, KPI row of
`.stat` tiles, house `table.data` in `.scrollwrap`). Dashboard rather than `document` because
the primary content is metrics and tables rather than prose, and because the wider container
suits an eight-column table.

### Signature element: the coverage plate

One small well per model, laid out as a dense grid, coloured by coverage class, ordered
problems-first. Faded wells sit outside the Ready population; hovering gives the model id,
slug, class, molecule count and status.

Two reasons it earns the space: a microplate is native vernacular for an audience that does
drug discovery, and a dense grid is the only device that makes ~220 discrete units legible
in a single glance — a table of 220 rows cannot do that, and a bar chart of 220 bars is
worse. It is also honest to the data: each model genuinely is a discrete unit that is either
covered or not.

Everything else on the page stays quiet so the plate carries the visual weight. That is the
one place boldness is spent.

### Colour and type: owned by `html-formatting`

**This skill does not define a palette.** Every colour, font, radius and shadow comes from the
Ersilia design system in the `html-formatting` skill, which is the single authority for how
Ersilia HTML looks. Read `html-formatting/references/design-system.md` for the tokens; do not
restate them here, or the two will drift and this copy will lose.

What this skill owns is the **mapping** — which token carries which meaning:

| Meaning | Token | Why |
|---|---|---|
| Complete coverage / image available | `--good` | A genuine healthy state |
| Incomplete coverage | `--warn` | A genuine caution state |
| No coverage / no image | `--bad` | A genuine failure state |
| Outside the Ready population | `--purple` | Not a state at all — a population mismatch, so it takes a data hue rather than a state token |

The design system reserves `--good`/`--warn`/`--bad` for exactly this: real states, addressed
semantically rather than by palette slot. Coverage is a state, so no colour had to be invented.

Two rules that survive from the report's own design and are worth keeping:

- **Colour encodes coverage class and nothing else.** The same token appears in the plate, the
  legend, the badges and the table, so the reader learns the mapping once. The Singularity
  section reuses the identical three tokens in the identical roles.
- **Emphasis is an accent rule, not a coloured numeral.** An alert stat tile takes a `--bad`
  top border; the number stays `--ink`. A large figure in the alert hue is harder to read than
  an ink one, and the rule is louder anyway.

### Class collisions: check the name before you use it

Three separate bugs in this report came from reusing a class name the surrounding CSS already
owned. Each time the page still *rendered*, just wrongly, which is what makes this worth a
standing note:

| Class | What went wrong |
|---|---|
| `.note` | Used for the legend's muted caption; also the yellow callout box, so every legend key was wrapped in a callout. Now `.dim` / `.fade`. |
| `.sw` | Used for the legend swatches; `ersilia.css` defines `.sw` as the **switch** component (a 34×19 pill with a white knob), so each swatch rendered as a tiny toggle. Now `.swatch`. |
| `.lede` | Used for every section intro but defined **nowhere** — neither here nor in `ersilia.css` — so the paragraphs rendered as unstyled full-width body text. Now defined in this skill's CSS from tokens. |

Before adding a utility class, grep `html-formatting/assets/ersilia.css` for the name. The
audit is cheap:

```bash
grep -nE "\.<name>[ ,{:]" ~/.claude/skills/html-formatting/assets/ersilia.css
```

Deliberate *extensions* of a house class are fine and are marked as such in the CSS —
`.badge{white-space:nowrap}` and `.stat.alert` both add to a house component rather than
redefining it.

### Type

Comes from the design system (`--sans` / `--mono`). The one thing this skill decides is *which
cells are data*: every model id, count, size and date is `.mono`, and numeric table cells use
`td.num` so `font-variant-numeric: tabular-nums` aligns them down the column. Prose does not
get tabular figures, and neither do the large `.stat` values — the design system deliberately
sets those proportional, because equal-width digits make a single big number look loose.

### Progressive disclosure

Three tiers, per the house UX rules:

1. **Surface** — the KPI row and the counted sub-headings.
2. **Hover** — every table column header carries a `title=` explaining what the column means,
   so the meaning is one hover away rather than spelled out in prose above the table.
3. **Methods** — a `<details>` block, *How these numbers are derived*, holding the population
   definition, what counts as "full", the multi-version rule, the upstream schema rename and
   the provenance timestamps. Every headline figure here is derived rather than read off a
   source, and the house rule is that derived metrics owe the reader their derivation.

### Quality floor

Responsive (grids collapse at 860px), visible keyboard focus, wide tables scroll inside
`.scrollwrap` so the page body never scrolls sideways, print stylesheet drops the filter
controls. Single light theme — the Ersilia brand is light, so no dark variant.

### Self-containment

**Zero network requests.** No external scripts, stylesheets or fonts; `ersilia.css` is inlined
by `apply_theme.py`, the favicon is an inline SVG data URI, and the maintenance plots are
base64 data URIs. GitHub links are navigational only. These reports get archived and forwarded,
and one that silently loses its styling or charts a month later is worse than no report. The
cost is file size — roughly 250 KB without plots, 700 KB with them — which is why `--plots` is
opt-in.

---

## Coverage classes

Every model lands in exactly one class, so the counts are a partition and can be checked by
addition. `complete + partial + missing` equals the hub total; `orphan` sits outside it by
definition, since an orphan is not in the hub listing.

| Class | Label in report | Test |
|---|---|---|
| `complete` | Complete | best stored version has ≥ 1,355,109 molecules |
| `partial` | Incomplete | 0 < best version < 1,355,109 |
| `missing` | Not started | in the Ready population, nothing in isaura |
| `orphan` | Not Ready | in isaura, outside the Ready population |

Singularity availability uses the same shape with three classes — `available`, `missing`,
`extra` — and the same three brand hues in the same roles, so the colour mapping transfers.

**The population is Ready models, so every `missing` is actionable by construction.** That is
the point of measuring against Ready rather than against all statuses: it removes the need for
the reader to mentally filter out Archived models. `orphan` and `extra` are the inverse case —
artefacts we store for models that are no longer served — and they are reported separately
because that is a question about reclaiming storage, never folded into the coverage
percentage.

Models stored at several versions are folded to their **best** version, because the question
is whether the predictions exist at all. Every version is still listed in the table's
Versions column, so a partial newer version behind a complete older one stays visible.

---

## Editing the report

`build_report.py` is organised as one function per section, each returning an HTML string,
composed in `build()`. To change a section, edit its function; to reorder, edit `build()`.

- `figure_grid(items)` — shared renderer for any row of headline figures, emitting house
  `.stat` tiles. The grid is a **fixed** four columns, not `auto-fit`: with eight cells,
  letting the browser choose stranded the last one beside a dead gap. The monthly snapshot's
  six figures use `.stats.six` (three columns) for the same reason.
- `badge(label, token)` — a house `.badge` tinted through its `--c` custom property.
- `outcome_badge(raw)` — maps the maintenance reports' ✅ / 🚨 / ❓ to a badge. The emoji are
  status markers rather than decoration so they would be permissible, but a badge says the
  word and does not rely on the reader knowing the icon.
- `data_table(headers, rows)` — a plain `table.data` in a `.scrollwrap`, for short tables that
  need no controls.
- `methods_block(...)` — the *How these numbers are derived* disclosure.
- `filterable_block(...)` — shared renderer for a table with its own search box, filter chips
  and result count. Everything inside is found **by class within a `.filterable` container**,
  never by id: the page now carries two of these, and duplicate ids would be invalid HTML and
  would leave the second table inert. Numeric columns carry `data-num='1'` on the header and
  `data-v` on cells so sorting compares values rather than comma-formatted strings.
- `figures_block` — the eight headline figures, spanning all three data sources.
- `attention_block` — failing tests + actionable coverage gaps.
- `plate_block` — the signature grid and its legend.
- `coverage_table` — the isaura table, via `filterable_block`.
- `sif_section` — the whole Singularity section: lede, figure grid, table. Renders a
  placeholder when `--sif` was not passed.
- `weekly_block`, `updated_block`, `monthly_block`, `plots_block` — maintenance sections.
- `_hv` — reads a monthly figure under either schema naming. See trap 4 in
  `data-sources.md`.

If the user wants a visually different report, that is a question for **`html-formatting`**,
not for this file — load that skill and work within its tokens and components. Reach into
`build_report.py`'s `CSS` constant only for genuine *structure* the design system does not
cover (the plate wells, the fixed-column KPI grid, the search input), and keep using tokens
there: `check_html.py` flags any hex outside the palette, and a hard-coded colour is how a page
quietly stops being Ersilia.

Keep the data JSONs and re-render — the expensive step is the isaura inventory, not the HTML.
