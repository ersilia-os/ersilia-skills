# Hub-DOI exclusion set

The review covers **novel** literature only. Any paper whose DOI is already attached to a
Hub model is dropped before screening (Step 5). This file is the source + the one-liner.

## Source

`ErsiliaModelsDOI.csv` — per-model publication metadata, maintained in the public
`ersilia-os/ersilia-maintenance` repo (~207 entries, refreshed by the maintenance pipeline).

```
https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/files/ErsiliaModelsDOI.csv
```

Columns: `model_id, slug, publication_type, doi, pdf, , Publication`. The `doi` column holds
either `https://doi.org/10....` or `-` (no DOI on record — skip those rows).

## Fetch + build the set

```bash
curl -s "https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/files/ErsiliaModelsDOI.csv" \
| python3 -c "
import csv, sys
hub = set()
for row in csv.DictReader(sys.stdin):
    doi = (row.get('doi') or '').strip()
    if not doi or doi == '-':
        continue
    # normalise: drop resolver prefix, lowercase
    doi = doi.lower().replace('https://doi.org/', '').replace('http://doi.org/', '').replace('doi:', '').strip()
    hub.add(doi)
print(len(hub))
import json
json.dump(sorted(hub), open('/tmp/hub_dois.json', 'w'))
"
```

This writes the normalised DOI set to `/tmp/hub_dois.json` and prints the count.

## Apply (Step 5)

Normalise every candidate DOI the same way (lowercase, strip `https://doi.org/`) before
membership testing. A candidate is **excluded** iff its normalised DOI is in the set.

- Match on **DOI only** — do not exclude on title/author similarity (too lossy).
- Preprints without a DOI cannot be matched; keep them.
- Record the number of candidates dropped — it goes in the report header
  (`Hub DOIs excluded: M`) and the in-chat summary.

## Notes

- If the fetch fails (network/egress), say so and proceed **without** exclusion rather than
  silently shipping a possibly-redundant review — flag in the report that exclusion was skipped.
- The CSV is the same source behind `hub-incorporation-criteria.md`'s priors; refresh
  expectations are the same (the maintenance repo updates it; always fetch live, never cache).
