# Author lookup — resolving who to credit, correctly

The credit rules are only as good as the names. This file is the procedure
`fetch_month_models.py` implements, what to do when it comes back thin, and how to get
names *right* — a misspelled author is a failed credit, not a typo.

The digest publishes nothing, so there is no profile lookup and no tagging worksheet here.
What matters is that the names, the order and the institutions in each paragraph are
correct.

## The two APIs

Both are free, need no key, and want a contact address in the query
(`mailto=hello@ersilia.io`) to stay in the polite pool.

**OpenAlex** — `https://api.openalex.org/works/doi:<DOI>` — is the primary source. It is
the only one of the two that gives:

- `authorships[].author_position` → `first` / `middle` / `last`, which is what makes
  "name the first and last author" a lookup rather than a guess
- `authorships[].institutions[].display_name` → affiliations, reliably populated
- `authorships[].countries` → ISO2 codes, used to spot Global-South institutions
- `authorships[].is_corresponding` → who to contact if a claim needs checking
- `open_access.oa_status` / `oa_url`, `cited_by_count`

**Crossref** — `https://api.crossref.org/works/<DOI>` — is the fallback and the
cross-check. Authoritative for the exact title, the journal name and the funder list;
its `affiliation` array is frequently **empty** (Elsevier, among others, does not deposit
it), which is why OpenAlex leads.

Where the two disagree on the author list, prefer Crossref for *spelling* (it is the
publisher's own deposit) and OpenAlex for *order and affiliation*.

## When the lookup comes back thin

- **An arXiv URL in `Publication`** — handled automatically. `normalise_doi()` converts an
  `arxiv.org/abs/…` or `/pdf/…` URL to the DOI arXiv mints for it
  (`10.48550/arXiv.<id>`), which OpenAlex then resolves. This is a deterministic mapping,
  not a guess. Note it as a metadata defect all the same: `Publication` is supposed to
  hold a DOI URL, and `/model-incorporation-metadata` should have written one.
- **No DOI and no arXiv URL in `Publication`** — nothing can be resolved. Ask the user for
  the author list. Do not write a post with no names; see `attribution-rules.md`.
- **DOI resolves in neither API** — very new DOIs can lag by days. Read the author list off
  the PDF instead, and record in the draft that names were transcribed by hand so a
  reviewer knows to check them.
- **Wrong affiliations, not just missing ones.** OpenAlex can resolve an institution
  *incorrectly*, and a wrong institution reads as authoritative in a report. For eos3xhm
  (HADES) it returned "Institute of Molecular Biology of the Slovak Academy of Sciences"
  and "Denso (United States)"; the paper says Denovo Sciences in Yerevan and the Armenian
  NAS — one country wrong, one company name mangled. So **check the institutions against
  the paper even when the API supplies them**, at least for the authors the post names.
- **Empty affiliations in both** — take institutions from the paper's title page. This is
  the normal case for **arXiv preprints**, which deposit no affiliation data at all: for
  eos9q2i (Mol-JEPA) OpenAlex returns five correctly ordered authors and zero institutions,
  and the affiliations only exist on the paper itself. Fetch the arXiv HTML
  (`arxiv.org/html/<id>`) rather than guessing, and record in the draft that they were
  transcribed by hand. Never infer an institution from an author's later career; the credit
  belongs to where the work was done.
- **Equal-contribution and multi-affiliation first authors** — name every institution the
  first author lists, in their order. Mol-JEPA's first author is affiliated with both a
  university and a company; dropping either misstates who did the work.
- **Consortium or group authorship** ("the X Consortium") — credit the consortium as named,
  plus any individual authors listed alongside it.

## Getting names right

This is the part that is easy to do badly and impossible to apologise for well.

- **Keep diacritics.** *Núria*, *Duran-Frigola*, *Müller*, *Şahin*. Copy the string from
  the API rather than retyping it. Stripping accents to "simplify" a name is a small
  erasure, and the people whose names carry them notice every time.
- **Do not reorder names.** APIs return given/family correctly for most records, but not
  all — Chinese, Korean, Vietnamese and Hungarian names are sometimes deposited
  family-name-first in the `given` field. If a name looks reordered, check the PDF's
  author line, which is authoritative.
- **Do not invent initials or expand them.** If the paper says "J. J. Collins", the post
  may say "James J. Collins" only if another source confirms the given name.
- **Titles.** Use none. The post names people as the paper does.
- **ORCID** is returned when available and is the cheapest way to disambiguate a common
  name.

## The Global-South lens

`fetch_month_models.py` flags `has_global_south_author` when any author's country appears
in the World Bank low- or lower-middle-income list (ISO2 set in `scripts/_common.py`;
canonical list with tiers and refresh cadence in
`event-discovery/references/lmic-countries.md`).

When it is true, **name those institutions explicitly** in the model's paragraph. This is
author credit, not organisational positioning — LMIC-led work in this field is
systematically under-cited, and naming the institution is the cheapest correction
available. When it is false, say nothing about it. A global-health framing bolted onto a
paper from a high-income lab is the kind of thing that reads as borrowed virtue.
