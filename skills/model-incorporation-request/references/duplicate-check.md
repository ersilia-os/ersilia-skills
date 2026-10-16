# Reading the duplicate check

`scripts/check_duplicates.py` answers one question before anything is drafted: is this model
already requested in, or part of, the Hub? It reads three sources and never writes anywhere.

| Source | What it holds | What the script uses it for |
|---|---|---|
| `new-model` requests on ersilia-os/ersilia, open and closed | Publication and Source Code for every model requested since the form existed, including ones still In progress | exact match on DOI, arXiv id and repository |
| `ErsiliaModelsDOI.csv` in ersilia-maintenance | DOIs of published models, including those from before the request form | exact match on DOI |
| `ersilia_search` | The Hub catalogue: title, task, status, description | similar models by name and by task and endpoint |

Both an exact and a similar check are needed because `ersilia_search` has no DOI or
source-repository column. It can say that something resembles your model, never that your paper
is already in the Hub.

## Output

One JSON object: `verdict` (`exact`, `similar` or `none`), `exact`, `similar`,
`related_requests` and `notes`. For an exact match on a request, `repo` is the eosXXXX
repository the approval bot announced, or `null` if it never created one. A closed request with
no repo was not incorporated; do not guess why.

## Limits to keep in mind

- **A preprint and its journal version have different DOIs** and will not match each other.
  Search the base name too. Searching `MoLFormer` for GP-MoLFormer found the closed request for
  the original model, which no identifier would have.
- **`related_requests` is a loose name match.** Expect noise, such as a request that merely uses
  the tool as an input. Read the title before reporting it.
- **Models In progress usually have an empty Description**, so a text search misses them. The
  script scans the non-Ready models by name for this reason.
- **`ersilia_search` rejects `--limit` above 500**, and its table view truncates titles. The
  script uses `--csv`. If you run it by hand, do the same and never expand a truncated title.
- **One paper can legitimately have several Hub entries.** CReM is deployed as mutate and grow,
  and the four MolGrad models share one paper. An exact match means "ask what this request
  adds", not "refuse".
- **`gh` must be authenticated.** If it is not, or `ersilia_search` is missing, the script says
  so in `notes` and skips that part. Pass the note on rather than reporting a clean result.
