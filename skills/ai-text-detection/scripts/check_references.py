"""Check that every reference in the document exists and is what it claims to be.

Fabricated references are the most defensible evidence of unchecked LLM use: anyone can
re-run the lookups. Each reference gets one status:

    ok                    found; title matches (and first author / year when given)
    metadata-mismatch     the work exists but the year or first author differ (humans do this too)
    doi-points-elsewhere  the DOI resolves to a different work than the one described
    doi-not-registered    the DOI is unknown to Crossref, DataCite and the DOI resolver
    not-found             no DOI and no matching record in Crossref or OpenAlex
    unverifiable          too little to search on (web pages, personal communications, ...)

Every status lists the URLs that were queried, so the user can show the check. Only the
reference strings are sent (to Crossref, DataCite, doi.org, OpenAlex, arXiv): never the
document text. Responses are cached in the work folder.

Input: the reference list from text.json, or ``--refs refs.json`` written by Claude when the
list needs manual splitting: ``[{"raw": "...", "doi": "...", "title": "...", "year": 2021,
"first_author": "Smith"}]`` (only ``raw`` is required).

Writes ``<work>/references.json``.

Usage:
    python check_references.py [--work /tmp/ai_text_detection] [--refs refs.json] [--max 200]
"""

from __future__ import annotations

import argparse
import difflib
import html
import itertools
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lib.common import USER_AGENT, WORK_DIR, read_json, warn, write_json
from lib.text import load_text, unligature

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.IGNORECASE)
ARXIV_RE = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5})(v\d+)?", re.IGNORECASE)
ISBN_RE = re.compile(r"ISBN(?:-1[03])?:?\s*([0-9Xx][0-9Xx\- ]{8,16}[0-9Xx])")
YEAR_RE = re.compile(r"\((?:19|20)\d\d[a-z]?\)|\b(?:19|20)\d\d[a-z]?\b")
START_RE = re.compile(r"^\s*(?:\[\d{1,3}\]|\d{1,3}\.|\d{1,3}\))\s+")
STOP = {
    "the",
    "of",
    "and",
    "in",
    "on",
    "for",
    "a",
    "an",
    "to",
    "with",
    "by",
    "from",
    "at",
    "as",
    "is",
    "are",
    "its",
    "via",
    "using",
    "into",
}
CACHE: dict[str, object] = {}


def norm(s: str) -> str:
    """Lower-case, ligatures expanded, accents and punctuation removed."""
    s = unicodedata.normalize("NFKD", unligature(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def tokens(s: str) -> list[str]:
    """Content tokens for title matching."""
    return [t for t in norm(s).split() if len(t) > 2 and t not in STOP]


def guess_title(raw: str) -> str | None:
    """The likely title segment of a reference string: the segment after the authors with
    the most real words (numbers don't count, so "Cell 180, 688-702 (2020)" never wins)."""
    segs = [x.strip() for x in re.split(r"[.?]\s+|[\u201c\u201d\"]", raw) if x.strip()]

    def nwords(x: str) -> int:
        return sum(1 for t in tokens(x) if t.isalpha() and len(t) > 2)

    segs = [x for x in segs[1:] if nwords(x) >= 2 and not DOI_RE.search(x)]
    return max(segs, key=nwords) if segs else None


def containment(title: str, raw: str) -> float:
    """How well a record title matches the reference, 0-1.

    The larger of: token Dice overlap with the guessed title segment (so a short generic
    title cannot match a long specific one), and character similarity of the two with
    spaces and punctuation removed (so typos, lost dashes and ligatures don't break a
    match). Without a guessable title segment, the share of the record title found
    anywhere in the reference.
    """
    tt = tokens(title)
    if not tt:
        return 0.0
    guess = guess_title(raw)
    if not guess:
        rt = set(tokens(raw))
        return sum(t in rt for t in tt) / len(tt)
    gt = set(tokens(guess))
    dice = 2 * len(set(tt) & gt) / (len(set(tt)) + len(gt))
    a, b = norm(title).replace(" ", ""), norm(guess).replace(" ", "")
    chars = difflib.SequenceMatcher(None, a, b).ratio() if a and b else 0.0
    return max(dice, chars)


def surname_in(surname: str, text: str) -> bool:
    """Whether a surname appears in the text, ignoring accents, case and punctuation."""
    sn = norm(surname).replace(" ", "")
    return len(sn) <= 2 or sn in norm(text).replace(" ", "")


BAD_RECORD = re.compile(
    r"^(faculty opinions|table|figure|fig\.|supplementary|correction|erratum|retraction|author correction|publisher correction)\b",
    re.IGNORECASE,
)


def split_references(text: str) -> list[str]:
    """One string per reference from the reference block."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []
    # Numbered references running on inside lines ("... (2019). 2. Gromski, P. S., ..."):
    # split at markers whose numbers go up one by one.
    flat = " ".join(lines)
    marks = [
        m
        for m in re.finditer(
            r"(?:^|(?<=\s))(\d{1,3})\.\s+(?=[A-Z][^\s,.]*[,.\s])", flat
        )
    ]
    seq, want = [], 1
    for m in marks:
        if int(m.group(1)) == want:
            seq.append(m)
            want += 1
    if len(seq) >= 3 and len(seq) > len(lines):
        bounds = [m.start() for m in seq] + [len(flat)]
        return [
            START_RE.sub("", flat[a:b]).strip() for a, b in itertools.pairwise(bounds)
        ]
    numbered = sum(bool(START_RE.match(ln)) for ln in lines)
    if numbered >= max(3, len(lines) // 3):
        refs, cur = [], ""
        for ln in lines:
            if START_RE.match(ln) and cur:
                refs.append(cur)
                cur = ln
            else:
                cur = f"{cur} {ln}".strip()
        refs.append(cur)
        return [START_RE.sub("", r) for r in refs]
    # Author-year lists: extraction already gives one block per reference.
    return lines


def get(url: str, accept_404: bool = True) -> tuple[int, object]:
    """(status, parsed JSON or None), cached, with a polite delay."""
    if url in CACHE:
        return CACHE[url]  # type: ignore[return-value]
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    out: tuple[int, object]
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
                try:
                    out = (r.status, json.loads(body))
                except json.JSONDecodeError:
                    out = (r.status, body)
                break
        except urllib.error.HTTPError as e:
            if e.code in (404, 400, 410) and accept_404:
                out = (e.code, None)
                break
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            out = (e.code, None)
            break
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < 2:
                time.sleep(2)
                continue
            out = (-1, str(e))
    time.sleep(0.15)
    if out[0] != -1:  # never cache a network failure: retry next run
        CACHE[url] = out
    return out


def crossref_doi(doi: str) -> dict | None:
    """Crossref metadata for a DOI (title, first author, year), or None."""
    st, data = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    if st != 200 or not isinstance(data, dict):
        return None
    m = data["message"]
    return {
        "title": html.unescape(" ".join(m.get("title") or [""])),
        "first_author": ((m.get("author") or [{}])[0]).get("family"),
        "year": ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0],
        "venue": " ".join(m.get("container-title") or []),
        "registry": "Crossref",
    }


def datacite_doi(doi: str) -> dict | None:
    """DataCite metadata for a DOI (datasets, software, some preprints), or None."""
    st, data = get(f"https://api.datacite.org/dois/{urllib.parse.quote(doi)}")
    if st != 200 or not isinstance(data, dict):
        return None
    a = data["data"]["attributes"]
    return {
        "title": ((a.get("titles") or [{}])[0]).get("title", ""),
        "first_author": ((a.get("creators") or [{}])[0]).get("familyName"),
        "year": a.get("publicationYear"),
        "venue": a.get("publisher"),
        "registry": "DataCite",
    }


def doi_exists(doi: str) -> bool:
    """Whether doi.org knows the DOI at all (any registration agency)."""
    st, data = get(f"https://doi.org/api/handles/{urllib.parse.quote(doi)}")
    return st == 200 and isinstance(data, dict) and data.get("responseCode") == 1


def _pick(cands: list[dict], raw: str) -> tuple[dict | None, float]:
    """Best candidate: title similarity, nudged by matching year and first author."""
    years = {int(y.strip("()")[:4]) for y in YEAR_RE.findall(raw)}
    best, best_key, best_score = None, -1.0, 0.0
    for c in cands:
        if not c.get("title") or BAD_RECORD.match(c["title"]):
            continue
        score = containment(c["title"], raw)
        key = score
        if c.get("year") and years and any(abs(int(c["year"]) - y) <= 1 for y in years):
            key += 0.05
        if c.get("first_author") and surname_in(c["first_author"], raw):
            key += 0.05
        if key > best_key:
            best, best_key, best_score = c, key, score
    return best, best_score


def search(raw: str) -> tuple[dict | None, float, list[str], bool]:
    """Best match in Crossref, OpenAlex, then Semantic Scholar: (record, score, urls, failed).

    ``failed`` is True when a lookup could not be completed (network), so a miss is not
    taken as evidence that the reference doesn't exist.
    """
    urls, cands, failed = [], [], False
    q = urllib.parse.quote(raw[:300])
    url = f"https://api.crossref.org/works?query.bibliographic={q}&rows=5&select=DOI,title,author,issued,container-title"
    urls.append(url)
    st, data = get(url)
    failed |= st == -1
    if st == 200 and isinstance(data, dict):
        for m in data["message"].get("items", []):
            cands.append(
                {
                    "title": html.unescape(" ".join(m.get("title") or [""])),
                    "doi": m.get("DOI"),
                    "first_author": ((m.get("author") or [{}])[0]).get("family"),
                    "year": ((m.get("issued") or {}).get("date-parts") or [[None]])[0][
                        0
                    ],
                    "venue": " ".join(m.get("container-title") or []),
                    "registry": "Crossref",
                }
            )
    best, score = _pick(cands, raw)
    if score < 0.85:
        url = f"https://api.openalex.org/works?search={q}&per-page=5&select=id,doi,title,authorships,publication_year"
        urls.append(url)
        st, data = get(url)
        failed |= st == -1
        if st == 200 and isinstance(data, dict):
            for w in data.get("results", []):
                auth = (w.get("authorships") or [{}])[0].get("author", {}).get(
                    "display_name"
                ) or ""
                cands.append(
                    {
                        "title": w.get("title") or "",
                        "doi": (w.get("doi") or "").replace("https://doi.org/", "")
                        or None,
                        "first_author": auth.split()[-1] if auth else None,
                        "year": w.get("publication_year"),
                        "venue": None,
                        "registry": "OpenAlex",
                        "openalex": w.get("id"),
                    }
                )
        best, score = _pick(cands, raw)
    if score < 0.85:
        guess = guess_title(raw) or raw[:200]
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/search/match?query="
            + urllib.parse.quote(guess[:200])
            + "&fields=title,year,authors,externalIds"
        )
        urls.append(url)
        st, data = get(url)
        failed |= st in (-1, 429)
        if st == 200 and isinstance(data, dict):
            for w in data.get("data", []):
                auth = ((w.get("authors") or [{}])[0]).get("name") or ""
                cands.append(
                    {
                        "title": w.get("title") or "",
                        "doi": (w.get("externalIds") or {}).get("DOI"),
                        "first_author": auth.split()[-1] if auth else None,
                        "year": w.get("year"),
                        "venue": None,
                        "registry": "Semantic Scholar",
                    }
                )
        best, score = _pick(cands, raw)
    return best, score, urls, failed


def isbn_valid(isbn: str) -> bool:
    """ISBN-10 or ISBN-13 checksum."""
    s = re.sub(r"[^0-9Xx]", "", isbn).upper()
    if len(s) == 10:
        total = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(s))
        return total % 11 == 0
    if len(s) == 13 and s.isdigit():
        return sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s)) % 10 == 0
    return False


def compare(rec: dict, raw: str, given: dict) -> list[str]:
    """Differences between a found record and what the reference states."""
    issues = []
    years = {int(y.strip("()")[:4]) for y in YEAR_RE.findall(raw)}
    if given.get("year"):
        years = {int(given["year"])}
    if rec.get("year") and years and all(abs(int(rec["year"]) - y) > 1 for y in years):
        issues.append(
            f"year: reference says {sorted(years)}, record says {rec['year']}"
        )
    fa = given.get("first_author") or ""
    if rec.get("first_author"):
        surname = rec["first_author"]
        if fa and not surname_in(surname, fa):
            issues.append(
                f"first author: reference says {fa}, record says {rec['first_author']}"
            )
        elif not fa and not surname_in(surname, raw):
            issues.append(
                f"first author {rec['first_author']} does not appear in the reference"
            )
    return issues


def find_doi(ref: dict, raw: str, out: dict) -> str | None:
    """The reference's DOI: the one given, else one found in the text. A DOI broken by a
    stray space after a dot ("10.1128/aac. 02490-20") is rejoined; an incomplete one is
    noted and dropped."""
    if ref.get("doi"):
        return ref["doi"]
    raw_fixed = re.sub(
        r"(\b10\.\d{4,9}/[^\s\"<>]*\.)\s+(\d[\w.\-\u2013]+)", r"\1\2", raw
    )
    m = DOI_RE.search(raw_fixed)
    doi = m.group(1).rstrip(".,;)]}").replace("\u2013", "-") if m else None
    if doi and len(doi.split("/", 1)[1]) < 5:
        out["issues"].append(f"DOI '{doi}' is incomplete; searched by title instead")
        return None
    return doi


def check_doi(doi: str, ref: dict, raw: str, out: dict) -> dict:
    """A reference with a DOI: is it registered, and does it belong to this work?"""
    out["doi"] = doi
    out["queried"].append(f"https://api.crossref.org/works/{doi}")
    rec = crossref_doi(doi)
    if rec is None:
        out["queried"].append(f"https://api.datacite.org/dois/{doi}")
        rec = datacite_doi(doi)
    if rec is None:
        out["queried"].append(f"https://doi.org/api/handles/{doi}")
        if doi_exists(doi):
            out.update(
                status="ok", found={"doi": doi, "registry": "doi.org (no metadata)"}
            )
            out["issues"].append(
                "DOI resolves but its registry gives no metadata to compare"
            )
            return out
        out["status"] = "doi-not-registered"
        return out
    rec["doi"] = doi
    out["found"] = rec
    rest = DOI_RE.sub("", raw)
    score = containment(rec["title"], rest) if rec.get("title") else 1.0
    out["title_match"] = round(score, 2)
    if len(tokens(rest)) >= 6 and score < 0.5 and rec.get("registry") == "DataCite":
        # Dataset and software DOIs often carry a different title than the citation.
        out["status"] = "metadata-mismatch"
        out["issues"].append(
            f'the DOI is a dataset or software record titled "{rec["title"]}"'
        )
        return out
    if len(tokens(rest)) >= 6 and score < 0.5:
        out["status"] = "doi-points-elsewhere"
        out["issues"].append(f'the DOI belongs to: "{rec["title"]}"')
        return out
    out["issues"] += compare(rec, raw, ref)
    out["status"] = "metadata-mismatch" if out["issues"] else "ok"
    return out


def check_arxiv(arxiv_id: str, raw: str, out: dict) -> dict:
    """A reference with an arXiv id: does the id exist, and is it this work?"""
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    out["queried"].append(url)
    st, body = get(url)
    if not (
        st == 200
        and isinstance(body, str)
        and "<entry>" in body
        and "Error" not in body.split("<entry>")[1][:200]
    ):
        out["status"] = "doi-not-registered"
        out["issues"].append("arXiv id not found")
        return out
    title = re.sub(
        r"\s+",
        " ",
        re.search(r"<entry>.*?<title>(.*?)</title>", body, re.DOTALL).group(1),
    )
    score = containment(title, raw)
    out["found"] = {"title": title, "registry": "arXiv", "arxiv": arxiv_id}
    out["title_match"] = round(score, 2)
    out["status"] = (
        "ok"
        if score >= 0.5 or len(tokens(ARXIV_RE.sub("", raw))) < 6
        else "doi-points-elsewhere"
    )
    if out["status"] != "ok":
        out["issues"].append(f'the arXiv id belongs to: "{title}"')
    return out


def check_by_search(ref: dict, raw: str, out: dict) -> dict:
    """A reference without an identifier: search for its title."""
    rec, score, urls, failed = search(raw)
    out["queried"] += urls
    out["title_match"] = round(score, 2)
    if rec and score >= 0.85:
        out["found"] = rec
        out["issues"] += compare(rec, raw, ref)
        out["status"] = "metadata-mismatch" if out["issues"] else "ok"
    elif rec and score >= 0.6:
        out["found"] = rec
        out["status"] = "metadata-mismatch"
        out["issues"].append(
            f'closest record only partly matches the title ({score:.0%}): "{rec["title"]}"'
        )
    elif failed:
        out["status"] = "unverifiable"
        out["issues"].append(
            "a lookup failed (network); re-run to check this reference"
        )
    else:
        out["status"] = "not-found"
        if re.search(r"https?://|www\.", raw) or not YEAR_RE.search(raw):
            # Web pages, reports and software are often absent from Crossref/OpenAlex.
            out["status"] = "unverifiable"
            out["issues"].append(
                "not in Crossref/OpenAlex; looks like a web page, report or software"
            )
        if rec:
            out["issues"].append(
                f'closest record ({score:.0%} title match): "{rec["title"]}"'
            )
    return out


def check_one(ref: dict, own_doi: str | None = None) -> dict:
    """Status of one reference. ``own_doi`` (the document's own DOI, e.g. from a page
    footer that leaked into the list) is never taken as the reference's DOI."""
    raw = ref["raw"]
    if own_doi:
        raw = re.sub(
            r"(?:https?://doi\.org/)?" + re.escape(own_doi),
            " ",
            raw,
            flags=re.IGNORECASE,
        )
    out = {
        "raw": ref["raw"],
        "status": None,
        "found": None,
        "issues": [],
        "queried": [],
    }
    doi = find_doi(ref, raw, out)
    if doi:
        return check_doi(doi, ref, raw, out)
    m = ARXIV_RE.search(raw)
    if m:
        return check_arxiv(m.group(1), raw, out)
    m = ISBN_RE.search(raw)
    if m and not isbn_valid(m.group(1)):
        out["issues"].append(f"ISBN {m.group(1)} fails its checksum")
    if len(tokens(raw)) < 5 or re.search(
        r"personal communication|unpublished|in preparation|submitted",
        raw,
        re.IGNORECASE,
    ):
        out["status"] = "unverifiable"
        return out
    if re.match(r"^\s*https?://\S+\s*$", raw):
        out["status"] = "unverifiable"
        out["issues"].append("bare URL; open it to check")
        return out
    return check_by_search(ref, raw, out)


def own_doi_of(doc: dict) -> str | None:
    """The document's own DOI: in its metadata, or repeated on its pages (a footer)."""
    meta_text = " ".join(str(v) for v in (doc.get("metadata") or {}).values())
    found = DOI_RE.findall(meta_text)
    body_dois = DOI_RE.findall(doc.get("text", ""))
    if not found and body_dois:
        common = max(set(body_dois), key=body_dois.count)
        found = [common] if body_dois.count(common) >= 3 else []
    return found[0].rstrip(".,;)]}") if found else None


def main(argv: list[str] | None = None) -> int:
    """Check every reference and write references.json."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--work", default=str(WORK_DIR))
    p.add_argument("--refs", help="structured references (JSON list) written by Claude")
    p.add_argument("--max", type=int, default=200)
    args = p.parse_args(argv)
    work = Path(args.work)
    cache_file = work / "refcache.json"
    CACHE.update({k: tuple(v) for k, v in (read_json(cache_file) or {}).items()})

    own_doi = own_doi_of(read_json(work / "text.json") or {})
    if args.refs:
        refs = read_json(args.refs) or []
    else:
        refs = [
            {"raw": r}
            for r in split_references(load_text(work).get("references_text", ""))
        ]
    if len(refs) > args.max:
        warn(f"checking the first {args.max} of {len(refs)} references")
        refs = refs[: args.max]
    results = []
    for i, ref in enumerate(refs, 1):
        r = check_one(ref, own_doi)
        r["n"] = i
        results.append(r)
        print(f"[{i}/{len(refs)}] {r['status']:<20} {r['raw'][:90]}", flush=True)
    write_json(cache_file, CACHE)
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    write_json(work / "references.json", {"references": results, "counts": counts})
    print(
        "references: "
        + (
            ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
            or "none in the document"
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
