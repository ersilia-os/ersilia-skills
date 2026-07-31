# Layout archetypes

Three layouts cover almost everything Ersilia builds. Pick one up front (the `--archetype`
flag to `apply_theme.py`), then fill it with the components from `design-system.md`. They share
the same tokens, type and components — only the skeleton differs. Each starter in `assets/`
(`starter-app.html`, `starter-document.html`, `starter-dashboard.html`) is a minimal, working
instance.

## 1. `app` — full-screen application (the gradi look)

**Use for:** interactive tools — an explorer, a selector, a filterable scorecard. Anything where
the user *works* with the data on one screen.

- Fixed **328px sidebar** (`.sidebar`, white, `border-right`) + fluid **`.main`**, laid out with
  `.app` (`grid-template-columns:328px 1fr; height:100vh; overflow:hidden`).
- **The shell never scrolls.** Data regions scroll internally via `.scrollwrap` (`overflow:auto;
  flex:1; min-height:0`). A 500-row table scrolls inside its panel; the header, controls and
  footer stay put.
- Sidebar holds: wordmark → `.wip` pill (if provisional) → controls (chips, switches, presets,
  search) → the compact credit footer at the bottom (`margin-top:auto`).
- Main holds: a `.toolbar` control row → the data region.
- Collapses to one column at the 900px breakpoint (built into `ersilia.css`).

**Variant — fixed sidebar, page scrolls.** For a dashboard people *scan* rather than
operate, the strict never-scrolling shell fights the content. Keep the sidebar
`position:fixed` and let the content column scroll normally with a `margin-left` equal
to the sidebar width, capped at ~1080px so wide cards stop stretching their charts.
Sidebar holds: wordmark → section nav (hue dot + label per section) → snapshot,
Methods and source pinned to the bottom with `margin-top:auto`.

At the 900px breakpoint the sidebar becomes a horizontal strip — and it must
**`flex-wrap:wrap` with the nav on its own full-width line** (`flex:1 0 100%` plus an
`order`). Without the wrap, the footer links claim the row and push the section nav off
screen entirely: the nav becomes unreachable on a phone, which is easy to miss because
the desktop layout is fine.

## 2. `document` — report / article

**Use for:** digests, write-ups, single-page reports, methodology docs. Something you *read*.

- Centered single column, `.document` (`max-width:980px; margin:0 auto`), generous vertical
  padding. The page scrolls normally.
- Header = `.brandhead` (eyebrow + wordmark + one-line lede).
- Body = `.section` blocks (quiet sentence-case `<h2>` label + content). Lead with the takeaway,
  keep prose tight, put data in `table.data`, tuck methodology behind a `<details>` or modal.
- Ends with the `.credit` footer.

## 3. `dashboard` — landing / overview

**Use for:** a landing page, a project overview, a "state of X" board. Something you *scan*.

- Centered wide container `.dashboard` (`max-width:1160px`).
- Hero = compact `.brandhead` wordmark (no marketing hero — see `ux-and-verbosity.md`).
- A **KPI row** of `.stat` tiles, then a responsive **`.grid`** of `.card`s
  (`repeat(auto-fill,minmax(240px,1fr))`).
- Use `.cbar` composite bars and `.badge`s inside cards. Ends with the `.credit` footer.

## Choosing

| If the page is… | Archetype |
|---|---|
| an interactive tool you operate on one screen | `app` |
| something you read top-to-bottom | `document` |
| an at-a-glance overview of tiles and cards | `dashboard` |

When unsure between `document` and `dashboard`: is the primary content **prose** (→ document) or
**metrics/cards** (→ dashboard)? For a retrofit, match the archetype to the page's existing
structure rather than forcing a re-layout — `apply_theme.py --mode retrofit` keeps the page's
body and just applies the theme; the deeper structural mapping is your judgement call.

## Dashboard grids: two layout traps that make panels balloon

Both of these were real bugs on a real dashboard, both looked like styling glitches, and
both were structural.

**1. A flexing chart must have `flex-basis: 0`, never `auto`.**

```css
.chart { flex: 1 1 0%; min-height: 110px; }   /* correct   */
.chart { flex: 1 1 auto; }                    /* unbounded */
```

With `auto`, the chart's *rendered* height counts as its own flex basis. A charting library
that resizes its canvas to fit therefore grows the card, which grows the grid row, which
grows the chart again — panels expand without bound. Any per-element `ResizeObserver` that
calls `resize()` also needs to be idempotent: compare against the last applied box, bail if
unchanged, and coalesce with one `requestAnimationFrame`, or the observer re-enters itself
forever.

**2. Nothing that expands in place may live in a grid row.**

Cards in a row share one height (`align-items: stretch`), so a `<details>` that adds 240px
of table to *one* card grows the row and stretches **every chart beside it**. Asking to see
one chart's numbers visibly ballooned its neighbours. Progressive disclosure inside a
tessellated grid belongs in a **dialog**, not an accordion: a dialog cannot move the page,
and a wide table finally gets room to be read. Keep the affordance a fixed-height button so
the card is exactly as tall whether or not the data is showing.

Regression-test it by measuring the row and every chart in it before and after the click and
asserting the two are identical. "It looks fine now" does not survive the next layout change.

## Rows must sum, and short lists must not spread

Group cards into explicit rows whose spans sum to the grid width, give each row a height
class, and let the cards stretch. That is what makes a page read as a dashboard rather than a
pile of cards — and it is worth a machine check, since a row summing to 11 fails silently.

The counterpart trap: a **category axis spreads its rows over the whole plot height**, so a
three-row ranking in a tall card comes out as dots marooned ~90px apart, reading as a broken
chart rather than a short list. Pad the plot area when the row count is low so the list
clusters at a sane pitch. And when you do, **pin the axis to label every row**
(`interval: 0` in ECharts): a shorter plot area makes the library decide the axis is crowded
and silently drop alternate labels, which deleted two of four income bands and left four
dots with two labels between them.

## The one-line caption budget is a function of card width

If captions are clamped to one line (`white-space: nowrap; text-overflow: ellipsis`), the
clamp does not save you — it truncates. A card three of twelve columns wide fits roughly
**40 characters**; five columns about 70. Write the caption for the card it lands in, at the
source, and assert `scrollWidth <= clientWidth` on every caption on every route. A complete
short sentence beats an elegant one cut off mid-word.
