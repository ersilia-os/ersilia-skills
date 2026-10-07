# Airtable tables

Base **Ersilia Content**, `app1iYv78K6xbHkmL`. Verified live on 2026-09-29; Events and Organisations on 2026-10-07. The same IDs are in `scripts/_common.py` (`TABLES`), so keep the two in step.

Select options are also in `scripts/_common.py` (`CHOICES`, `KNOWN_YEARS`). `build_writes.py` refuses any other value, so update both when an option is added in Airtable.

"Stats" marks the fields the ersilia-stats site reads: an empty one drops the row from a chart. "Writes" is the policy in `rules.json`: `overwrite`, `fill_empty`, `flag` (never written), or `create` (set only on a new row).

## Repositories `tbluZtI3W9pseCSPH`

| Key | Field | ID | Type | Stats | Writes |
|---|---|---|---|---|---|
| name | Name | `fldtnOlLM2rqUZQpr` | text (primary; the repo slug) | | create; renames; the row is deleted when the repo is gone (approval only) |
| title | Title | `fldYNOnc9KYHcQb7B` | text | | never |
| description | Description | `fldBrXumaKuyUcgnH` | long text | | fill_empty from GitHub; copied to GitHub when only Airtable has one (not for archived repos) |
| status | Status | `fldbqy6izSeIK4L7M` | multi select: Todo, In progress, Completed, Archived, Discontinued, Idle | yes | choice when it disagrees with the GitHub property |
| type | Type | `fldaYAL5URJa3gnRB` | multi select: Workshop, Package, Analysis, Automation, Template, App, Documentation | yes | choice when it disagrees with the GitHub property |
| visibility | Visibility | `fldXhoqkmBs6ZRhnn` | single select: Public, Private | yes | overwrite |
| projects | Projects | `fldLxYAsHn1MDlOh4` | links to Projects | | never |
| creation_date | Creation Date | `fldBH2270474FY9XW` | date (GitHub `created_at`) | yes | overwrite |

`URL` (`fldvMLxQibv9YiJ1t`) is a formula on Name. Model repos (`eos` + digit + 3 characters) belong to the Ersilia Model Hub base, never here. The site takes the Public/Private split from Visibility, so a private repo marked Public would get its name published: that is the most urgent kind of fix.

## Publications `tbljYubYjWAtO1ab8`

| Key | Field | ID | Type | Stats | Writes |
|---|---|---|---|---|---|
| slug | Slug | `fldBcOxnF9AnbzfAA` | text (primary) | | create (judgement) |
| scholar_id | Google Scholar ID | `fldGKuzyPoWBt3ZBn` | text | | never (manual) |
| authors | Authors | `fldFQp6L6ErpBSTyS` | text | | create |
| title | Title | `flddeYa3EUx5eWVXL` | text | | create |
| journal | Journal | `fldmvLkFLT7v3qrew` | text | yes | fill_empty |
| url | URL | `fldMEidEAHAQEyrDr` | url | | create |
| doi | DOI | `fldHf5iG5y5Ub4Cym` | url, stored as `https://doi.org/…` | yes | fill_empty |
| status | Status | `fldAvDFvtrpgNgcIo` | single select: In progress, Preprint, Peer reviewed | yes | create |
| year | Year | `fldP37UlUVMWE9y2M` | single select, one option per year (2013–2026 so far) | yes | fill_empty; a new year option is created with typecast |
| affiliation | Ersilia Affiliation | `fldpo1rqH3ALxm4J0` | single select: Yes, No | yes | create |
| senior | Senior | `fldSjwNhFJonAK04F` | single select: Yes, No | | create (computed: an Ersilia author is last or corresponding) |
| topic | Topic | `fldM4DFkZnjxP9e6o` | single select: Bioinformatics, Chemoinformatics, Medical informatics, Molecular biology | yes | create (judgement) |
| type | Type | `fldfcaghlytTH0AOU` | single select: Research, Review | yes | create |
| african_collaboration | African collaboration | `fldLFGg2jkcP0IfGR` | single select: Yes, No | yes | create; fill_empty (computed: any author institution in Africa) |

The table deliberately includes team members' papers from before Ersilia (Ersilia Affiliation = No).

## Blogposts `tblsBj6ZoDNMlmrzm`

| Key | Field | ID | Type | Stats | Writes |
|---|---|---|---|---|---|
| slug | Slug | `fldXbpkgq9bE5lQSL` | text (primary) | | create |
| title | Title | `fldy4IdDdGDlvusvx` | text | | create |
| date | Date | `fldiJWivfdBCU0EBb` | date | yes | fill_empty |
| url | URL | `fldx3jkvfVcjP7Akv` | url | | tracking query stripped; repointed to the publication copy |
| author | Author | `fldsEdAuhkSboI9kU` | links to Community | | fill_empty |
| publisher | Publisher | `fld8HeAV2SiYL7vLw` | single select: Ersilia, Other | yes | create |
| category | Category | `fld5t5MIGbE6e8G2B` | multi select: Technology, Training, News, Global Health, Science | yes | create (judgement) |

Rows from other outlets (GitHub blog, Mozilla, SSI...) have Publisher = Other and are not checked against Medium.

## Community `tblS9TeBRYUpLwSCk`

Only `Name` (`fldMkjzLdEO4gNnZo`) is used, to link blog authors. It holds personal data: read it by name filter, never in full.

## Events `tbltd1A9nnXy6Ug8p`

Presentations, workshops and visits by Ersilia. Checked against dated Drive folders (see `sources.json`, `events`).

| Key | Field | ID | Type | Writes |
|---|---|---|---|---|
| name | Name | `fldv9qQr9FJjNnifz` | text (primary) | create (judgement) |
| description | Description | `fld79PPhYg0CRQNQF` | text, one sentence | create (judgement) |
| date | Date | `fld0IKh6ZrFoS0xci` | date | create (from the folder; judgement for a month-only folder) |
| url | Event URL | `fldu2MuK5xBIHQL4G` | url | create (judgement) |
| organisations | Organisations | `fldH50EYeERnwGvP2` | links to Organisations | create (judgement) |
| country | Country | `fldpAljFchUPIseO6` | links to Countries `tblujd4T9of8KAmP2` | create (judgement) |

`Videos` (links), `Quarter`, `Year`, `Organiser` and `Country (from Country)` are not written: the last four are formulas or lookups. Online events have no Country.

## Organisations `tblxKMlzYuoSzBaDC`

Only `Name` (`fldSE7d8F3XQlvBVT`) and `Website` (`fld5Yol2i0hMTVj83`) are used: an event's host is looked up by name, and created with these two fields when it is missing (approval only).
