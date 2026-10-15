#!/usr/bin/env python3
"""check_duplicates.py — is this model already requested in, or part of, the Ersilia Model Hub?

    python check_duplicates.py --publication <url> --source <url> \
        --name "<tool name>" --query "<task> <endpoint>"

Two independent, read-only checks. Prints one JSON object on stdout; warnings go to stderr
and to the ``notes`` list.

* ``exact``   the paper (DOI or arXiv id) or the source repository already appears in a
              ``new-model`` request on ersilia-os/ersilia, open or closed, or in the
              published-models DOI list. Matching is on identifiers only, never on titles.
              For a matched request, ``repo`` is the eosXXXX repository the bot created.
* ``similar`` ``ersilia_search`` by tool name and by task/endpoint across every status, plus
              a scan of the non-Ready models. Models still In progress usually have an empty
              Description, so a text query alone misses them.

``related_requests`` lists requests whose title or body mention the tool name but share no
identifier with this one, which is how a sibling model (the base tool, a variant) shows up.

``verdict`` is ``exact``, ``similar`` or ``none``. A preprint and its journal version have
different DOIs and will not match each other, so always search the base name as well.
"""
import argparse
import csv
import io
import json
import re
import shutil
import subprocess
import sys
import urllib.request

REPO = "ersilia-os/ersilia"
DOI_CSV = ("https://raw.githubusercontent.com/ersilia-os/ersilia-maintenance/main/"
           "files/ErsiliaModelsDOI.csv")
ISSUE_LIMIT = 500          # `gh issue list` cap used here; a full page means we may be truncated
SEARCH_LIMIT = 500         # ersilia_search rejects --limit above 500
MIN_NAME_LEN = 4           # shorter names match too much noise

DOI_RE = re.compile(r'10\.\d{4,9}/[^\s"\'<>\]]+')
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", re.I)
REPO_RE = re.compile(r"(github|gitlab)\.com/([^/\s#?)]+)/([^/\s#?)]+)", re.I)
BOT_REPO_RE = re.compile(r"ersilia-os/(eos[0-9a-z]{4})")


def warn(notes, msg):
    notes.append(msg)
    print(f"warning: {msg}", file=sys.stderr)


def clean_doi(s):
    """Lowercase, drop trailing punctuation and any unbalanced closing parenthesis."""
    s = s.lower().rstrip(".,;")
    while s.endswith(")") and s.count(")") > s.count("("):
        s = s[:-1]
    return s.rstrip("/")


def norm(s):
    """Letters and digits only, lowercase: 'GP-MoLFormer' and 'gp molformer' compare equal."""
    return re.sub(r"[\W_]+", "", (s or "").lower())


def keys_from(publication="", source=""):
    """Identifier keys for a paper and a repository: doi:, arxiv:, repo:."""
    keys = set()
    m = DOI_RE.search(publication or "")
    if m:
        doi = clean_doi(m.group(0))
        keys.add("doi:" + doi)
        a = re.match(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", doi)  # arXiv's own DOIs
        if a:
            keys.add("arxiv:" + a.group(1))
    m = re.search(r"nature\.com/articles/([a-z0-9\-]+)", publication or "", re.I)
    if m:
        keys.add("doi:10.1038/" + m.group(1).lower())
    m = ARXIV_RE.search(publication or "")
    if m:
        keys.add("arxiv:" + m.group(1))
    m = REPO_RE.search(source or "")
    if m:
        name = re.sub(r"\.git$", "", m.group(3))
        keys.add(f"repo:{m.group(1)}.com/{m.group(2)}/{name}".lower())
    return keys


def section(body, header):
    m = re.search(r"^###\s+" + re.escape(header) + r"\s*$(.*?)(?=^###\s+|\Z)",
                  body or "", re.M | re.S)
    return m.group(1).strip() if m else ""


def gh_json(args):
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:300] or f"gh exited {p.returncode}")
    return json.loads(p.stdout)


def bot_repo(number, notes):
    """The eosXXXX repository the approval bot announced on a request, if any."""
    try:
        data = gh_json(["issue", "view", str(number), "--repo", REPO, "--json", "comments"])
    except Exception as e:  # noqa: BLE001 - report and carry on
        warn(notes, f"could not read comments on #{number}: {e}")
        return None
    for c in data.get("comments", []):
        if (c.get("author") or {}).get("login") == "github-actions":
            m = BOT_REPO_RE.search(c.get("body", ""))
            if m:
                return m.group(1)
    return None


def check_requests(cand_keys, name, notes):
    """Match the candidate against every new-model request. Returns (exact, related)."""
    try:
        issues = gh_json(["issue", "list", "--repo", REPO, "--label", "new-model",
                          "--state", "all", "--limit", str(ISSUE_LIMIT),
                          "--json", "number,title,body,state"])
    except Exception as e:  # noqa: BLE001
        warn(notes, f"could not read new-model requests ({e}); request check skipped")
        return [], []
    if len(issues) >= ISSUE_LIMIT:
        warn(notes, f"read {ISSUE_LIMIT} requests, the cap; older ones may be missing")

    exact, related = [], []
    needle = norm(name)
    for it in issues:
        body = it.get("body") or ""
        ks = keys_from(section(body, "Publication"), section(body, "Source Code"))
        hit = sorted(cand_keys & ks)
        entry = {"source": "request", "number": it["number"], "title": it["title"],
                 "state": it["state"].lower()}
        if hit:
            exact.append({**entry, "matched": hit, "repo": bot_repo(it["number"], notes)})
        elif len(needle) >= MIN_NAME_LEN and needle in norm(it["title"] + " " + body):
            related.append(entry)
    return exact, related


def check_published(cand_keys, notes):
    """Match the paper DOI against the published-models list (covers pre-form-era models)."""
    dois = {k[4:] for k in cand_keys if k.startswith("doi:")}
    if not dois:
        return []
    try:
        raw = urllib.request.urlopen(DOI_CSV, timeout=30).read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        warn(notes, f"could not read the published-models list ({e}); list check skipped")
        return []
    out = []
    for row in csv.DictReader(io.StringIO(raw)):
        d = (row.get("doi") or "").strip().lower()
        d = re.sub(r"^(https?://doi\.org/|doi:)", "", d)
        if d and d != "-" and clean_doi(d) in dois:
            out.append({"source": "published-list", "model_id": row.get("model_id"),
                        "slug": row.get("slug"), "matched": ["doi:" + clean_doi(d)]})
    return out


def run_search(args, notes):
    p = subprocess.run(["ersilia_search", *args, "--csv"], capture_output=True, text=True)
    if p.returncode != 0:
        warn(notes, f"ersilia_search {' '.join(args)[:60]} failed: "
                    f"{(p.stderr.strip().splitlines() or ['no output'])[-1][:160]}")
        return []
    return list(csv.DictReader(io.StringIO(p.stdout)))


def check_similar(name, query, notes):
    if not shutil.which("ersilia_search"):
        warn(notes, "ersilia_search is not installed; run `pip install -q "
                    "git+https://github.com/ersilia-os/search-engine.git`. "
                    "Similar-model check skipped")
        return []
    found = {}

    def add(rows, why):
        for r in rows:
            e = found.setdefault(r["Identifier"], {
                "identifier": r["Identifier"], "slug": r.get("Slug"), "title": r.get("Title"),
                "status": r.get("Status"), "task": r.get("Task"), "subtask": r.get("Subtask"),
                "found_by": []})
            if why not in e["found_by"]:
                e["found_by"].append(why)

    if name:
        add(run_search(["--text", name, "--all-statuses", "--limit", "20"], notes), "name")
    if query:
        add(run_search(["--text", query, "--all-statuses", "--limit", "20"], notes),
            "task/endpoint")
    needle = norm(name)
    if len(needle) >= MIN_NAME_LEN:
        nonready = run_search(["--status", "In progress", "--status", "In maintenance",
                               "--status", "Archived", "--limit", str(SEARCH_LIMIT)], notes)
        for r in nonready:
            blob = " ".join(r.get(k) or "" for k in ("Identifier", "Slug", "Title", "Description"))
            if needle in norm(blob):
                add([r], "non-Ready scan")
    return list(found.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publication", default="", help="DOI or arXiv URL of the paper")
    ap.add_argument("--source", default="", help="source code repository URL")
    ap.add_argument("--name", default="", help="the tool or model name used in the paper")
    ap.add_argument("--query", default="", help="task and endpoint words, e.g. 'scaffold hopping'")
    a = ap.parse_args()

    notes = []
    cand = keys_from(a.publication, a.source)
    if not cand:
        warn(notes, "no DOI, arXiv id or repository could be parsed; exact check will find nothing")

    exact, related = check_requests(cand, a.name, notes)
    exact += check_published(cand, notes)
    exact_ids = {e["number"] for e in exact if e["source"] == "request"}
    related = [r for r in related if r["number"] not in exact_ids]
    similar = check_similar(a.name, a.query, notes)

    verdict = "exact" if exact else ("similar" if similar or related else "none")
    print(json.dumps({
        "candidate": {"keys": sorted(cand), "name": a.name, "query": a.query},
        "verdict": verdict, "exact": exact, "similar": similar,
        "related_requests": related, "notes": notes,
    }, indent=2))


if __name__ == "__main__":
    main()
