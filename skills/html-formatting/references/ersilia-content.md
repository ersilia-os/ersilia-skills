# Ersilia content — what to say, and how much

A page reads as Ersilia through a few precise, restrained content moves — not a paragraph of
"about us" on the front page. Name the org twice, link out, and stop.

## The two places Ersilia appears

1. **Eyebrow** (top of the page) — the mono periwinkle micro-label:
   `<span class="eyebrow brand">{Project} · Ersilia Open Source Initiative</span>`
   above the wordmark. This is the identity signature. That's all it needs to be.
2. **Footer credit** (bottom) — the attribution + source link.

Do **not** add a marketing "About Ersilia" block to the main view. The one-line mission belongs
in the footer at most.

## The canonical footer

`assets/footer.html` is the standard (assembled automatically by `apply_theme.py`). Its wording
mirrors the org-wide README footer in
`skills/repository-auditing/references/canonical-footer.md`, rendered as HTML:

```html
<footer class="credit">
  Brought to you by the <a href="https://ersilia.io" target="_blank" rel="noopener">Ersilia Open Source Initiative</a>
  — a tech-nonprofit fueling sustainable research in the Global South.<br>
  <a href="{source_url}" target="_blank" rel="noopener">⌥ Source code on GitHub ↗</a>
</footer>
```

- Keep the ersilia.io link and the "tech-nonprofit … Global South" clause. That clause is the
  one piece of mission copy that's welcome — it states who Ersilia is without a sales pitch.
- The **source link** is dropped automatically when no `--source-url` is given. Include it for
  anything with a public repo — foregrounding the source is part of the open-source posture.
- For the **app-shell** archetype the footer sits inside the sidebar (compact form); for
  document/dashboard it sits at the bottom of the page. `apply_theme.py` won't add a second
  footer if the body already contains a `.credit` block.

## Logo & favicon

- **Favicon:** a plain disc in one of the **official brand colours**, shipped as an
  **inline-SVG data-URI** in `assets/head.html`. No external file (CSP-safe). This is the
  default; don't reach for a raster, and don't reintroduce the old ring-and-dot "target" mark.
  - Keep it a solid disc. A favicon is seen at 16px, where any interior detail — a lattice, a
    ring, a glyph — collapses into a smudge. One shape, one colour, and the tab stays legible.
  - `apply_theme.py --favicon` picks the colour: `plum purple mint blue yellow pink orange
    egray`, a literal hex, `random`, or **`auto`** (the default).
  - **`auto` hashes the page title.** So a page keeps the same icon across rebuilds while
    different Ersilia pages get different ones — a tab strip of Ersilia tools stays
    distinguishable, and nobody's tab silently changes colour on a redeploy. Prefer it.
    Reach for `random` only for one-off pages, and name a colour when a page has an identity
    worth pinning (the repository browser is pinned to `plum`).
  - `egray` is selectable but never drawn by `auto`/`random`: a grey dot reads as a disabled
    or still-loading tab.
- **Logo image:** prefer the **typographic wordmark** over a raster logo (gradi does). The
  canonical raster is `assets/Ersilia_Brand.png` (org-wide), usually referenced from a README,
  not a web app. If a page genuinely needs the raster logo:
  - In a normal web page you may link it via its `raw.githubusercontent.com` URL.
  - In a **Claude Artifact**, external images are blocked by CSP — you must **embed it as a
    `data:` URI**, or stick with the wordmark. Don't leave a broken `<img>`.

## The social preview card

For a **hosted** page (not an Artifact), the link preview is part of the identity — it is what
people actually see when the page is shared on LinkedIn or in Slack.

- **The image is a screenshot of the page**, produced by `scripts/make_og_image.py`. Not a
  marketing card, not a logo on a coloured field: the page *is* the pitch, and a screenshot
  stays honest as the page changes. Zoom it (`--zoom 1.4`) so the wordmark, the title and the
  first rows of real content fill the card — the preview is rendered small.
- **The description is one plain sentence** saying what the page lets you do, in the same voice
  as the lede: *"Search, filter and browse every repository in Ersilia's open-source
  ecosystem."* No mission statement, no "empowering", no exclamation. It appears under the
  card, where a marketing line reads as noise.
- **`og:title` is the page title**, unchanged. Don't write a second, punchier title for social.
- Regenerate the image when the page's **design** changes, not when its data does — the card is
  an impression of the page, not a live view of it.

See the walkthrough in `SKILL.md` for the commands and the platform constraints (absolute URL,
1.91:1, LinkedIn's ~7-day cache).

## Links to use

- Ersilia home: `https://ersilia.io`
- Model Hub / code: `https://github.com/ersilia-os/ersilia`
- The page's own repo: `https://github.com/ersilia-os/<repo>` (the footer source link)

## Voice

Technical but plain, mission-aware, never salesy. Ersilia works on AI/ML for antimicrobial drug
discovery and global-health equity (an explicit LMIC / Global-South lens) — let that show
through *what the page is about and how honestly it's framed*, not through adjectives. See
`ux-and-verbosity.md` for the honesty conventions (provisional flagging, no overselling).
