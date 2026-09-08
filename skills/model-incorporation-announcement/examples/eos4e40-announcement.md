# Announcement — eos4e40 · chemprop-antibiotic

**Paper:** A Deep Learning Approach to Antibiotic Discovery — *Cell*, 2020 · [10.1016/j.cell.2020.01.021](https://doi.org/10.1016/j.cell.2020.01.021)
**Authors:** Jonathan Stokes (first) → James J. Collins (last), 20 total — first, last and a count, per the >5 rule

**Method paragraph checked against the abstract:** `publication.abstract` came back
**empty** — OpenAlex holds no abstract for this *Cell* paper and Crossref deposits none.
Claims were verified against the paper itself and the `Description` field instead, recorded
here so a reviewer knows the automated check did not run.

## Post

```text
New in the Ersilia Model Hub: Broad spectrum antibiotic activity

We are very excited to announce the incorporation of the model that helped find halicin — an antibiotic structurally unlike anything in clinical use.

Thanks to Jonathan Stokes, James J. Collins and 18 colleagues at MIT and the Broad Institute, the model scores any compound for its probability of inhibiting E. coli growth.

Their study in Cell trained it on a plain growth-inhibition assay, then screened chemical libraries for compounds structurally divergent from known antibiotics. Halicin, one of the molecules it flagged, held up in vitro and in vivo.

Paper: https://doi.org/10.1016/j.cell.2020.01.021
The authors' code: http://chemprop.csail.mit.edu/checkpoints

It now runs over your own compound set in one command, with no ML setup:

ersilia fetch chemprop-antibiotic

https://github.com/ersilia-os/eos4e40

Antimicrobial resistance kills hardest where treatment options are thinnest. Work like this counts for most when the researchers facing that burden can actually run it.

#AntimicrobialResistance #DrugDiscovery #OpenScience
```

## Profiles to tag

Authors only — Ersilia does not tag institutions. With 20 authors the post names the first
and the last, so those are the two looked up. Never tag a row marked `ambiguous` or
`unverified`.

| Author | Position | Profile | Status |
|---|---|---|---|
| Jonathan Stokes | first | `linkedin.com/in/jon-stokes-9ba30845` (Stoked Bio) **or** `linkedin.com/in/jonathan-michael-stokes-a79b26145` (Broad Institute) | **ambiguous** — two profiles for the same person. He was a Banting fellow at the Broad 2017–2021 and now runs a lab at McMaster plus the startup Stoked Bio, so the profile whose title *matches the paper* is the stale one |
| James J. Collins | last | none found | **unverified** — no personal profile surfaced, including a search restricted to linkedin.com. The one `/in/` hit for "James Collins" is a Pfizer senior scientist, a different person; every other result is a third party posting about him. Senior academics are often not on the platform |

**No profile page was opened** (LinkedIn returns HTTP 999 to non-browser clients).
