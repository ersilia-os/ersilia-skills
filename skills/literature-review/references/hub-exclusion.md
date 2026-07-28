# Exclusion sets

The review covers **novel** literature only. A candidate is dropped before screening (Step 5)
if it is already **in the Hub** *or* already **in the incorporation pipeline**. There are two
independent exclusion sets — build both in Step 2, then apply **both** in Step 5. Keep them
separate: the Hub set is keyed by bare DOI, the pipeline set by prefixed keys (`doi:` / `arxiv:`
/ `repo:`), and their drop counts are tracked separately (Hub vs. pipeline).

1. **Hub set** — models already published to the Hub, keyed by DOI (`ErsiliaModelsDOI.csv`).
2. **Pipeline set** — models already *requested* / in progress, keyed by DOI, arXiv ID, and
   source-repo URL (the `new-model` issues on `ersilia-os/ersilia`).

The pipeline set exists because a model being incorporated has **no DOI in the CSV yet** — it
would otherwise surface as "novel" even though the team is already working on it.

---

## 1. Hub set (already published)

### Source

`ErsiliaModelsDOI.csv` — per-model publication metadata, maintained in the public
`ersilia-os/ersilia-maintenance` repo (~207 entries, refreshed by the maintenance pipeline).

```
https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/files/ErsiliaModelsDOI.csv
```

Columns: `model_id, slug, publication_type, doi, pdf, , Publication`. The `doi` column holds
either `https://doi.org/10....` or `-` (no DOI on record — skip those rows).

### Fetch + build the set

```bash
curl -s "https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/files/ErsiliaModelsDOI.csv" \
| python3 -c "
import csv, sys, json
hub = set()
for row in csv.DictReader(sys.stdin):
    doi = (row.get('doi') or '').strip()
    if not doi or doi == '-':
        continue
    # normalise: drop resolver prefix, lowercase
    doi = doi.lower().replace('https://doi.org/', '').replace('http://doi.org/', '').replace('doi:', '').strip()
    hub.add(doi)
print(len(hub))
json.dump(sorted(hub), open('/tmp/hub_dois.json', 'w'))
"
```

This writes the normalised DOI set to `/tmp/hub_dois.json` and prints the count.

---

## 2. Pipeline set (already requested / in progress)

### Source

The `new-model`-labelled issues on `ersilia-os/ersilia` (`🦠 Model Request: …`). **All states**
(open + closed) — a closed request is either already incorporated (also covered by the Hub set)
or was deliberately triaged out, and in both cases the team does not want it re-surfaced.

> Model incorporation does **not** happen through PRs on `ersilia-os/ersilia` (those are
> dependency bumps). The per-model work lives in separate `eosXXXX` repos; the aggregatable
> pipeline signal is the request issue. `repo_info.json` lists in-progress repos but carries no
> DOI, so it can't be matched against paper DOIs — the issues are the usable source.

Each issue body has `### Publication` and `### Source Code` fields. Coverage is imperfect (many
Publication fields are `_No response_`), so extract **three** key types and match on any of them:
DOI, arXiv ID, and normalised source-repo URL. Empirically ~200 of ~250 issues yield ≥1 key
(≈100 repos, ≈75 DOIs, ≈10 arXiv).

### Fetch + build the set

```bash
gh issue list --repo ersilia-os/ersilia --label new-model --state all --limit 500 \
  --json number,title,body > /tmp/newmodel_issues.json

python3 - <<'PY'
import json, re
issues = json.load(open('/tmp/newmodel_issues.json'))

def section(body, header):
    m = re.search(r'^###\s+'+re.escape(header)+r'\s*$(.*?)(?=^###\s+|\Z)', body or '', re.M|re.S)
    return m.group(1).strip() if m else ''

def pub_keys(pub):
    keys = set()
    if not pub:
        return keys
    u = pub.strip()
    m = re.search(r'10\.\d{4,9}/[^\s"\'<>)]+', u)          # embedded DOI (doi.org, chemrxiv, …)
    if m: keys.add('doi:' + m.group(0).lower().rstrip('.').rstrip('/'))
    m = re.search(r'nature\.com/articles/([a-z0-9\-]+)', u, re.I)   # nature.com -> DOI
    if m: keys.add('doi:10.1038/' + m.group(1).lower())
    m = re.search(r'arxiv\.org/abs/(\d{4}\.\d{4,5})', u, re.I)
    if m: keys.add('arxiv:' + m.group(1))
    return keys

def repo_key(url):
    if not url: return None
    m = re.search(r'(github|gitlab)\.com/([^/\s]+/[^/\s#)]+)', url, re.I)
    if m: return 'repo:' + (m.group(1)+'.com/'+m.group(2)).lower().replace('.git','').rstrip('/')
    return None

keys = set()
matched = 0
for it in issues:
    ks = pub_keys(section(it['body'], 'Publication'))
    r = repo_key(section(it['body'], 'Source Code'))
    if r: ks.add(r)
    if ks: matched += 1
    keys |= ks

total = len(issues)
unmatchable = total - matched
frac = unmatchable / total if total else 0
json.dump(sorted(keys), open('/tmp/pipeline_keys.json', 'w'))
print(f"pipeline: {len(keys)} keys from {matched}/{total} issues ({unmatchable} unmatchable)")
if frac > 0.30:
    print(f"WARNING: {frac:.0%} of new-model issues yielded no key — extraction may have "
          f"drifted (issue-form headings or Publication URL formats changed). Inspect a few "
          f"unmatchable issue bodies and update the regexes in this file.")
PY
```

This writes the prefixed key set (`doi:…`, `arxiv:…`, `repo:…`) to `/tmp/pipeline_keys.json`
and prints a **coverage line**.

### Coverage self-check (this is how the in-skill list stays trustworthy)

The pipeline set is fetched live every run, so it never goes stale — but its quality depends on
the regexes above still matching the issue-body format. That can drift **silently**: if the
GitHub request form changes its headings, or people paste URL shapes the regex doesn't know, the
script still returns a (smaller) number with no error. The coverage line is the guardrail.

- **Baseline:** ~200 / 250 issues yield ≥1 key (~20% unmatchable — mostly `_No response_`
  Publication fields with no repo either, which is expected and fine).
- **Action:** if the run prints the `WARNING` (>30% unmatchable), open a few of the unmatchable
  issues, see what format they use, and extend `pub_keys` / `repo_key` here. Surface the warning
  to the user rather than shipping a silently-degraded exclusion.

---

## Apply (Step 5)

For **every candidate**, build the same prefixed keys and test membership:

- `doi:<normalised doi>` — lowercase, strip `https://doi.org/`. Test against the Hub set
  (bare DOI) **and** the pipeline set (as `doi:<doi>`).
- `arxiv:<id>` — for arXiv candidates.
- `repo:<host.com/owner/repo>` — from the candidate's public repo URL (the 💻 signal), if any.

A candidate is **excluded** iff:
- its normalised DOI is in the **Hub** set, **or**
- any of its keys (`doi:`, `arxiv:`, `repo:`) is in the **pipeline** set.

Rules:
- Match on identifiers only — never on title/author similarity (too lossy).
- Preprints without any identifier cannot be matched; keep them.
- Record the two drop counts **separately**: `Hub DOIs excluded: M` and
  `Pipeline models excluded: P`. Both go in the report header and the in-chat summary.

## Notes

- If either fetch fails (network/egress, `gh` not authenticated), say so and proceed **without
  that set** rather than silently shipping a possibly-redundant review — flag in the report
  which exclusion was skipped.
- `gh` must be authenticated (`gh auth status`) for the pipeline set. In Claude.ai (no `gh`),
  the pipeline set may be unavailable — note it and rely on the Hub set alone.
- Always fetch both sources live; never cache. The maintenance repo and the issue tracker both
  move.
