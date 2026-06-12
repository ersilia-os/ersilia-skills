# Literature Search API Reference

> **Environment note:** In Claude.ai, direct HTTP calls to PubMed and Europe PMC may be
> blocked by the network egress policy. In that case, use `web_search` with `site:` prefixes
> as described in SKILL.md. The API patterns below apply in Claude Code / Cowork environments
> where the domains `eutils.ncbi.nlm.nih.gov` and `www.ebi.ac.uk` have been added to the
> network allowlist.

---

## 1. PubMed E-utilities (NCBI)

Base URL: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

### Search — esearch

Returns a list of PMIDs matching a query.

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?\
db=pubmed&term=<URL_ENCODED_QUERY>&retmax=20&retmode=json&sort=relevance"
```

Response path: `data["esearchresult"]["idlist"]` → list of PMID strings.

**Query syntax tips:**
- URL-encode spaces as `+`
- Use field qualifiers: `[Title/Abstract]`, `[MeSH Terms]`, `[Author]`
- Boolean: `AND`, `OR`, `NOT` (uppercase)
- Example: `PfDHFR+AND+malaria+AND+inhibitor[Title/Abstract]`

### Fetch abstracts — efetch

Returns full records (title, abstract, authors, journal, year) for a list of PMIDs.

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?\
db=pubmed&id=<PMID1,PMID2,...>&rettype=abstract&retmode=text"
```

For structured XML (easier to parse):
```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?\
db=pubmed&id=<PMID1,PMID2,...>&rettype=xml&retmode=xml"
```

### Summary — esummary (faster, lighter)

```bash
curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?\
db=pubmed&id=<PMID1,PMID2,...>&retmode=json"
```

Response path: `data["result"][pmid]["title"]`, `["authors"]`, `["pubdate"]`, `["source"]`

### Full Python pattern

```python
import subprocess, json, urllib.parse

def pubmed_search(query, max_results=20):
    q = urllib.parse.quote(query)
    cmd = f'curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={q}&retmax={max_results}&retmode=json&sort=relevance"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return data["esearchresult"]["idlist"]

def pubmed_fetch(pmids):
    ids = ",".join(pmids)
    cmd = f'curl -s "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={ids}&rettype=abstract&retmode=text"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout
```

**Rate limits:** 3 requests/sec without API key; 10/sec with `&api_key=<key>`.

---

## 2. Europe PMC

Base URL: `https://www.ebi.ac.uk/europepmc/webservices/rest/`

### Search

```bash
curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?\
query=<URL_ENCODED_QUERY>&format=json&pageSize=20&sort=CITED"
```

Response path: `data["resultList"]["result"]` → list of article objects.

Key fields per article: `pmid`, `title`, `authorString`, `pubYear`, `abstractText`,
`doi`, `journalTitle`, `isOpenAccess`

**Useful query operators:**
```
TITLE:"InhA" AND ABSTRACT:"inhibitor"
(HAS_FULLTEXT:y)                           # open-access full text only
FIRST_PDATE:[2019-01-01 TO 2024-12-31]    # date range
(SRC:MED OR SRC:PPR)                       # journals + preprints
```

### Full example

```bash
curl -s "https://www.ebi.ac.uk/europepmc/webservices/rest/search?\
query=Mycobacterium+tuberculosis+InhA+drug+discovery&format=json&pageSize=15&sort=CITED" \
| python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data['resultList']['result']:
    print(r.get('title'), '|', r.get('pubYear'), '|', r.get('doi','no-doi'))
"
```

---

## 3. Crossref (author and date verification)

Use Crossref to verify first-author surnames and publication dates before composing any entry.
Never fabricate author names — omit if lookup fails.

### By DOI

```bash
curl -s "https://api.crossref.org/works/<doi>"
```

Key fields: `message.author[0].family` (first-author surname),
`message.published["date-parts"][0]` (YYYY or YYYY-MM-DD),
`message.container-title[0]` (journal name).

### By title (when DOI unknown)

```bash
curl -s "https://api.crossref.org/works?query.title=<title>&filter=container-title:<journal>&rows=3"
```

Pick the result with the highest `score` and verify title similarity before using it.

### Python pattern

```python
import subprocess, json, urllib.parse

def crossref_by_doi(doi):
    cmd = f'curl -s "https://api.crossref.org/works/{urllib.parse.quote(doi, safe="")}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    msg = data.get("message", {})
    author = msg.get("author", [{}])[0].get("family", None)
    date_parts = msg.get("published", {}).get("date-parts", [[None]])[0]
    year = date_parts[0] if date_parts else None
    return author, year
```

---

## 4. bioRxiv / ChemRxiv

Neither source has a public keyword-search API. Use `web_search` instead.

### bioRxiv

```
web_search query: site:biorxiv.org <topic> drug discovery 2024
```

Then use `web_fetch` on the preprint landing page to extract DOI, title, authors, abstract, date.
bioRxiv DOI format: `10.1101/YYYY.MM.DD.NNNNNN`

### ChemRxiv

```
web_search query: site:chemrxiv.org <topic> ADMET OR "activity prediction" 2024
```

ChemRxiv DOI format: `10.26434/chemrxiv-YYYY-XXXXX`

---

## 5. Deduplication

After collecting results from all sources, deduplicate:
1. By DOI (exact match)
2. By PMID (for papers indexed in both PubMed and Europe PMC)
3. By title similarity (for preprints that later appeared in journals)

Keep the journal version when both preprint and published versions are found.

---

## 6. Pagination

- **PubMed**: add `&retstart=<offset>` for pages beyond the first 20
- **Europe PMC**: add `&cursorMark=<value>` (returned in `nextCursorMark`) for pagination
- **bioRxiv/ChemRxiv**: paginate via web_search with adjusted date ranges or query variants
