"""Check what the org file says about Google Drive and Airtable against what exists.

These resources sit behind connectors that scripts cannot call, so the check has three
steps:

1. ``extract`` parses the org file for the shared drives and Airtable bases it names
   (bold list items under the sections set in ``rules.json`` ``connectors``) and writes
   ``claims.json``. If Google Drive for desktop is synced on this machine, it also lists
   the real shared-drive names into ``drive-local.json``.
2. Claude verifies each claim with the read-only Drive and Airtable connectors (SKILL.md,
   Step 3) and writes ``observed.json``:

       {"drive": {"method": "connector" | "local",
                  "drives": {"Grants": {"status": "found" | "missing" | "unverified",
                                        "root_id": "0A...", "evidence": "...",
                                        "matches_description": true,
                                        "shared_publicly": false}},
                  "unlisted": ["Docs"]},
        "airtable": {"bases": ["Ersilia Content", "Ersilia Model Hub", "..."]}}

3. ``compare`` turns claims plus observations into findings, ``connectors.json``.

``~/.claude/org-context/drive-map.json`` caches the root folder ID of each shared drive
once the user confirms it, so later runs check a known root instead of searching again.
It lives outside the repository on purpose: ersilia-skills is public, and Drive IDs and
folder names are internal.

Usage:
    python connector_claims.py extract [--work /tmp/org_context]
    python connector_claims.py compare [--work /tmp/org_context]
    python connector_claims.py map --drive Grants --root 0A... --signature "year folders"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from _common import (
    REFS,
    WORK_DIR,
    die,
    load_work,
    read_json,
    sections,
    units,
    write_json,
)
from check_claude_md import Findings

LOCAL_DRIVE_GLOB = "Library/CloudStorage/GoogleDrive-*/Shared drives"
DRIVE_LINK_RE = re.compile(
    r"drive\.google\.com/drive/(?:u/\d+/)?folders/([A-Za-z0-9_-]+)"
)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
DRIVE_MAP = Path.home() / ".claude" / "org-context" / "drive-map.json"


def claims_in(text: str, title: str) -> list[dict]:
    """Bold-led list items inside every section whose heading contains ``title``."""
    out = []
    for s in sections(text):
        if title.lower() not in s["title"].lower():
            continue
        for u in units(text):
            if s["start"] < u["line"] <= s["end"] and u["lead"]:
                name = MD_LINK_RE.sub(r"\1", u["lead"]).rstrip(":").strip()
                desc = re.sub(r"^\*\*.+?\*\*:?\s*", "", u["text"]).strip()
                link = DRIVE_LINK_RE.search(u["text"])
                out.append(
                    {
                        "name": name,
                        "description": desc,
                        "line": u["line"],
                        "link_id": link.group(1) if link else None,
                    }
                )
    return out


def local_drives() -> list[str] | None:
    """Shared-drive names from a local Google Drive for desktop sync, or None."""
    roots = sorted(Path.home().glob(LOCAL_DRIVE_GLOB))
    if not roots:
        return None
    return sorted({p.name for root in roots for p in root.iterdir() if p.is_dir()})


def extract(work: Path, rules: dict) -> int:
    """Write claims.json (and drive-local.json when Drive is synced)."""
    targets, texts = load_work(work)
    org = next((t for t in targets if t["role"] == "org"), None)
    if not org:
        die("the org file is not in this review; nothing to extract")
    text = texts[org["id"]]
    claims = {
        "target": org["id"],
        "drive": claims_in(text, rules["drive_section"]),
        "airtable": claims_in(text, rules["airtable_section"]),
    }
    write_json(work / "claims.json", claims)
    names = local_drives()
    if names is not None:
        write_json(work / "drive-local.json", names)
    roots = known_roots(claims["drive"], DRIVE_MAP)
    print(
        f"{len(claims['drive'])} shared drives and {len(claims['airtable'])} Airtable "
        f"bases named in the org file"
    )
    for c in claims["drive"]:
        known = roots.get(c["name"])
        print(
            f"  drive  {c['name']}: "
            + (
                f"root {known['root_id']} ({known['from']})"
                if known
                else "no known root"
            )
        )
    for c in claims["airtable"]:
        print(f"  base   {c['name']}")
    print(
        "local Drive sync: "
        + (
            f"{len(names)} shared drives listed"
            if names is not None
            else "not found; use the connector"
        )
    )
    return 0


def known_roots(claims: list[dict], drive_map: Path) -> dict[str, dict]:
    """Drive roots by name: links in the org file first, then the personal cache.

    A root link in the org file was confirmed when that file was merged, so it is the
    shared source of truth; the cache only covers drives the file does not link.
    """
    roots = {
        name: {**v, "from": "cache"}
        for name, v in (read_json(drive_map) or {"drives": {}})["drives"].items()
    }
    for c in claims:
        if (c.get("link_id") or "").startswith("0A") and c["name"] not in roots:
            roots[c["name"]] = {"root_id": c["link_id"], "from": "org file"}
    return roots


def check_drive_link(f, tid: str, c: dict, obs: dict, cache: dict) -> None:
    """A published drive link must be the confirmed root of a drive nobody outside can open."""
    link, root = c.get("link_id"), cache.get(c["name"], {}).get("root_id")
    if not link:
        return
    if not link.startswith("0A"):
        f.add(
            tid,
            "FACT-DRIVE-LINK",
            "fix",
            c["line"],
            f"Link for '{c['name']}' points below the drive root",
            "Publish root links only; a deeper folder can carry its own public sharing.",
        )
    elif root and link != root:
        f.add(
            tid,
            "FACT-DRIVE-LINK",
            "fix",
            c["line"],
            f"Link for '{c['name']}' is not its confirmed root",
        )
    elif not root:
        f.add(
            tid,
            "FACT-DRIVE-LINK",
            "consider",
            c["line"],
            f"Link for '{c['name']}' points at a root not confirmed by the user",
        )
    if obs.get("shared_publicly"):
        f.add(
            tid,
            "FACT-DRIVE-PUBLIC",
            "fix",
            c["line"],
            f"Shared drive '{c['name']}' is open beyond named people",
            "Its root allows 'anyone' or whole-domain access; fix the sharing or drop the link.",
        )


def compare(work: Path, rules: dict, drive_map: Path = DRIVE_MAP) -> int:
    """Write connectors.json from claims.json and observed.json."""
    claims = read_json(work / "claims.json")
    observed = read_json(work / "observed.json")
    if claims is None:
        die("claims.json is missing: run 'connector_claims.py extract' first")
    if observed is None:
        die("observed.json is missing: verify the claims with the connectors (Step 3)")
    tid, f = claims["target"], Findings()

    drive = observed.get("drive", {})
    local = read_json(work / "drive-local.json")
    seen = drive.get("drives", {})
    cache = known_roots(claims["drive"], drive_map)
    unverified = []
    for c in claims["drive"]:
        check_drive_link(f, tid, c, seen.get(c["name"], {}), cache)
        if local is not None:
            status = "found" if c["name"] in local else "missing"
            obs = {"status": status, "evidence": "local Drive sync"}
        else:
            obs = seen.get(
                c["name"], {"status": "unverified", "evidence": "not checked"}
            )
        if obs["status"] == "missing":
            f.add(
                tid,
                "FACT-DRIVE",
                "fix",
                c["line"],
                f"Shared drive '{c['name']}' not found",
                obs.get("evidence", ""),
            )
        elif obs["status"] == "unverified":
            unverified.append(c)
        elif obs.get("matches_description") is False:
            f.add(
                tid,
                "FACT-DRIVE-DESC",
                "consider",
                c["line"],
                f"Shared drive '{c['name']}' holds something other than described",
                obs.get("evidence", ""),
            )
    if unverified:
        f.add(
            tid,
            "FACT-DRIVE-UNVERIFIED",
            "consider",
            unverified[0]["line"],
            f"{len(unverified)} shared drive(s) not verified: "
            + ", ".join(c["name"] for c in unverified),
            "Map each to its root once (Step 3); later runs check it in one call.",
        )
    unlisted = (
        sorted(set(local or []) - {c["name"] for c in claims["drive"]})
        if local
        else drive.get("unlisted", [])
    )
    unlisted = [n for n in unlisted if n not in rules["drive_ignore"]]
    if unlisted:
        f.add(
            tid,
            "FACT-DRIVE-UNLISTED",
            "consider",
            None,
            f"Shared drives not mentioned: {', '.join(unlisted)}",
            "Add the ones agents need; add the rest to rules.json connectors.drive_ignore.",
        )

    bases = observed.get("airtable", {}).get("bases")
    if bases is None:
        for c in claims["airtable"]:
            f.add(
                tid,
                "FACT-AIRTABLE",
                "consider",
                c["line"],
                f"Airtable base '{c['name']}' could not be verified",
            )
    else:
        for c in claims["airtable"]:
            if c["name"] not in bases:
                f.add(
                    tid,
                    "FACT-AIRTABLE",
                    "fix",
                    c["line"],
                    f"Airtable base '{c['name']}' not found",
                )
        extra = [
            b
            for b in bases
            if b not in {c["name"] for c in claims["airtable"]}
            and b not in rules["airtable_ignore"]
        ]
        if extra:
            f.add(
                tid,
                "FACT-AIRTABLE-UNLISTED",
                "consider",
                None,
                f"Airtable bases not mentioned: {', '.join(extra)}",
                "Add the ones agents need; add the rest to rules.json connectors.airtable_ignore.",
            )

    write_json(work / "connectors.json", f.items)
    print(f"{len(f.items)} connector finding(s)")
    for i in f.items:
        print(f"  {i['key']}: {i['title']}")
    return 0


def map_drive(name: str, root: str, signature: str) -> int:
    """Cache a user-confirmed shared-drive root in DRIVE_MAP."""
    if not root.startswith("0A"):
        die(f"{root} is not a shared-drive root ID (they start with '0A')")
    cache = read_json(DRIVE_MAP) or {"drives": {}}
    cache["drives"][name] = {"root_id": root, "signature": signature}
    write_json(DRIVE_MAP, cache)
    print(f"mapped shared drive '{name}' to {root} in {DRIVE_MAP}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run ``extract``, ``compare`` or ``map``."""
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("cmd", choices=("extract", "compare", "map"))
    p.add_argument("--drive")
    p.add_argument("--root")
    p.add_argument("--signature", default="")
    p.add_argument("--drive-map", default=str(DRIVE_MAP))
    p.add_argument("--work", default=WORK_DIR)
    p.add_argument("--rules", default=str(REFS / "rules.json"))
    args = p.parse_args(argv)
    rules = read_json(args.rules)["connectors"]
    work = Path(args.work)
    if args.cmd == "map":
        if not (args.drive and args.root):
            die("map needs --drive and --root")
        return map_drive(args.drive, args.root, args.signature)
    if args.cmd == "extract":
        return extract(work, rules)
    return compare(work, rules, Path(args.drive_map))


if __name__ == "__main__":
    sys.exit(main())
