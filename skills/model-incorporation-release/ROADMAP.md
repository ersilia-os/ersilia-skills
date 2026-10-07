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
then shows the missing paper.

### Never pick a version, never hand-edit CI-owned metadata

These follow the model repos' own `CLAUDE.md`.

## Planned improvements (not implemented)

- **`--audit-papers` backfill.** List every Ready model with no paper in the folder,
  counting shared papers under every sibling's ID. Then stage the missing ones in
  batches and propose renames for shared papers that carry too few IDs. State on
  2026-10-07: 5 files missing (eos88ir, eos92m1, eos5j3l, eos1ltv,
  eos55vx_eos6a1h) and one rename (`eos4q1a.pdf` → `eos4q1a_eos9p57.pdf`).
- **Smoke test of the published image.** Pull `ersiliaos/<id>:<tag>`, run it on
  `examples/run_input.csv` and compare with `run_output.csv`. This checks the artifact
  users actually get, not just CI.
- **A short release note in Slack.** Possibly redundant with the monthly
  `model-incorporation-digest`.
- **Message templates.** `references/messages.md` with the wording for steps 1–5, so
  every run looks the same, as the digest skill does with its Slack template.
