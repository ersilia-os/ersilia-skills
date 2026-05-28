# Source catalogue

Each source the digest can draw from, with endpoint, query shape, rate limit, and the script
that wraps it. Sources marked **MVP** are implemented in v1. Others are deferred to later
phases — note them in the digest footer as "not scanned this week" when run.

## Schema for normalised items

All `scripts/fetch_*.py` emit a JSON list where each item conforms to:

```json
{
  "title": "string",
  "authors": [
    {"name": "string", "affiliation": "string?", "country": "ISO2?"}
  ],
  "venue": "string",
  "date": "YYYY-MM-DD",
  "doi": "string?",
  "arxiv_id": "string?",
  "url": "string",
  "abstract": "string?",
  "source": "biorxiv|europepmc|arxiv|chemrxiv|slack|gmail|newsletter|...",
  "source_subtype": "string?",
  "raw": { "...": "source-specific payload, preserved for debugging" }
}
```

Fields without a `?` are required. `country` is filled in by `dedup_and_rank.py` (not the
fetcher) via affiliation parsing against `lmic-countries.md`.

---

## v1 (MVP) sources

### bioRxiv — `scripts/fetch_biorxiv.py`

- **Endpoint**: `https://api.biorxiv.org/details/biorxiv/{from}/{to}/{cursor}`
- **Auth**: none. Public API.
- **Date format**: `YYYY-MM-DD`.
- **Pagination**: 100 items per page; `cursor` is the offset.
- **Categories to keep**: `bioinformatics`, `biochemistry`, `pharmacology and toxicology`,
  `microbiology`, `systems biology`, `synthetic biology`, `genomics`, `molecular biology`
  (filter client-side; the API does not support category filters).
- **Rate limit**: undocumented. Be polite — 1 request per second; back off on 429.
- **Notes**: bioRxiv returns the *most recent revision* for each preprint in the window. A
  paper revised twice in the window appears once. Title and abstract are clean; affiliations
  are a single string per author.

### Europe PMC — `scripts/fetch_europepmc.py`

- **Endpoint**: `https://www.ebi.ac.uk/europepmc/webservices/rest/search`
- **Auth**: none for low volume; register a free email for higher quotas.
- **Query**: `FIRST_PDATE:[{from} TO {to}] AND ({keyword query})` where the keyword query is
  composed from `search-landscape.md` (methods × diseases × endpoints; OR-joined per group).
- **Format**: `format=json`, `resultType=core`, `pageSize=100`.
- **Pagination**: `cursorMark`.
- **Rate limit**: 10 requests/sec. Keep parallelism low (1–2).
- **Notes**: Covers peer-reviewed papers and Europe PMC-indexed preprints (overlaps with
  bioRxiv; dedup_and_rank handles this). Affiliation parsing in EPMC is structured per author.

### Slack — `scripts/fetch_slack.py`

- **Source**: claude.ai Slack MCP — `slack_search_channels`, `slack_read_channel`,
  `slack_read_thread`, `slack_read_user_profile`.
- **Workspace**: `ersilia-workspace`. Surface this in the connector semaphore alongside
  the channel name.
- **Target channel**: `#literature` if it exists; otherwise the closest match found by
  `slack_search_channels`. Log which channel was scanned in the connector semaphore and
  in the methodology footer.
- **Two-step pattern**: the MCP is not callable from Python subprocesses. SKILL.md Step 3
  tells Claude to collect messages via the MCP into `/tmp/slack_raw.json`, then invoke
  this script.
- **Date filter**: last 7 days ending today (Claude filters when collecting; the script
  has no date filter of its own).
- **Extraction**: URLs in messages (esp. DOI, bioRxiv, arXiv, GitHub, Hugging Face). Track
  the sharer for attribution.
- **Rate limit**: governed by the MCP layer; no explicit budget needed.

### Gmail — `scripts/fetch_gmail.py`

High-signal source — covers Google Scholar alerts (pre-tuned to the user's
research interests), publisher table-of-contents emails, curated newsletters,
and any thread where a collaborator shared a paper or code link.

- **Source**: claude.ai Gmail MCP — `search_threads`, `get_thread`,
  `list_labels`.
- **Two-step pattern**: same shape as Slack — Claude collects via MCP into
  `/tmp/gmail_raw.json`, then the script normalises. SKILL.md Step 3 has the queries.
- **Privacy rule**: the digest **never** names the inbox being read. The normaliser
  drops the raw sender email address from output items and labels the connector by
  what it covers (Scholar alerts, newsletters, collaborator mentions). The semaphore
  row reads `Alerts and Newsletters` (per `output-template.md`), not the email
  address.
- **Primary collection target — the user-maintained `Research-Updates` label.**
  The user files everything literature-relevant under one Gmail label. The
  single query `label:Research-Updates after:YYYY/MM/DD` returns the entire
  in-window stream and subsumes the per-sender buckets below. Always run it
  first; treat the per-sender queries as a fallback when the label is
  unavailable or empty.
- **Expected sender families inside the label** (use this list to know what to
  expect, not as a separate collection plan):
  - **Scholar alerts**: `scholaralerts-noreply@google.com`,
    `scholarcitations-noreply@google.com` — one paper or short list per email.
  - **Publisher ToC ealerts**: `ealert@nature.com` and `alerts@nature.com`
    (Nature, NMI, Nat Comms, Comm Chem, Comm Med, Comm Bio, npj * — including
    *npj Digital Medicine*); `journalalerts@acs.org` (JCIM, J Med Chem, ACS Med
    Chem Lett, ACS Infect Dis, ACS Omega, J Nat Prod); `updates@acspubs.org`
    (ACS most-read highlights); `WileyOnlineLibrary@wiley.com` (ChemMedChem,
    Clinical Pharmacology & Therapeutics); `cellpress@notification.elsevier.com`
    (Cell Reports, Cell, Cell Reports Medicine); `alerts@elifesciences.org`;
    `briefing@nature.com` and `scienceadviser@aaas.sciencepubs.org` for
    cross-domain news framing; `thelancet@notification.elsevier.com`;
    `email@emails.bmj.com`.
  - **Curated weekly digests**: `do-not-reply@semanticscholar.org` (5–10 papers
    matched to user feeds, with TLDRs); `digest@theacademicdigest.app`
    (5 papers per project keyword stack).
  - **Topical newsletters**: Substack-hosted newsletters (Asimov Press, Pat
    Walters, Owl Posting, Decoding Bio, etc. — extend the allow-list when new
    senders come on).
  - **Collaborator mentions** — only include threads whose body contains at
    least one DOI / arXiv ID / bioRxiv-or-chemRxiv URL / GitHub repo URL /
    Hugging Face URL.
- **ToC emails are dense and often blow the MCP per-thread output limit.** A
  single NMI Vol N No M or JCIM ASAP email can carry 20–30 paper links. When
  `get_thread` errors with "exceeds maximum allowed tokens", the response
  surfaces the on-disk path where the full HTML was saved — parse it with a
  short Python + regex snippet (Nature DOIs follow `s\d{5}-\d+-\d+-\w+`; ACS
  follow `10\.1021/acs\.<journal>\.[0-9a-z]+`). Then **always verify
  title → first author → DOI mapping via Crossref** before composing entries;
  the link order inside ACS ToC HTML does not reliably match the title order,
  and trusting the inline ordering is how v1/v2 of this digest fabricated
  several first-author names.
- **Scholar redirect unwrapping**: Scholar alert links are wrapped in
  `scholar.google.com/scholar_url?url=...`. The script unwraps them so dedup sees
  the canonical paper URL.
- **Ranker handling**: Slack and Gmail items often arrive with no abstract
  (Scholar/ToC snippets are very short). `scripts/dedup_and_rank.py` applies a
  +3 `community_curated` bonus to compensate so these items are not pruned by
  the keyword-only top-N cut. The LLM triage step is still the gate — the
  bonus only guarantees these items reach triage.
- **Rate limit**: governed by the MCP layer.

---

## Phase B sources

### arXiv — `scripts/fetch_arxiv.py`

- **Endpoint**: `http://export.arxiv.org/api/query`
- **Categories**: `q-bio.BM`, `q-bio.QM`, `cs.LG`, `cs.AI`, `stat.ML` (filter post-fetch).
- **Date filter**: arXiv's API does not filter by date directly; query with
  `cat:q-bio.BM AND submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]`.
- **Auth**: none. Be polite — ≤ 1 request/3s per arXiv guidelines.

---

## Phase C sources

### chemRxiv — `scripts/fetch_chemrxiv.py`

- **Endpoint**: `https://chemrxiv.org/engage/chemrxiv/public-api/v1/items`
- **Date filter**: `searchDateFrom` / `searchDateTo`.
- **Auth**: none.

### Semantic Scholar — `scripts/fetch_semantic_scholar.py`

- **Endpoint**: `https://api.semanticscholar.org/graph/v1/paper/search/bulk`
- **Auth**: API key recommended for >100 req/5min (free).
- **Use case**: citation-aware ranking; resolve preprint → published bridging via the
  `externalIds` field.

### Named-journal RSS — `scripts/fetch_journal_rss.py`

- **Source**: per-journal RSS feeds from Nature, ACS, Wiley, Cell Press, etc.
- **Maintained list**: `references/journal-feeds.yaml` (not yet created).
- **Notes**: many publishers throttle aggressively or require sign-in; degrade gracefully.

### Newsletters — `scripts/fetch_newsletters.py`

- **Source**: Gmail-delivered newsletters via the Gmail MCP.
- **Senders to track** (initial): The Decoding Bio, Asimov Press, Practical Cheminformatics
  (Pat Walters), Owl Posting. Add more in `references/newsletter-senders.yaml` later.
- **Date filter**: last 7 days.

### GitHub & Hugging Face — `scripts/fetch_github_huggingface.py`

- **GitHub**: `https://api.github.com/search/repositories?q=topic:drug-discovery+pushed:>{date}`
- **Hugging Face**: `https://huggingface.co/api/models?filter=chemistry&sort=lastModified`
- **Both**: optional API keys for higher quotas.

---

## Deferred to a future phase

- **Papers with Code** — useful but most chemistry items already appear via arXiv/bioRxiv.
- **LinkedIn** — needs Claude in Chrome / browser automation. Not set up.
- **Twitter/Bluesky** — high noise; revisit if a clean signal proves available.

---

## Failure handling

Every fetcher must:

1. Exit with code 0 if it returned a (possibly empty) JSON list.
2. Exit with code 0 (not non-zero) if the upstream API was unreachable — but log a clear
   `WARNING: {source} unreachable: {reason}` to stderr and write an empty list to `--out`.
3. The skill's `## Render` step reads stderr from each fetcher and lists the unreachable
   sources in the digest's methodology footer.

This is intentional: a flaky source must not abort the whole digest.
