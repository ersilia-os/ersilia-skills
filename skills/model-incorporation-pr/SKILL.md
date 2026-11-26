---
name: model-incorporation-pr
description: >
  Commit a finished Ersilia model incorporation and open the pull request that submits it
  to ersilia-os/<model_id>. Use this skill once the model has been coded and tested (and,
  where they apply, reproduced and optimized) and the user wants to submit it. It checks
  the repository, stages only the intended files, commits on the fork's main branch, asks
  for explicit approval, pushes to the fork, opens the PR from the fork's main into the
  organisation's main with the `semver:major` version label and a body that says what was
  and was not run, reports the PR checks and, once the user has authorised it and every
  check is green, merges it. Trigger on
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

Until 24 November 2026 the PR test (`test-model-pr.yml` in `ersilia-model-workflows`) cloned
the fork's default branch, whatever the PR's head was, so a PR from any other branch was
tested against code it did not contain (eos5j3l#1 and eos55vx#1 were closed and redone from
`main`). Since ersilia-model-workflows#21 the test checks out the PR's head commit, so a
branch would now work too. This skill still uses the fork's `main`: it is the shape every
merged incorporation has, and the preflight and merge steps below rely on it.

## The version label

Every PR to a model's `main` needs exactly one version label: `semver:patch`,
`semver:minor`, `semver:major` or `no-release` (ersilia-model-workflows#22). The required
check `Check version label / check-version-label / verdict` fails when the label is missing
or lower than the bump it detects from the diff. After the merge, the workflows release the
model from that label, so no one creates the release by hand.

For an incorporation the label is always **`semver:major`**. The template's
`run_columns.csv` has no columns and its `run_output.csv` is empty, so any real model adds
output columns, which the check classifies as MAJOR; a lower label fails. The version is
still `v1.0.0`: a repository with no tags gets its first release whatever the label.

Adding a label needs triage permission on `ersilia-os/<id>`. Ersilia team members have it;
an external contributor does not, and a maintainer adds the label for them.

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
7. The PR carries exactly one version label, `semver:major`. Never `no-release`, and never
   a second label: the check fails on either.
8. Say in the PR what was not run. A skipped reproduction or optimization is stated, with the
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
# 4. storage: checkpoints in git unless a file is 100 MiB or more; a populated fit/ always on eosvc
find model/checkpoints -type f -size +104857599c
find model/framework/fit -type f ! -name .gitkeep ! -path model/framework/fit/README.md
cat access.json 2>/dev/null       # names only the folders on eosvc; absent when nothing is on eosvc
git ls-files ':(attr:filter=lfs)'   # must print nothing: no Git LFS
grep -n -E 'from_pretrained|hf_hub_download|snapshot_download|gdown|wget|curl|urlretrieve|urlopen|requests\.get|torch\.hub|load_state_dict_from_url|pooch|get_file' model/framework/code -r   # each hit: is it a run-time weight download?
# for each folder on eosvc (skip if none), S3 must match local:
conda run -n eosvc eosvc view --path model/checkpoints    # and/or --path model/framework/fit
# the last line must read "0 modified · 0 local-only · 0 remote-only"
# if access.json exists, a folder kept in git must have NOTHING on S3 (CI's
# `eosvc download --path .` would overwrite it): `eosvc view` on that folder must list no
# remote files

# 5. strays. Any eosvc command recreates .eosvc/, so delete it after step 4, not before
rm -rf .eosvc
git status --porcelain
git ls-files -o -m --exclude-standard | xargs -r -d '\n' du -k 2>/dev/null | sort -rn | head -3
```

`model/checkpoints/` with a file listed by the first `find` must be gitignored and on eosvc as a
whole; without one it must be in git and must not be on S3, because CI downloads the S3 copy
over the git one. `model/framework/fit/` with anything listed by the second `find` must be on
eosvc. No file may be tracked by Git LFS, and the model must not download weights at run time
(`from_pretrained` on a local `model/checkpoints/` path is fine). If any of this is not the case,
stop and say which. Rule: [Checkpoints and storage](https://ersilia.gitbook.io/ersilia-book/ersilia-model-hub/model-contribution/model-template#checkpoints-and-storage).

The status must list only intended files. Stage `model/checkpoints/` when it is in git, and
`model/framework/fit/` only when it holds just the template skeleton. Never stage `.eosvc/`, `*-test.json`, `__pycache__/`, `.env`, `.config`,
a gitignored folder, a file of 100 MiB or more, or a file in the megabytes outside those two
folders. A `mock.txt` or `.gitattributes` left by an older template must show as deleted.

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
name. Never `git add -A` or `git add .`. A `mock.txt` or `.gitattributes` from an older
template is staged as a deletion only if git tracks it, so a missing file never breaks the
`git add`:
```bash
for f in mock.txt .gitattributes; do
  if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then git add -- "$f"; fi
done
```

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
Checkpoints: <in git / on S3 via eosvc, a file is 100 MiB or more>; fit/: <template skeleton / on S3 via eosvc>. Shallow test: <result>.
Reproduction: <ran / not run, and why>. Optimization: <ran / not run, and why>.

Refs ersilia-os/ersilia#<n>
```

Re-run the skip-token grep from preflight step 6 on `HEAD` before going on.

## Step 2: Ask, then push

Show the user the commit(s) and the plan: push `origin main` (their fork `<login>/<id>`),
then open a PR into `ersilia-os/<id>:main` with the `semver:major` label.

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
- Checkpoints and training data: <checkpoints in git / on S3 via eosvc (a file is 100 MiB or more); fit/ skeleton only / on S3 via eosvc; S3 and local match>
- Reproduction: <ran, with the headline numbers / not run, and why>
- Optimization: <ran, with the size change / not run, and why>

### Review notes
<Anything non-obvious: a deliberate departure from the paper, a Variable output, a licence
flag. Omit the heading if there is nothing.>
```

```bash
gh pr create --repo ersilia-os/$ID --base main --head "$LOGIN:main" \
  --title "Add <Title> (<slug>)" --body-file <body-file> --label semver:major
```

If `gh pr create` fails because the label cannot be added (no triage permission on
`ersilia-os/<id>`), open the PR without `--label`, and tell the user that an Ersilia
maintainer must add `semver:major` before the label check can pass. Do not comment on the PR
or the request issue to ask for it unless the user says so.

On an update (Step 0 found an open PR from `<login>:main`), check its labels with
`gh pr view <n> --repo ersilia-os/$ID --json labels` and, if `semver:major` is missing, add it
after asking: `gh pr edit <n> --repo ersilia-os/$ID --add-label semver:major`. Remove any
other version label in the same way (`--remove-label`).

## Step 4: Watch the check and hand over

- Run `gh pr checks <n> --repo ersilia-os/$ID --watch --interval 60` in the background and
  report when it finishes. Two workflows run: "Test model on PR" (the shallow test) and
  "Check version label". Opening a PR with a label sends two events a second apart, so the
  first "Check version label" run is usually cancelled by the second; that is expected. If a
  run is waiting for approval, tell the user; do not approve it.
- If `verdict` fails, read its summary (`gh run view <run-id> --repo ersilia-os/$ID --log-failed`):
  it says which label it found and the minimum it detected. A missing label is fixed by
  adding `semver:major` (Step 3); nothing needs re-running, because a label change starts the
  check again.
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

The rollup keeps every run, including the cancelled duplicates of "Check version label", so
judge each check by its latest run:

```bash
gh pr view <n> --repo ersilia-os/$ID --json statusCheckRollup --jq '
  [.statusCheckRollup[] | select(.__typename == "CheckRun")]
  | group_by(.workflowName + " / " + .name)
  | map(max_by(.startedAt) | "\(.workflowName) / \(.name): \(.status) \(.conclusion)") | .[]'
```

Green means `state` is `OPEN`, `mergeable` is `MERGEABLE`, `mergeStateStatus` is `CLEAN`,
`headRefOid` is the commit you pushed, and the latest run of every check is `COMPLETED`
with `SUCCESS`, with one exception: `check-version-label / run-examples` may be `SKIPPED`
(it runs only when the detector needs to compare outputs, never for an incorporation).
`Test model on PR / test-model-pr / model-test` and
`Check version label / check-version-label / verdict` must both be `SUCCESS`. Then:

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
S3 upload and image build. "Test model image" follows, and its `release` job creates
`v1.0.0` from the label once the image tests pass; nobody creates the release by hand. Do not
wait for it and do not dispatch anything. Report the merge and point to
`/model-incorporation-release`, which checks the build and the release.

Report the PR URL, the state of the checks, what was not run, and whether it was merged.
Then stop.

## Never

Force-push, push or merge without approval, merge with a pending or failed check (or a
skipped one other than `run-examples`), open the PR with a label other than `semver:major`,
use `--admin` or `--delete-branch`, close or edit the request issue, edit `README.md`,
change repository settings or secrets, add a CI-skip token, or use `Fixes`.

## Next steps

> **Remaining steps:**
> 1. Merge the pull request, if it was not merged above
> 2. Run `/model-incorporation-release` to confirm CI is green, check the release, deposit
>    the paper and close the request
