# UX & verbosity — sleek, not populated

This is the half of the skill that isn't colours. It answers the brief directly: *default
outputs are too populated and not sleek.* The Ersilia philosophy, taken from the gradi app, is
**quiet chrome + dense data, revealed progressively.** Aesthetics get you recognised; these
decisions get you *good*.

## The governing principle

**Sleek beats complete.** A first-time viewer should grasp the page in ~30 seconds. Depth is
not removed — it is *layered*, so the surface stays calm while the detail is one interaction
away. When in doubt, cut a section from the main view and move it behind disclosure.

## Progressive disclosure — the three tiers

Deliver help and detail in escalating tiers, never all at once:

1. **Surface** — terse labels, abbreviations, a single number. Quiet sentence-case labels, not
   sentences. (gradi shortens "essential" → "Es" on the surface.)
2. **`title=` / `data-tip` hover** — a one-line explanation on the control itself. Native
   `title=` for the cheap case; the styled `.hovertip[data-tip]` (dark bubble) for a richer
   sentence. Put the "what does this column mean" here.
3. **Methods / About modal** — the heavy scientific verbosity (formulas, data provenance, DOIs,
   references) lives in a `.modal`, one click deep via a "Methods ⓘ" button. It is *present* —
   Ersilia is rigorous — but never dumped on the main view.

If a page has a lot of prose and none of these devices, it is a wall of text (`check_html.py`
flags `T2-WALL-OF-TEXT`). Use `<details>` at minimum.

## Trim the clutter — concrete rules

- **One `<h1>`** (the wordmark). Everything else is `<h2>`/`<h3>`. (`T1-MULTI-H1`)
- **≤ ~8 top-level sections.** More than that reads as a dashboard nobody finished. Merge,
  drop, or nest. (`T1-CLUTTER-SECTIONS`)
- **One calm accent.** Let periwinkle carry interaction. Reserve the data hues for *encoding a
  variable*; a page splashed with 6 flat colours looks noisy. (`T2-ACCENT-SPRAWL`)
- **No decorative emoji.** Emoji are **status markers only** (🟢/🔴 as data) — never section
  chrome. Tag sections with the eyebrow label. (Same stance as `repository-auditing`;
  `T2-EMOJI-HEADINGS`.)
- **Whitespace is a feature.** Use the spacing rhythm in `ersilia.css`; don't pack panels
  edge to edge. Dense *data* is fine; dense *chrome* is not.
- **Numbers are mono + tabular** so columns align and scan. Prose is `--ink`; secondary is
  `--muted`; captions `--faint`. Three levels of grey, no more.
- **Kill hero bloat.** No giant marketing hero, no full-width gradient banner. The wordmark +
  eyebrow is the header. Get to the content.

## The default failure mode of a data page: one chart type, repeated

If you are building anything with more than a handful of charts, this is the thing
most likely to go wrong, and it will not look like a bug. One real dashboard shipped
with **62% of its charts being bar charts and 26 of 61 being the identical horizontal
bar.** Every chart was individually defensible; together they read as a wall of one
colour and the user's verdict was "too many barplots, everything is too blue".

Count your forms before you ship. Then:

- **The horizontal bar is almost always the wrong default.** A dot with a hairline
  leader (a lollipop) carries the same comparison with a fraction of the ink, and it
  does not become a 1000px smear when the card is wide.
- **Not every ratio is a chart.** A label, a number and a thin bar (a meter row) is
  often better. Several two-category splits belong in one card as stacked share bars,
  not in three cards as three donuts.
- **A top-N with several measures is a table**, with an inline microbar in the last
  column. One such table can replace three ranking charts and shows the columns a bar
  chart has to hide.
- **Two categories are never a pie.** One split bar, or a stat tile.
- **Size the card from the data, not from editorial rank.** A seven-category chart in a
  full-width card is seven bars adrift in whitespace; an eighteen-row ranking in a
  narrow card truncates every label. Derive the span from how many categories the
  metric actually has.

## Honesty as a design element

Ersilia pages are transparent about data maturity — it builds trust and it's the house style:

- Flag provisional/prototype work with the **`.wip` pill** ("Work in progress · prototype") and
  hatch provisional regions with `.provisional`.
- **`.wip` is amber and therefore a warning.** Do not reach for it for neutral metadata
  — a snapshot date, a "this table is not loaded yet" note. Those want a plain
  surface-2 pill; using `.wip` makes routine information look like a problem.
- Don't oversell. Copy is technical but plain: "Higher = better target", "lower is safer".
- State units, thresholds, and the date. If a number is a mock/placeholder, say so.

## Attribution & open-source posture

- Every page carries the **credit footer** (see `ersilia-content.md`) linking `ersilia.io`.
- Foreground the **source link** ("Source code on GitHub") when the page has a public repo —
  open-source transparency is part of the brand, not an afterthought.

## Functionality & interaction

- **Interactions are quiet and fast:** `--tap` transitions, `prefers-reduced-motion` honoured,
  focus rings visible (`:focus-visible`). No bouncing, no confetti.
- **Data regions scroll internally** (`.scrollwrap`), the page shell stays put — a table with
  200 rows shouldn't push the footer off-screen.
- **Everything keyboard-reachable**; real `<button>`s, not clickable `<div>`s.
- **Improve, don't just paint.** When restyling, also fix the UX: collapse redundant controls,
  add a search/filter if a table is long, add the Methods modal if the page makes scientific
  claims, split an overloaded view into tabs. The skill's job is "as good as possible", not a
  reskin.
