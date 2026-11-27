"""Show the precalculation queue from the Airtable Precalculations table.

For every calculation column, list the snapshots that are:

* ready     - status "To do" and every dependency is met
* blocked   - status "Blocked" (or "To do" with an unmet dependency)
* ongoing   - status "Ongoing"

It also flags rows where the table contradicts the dependency rules, for
example eosframes marked To do while reference_library_1M_v0 is not yet in
isaura, or eosframes still Blocked although the reference library is done (the
unblock automation missed it). The script only reads; it never writes.

Usage:
    python build_queue.py --airtable precalc.json
    python build_queue.py --airtable precalc.json --calc eosframes --json queue.json
    python build_queue.py --from-api
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from _precalc import CALCULATIONS, DEPENDENCIES, add_source_args, load_records


def dependency_met(row: dict, calc: str) -> bool:
    """Return True when every calculation that ``calc`` waits for is finished."""
    if calc not in DEPENDENCIES:
        return True
    parent, needed = DEPENDENCIES[calc]
    return row.get(parent) == needed


def build_queue(
    records: list[dict], calcs: list[str], include_superseded: bool = False
) -> dict:
    """Group snapshots by calculation and state, and collect rule violations.

    Parameters
    ----------
    records : list of dict
        Normalised Precalculations rows, as returned by ``load_records``.
    calcs : list of str
        Calculation columns to include.
    include_superseded : bool
        When False (default), pending work on older major versions is set aside
        in a ``superseded`` group instead of the ready / blocked queue: running
        it rarely makes sense once a newer version exists.

    Returns
    -------
    dict
        ``{"queue": {calc: {state: [snapshot, ...]}}, "issues": [...]}``.
    """
    queue = {c: defaultdict(list) for c in calcs}
    issues = []
    for row in sorted(records, key=lambda r: r["snapshot"]):
        snap = row["snapshot"]
        for calc in calcs:
            status = row.get(calc)
            met = dependency_met(row, calc)
            pending = status in ("To do", "Blocked")
            if pending and row["version"] == "Superseded" and not include_superseded:
                queue[calc]["superseded"].append(snap)
                continue
            if status == "To do":
                if met:
                    queue[calc]["ready"].append(snap)
                else:
                    queue[calc]["blocked"].append(snap)
                    parent, needed = DEPENDENCIES[calc]
                    issues.append(
                        {
                            "snapshot": snap,
                            "calculation": calc,
                            "problem": "To do but dependency not met",
                            "detail": f"{parent} is {row.get(parent)!r}, needs {needed!r}",
                            "proposed": "Blocked",
                        }
                    )
            elif status == "Blocked":
                queue[calc]["blocked"].append(snap)
                if met:
                    issues.append(
                        {
                            "snapshot": snap,
                            "calculation": calc,
                            "problem": "Blocked but dependency is met",
                            "detail": "the unblock automation did not fire",
                            "proposed": "To do",
                        }
                    )
            elif status == "Ongoing":
                queue[calc]["ongoing"].append(snap)
            elif status and " + " in status:
                issues.append(
                    {
                        "snapshot": snap,
                        "calculation": calc,
                        "problem": "several statuses in one cell",
                        "detail": status,
                        "proposed": None,
                    }
                )
    return {"queue": {c: dict(v) for c, v in queue.items()}, "issues": issues}


def print_summary(result: dict, show: int) -> None:
    """Print a compact, human-readable queue summary."""
    print(
        f"{'calculation':<28}{'ready':>8}{'blocked':>9}{'ongoing':>9}"
        f"{'old version':>13}"
    )
    for calc, states in result["queue"].items():
        print(
            f"{calc:<28}{len(states.get('ready', [])):>8}"
            f"{len(states.get('blocked', [])):>9}{len(states.get('ongoing', [])):>9}"
            f"{len(states.get('superseded', [])):>13}"
        )
    print(
        "\n'old version' = pending work on a superseded major version, left out "
        "of the queue.\nMark it Not required or Deleted, or pass --include-superseded."
    )
    for calc, states in result["queue"].items():
        for state in ("ongoing", "ready"):
            snaps = states.get(state, [])
            if snaps:
                more = f" (+{len(snaps) - show} more)" if len(snaps) > show else ""
                print(f"\n{calc} - {state}: " + ", ".join(snaps[:show]) + more)
    if result["issues"]:
        print(f"\n{len(result['issues'])} row(s) contradict the dependency rules:")
        for i in result["issues"]:
            fix = f" -> propose {i['proposed']}" if i["proposed"] else ""
            print(
                f"  {i['snapshot']:<16}{i['calculation']:<14}{i['problem']} ({i['detail']}){fix}"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_source_args(ap)
    ap.add_argument(
        "--calc",
        action="append",
        choices=list(CALCULATIONS),
        help="Only these calculations (repeatable). Default: all.",
    )
    ap.add_argument(
        "--include-superseded",
        action="store_true",
        help="Queue pending work on older major versions too",
    )
    ap.add_argument("--show", type=int, default=15, help="Snapshots listed per group")
    ap.add_argument("--json", help="Also write the full result to this path")
    args = ap.parse_args()

    records = load_records(args)
    if not records:
        sys.exit("ERROR: no Precalculations records loaded.")
    result = build_queue(
        records, args.calc or list(CALCULATIONS), args.include_superseded
    )
    result["n_records"] = len(records)
    print(f"{len(records)} snapshots in Precalculations\n")
    print_summary(result, args.show)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"\n[queue] wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
