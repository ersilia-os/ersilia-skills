#!/usr/bin/env python3
"""paper_target.py — where a model's paper belongs in Drive, and under what name.

    python paper_target.py eos55vx

Prints the model's Title and Publication (from metadata.yml on main), the normalised
DOI, every other Hub model that cites the same publication, and the canonical file
name in the `ersilia_models_articles` folder:

* one model per paper  -> ``eos88ir.pdf``
* a shared paper       -> the Ready IDs sorted and joined, ``eos55vx_eos6a1h.pdf``
  (the folder's existing convention, e.g. ``eos4ex3_eos6m2k.pdf``). Siblings that are
  not Ready are listed separately and left out of the name until the user decides.

It also prints the Drive ``search_files`` queries the skill runs before depositing,
one per sibling, because a shared paper may already be there under a name that starts
with the other model's ID.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    CATALOG_URL,
    PAPERS_FOLDER_ID,
    PAPERS_FOLDER_URL,
    check_model_id,
    emit,
    fetch_json,
    normalise_doi,
    remote_metadata,
    warn,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("model_id")
    args = parser.parse_args()
    model_id = check_model_id(args.model_id)

    metadata = remote_metadata(model_id)
    publication = metadata.get("Publication")
    publication_type = metadata.get("Publication Type")
    doi = normalise_doi(publication)

    # Publication Type "Other" means there is no paper: an Ersilia-internal model whose
    # Publication points at a GitHub repo or ersilia.io, or a wrapper around a tool's
    # docs (RDKit, Datamol). 30 of the 37 Ready models without a PDF in the folder were
    # exactly this on 2026-10-07. The paper step is then not applicable, and it must not
    # block closing the request.
    if publication_type == "Other":
        emit(
            {
                "model_id": model_id,
                "title": metadata.get("Title"),
                "publication": publication,
                "publication_type": publication_type,
                "paper_expected": False,
                "reason": "Publication Type is 'Other': there is no paper to deposit.",
            }
        )
        return

    ready, pending = [], []
    if doi:
        for row in fetch_json(CATALOG_URL) or []:
            other = row.get("Identifier")
            if other and other != model_id and normalise_doi(row.get("Publication")) == doi:
                (ready if row.get("Status") == "Ready" else pending).append(
                    {"id": other, "status": row.get("Status"), "title": row.get("Title")}
                )
    else:
        warn(f"Publication {publication!r} carries no DOI; shared-paper detection skipped.")

    # Only Ready siblings go into the name: an "In progress" entry citing the same paper
    # may never ship (eos8he2 duplicates eos55vx's title), so the user decides on those.
    ids = sorted({model_id, *(s["id"] for s in ready)})
    every_id = sorted({model_id, *(s["id"] for s in ready + pending)})
    emit(
        {
            "model_id": model_id,
            "title": metadata.get("Title"),
            "publication": publication,
            "publication_type": publication_type,
            "paper_expected": True,
            "doi": doi,
            "siblings_ready": sorted(ready, key=lambda s: s["id"]),
            "siblings_pending": sorted(pending, key=lambda s: s["id"]),
            "canonical_name": "_".join(ids) + ".pdf",
            "folder_id": PAPERS_FOLDER_ID,
            "folder_url": PAPERS_FOLDER_URL,
            # Search under every sharing ID, pending ones included: the paper may already
            # be there under a name that starts with another model's ID.
            "drive_queries": [
                f"parentId = '{PAPERS_FOLDER_ID}' and title contains '{i}'" for i in every_id
            ],
        }
    )


if __name__ == "__main__":
    main()
