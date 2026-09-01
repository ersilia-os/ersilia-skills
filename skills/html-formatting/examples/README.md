# Examples

A before/after pair showing what the skill does to a typical off-brand page. Both are complete
HTML files — open them in a browser side by side.

## `before.html` — a typical un-styled dashboard

A plausible starting point: Bootstrap + Google Fonts from a CDN, GitHub-blue and green and red
hard-coded, pure-black text, a giant number in a boxed card, emoji in the `<h1>`, a wall of
intro prose, **seven** flat top-level sections, an external image, and no Ersilia attribution.

Running the checker on it:

```
$ python scripts/check_html.py examples/before.html
Verdict: 1 blocker · 3 should-fix · 3 nice-to-have.
```

- `T0-SELF-CONTAINED` (Blocker) — Bootstrap, the Google Font, and the remote image.
- `T0-ATTRIBUTION` — no `ersilia.io` link.
- `T1-COLOR-OFFBRAND`, `T1-FONT-FOREIGN`, `T1-CLUTTER-SECTIONS` (7 sections).
- `T2-EMOJI-HEADINGS`, `T2-IMG-ALT`.

## `after.html` — the same page, Ersilia

The structure mapped onto Ersilia components (`.brandhead` wordmark + eyebrow, a `.stat` KPI row,
`table.data` with pastel badges), off-brand colours/fonts replaced by tokens, the seven flat
sections collapsed into one `<details>` (progressive disclosure), the emoji dropped, the credit
footer with source link added, and the whole thing inlined so it is self-contained.

```
$ python scripts/check_html.py examples/after.html
Verdict: clean — the page matches the Ersilia house style. ✅
```

## How `after.html` was produced

The Ersilia-mapped body was assembled into a self-contained page by the skill's own assembler:

```bash
python scripts/apply_theme.py <mapped-body.html> \
  --out examples/after.html --title "Screening summary" \
  --source-url "https://github.com/ersilia-os/antibiotic-screen"
```

`apply_theme.py` inlined `assets/ersilia.css`, added the canonical `<head>` (SVG favicon), and
appended the footer. The **mapping** of the old structure onto Ersilia components and the
**clutter trim** (KPI tiles, badges, the `<details>`) are the judgement part — the script themes
the shell, you make it read as Ersilia. See `SKILL.md` Step 2–3.
