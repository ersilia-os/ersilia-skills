---
name: model-incorporation-pr
description: >
  Commit a finished Ersilia model incorporation and open the pull request that submits it
  to ersilia-os/<model_id>. Use this skill once the model has been coded and tested (and,
  where they apply, reproduced and optimized) and the user wants to submit it. It checks
  the repository, stages only the intended files, commits on the fork's main branch, asks
  for explicit approval, pushes to the fork, opens the PR from the fork's main into the
  organisation's main with a body that says what was and was not run, reports the PR check
  and, once the user has authorised it and every check is green, merges it. Trigger on
  phrases like "open the PR", "submit the model", "commit and push the incorporation",
  "push eosXXXX", or "/model-incorporation-pr".
argument-hint: <model_id> <model_path>
allowed-tools: [Bash, Read, AskUserQuestion]
---

# Model Incorporation – Pull Request

You take a finished incorporation from files on disk to an open pull request with a running
check, and, if the user authorises it, on to a merged one once every check is green.

## Parse arguments

- `model_id` (required): `eos` + 4 alphanumerics, e.g. `eos80sj`.
- `model_path` (required): local clone of the user's fork, e.g. `~/Desktop/eos80sj`.
- The number of the request issue on `ersilia-os/ersilia`. Take it from the conversation, or
  find it with `gh issue list --repo ersilia-os/ersilia --search "<slug> in:title"`, or ask.

If an argument is missing and cannot be found, ask before going on.

## Why the PR comes from the fork's `main`

The check on an incorporation PR (`test-model-pr.yml` in `ersilia-model-workflows`) checks
out the base repository, deletes that checkout, then clones **`<PR author>/<repo>` on its
default branch** and tests that. It tests the fork's `main`, whatever the PR's head is. A PR
from any other branch gets a check that runs against code it does not contain.

The merged incorporations show the working shape: eos5j3l#2, eos55vx#2, eos92m1#1 and
eos9q2i#1 all came from `<fork>:main`. The feature-branch attempts eos5j3l#1 and eos55vx#1
were closed and redone from `main`. So: commit on the fork's `main`, push to the fork, open
the PR with head `<login>:main`.

## Rules

1. **Every push and every merge needs explicit approval.** Approval to commit is not approval
   to push. Approval to push is not approval to merge unless the user chose the option that
   says so (Step 2).
2. Never force-push, never close an issue, never edit `README.md` (it is generated from the
   metadata).
3. **No CI-skip token** in any commit message of this PR: `[skip ci]`, `[ci skip]`,
   `[no ci]`, `[skip actions]`, `[actions skip]`, `skip-checks: true`. GitHub honours them
   anywhere in the message, even in prose that only mentions them, and the PR check would
   silently not run.
4. Link the request with `Refs ersilia-os/ersilia#<n>`, never `Fixes`, `Closes` or
   `Resolves`. The issue is closed later, by `/model-incorporation-release`.
5. Do not re-run or dispatch workflows without asking. The organisation's Actions budget is
   limited.
6. Merge only through Step 5: every check green, head unchanged since it went green, no
   `--admin`, and never `--delete-branch` (the PR's head is the fork's `main`).
7. Say in the PR what was not run. A skipped reproduction or optimization is stated, with the
   reason, never left for the reviewer to infer.

## Step 0: Preflight

Read-only apart from deleting `.eosvc/`. Stop at the first failure and say how to fix it.

```bash
cd <model_path>; ID=<model_id>; LOGIN=$(gh api user --jq .login)

# 1. origin is the user's fork of ersilia-os/$ID, default branch main, checked out
gh repo view "$(git remote get-url origin)" --json isFork,parent,defaultBranchRef \
  --jq '{isFork, parent: (.parent.owner.login + "/" + .parent.name), default: .defaultBranchRef.name}'
git branch --show-current                        # main
git remote get-url origin                        # must contain /$LOGIN/
git config user.name; git config user.email      # both set
git fetch origin && git rev-list --count HEAD..origin/main   # 0: the fork has nothing new
```

Expect `isFork: true`, `parent: ersilia-os/<id>`, `default: main`. If `origin` is the
organisation repo itself, stop and ask: the shape below needs a fork.

```bash
# 2. nothing already in flight
gh pr list --repo ersilia-os/$ID --state all --json number,state,headRefName,author
gh api repos/ersilia-os/$ID/commits --jq '[.[].commit.author.name] | unique'   # ["ersilia-bot"]: nothing merged yet
```

An open PR from `<login>:main` means this is an update: push, skip Step 3's `gh pr create`
and report that PR. A merged one means stop.

```bash
# 3. metadata limits that CI enforces. <skill-dir> is the folder this file is in
conda run -n ersilia python <skill-dir>/scripts/check_metadata.py "$PWD"
```

```bash
# 4. checkpoints on S3 match local (skip for models without checkpoints)
conda run -n eosvc eosvc view --path model/checkpoints
# the last line must read "0 modified · 0 local-only · 0 remote-only"

# 5. strays. Any eosvc command recreates .eosvc/, so delete it after step 4, not before
rm -rf .eosvc
git status --porcelain
git ls-files -o -m --exclude-standard | xargs -r -d '\n' du -k 2>/dev/null | sort -rn | head -3
```

The status must list only intended files. Never stage `.eosvc/`, `*-test.json`,
`__pycache__/`, `.env`, `.config`, anything under `model/checkpoints/` or `model/framework/fit/`,
or a file in the megabytes. `mock.txt` and `.gitattributes` must show as deleted.

```bash
# 6. earlier unpushed commits carry no skip token
git log origin/main..HEAD --format=%B | grep -n -i -E '\[(skip ci|ci skip|no ci|skip actions|actions skip)\]|skip-checks:' && echo STOP
```

Finally collect what the PR must report, from the conversation or by asking: did
`ersilia test --shallow` pass on this exact tree (and what was the result), was
`/model-incorporation-reproduce` run (if not, why), was `/model-optimization` run (if not,
why). If the files changed after the last test, say so and offer to re-test first.

## Step 1: Commit

Build the file list from `git status --porcelain`, drop the strays, and add the paths by
name. Never `git add -A` or `git add .`. Deleted template files are staged the same way
(`git add -- mock.txt .gitattributes`).

```bash
git add -- <path> <path> ...
git diff --cached --stat
```

**Re-invoked after `/model-optimization`.** The first commit already exists (local commits
ahead of `origin/main`) and the working tree holds the optimizer's uncommitted `install.yml`
changes. Commit those as a second, separate commit, so the reviewer can diff the optimization
on its own: `Optimize <id> install.yml`, with the size change from the optimizer's report in
the body. If the tree is clean, the optimizer found nothing to remove: say so, commit
nothing, and go on to Step 2. If the work is already committed and the tree is clean for any
other reason, skip straight to Step 2.

Write the message to a file and commit with `-F`:

```
Incorporate <Title> (<id>)

<One sentence on what the model returns.>
Checkpoints are on S3 via eosvc. Shallow test: <result>.
Reproduction: <ran / not run, and why>. Optimization: <ran / not run, and why>.

Refs ersilia-os/ersilia#<n>
```

Re-run the skip-token grep from preflight step 6 on `HEAD` before going on.

## Step 2: Ask, then push

Show the user the commit(s) and the plan: push `origin main` (their fork `<login>/<id>`),
then open a PR into `ersilia-os/<id>:main`.

If `/model-optimization` is installed (`test -d ~/.claude/skills/model-optimization`), has not
run on this model and the user has not ruled it out, ask with AskUserQuestion:

- **Push and open the PR now.** Merging is asked about later, when the check is green.
- **Push, open the PR and merge it once every check is green.** One approval covers the
  merge, if Step 5's conditions hold.
- **Run `/model-optimization` first.** Nothing is pushed and the commits stay local. The
  optimizer edits `install.yml` and leaves the change uncommitted, and its own PR step stays
  off because it sees local commits ahead of `origin/main`. Tell the user to run it and then
  to invoke this skill again, and stop here.

If it is not installed, already ran, or the user already said to skip it, ask only the first two.
Only on a yes:

```bash
git push origin main
```

If the push is rejected as non-fast-forward, stop and report. Never force.

## Step 3: Open the PR

Write the body to a file outside the repository:

```
## <Title> (`<id>`, slug `<slug>`)

<Two or three sentences: what the model returns, and the one design choice a reviewer must
know (for a generative model, how outputs are sampled and filtered).>

Refs ersilia-os/ersilia#<n>

### Checks run
- `ersilia test --shallow`: <result>
- Checkpoints: uploaded with eosvc, S3 and local match
- Reproduction: <ran, with the headline numbers / not run, and why>
- Optimization: <ran, with the size change / not run, and why>

### Review notes
<Anything non-obvious: a deliberate departure from the paper, a Variable output, a licence
flag. Omit the heading if there is nothing.>
```

```bash
gh pr create --repo ersilia-os/$ID --base main --head "$LOGIN:main" \
  --title "Add <Title> (<slug>)" --body-file <body-file>
```

## Step 4: Watch the check and hand over

- Run `gh pr checks <n> --repo ersilia-os/$ID --watch --interval 60` in the background and
  report when it finishes. If the run is waiting for approval, tell the user; do not approve it.
- Look at the fork too: `gh run list --repo $LOGIN/$ID --limit 5`. Actions are enabled on
  forks and `upload-model.yml` fires on every push to `main`, guarded only against the
  template repository, so the push may have started workflows there. Report what ran. Do not
  disable anything.
- If the check fails, read `gh run view <run-id> --repo ersilia-os/$ID --log-failed`, propose
  the fix (`/model-fixing` covers the usual ones), and commit it to the fork's `main`. The PR
  updates itself. Ask before every push, and do not re-run the workflow.

## Step 5: Merge when green

Only when every check has finished green. If the user chose the merge option in Step 2, go
ahead. Otherwise ask first, in one line, and merge only on a yes.

```bash
gh pr view <n> --repo ersilia-os/$ID --json state,mergeable,mergeStateStatus,headRefOid,statusCheckRollup
```

Green means `state` is `OPEN`, `mergeable` is `MERGEABLE`, `mergeStateStatus` is `CLEAN`, every
entry of `statusCheckRollup` concluded `SUCCESS` (none pending, skipped or failed) and
`headRefOid` is the commit you pushed. Then:

```bash
gh pr merge <n> --repo ersilia-os/$ID --merge --match-head-commit <headRefOid>
```

`--merge` makes a merge commit, as in eos5j3l#2 and eos92m1#1 (eos55vx#2 was squashed), and
it keeps the optimization commit visible. `--match-head-commit` refuses the
merge if anything was pushed after the check went green.

If the state is anything else, report it and stop. `BLOCKED` (a required review) and a failed
check are for the user to resolve. Do not use `--admin`, and do not wait in a loop for a state
that is not coming.

The merge makes `upload-model.yml` run on the organisation repository's `main`: source test,
S3 upload and image build. Do not wait for it and do not dispatch anything. Report the merge
and point to `/model-incorporation-release`, which follows the build.

Report the PR URL, the state of the checks, what was not run, and whether it was merged.
Then stop.

## Never

Force-push, push or merge without approval, merge with a pending, failed or skipped check,
use `--admin` or `--delete-branch`, close or edit the request issue, edit `README.md`,
change repository settings or secrets, add a CI-skip token, or use `Fixes`.

## Next steps

> **Remaining steps:**
> 1. Merge the pull request, if it was not merged above
> 2. Run `/model-incorporation-release` to confirm CI is green, check the release, deposit
>    the paper and close the request
