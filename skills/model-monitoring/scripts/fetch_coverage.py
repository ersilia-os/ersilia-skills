"""Compute isaura precalculation coverage for every model in the Ersilia Model Hub.

The question this answers: for which models do we have the full set of
precalculated predictions, for which are they incomplete, and for which do we
have nothing at all?

Two sources are joined:

  * `isaura stats` — a JSON inventory of what is actually stored in the
    isaura-public bucket (one record per model *version*).
  * `ersilia_search` — the hub's own search engine, which is the authoritative
    list of models that exist and their status.

Coverage is the set difference. Output is a single JSON file consumed by
build_report.py.

Usage:
    python fetch_coverage.py --out coverage.json
    python fetch_coverage.py --out coverage.json --reuse-stats prior_stats.json
"""

import argparse
import glob
import json
import os
import sys
import tempfile
from datetime import datetime, timezone

from _common import (
    FULL_COUNT,
    SEARCH_LIMIT,
    parse_hub_csv,
    resolve_tool,
    run,
)


def collect_isaura_stats(bucket, stats_dir, isaura_env):
    """Run `isaura stats` against the remote bucket and return the parsed JSON.

    `isaura stats` is preferred over `isaura catalog`: catalog renders a Rich
    table with a live spinner, so its stdout is full of ANSI escapes and
    carriage returns that are miserable to parse, while stats writes clean JSON
    and additionally carries each model's hub metadata.
    """
    isaura = resolve_tool("isaura", isaura_env)
    cmd = [isaura, "stats", "-pn", bucket, "-r", "-o", stats_dir]
    print(f"[coverage] running: {' '.join(cmd)}", file=sys.stderr)
    run(cmd, timeout=3600)
    written = sorted(glob.glob(os.path.join(stats_dir, "isaura_stats_*.json")))
    if not written:
        sys.exit(
            f"ERROR: `isaura stats` reported success but wrote no "
            f"isaura_stats_*.json into {stats_dir}"
        )
    return json.load(open(written[-1]))


def collect_hub_models(search_env, status="Ready"):
    """Return the hub inventory as a list of dicts.

    The population defaults to **Ready** models, because those are the ones users
    can actually run: a missing precalculation for a Ready model is a live
    performance gap, whereas an Archived model was never going to be served and
    would only pad the denominator. Pass status="all" to widen it.
    """
    search = resolve_tool("ersilia_search", search_env)
    cmd = [search, "--limit", str(SEARCH_LIMIT), "--csv"]
    if status == "all":
        cmd.insert(1, "--all-statuses")
    else:
        cmd[1:1] = ["--status", status]
    print(f"[coverage] running: {' '.join(cmd)}", file=sys.stderr)
    proc = run(cmd, timeout=600)
    rows = parse_hub_csv(proc.stdout)
    if not rows:
        sys.exit("ERROR: ersilia_search returned no models — is the API reachable?")
    if len(rows) >= SEARCH_LIMIT:
        sys.exit(
            f"ERROR: ersilia_search returned {len(rows)} models, which is at the "
            f"server-side --limit ceiling of {SEARCH_LIMIT}. The result is very "
            f"likely truncated, so coverage numbers would be wrong. The search "
            f"API needs pagination support before this skill can be trusted at "
            f"this hub size."
        )
    return rows


def fold_versions(stats):
    """Collapse isaura's per-version records into one record per model_id.

    A model can be stored several times (eos1lb5/v1 and /v2). For "do we have
    the predictions?" the best version is what matters, so we keep the max
    molecule count and record every version we saw alongside it.
    """
    folded = {}
    for entry in stats.get("models", []):
        mid = entry.get("model_id")
        if not mid:
            continue
        molecules = entry.get("molecules") or 0
        rec = folded.setdefault(
            mid,
            {
                "model_id": mid,
                "best_version": entry.get("model_version"),
                "molecules": molecules,
                "versions": [],
                "total_bytes": 0,
                "n_columns": entry.get("n_columns"),
                "isaura_metadata": entry.get("metadata") or {},
            },
        )
        rec["versions"].append(
            {
                "version": entry.get("model_version"),
                "molecules": molecules,
                "total_gb": entry.get("total_gb"),
                "n_columns": entry.get("n_columns"),
            }
        )
        rec["total_bytes"] += entry.get("total_bytes") or 0
        if molecules > rec["molecules"]:
            rec["molecules"] = molecules
            rec["best_version"] = entry.get("model_version")
            rec["n_columns"] = entry.get("n_columns")
    for rec in folded.values():
        rec["versions"].sort(key=lambda v: str(v["version"]))
        rec["total_gb"] = round(rec["total_bytes"] / 1e9, 4)
    return folded


def classify(hub_rows, folded, full_count):
    """Assign every model to exactly one coverage class.

    complete — every reference molecule has a prediction
    partial  — some predictions stored, but fewer than the full collection
    missing  — the hub knows this model, isaura has nothing for it
    orphan   — isaura holds data for a model outside the population being
               measured. With the default Ready-only population that means an
               Archived or In-maintenance model whose predictions we are still
               paying to store, which is a storage-reclamation question rather
               than a coverage gap — so it is counted separately and never mixed
               into the coverage percentage.
    """
    models = []
    seen_in_hub = set()

    for row in hub_rows:
        mid = row["Identifier"]
        seen_in_hub.add(mid)
        stored = folded.get(mid)
        molecules = stored["molecules"] if stored else 0
        if not stored or molecules == 0:
            coverage = "missing"
        elif molecules >= full_count:
            coverage = "complete"
        else:
            coverage = "partial"
        models.append(
            {
                "model_id": mid,
                "slug": row.get("Slug", ""),
                "title": row.get("Title", ""),
                "status": row.get("Status", ""),
                "task": row.get("Task", ""),
                "subtask": row.get("Subtask", ""),
                "tag": row.get("Tag", ""),
                "biomedical_area": row.get("Biomedical Area", ""),
                "coverage": coverage,
                "molecules": molecules,
                "pct": round(100.0 * molecules / full_count, 2) if full_count else 0.0,
                "missing_molecules": max(full_count - molecules, 0),
                "best_version": stored["best_version"] if stored else None,
                "versions": stored["versions"] if stored else [],
                "total_gb": stored["total_gb"] if stored else 0.0,
                "n_columns": stored["n_columns"] if stored else None,
                "in_hub": True,
            }
        )

    for mid, stored in sorted(folded.items()):
        if mid in seen_in_hub:
            continue
        meta = stored.get("isaura_metadata") or {}
        models.append(
            {
                "model_id": mid,
                "slug": "",
                "title": "",
                "status": meta.get("Status", "unknown"),
                "task": meta.get("Task", ""),
                "subtask": meta.get("Subtask", ""),
                "tag": meta.get("Tag", ""),
                "biomedical_area": meta.get("BiomedicalArea", ""),
                "coverage": "orphan",
                "molecules": stored["molecules"],
                "pct": round(100.0 * stored["molecules"] / full_count, 2)
                if full_count
                else 0.0,
                "missing_molecules": max(full_count - stored["molecules"], 0),
                "best_version": stored["best_version"],
                "versions": stored["versions"],
                "total_gb": stored["total_gb"],
                "n_columns": stored["n_columns"],
                "in_hub": False,
            }
        )

    return models


def summarise(models, full_count, stats):
    """Build the headline numbers, split by coverage class and by status.

    The split by status matters for triage: a missing Archived model is expected
    and needs no action, while a missing Ready model is a real gap a user can
    act on. Reporting one number for both would hide the actionable set.
    """
    by_coverage = {}
    for m in models:
        by_coverage.setdefault(m["coverage"], []).append(m)

    actionable = [
        m for m in models if m["coverage"] in ("missing", "partial") and m["in_hub"]
    ]

    status_matrix = {}
    for m in models:
        status_matrix.setdefault(m["status"] or "unknown", {}).setdefault(
            m["coverage"], 0
        )
        status_matrix[m["status"] or "unknown"][m["coverage"]] += 1

    stored_gb = round(sum(m["total_gb"] for m in models), 2)
    hub_total = sum(1 for m in models if m["in_hub"])
    orphans = by_coverage.get("orphan", [])

    return {
        "full_count": full_count,
        "hub_models": hub_total,
        "orphan_gb": round(sum(m["total_gb"] for m in orphans), 2),
        "isaura_entries": len(stats.get("models", [])),
        "isaura_unique_models": len({m["model_id"] for m in models if m["molecules"] > 0}),
        "counts": {k: len(v) for k, v in sorted(by_coverage.items())},
        "pct_hub_complete": round(
            100.0 * len(by_coverage.get("complete", [])) / hub_total, 1
        )
        if hub_total
        else 0.0,
        "actionable_ready_gaps": len(actionable),
        "stored_gb": stored_gb,
        "status_matrix": status_matrix,
        "multi_version_models": sum(1 for m in models if len(m["versions"]) > 1),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Path for the coverage JSON output")
    ap.add_argument("--bucket", default="isaura-public",
                    help="isaura project bucket (note the hyphen)")
    ap.add_argument("--full-count", type=int, default=FULL_COUNT,
                    help="Molecule count that counts as full coverage")
    ap.add_argument("--isaura-env", default="ersilia",
                    help="conda env holding the isaura CLI")
    ap.add_argument("--search-env", default="ersilia-search",
                    help="conda env holding ersilia_search")
    ap.add_argument("--status", default="Ready",
                    help="Hub population to measure coverage against: a status "
                         "such as Ready (default), or 'all' for every status")
    ap.add_argument("--reuse-stats",
                    help="Path to an existing isaura_stats_*.json, to skip the "
                         "slow remote inventory while iterating")
    ap.add_argument("--stats-dir",
                    help="Directory to write the isaura stats JSON into "
                         "(default: a temporary directory)")
    args = ap.parse_args()

    if args.reuse_stats:
        print(f"[coverage] reusing stats from {args.reuse_stats}", file=sys.stderr)
        stats = json.load(open(args.reuse_stats))
    else:
        stats_dir = args.stats_dir or tempfile.mkdtemp(prefix="isaura_stats_")
        os.makedirs(stats_dir, exist_ok=True)
        stats = collect_isaura_stats(args.bucket, stats_dir, args.isaura_env)

    hub_rows = collect_hub_models(args.search_env, args.status)
    folded = fold_versions(stats)
    models = classify(hub_rows, folded, args.full_count)
    summary = summarise(models, args.full_count, stats)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hub_status": args.status,
        "bucket": args.bucket,
        "isaura_generated_at_utc": stats.get("generated_at_utc"),
        "summary": summary,
        "models": sorted(
            models,
            key=lambda m: (
                {"partial": 0, "missing": 1, "orphan": 2, "complete": 3}[m["coverage"]],
                m["status"] != "Ready",
                m["model_id"],
            ),
        ),
    }

    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    c = summary["counts"]
    print(
        f"[coverage] wrote {args.out}\n"
        f"           hub={summary['hub_models']} "
        f"complete={c.get('complete', 0)} partial={c.get('partial', 0)} "
        f"missing={c.get('missing', 0)} orphan={c.get('orphan', 0)}\n"
        f"           actionable Ready gaps={summary['actionable_ready_gaps']} "
        f"stored={summary['stored_gb']} GB",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
