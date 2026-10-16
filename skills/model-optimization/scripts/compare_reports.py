"""Compare two `ersilia test` JSON reports (before and after optimization).

Usage
-----
    python compare_reports.py <before-test.json> <after-test.json> \
        [--env-before env-before.json --env-after env-after.json]

The optional env reports are the JSON printed by build_env.py.

Prints a markdown comparison (sizes, Computational Performance 1..5, check
regressions) and exits 1 if any check that passed before fails after.

With --checks-only, prints only the check summary. Use it to gate a
candidate's shallow report against the baseline deep report: checks that only
the deep test runs are absent from the shallow report and don't count as
regressions.
"""

import argparse
import json
import sys

CP_LABELS = {
    "pred_1": "Computational Performance 1 (1 input)",
    "pred_2": "Computational Performance 2 (10 inputs)",
    "pred_3": "Computational Performance 3 (100 inputs)",
    "pred_4": "Computational Performance 4 (1,000 inputs)",
    "pred_5": "Computational Performance 5 (10,000 inputs)",
}


def load(path):
    with open(path) as f:
        return json.load(f)


def flatten_checks(report):
    out = {}
    for section, checks in report.items():
        if isinstance(checks, dict):
            for k, v in checks.items():
                if isinstance(v, bool):
                    out[f"{section}.{k}"] = v
    return out


def delta(before, after, unit):
    if before is None or after is None or before <= 0 or after < 0:
        return f"| {fmt(before, unit)} | {fmt(after, unit)} | n/a |"
    pct = (after - before) / before * 100
    return f"| {fmt(before, unit)} | {fmt(after, unit)} | {pct:+.1f}% |"


def fmt(v, unit):
    if v is None:
        return "n/a"
    if v < 0:
        return "timeout"
    return f"{v:,.1f} {unit}" if unit == "MB" else f"{v:,.2f} {unit}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--env-before")
    ap.add_argument("--env-after")
    ap.add_argument("--checks-only", action="store_true")
    args = ap.parse_args()
    b, a = load(args.before), load(args.after)

    lines = [] if args.checks_only else metric_lines(b, a, args)
    status = check_lines(b, a, lines)
    print("\n".join(lines).strip())
    sys.exit(status)


def metric_lines(b, a, args):
    lines = ["| Metric | Before | After | Change |", "|---|---|---|---|"]
    bs, as_ = b.get("model_size_check", {}), a.get("model_size_check", {})
    for key, label in (
        ("environment_size_mb", "Environment size"),
        ("directory_size_mb", "Model directory size"),
        ("image_size_mb", "Image size"),
    ):
        if key in bs or key in as_:
            lines.append(f"| {label} " + delta(bs.get(key), as_.get(key), "MB"))
    if args.env_before and args.env_after:
        eb, ea = load(args.env_before), load(args.env_after)
        lines.append("| Scratch env size " + delta(eb["env_size_mb"], ea["env_size_mb"], "MB"))
        lines.append("| GPU/CUDA payload " + delta(eb["gpu_payload_mb"], ea["gpu_payload_mb"], "MB"))
    bp = b.get("computational_performance_summary", {}).get(
        "computational_performance_tracking_details", {}) or {}
    ap_ = a.get("computational_performance_summary", {}).get(
        "computational_performance_tracking_details", {}) or {}
    for key, label in CP_LABELS.items():
        lines.append(f"| {label} " + delta(bp.get(key), ap_.get(key), "s"))
    return lines


def check_lines(b, a, lines):
    cb, ca = flatten_checks(b), flatten_checks(a)
    regressions = sorted(k for k, v in cb.items() if v and ca.get(k) is False)
    fixed = sorted(k for k, v in cb.items() if v is False and ca.get(k) is True)
    lines.append("")
    lines.append(f"Checks passing before: {sum(cb.values())}/{len(cb)}; "
                 f"after: {sum(ca.values())}/{len(ca)}")
    if regressions:
        lines.append("")
        lines.append("**Regressions (passed before, fail after):**")
        lines.extend(f"- `{k}`" for k in regressions)
    if fixed:
        lines.append("")
        lines.append("Newly passing: " + ", ".join(f"`{k}`" for k in fixed))
    return 1 if regressions else 0


if __name__ == "__main__":
    main()
