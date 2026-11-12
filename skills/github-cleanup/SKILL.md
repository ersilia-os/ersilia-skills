---
name: github-cleanup
description: >
  Interactively clean up your own GitHub backlog in the ersilia-os organisation:
  notifications about issues and PRs that are already closed or merged, noisy
  notifications (CI runs, subscriptions, old threads), reviews waiting on you,
  your stale pull requests, stale issues you opened or are assigned to, and
  branches you left behind after a PR was merged or abandoned. Scripts build a
  numbered plan; you walk the user through it one category at a time, and run
  only the gh commands they approve. Learns from feedback on every run.
  Triggers include: "clean up my GitHub", "github cleanup", "/github-cleanup",
  "triage my notifications", "clear my GitHub inbox", "close my stale issues",
  "which of my PRs are stale", "delete my merged branches", "what's waiting on me
  on GitHub". Always use this skill for these requests, even if the ask seems simple.
---

# GitHub cleanup

You help the user clear their own GitHub backlog in `ersilia-os`. Only items that involve them count: their notifications, their PRs and issues, the reviews requested from them, and the branches of their PRs. Other people's work is never touched.

## The one rule

**Never run a GitHub write without the user's explicit approval of those item numbers, in this run, given after they have seen them.** This holds in auto mode too. Closing, commenting, unassigning, marking a notification done, unsubscribing and deleting a branch are all writes. A plan, an earlier approval, or "it's obviously stale" is not approval. Never type a `gh` write command yourself: only `apply_actions.py` runs them, and it refuses anything outside its whitelist.

## How the work is split

Scripts decide which items are candidates and build the commands. You explain them, judge the items that need reading (reviews, stale PRs and stale issues), and ask the user. Every threshold lives in `references/rules.json`. If the plan gets something wrong, fix the rule (Step 6) rather than working around it.

Scripts run from `scripts/` with the Python 3 standard library and the `gh` CLI. They work in `/tmp/github_cleanup/`. If `gh` is not found, put Homebrew on the PATH first: `export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"`.

| Script | Does |
|---|---|
| `record_feedback.py` | Lists the lessons (`list`) or logs a new one (`add`) |
| `fetch_notifications.py` | Reads the inbox (ersilia-os threads only) and whether each subject is closed or merged. Slowest step, about 3 min |
| `fetch_mine.py` | Reads your open PRs, review requests, and issues you opened or are assigned to |
| `fetch_branches.py` | Reads the head branches of your PRs that still exist, about 2 min |
| `plan_cleanup.py` | Applies the rules and the ignore list, and writes the numbered plan |
| `render_plan.py` | Shows the plan as steps (`--steps`, `--step k`, `--step k --full`) |
| `build_actions.py` | Turns approved item numbers into gh commands; `--reject` keeps items for good |
| `apply_actions.py` | Runs only whitelisted commands, re-checks branches live, reads results back |
| `selftest.py` | Offline regression test over `examples/cases/` and the whitelist |

## Workflow

### 0. Pre-flight

1. `gh auth status`. If you are not logged in, stop and ask the user to run `! gh auth login`.
2. `gh api rate_limit --jq .resources.core`. A full run needs about 1,500 calls (the quota is 5,000 an hour, shared with every other gh tool). If fewer are left, tell the user when it resets and stop. Any script that hits the limit stops the run on purpose, because a plan built from partial data is wrong.
3. `python record_feedback.py list`. Read every lesson and apply it this run.
4. `rm -rf /tmp/github_cleanup && mkdir -p /tmp/github_cleanup`.

### 1. Fetch and plan (read-only)

The three fetches are independent. Run them in one command so they go in parallel:

```
python fetch_notifications.py & python fetch_mine.py & python fetch_branches.py & wait
python plan_cleanup.py
python render_plan.py --steps
```

Report any `partial:` line. Then give the user the list of steps and the totals in one short message, before you start the walkthrough.

### 2. Judge the items that need reading

Review requests, stale PRs and stale issues have no proposed action. For each one, read the thread before its step comes up: `gh pr view <n> -R ersilia-os/<repo> --comments` or `gh issue view ...`. Then propose an action from the item's `allowed` list:

- **Issue:** `close-completed` when the thread shows the work was done, for example a linked merged PR or "fixed in". Use `close-not-planned` when it was overtaken, duplicated, or nobody needs it any more. Use `unassign` when the work is real but no longer yours. Use `comment` to ask a question before closing.
- **Your PR:** `close` when it was superseded or abandoned. Use `comment` to ping the reviewers when it is still wanted.
- **Review request:** `comment` to give a quick review or a status note. Use `remove-reviewer` when someone else is better placed. If the PR really deserves a proper review, say so and propose no action: the user reviews it outside this skill.
- If you cannot tell, propose nothing and say why. Keeping an item is always a valid answer.

Write your proposals to `/tmp/github_cleanup/judgements.json`:

```json
{"509": {"action": "close-not-planned", "comment": "Closing: the PAT was rotated in 2025.", "why": "fixed outside GitHub; thread silent for 2 years"}}
```

Comments are short and plain, and written in the user's voice. Don't use emojis, don't sign off, and don't use @-mentions unless you are pinging reviewers on purpose. A close with no comment is fine when the reason is obvious. Run `render_plan.py --step k` again and it shows your proposals and comment text, so the user approves exactly what will be posted.

### 3. Walk through the steps, one at a time

For each step `k`:

1. `python render_plan.py --step k`.
2. Explain the step in two or three plain sentences: what the items are, why they are proposed, and anything worth a second look. Notification steps are shown grouped by repo with item ranges. Point out the biggest groups and anything surprising, for example a mention that is still unread.
3. Ask with `AskUserQuestion`:
   - **Approve all**: every item in the step, each with its proposed action.
   - **Approve some**: the user gives numbers or ranges, for example `1-47,105`.
   - **Change the action**: for example "done instead of unsubscribe for 160-335", or a different action or comment for one item. Write the override into `judgements.json` (one entry per item number), show the result, and ask again.
   - **Skip this step**.
   - **Keep for good** (issues, PRs, branches, and notifications about an issue or PR): never proposed again. Ask for a one-line reason.
4. Flags are report only. Show them, and ask whether any of them should become a rule.

Keep each message short. Don't show the next step until the current one is answered.

### 4. Write what was approved, straight after each approval

```
python build_actions.py --approve <numbers/ranges> [--reject <numbers> --reason "<why>"]
```

`build_actions.py` reads `judgements.json` by itself. Tell the user in one line what is about to happen, for example "Marking 156 notifications done", then run:

```
python apply_actions.py
```

Report the result line. On any `FAILED`, `REFUSED` or `ran, but` line, show it and ask before any further write. Applied items are recorded, and are never run twice.

`build_actions.py` refuses unknown or already-applied items, flags, actions an item does not allow, and a comment action with no text. `apply_actions.py` refuses anything outside the whitelist, and re-reads each branch just before deleting it: a protected branch, the default branch, or a branch matching a protected pattern is never deleted. Don't work around a refusal.

### 5. Summary

A few lines: what was done, closed, unassigned or deleted, with counts, and what was kept or skipped. Read the counts from `/tmp/github_cleanup/applied.json`. Add one line on what is left: the active notifications the plan left alone, and open items that are not stale yet.

### 6. Learn from the run

Ask: "Anything I should handle differently next time?" For each piece of feedback, change data first:

- A threshold, a noise reason or a title pattern goes in `references/rules.json` (for example `notifications.noise_title_patterns`, or `issues.stale_after_days`).
- A single item to keep goes in `references/ignore-list.json`, through `build_actions.py --reject`.
- A change to the script logic needs a new `examples/cases/*.json` case that reproduces it. `python selftest.py` must pass.
- A change to how the walkthrough runs goes in this file.

Then log it: `python record_feedback.py add --text "<what the user said>" --kind rule|ignore|code|process --change "<what changed>" [--fixture <case>]`. Edits to the skill go through a branch and a PR on `ersilia-skills`, like any other change to this repo.

## What this skill does not do

- It does not touch repositories outside `ersilia-os`, other people's PRs and issues, or branches without a PR, because nothing says who owns them.
- It never merges, reopens, labels, assigns someone else, or deletes a repository.
- For the org-wide view of stale work, use `github-digest`.
