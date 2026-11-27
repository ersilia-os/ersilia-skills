"""Compare Airtable reference_library_1M_v0 statuses with what isaura stores.

isaura keeps one record per model version (``eos9x3z`` / ``v1``), which maps
one-to-one onto the Airtable Snapshot (``eos9x3z_v1``). For each snapshot this
script compares the Airtable status with the number of molecules stored, and
sorts every disagreement into one of these classes:

* confirmed           - Airtable says Isaura and isaura holds the full library
* isaura_incomplete   - Airtable says Isaura, isaura holds fewer molecules
* isaura_missing      - Airtable says Isaura, isaura holds nothing: the data was
                        there and has been removed, so it proposes Deleted
* untracked_complete  - isaura holds the full library, Airtable does not say Isaura
* partial_in_progress - isaura holds part of the library, Airtable does not say Isaura
* isaura_without_row  - isaura holds a model version that has no Airtable row
* not_in_isaura       - nothing stored yet, Airtable does not say Isaura (only
                        reported with --snapshot, where it answers "is it done?")

Only the reference library is checked here, because it is the only library
whose isaura inventory is in the public bucket today. The script only reads and
proposes; writes to Airtable go through the skill, after the user confirms.

Usage:
    python reconcile_isaura.py --airtable precalc.json --reuse-stats isaura_stats.json
    python reconcile_isaura.py --airtable precalc.json --snapshot eos9x3z_v1
    python reconcile_isaura.py --from-api --json reconcile.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from _precalc import (
    HUMAN_DECISIONS,
    REFERENCE_LIBRARY_SIZE,
    add_source_args,
    load_records,
    split_snapshot,
)

# Reuse the isaura lookup and inventory code from model-monitoring instead of
# duplicating it. Both skills live side by side in ersilia-skills/skills/.
MONITORING_SCRIPTS = (
    Path(__file__).resolve().parents[2] / "model-monitoring" / "scripts"
)
sys.path.insert(0, str(MONITORING_SCRIPTS))

CALC = "reference_library_1M_v0"


def load_isaura_stats(args) -> dict:
    """Return the isaura stats payload, reusing a saved file when given one."""
    if args.reuse_stats:
        return json.loads(Path(args.reuse_stats).read_text())
    try:
        from fetch_coverage import collect_isaura_stats
    except ImportError:
        sys.exit(
            f"ERROR: could not import model-monitoring from {MONITORING_SCRIPTS}.\n"
            "Run `isaura stats -pn isaura-public -r -o <dir>` yourself and pass "
            "the JSON with --reuse-stats."
        )
    stats_dir = args.stats_dir or tempfile.mkdtemp(prefix="isaura_stats_")
    os.makedirs(stats_dir, exist_ok=True)
    return collect_isaura_stats(args.bucket, stats_dir, isaura_bin=args.isaura_bin)


def isaura_counts(stats: dict) -> dict:
    """Map ``eosXXXX_vN`` to the number of molecules isaura stores for it."""
    counts = {}
    for entry in stats.get("models", []):
        mid, ver = entry.get("model_id"), entry.get("model_version")
        if mid and ver:
            key = f"{mid}_{ver}"
            counts[key] = max(counts.get(key, 0), entry.get("molecules") or 0)
    return counts


def reconcile(
    records: list[dict], counts: dict, full: int, only: set | None = None
) -> dict:
    """Classify each snapshot by comparing its Airtable status with isaura.

    Parameters
    ----------
    records : list of dict
        Normalised Precalculations rows.
    counts : dict
        Snapshot -> molecules stored in isaura.
    full : int
        Size of the complete reference library.
    only : set of str, optional
        Restrict the check to these snapshots.

    Returns
    -------
    dict
        Class name -> list of findings, a ``proposals`` list of
        ``{record_id, snapshot, field, from, to}`` changes for the skill to show,
        and ``rows`` with every checked snapshot's version and status.
    """
    classes = {
        k: []
        for k in (
            "confirmed",
            "isaura_incomplete",
            "isaura_missing",
            "untracked_complete",
            "partial_in_progress",
            "isaura_without_row",
            "not_in_isaura",
        )
    }
    proposals = []
    seen = set()
    for row in records:
        snap = row["snapshot"]
        if only and snap not in only:
            continue
        seen.add(snap)
        status = row.get(CALC)
        n = counts.get(snap, 0)
        item = {"snapshot": snap, "airtable": status, "molecules": n}
        if status == "Isaura":
            if n >= full:
                classes["confirmed"].append(item)
            elif n > 0:
                classes["isaura_incomplete"].append(item)
            else:
                classes["isaura_missing"].append(item)
                # Something marked Isaura that is no longer stored was removed
                # on purpose (old versions are pruned), so it becomes Deleted.
                # An empty inventory means the read failed, not that everything
                # was deleted; main() refuses to propose anything in that case.
                proposals.append(
                    {
                        "record_id": row["record_id"],
                        "snapshot": snap,
                        "field": CALC,
                        "from": status,
                        "to": "Deleted",
                        "reason": "marked Isaura, nothing stored in isaura",
                    }
                )
        elif n >= full:
            classes["untracked_complete"].append(item)
            if status in HUMAN_DECISIONS:
                continue
            proposals.append(
                {
                    "record_id": row["record_id"],
                    "snapshot": snap,
                    "field": CALC,
                    "from": status,
                    "to": "Isaura",
                    "reason": f"isaura holds {n:,} molecules (complete)",
                }
            )
        elif n > 0:
            classes["partial_in_progress"].append(item)
        elif only:
            classes["not_in_isaura"].append(item)
    if not only:
        for snap, n in sorted(counts.items()):
            if snap not in seen:
                model_id, version = split_snapshot(snap)
                classes["isaura_without_row"].append(
                    {
                        "snapshot": snap,
                        "model_id": model_id,
                        "version": version,
                        "molecules": n,
                    }
                )
    # Every checked row's status, so model-monitoring can show an Airtable column
    # next to its coverage table, not only the disagreements.
    rows = [
        {"snapshot": r["snapshot"], "version": r["version"], "airtable": r.get(CALC)}
        for r in records
        if not only or r["snapshot"] in only
    ]
    return {
        "full_count": full,
        "classes": classes,
        "proposals": proposals,
        "rows": rows,
    }


def print_summary(result: dict) -> None:
    """Print counts per class and every finding that needs a decision."""
    labels = {
        "confirmed": "Isaura in Airtable, complete in isaura",
        "isaura_incomplete": "Isaura in Airtable, INCOMPLETE in isaura",
        "isaura_missing": "Isaura in Airtable, NOTHING in isaura (-> Deleted)",
        "untracked_complete": "complete in isaura, Airtable not updated",
        "partial_in_progress": "partial in isaura, not marked Isaura",
        "isaura_without_row": "in isaura, no Airtable row",
        "not_in_isaura": "nothing in isaura yet (status unchanged)",
    }
    for key, label in labels.items():
        if key == "not_in_isaura" and not result["classes"][key]:
            continue  # only meaningful when checking single snapshots
        print(f"{len(result['classes'][key]):>5}  {label}")
    for key in (
        "isaura_incomplete",
        "isaura_missing",
        "partial_in_progress",
        "isaura_without_row",
        "not_in_isaura",
    ):
        items = result["classes"][key]
        if items:
            print(f"\n{labels[key]}:")
            for i in items:
                print(
                    f"  {i['snapshot']:<16}{i.get('airtable') or '-':<14}{i['molecules']:>12,}"
                )
    if result["proposals"]:
        print(f"\nProposed Airtable updates ({len(result['proposals'])}):")
        for p in result["proposals"]:
            print(
                f"  {p['snapshot']:<16}{p['field']}: {p['from']} -> {p['to']}  ({p['reason']})"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_source_args(ap)
    ap.add_argument(
        "--snapshot", action="append", help="Only check this snapshot (repeatable)"
    )
    ap.add_argument(
        "--reuse-stats", help="Saved isaura_stats_*.json; skips the remote inventory"
    )
    ap.add_argument(
        "--stats-dir", help="Where a fresh `isaura stats` run writes its JSON"
    )
    ap.add_argument("--bucket", default="isaura-public")
    ap.add_argument("--isaura-bin", default=os.environ.get("ISAURA_BIN"))
    ap.add_argument("--full-count", type=int, default=REFERENCE_LIBRARY_SIZE)
    ap.add_argument("--json", help="Also write the full result to this path")
    args = ap.parse_args()

    records = load_records(args)
    counts = isaura_counts(load_isaura_stats(args))
    if not counts:
        sys.exit(
            "ERROR: the isaura inventory is empty. That means the read failed, not "
            "that every snapshot was deleted. Nothing is proposed."
        )
    only = set(args.snapshot) if args.snapshot else None
    if only:
        unknown = only - {r["snapshot"] for r in records}
        if unknown:
            sys.exit(f"ERROR: not in Precalculations: {', '.join(sorted(unknown))}")
    result = reconcile(records, counts, args.full_count, only)
    print_summary(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"\n[reconcile] wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
