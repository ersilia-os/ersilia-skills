---
name: model-incorporation-release
description: >
  Finish an Ersilia Model Hub incorporation after its pull request is merged: confirm
  every GitHub Actions workflow on the model repo is green (watching runs still in
  progress), make sure the model has a correct GitHub release and that the DockerHub
  image is retagged, verify metadata.yml and the Hub catalogue, deposit the model's paper
  in the `ersilia_models_articles` Google Drive folder as <model id>.pdf, and close the
  model request issue. This is the last step of the incorporation pipeline, after
  model-incorporation-reproduce and the PR merge. Use it whenever the user wants to
  release, finish, close out or ship an incorporated model, asks whether a model's CI is
  green or why its release or retag failed, or wants the model's paper put in Drive.
  Triggers include: "release the model", "/model-incorporation-release", "finish the
  incorporation", "is eosXXXX green", "are all tests green", "create the release",
  "the retag failed", "upload the paper to drive", "deposit the paper",
  "close the model request". Always use this skill for post-merge incorporation work,
  even if the ask seems simple.
argument-hint: "<eosXXXX> [--paper <pdf-path-or-drive-link>] [--check-only]"
allowed-tools: [Bash, Read, AskUserQuestion, search_files, get_file_metadata, copy_file, update_file]
---

# Ersilia Model Incorporation Release

Your job is to take a model from **"PR merged"** to **"green, released, paper deposited,
request closed"**, and to say clearly which of those is not true yet.

Everything after the merge is done by CI in `ersilia-os/<id>`: tests, S3 upload,
DockerHub image, metadata, Airtable, catalogue and usually the `v1.0.0` release. This
skill mostly **checks** that CI did its job. It acts only where CI does not (a release
the bot skipped, the paper, the issue) and it **asks before every outward action**.
The model repo's own `CLAUDE.md` sets the rules you follow:
- a model is not done until every workflow is green;
- versions are semantic;
- never change a version without asking.

## Parse arguments

- `<eosXXXX>` (required): the model identifier. Ask for it if missing.
- `--paper <path-or-link>` (optional): the paper as a local PDF, or as a Drive link or
  file ID. Also use a paper the user gave earlier in the session.
- `--check-only` (optional): report the CI and release state, then stop. No watching,
  no releasing, no Drive or issue actions.

## Read these first

- **`references/lessons-learned.md`**: every known failure mode, with its diagnosis and
  fix. Read it before you interpret a red run or touch a release; most surprises are
  already there.

Scripts live in `scripts/` next to this file. Run them by full path. They print JSON
on stdout and warnings on stderr, and need the `gh` CLI (authenticated) plus
`pdfinfo`/`pdftotext` (poppler-utils) for the PDF check.

---

## Step 0 — Resolve the model

```bash
gh api repos/ersilia-os/<id> --jq '{full_name, created_at}'
gh search issues "<id>" --repo ersilia-os/ersilia --label new-model --json number,title,state,url
```

The request issue is found because the bot's "New Model Repository Created" comment
names the repo. Note its number for Step 5. If the search finds none, ask the user for
the issue number. Do not skip Step 5 silently.

## Step 1 — Green gate

```bash
python scripts/ci_status.py <id>
```

Show the user a status table built from the JSON:

| Stage | Source |
|---|---|
| PR test | `pr_test` |
| Source test, S3 upload, pack build (amd64, arm64, merge) | `upload.jobs` |
| Image test amd64, arm64, retag-image, post-upload | `image.jobs` |

Then act on `overall`:

- **`green`**: go to Step 2. Carry every entry of `warnings` into the final summary
  (e.g. an arm64 image test that failed inside a green run means the image is
  amd64-only).
- **`running`**: unless `--check-only`, **watch it in-session**. For each id in
  `watch`, start a background Bash command:
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
  - **Infrastructure problem** (timeout, runner disk, a skipped post-upload): propose
    the re-run the hint names. Re-running is an outward action, so ask first.
  - **Model problem** (install, inference, output columns): stop and hand off to
    `/ersilia-model-test`, then `/model-fixing`. This skill does not fix models.
- **`missing`**: no run exists for the real HEAD. Show `reason`. Offer
  `gh workflow run upload-model.yml -R ersilia-os/<id>` (after confirmation).
- **`not_merged`**: main still holds only the template's Initial commit. Report the
  open PRs and the PR-test state, and stop. The release step starts after the merge.

Never move on to Step 2 unless `overall` is `green`. Publishing a release while the
image test was still running is what broke eos8gop.

## Step 2 — Release

```bash
python scripts/release_state.py <id>
```

Act on `action`:

- **`verified`**: the normal case. Usually the bot made `v1.0.0` and post-upload
  retagged the image. A bot release's tag sitting behind main's later bot commits is
  **expected**; do not "fix" it.
- **`create_release`**: CI is green but no release exists. Usually a tag already
  existed, so post-upload skipped its automatic release.
  1. Show the user the `reasons` and the exact `proposed.command`. It targets main HEAD,
     which the script only proposes once HEAD is the bot's final "updating readme"
     commit.
  2. After confirmation, run it, then watch the triggered "Retag image on release" run
     (`gh run list -R ersilia-os/<id> --workflow "Retag image on release" --limit 1`,
     then `gh run watch`).
  3. Re-run `release_state.py` to confirm.
- **`wait_for_bot_commits`** or **`wait_for_retag`**: post-upload or the retag workflow
  is still writing to main. Watch the run, then re-check. Never create a release at a
  commit the bot is about to move past.
- **`recreate_release_at_head`**: a manual release failed to retag. If its log says
  `failed to push some refs`, the tag is behind HEAD. This is the eos8gop fix:
  ```bash
  gh release delete <tag> -R ersilia-os/<id> --cleanup-tag --yes
  gh release create <tag> -R ersilia-os/<id> --target <main HEAD sha> --title "Release <tag>" --generate-notes
  ```
  Deleting a release is destructive: show both commands and get an explicit yes first.
- **`unreleased_changes`**: people committed to main after the latest release, so the
  published image no longer matches main. Ask which bump applies, offering
  `release.next_versions` and the MAJOR/MINOR/PATCH rules in the model repo's
  `CLAUDE.md`. Never choose for the user. Then create the release at main HEAD as above.
- **`investigate`**: the release exists but DockerHub, metadata.yml or the Hub
  catalogue disagree. Show the `reasons`. Most often a later workflow has not finished;
  re-check once before raising it.

## Step 3 — Verify publication

From the `release_state.py` JSON, confirm and report:

- DockerHub `latest` and the release tag share one digest (`docker.match`);
- metadata.yml has `Status: Ready`, `Release` equal to the tag, and `DockerHub` filled;
- the Hub catalogue (`catalog`) agrees. A lag here is a **warning**, not a failure, because it syncs after metadata.

## Step 4 — Deposit the paper

The paper goes in Drive folder `ersilia_models_articles`
(`https://drive.google.com/drive/folders/1_3ZY6-sFZnW0gWanxn9uHOHgkyfgmBHU`).

### 4a — Work out the name and check for a duplicate

```bash
python scripts/paper_target.py <id>
```

- **Name:** `canonical_name` is `<id>.pdf`, or the sorted, `_`-joined IDs of every
  **Ready** model citing the same DOI (`eos55vx_eos6a1h.pdf`). If `siblings_pending` is
  non-empty, ask whether those models should be in the name too.
- **Duplicates:** run each query in `drive_queries` with `search_files`.
  - If the paper is already there under the canonical name, skip to Step 5.
  - If it is there under a shorter shared name, propose renaming that file to the
    canonical name with `update_file` (the link stays the same) instead of adding a copy.

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
  python scripts/prepare_paper.py <validated pdf> --name <canonical_name>
  ```
  This copies the paper to the outbox, `ersilia-model-papers/<canonical_name>` inside
  the user's Downloads folder, and prints its exact `size_bytes`. The Downloads folder
  is resolved per OS (Windows known folder, XDG on Linux, `~/Downloads` on macOS);
  override it with `$ERSILIA_MODEL_PAPERS_OUTBOX`.
  - If `leftovers` is non-empty, tell the user. Those are papers staged in an earlier
    incorporation and never confirmed as uploaded. Offer to check each against the
    Drive folder; never delete them unasked.
  - Give the user the `staged_path` and the `drive_folder_url`. Offer to open both by
    running the `open_folder` and `open_drive` commands from the JSON; they are already
    right for the current OS.
  - Then wait for them to say it is uploaded.

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

## Step 5 — Close the request issue (confirm first)

**Gate: the paper must be verified in Drive (Step 4) before the issue is closed.**
Closing the request is what tells the team the model is done. A paper left for "later"
gets forgotten: 6 of the 10 most recent Ready models were missing theirs. The gate
covers only this step. CI, the release and the verification are automated and have
usually already happened, so holding them back would only hide problems.

If the paper cannot be deposited yet (closed access with no PDF to hand, a preprint
with no PDF), keep the issue open and say what is missing. Close it without the paper
only when the user explicitly says so ("close it without the paper"). In that case,
mark the summary's paper line ❌ and do not call the incorporation complete. An
instruction like "I'll upload it later" is not that override: explain the gate, offer to
stage the paper now, and leave the issue open unless they then confirm.

Post exactly this comment, nothing more, then close the issue:

```bash
gh issue comment <n> -R ersilia-os/ersilia --body "This model has been incorporated. 🚀"
gh issue close <n> -R ersilia-os/ersilia
```

Skip this if the issue is already closed.

## Step 6 — Summary

End with one checklist, each line with its link:

```
eosXXXX — <Title>
✅ CI green on <sha7> (upload <run>, image <run>)        ⚠ <each warning>
✅ Release <tag> by <bot|person> — <release url>
✅ DockerHub latest = <tag> (<digest12>) — <hub url>
✅ metadata.yml Ready / <tag>     ⚠ catalogue lagging (if so)
✅ Paper → <canonical_name> — <drive link>
✅ Request #<n> closed
```

Use ❌ or ⏳ with the reason for anything not done. Call the incorporation **complete**
only when every line is ✅; warnings (⚠) do not block that. If something new went wrong,
add an entry to `references/lessons-learned.md`, or tell the user it deserves one.

---

## Rules

- **Ask before every outward action:** re-running CI, creating or deleting a release,
  copying or renaming in Drive, commenting on or closing the issue.
- **Never pick a version number.** The user chooses the bump.
- **Never hand-edit the fields CI owns** (Status, Release, DockerHub, Image Size,
  Computational Performance, Docker Architecture) in metadata.yml.
- **Never upload a paper through `create_file`**, and never bring in other upload
  tooling. Use `copy_file` or the hand-off.
- **No closing the request without a verified paper**, unless the user explicitly says to
  close without it.
- **Delete only the staged copy you verified**, never other files in the outbox, and
  never the user's own PDF wherever they gave it from.
- **Fixing the model is out of scope.** Hand off to `ersilia-model-test` → `model-fixing`.

## Next steps

> **The incorporation is complete.** The model will appear in the next
> `/model-incorporation-digest`, which summarises each month's incorporations.
