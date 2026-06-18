# Slack alert template — published digest notification

Sent **once** after a successful push to `ersilia-os/digests` — never on `--dry-run`, never
on failure, never on the `--no-readme` path mid-step. The skill only sends this when
`scripts/upload_digest.py` exits 0.

## Channel

Workspace `ersilia-workspace`. **Channel: `#coding` — ID `C01JL4SDKSL`.** This is where the
engineering team watches GitHub activity. (For reference, the literature digest posts to
`#literature` = `C010067BP2Q`.)

## Template

```markdown
🛠️ *New GitHub digest — week of {YYYY-MM-DD}*

Activity: {prs_merged} PRs merged · {prs_opened} opened · {issues_closed} issues closed · {issues_opened} opened (non-model repos).
Attention: {n_stale_prs} stale PRs · {n_open_issues} open issues. Registry: {n_missing} missing · {n_status_mm}+{n_type_mm} misaligned · {n_curation} need curation.

Read it on GitHub: {html_url}
```

## Field rules

- **Date** is the ISO end date of the window.
- Activity numbers come from `github.json` `counts`; attention/registry numbers from the
  open snapshot and `health.json` summary (`{n_status_mm}`/`{n_type_mm}` = `status_mismatch`/
  `type_mismatch`). Use the non-model figures (the model summary is in the digest itself, not
  the alert).
- Keep it to the three lines above — it is a pointer, not a summary. People click through.

## Worked example

```text
🛠️ *New GitHub digest — week of 2026-06-16*

Activity: 0 PRs merged · 4 opened · 8 issues closed · 1 opened (non-model repos).
Attention: 5 stale PRs · 349 open issues. Registry: 2 missing · 1+1 misaligned · 6 need curation.

Read it on GitHub: https://github.com/ersilia-os/digests/blob/main/github/26-06-16-github-digest.md
```

## Rules of decorum

- The 🛠️ prefix is the only allowed emoji in the alert.
- Do not name team members in prose (the activity is attributed by handle inside the digest,
  which is fine; the Slack pointer stays high-level).
- Do not post if the upload failed or was a dry-run — **only** on a confirmed successful push.
- Post exactly once per push, including `--force` re-pushes (the team should know it changed).
