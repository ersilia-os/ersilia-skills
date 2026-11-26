"""Render the weekly Slack nudges from `fetch_nudges.py` output.

One direct message per person. This script only prepares the messages; they are sent by
the person running the skill, through the Slack connector (`slack_send_message`), so they
come from that person. Nothing is prepared for sending without explicit logins:

    python send_nudges.py --input /tmp/nudges.json --plan            # who gets what
    python send_nudges.py --input /tmp/nudges.json --plan --show     # full messages
    python send_nudges.py --input /tmp/nudges.json --render --to GemmaTuron,TiagoJanela \
        --out /tmp/nudges_to_send.json

There is no send-to-all. `--to` must name each person.

The GitHub → Slack map is a JSON file outside the (public) repo, default
`~/.config/ersilia/slack-people.json`:
`{"some-login": {"slack": "U0000000000", "email": "name@ersilia.io"}, ...}`.
Only people whose map email is `@ersilia.io` are rendered; the skill checks the live Slack
profile again before sending. People missing from the map are reported, never skipped
silently.

Exit codes: 0 on success, 1 if a requested person cannot be messaged, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import read_json, warn

DEFAULT_PEOPLE = "~/.config/ersilia/slack-people.json"
# Only people whose Slack account uses an Ersilia email get messages.
ALLOWED_DOMAIN = "@ersilia.io"
CAP = 10

SECTIONS = [
    ("needs_reply", "Issues waiting for your reply"),
    ("stale_assigned", "Assigned to you, no activity for a month or more"),
    ("quiet_own", "Opened by you, no activity for 3+ months: carry on or close"),
    ("housekeeping", "Housekeeping issues assigned to you"),
]


def link(url: str, text: str) -> str:
    """Slack mrkdwn link. `<`, `>` and `&` must be escaped in the text."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<{url}|{text}>"


def plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def capped(lines: list[str], total: int) -> list[str]:
    out = lines[:CAP]
    if total > CAP:
        out.append(f"_…and {total - CAP} more._")
    return out


def issue_line(i: dict) -> str:
    title = (
        i["title"] if len(i["title"]) <= 70 else i["title"][:67].rsplit(" ", 1)[0] + "…"
    )
    where = link(i["url"], f"{i['repo']} #{i['number']}")
    if i["flag"] == "needs_reply":
        who = i["last_by"] or "someone outside the team"
        return f"• {where} {title}. Last reply from {who}, {i['days_quiet']} days ago."
    return f"• {where} {title}. Quiet for {i['days_idle']} days."


def branch_line(b: dict) -> str:
    what = {
        "merged": "PR merged, safe to delete",
        "closed": "PR closed, safe to delete",
        "idle": f"no PR, last commit {b['last_commit']}",
    }[b["reason"]]
    return f"• `{b['repo']}` / {link(b['url'], b['branch'])}: {what}"


def fork_line(f: dict) -> str:
    return (
        f"• {link(f['url'], f['fork'])}: fork of `{f['parent']}`, "
        f"last push {f['pushed_at']}"
    )


def render(bundle: dict) -> str | None:
    """The message for one person, or None if there is nothing to say."""
    parts = ["*GitHub housekeeping: your weekly to-do*"]
    for flag, heading in SECTIONS:
        items = [i for i in bundle["issues"] if i["flag"] == flag]
        if items:
            parts.append(f"\n*{heading}* ({len(items)})")
            parts += capped([issue_line(i) for i in items], len(items))
    branches = bundle["branches"]
    if branches:
        parts.append(
            f"\n*Your branches that look finished or abandoned* ({len(branches)})"
        )
        parts += capped([branch_line(b) for b in branches], len(branches))
    forks = bundle["forks"]
    if forks:
        parts.append(f"\n*Your forks with no push for 6+ months* ({len(forks)})")
        parts += capped([fork_line(f) for f in forks], len(forks))
    if len(parts) == 1:
        return None
    parts.append(
        "\nReply on the issue, delete the branch or fork, or close what is no longer "
        "relevant. Nothing is deleted automatically. Questions: reply here."
    )
    return "\n".join(parts)


def is_ersilia(email: str | None) -> bool:
    return bool(email) and email.strip().lower().endswith(ALLOWED_DOMAIN)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--input", default="/tmp/nudges.json")
    p.add_argument("--people", default=DEFAULT_PEOPLE)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--render", action="store_true")
    p.add_argument("--to", default="", help="comma-separated GitHub logins to message")
    p.add_argument(
        "--show", action="store_true", help="with --plan, print each message"
    )
    p.add_argument("--out", default="/tmp/nudges_to_send.json")
    args = p.parse_args(argv)

    data = read_json(args.input)
    if not data or "people" not in data:
        print(
            f"ERROR: {args.input} is missing or not fetch_nudges.py output",
            file=sys.stderr,
        )
        return 2
    people_path = Path(args.people).expanduser()
    people = read_json(str(people_path)) or {}
    # Older maps were {login: slack_id}; treat a bare ID as having an unknown email.
    people = {k: v if isinstance(v, dict) else {"slack": v} for k, v in people.items()}
    slack_ids = {k: v["slack"] for k, v in people.items() if v.get("slack")}
    if not slack_ids:
        warn(f"no GitHub→Slack map at {people_path}; nobody can be messaged")

    messages = {
        login: render(b)
        for login, b in sorted(data["people"].items())
        if login != "UNOWNED"
    }
    messages = {k: v for k, v in messages.items() if v}

    if args.plan:
        for login, text in messages.items():
            b = data["people"][login]
            entry = people.get(login, {})
            if "slack" not in entry:
                sid = "NO SLACK ID"
            elif "email" in entry and not is_ersilia(entry["email"]):
                sid = f"SKIP (not {ALLOWED_DOMAIN})"
            else:
                sid = entry["slack"]
            counts = " · ".join(
                plural(len(b[k]), one, many)
                for k, one, many in (
                    ("issues", "issue", "issues"),
                    ("branches", "branch", "branches"),
                    ("forks", "fork", "forks"),
                )
            )
            print(f"{login}\t{sid}\t{counts}")
            if args.show:
                print(text, end="\n\n")
        unowned = data["people"].get("UNOWNED", {}).get("issues", [])
        for i in unowned:
            print(f"UNOWNED\t{i['repo']} #{i['number']}\t{i['url']}")
        return 0

    wanted = [x.strip() for x in args.to.split(",") if x.strip()]
    if not wanted:
        print("ERROR: --render needs --to (there is no send-to-all)", file=sys.stderr)
        return 2
    out, failed = [], 0
    for login in wanted:
        entry = people.get(login, {})
        if login not in messages:
            print(f"{login}\tnothing to send")
        elif "slack" not in entry:
            print(f"{login}\tNO SLACK ID in {people_path}")
            failed += 1
        elif not is_ersilia(entry.get("email")):
            print(f"{login}\tskipped: email is not {ALLOWED_DOMAIN}")
        else:
            out.append(
                {"login": login, "slack": entry["slack"], "text": messages[login]}
            )
            print(f"{login}\tready")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"{len(out)} message(s) written to {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
