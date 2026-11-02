"""Regression self-test for the literature-digest normalisers.

Each case reproduces a real failure from a past run, so a lesson learned once is not lost.
Run from the skill folder before changing `_common.py`, `fetch_gmail.py` or `fetch_slack.py`:

    python scripts/selftest.py

Exits 0 when every case passes, 1 otherwise.
"""

from __future__ import annotations

import sys

from _common import extract_dois
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

    passed = sum(results)
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
