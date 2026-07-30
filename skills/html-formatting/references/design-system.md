# The Ersilia HTML design system

The single source of truth is `assets/ersilia.css` — inline it, don't paraphrase it. This
file explains the *intent* behind the tokens so you apply them correctly. The palette is not
invented here: it is the official Ersilia brand palette from the `stylia` package (the same
colours Ersilia figures use) fused with the reference web implementation,
`ersilia-os/gradi-target-prioritization` (`app/styles.css`).

## The one rule

**Every colour, size and font comes from a token.** Never hard-code a hex value in a page —
use `var(--…)`. The compliance checker (`check_html.py`) flags any hex outside the palette.
When you need a lighter/darker shade, derive it with `color-mix(in srgb, var(--brand) 15%,
var(--surface))` rather than picking a new colour.

## Colour: identity vs interaction (this distinction matters)

Follow gradi's resolution exactly:

- **`--plum` `#50285A` is the brand *identity*.** In `stylia` it literally "replaces black" as
  the foreground of figures. On the web it appears in the **favicon**, the **wordmark accent**,
  and the **composite/score gradient** (`--purple` → `--brand`). Used sparingly, as a signature.
- **`--brand` `#6C5CE7` (periwinkle) is the interactive *primary*.** Links, focus rings, active
  states, sliders, the primary button. It harmonises with the data hues; plum would be too heavy
  for every link.
- **`--ink` `#2C3E50` is body text** (stylia's "soft off-black", never pure `#000`).

| Role | Token |
|---|---|
| Page background | `--bg #FAFAFC` |
| Cards / panels / sidebar | `--surface #FFFFFF` |
| Recessed fills (inputs, chips, zebra) | `--surface-2 #F4F4F8` |
| Hairline borders | `--border #E6E6EE` |
| Body / secondary / caption text | `--ink` / `--muted #6B6675` / `--faint #9A93A6` |
| Links, focus, active | `--brand #6C5CE7` |
| Good / warn / bad | `--good #3F9D6B` / `--warn #C98A1E` / `--bad #D9534F` |

**Data hues** (`--crimson --tangerine --amber --lime --turquoise --cobalt --periwinkle
--orchid --fuchsia`, plus the pastels `--purple --mint --blue --yellow --pink --orange`): use
these to **encode a variable** — one hue per axis/category/organism — *not* as decoration. If a
colour isn't carrying information, it should be a neutral. Using many hues flat is the fastest
way to look cluttered (the checker's `T2-ACCENT-SPRAWL`).

Shadows are **plum-tinted** (`rgba(80,40,90,.07)`), not neutral gray — a subtle brand signature.

## Typography: two families, mono does the signature work

- `--sans` = **Inter** → system-ui fallback. Inter is *named but not loaded* (external fonts are
  blocked by the Artifact CSP); the system fallback is 95% of the look. Embed Inter as a base64
  `@font-face` only when pixel-perfect type is essential.
- `--mono` = a `ui-monospace` stack, reserved for **data**: every number uses mono +
  `font-variant-numeric:tabular-nums` (class `.num` / `.mono` / `.stat .v`), so digits line up in
  columns. IDs and accessions too. **Mono earns its place on numbers, not on chrome.**
- **Labels are quiet, not shouty.** The eyebrow, section headings, stat labels and table column
  heads are **sentence-case sans, `--muted`, weight 500–600, no letter-spacing** (see `.eyebrow`,
  `.section > h2`, `.stat .k`, `table.data th`). **Do not use `text-transform:uppercase` for
  chrome** — stacked uppercase micro-labels read as techy and undercut the neutral, sleek feel we
  want. (The checker flags uppercase overuse as `T2-UPPERCASE`.)
- **Italic carries meaning:** organism and gene names are always italic (`.gene`, `i.sci`),
  per biological nomenclature.
- **Weights:** 400 body; **540/560** for buttons and labels (a deliberate semi-bold); 600 for
  emphasis and numbers; 700 for the wordmark and hero figures.
- **Small and dense:** 13px base, 11–12px tables, 10–11px labels. Ersilia pages are information-
  dense but quiet — not big-type marketing pages.

## Components (all in `ersilia.css`)

- **Wordmark header** — `.brandhead` = an `.eyebrow.brand` line (`… · Ersilia Open Source
  Initiative`, mono periwinkle) above an `<h1 class="wordmark">` whose accent word is
  `<em>` (italic periwinkle). No logo image; a typographic wordmark is the default.
- **Eyebrow** `.eyebrow` — the quiet sentence-case sans micro-label (muted; `.brand` variant is
  periwinkle). Use it to tag a section or set context, instead of decorative emoji.
- **Cards / panels** `.card`, `.panel` — white, hairline border, `--radius` 14px, soft shadow.
- **Stat tiles** `.stat` (`.k` label / `.v` mono value / `.d` sub) — the KPI row.
- **Buttons** — quiet by default; `.primary` is periwinkle. **Pills/chips** `.pill`/`.chip`
  (fully rounded, mono); pressed state is a periwinkle `color-mix`. **Switch** `.sw` (turquoise
  when on).
- **Badges** `.badge` — pastel, derived from a hue via `--c` (`style="--c:var(--mint)"`), with
  `.good/.warn/.bad` shortcuts. Text is a darker mix of the same hue.
- **Data tables** `table.data` — quiet sentence-case sticky headers, zebra rows via `color-mix`,
  right-aligned mono numeric cells (`td.num`). Wrap wide tables in `.scrollwrap` so the region
  scrolls, not the page.
- **Composite bar** `.cbar > .fill` — the plum→periwinkle identity gradient, for a 0–1 score.
- **Honesty pill** `.wip` + `.provisional` hatch — see `ux-and-verbosity.md`.
- **Footer credit** `.credit` — the attribution block; see `ersilia-content.md`.

## What to inline where

`apply_theme.py` inlines `ersilia.css` into a single `<style>` in the canonical `<head>` and,
for a retrofit, appends the page's own styles *after* it (so tokens are available and page rules
still cascade). You rarely write the `<head>` by hand — run the assembler. When you do write
markup, reach for the classes above before inventing a new one.
