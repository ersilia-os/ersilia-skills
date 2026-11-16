"""Compare the document with the same author's own writing from before ChatGPT.

A sudden change in someone's style is more telling than how they compare with "average
human text": it controls for their field, their English and their habits. This script
collects the author's earlier text, scores it like the document, and reports where the
document falls in the author's own range.

Sources for the author's earlier text (use one):

    --openalex-author A5023888391   their abstracts in OpenAlex, published up to 2022.
                                    Sends only the author ID to OpenAlex. Find the ID
                                    yourself and confirm it with the user first; it is a
                                    lookup about a named person.
    --files a.txt b.pdf ...         text the user supplies (their old emails, reports, drafts).

Abstracts are co-written, so treat an OpenAlex baseline as the author's *group* style.
First-author papers are preferred (--first-author-only).

Writes ``<work>/baseline.json``. It compares style only; the document itself is never sent
anywhere (only the author ID goes to OpenAlex). Files given with --files that are PDF or DOCX
need the env: ``conda run -n ai-text-detection python baseline.py --files ...``.

Usage:
    python baseline.py --openalex-author A5023888391 [--first-author-only] [--max 40]
    python baseline.py --files old1.txt old2.txt
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from lib.common import USER_AGENT, WORK_DIR, die, read_json, warn, write_json
from lib.text import chunks, words
from stylometry import FEATURES, features


def openalex_texts(author: str, first_only: bool, n: int) -> list[dict]:
    """Abstracts (reconstructed from the inverted index) published up to 2022."""
    url = (
        "https://api.openalex.org/works?filter="
        + urllib.parse.quote(
            f"author.id:{author},publication_year:<2023,has_abstract:true"
        )
        + "&per-page=100&sort=publication_year:desc&select=id,title,publication_year,abstract_inverted_index,authorships"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    out = []
    for w in data.get("results", []):
        auths = w.get("authorships") or []
        if first_only and (
            not auths or author not in (auths[0].get("author", {}).get("id") or "")
        ):
            continue
        inv = w.get("abstract_inverted_index") or {}
        pos = sorted((p, word) for word, ps in inv.items() for p in ps)
        text = " ".join(word for _, word in pos)
        if len(words(text)) >= 120:
            out.append(
                {
                    "source": w["id"],
                    "year": w.get("publication_year"),
                    "title": w.get("title"),
                    "text": text,
                }
            )
        if len(out) >= n:
            break
    return out


def file_texts(paths: list[str]) -> list[dict]:
    """Plain text of user-supplied files (PDF/DOCX via extract_text in the env)."""
    import subprocess
    import tempfile

    out = []
    for p in paths:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("extract_text.py")),
                    p,
                    "--work",
                    tmp,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            doc = read_json(Path(tmp) / "text.json")
            if proc.returncode != 0 or not doc:
                warn(f"could not read {p}: {proc.stderr.strip()[:200]}")
                continue
            out.append(
                {"source": p, "year": None, "title": Path(p).name, "text": doc["text"]}
            )
    return out


def main(argv: list[str] | None = None) -> int:
    """Build the author's baseline and compare the document with it."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--openalex-author")
    g.add_argument("--files", nargs="+")
    p.add_argument("--first-author-only", action="store_true")
    p.add_argument("--max", type=int, default=40)
    args = p.parse_args(argv)
    work = Path(args.work)

    texts = (
        openalex_texts(args.openalex_author, args.first_author_only, args.max)
        if args.openalex_author
        else file_texts(args.files)
    )
    if len(texts) < 3:
        die(f"only {len(texts)} usable earlier text(s); a baseline needs at least 3")
    windows = []
    for t in texts:
        doc = {
            "text": t["text"],
            "sections": [{"title": "baseline", "start": 0, "end": len(t["text"])}],
        }
        for c in chunks(doc):
            f = features(c["text"])
            windows.append(
                {
                    "source": t["source"],
                    "year": t["year"],
                    "text": c["text"],
                    **{k: f[k] for k in FEATURES},
                }
            )
    sty = read_json(work / "stylometry.json") or {}
    doc_vals: dict[str, float] = {}
    for k in FEATURES:
        vals = [
            w[k]
            for w in sty.get("windows", [])
            if w.get(k) == w.get(k) and w.get(k) is not None
        ]
        if vals:
            doc_vals[k] = statistics.median(vals)

    comparison = {}
    for k, v in doc_vals.items():
        base = sorted(
            w[k] for w in windows if w.get(k) is not None and w.get(k) == w.get(k)
        )
        if len(base) < 3:
            continue
        below = sum(1 for b in base if b < v) / len(base)
        comparison[k] = {
            "document_median": v,
            "baseline_median": statistics.median(base),
            "baseline_min": base[0],
            "baseline_max": base[-1],
            "share_of_baseline_below": below,
            "outside_range": v < base[0] or v > base[-1],
        }
    for w in windows:
        w.pop("text", None)
    write_json(
        work / "baseline.json",
        {
            "source": "openalex" if args.openalex_author else "files",
            "n_texts": len(texts),
            "n_windows": len(windows),
            "years": sorted({t["year"] for t in texts if t["year"]}),
            "comparison": comparison,
            "windows": windows,
        },
    )
    print(f"baseline: {len(texts)} earlier text(s), {len(windows)} window(s)")
    for k, c in comparison.items():
        flag = "  OUTSIDE the author's earlier range" if c["outside_range"] else ""
        print(
            f"  {k:<15} document {c['document_median']:.3f}; earlier writing {c['baseline_median']:.3f} "
            f"(range {c['baseline_min']:.3f}-{c['baseline_max']:.3f}){flag}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
