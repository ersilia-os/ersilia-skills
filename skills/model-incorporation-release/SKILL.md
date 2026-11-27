---
name: model-incorporation-release
description: >
  Follow an Ersilia Model Hub incorporation from the merge of its pull request until the
  model is released, and close the model request. Monitors every GitHub Actions workflow
  on the model repo until the chain finishes (PR test, source test, S3 upload, image
  build, image tests for amd64 and arm64, retag, post-upload, release, SIF build),
  watching runs still in progress, then verifies that the release CI created from the
  PR's version label exists, that the DockerHub image is retagged, that metadata.yml is
  Ready with the Release, and that the Hub catalogue agrees. It never creates, deletes or
  recreates a release: when none appears it reports why and what an Ersilia maintainer
  must do. Once the release is verified complete it closes the model request issue, which
  anyone following their own model, including an external contributor, can do. Only for
  Ersilia maintainers it also files the model's paper in the `ersilia_models_articles`
  Google Drive folder, which they must do before closing the request. This is the last
  step of the incorporation pipeline, after the PR is merged. Use it whenever the user
  wants to follow, finish or close out an incorporated model, asks whether a model's CI
  is green, whether it has been released or why its retag failed, or (maintainers) wants
  the model's paper put in Drive. Triggers include: "follow the release", "monitor the
  release", "release the model", "/model-incorporation-release", "finish the
  incorporation", "is eosXXXX green", "is my model released", "are all tests green",
  "the retag failed", "close the model request", "upload the paper to drive", "deposit
  the paper". Always use this skill for post-merge incorporation work, even if the ask
  seems simple.
argument-hint: "<eosXXXX> [--paper <pdf-path-or-drive-link>] [--check-only]"
allowed-tools: [Bash, Read, AskUserQuestion, search_files, get_file_metadata, copy_file, update_file]
---

# Ersilia Model Incorporation Release

Your job is to follow a model from **"PR merged"** to **"CI green, released, request
closed"**, and to say clearly which of those is not true yet. For an Ersilia maintainer it
also includes **"paper filed"**.

This skill is for **everyone**: Ersilia maintainers, and external contributors who want to
follow their model until the final release and close the request themselves, which is
encouraged. What differs is only what each may do (Step 0).

Everything after the merge is done by CI in `ersilia-os/<id>`: tests, S3 upload,
DockerHub image, metadata, Airtable, catalogue and the release. Since 25 Nov 2026
(ersilia-model-workflows#22) the release comes from the version label of the merged PR:
the `release` job of "Test model image" creates the tag (`v1.0.0` for a first
incorporation, whatever the label) and the `retag` job tags the image. **This skill never
creates a release.** It watches CI until the release exists, checks that it is correct, and
closes the request only when the release is verified complete. Where CI does not release
(for example the PR was merged without a version label), it reports why and what an Ersilia
maintainer must do. It acts only to watch, to close the request and, for maintainers, to
re-run CI and file the paper, and it **asks before every outward action**.
The model repo's own `CLAUDE.md` sets the rules you follow:
- a model is not done until every workflow is green;
- versions are semantic;
- never choose or change a version.

## Parse arguments

- `<eosXXXX>` (required): the model identifier. Ask for it if missing.
- `--paper <path-or-link>` (optional, Ersilia maintainers only): the paper as a local PDF,
  or as a Drive link or file ID. Also use a paper the user gave earlier in the session.
- `--check-only` (optional): report the CI and release state, then stop. No watching, no
  re-running, no Drive or issue actions.

## Read these first

- **`references/lessons-learned.md`**: every known failure mode, with its diagnosis and
  fix. Read it before you interpret a red run or explain why no release appeared; most
  surprises are already there. Where an entry says to create, delete or recreate a release,
  that is what a maintainer does by hand: this skill reports it and never runs it.

Scripts live in `scripts/` next to this file. Run them by full path. They print JSON
on stdout and warnings on stderr, and need the `gh` CLI (authenticated). The paper scripts
(Step 4, maintainers only) also need `pdfinfo`/`pdftotext` (poppler-utils) for the PDF
check.

---

## Step 0 — Resolve the model and who is asking

```bash
gh api repos/ersilia-os/<id> --jq '{full_name, created_at}'
gh search issues "<id>" --repo ersilia-os/ersilia --label new-model --json number,title,state,url
gh api repos/ersilia-os/ersilia --jq .permissions.push
```

The request issue is found because the bot's "New Model Repository Created" comment
names the repo. Note its number for Step 5. If the search finds none, ask the user for
the issue number. Do not skip Step 5 silently.

The last command decides who is asking, as `/model-incorporation-request` does: `true`
means an **Ersilia maintainer** (write access). Anything else (`false`, empty, or an
error) means **not a maintainer**; do not ask them which they are.

| | Ersilia maintainer | Anyone else |
|---|---|---|
| Watch CI, check the release, report | yes | yes |
| Re-run or dispatch workflows (after asking) | yes | no: give the failing run link and say to ask an Ersilia maintainer |
| The paper (Step 4) | yes, and it is mandatory | skipped: never ask them to upload anything, and do not mention a Drive deposit |
| Close the request (after asking, once the release is verified complete) | yes, after the paper (Step 5) | yes; no paper gate |

## Step 1 — Follow CI until the chain finishes

```bash
python scripts/ci_status.py <id>
```

Show the user a status table built from the JSON:

| Stage | Source |
|---|---|
| PR test | `pr_test` |
| Resolve label, source test, S3 upload, pack build (amd64, arm64, merge) | `upload.jobs` |
| Image test amd64, arm64, retag-image, post-upload, release, retag, build-sif | `image.jobs` |

An arm64 build that fails inside a green upload run is allowed since
ersilia-model-workflows#20: the image is then published for amd64 only, and its arm64
test shows as skipped.

Then act on `overall`:

- **`green`**: go to Step 2. Carry every entry of `warnings` into the final summary
  (e.g. an arm64 image test that failed inside a green run means the image is
  amd64-only). After a `semver:patch` or `no-release` merge the image test, post-upload
  and the release jobs of "Test model image" are skipped by design; `reason` says which
  route ran.
- **`running`**: unless `--check-only`, **watch it in-session**. This is read-only, so it
  is for everyone. For each id in `watch`, start a background Bash command:
  ```bash
  gh run watch <run_id> -R ersilia-os/<id> --exit-status --interval 60
  ```
  Tell the user how long it usually takes:
  - "Test and upload model": 15–25 min;
  - "Test model image": about 1–2 h, and up to about 12 h for a slow model, because amd64 and arm64 run one after the other.

  When the watch exits you are re-invoked. Run `ci_status.py` again, because the image
  test only appears after the upload finishes, and watch that too. Do not poll in a
  loop.
- **`failed`**: show each entry of `failures` (pattern and hint) and match it against
  `references/lessons-learned.md`.
  - **Infrastructure problem** (timeout, runner disk, a skipped post-upload): a
    maintainer is offered the re-run the hint names, after asking, because re-running
    spends the organisation's Actions budget. Anyone else gets the failing run link and
    is told to ask an Ersilia maintainer to re-run it.
  - **A hint that talks about making or fixing a release by hand** (the stale-tag hint
    on a retag run): that is information for a maintainer. Report it, never run it.
  - **Model problem** (install, inference, output columns): stop and hand off to
    `/ersilia-model-test`, then `/model-fixing`. This skill does not fix models.
- **`missing`**: no run exists for the real HEAD. Show `reason`. A maintainer can be
  offered `gh workflow run upload-model.yml -R ersilia-os/<id>` (after confirmation);
  anyone else is told to ask an Ersilia maintainer. On a model that already has a release,
  a dispatched run rebuilds and tests but releases nothing, so Step 2 may then report that
  the release is still missing; that is for a maintainer too.
- **`untested`**: the runs for the real HEAD are green, but a person pushed newer
  commits that skipped CI and change files that reach the model (listed in
  `untested_commits`, with their files). Show `reason`. If a commit only moves checkpoints
  between Git and eosvc, check with the user that every file's sha256 is unchanged; if so,
  go on as for `green` and say so in the summary. Otherwise a maintainer is offered the
  dispatch above, after confirmation, and anyone else is told to ask one.
- **`not_merged`**: main still holds only the template's Initial commit. Report the
  open PRs and the PR-test state, and stop. This skill starts after the merge.

Never move on to Step 2 unless `overall` is `green`: wait for the chain to finish. A
release published by hand while the image test was still running is what broke eos8gop
(lessons-learned), which is one reason this skill never publishes one.

## Step 2 — Verify the release (read-only)

```bash
python scripts/release_state.py <id>
```

The script only reads. Its action names come from the days when the skill made releases;
treat every `proposed` command it prints as information for a maintainer, never something
to run. Act on `action`:

- **`verified`**: the normal case. CI made the release (the `release` job, from the PR's
  version label; on repos with the older wrappers, post-upload) and the image was
  retagged. A bot release's tag sitting behind main's later bot commits is **expected**;
  do not "fix" it.
- **`create_release`**: CI is green but **no release exists**. Do not make one. Report that
  the model is not released, and why. Check the `resolve` job of the last "Test and upload
  model" run first: a run with no version label (a manual dispatch, or a PR merged without
  a label) releases nothing, with a warning. On repos with the older wrappers, a tag that
  already existed made post-upload skip its release. Then say what an Ersilia maintainer
  must do: publish the release, choosing the version (the script's `proposed.command`
  shows the release at main HEAD that they would create, once HEAD is the bot's final
  "updating readme" commit). Show that command to the user as information for the
  maintainer; never run it and never offer to. Anyone else is told to ask an Ersilia
  maintainer, with the run link.
- **`wait_for_bot_commits`** or **`wait_for_retag`**: post-upload or the retag workflow
  is still writing to main. Watch the run, then re-check. Do not conclude anything yet.
- **`recreate_release_at_head`**: a release made by hand failed to retag. If the failed
  run's log says `failed to push some refs`, its tag is behind main HEAD (the eos8gop
  case). Report the run link and that a maintainer has to fix the release by hand; the
  fix is in `references/lessons-learned.md`. Do not run it.
- **`unreleased_changes`**: people committed to main after the latest release, so the
  published image no longer matches main. Commits that change only CI or editor files
  (`.github/`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `AGENTS.md`) and commits from
  PRs labelled `no-release` are already left out and listed in `warnings`. Normally a
  later change is released from its own PR's label, so first check whether its PR is
  still running through CI. If the commits reached main without a labelled PR, list them
  and say that a new release needs a version bump chosen by an Ersilia maintainer
  (`release.next_versions` and the MAJOR/MINOR/PATCH rules in the model repo's
  `CLAUDE.md`). Never choose the bump, and never create the release.
- **`investigate`**: the release exists but DockerHub, metadata.yml or the Hub
  catalogue disagree. Show the `reasons`. Most often a later workflow has not finished;
  re-check once before raising it.

When no release appears, the request issue stays open (Step 5): say that in the summary.

## Step 3 — Verify publication

From the `release_state.py` JSON, confirm and report:

- DockerHub `latest` and the release tag share one digest (`docker.match`);
- metadata.yml has `Status: Ready`, `Release` equal to the tag, and `DockerHub` filled;
- the Hub catalogue (`catalog`) agrees. A lag here is a **warning**, not a failure, because it syncs after metadata.

## Step 4 — File the paper (Ersilia maintainers only)

**Only if Step 0 said the user is an Ersilia maintainer.** For anyone else, skip this whole
step: do not ask for a paper, do not mention Drive or a deposit, and say once, in the
summary, that Ersilia maintainers file the paper. The gate in Step 5 does not apply to
them.

For a maintainer the paper is **mandatory**: the request is not closed until it is in the
folder, or the maintainer says it is (4e).

The paper goes in Drive folder `ersilia_models_articles`
(`https://drive.google.com/drive/folders/1_3ZY6-sFZnW0gWanxn9uHOHgkyfgmBHU`).

### 4a — Work out the name and check for a duplicate

```bash
python scripts/paper_target.py <id>
```

- **No paper expected:** if `paper_expected` is `false` (Publication Type `Other`: an
  Ersilia-internal model or a tool wrapper whose Publication is a repo or docs link),
  there is nothing to deposit. Skip the rest of Step 4, and treat the gate in Step 5 as
  passed.
- **Name:** `canonical_name` is `<id>.pdf`, or the sorted, `_`-joined IDs of every
  **Ready** model citing the same DOI (`eos55vx_eos6a1h.pdf`). If `siblings_pending` is
  non-empty, ask whether those models should be in the name too.
- **Duplicates:** run each query in `drive_queries` with `search_files`.
  - If the paper is already there under the canonical name, skip to Step 5.
  - If it is there under a shorter shared name, propose renaming that file to the
    canonical name with `update_file` (the link stays the same) instead of adding a copy.
- **The user says they already uploaded it:** go to 4e.

### 4b — Get the paper, in this order

1. **The user gave it**: `--paper`, or a PDF or Drive link earlier in the session.
2. **Open access**: always try this before asking the user.
   ```bash
   python scripts/fetch_open_paper.py "<Publication>" <scratchpad>/papers/<id>/paper.pdf
   ```
   Download into the scratchpad, never straight into the outbox, so a paywall page or
   the wrong paper never reaches the folder the user drags from. Keep each download in
   its own new directory. When it succeeds, carry on through 4c and 4d **without asking**:
   the user's first sight of the paper is the staged, validated file, ready to drag.

   **Except when `preprint_of_journal_article` is true.** The paper was published in a
   journal, but the only free copy is the preprint (eos1ltv and eos55vx, both Nature
   Machine Intelligence). The folder should hold the published version. Ask the user for
   it, giving the `landing_page` link; their institution usually has access. Stage the
   preprint only if they say to use it. A model whose DOI is itself a preprint (arXiv,
   bioRxiv, ChemRxiv) is not affected: there, the preprint is the publication.
3. **Otherwise** (exit 2, `status` `closed` or `not_fetched`): **stop and ask the user
   for the PDF**. Give them the `landing_page` link. Never deposit a guess, and never
   work around a paywall.

### 4c — Validate

```bash
python scripts/check_pdf.py <pdf> --model-id <id>
```

| Exit code | Meaning | What to do |
|---|---|---|
| 0 | Valid PDF, identified as this model's paper | Continue |
| 1 | Not a usable PDF (HTML stub, truncated) | Refetch or ask the user |
| 3 | Valid PDF of unconfirmed identity | Show `first_page_excerpt` and ask |

For a paper given as a Drive file, check `mimeType: application/pdf` and a plausible
`fileSize` with `get_file_metadata` instead.

### 4d — Deposit

Staging a local copy needs no confirmation; it touches only the user's own outbox.
Anything that writes to Drive (`copy_file`, a rename with `update_file`) is confirmed
first.

The Drive connector cannot upload a real paper: content travels inline, and even the
smallest paper is too large (see lessons-learned). The upload is manual by design
(`ROADMAP.md` records why). So:

- **Paper already in Drive:** use `copy_file`, with `parentId`
  `1_3ZY6-sFZnW0gWanxn9uHOHgkyfgmBHU` and `title` set to the canonical name. Check the
  returned `parentId`: without write access to the folder, `copy_file` silently puts
  the copy in the user's My Drive root. If that happens, say so and trash the stray copy
  only with the user's OK.
- **Local PDF** (the usual case; the upload is manual by design): prepare it for the user.
  ```bash
  python scripts/prepare_paper.py <validated pdf> --name <canonical_name> --open
  ```
  This copies the paper to the outbox, `ersilia-model-papers/<canonical_name>` inside
  the user's Downloads folder, and prints its exact `size_bytes`. The Downloads folder
  is resolved per OS (Windows known folder, XDG on Linux, `~/Downloads` on macOS);
  override it with `$ERSILIA_MODEL_PAPERS_OUTBOX`.
  - `--open` opens the outbox in the file manager and the Drive folder in the browser
    automatically, without asking: both are local and harmless, and the maintainer only
    has to drag the file across. When staging several papers in one go, pass `--open` on
    the last one only, so the windows open once.
  - If `opened.done` is false (no screen, e.g. over SSH), say so and give the
    `staged_path` and `drive_folder_url` instead.
  - If `leftovers` is non-empty, tell the user. Those are papers staged in an earlier
    incorporation and never confirmed as uploaded. Offer to check each against the
    Drive folder; never delete them unasked.
  - Tell the user which file to drag in, then wait for them to say it is uploaded.

Then **verify** with `search_files` that a file with the canonical name exists in the
folder, and, for a manual upload, that its `fileSize` equals `size_bytes`. A different
size means a different file was dragged in: say so, and do not clear anything.
Report the Drive link.

Once verified, **clear the staged copy** so the outbox is empty for the next
incorporation:

```bash
python scripts/prepare_paper.py --clear --name <canonical_name> --drive-size <fileSize from search_files>
```

It deletes the copy only when the sizes match, so a wrong upload never costs the local
file. It deletes nothing else: if `outbox_now` still lists files, mention them.

### 4e — The maintainer says it is already uploaded

A maintainer may have filed the paper through their own channels, before or while the skill
runs. Their word is enough to go on:

1. **Accept it as confirmation.** Do not stage or fetch anything.
2. **Still try to verify, when the Drive connector is available** (`search_files` is among
   your tools): run the queries in `drive_queries` from `paper_target.py`.
   - Found under the canonical name: report the Drive link. The paper is verified.
   - Not found, or no Drive connector: do not block. If the search found nothing, say once
     that you could not see the file (it may be named differently or still syncing); if
     the maintainer still confirms, go on.
3. **In the summary, mark the paper line "confirmed by the user"** whenever it was not
   verified in Drive.
4. There is no size to compare, so do not run `prepare_paper.py --clear`. If the outbox
   holds a staged copy of this paper, tell the user it is still there.

## Step 5 — Close the request issue (confirm first)

**Close the request only when the release is verified complete**, and say what is missing
if it is not:

- Step 1: `overall` is `green`, so every workflow has finished green;
- Step 2: `action` is `verified`, so the release tag exists and the image is retagged;
- Step 3: metadata.yml has `Status: Ready`, `Release` equal to the tag and `DockerHub`
  filled. A catalogue that lags is only a warning.

If anything is still running, failed or missing, keep the issue open and say so. Closing
the request is what tells the team the model is done, so never close it on a hunch that
"it should be fine".

**Ersilia maintainers: the paper is a second gate.** The paper must be verified in Drive,
or confirmed by the maintainer (4e), before the issue is closed, unless `paper_target.py`
said `paper_expected: false` (no paper exists). A paper left for "later" gets forgotten: 6
of the 10 most recent Ready models were missing theirs. If the paper cannot be filed yet
(closed access with no PDF to hand, a preprint with no PDF), keep the issue open and say
what is missing. Close it without the paper only when the user explicitly says so ("close
it without the paper"). In that case, mark the summary's paper line ❌ and do not call the
incorporation complete. An instruction like "I'll upload it later" is not that override:
explain the gate, offer to stage the paper now, and leave the issue open unless they then
confirm.

**Anyone else: there is no paper gate.** Close the request once the release is verified
complete. Ersilia maintainers file the paper on their side.

Ask before closing. Then post exactly this comment, nothing more, and close the issue as
completed:

```bash
gh issue comment <n> -R ersilia-os/ersilia --body "This model has been incorporated. 🚀"
gh issue close <n> -R ersilia-os/ersilia
```

If `gh` refuses (the issue's author and Ersilia maintainers can close it), report the error
and the issue link, and say the issue's author or an Ersilia maintainer can close it. Do not
look for another way round.

Skip this if the issue is already closed.

## Step 6 — Summary

End with one checklist, each line with its link:

```
eosXXXX — <Title>
✅ CI green on <sha7> (upload <run>, image <run>)        ⚠ <each warning>
✅ Release <tag> by <bot|person> — <release url>
✅ DockerHub latest = <tag> (<digest12>) — <hub url>
✅ metadata.yml Ready / <tag>     ⚠ catalogue lagging (if so)
✅ Request #<n> closed
```

Add one paper line, by who asked:

- **Ersilia maintainer:** `✅ Paper → <canonical_name> — <drive link>`, or
  `✅ Paper confirmed by the user (not verified in Drive)`, or `➖ No paper: Publication Type Other`.
- **Anyone else:** `➖ Ersilia maintainers file the paper`.

If the model is not released, replace the release lines with `❌ Not released: <why>` and say
what an Ersilia maintainer must do, with the run links. The request line then reads
`⏳ Request #<n> left open`.

Use ❌ or ⏳ with the reason for anything not done. Call the incorporation **complete**
only when every line is ✅ or ➖; warnings (⚠) do not block that. If something new went wrong,
add an entry to `references/lessons-learned.md`, or tell the user it deserves one.

---

## Rules

- **Never create, publish, delete or recreate a release or a tag**, and never run
  `gh release` or `git tag` commands. The release comes from the merged PR's version label.
  When none appears, report why and what a maintainer must do.
- **Ask before every outward action:** re-running CI (maintainers only), copying or
  renaming in Drive (maintainers only), commenting on or closing the issue.
- **Re-running or dispatching a workflow is for Ersilia maintainers.** For anyone else, give
  the failing run link and say to ask a maintainer.
- **Never pick a version number.** The PR's version label sets it; if a release has to be
  made by hand, an Ersilia maintainer makes it and chooses the bump.
- **Never hand-edit the fields CI owns** (Status, Release, DockerHub, Image Size,
  Computational Performance, Docker Architecture) in metadata.yml.
- **The paper is for Ersilia maintainers.** Never ask anyone else to upload anything to
  Drive, and do not mention a Drive deposit to them.
- **Never upload a paper through `create_file`**, and never bring in other upload
  tooling. Use `copy_file` or the hand-off.
- **No closing the request before the release is verified complete.** A maintainer also
  needs the paper, unless the user explicitly says to close without it.
- **Delete only the staged copy you verified**, never other files in the outbox, and
  never the user's own PDF wherever they gave it from.
- **Fixing the model is out of scope.** Hand off to `ersilia-model-test` → `model-fixing`.

## Next steps

> **The incorporation is complete.** The model will appear in the next
> `/model-incorporation-digest`, which summarises each month's incorporations.
