# Compliance checks

The catalogue `check_html.py` runs. It is **report-only** — it flags, with a concrete fix, and
never edits the page. Findings carry a stable `id`, a **tier** (T0 identity → T2 polish), a
**severity** (`Blocker` / `Should-fix` / `Nice-to-have`), and a `confidence` (`high` for
deterministic checks, `medium` for the heuristics that can be fooled).

**Guiding rule:** *a skipped check is never a pass.* When a check can't be evaluated (no CSS, no
font set), it goes to the report's **Checks not run** section — silence must never read as clean.

## T0 · Identity & self-containment

| id | severity | fires when | fix |
|---|---|---|---|
| `T0-SELF-CONTAINED` | Blocker | any external `<link rel=stylesheet>`, web font, `<script src>`, or `<img src>` on an off-document host survives in the page | Inline it (CSS/JS in-page, images/fonts as `data:` URIs). Artifacts block all external hosts via CSP — external assets silently fail. |
| `T0-ATTRIBUTION` | Should-fix | the page contains no `ersilia.io` link | Add the canonical credit footer (`assets/footer.html`). |

## T1 · House style

| id | severity | fires when | fix |
|---|---|---|---|
| `T1-COLOR-OFFBRAND` | Should-fix | a hex colour outside the `ersilia.css` palette appears in the CSS | Replace with a token (`var(--plum)`, `var(--brand)`, `var(--ink)`, a data hue). Derive shades with `color-mix`, don't hard-code. |
| `T1-FONT-FOREIGN` | Should-fix | a `font-family` is set using a foreign stack (Segoe UI / Arial / Roboto / -apple-system) with **no** Ersilia family (Inter / mono) present | Use `var(--sans)` and `var(--mono)`. |
| `T1-FAVICON` | Nice-to-have | no `<link rel="icon">` | Add the inline-SVG target favicon (`assets/head.html`). |
| `T1-CLUTTER-SECTIONS` | Should-fix | more than **8** top-level `<h2>` sections (heuristic, medium confidence) | Merge/drop sections; push detail behind progressive disclosure. |
| `T1-MULTI-H1` | Nice-to-have | more than one `<h1>` | Keep a single wordmark `<h1>`; demote the rest. |

## T2 · Polish & accessibility

| id | severity | fires when | fix |
|---|---|---|---|
| `T2-EMOJI-HEADINGS` | Nice-to-have | a heading contains decorative emoji | Drop it; emoji are status markers only. Tag sections with the eyebrow label. |
| `T2-UPPERCASE` | Nice-to-have | more than **2** `text-transform:uppercase` rules (medium confidence) | Prefer quiet sentence-case sans labels; reserve uppercase for a single deliberate accent, not every micro-label. |
| `T2-WALL-OF-TEXT` | Nice-to-have | > **6000** chars of prose **and** no `<details>` / `data-tip` / `.hovertip` / `.modal` (medium confidence) | Layer the detail behind a disclosure device. |
| `T2-ACCENT-SPRAWL` | Nice-to-have | more than **4** distinct data-hue vars used (medium confidence) | Let one accent (periwinkle) carry interaction; use hues only to encode a variable. |
| `T2-IMG-ALT` | Nice-to-have | an `<img>` has no `alt=` | Add descriptive `alt` (empty `alt=""` only for decoration). |
| `T2-DOCTYPE` | Nice-to-have | no `<!doctype html>` | Start with `<!doctype html>` (the assembler adds it). |

## Thresholds

The numeric thresholds live at the top of `check_html.py` (`MAX_TOP_HEADINGS=8`,
`WALL_OF_TEXT_CHARS=6000`, `MAX_FLAT_ACCENTS=4`, `MAX_UPPERCASE_RULES=2`). They are deliberately
loose — the goal is to
catch "populated, not sleek", not to nitpick a dense-but-intentional data page. Tune them there,
and keep this table in sync.

## Checking a JavaScript-rendered page

`check_html.py` parses the HTML as served. If the page builds its body at run time
(any dashboard that fetches JSON and renders charts), the checker sees an almost-empty
document, reports nothing, and **silence reads as a pass**. Snapshot the rendered DOM
first, then check the snapshot:

1. Serve the page and drive a headless browser to the route you want.
2. Inline the same-origin stylesheets into the clone (fetch each `<link rel=stylesheet>`
   and append a `<style>`), or every CSS-based check silently skips.
3. Write `document.documentElement.outerHTML` to a file and run the checker on it.
4. Repeat per route — a routed site has a different body per view.

**Disable the HTTP cache when you do this.** A cached stylesheet will happily serve the
*previous* design to your screenshots and your checks, which invalidates the result
without any error. `Page.navigate` does not take `ignoreCache`; use
`Network.setCacheDisabled` or `Page.reload({ignoreCache:true})`.

## What the checker does *not* do

It does not judge whether the *content* is good, whether the layout archetype was the right
choice, or whether the interaction actually works. Those are your judgement (see
`ux-and-verbosity.md`). The checker is a floor for brand + self-containment + obvious clutter,
not a substitute for design sense.

Above all it cannot see the things that actually make a page look bad: a card orphaned
beside a void, a truncated label, a clipped sparkline, a white tile with white text on
it, seven bars adrift in whitespace, or the same chart type twenty-six times. **Render
every view and look at it.** Every one of those examples is a real defect found by
looking at a screenshot after the checker had reported clean.
