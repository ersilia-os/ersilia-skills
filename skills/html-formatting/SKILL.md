---
name: html-formatting
description: >
  Style any HTML — a web page, dashboard, report, landing page, web app, or Claude Artifact —
  into the recognisable Ersilia look and feel, and improve its UX at the same time. Covers not
  just aesthetics (the plum/periwinkle palette, Inter + mono type, the wordmark header) but the
  decisions that make Ersilia pages good: how sleek vs populated they are, how much to say about
  Ersilia and where, how help and methodology are delivered (progressive disclosure), and how to
  keep a page self-contained so it survives as an Artifact. Consult this skill BEFORE writing or
  restyling any HTML in an Ersilia context — default output tends to be too populated and not
  sleek; this makes it calm, brand-faithful, and self-contained. Triggers include: "make a
  website", "build an HTML page", "create a dashboard", "landing page", "web app", "make an
  artifact", "stylize/restyle this HTML", "make it sleek / less cluttered", "Ersilia look and
  feel", "apply the Ersilia style", "/html-formatting". Always use this skill whenever you are
  about to produce HTML for Ersilia, even if the request seems simple.
argument-hint: "[<html-file>] [--mode new|retrofit|check] [--archetype app|document|dashboard]"
allowed-tools: [Read, Write, Edit, Bash, WebFetch, AskUserQuestion, Artifact]
---

# HTML formatting — the Ersilia look and feel

You make HTML that is recognisably **Ersilia**: a calm, information-dense, self-contained page in
the plum/periwinkle house style, with the UX and verbosity decisions that make it *good*, not
just on-brand. The reference implementation is `ersilia-os/gradi-target-prioritization`
(`ersilia-os.github.io/gradi-target-prioritization/`); the authoritative palette is the `stylia`
package. This skill packages that into a reusable system.

**Consult-first.** Read this skill *before* you write any HTML for Ersilia — a page, a report, a
dashboard, or a Claude Artifact. You do not need the user to say "make it Ersilia". Default
output is usually too populated and not sleek; the whole point here is to fix that by design.

The standard lives in `references/` and `assets/`; deterministic scripts do the mechanical
assembly and the compliance check; your judgement does the structural mapping and the UX
improvements. This skill mirrors `repository-auditing` in shape.

---

## Modes

- **new** — you are creating a page from scratch. Scaffold from an archetype, fill it in.
- **retrofit** — you are restyling an existing HTML (yours or the user's). Apply the theme, keep
  the content, then map its structure onto Ersilia components and fix the UX.
- **check** — you just want to score an existing page against the house style (report-only).

Default: `retrofit` if given a file, `new` otherwise.

---

## Workflow

### Step 0 — Load the standard

Read these four references into context first (quote them, don't paraphrase):

- `references/design-system.md` — the tokens, typography and component library.
- `references/ux-and-verbosity.md` — sleek-not-populated, progressive disclosure, honesty.
- `references/ersilia-content.md` — what to say about Ersilia, the footer, favicon, logo.
- `references/layout-archetypes.md` — `app` / `document` / `dashboard` and when to use each.

`references/checks.md` documents the compliance checker; read it if a finding is unclear.

### Step 1 — Pick the archetype

Infer from the task (see the table in `layout-archetypes.md`): an interactive tool → `app`;
something read top-to-bottom → `document`; an at-a-glance overview → `dashboard`. Only ask the
user (with `AskUserQuestion`) if it's genuinely ambiguous. For a **retrofit**, match the page's
existing structure rather than forcing a re-layout.

### Step 2 — Build

**New:**
```bash
python scripts/apply_theme.py --mode new --archetype <app|document|dashboard> \
  --out <path> --title "<Wordmark>" --eyebrow "<Project>" \
  --lede "<one sentence>" --source-url "<repo url, if any>"
```
This scaffolds a self-contained page (canonical `<head>` with `ersilia.css` inlined + SVG
favicon, the archetype body, the credit footer). Then **fill it with real content** using the
components in `design-system.md` — replace the placeholder rows/cards, wire up any data.

**Retrofit:**
```bash
python scripts/apply_theme.py --mode retrofit <input.html> --out <path> \
  --title "<Wordmark>" --source-url "<repo url, if any>"
```
This swaps in the canonical head (theme + favicon), keeps the page's own `<style>` (cascading
after the theme), drops external CSS/font `<link>`s, and appends the footer. **Then do the real
work by hand:** map the page's structure onto Ersilia components (`.card`, `table.data`, the
wordmark header, the eyebrow, badges), replace off-brand colours/fonts with tokens, and apply the
UX improvements from `ux-and-verbosity.md` (trim sections, add progressive disclosure, fix
interactions). The script gets you a themed shell; you make it actually Ersilia.

### Step 3 — Apply the sleek-not-populated pass

Work `ux-and-verbosity.md` as a checklist: one `<h1>`; ≤ ~8 sections; one calm accent; no
decorative emoji; whitespace; mono tabular numbers; three greys max; provisional flagging; the
credit footer with source link. **Improve the UX, don't just paint** — collapse redundant
controls, add search/filter to long tables, add a Methods modal if the page makes scientific
claims, split overloaded views into tabs.

### Step 4 — Check and fix

```bash
python scripts/check_html.py <path> --date <YYYY-MM-DD>
```
Read the report. Fix every **Blocker** (self-containment) and **Should-fix** (off-brand
colours/fonts, missing attribution, clutter). Weigh the **Nice-to-have** heuristics with
judgement — a dense data page may legitimately trip `T1-CLUTTER-SECTIONS`; say so rather than
mangling it. Re-run until clean or until the residual is justified. Never silently ignore a
finding.

### Step 5 — Publish (if it's an Artifact)

The page is already self-contained and light-committed, which is exactly what the Artifact tool
needs. Load the `artifact-design` skill for publishing mechanics, then publish. Note in the page
that it commits to a **single light theme** on purpose (the Artifact "deliberately commits to one
look" exception) — do not bolt on a dark theme; the Ersilia brand is light.

---

## Things to avoid

- **External assets in anything that may become an Artifact.** No CDN CSS, Google Fonts, remote
  images. Inline everything; embed images as `data:` URIs. (`T0-SELF-CONTAINED`.)
- **Hard-coded hex colours.** Always `var(--…)`; derive shades with `color-mix`.
- **A foreign font stack.** Use `var(--sans)` / `var(--mono)`.
- **Decorative emoji** as section chrome. Status markers only; tag sections with the mono eyebrow.
- **Over-population.** Too many sections, six flat accent colours, a wall of text with no
  disclosure, a giant marketing hero. Sleek beats complete.
- **A marketing "About Ersilia" block** on the main view. Name in the eyebrow + footer; that's it.
- **Inventing brand colours or a dark palette.** Single light theme, tokens only.
- **A reskin that ignores UX.** The brief is "as good as possible" — fix functionality too.

---

## Relationship to other skills & tools

- **`artifact-design`** — general design fundamentals + Artifact publishing mechanics. This skill
  layers the *Ersilia identity + verbosity philosophy* on top; load `artifact-design` for the
  publish step and for anything this skill doesn't cover.
- **`dataviz`** — for charts/plots inside the page, defer chart craft to `dataviz`, but keep the
  colours consistent with the Ersilia palette here.
- **`stylia-plotting`** — the matplotlib equivalent. If a page embeds Ersilia figures, use
  `stylia` so the figures and the page share one palette (they are the same colours by design).
- **`repository-auditing`** — the sibling skill this one is modelled on (references carry the
  standard; scripts are deterministic; the checker is report-only).

---

## Scripts

- `scripts/apply_theme.py` — assembler. `new` scaffolds from an archetype; `retrofit` themes an
  existing page. Output is self-contained. `str.replace` token templating; stdlib only.
- `scripts/check_html.py` — compliance checker. Scores a page against `references/checks.md`,
  writes a tiered Markdown report (+ optional findings JSON). Report-only.
- `scripts/_common.py` — shared findings model + the `html.parser`-based HTML model and the
  canonical palette/font token sets.

Pass the real date to `check_html.py --date` — the scripts never call `datetime.now()`
(repo convention).
