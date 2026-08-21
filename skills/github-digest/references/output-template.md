# Digest output template

Exact structure for `digests/YY-MM-DD-github-digest.md` (local working copy) and
`ersilia-os/digests/github/YY-MM-DD-github-digest.md` (canonical remote path). The local
file is a staging area; `scripts/upload_digest.py` publishes it. Match this verbatim.

**Two governing principles:**
1. **Succinct, scannable, high-signal** — lead with takeaways, counts over prose, cap every
   list, a ~30-second read.
2. **Action before history** — things that need a human come first (attention items, registry
   drift), things already done come last (recent activity, the sync log). Order the chapters
   exactly as below.

Use **emojis to aid readability** — one on each chapter heading (from the set below) and the
work-type markers on activity lines. Keep them purposeful, not sprinkled: headings and markers
only, never mid-sentence in prose.

The digest is publicly hosted. GitHub usernames (`@handle`) are already public on the repos,
so attributing activity to a handle is fine — keep the tone factual and neutral. **Never** name
an internal Slack channel or paste anything not already visible on GitHub.

## File header

```markdown
# Ersilia GitHub Digest — Week of {YYYY-MM-DD}
```

The date is the **end** of the window. Proceed directly to the semaphore and legend.

## Connector status (semaphore) + legend

Immediately after the H1, render the connector semaphore and a one-line marker legend.
Each line ends with **two trailing spaces** for a hard line break.

```markdown
**Connectors:** GitHub 🟢 · Airtable 🟢
**Markers:** 🐛 Bug · ✨ Feature · 📄 Docs · 🔧 Infra · 🕒 Stale
```

- `GitHub` reflects `connector_status.github` (🟢 ok, 🔴 partial/failed). A partial status
  often means the custom-property read failed — alignment will be thin; say so there.
- `Airtable` is 🟢 if the registry was read and reconciled, 🔴 if that failed (then Registry
  alignment says so plainly rather than showing stale findings).
- Allowed emoji: the markers above, the chapter-heading emoji below, and 🟢/🔴. Nothing else.

## Chapters (fixed order — action first, history last)

```markdown
## ✨ Highlights
## ⚠️ Needs attention
## 🔧 Registry alignment
## 📊 Repository overview
## ✅ Recent activity
```

Go straight from each heading to its content — no framing sentence. If a whole chapter is
empty, write one italic line rather than a placeholder list.

---

### `## ✨ Highlights`

**2–4 sentences, no more.** A factual narrative of what mattered, from the `highlights` block
in `github.json` cross-checked against the activity buckets. Name the 1–3 repos with the most
movement and the single most important change; close with a one-clause registry-health read
(e.g. "registry in sync — no Status/Type drift"). Plain prose, no bullets. If the window was
quiet, say so in one sentence.

---

### `## ⚠️ Needs attention`  (ACTION — comes first)

Current open state (not window-bound). **Cap the lists** and state totals so nothing is hidden.

```markdown
### Stale pull requests
### Long-open issues
### 💡 Easy wins
```

- **Stale pull requests**: open non-model PRs with `stale: true`, most-stale first. Up to 10;
  if more, end with `_…and {N} more stale PRs._`
- **Long-open issues**: open non-model issues by `age_days` descending. Up to 10; append
  `_…and {N} more open issues ({total} open in total)._`

Per-item line for those two lists:

```markdown
- [{repo} #{number}]({url}) — **{title}** · open {age_days}d · last activity {days_since_update}d ago · @{author} 🕒
```

- Append 🕒 only when `stale` is true. Optionally note `· unassigned` when relevant; stay compact.
- If zero, write *Nothing stale this week.* / *No open issues.*

- **💡 Easy wins**: issues that look quick to resolve. `fetch_github.py` pre-flags candidates
  (`easy_candidate: true`, with `easy_reasons`) on `open_snapshot.open_issues`. **Apply
  judgement** — keep genuinely small, well-scoped work (docs, typos, small bugs, dependency
  bumps, clear one-liners) and **drop false positives** (model requests, vague discussions,
  anything needing design). Up to 5, best first:

```markdown
- [{repo} #{number}]({url}) — **{title}** · {why it's easy} · @{author}
```

  `{why it's easy}` is a 3–6 word reason you stand behind (e.g. "docs typo", "pin one
  dependency"), not a label dump. If nothing qualifies, write *No obvious quick wins this week.*

---

### `## 🔧 Registry alignment`  (ACTION)

`reconcile_airtable.py` findings (`health.json`): how the Airtable Repositories registry lines
up with GitHub. **Report-only** — a to-do list for a human. Lead with a one-line verdict, then
detail subsections (skip empty):

```markdown
{missing} missing · {ghost} ghost · {status_mm} status · {type_mm} type · {curation} uncurated.
```

(`missing` = `missing_from_airtable`; `ghost` = `stale_in_airtable`; `status_mm`/`type_mm` =
mismatch counts; `curation` = `missing_status` + `missing_type`.) If **every** alignment count
is zero: `Registry is in sync with GitHub — no action needed.`

```markdown
### Missing from registry
- [{name}](https://github.com/ersilia-os/{name}) — in GitHub, not in the Repositories table{ · archived}

### Ghost records
- `{name}` — in the registry (status {Status}) but no longer in the org (renamed/deleted)

### Status / Type mismatches
- `{name}` — Status: Airtable «{airtable}» vs GitHub «{github}»
- `{name}` — Type: Airtable «{airtable}» vs GitHub «{github}»

### Needs curation
- `{name}` — no Status{, no Type}

### Possibly out of date
- `{name}` — marked {Status} but had activity this week        (active_but_parked)
```

- Cap each subsection at ~15 lines; if longer, list 15 and append `_…and {N} more._`
- Airtable and GitHub share the same Status/Type vocabulary, so mismatches are real drift and
  normally few — list them all (within the cap), don't dismiss them as noise. `Status` is a
  multi-select in Airtable while the GitHub property is usually single-valued, so an Airtable
  value like «Completed, Archived» against GitHub «Completed» is a genuine finding: report both.
- Order `missing_from_airtable` with non-archived repos first, archived after.
- `metric_drift` is vestigial (the metric columns are gone from the table) — never render it.

---

### `## 📊 Repository overview`  (context)

Compact stratification of the **trackable** estate from the `repos` block. Three lines:

```markdown
{repos.trackable} tracked repos ({repos.model} model packages tracked separately) · {repos.archived} archived.
**By type:** Package {n} · Analysis {n} · App {n} · Automation {n} · Template {n} · Workshop {n} · Documentation {n}{ · unset {n}}
**By status:** In progress {n} · Completed {n} · Idle {n} · Discontinued {n} · Archived {n} · Todo {n}{ · unset {n}}
```

- Descending count (JSON is pre-sorted); omit zero buckets; show `unset {n}` only if present.

---

### `## ✅ Recent activity`  (completed — comes after the action items)

Non-model issue/PR activity inside the window, grouped (skip empty subsections), in order:

```markdown
### Pull requests merged
### Pull requests opened
### Issues closed
### Issues opened
```

Per-item line:

```markdown
- [{repo} #{number}]({url}) {work-type emoji?} — **{title}** · @{author} · {YYYY-MM-DD}
```

- Short repo name (no `ersilia-os/`). Date = the relevant event date (merged/created/closed).
- Work-type emoji (🐛/✨/📄/🔧) only when label/title makes it obvious; else omit. Never guess.
- Order within a subsection by repo name, then number.

Close with the **model-repo summary line** (always render, even if zero):

```markdown
**Model repos (eosXXXX):** {prs_merged} PRs merged · {prs_opened} opened · {issues_closed} issues closed · {issues_opened} opened — across {repos_touched} repos. Managed via the model-incorporation flow.
```

## Footer

No footer. The file ends after the model-repo summary line. No methodology block, no sign-off.

## Worked micro-example

```markdown
# Ersilia GitHub Digest — Week of 2026-06-18

**Connectors:** GitHub 🟢 · Airtable 🟢
**Markers:** 🐛 Bug · ✨ Feature · 📄 Docs · 🔧 Infra · 🕒 Stale

## ✨ Highlights
Busiest on `ersilia` and `zairachem-docker`. `zairachem-docker` cleared four long-standing
descriptor/scaffold bugs; the standout new PR is the `olinda` calibrator fix (#17). Registry
is in sync — no Status/Type drift.

## ⚠️ Needs attention

### Stale pull requests
- [model-validations #11](https://github.com/ersilia-os/model-validations/pull/11) — **Update reproducibility notebook** · open 847d · last activity 840d ago · @leilayesufu 🕒
_…and 14 more stale PRs._

### Long-open issues
- [griddify #1](https://github.com/ersilia-os/griddify/issues/1) — **Distance/similarity between features** · open 1535d · last activity 1534d ago · @miquelduranfrigola 🕒
_…and 334 more open issues (344 open in total)._

### 💡 Easy wins
- [isaura #20](https://github.com/ersilia-os/isaura/issues/20) — **Reader returns previous read data** · likely a small caching bug · @GemmaTuron

## 🔧 Registry alignment

1 missing · 1 ghost · 0 status · 0 type · 0 uncurated.

### Missing from registry
- [eosxxxx-dev](https://github.com/ersilia-os/eosxxxx-dev) — in GitHub, not in the Repositories table

### Ghost records
- `eos` — in the registry (status In progress) but no longer in the org (renamed/deleted)

## 📊 Repository overview
175 tracked repos (236 model packages tracked separately) · 45 archived.
**By type:** Analysis 68 · Package 67 · Automation 14 · Workshop 11 · App 7 · Template 5 · Documentation 3
**By status:** Completed 77 · In progress 43 · Archived 18 · Discontinued 18 · Idle 14 · Todo 4

## ✅ Recent activity

### Pull requests opened
- [olinda #17](https://github.com/ersilia-os/olinda/pull/17) 🐛 — **Fix broken isotonic calibrator** · @GemmaTuron · 2026-06-16

### Issues closed
- [zairachem-docker #38](https://github.com/ersilia-os/zairachem-docker/issues/38) — **All Nan descriptors** · @GemmaTuron · 2026-06-15

**Model repos (eosXXXX):** 0 PRs merged · 0 opened · 0 issues closed · 3 opened — across 29 repos. Managed via the model-incorporation flow.
```
