# model-incorporation-release — decisions and planned improvements

This file is for the people maintaining the skill, not for a run. It records why the
skill's scope is what it is, so the same "why don't we automate X?" question doesn't
have to be re-argued each time it comes up.

## v1 scope decisions (2026-10-07, at skill creation)

### The paper upload is manual

- **Why the connector can't do it:** the Drive connector (Google's
  `drivemcp.googleapis.com`) takes upload content only inline, as base64 in the tool
  call. A test on 2026-10-07 uploaded 634 B and 20 KB PDFs intact. The smallest real
  paper (217 KB) is too large for a single tool result, and Drive has no append. Details
  are in `references/lessons-learned.md`.
- **Rejected: rclone.** It needs a full-Drive token on disk, and its shared OAuth client
  is being retired in 2026, so every user would also need a Google Cloud OAuth client.
  The user ruled it out for good.
- **Rejected: a local Drive MCP server.** piotr-agier/google-drive-mcp v2.12.0 was
  reviewed. It is technically sound (it talks only to Google, writes its token with
  `0600`, and streams uploads from a local path). But it needs a Google Cloud OAuth
  client, a full-Drive token on disk and community code holding that token, all for a
  step that takes a person ten seconds.
- **Chosen:** the skill finds or downloads the paper, validates it, names it and stages
  it in `ersilia-model-papers/` inside the Downloads folder. The user drags it into
  Drive. The skill verifies the name and size, then clears the staged copy. A paper
  that is already in Drive is copied server-side with `copy_file`, with no manual step.

### The paper gates closing the request issue, and nothing else

Closing the request is what tells the team "done", and papers left for later get
forgotten. On 2026-10-07, 6 of the 10 most recent Ready models had no paper in the
folder. CI and the release are not gated, because they are automated and usually
finished before the skill runs. The user can override the gate explicitly; the summary
then shows the missing paper. *(Since 2026-11-27 the gate applies to Ersilia maintainers
only; see the decisions below.)*

### Never pick a version, never hand-edit CI-owned metadata

These follow the model repos' own `CLAUDE.md`.

## Decisions of 2026-11-27 (agreed with Tiago)

### The skill monitors; it never makes a release

- **Why:** the release is specified in the PR. Since ersilia-model-workflows#22 (25 Nov 2026)
  the `release` job creates it from the merged PR's version label, and `retag` tags the
  image. A skill that also released by hand could publish while the image test was still
  running (eos8gop) or collide with the bot's own tag.
- **What changed:** the skill follows the whole chain (PR test, source test, S3 upload, pack
  build, image tests, retag, post-upload, release, SIF) until the release exists and is
  correct, and closes the request only then. The paths that made or deleted releases
  (`create_release`, `recreate_release_at_head`, and the creation inside
  `unreleased_changes`) are gone from `SKILL.md`. Where CI does not release (a PR merged
  without a label), the skill reports why and what an Ersilia maintainer must do.
- **Scripts:** `release_state.py` stays read-only. Its action names and its
  `proposed.command` are unchanged, and `SKILL.md` treats them as information for a
  maintainer, never something to run. Renaming them was left out to keep this change small.

### The skill is for everyone

- External contributors can follow their model to the final release and close the request
  themselves, which is encouraged. Closing needs the release verified complete (CI green,
  release tag, image retagged, `metadata.yml` Ready with the Release; a lagging catalogue
  is a warning). The skill still asks first, and if `gh` refuses it reports the error.
- **Who is a maintainer:** `gh api repos/ersilia-os/ersilia --jq .permissions.push` prints
  `true`, as in `model-incorporation-request`. Re-running or dispatching workflows is offered
  only to maintainers; anyone else gets the failing run link and is told to ask one.

### The paper is for Ersilia maintainers, and it is mandatory for them

- An external contributor is never asked to upload anything to the shared Drive (they have
  no access) and is not told about the deposit. The summary says Ersilia maintainers file
  the paper, and the paper gate in Step 5 does not apply to them.
- A maintainer must not close the request until the paper is in the folder. The explicit
  "close it without the paper" override stays.
- **New:** a maintainer can say they already uploaded it. The skill accepts that, still
  tries `search_files` when the Drive connector is available, and marks the summary line
  "confirmed by the user" when it could not verify the file.
- **Consequence:** a contributor can close the request without a paper, so a missing paper
  no longer blocks anyone but a maintainer. `--audit-papers` below becomes more important:
  it is the way to catch what the gate no longer does.

## Planned improvements (not implemented)

- **`--audit-papers` mode (higher priority since 2026-11-27).** List every Ready model with no
  paper in the folder, counting shared papers under every sibling's ID and skipping
  `Publication Type: Other`. Then stage the missing ones in batches. A one-off audit and
  backfill was done by hand on 2026-10-07: 7 models, 6 files, all uploaded. This mode would
  make it repeatable, and now that external contributors can close a request without a
  paper, it is how maintainers catch the papers the closing gate no longer holds back.
- **Smoke test of the published image.** Pull `ersiliaos/<id>:<tag>`, run it on
  `examples/run_input.csv` and compare with `run_output.csv`. This checks the artifact
  users actually get, not just CI.
- **A short release note in Slack.** Possibly redundant with the monthly
  `model-incorporation-digest`.
- **Message templates.** `references/messages.md` with the wording for steps 1–5, so
  every run looks the same, as the digest skill does with its Slack template.
