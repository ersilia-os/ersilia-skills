"""Regression self-test for the literature-digest normalisers and pool selection.

Each case reproduces a real failure from a past run, so a lesson learned once is not lost.
Run from the skill folder before changing `_common.py`, `fetch_gmail.py`, `fetch_slack.py`
or `dedup_and_rank.py`:

    python scripts/selftest.py

Exits 0 when every case passes, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from _common import extract_dois
from enrich_abstracts import doi_candidates, enrich, strip_markup
from dedup_and_rank import _hub_fit, parse_landscape, parse_lmic, score_item, select_pool
from fetch_gmail import normalise_thread
from fetch_slack import normalise_message


def check(name: str, got, want) -> bool:
    """Print one PASS/FAIL line and return whether the case passed."""
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {name}")
    if not ok:
        print(f"      got : {got!r}\n      want: {want!r}")
    return ok


def main() -> int:
    results: list[bool] = []

    # 2026-11-02: the DOI regex stopped at the first "." and returned "10.1021/acs".
    results.append(
        check(
            "DOI keeps dots inside the suffix",
            extract_dois("see 10.1021/acs.jmedchem.6c00791."),
            ["10.1021/acs.jmedchem.6c00791"],
        )
    )
    results.append(
        check(
            "DOI from ACS article URL drops page-id and slug segments",
            extract_dois(
                "https://pubs.acs.org/jmcmar/article/doi/10.1021/acs.jmedchem.6c00791/5460670/"
                "Democratizing-Drug-Discovery"
            ),
            ["10.1021/acs.jmedchem.6c00791"],
        )
    )
    results.append(
        check(
            "DOI from OUP article URL drops the page-id and the login query",
            extract_dois(
                "https://academic.oup.com/nar/advance-article/doi/10.1093/nar/gkag1057/9002501"
                "?login=false"
            ),
            ["10.1093/nar/gkag1057"],
        )
    )
    results.append(
        check(
            "DOI with parentheses in the suffix survives",
            extract_dois("doi:10.1016/S0140-6736(20)30183-5"),
            ["10.1016/s0140-6736(20)30183-5"],
        )
    )

    # Slack: the full DOI must reach the item so the seen-set can match it exactly.
    slack_items = normalise_message(
        {
            "text": "<https://pubs.acs.org/jmcmar/article/doi/10.1021/acs.jmedchem.6c00791/5460670/X>",
            "ts": "1793293638.006779",
            "user_real_name": "A",
        }
    )
    results.append(
        check(
            "Slack item carries the full DOI",
            [i["doi"] for i in slack_items],
            ["10.1021/acs.jmedchem.6c00791"],
        )
    )

    # 2026-11-02: every link in a Scholar alert inherited the thread's first DOI and the
    # thread snippet as its title.
    thread = {
        "id": "t1",
        "subject": "Antibiotic drug discovery - new results",
        "sender": "scholaralerts-noreply@google.com",
        "sender_name": "Google Scholar Alerts",
        "date": "2026-10-30",
        "snippet": "Functional asymmetry of the transmembrane subunits",
        "body_text": (
            "Functional asymmetry of the transmembrane subunits YbhS and YbhR | A Author, B Author"
            " | Frontiers in Microbiology, 2026 | https://doi.org/10.3389/fmicb.2026.1111111\n"
            "[PDF] A second, unrelated paper about antibiotic discovery | C Author | Microbiology,"
            " 2026 | https://www.example.org/paper/two\n"
        ),
    }
    items = normalise_thread(thread)
    results.append(
        check(
            "Gmail entry lines keep their own titles",
            [i["title"] for i in items],
            [
                "Functional asymmetry of the transmembrane subunits YbhS and YbhR",
                "A second, unrelated paper about antibiotic discovery",
            ],
        )
    )
    results.append(
        check(
            "Gmail entries do not inherit another link's DOI",
            [i["doi"] for i in items],
            ["10.3389/fmicb.2026.1111111", None],
        )
    )
    results.append(
        check(
            "Gmail entry keeps its authors",
            [a["name"] for a in items[0]["authors"]],
            ["A Author", "B Author"],
        )
    )

    # 2026-11-10: a plain top-80 held no Slack-shared links (generic titles, no abstract,
    # ranked 340th of 1194) and almost no Gmail alert items.
    ranked = [{"id": i, "source": "biorxiv"} for i in range(10)]
    ranked += [{"id": 10 + i, "source": "gmail"} for i in range(5)]
    ranked += [{"id": 15, "source": "slack"}]
    pool = select_pool(ranked, top_n=3, pin_sources=["slack"], reserve={"gmail": 2})
    results.append(
        check(
            "Pool keeps top-N, every Slack item and the reserved Gmail slots, in rank order",
            [it["id"] for it in pool],
            [0, 1, 2, 10, 11, 15],
        )
    )

    # 2026-11-10: off-topic bioRxiv papers with an abstract out-scored real Hub candidates
    # that arrived as titles only. Hub-relevant items must rank in the upper half.
    skill_dir = Path(__file__).resolve().parent.parent
    landscape = parse_landscape(str(skill_dir / "references" / "search-landscape.md"))
    lmic = parse_lmic(str(skill_dir / "references" / "lmic-countries.md"))
    fixture = json.loads((skill_dir / "tests" / "fixtures" / "hub_ranking_2026-11-10.json").read_text())
    for it in fixture:
        it["score"] = score_item(dict(it), landscape, lmic, set(), date(2026, 11, 3), date(2026, 11, 10))
    order = sorted(fixture, key=lambda it: -it["score"]["total"])
    ranks = sorted(i + 1 for i, it in enumerate(order) if it["hub_candidate"])
    results.append(
        check(
            "Hub-relevant fixture items have a median rank in the top 40 of 91",
            ranks[len(ranks) // 2] <= 40,
            True,
        )
    )
    results.append(
        check(
            "Off-modality title is penalised; small-molecule title is not",
            (_hub_fit({"title": "Single-cell RNA atlas of liver"})[1], _hub_fit({"title": "RNA-targeted aminopyridine compounds"})[1]),
            (3, 0),
        )
    )

    # 2026-11-10: every Gmail item arrived without an abstract and every Slack item with a
    # generic title, so the ranker saw only a few title words.
    results.append(
        check(
            "Crossref JATS abstract is reduced to plain text",
            strip_markup("<jats:title>Abstract</jats:title><jats:p>Models &amp; data <jats:italic>in vitro</jats:italic>.</jats:p>"),
            "Models & data in vitro .",
        )
    )
    results.append(
        check(
            "DOI with a page id and slug is also tried in shorter forms",
            doi_candidates("10.1039/d6dd00444j/1373125/metapli-retrieval"),
            ["10.1039/d6dd00444j/1373125/metapli-retrieval", "10.1039/d6dd00444j/1373125", "10.1039/d6dd00444j"],
        )
    )
    items = [
        {"title": "Looks actually good", "doi": "10.1/a", "source": "slack", "abstract": None},
        {"title": "Kept title", "doi": "10.1/b", "source": "gmail", "abstract": None},
        {"title": "Has one", "doi": "10.1/c", "source": "gmail", "abstract": "Existing."},
        {"title": "Unresolvable", "doi": "10.1/d", "source": "gmail", "abstract": None},
    ]
    fake = {"10.1/a": {"title": "Real title", "abstract": "Real abstract."}, "10.1/b": {"title": "Other", "abstract": "B abstract."}}
    gained = enrich(items, {}, workers=1, lookup=lambda it: fake.get(it["doi"]))
    results.append(
        check(
            "Enrichment fills abstracts, retitles only placeholder Slack items, leaves the rest",
            (gained, [it["title"] for it in items], [it["abstract"] for it in items]),
            (2, ["Real title", "Kept title", "Has one", "Unresolvable"], ["Real abstract.", "B abstract.", "Existing.", None]),
        )
    )

    passed = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
