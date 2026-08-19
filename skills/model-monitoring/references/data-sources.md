# Data sources, commands and known traps

Everything in this file was verified by running it. The traps in particular are not
guessable from the tools' `--help` output, and two of them have already produced a
plausible-looking but wrong report. Read this before running the scripts.

## Contents

- [Where the tools live](#where-the-tools-live)
- [Source 1 — isaura (what is stored)](#source-1--isaura-what-is-stored)
- [Source 2 — ersilia_search (what exists)](#source-2--ersilia_search-what-exists)
- [Source 3 — models-sif S3 bucket (what can run on HPC)](#source-3--models-sif-s3-bucket-what-can-run-on-hpc)
- [Source 4 — ersilia-maintenance (what was tested)](#source-4--ersilia-maintenance-what-was-tested)
- [Known traps](#known-traps)
- [Reference numbers](#reference-numbers)

---

## Where the tools live

Neither tool is on the default PATH, and they are in **different** conda environments:

| Tool | Environment | Path |
|---|---|---|
| `isaura` | `ersilia` | `~/anaconda3/envs/ersilia/bin/isaura` |
| `ersilia_search` | `ersilia-search` | `~/anaconda3/envs/ersilia-search/bin/ersilia_search` |

`scripts/_common.py` resolves these automatically, checking the standard conda roots
(`anaconda3`, `miniconda3`, `miniforge3`, `/opt/conda`), then `CONDA_PREFIX`, then PATH. It
exits with an actionable message rather than continuing when a tool is absent.

Resolving the binary from the environment prefix is preferred over `conda run`, which wraps
stdout and can mask exit codes — awkward when a script's whole job is to capture output.

**There is no GitHub CLI on this machine.** `~/anaconda3/envs/ersilia-search/bin/gh` is an
unrelated tool that shares the name; `gh auth status` fails against it with an argparse
error. Everything needed from GitHub here is public, so the scripts use plain HTTPS via
`urllib`. Set `GITHUB_TOKEN` only if a run ever hits an API rate limit.

---

## Source 1 — isaura (what is stored)

isaura holds the precalculated model outputs. Buckets:

```
isaura-public    public    http://83.48.73.209:8080/isaura-public
isaura-private   private
```

List them with `isaura info --remote`.

### Use `stats`, not `catalog`

Both list stored models. Use `stats`:

```bash
isaura stats -pn isaura-public -r -o <output-dir>
```

It writes `isaura_stats_<timestamp>.json` into the directory and returns clean, parseable
JSON that additionally carries each model's hub metadata.

`isaura catalog -pn isaura-public --remote` renders the same information as a Rich table
behind a live spinner, so its stdout is a thicket of ANSI escapes and carriage returns.
It is fine for a human at a terminal, and a poor parsing target.

Both walk the whole remote bucket, taking **about 30 seconds** — the slowest step in the
skill, though not a long wait. Keep the JSON and use
`fetch_coverage.py --reuse-stats <path>` while iterating on presentation.

### `stats` payload shape

```json
{
  "schema_version": "1",
  "producer": "isaura stats",
  "generated_at_utc": "2026-08-19T06:11:16.779903+00:00",
  "buckets": ["isaura-public"],
  "models_total": 231,
  "models": [
    {
      "bucket": "isaura-public",
      "model_id": "eos11sm",
      "model_version": "v1",
      "model": "eos11sm/v1",
      "molecules": 1355109,
      "total_bytes": 322171409,
      "total_gb": 0.300046,
      "n_columns": 3,
      "metadata": {
        "Status": "Ready", "Task": "Annotation",
        "Subtask": "Activity prediction", "Tag": "Antimicrobial activity",
        "BiomedicalArea": "Antimicrobial resistance", "TargetOrganism": "Any",
        "OutputDimension": 1, "PublicationYear": 2025
      }
    }
  ]
}
```

One record **per model version**, not per model. `molecules` is the coverage figure.

---

## Source 2 — ersilia_search (what exists)

The hub's search engine, backed by `https://search-engine-six-iota.vercel.app`. This is the
authoritative list of which models exist — isaura only knows about models it already stores,
so it cannot tell you what is missing.

```bash
ersilia_search --status Ready --limit 500 --csv
```

CSV columns:

```
Identifier, Slug, Title, Task, Subtask, Status, Description, Interpretation,
Tag, Biomedical Area, Target Organism, License, Publication Year, GitHub,
score, matched_keywords
```

**`--status Ready` is the population the report measures**, because those are the models
users can actually run: a missing artefact for a Ready model is a live gap, whereas an
Archived model was never going to be served and would only pad the denominator. 218 of the
247 known models are Ready.

`--all-statuses` (all 247) is available via `fetch_coverage.py --status all`. Watch what it
does to the classes: it makes the `orphan` count fall to near zero, because almost every
stored model is known to the hub under *some* status. Under the Ready-only default those
same models surface as `orphan` instead — stored artefacts for models that are no longer
served, which is a storage-reclamation signal rather than a coverage gap.

Valid `Status` values from `--list-facets`: `Ready`, `In progress`, `Archived`. Note the
maintenance reports and isaura's own metadata also use `In maintenance`, which is **not** a
search facet value — these systems do not share a single status vocabulary, so never assume
a status string from one source is valid in another.

---

## Source 3 — models-sif S3 bucket (what can run on HPC)

Built Singularity images live in the **`models-sif`** bucket of the Ersilia AWS account,
read with the AWS CLI (`/usr/local/bin/aws`) under the **`ersilia`** profile.

```bash
AWS_PROFILE=ersilia aws s3api list-objects-v2 --bucket models-sif --output json
```

**The bucket is `models-sif`, with a hyphen.** S3 bucket names cannot contain underscores,
so `models_sif` returns `NoSuchBucket`. This is worth remembering because the bucket is
usually referred to in conversation as "models_sif".

Keys are flat — no prefixes — one object per model version:

```
eos11sm_v1.sif      213,938,176 bytes    2026-06-10
eos157v_v1.sif    2,299,494,400 bytes    2026-08-04
```

so the pattern is `^(eos[0-9a-z]{4})_(v\d+)\.sif$`. `fetch_sif.py` reports any key that does
not match under `unexpected_keys` instead of dropping it: an unmatched key almost always
means the naming convention moved and images are about to be silently under-counted.

Images are far larger than the isaura payloads — a median of ~0.9 GB and a maximum of 5.7 GB,
against ~0.1 GB for a typical isaura model — so do not treat the two storage figures as
comparable per model.

`list-objects-v2` returns at most 1000 keys per response. The AWS CLI paginates
automatically, but `fetch_sif.py` still asserts on `IsTruncated`, because reporting from a
truncated listing would mark real images as missing.

`fetch_sif.py` takes the hub population from `coverage.json` rather than calling
`ersilia_search` again, so the isaura and Singularity percentages are always measured against
an identical set of models. Run `fetch_coverage.py` first.

---

## Source 4 — ersilia-maintenance (what was tested)

Public repo `ersilia-os/ersilia-maintenance`, read from
`https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/<path>`.

| File | Contents |
|---|---|
| `reports/weekly_model_testing.md` | Weekly shallow-test table: model, slug, ✅/🚨, timestamp |
| `reports/failing_models.md` | Models whose last test failed (Archived excluded) |
| `reports/updated_models.md` | Models whose upstream source moved on since packaging |
| `reports/monthly_health_report.md` | Current month's snapshot bullets, embeds the plots |
| `reports/monthly_health_history.json` | Per-month totals, one entry per month |
| `reports/health_and_testing.png` | Trend: ready passing / not tested / failing |
| `reports/issues_and_added.png` | Trend: open issues and models packaged per month |
| `reports/distributions_tasks_source.png` | Pies: models by subtask and by source type |
| `reports/model_report.md` | Full per-model report (not currently parsed) |
| `files/weekly_test_results.txt` | Raw test log, ~1.6 MB (not currently parsed) |

Outcomes are encoded as **emoji, not words**: `✅` passed, `🚨` failed, `ℹ️`
informational, `❓` unknown. Table headers are decorated too (`🧬 repository_name`), so
`fetch_maintenance.py` strips non-word characters to derive stable keys.

---

## Known traps

### 1. `wc -l` over-counts the search CSV by 2×

Model descriptions contain embedded newlines, so the byte stream has far more physical lines
than records: 247 models look like 500 lines. That number is doubly misleading because it
sits exactly at the `--limit` ceiling and reads like truncation.

Always parse with Python's `csv` module (`_common.parse_hub_csv`). Never count lines.

### 2. `--limit` is capped at 500, server-side

`--limit 501` and above return **HTTP 422 Unprocessable Entity**. There is no `--offset` or
pagination flag, so 500 is the hard ceiling on what this tool can report.

The hub is at 247 models, so there is headroom — but `fetch_coverage.py` **exits with an
error** if it ever receives 500 rows, rather than reporting a silently truncated coverage
figure. If that fires, the search API needs pagination; do not raise the limit.

### 3. The bucket is `isaura-public`, with a hyphen

`-pn 'isaura public'` (with a space) is not a valid bucket name.

### 4. The monthly history schema changed in 2026-06

Months up to 2026-05 use one set of `totals` keys; 2026-06 onward uses another:

| Until 2026-05 | From 2026-06 |
|---|---|
| `healthy` | `ready_passing` |
| `failing` | `ready_failing` |
| `never_tested` | `ready_not_tested` |
| `tested_at_least_once`, `outdated`, `no_open_issues`, `active_models` | `ready_total`, `archived` |

`total_models` and `with_open_issues` are stable across both.

This one bit already: reading only the old names rendered the three most recent months as
**0 passing, 0 failing**, which reads as the hub collapsing rather than as a rename.
`build_report.py`'s `_hv()` tries each known name and renders an em dash when a month
genuinely lacks a figure, so a real zero and an absent field stay distinguishable.

If the recent months ever go all-zero again, assume another rename and check the keys:

```bash
python3 -c "
import json,urllib.request
u='https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/reports/monthly_health_history.json'
for h in json.load(urllib.request.urlopen(u)):
    print(h['month'], sorted((h.get('totals') or {}).keys()))"
```

### 5. Dates parse as counts if you are careless

The monthly snapshot bullets are `- **Label:** N`. A naive `\*\*(...):\*\*\s*(\d+)` also
matches `**Generated at:** 2026-08-01` and records `generated_at: 2026` beside the real
model tallies. The regex carries a `(?![\d\-:.])` guard.

### 6. The two inventories legitimately disagree

The monthly health report counted **262** models while the search engine returned **247** on
the same day. They count different populations — repositories under maintenance versus
models indexed by hub search — so neither is wrong and there is nothing here to fix.

The report deliberately does **not** comment on the gap: it is expected, and explaining it
every week is noise. Use the search-engine figure for anything coverage-related, since that
is the population coverage is computed against. Only chase this if the gap changes sharply.

---

## Reference numbers

Measured 2026-08-19. Useful as a smell test — order of magnitude, not exact matches.

| Quantity | Value |
|---|---|
| Full reference collection | **1,355,109** molecules |
| **Ready** models in hub search (the population) | **218** |
| Models in hub search, all statuses | 247 (218 Ready, 25 Archived, 4 In progress) |
| Records in `isaura-public` | 231 model/version pairs |
| Distinct models with stored predictions | 196 |
| Models with more than one stored version | 20 |
| isaura `complete` / `partial` / `missing` / `orphan` | 192 / 0 / 26 / 4 |
| isaura coverage of Ready models | 88.1% |
| Total stored in isaura | ~453 GB |
| Objects in `models-sif` | 185 images for 166 models |
| `.sif` `available` / `missing` / `extra` | 162 / 56 / 4 |
| `.sif` coverage of Ready models | 74.3% |
| Models with more than one image | 19 |
| Total stored in `models-sif` | ~293 GB (median 0.9 GB, max 5.7 GB) |
| Monthly health report total | 262 models |

`partial` and `orphan` were both zero on this date. They are still computed, rendered and
tested (with synthetic fixtures) because the question the skill exists to answer explicitly
includes incomplete coverage, and an untested render path is one that breaks the first time
it is needed.
