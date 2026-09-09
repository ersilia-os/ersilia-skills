# Author lookup — resolving who to credit, correctly

The credit rules are only as good as the names. This file is the procedure
`fetch_model_context.py` implements, what to do when it comes back thin, and how to get
names *right* — a misspelled author is a failed credit, not a typo.

## The two APIs

Both are free, need no key, and want a contact address in the query
(`mailto=hello@ersilia.io`) to stay in the polite pool.

**OpenAlex** — `https://api.openalex.org/works/doi:<DOI>` — is the primary source. It is
the only one of the two that gives:

- `authorships[].author_position` → `first` / `middle` / `last`, which is what makes
  "name the first and last author" a lookup rather than a guess
- `authorships[].institutions[].display_name` → affiliations, reliably populated
- `authorships[].countries` → ISO2 codes, used to spot Global-South institutions
- `authorships[].is_corresponding` → the author most worth trying to tag
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
  name before looking for a LinkedIn profile.

## LinkedIn profile verification

**You cannot open a LinkedIn profile.** LinkedIn answers non-browser clients with
`HTTP 999 Unknown Status`; `WebFetch` on a `/in/` URL returns nothing. So verification
cannot mean "read the profile and check it" — it has to be built out of what search
results and independent sources give you.

Search-result titles are the lever. LinkedIn renders them as
**`Name - Employer | LinkedIn`**, so the title itself carries the affiliation without the
page being readable: *"Florian Rottach - Boehringer Ingelheim | LinkedIn"*.

The protocol:

1. Search the author's name plus their affiliation from the paper.
2. Read the **affiliation out of the result title** and check it against the paper.
3. Find **at least one independent source** tying that person to this paper or lab — a
   Google Scholar profile, an ORCID, a lab page, an institutional directory, a personal
   site. One source is a name match; two agreeing sources are an identification.
4. Record the status. Then stop — the human posting makes the final call in the composer,
   which is the only place the profile is actually visible.

### Statuses

| Status | Means | Taggable |
|---|---|---|
| `confirmed` | a human opened the profile and it matches | yes |
| `corroborated` | title affiliation matches **and** ≥1 independent source ties the person to this paper or lab | yes — human confirms in the composer |
| `ambiguous` | several candidate profiles, or a common name with nothing distinguishing | **no** |
| `unverified` | nothing found | **no** |

Only a human can write `confirmed`; the best this skill produces on its own is
`corroborated`. `check_post.py` R7 accepts either and fails on the other two.

### Two traps that came up on the first real lookup

- **A person can have two live-looking profiles.** Randall Balestriero moved from Meta AI
  to Brown CS in August 2024 and both profiles surface, one titled for each employer.
  Neither can be opened to see which is current, so the row is `ambiguous` — the poster
  picks in the composer. Career moves between preprint and incorporation make this common.
- **Common names collide.** "William Rudman" returns the UT Austin postdoc who co-wrote the
  paper and an unrelated person running a grant institute. The distinguishing evidence was
  his personal site and a Brown lab page, not the LinkedIn result. Record the exact URL, and
  say in the row that the name is shared.

### Institutions are not tagged

Only authors. Ersilia does not tag institutional pages, for two reasons that reinforce each
other: they are far more ambiguous than they look, and the payoff is small.

"University of Tübingen" surfaces at least four candidates — one `linkedin.com/school/…`
page and several `linkedin.com/company/…` pages with wildly different follower counts, one
of which is actually Paul Sabatier and CNRS. MIT has a `school/mit` page plus separate
pages for edX, Professional Education, Sloan and the School of Engineering. Picking wrong
tags the wrong institution in public, and getting it right buys reach that the authors'
own profiles already provide.

Name the institutions in the **post text** — the credit block requires it. Just do not
tag them.

### Which authors to look up

Look up exactly the authors **named in the post**:

- ≤5 authors → all of them, since the post names them all.
- >5 authors → the first and the last, since those are the two the post names.

Do not look up middle authors the post does not name; a profile nobody will tag is wasted
work, and an unused row invites someone to tag it later without re-checking.

## The Global-South lens

`fetch_model_context.py` flags `has_global_south_author` when any author's country appears
in the World Bank low- or lower-middle-income list (ISO2 set in `scripts/_common.py`;
canonical list with tiers and refresh cadence in
`event-discovery/references/lmic-countries.md`).

When it is true, **name those institutions explicitly** in the post. This is author credit,
not organisational positioning — LMIC-led work in this field is systematically
under-cited, and naming the institution is the cheapest correction available. When it is
false, say nothing about it. A global-health framing bolted onto a paper from a
high-income lab is the kind of thing that reads as borrowed virtue.
