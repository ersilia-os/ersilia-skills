# Profile — Analysis

Applies to Airtable `Type = Analysis`. 69 of 179 repos, effectively tied with Package for the
largest group. The written spec is `ersilia-os/eos-analysis-template/CLAUDE.md`, which is the
most prescriptive `CLAUDE.md` in the org. Good real-world examples:
`pharmacogx-embeddings` (100-line README), `mtb-targeted-protein-degradation` (97 lines,
and one of only three repos org-wide with a `CLAUDE.md`).

## Expected layout — this is a closed set

```
├── data/
│   ├── raw/          # original, untouched datasets (eosvc-tracked, not in git)
│   └── processed/    # cleaned and transformed datasets (eosvc-tracked, not in git)
├── scripts/          # standalone scripts, numbered sequentially (01_, 02_, ...)
├── notebooks/        # Jupyter notebooks for exploration and prototyping
├── assets/           # images, figures, static resources
├── output/           # results, numbered to match the scripts that produced them (not in git)
├── src/              # core source code and reusable modules
├── tools/            # helper utilities and development tools
├── docs/             # documentation and reports
├── tmp/              # temporary files (not in git)
└── requirements.txt  # version-pinned dependencies
```

Not all folders are mandatory. But the set is closed: *"Do **not** create new folders at the
root level outside the ones listed above."* That is why `ANA-EXTRA-ROOT-DIR` is a Blocker
rather than a Should-fix — it is the one layout rule the template states as a prohibition.

Before reporting an unused folder as cruft, note the template's own instruction: *"Before
wrapping up the repository, ask before removing any unused folders."* The audit reports; it
never proposes deletion as a certainty.

## Normative rules, quoted from the template `CLAUDE.md`

**Version control**
- *"**Git** tracks code only: `scripts/`, `notebooks/`, `src/`, `tools/`, `docs/`, `assets/`"*
- *"**eosvc** tracks data: `data/` and `output/` are linked to an S3 bucket and excluded from git"*
- *"`access.json` records whether data/output are public or private"*
- *"Empty folders are preserved with `.gitkeep` files. As soon as a folder contains data or
  files, remove the `.gitkeep` since it is no longer needed."*
- Status badge under the H1, three states: `pending` (red) → `in progress` (orange) → `ready` (green).

**Hard requirements**
- *"All Python plotting should strictly use the [stylia](https://github.com/ersilia-os/stylia) library."*
  Invoke the `/stylia-plotting` skill for guidance.
- *"Scripts in `scripts/` must be numbered sequentially (`01_preprocess.py`, `02_train.py`, ...)
  and outputs in `output/` should follow the same numbering."*

**Scientific rigor**
- *"Citations must be real. Never invent paper titles, authors, DOIs, journal names, or publication years."*
- *"Claims need sources."* Distinguish an observation from a claim needing a citation.
- *"Record dataset provenance … record the version or snapshot date in `scripts/README.md` or
  as a comment in the downloading script. Datasets without a recorded version are not reproducible."*
- *"Set random seeds … Use a project-wide `RANDOM_SEED` constant in `src/default.py`."*

**Naming and structure**
- Project-wide constants go in `src/default.py`, `ALL_CAPS`.
- Scripts importing from `src/` must open with exactly this preamble:
  ```python
  import os
  import sys
  root = os.path.dirname(os.path.abspath(__file__))
  sys.path.append(os.path.join(root, "..", "src"))
  ```
- *"Declare input and output folder paths as variables at the top of the script (module level,
  not inside functions) and ensure they exist with `os.makedirs(..., exist_ok=True)`. Do not
  create folders inside functions unless strictly necessary."*

**README**
- *"Aim for ~50 lines for the root README — if it grows beyond that, move the long-form content
  into `docs/`."* The checker's threshold is 60 non-blank lines, to leave headroom.
- *"Avoid: copying the folder tree (link to the structure section in `CLAUDE.md` instead),
  badge collections beyond the status badge, generic Installation / Contributing / License
  boilerplate, AI-style restatements of what each function does."*
- *"Do not replicate the folder structure or document individual scripts."*
- `scripts/README.md` is optional. When present: one to three sentences per script, no
  inputs/outputs (those belong in the script docstring), and **any key decision stated
  explicitly** — *"If the script encodes a key decision (a threshold, a cutoff, a minimum
  number of molecules, a model choice), state that value and its rationale."*

**docs/**
- Methodology notes, literature summaries, decision logs, and AI-generated reports all live
  in `docs/` — *"these should land here, not as ad-hoc files at the root"*.
- Naming: `YYYY-MM-DD_topic.md` or `NN_topic.md`.

## What the audit does not check

The template's **Human sign-off** rules — never choose a threshold, never drop data points,
never interpret results autonomously, never delete files, `data/raw/` is read-only — govern
how an agent behaves inside the repo. They are not statically checkable, and this skill does
not attempt to infer past violations from the tree. If a `scripts/README.md` documents a
threshold, that is a good sign; the absence of one is `ANA-NO-PROVENANCE` territory at most.

## Reality check

`eos-analysis-template` itself ships a zero-byte `requirements.txt` against its own rule
*"Pin versions in `requirements.txt`"*, and documents `src/`, `tools/` and `output/` in both
its README and `CLAUDE.md` while shipping none of the three. Both are real findings; the
template being the source of the rule does not exempt it.
