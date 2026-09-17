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
| `website/assets/style.css` | `--digest-models` / `-hover`, `.has-mod`, `.swatch.mod`, `.nav-dot.is-models` |

### The colour

The calendar encodes each family by colour, and the four in use are literature mint
`#bee6b4`, github coral `#faa08c`, events blue `#8cc8fa`, and plum `#50285a` for a day
carrying more than one. Model incorporations take **amber `#eec95f`**, hovering to the
Ersilia brand amber `#e2a72e`. Amber is the one warm hue not already spoken for, and at
the calendar's 13px cell it stays distinct from the coral.

### `wide: true`

The site caps prose at 720px but lets table-first documents use a 1100px column. This
digest opens with a one-row-per-model summary table, so it takes the wide column for the
same reason the event reports do.

## A dating collision worth knowing about

The digest is dated the last day of the month it covers. Month ends are busy: August 2026
already carried both a literature and a github digest on the 31st, so that day renders as
the plum "multiple" cell rather than amber, and its link opens the literature digest.
Nothing breaks — the tooltip names all three and the sidebar and Recent list are
unaffected — but the family colour will not always be the one visible on the grid.
