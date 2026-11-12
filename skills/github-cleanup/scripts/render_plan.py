"""Show the cleanup plan as short review steps, one category at a time.

Steps follow the category order of plan_cleanup.py. A category longer than
``render.max_items_per_step`` (rules.json) is split into parts, so each question to the
user stays small.

Usage:
    python render_plan.py --steps        # numbered steps with counts
    python render_plan.py --step 3       # one step, item by item (notifications: grouped by repo)
    python render_plan.py --step 1 --full  # a notification step, item by item
    [--plan /tmp/github_cleanup/plan.json] [--judgements /tmp/github_cleanup/judgements.json]
"""

from __future__ import annotations

import argparse
import re
import sys

from _common import WORK_DIR, die, load_rules, read_json
from plan_cleanup import CATEGORIES

TITLES = {
    "notif_closed": "Notifications about closed or merged items",
    "notif_noise": "Noise notifications",
    "review_requests": "Reviews waiting on you",
    "stale_prs": "Your stale pull requests",
    "stale_issues": "Your stale issues",
    "branches": "Leftover branches",
    "flags": "For your info (nothing to approve)",
}


GROUPED = {"notif_closed", "notif_noise"}
# Model repos (eos + 4 chars) are many and alike: shown as one bucket.
MODEL_REPO_RE = re.compile(r"^eos[0-9a-z]{4}$", re.IGNORECASE)
MODEL_BUCKET = "model repos (eosXXXX)"


def ranges(nums: list[int]) -> str:
    """[1,2,3,7,9,10] -> "1-3,7,9-10"."""
    out, start, prev = [], None, None
    for n in sorted(nums) + [None]:
        if start is None:
            start = prev = n
        elif n is not None and n == prev + 1:
            prev = n
        else:
            out.append(f"{start}" if start == prev else f"{start}-{prev}")
            start = prev = n
    return ",".join(out)


def describe_grouped(
    items: list[dict], examples: int = 2, min_detail: int = 3
) -> list[str]:
    """One block per (repo, proposed action) with item ranges; small groups rolled up."""
    groups: dict[tuple, list[dict]] = {}
    for i in items:
        repo = MODEL_BUCKET if MODEL_REPO_RE.match(i["repo"] or "") else i["repo"]
        groups.setdefault((repo, i["proposed"]), []).append(i)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    lines, small = [], []
    for (repo, action), group in ordered:
        if len(group) < min_detail:
            small.append(((repo, action), group))
            continue
        lines.append(
            f"[{ranges([i['n'] for i in group])}] {repo}: {len(group)} thread(s) -> {action}"
        )
        reasons: dict[str, int] = {}
        for i in group:
            r = re.sub(r"\d+", "N", i["reason"])
            reasons[r] = reasons.get(r, 0) + 1
        top = sorted(reasons.items(), key=lambda kv: -kv[1])[:3]
        lines.append("      why: " + "; ".join(f"{r} ({c})" for r, c in top))
        for i in group[:examples]:
            lines.append(f"      e.g. {i['label']}")
    by_action: dict[str, list[tuple]] = {}
    for (repo, action), group in small:
        by_action.setdefault(action, []).append((repo, group))
    for action, rows in by_action.items():
        nums = [i["n"] for _, g in rows for i in g]
        repos = ", ".join(f"{r} ({len(g)})" if len(g) > 1 else r for r, g in rows)
        lines.append(
            f"[{ranges(nums)}] {len(rows)} more repo(s), {len(nums)} thread(s) -> {action}: {repos}"
        )
    return lines


def build_steps(items: list[dict], size: int) -> list[dict]:
    """Group plan items into ordered steps of at most ``size`` items."""
    steps = []
    for cat in CATEGORIES:
        group = [i for i in items if i["category"] == cat]
        # Notifications are bulk and low-risk: one step, shown grouped by repo.
        chunk_size = (len(group) or 1) if cat in GROUPED else size
        parts = [group[k : k + chunk_size] for k in range(0, len(group), chunk_size)]
        for p, chunk in enumerate(parts, 1):
            suffix = f" (part {p}/{len(parts)})" if len(parts) > 1 else ""
            steps.append(
                {
                    "category": cat,
                    "title": TITLES[cat] + suffix,
                    "writable": cat != "flags",
                    "items": chunk,
                }
            )
    for k, s in enumerate(steps, 1):
        s["k"] = k
    return steps


def describe(item: dict, judgement: dict | None) -> list[str]:
    """Plain-language lines for one item."""
    lines = [
        f"[{item['n']}] {item['label']}",
        f"      {item['reason']}",
        f"      {item['url']}",
    ]
    action = (judgement or {}).get("action") or item.get("proposed")
    if item["actions"]:
        lines.append(
            f"      proposed: {action or '(Claude to judge)'}   allowed: {', '.join(item['actions'])}"
        )
    if (judgement or {}).get("comment"):
        lines.append(f"      comment: {judgement['comment']}")
    if (judgement or {}).get("why"):
        lines.append(f"      why: {judgement['why']}")
    return lines


def main(argv: list[str] | None = None) -> int:
    """Print the requested view."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--plan", default=f"{WORK_DIR}/plan.json")
    p.add_argument("--judgements", default=f"{WORK_DIR}/judgements.json")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--steps", action="store_true")
    g.add_argument("--step", type=int)
    p.add_argument(
        "--full", action="store_true", help="list grouped notification items one by one"
    )
    args = p.parse_args(argv)

    plan = read_json(args.plan) or die(
        f"missing {args.plan}; run plan_cleanup.py first"
    )
    steps = build_steps(plan["items"], load_rules()["render"]["max_items_per_step"])
    judgements = read_json(args.judgements) or {}

    if args.steps:
        if not steps:
            print("Nothing to clean.")
        for s in steps:
            tag = "" if s["writable"] else "  (report only)"
            print(f"Step {s['k']}. {s['title']}: {len(s['items'])} item(s){tag}")
        print(f"Left alone: {plan['active_notifications']} active notification(s).")
        for line in plan["skipped"]:
            print(f"Not fully checked: {line}")
        return 0

    step = next((s for s in steps if s["k"] == args.step), None)
    if step is None:
        die(f"no step {args.step}; there are {len(steps)}")
    print(f"Step {step['k']}/{len(steps)}. {step['title']}")
    if step["category"] in GROUPED and not args.full:
        print("\n".join(describe_grouped(step["items"])))
        print(
            f"All items: {ranges([i['n'] for i in step['items']])}  (--full lists them one by one)"
        )
        return 0
    for item in step["items"]:
        print("\n".join(describe(item, judgements.get(str(item["n"])))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
