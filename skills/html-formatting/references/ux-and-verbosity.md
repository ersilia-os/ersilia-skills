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

## Framing: a correct number can still ask the wrong question

The sharpest content note from a real review was not about a wrong figure. It was that a
Community section led with a churn ledger (joiners vs leavers vs net change, in green and
red) and a cohort-retention heatmap — *"the focus is too much on retention, which is
somewhat negative; it looks as if people leave very easily."*

Both charts were arithmetically correct. Both were the wrong question:

- **The denominator was doing rhetorical work.** "10% of joiners are still involved"
  describes an organisation whose contributors are mostly interns, students and fellows on
  fixed terms. Nothing leaked. The metric imported a retention standard from a context that
  did not apply.
- **A tiny cohort set the colour scale.** One 2020 member sitting at 100% made the ramp's
  maximum, squashing every real cohort into the pale end. Cohort grids need a floor on
  cohort size, or they are a picture of their smallest row.
- **The framing leaked onto the front page**, because the landing card quoted the lead
  chart's computed takeaway.

What replaced it measures participation: how many people have taken part (rising), how many
are involved *at once*, how long they stay, where they come from. Same table, same rows, no
spin — and the negative reading disappeared because the question changed.

Practical rules:

- **State a distribution as its commonest value, not as a share falling short of a
  threshold.** "48 of 102 ran 3–6 months, the most common length" and "93 of 102 lasted
  under six months" are the same numbers; only the second implies a target being missed.
  If there is no standard to fall short of, do not imply one.
- **Do not delete the honest bad news.** Keep the figure that shows a real decline and say
  it plainly. Removing a churn chart because it read as negative is right; suppressing
  concurrent headcount because it fell would be dishonest.
- **When two numbers wear the same label, one of them is wrong.** A hero tile read
  "Countries 25" (community + events) while another page read "45 countries" (organisations
  + community + events). Both correct, both labelled "Countries". Name the narrower one
  precisely or drop it.
- **Exclude the non-answers from a ranking, and say that you did.** A "target organism"
  ranking is dominated by "Any" (organism-agnostic) and "Homo sapiens" (a human property,
  not a pathogen). Dropping both turns a useless bar chart into the mission-relevant one —
  but the exclusion has to be stated in the caption and in Methods, or it is a silent edit.

## Derived metrics owe the reader their derivation

The most interesting figures are usually the ones nobody had subtracted yet: years between
a paper's publication and its packaging; the largest input batch a model completed. Neither
is a column in the source.

The second was inferred from five runtime columns where **`-1` means the model failed at
that size** — a convention a reader cannot possibly guess from the chart. If a number is
derived, Methods must say so and name the convention. Also state what was dropped and why:
three models whose incorporation year preceded their publication year were excluded,
because a negative lag means one of the two dates is wrong, not that a paper was wrapped
before it existed.

## Rate and total belong in one chart

A cumulative curve only ever rises, so on its own it cannot show whether growth is
accelerating or stalling. Putting the two behind a Cumulative / Per-period **toggle** is
worse than either: the reader can only ever see one, and toggles are for switching
*measure*, not for hiding half of one.

Draw them as two panels sharing one category axis — per-period bars above, running total
below, axis pointers linked. Never as two y-axes on one plot.