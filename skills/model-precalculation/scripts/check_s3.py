"""Check eosframes and eosquality outputs in S3 against the Airtable statuses.

Both tools write their outputs to the ``eosvc-public`` bucket, computed on the
reference library (``ersilia_reference_library_v0`` = reference_library_1M_v0):

* eosframes: ``eosframes/output/ersilia_reference_library_v0/<snapshot>_transformer.json``
* eosquality: five score files ``eosquality/output/scores_<set>_1000_<snapshot>.csv``
  (sets: drugs, inert, molecules, np_large, synthetic) plus the fitted
  artifacts in ``eosquality/output/artifacts_<model_id>/``. The artifacts folder
  carries no version in its name, so the version is read from
  ``artifacts_<model_id>/shared/metadata.json``.

A snapshot counts as complete only when every expected file exists (and, for
eosquality, the artifacts belong to the same version). Findings per calculation:

* confirmed           - complete in S3, Done in Airtable
* untracked_complete  - complete in S3, Airtable not Done (proposes Done)
* incomplete          - some files missing, or artifacts from another version
* done_but_missing    - Done in Airtable, nothing in S3: the output was there and
                        has been removed, so it proposes Deleted
* s3_without_row      - output for a snapshot with no Airtable row

Uses the AWS CLI (no Python dependencies). Read-only: writes nothing to S3 or
Airtable.

Usage:
    python check_s3.py --airtable precalc.json
    python check_s3.py --airtable precalc.json --snapshot eos3804_v1 --profile default
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

from _precalc import HUMAN_DECISIONS, add_source_args, load_records

BUCKET = "eosvc-public"
LIBRARY_ID = "ersilia_reference_library_v0"
FRAMES_PREFIX = f"eosframes/output/{LIBRARY_ID}/"
QUALITY_PREFIX = "eosquality/output/"
QUALITY_SETS = ("drugs", "inert", "molecules", "np_large", "synthetic")

SNAP = r"(eos[0-9][a-z0-9]{3}_v\d+)"


def aws(args: list[str], profile: str | None) -> str:
    """Run an AWS CLI command and return stdout, stopping with a clear error."""
    cmd = ["aws", *args] + (["--profile", profile] if profile else [])
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        sys.exit(
            f"ERROR: {' '.join(cmd)} failed:\n{proc.stderr.strip()}\n"
            "Check the AWS profile with --profile (see `aws configure list-profiles`)."
        )
    return proc.stdout


def list_frames(bucket: str, profile: str | None) -> set[str]:
    """Return the snapshots that have an eosframes transformer in S3."""
    out = aws(["s3", "ls", f"s3://{bucket}/{FRAMES_PREFIX}"], profile)
    return set(re.findall(SNAP + r"_transformer\.json", out))


def list_quality(bucket: str, profile: str | None) -> dict[str, dict]:
    """Return, per snapshot, which eosquality score sets exist and the artifacts version."""
    out = aws(["s3", "ls", f"s3://{bucket}/{QUALITY_PREFIX}"], profile)
    snaps: dict[str, dict] = {}
    for kind, snap in re.findall(r"scores_(\w+?)_1000_" + SNAP + r"\.csv", out):
        snaps.setdefault(snap, {"sets": set(), "artifacts_version": None})["sets"].add(
            kind
        )
    artifact_models = set(re.findall(r"PRE artifacts_(eos[0-9][a-z0-9]{3})/", out))
    versions = {}
    for model_id in sorted(artifact_models):
        key = f"s3://{bucket}/{QUALITY_PREFIX}artifacts_{model_id}/shared/metadata.json"
        raw = aws(["s3", "cp", key, "-"], profile)
        try:
            versions[model_id] = json.loads(raw).get("version")
        except json.JSONDecodeError:
            versions[model_id] = None
    for snap, info in snaps.items():
        info["artifacts_version"] = versions.get(snap.split("_")[0])
    return snaps


def quality_complete(snap: str, info: dict | None) -> tuple[bool, str]:
    """Decide whether eosquality is complete for ``snap`` and say why not."""
    if not info:
        return False, "no score files"
    missing = sorted(set(QUALITY_SETS) - info["sets"])
    version = snap.split("_")[1]
    if missing:
        return False, f"missing score sets: {', '.join(missing)}"
    if info["artifacts_version"] != version:
        return False, f"artifacts are for {info['artifacts_version'] or 'no version'}"
    return True, "5/5 score sets, artifacts match"


def check(records: list[dict], frames: set, quality: dict, only: set | None) -> dict:
    """Compare S3 contents with Airtable for eosframes and eosquality.

    Parameters
    ----------
    records : list of dict
        Normalised Precalculations rows.
    frames : set of str
        Snapshots with an eosframes transformer in S3.
    quality : dict
        Snapshot -> {"sets", "artifacts_version"} for eosquality.
    only : set of str, optional
        Restrict the check to these snapshots.

    Returns
    -------
    dict
        ``{calc: {class: [finding, ...]}, "proposals": [...]}``.
    """
    classes = (
        "confirmed",
        "untracked_complete",
        "incomplete",
        "done_but_missing",
        "s3_without_row",
    )
    result = {c: {k: [] for k in classes} for c in ("eosframes", "eosquality")}
    proposals = []
    seen = set()
    for row in records:
        snap = row["snapshot"]
        if only and snap not in only:
            continue
        seen.add(snap)
        for calc in ("eosframes", "eosquality"):
            if calc == "eosframes":
                complete = snap in frames
                partial, why = (
                    False,
                    "transformer found" if complete else "no transformer",
                )
            else:
                complete, why = quality_complete(snap, quality.get(snap))
                partial = snap in quality and not complete
            status = row.get(calc)
            item = {"snapshot": snap, "airtable": status, "detail": why}
            if complete and status == "Done":
                result[calc]["confirmed"].append(item)
            elif complete:
                result[calc]["untracked_complete"].append(item)
                if status not in HUMAN_DECISIONS:
                    proposals.append(
                        {
                            "record_id": row["record_id"],
                            "snapshot": snap,
                            "field": calc,
                            "from": status,
                            "to": "Done",
                            "reason": f"S3: {why}",
                        }
                    )
            elif partial:
                result[calc]["incomplete"].append(item)
            elif status == "Done":
                result[calc]["done_but_missing"].append(item)
                # Marked Done but nothing left in S3: removed on purpose.
                proposals.append(
                    {
                        "record_id": row["record_id"],
                        "snapshot": snap,
                        "field": calc,
                        "from": status,
                        "to": "Deleted",
                        "reason": f"marked Done, nothing in S3 ({why})",
                    }
                )
    if not only:
        for snap in sorted(frames - seen):
            result["eosframes"]["s3_without_row"].append({"snapshot": snap})
        for snap in sorted(set(quality) - seen):
            result["eosquality"]["s3_without_row"].append({"snapshot": snap})
    result["proposals"] = proposals
    return result


def print_summary(result: dict) -> None:
    """Print counts per calculation and class, then every finding needing a decision."""
    labels = {
        "confirmed": "complete in S3, Done in Airtable",
        "untracked_complete": "complete in S3, Airtable not updated",
        "incomplete": "INCOMPLETE in S3",
        "done_but_missing": "Done in Airtable, MISSING in S3 (-> Deleted)",
        "s3_without_row": "in S3, no Airtable row",
    }
    for calc in ("eosframes", "eosquality"):
        print(f"{calc}:")
        for key, label in labels.items():
            print(f"  {len(result[calc][key]):>5}  {label}")
        for key in ("incomplete", "done_but_missing", "s3_without_row"):
            for i in result[calc][key]:
                print(
                    f"         {i['snapshot']:<14}{labels[key]}  {i.get('detail', '')}"
                )
    if result["proposals"]:
        print(f"\nProposed Airtable updates ({len(result['proposals'])}):")
        for p in result["proposals"]:
            print(
                f"  {p['snapshot']:<14}{p['field']}: {p['from']} -> {p['to']}  ({p['reason']})"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_source_args(ap)
    ap.add_argument(
        "--snapshot", action="append", help="Only check this snapshot (repeatable)"
    )
    ap.add_argument("--bucket", default=BUCKET)
    ap.add_argument(
        "--profile",
        default=os.environ.get("AWS_PROFILE"),
        help="AWS CLI profile (default: AWS_PROFILE, else the CLI default)",
    )
    ap.add_argument("--json", help="Also write the full result to this path")
    args = ap.parse_args()

    records = load_records(args)
    only = set(args.snapshot) if args.snapshot else None
    if only:
        unknown = only - {r["snapshot"] for r in records}
        if unknown:
            sys.exit(f"ERROR: not in Precalculations: {', '.join(sorted(unknown))}")
    frames = list_frames(args.bucket, args.profile)
    quality = list_quality(args.bucket, args.profile)
    if not frames or not quality:
        sys.exit(
            "ERROR: an S3 listing came back empty. That means the wrong bucket or "
            "profile, not that every output was deleted. Nothing is proposed."
        )
    result = check(records, frames, quality, only)
    print_summary(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2)
        print(f"\n[s3] wrote {args.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
