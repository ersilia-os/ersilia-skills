"""Inventory the Singularity (.sif) images in S3 and join them against the hub.

Answers: for which hub models do we have a built Singularity image, and for which
do we not? A `.sif` is how a model gets run on HPC and on hosts without Docker, so
a Ready model with no image is a real deployment gap rather than a cosmetic one.

The bucket is `models-sif` in the Ersilia AWS account — note the **hyphen**: S3
bucket names cannot contain underscores, so `models_sif` does not exist. Keys are
flat, one per model version: `<model_id>_<version>.sif`, e.g. `eos11sm_v1.sif`.

The hub population is read from the coverage JSON rather than by calling
`ersilia_search` again, so both sections of the report are guaranteed to be
measured against exactly the same set of models. Run fetch_coverage.py first.

Usage:
    python fetch_sif.py --coverage coverage.json --out sif.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

BUCKET = "models-sif"
PROFILE = "ersilia"

# Flat keys, one per model version. Anything else in the bucket is reported
# rather than silently dropped, since an unexpected key usually means a naming
# convention changed and the join is about to under-report.
KEY_RE = re.compile(r"^(eos[0-9a-z]{4})_(v\d+)\.sif$", re.IGNORECASE)

# list-objects-v2 caps a single response at 1000 keys. The AWS CLI paginates for
# us, but we assert rather than trust it: a truncated inventory would silently
# report images as missing.
S3_PAGE_MAX = 1000


def list_bucket(bucket, profile):
    """Return the bucket's objects via the AWS CLI."""
    env = dict(os.environ)
    if profile:
        env["AWS_PROFILE"] = profile
    cmd = ["aws", "s3api", "list-objects-v2", "--bucket", bucket, "--output", "json"]
    print(f"[sif] running: {' '.join(cmd)} (profile={profile})", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
    if proc.returncode != 0:
        err = proc.stderr.strip()
        hint = ""
        if "NoSuchBucket" in err:
            hint = (
                f"\nThe bucket `{bucket}` does not exist. Note S3 forbids underscores "
                f"in bucket names, so it is `models-sif`, not `models_sif`."
            )
        elif "AccessDenied" in err or "ExpiredToken" in err or "credential" in err.lower():
            hint = (
                f"\nCredentials for profile `{profile}` were rejected. Check "
                f"~/.aws/credentials, or pass --profile."
            )
        sys.exit(f"ERROR: listing s3://{bucket} failed:\n{err}{hint}")
    data = json.loads(proc.stdout or "{}")
    objs = data.get("Contents", [])
    if data.get("IsTruncated") and len(objs) >= S3_PAGE_MAX:
        sys.exit(
            f"ERROR: the listing of s3://{bucket} came back truncated at "
            f"{len(objs)} keys. Reporting from a partial listing would mark real "
            f"images as missing, so this stops instead."
        )
    return objs


def fold_images(objs):
    """Collapse the flat key list into one record per model id.

    A model can have several images (`v1` and `v2`); the newest is what would be
    pulled, so that one drives the reported size and date, and every version is
    kept alongside it.
    """
    folded, unexpected = {}, []
    for o in objs:
        key = o.get("Key", "")
        m = KEY_RE.match(key)
        if not m:
            unexpected.append(key)
            continue
        mid, version = m.group(1).lower(), m.group(2).lower()
        rec = folded.setdefault(
            mid, {"model_id": mid, "images": [], "total_bytes": 0}
        )
        rec["images"].append(
            {
                "version": version,
                "key": key,
                "bytes": o.get("Size", 0),
                "gb": round((o.get("Size") or 0) / 1e9, 3),
                "last_modified": (o.get("LastModified") or "")[:19],
            }
        )
        rec["total_bytes"] += o.get("Size") or 0
    for rec in folded.values():
        rec["images"].sort(key=lambda i: i["version"])
        newest = max(rec["images"], key=lambda i: (i["last_modified"], i["version"]))
        rec["latest_version"] = newest["version"]
        rec["latest_gb"] = newest["gb"]
        rec["last_modified"] = newest["last_modified"]
        rec["total_gb"] = round(rec["total_bytes"] / 1e9, 3)
        rec["n_images"] = len(rec["images"])
    return folded, unexpected


def classify(hub_models, folded):
    """Assign every model to exactly one availability class.

    available — an image exists for this hub model
    missing   — the hub lists the model, no image was built
    extra     — an image exists for a model outside the measured population
                (typically Archived): storage we are paying for rather than a gap
    """
    rows, seen = [], set()
    for hm in hub_models:
        mid = hm["model_id"]
        seen.add(mid)
        img = folded.get(mid)
        rows.append(
            {
                "model_id": mid,
                "slug": hm.get("slug", ""),
                "status": hm.get("status", ""),
                "task": hm.get("task", ""),
                "subtask": hm.get("subtask", ""),
                "biomedical_area": hm.get("biomedical_area", ""),
                "sif": "available" if img else "missing",
                "n_images": img["n_images"] if img else 0,
                "latest_version": img["latest_version"] if img else None,
                "versions": [i["version"] for i in img["images"]] if img else [],
                "latest_gb": img["latest_gb"] if img else 0.0,
                "total_gb": img["total_gb"] if img else 0.0,
                "last_modified": img["last_modified"] if img else "",
                "in_hub": True,
            }
        )

    for mid, img in sorted(folded.items()):
        if mid in seen:
            continue
        rows.append(
            {
                "model_id": mid, "slug": "", "status": "not in population",
                "task": "", "subtask": "", "biomedical_area": "",
                "sif": "extra", "n_images": img["n_images"],
                "latest_version": img["latest_version"],
                "versions": [i["version"] for i in img["images"]],
                "latest_gb": img["latest_gb"], "total_gb": img["total_gb"],
                "last_modified": img["last_modified"], "in_hub": False,
            }
        )
    return rows


def summarise(rows, objs, folded, unexpected):
    counts = {}
    for r in rows:
        counts[r["sif"]] = counts.get(r["sif"], 0) + 1
    hub_total = sum(1 for r in rows if r["in_hub"])
    avail = [r for r in rows if r["sif"] == "available"]
    extra = [r for r in rows if r["sif"] == "extra"]
    sizes = sorted(r["latest_gb"] for r in avail if r["latest_gb"])
    biggest = max(avail, key=lambda r: r["latest_gb"], default=None)
    return {
        "hub_models": hub_total,
        "counts": counts,
        "pct_available": round(100.0 * len(avail) / hub_total, 1) if hub_total else 0.0,
        "images_total": len(objs),
        "models_with_images": len(folded),
        "multi_image_models": sum(1 for f in folded.values() if f["n_images"] > 1),
        "total_gb": round(sum(f["total_gb"] for f in folded.values()), 2),
        "extra_gb": round(sum(r["total_gb"] for r in extra), 2),
        "median_gb": sizes[len(sizes) // 2] if sizes else 0.0,
        "largest": {"model_id": biggest["model_id"], "gb": biggest["latest_gb"]}
        if biggest else None,
        "unexpected_keys": unexpected,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Path for the sif JSON output")
    ap.add_argument("--coverage", required=True,
                    help="coverage.json from fetch_coverage.py, used for the hub "
                         "population so both sections measure the same models")
    ap.add_argument("--bucket", default=BUCKET, help="S3 bucket holding the images")
    ap.add_argument("--profile", default=PROFILE, help="AWS profile to use")
    args = ap.parse_args()

    cov = json.load(open(args.coverage))
    hub_models = [m for m in cov.get("models", []) if m.get("in_hub")]
    if not hub_models:
        sys.exit(
            f"ERROR: {args.coverage} contains no in-hub models, so there is "
            f"nothing to join images against. Re-run fetch_coverage.py."
        )

    objs = list_bucket(args.bucket, args.profile)
    folded, unexpected = fold_images(objs)
    rows = classify(hub_models, folded)
    summary = summarise(rows, objs, folded, unexpected)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "bucket": args.bucket,
        "hub_status": cov.get("hub_status", "Ready"),
        "summary": summary,
        "models": sorted(
            rows,
            key=lambda r: (
                {"missing": 0, "extra": 1, "available": 2}[r["sif"]],
                r["model_id"],
            ),
        ),
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    c = summary["counts"]
    print(
        f"[sif] wrote {args.out}\n"
        f"      {summary['images_total']} images for "
        f"{summary['models_with_images']} models, {summary['total_gb']:,.0f} GB\n"
        f"      hub={summary['hub_models']} available={c.get('available', 0)} "
        f"missing={c.get('missing', 0)} extra={c.get('extra', 0)} "
        f"({summary['pct_available']}% covered)"
        + (f"\n      UNEXPECTED KEYS: {unexpected[:5]}" if unexpected else ""),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
