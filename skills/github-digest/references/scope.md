# Scope — what the GitHub digest covers

The digest sweeps the entire **`ersilia-os`** GitHub organisation, but treats two classes
of repo differently.

## Model repos vs non-model repos

- **Model repos** are named `eosXXXX` — `eos` followed by four lowercase alphanumeric
  characters (regex `^eos[0-9a-z]{4}$`, see `scripts/_common.py:is_model_repo`). They are
  the Ersilia Model Hub model packages. There are ~237 of them. They have their own
  incorporation flow and are catalogued in a **separate** Airtable base ("Ersilia Model
  Hub" → `Models`), **not** the Repositories table this digest checks.
  - In the digest, model-repo issue/PR activity is **collapsed into a single summary line**
    (counts only) in the Recent-activity chapter. Do not itemise individual model-repo
    issues or PRs — that is the job of the model-incorporation workflow, not this digest.
- **Non-model repos** are everything else (~180): packages, apps, tools, analyses,
  templates, workshops, automation, documentation. These get **full itemised** treatment
  in the digest and are the repos reconciled against the Airtable Repositories table.

`fetch_github.py` does this split automatically: `activity.*` and `open_snapshot.*` already
contain only non-model items, and `model_summary` holds the aggregated model counts.

## Repos excluded from the Airtable registry-health check

`reconcile_airtable.py` compares **trackable** org repos against the Repositories table.
Trackable = first-party, non-model. Specifically excluded from the "missing from Airtable"
finding:

- **Forks** (`fork: true`) — not first-party work; the table does not catalogue them.
- **Model repos** (`eosXXXX`) — tracked in the other Airtable base.

**Archived** repos stay in scope: they should still be catalogued (typically with status
`Completed`, `Discontinued`, or `Archived`), so an archived repo missing from the table is
still a finding.

## GitHub custom properties (Type & Status)

`ersilia-os` publishes two **organisation custom properties** on every repo, **mirrored from
the Ersilia Content Airtable** by the nightly cron:

- `type` — `Workshop`, `Package`, `Analysis`, `Automation`, `Template`, `App`,
  `Documentation`, `Model`.
- `status` — `Todo`, `In progress`, `Completed`, `Archived`, `Discontinued`, `Idle`.

`fetch_github.py` reads them in bulk via `gh api --paginate orgs/ersilia-os/properties/values`
and attaches `gh_type` / `gh_status` (lists) to each repo, plus `repos.by_type` /
`repos.by_status` stratification counts over **trackable** repos (used in the digest's
Repository overview). Nearly all repos carry `type`; only the ~180 curated non-model repos
carry `status` (model repos are `type: Model` with no status).

### Alignment with Airtable (strict compare)

`reconcile_airtable.py` compares each side's Status and Type **strictly** (set equality of the
trimmed strings) for repos present on both sides, and reports both values when they differ
(`status_mismatch`, `type_mismatch`). Airtable and GitHub share the **same** Status vocabulary
(Todo, In progress, Completed, Archived, Discontinued, Idle) and the same Type vocabulary, so
the GitHub mirror should match Airtable exactly. A mismatch therefore means the nightly cron
lagged or one side was hand-edited — there is no expected systematic vocabulary noise.

The one value that exists only on GitHub is the **`Model`** type (model repos live in a
separate Airtable base), so it never appears in the Repositories-table comparison.

A side with an *empty* value is not a mismatch — that is the existing `missing_status` /
`missing_type` curation finding instead.

## Activity windows

- The **Recent activity** chapter uses the `--from`/`--to` window: issues opened, issues
  closed, PRs opened, PRs merged within it.
- The **Needs attention** chapter is a snapshot of *current* open state, not window-bound:
  open PRs and open issues across non-model repos, annotated with `age_days`,
  `days_since_update`, and a `stale` flag (default: no update in ≥ 30 days, `--stale-days`).
- For the exact chapter order in the digest (action items first), see `output-template.md`.

## Housekeeping (branches and forks)

`fetch_housekeeping.py` sweeps every **non-archived** repo, model repos included. Archived
repos are read-only on GitHub, so nothing in them can be tidied.

**Stale branches.** Never flagged: the default branch, protected branches, and branches
backing an open PR (those are covered by the stale-PR list). Flagged:

| Reason | Rule | Meaning |
|---|---|---|
| `merged` | its PR was merged ≥ 14 days ago (`--merged-grace-days`) | safe to delete |
| `closed` | its PR was closed unmerged ≥ 14 days ago | almost always safe to delete |
| `idle` | no PR, no commit for ≥ 90 days (`--branch-idle-days`) | ask the author |

Only the first 100 branches of a repo are read; a repo with more is listed in `errors` and
the status becomes `partial`.

**Forks.**
- *Org-owned forks* (`isFork` under `ersilia-os`): parent, last push, ahead/behind the
  parent's default branch. The decision (keep, archive, delete) is a human one.
- *Personal forks*: forks of org repos owned by a current **org member**, with no push for
  ≥ 180 days (`--fork-idle-days`). Forks by people outside the org are ignored — we can neither
  delete nor reasonably chase them. Former team members drop out once they leave the org.

**Where findings go.** One `housekeeping`-labelled issue per non-model repo with stale
branches; one roll-up issue in `ersilia-os/ersilia-maintenance` for model repos; org forks
only in the digest unless `--org-forks-repo` is given. Personal forks go to the person, not
an issue. Issues carry a hidden marker so a later run updates the open issue instead of
opening a duplicate.

**Who is assigned.** Assignment is how people find out: GitHub emails assignees, and the
weekly Slack nudges follow assignees. The body lists authors in backticks, never @mentions.
1. Branch authors who are current org members, most branches first, at most 3.
2. Else the repo's `CODEOWNERS` (individuals who are members; teams are skipped).
3. Else the member with most commits on the default branch in the last 12 months.
4. Else unassigned, and the digest lists the repo under *Unowned* for a human to triage.
Bot accounts (`ersilia-bot`, `*-bot`, `*[bot]`) are never assigned. Roll-up issues are not
assigned. **Nothing is ever deleted or closed by the skill.**

## Label → work-type hints (for grouping recent activity)

GitHub labels vary across ersilia-os repos, but these recurring ones help group activity by
theme when composing the digest. This is a soft hint for readability, not a hard taxonomy:

| Theme | Typical labels / signals |
|---|---|
| 🐛 Bug | `bug`, `fix`, titles starting "Fix"/"Bugfix" |
| ✨ Feature | `enhancement`, `feature`, `feat` |
| 📄 Docs | `documentation`, `docs` |
| 🔧 Infra / automation | `ci`, `infra`, `dependencies`, `automation`, Dependabot authors |
| 🧪 Model work | repo is `eosXXXX` (already summarised), or `model`, `incorporation` labels |

When labels are absent (common on ersilia-os), fall back to the repo name and PR/issue title
to place an item. Never invent a label that isn't there.

## Easy-win issues (script pre-filter + human judgement)

The digest surfaces a short list of open issues that look quick to resolve. The org barely
uses `good first issue` / `help wanted` labels, so this is **not** a pure label rule:

- `fetch_github.py` **pre-flags candidates** on `open_snapshot.open_issues`
  (`easy_candidate: true` with `easy_reasons`). Signals: an easy-ish label
  (`documentation`/`docs`/`low priority`/`question`/`good first issue`/`help wanted`/`typo`),
  a short title, recency (≤120d), and being unassigned. To qualify it needs a label hit **or**
  (short title **and** recent), and must not be stale.
- The skill then **applies judgement** over that bounded candidate set: keep genuinely small,
  well-scoped work (docs/typos/small bugs/dependency bumps/clear one-liners) and **drop false
  positives** (model requests, vague discussions, anything needing design). Cap the list at 5.

The pre-filter is deliberately loose so nothing easy is missed; the trimming is the skill's
job, not the script's.
