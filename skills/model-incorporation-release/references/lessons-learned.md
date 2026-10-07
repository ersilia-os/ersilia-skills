# Lessons learned: releasing an incorporated model

Each entry: what you see, why it happens, and what to do. They come from real
incorporations; the model IDs are there so the evidence can be re-read with
`gh run list -R ersilia-os/<id>`. **Add a new entry whenever a release teaches something
new**, in the same shape.

## The CI chain, briefly

Every eos repo carries thin wrappers around `ersilia-os/ersilia-model-workflows`:

| Workflow | Trigger | Jobs (in order) |
|---|---|---|
| Test model on PR | pull request to main | test the model on the PR branch |
| Test and upload model | push to main, `workflow_dispatch` | `test-model-source` → `upload-model-to-s3` → `upload-ersilia-pack` (amd64, arm64, merge-multiarch) |
| Test model image | `workflow_run` of the above | `test-image-amd64` → `test-image-arm64` → `retag-image` → `post-upload` |
| Retag image on release | release published | retag `latest` → tag, write `Release` to metadata, **push to main**, Airtable, S3 |

`post-upload` writes Status Ready, DockerHub, Image Size, the Computational Performance
fields and Release into metadata.yml. It then updates Airtable, syncs the S3
`models.json` catalogue and regenerates the README. These steps leave two or more
`ersilia-bot` "updating … [skip ci]" commits on main. If the repo has **no tags**, it
also creates release `v1.0.0` and retags the image itself.

---

## "Initial commit" failure on every new repo

- **Symptom:** the first "Test and upload model" run, on the template's Initial commit, fails within minutes.
- **Cause:** the template is not a working model. Expected; ignore it.
- **What to do:** nothing. `ci_status.py` lists it under `noise`. If main still holds *only* the Initial commit, the incorporation PR has not been merged (`overall: not_merged`, e.g. eos70bl) and the release step cannot start.

## Releasing while the image test is still running (eos8gop)

- **Symptom:** a person published `v1.0.0` while "Test model image" was running. That run later hit the 6 h limit and was cancelled.
- **What it caused:** a tag now existed, so the next successful post-upload skipped its automatic release. Two "Retag image on release" runs then failed.
- **What to do:** never create or publish a release until `ci_status.py` says `green`. That is the skill's first gate.

## Retag fails with "failed to push some refs" (eos8gop)

- **Symptom:** "Retag image on release" fails at its final push step.
- **Cause:** a manually published release triggers the retag workflow. That workflow checks out the tag's commit, edits metadata.yml and pushes to main. If the bot's commits have moved main past the tag, the push is rejected. eos8gop's tag sat at `b27702b` while main had moved on.
- **What to do:** recreate the release at main HEAD, *after* the bot's final "updating readme" commit. Delete the release and its tag (`gh release delete <tag> -R … --cleanup-tag`), then `gh release create <tag> --target <main HEAD sha>`. This is destructive, so get explicit confirmation. eos8gop's retag succeeded once `v1.0.0` pointed at `e6a6762`, which was HEAD.

## A bot release's tag sits behind main, and that is fine (eos88ir, eos2srx, eos1ltv)

- **Symptom:** `v1.0.0` points at the merge commit, while main has several newer bot commits.
- **Cause:** post-upload creates the release at the upload run's commit and retags the image in the same job. Releases made with a workflow's `GITHUB_TOKEN` trigger no other workflows, so the retag workflow never runs and nothing pushes against the tag.
- **What to do:** nothing. Check that the DockerHub `latest` and `v1.0.0` digests match (`release_state.py` does this). The tag-must-equal-HEAD rule applies **only to manual releases**.

## The bot skips v1.0.0 whenever any tag exists

- **Symptom:** CI is fully green, but no release appeared.
- **Cause:** post-upload's "Check if any tag exists" step found a tag (often one left by an earlier premature release) and skipped creating the release.
- **What to do:** `release_state.py` returns `create_release` with the exact command. A manual release triggers the retag workflow, so target main HEAD after the bot's final commit (see above).

## Image test cancelled after ~6 h (eos8gop)

- **Symptom:** `test-image-amd64` and/or `test-image-arm64` end `cancelled` after about 360 minutes.
- **Cause:** GitHub's 6 h job limit. The architectures run one after the other, so a slow model can need about 12 h in total.
- **What to do:** first check that inference on `examples/run_input.csv` is not pathologically slow (that is a model-fixing problem). Then re-run with `gh workflow run upload-model.yml -R ersilia-os/<id>`, which starts the chain again and does not need an empty commit.

## One architecture fails inside a green image run (eos1ltv)

- **Symptom:** "Test model image" concludes `success`, but `test-image-arm64` failed.
- **Cause:** the workflow publishes the architectures that passed. eos1ltv shipped amd64-only (`Docker Architecture: [AMD64]`).
- **What to do:** not a blocker. Report it as a warning so nobody announces an arm64 image that does not exist, and raise it as follow-up work if arm64 matters for the model.

## The PR was merged on a red PR test (eos1ltv)

- **Symptom:** the latest "Test model on PR" failed, yet main moved on and its runs are green.
- **What to do:** the main-branch runs decide. Mention it in the summary anyway.

## The catalogue lags behind metadata.yml

- **Symptom:** metadata.yml says Ready and `v1.0.0`, but `models.json` on S3 still shows the old state.
- **Cause:** the catalogue is synced from Airtable by a later step.
- **What to do:** report it as a warning, never a failure, and re-check later.

---

## Papers

## Shared papers use joined names

- **Rule:** when several models come from one paper, the folder holds one file named after all of them, sorted and joined with `_`: `eos4ex3_eos6m2k.pdf`, `eos2a9n_eos4b8j.pdf`.
- **How the skill does it:** `paper_target.py` finds the siblings through the catalogue's Publication DOIs. Only **Ready** siblings go into the name. An "In progress" sibling may never ship: eos8he2 cites eos55vx's paper with eos55vx's own title and is still In progress. Ask the user about those.
- **When renaming:** if the paper is already in the folder under a shorter shared name, propose renaming the existing file with Drive `update_file` (the rename keeps its link). Never add a second copy.

## Internal models have no paper

- **Symptom:** an audit on 2026-10-07 found 37 Ready models with no PDF in the folder,
  but 30 of them have `Publication Type: Other`. These are Ersilia-internal models (the
  chembl-antimicrobial series, the lazy-chemvis projectors) whose Publication is a
  GitHub repo or ersilia.io, plus tool wrappers (RDKit, Datamol).
- **What to do:** there is nothing to deposit. `paper_target.py` returns
  `paper_expected: false`, the paper step is skipped, and the request can close.

## Long metadata values wrap

- **Symptom:** a value read from metadata.yml is cut short (eos2e3s's Title ended at
  "…from").
- **Cause:** long YAML values continue on indented lines.
- **What to do:** `read_metadata_fields` folds continuation lines back in. Any new
  parser has to do the same, or title matching in `check_pdf.py` works on half a title.

## Paywall stubs are not papers

- **Symptom:** a "PDF" of a few hundred bytes. The 425-byte `cplank.pdf` and `trimole.pdf` in `assessments_2026-08-31/pdfs/` are XHTML error pages.
- **What to do:** `check_pdf.py` rejects anything that does not start with `%PDF-` or is under 30 KB. It also confirms the paper's identity from the DOI or title on its first pages, so a neighbour's paper is not deposited under the wrong ID.

## Open access does not mean scriptable

- **Symptom:** OpenAlex says eos88ir's Nat Commun paper is `gold`, but it has no `pdf_url`. nature.com's `.pdf` URL also answers scripts with an HTML cookie page.
- **What to do:** after `fetch_open_paper.py` exits 2, ask the user for the PDF and give them the `landing_page` link. Do not try to get around publisher bot protection or paywalls.

## The Drive connector cannot upload a paper

- **Rule:** the connector (Google's own `drivemcp.googleapis.com` server) takes upload content only inline, as base64 in the tool call. Tested on 2026-10-07:
  - 634 B and 20 KB PDFs uploaded intact; the 20 KB one cost about 51K tokens;
  - the smallest real paper (217 KB, about 290K base64 characters) is larger than a single tool result can hold, so Claude cannot read or send it;
  - Drive has no append operation, so it cannot be sent in chunks.
- **How papers get there:**
  - a paper already in Drive goes in with `copy_file` (server-side, any size);
  - a local PDF is staged by `prepare_paper.py` in `ersilia-model-papers/` in the Downloads folder, under
    its canonical name, dragged in by the user, then verified with `search_files`
    (title, and `fileSize` equal to the staged `size_bytes`).
- **Local upload tooling was rejected (2026-10-07).** rclone, and a local Drive MCP server
  (piotr-agier/google-drive-mcp v2.12.0 was reviewed and found technically sound), would
  both need a Google Cloud OAuth client and a full-Drive token on disk, for a step that
  takes a person ten seconds. The upload stays manual.
