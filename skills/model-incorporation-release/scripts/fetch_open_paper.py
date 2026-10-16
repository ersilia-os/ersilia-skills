#!/usr/bin/env python3
"""fetch_open_paper.py — download a model's paper when it is open access.

    python fetch_open_paper.py "https://doi.org/10.1038/s41467-026-77700-z" /tmp/paper.pdf
    python fetch_open_paper.py "https://arxiv.org/abs/2608.22642" /tmp/paper.pdf

Tries, in order, and keeps the first download that is really a PDF (``%PDF-`` and at
least 30 KB, so an HTML paywall page saved as .pdf never passes):

1. arXiv, when the Publication is an arXiv URL or a 10.48550 DOI;
2. every ``pdf_url`` OpenAlex lists for the DOI, best open-access location first;
3. the Europe PMC render of the PMC copy, when OpenAlex knows a PMCID;
4. publisher PDF URL patterns for open-access publishers (Nature/Springer Nature,
   BMC/SpringerOpen, bioRxiv/medRxiv), derived from the DOI. OpenAlex often marks a
   paper gold OA without any ``pdf_url`` (eos88ir's Nat Commun paper is one), although
   nature.com currently answers scripts with an HTML cookie page, so that case usually
   ends with the user downloading it from ``landing_page``.

Exit codes: 0 = saved; 2 = no open-access PDF could be fetched. ``status`` says why:
``closed`` (OpenAlex says the paper is not OA) or ``not_fetched`` (OA, but every source
failed). Either way the skill then asks the user for the PDF. A paywalled paper is
never worked around.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import POLITE_MAILTO, arxiv_id, emit, fetch, fetch_json, normalise_doi  # noqa: E402

MIN_BYTES = 30 * 1024

# DOI prefixes of preprint servers: arXiv, bioRxiv/medRxiv, ChemRxiv, Research Square,
# Preprints.org. For these the preprint *is* the publication.
PREPRINT_DOI_PREFIXES = ("10.48550/", "10.1101/", "10.26434/", "10.21203/", "10.20944/")

# OpenAlex location versions, best first. Unknown versions sit between accepted and
# submitted, so a labelled preprint is only taken when nothing better is available.
VERSION_RANK = {"publishedVersion": 0, "acceptedVersion": 1, None: 2, "submittedVersion": 3}


def publisher_candidates(doi):
    """Direct PDF URLs for open-access publishers whose URL scheme follows the DOI."""
    candidates = []
    if doi.startswith("10.1038/"):
        candidates.append(f"https://www.nature.com/articles/{doi.split('/', 1)[1]}.pdf")
    if doi.startswith(("10.1186/", "10.1007/", "10.1038/")):
        candidates.append(f"https://link.springer.com/content/pdf/{doi}.pdf")
    if doi.startswith("10.1101/"):
        candidates.append(f"https://www.biorxiv.org/content/{doi}.full.pdf")
        candidates.append(f"https://www.medrxiv.org/content/{doi}.full.pdf")
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("publication", help="the Publication field: a DOI, doi.org URL or arXiv URL")
    parser.add_argument("out", help="where to save the PDF")
    args = parser.parse_args()

    doi = normalise_doi(args.publication)
    arxiv = arxiv_id(args.publication) or arxiv_id(doi)
    report = {
        "publication": args.publication,
        "doi": doi,
        "status": None,
        # Where the user can download it by hand when every scripted source fails
        # (nature.com, for one, serves HTML to scripts even for gold-OA papers).
        "landing_page": f"https://doi.org/{doi}" if doi else args.publication,
        "tried": [],
    }

    # A journal article can have a free preprint while the published version is
    # paywalled (eos1ltv and eos55vx, both Nature Machine Intelligence, on 2026-10-07).
    # Each candidate carries its version so the published one is tried first, and the
    # report says when only a preprint was found.
    journal_article = bool(doi) and not doi.startswith(PREPRINT_DOI_PREFIXES)
    report["journal_article"] = journal_article

    candidates = []  # (source, url, version)
    if arxiv:
        candidates.append(("arxiv", f"https://arxiv.org/pdf/{arxiv}", "submittedVersion"))

    openalex = fetch_json(f"https://api.openalex.org/works/doi:{doi}?mailto={POLITE_MAILTO}") if doi else None
    is_oa = None
    if openalex:
        is_oa = (openalex.get("open_access") or {}).get("is_oa")
        report["oa_status"] = (openalex.get("open_access") or {}).get("oa_status")
        best = openalex.get("best_oa_location") or {}
        if best.get("pdf_url"):
            candidates.append(("openalex_best", best["pdf_url"], best.get("version")))
        for location in openalex.get("locations") or []:
            url = location.get("pdf_url")
            if url and location.get("is_oa") and url != best.get("pdf_url"):
                candidates.append(("openalex_location", url, location.get("version")))
        pmcid = ((openalex.get("ids") or {}).get("pmcid") or "").rsplit("/", 1)[-1]
        if pmcid:
            candidates.append(
                ("europepmc", f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf", None)
            )
    if doi and is_oa is not False:
        candidates += [("publisher", url, "publishedVersion") for url in publisher_candidates(doi)]
    candidates.sort(key=lambda c: VERSION_RANK.get(c[2], 2))

    if not candidates:
        report["status"] = "closed" if is_oa is False else "not_fetched"
        emit(report)
        sys.exit(2)

    for source, url, version in candidates:
        body = fetch(url, timeout=60, binary=True)
        if body is None:
            report["tried"].append({"source": source, "url": url, "result": "download failed"})
            continue
        if not body.startswith(b"%PDF-"):
            report["tried"].append({"source": source, "url": url, "result": "not a PDF (HTML or paywall page)"})
            continue
        if len(body) < MIN_BYTES:
            report["tried"].append({"source": source, "url": url, "result": f"too small ({len(body)} bytes)"})
            continue
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(body)
        report.update(
            status="fetched",
            source=source,
            url=url,
            version=version,
            # True when the paper is a journal article but the free copy is a preprint:
            # the skill then asks the user for the published PDF before staging this one.
            preprint_of_journal_article=journal_article and version == "submittedVersion",
            path=str(out),
            size_kb=round(len(body) / 1024, 1),
        )
        report["tried"].append({"source": source, "url": url, "result": "ok"})
        emit(report)
        return

    report["status"] = "closed" if is_oa is False and not arxiv else "not_fetched"
    emit(report)
    sys.exit(2)


if __name__ == "__main__":
    main()
