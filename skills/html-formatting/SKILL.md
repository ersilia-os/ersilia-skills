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

Either mode: if the page will be **hosted** at a public URL rather than published as an
Artifact, add the social-preview flags — see [Social preview](#social-preview-hosted-pages-only).

### Step 3 — Apply the sleek-not-populated pass

Work `ux-and-verbosity.md` as a checklist: one `<h1>`; ≤ ~8 sections; no decorative
emoji; whitespace; light chrome (450, colour carries state); three greys max;
provisional flagging; the credit footer with source link. **Improve the UX, don't just
paint** — collapse redundant controls, add search/filter to long tables, add a Methods
modal if the page makes scientific claims, split overloaded views into tabs.

**If the page has charts, count the forms.** A wall of one chart type is the commonest
way a data page fails, and it looks fine chart-by-chart — see the form-variety section
in `ux-and-verbosity.md`. On a multi-section dashboard, give each section its own hue
(`design-system.md`) rather than making everything the one accent.

### Step 4 — Check and fix

```bash
python scripts/check_html.py <path> --date <YYYY-MM-DD>
```

For a **JavaScript-rendered** page this must run against a snapshot of the rendered DOM,
with the HTTP cache disabled — otherwise the checker inspects an empty body, or a stale
stylesheet, and reports clean either way. See `checks.md`.

Then **render every view and look at it.** The checker validates colour and
self-containment; it cannot see an orphaned card, a clipped label, a white-on-white
tile, or the same chart repeated twenty times. Those are the defects that make a page
look bad, and looking is the only way to find them.

Read the report. Fix every **Blocker** (self-containment) and **Should-fix** (off-brand
colours/fonts, missing attribution, clutter). Weigh the **Nice-to-have** heuristics with
judgement — a dense data page may legitimately trip `T1-CLUTTER-SECTIONS`; say so rather than
mangling it. Re-run until clean or until the residual is justified. Never silently ignore a
finding.

### Social preview (hosted pages only)

A page that will be **shared as a link** — LinkedIn, Slack, X, WhatsApp — needs Open Graph
tags, or it previews as a bare card with only its title. The Ersilia preview image is a
**screenshot of the page itself**, not a marketing card:

```bash
# 1. build the page, then screenshot it into the 1.91:1 card
python scripts/make_og_image.py <page.html> --out og-image.png --zoom 1.4
# 2. rebuild with the tags, pointing at the URL the PNG will be served from
python scripts/apply_theme.py --mode retrofit <src.html> --out <page.html> \
  --title "<Wordmark>" --description "<one plain sentence>" \
  --url "https://<host>/<path>/" --og-image "https://<host>/<path>/og-image.png" \
  --og-image-alt "<what the screenshot shows>"
```

What actually breaks these cards, in order of frequency:

- **`og:image` must be an absolute `https://` URL.** A relative path or a `data:` URI cannot
  work — the crawler fetches the image from its own servers with no page context.
  `apply_theme.py` refuses to build rather than ship a silently broken card.
- **The image must be publicly reachable**, ~1.91:1, ≥1200px wide, under 5MB. 1200×630 at 2×
  (what `make_og_image.py` writes by default) is right.
- **`--zoom` matters.** LinkedIn renders the card a few hundred pixels wide; a 1:1 viewport
  crop turns 13px table text to mush. 1.3–1.5 for a dense data page.
- **The crawler runs no JavaScript** — which is fine, the tags are static — but it does mean
  the *screenshot* is the only way a JS-rendered page shows its content in a preview.
- **LinkedIn caches a preview for about 7 days.** After deploying, force a re-scrape at
  <https://www.linkedin.com/post-inspector/>. Do it *after* the deploy is live: a scrape that
  lands first caches the empty card.

None of this applies to an **Artifact** — it has no public URL, so omit the flags and ignore
`T1-SOCIAL-PREVIEW`.

### Step 5 — Publish (if it's an Artifact)

The page is already self-contained and light-committed, which is exactly what the Artifact tool
needs. Load the `artifact-design` skill for publishing mechanics, then publish. Note in the page
that it commits to a **single light theme** on purpose (the Artifact "deliberately commits to one
look" exception) — do not bolt on a dark theme; the Ersilia brand is light.

---

## Artifact or hosted site? The inlining rule depends on it

`T0-SELF-CONTAINED` fires on assets from an **off-document host**. Same-origin files are
not a violation, and the two targets want different things:

- **Artifact** — inline everything. External hosts are blocked by CSP, so a CDN
  stylesheet or a remote image silently fails. Embed images and fonts as `data:` URIs.
- **Hosted site** (GitHub Pages and similar) — same-origin `<link>` and `<script src>`
  are correct. Inlining a megabyte of chart library and a megabyte of map geometry into
  the HTML trades real page weight for portability you do not need. Note the choice in
  the page and the README so it does not read as an oversight.

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
- `scripts/make_og_image.py` — social-preview screenshotter. Serves the page locally (so its
  sibling data files load), captures it with headless Chrome, writes one 1200×630 @2× PNG.
  `--zoom` scales the page up so the card stays legible. Stdlib only.
- `scripts/check_html.py` — compliance checker. Scores a page against `references/checks.md`,
  writes a tiered Markdown report (+ optional findings JSON). Report-only.
- `scripts/_common.py` — shared findings model + the `html.parser`-based HTML model and the
  canonical palette/font token sets.

Pass the real date to `check_html.py --date` — the scripts never call `datetime.now()`
(repo convention).
