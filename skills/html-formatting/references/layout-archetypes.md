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

## 2. `document` — report / article

**Use for:** digests, write-ups, single-page reports, methodology docs. Something you *read*.

- Centered single column, `.document` (`max-width:980px; margin:0 auto`), generous vertical
  padding. The page scrolls normally.
- Header = `.brandhead` (eyebrow + wordmark + one-line lede).
- Body = `.section` blocks (mono uppercase `<h2>` label + content). Lead with the takeaway,
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
