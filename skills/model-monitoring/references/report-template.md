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

## The design system

Grounded in the subject's own world rather than in generic dashboard conventions.

### Signature element: the coverage plate

One small well per model, laid out as a dense grid, coloured by coverage class, ordered
problems-first. Faded wells are models that are not `Ready`; hovering gives the model id,
slug, class, molecule count and status.

Two reasons it earns the space: a microplate is native vernacular for an audience that does
drug discovery, and a dense grid is the only device that makes ~250 discrete units legible
in a single glance — a table of 250 rows cannot do that, and a bar chart of 250 bars is
worse. It is also honest to the data: each model genuinely is a discrete unit that is either
covered or not.

Everything else on the page is kept deliberately quiet so the plate carries the visual
weight. That is the one place boldness is spent.

### Palette — the Ersilia brand colours

The brand palette is used verbatim. Its shape drives how colour works on the page: it is
**one dark plum plus a set of light pastels**, so the pastels are strong as fills and
illegible as text on white.

| Brand colour | Hex | Use in the report |
|---|---|---|
| Plum | `#50285A` | Masthead, all body text, headings, numerals, links, active chips |
| Mint | `#BEE6B4` | `complete` wells and badges, progress fill, masthead eyebrow |
| Yellow | `#FAD782` | `partial` wells and badges, note-box rule, masthead inline code |
| Orange | `#FAA08C` | `missing` wells and badges, alert accent rule |
| Purple | `#AA96FA` | `orphan` wells and badges, link underlines |
| Gray | `#D2D2D0` | All rules and borders |
| White | `#FFFFFF` | Card surfaces |
| Blue `#8CC8FA`, Pink `#DCA0DC` | | Declared as tokens, held in reserve |

Two consequences worth preserving:

- **Text is plum, fills are pastel.** Badges are a pastel fill with plum text, because no hue
  in the palette carries white text at 11px.
- **Emphasis is an accent rule, not coloured text.** Alert figures get an Orange top border
  and a pale wash rather than an orange numeral — a 30px number in `#FAA08C` on white is
  hard to read, and the figures are the one thing that must be readable at a glance.

Surfaces `--paper` (`#F7F7F5`) and `--plate` (`#EDEDEA`) are light tints derived from brand
Gray, and `--ink-soft` / `--muted` are lighter plums. Every actual hue on the page is a
brand value.

Colour encodes coverage class and **nothing else**. The same value is reused verbatim in the
plate, the legend, the badges and the table, so the reader learns the mapping once.

### One CSS trap already hit

The legend's muted caption originally used `class="note"`, colliding with the global `.note`
yellow-callout rule and wrapping every legend caption in a callout box. It now uses `.dim`
and `.fade`. When adding a utility class, check it against the existing rules first — this
is the failure mode `frontend-design` warns about, and it is easy to miss because the page
still renders, just wrongly.

### Type

IBM Plex Sans for prose, IBM Plex Mono for every model id, count and timestamp. Plex has a
technical, instrument-like character that suits a monitoring page, and the mono face is
functional rather than decorative: `font-variant-numeric: tabular-nums` means molecule
counts and GB figures align for comparison down a column. Prose does not get tabular
figures. Fonts load from Google Fonts with real system fallbacks, so the page degrades
cleanly offline — the only network reference in the file, and a non-blocking one.

### Quality floor

Responsive to mobile (grids collapse at 820px), visible keyboard focus, reduced motion
respected, print stylesheet that drops the dark masthead and the filter controls. Wide
tables scroll inside their own container so the page body never scrolls sideways.

### Self-containment

No external scripts or stylesheets; plots inlined as base64 data URIs; GitHub links are
navigational only. These reports get archived and forwarded, and one that silently loses its
charts a month later is worse than no report. The cost is file size — roughly 250 KB
without plots, 600 KB with them — which is why `--plots` is opt-in.

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

- `figure_grid(items)` — shared renderer for any row of headline figures. The grid is a
  **fixed** four columns, not `auto-fit`: with eight cells, letting the browser choose
  stranded the last one beside a dead grey gap. The monthly snapshot's six figures use
  `.figures.six` (three columns) for the same reason.
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

If the user wants a visually different report, load the `frontend-design` skill and work
from these notes: knowing what each choice is doing makes it possible to replace a decision
coherently rather than layering CSS over it. Keep the data JSONs and re-render — the
expensive step is the isaura inventory, not the HTML.
