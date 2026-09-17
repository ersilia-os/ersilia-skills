# Publishing to the digests site

The public copy of the digest is published to `ersilia-os/digests`, a Jekyll site served
at `ersilia-os.github.io/digests/`. This file records how that site actually works, because
two things about it are surprising and both cost time to rediscover.

## The digests have no YAML front matter

Every published digest is plain markdown beginning with its `#` heading. Jekyll would
normally treat such a file as a static asset and copy it through unrendered — which is
exactly what a plain local `jekyll build` does. The live site renders them because GitHub
Pages loads the `github-pages` gem, which bundles:

- **`jekyll-optional-front-matter`** — renders markdown that has no YAML header at all.
  Without it, nothing in `literature/`, `github/`, `events/` or `models/` becomes a page.
- **`jekyll-titles-from-headings`** — sets `page.title` from the first `#` heading, which
  is where each digest's `<title>` comes from.

So a local preview must name both plugins explicitly or it diverges from production in two
visible ways: the digests do not render, and once they do their `<title>` is the site name.

## Previewing locally

The site lives in `website/`, and the digests are copied into it at build time by
`.github/workflows/pages.yml` — they are **not** committed inside `website/`.

```bash
git clone --depth 1 https://github.com/ersilia-os/digests.git
cd digests
cp -r literature website/literature
cp -r github website/github
[ -d events ] && cp -r events website/events
[ -d models ] && cp -r models website/models

cat > website/_config.local.yml <<'YAML'
plugins:
  - jekyll-optional-front-matter
  - jekyll-titles-from-headings
YAML

cd website
JEKYLL_NO_BUNDLER_REQUIRE=true jekyll build \
    --config _config.yml,_config.local.yml --destination ../_site
```

`_config.local.yml` is a preview-only file and is not committed: on Pages those plugins
arrive with the `github-pages` gem.

Serve `_site` from a directory where it is named `digests`, because the site is built with
`baseurl: /digests` and its asset and page links are absolute:

```bash
mkdir -p preview && cp -r _site preview/digests
cd preview && python3 -m http.server 8787
# then open http://localhost:8787/digests/
```

On a system Ruby too old for current Jekyll, `gem install --user-install jekyll -v 3.9.5`
works once `ffi -v 1.15.5`, `i18n -v 1.14.8`, `public_suffix -v 4.0.7` and
`addressable -v 2.8.5` are pinned first. `JEKYLL_NO_BUNDLER_REQUIRE=true` stops Jekyll
trying to load the repo's Gemfile.

## Adding the models category

Five files, all in `ersilia-os/digests`. `references/digests-add-models-category.patch`
is the tested diff, built and previewed locally against that repo; the shape is:

| File | Change |
|---|---|
| `.github/workflows/pages.yml` | `if [ -d models ]; then cp -r models website/models; fi` — each category is copied **by name**, so a new folder is not picked up on its own |
| `website/_config.yml` | `- scope: {path: "models"}` → `layout: digest`, `wide: true` |
| `website/_layouts/base.html` | gather `modeldigests`, add the sidebar group and its dot |
| `website/index.md` | calendar: gather, date→URL lookup, a cell branch, a legend swatch, a "Recent" list |
| `website/assets/style.css` | `--digest-models` / `-hover`, `.has-mod`, `.swatch.mod`, `.nav-dot.is-models`, and scoping the existing column widths to `.family-events` |

### The colour

The calendar encodes each family by colour, and the four in use are literature mint
`#bee6b4`, github coral `#faa08c`, events blue `#8cc8fa`, and plum `#50285a` for a day
carrying more than one. Model incorporations take **amber `#eec95f`**, hovering to the
Ersilia brand amber `#e2a72e`. Amber is the one warm hue not already spoken for, and at
the calendar's 13px cell it stays distinct from the coral.

### Table column widths are per family

This family no longer emits a table, so it sets no widths and takes no `wide` column — the
config's own note is that widening prose only makes line length worse. The scoping below
still matters for any family that does add one.

The site's column widths were written for event-discovery's ten-column table but were
scoped to `.content`, so every family's table inherited them. A four-column digest was
handed 14%/5%/9%/9%, which put the Title column at 5% and left a third of the table
unallocated — with `table-layout: fixed`, nothing reclaims it.

The patch scopes those rules to `.family-events` and gives this family its own, keyed off
a `family:` value set in the `_config.yml` defaults and emitted onto the article element by
`base.html`. Any family adding a table from now on sets its own widths the same way rather
than inheriting somebody else's.

This family's four columns sum to 100% (Model 12, Title 40, Task 20, Authors 28) and the
table carries the body font size rather than the compressed size the ten-column event table
needs. Inline code in a cell is set to `1em` with no background, so the identifier and
author columns sit level with the prose columns instead of shrinking away from them.

## A dating collision worth knowing about

The digest is dated the last day of the month it covers. Month ends are busy: August 2026
already carried both a literature and a github digest on the 31st, so that day renders as
the plum "multiple" cell rather than amber, and its link opens the literature digest.
Nothing breaks — the tooltip names all three and the sidebar and Recent list are
unaffected — but the family colour will not always be the one visible on the grid.
