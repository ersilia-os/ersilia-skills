#!/usr/bin/env python3
"""selftest_publish.py — exercise the publish path without network or credentials.

    python selftest_publish.py

`upload_digest.py` and `check_remote_digest.py` talk to GitHub through the `gh` CLI, so
neither can be run for real in a sandbox, and the one mistake they exist to prevent —
publishing the internal render, with its list of unrepaired defects, to a public page — is
exactly the kind that is only noticed after the fact.

So this stands up a fake `gh` backed by a temporary directory, implementing just the two
contents-API calls the scripts make, and drives the whole sequence against it: the
staleness guard, a first upload, the refusal to overwrite, `--force`, the README index and
its ordering, and the public/internal split. Everything here is local and deterministic.

Exits 0 if every check passes, 1 on the first failure, naming it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

FAKE_GH = '''#!/usr/bin/env python3
import base64, hashlib, json, os, sys
from pathlib import Path
ROOT = Path(os.environ["FAKE_REPO_DIR"])
argv = sys.argv[1:]
if not argv or argv[0] != "api":
    sys.stderr.write("fake gh: only 'api' supported\\n"); sys.exit(1)
is_put = "-X" in argv and argv[argv.index("-X") + 1] == "PUT"
endpoint = [a for a in argv[1:] if a.startswith("repos/")][0]
_, owner, repo, _c, *rest = endpoint.split("?", 1)[0].split("/")
target = ROOT / "/".join(rest)
def blob(p):
    data = p.read_bytes()
    return {"type": "file", "name": p.name, "path": str(p.relative_to(ROOT)),
            "sha": hashlib.sha1(data).hexdigest(),
            "content": base64.b64encode(data).decode(),
            "html_url": f"https://github.com/{owner}/{repo}/blob/main/{p.relative_to(ROOT)}",
            "download_url": f"https://raw.githubusercontent.com/{owner}/{repo}/main/{p.relative_to(ROOT)}"}
if is_put:
    payload = json.loads(sys.stdin.read())
    if target.exists():
        if payload.get("sha") != hashlib.sha1(target.read_bytes()).hexdigest():
            sys.stderr.write("gh: Conflict (HTTP 409)\\n"); sys.exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(payload["content"]))
    print(json.dumps({"content": blob(target)})); sys.exit(0)
if target.is_dir():
    print(json.dumps([blob(p) for p in sorted(target.iterdir()) if p.is_file()])); sys.exit(0)
if target.is_file():
    print(json.dumps(blob(target))); sys.exit(0)
sys.stderr.write("gh: Not Found (HTTP 404)\\n"); sys.exit(1)
'''

CONTEXT = {
    "month": "2026-08", "month_label": "August 2026", "catalog_size": 254,
    "n_models": 1, "by_task": {"Annotation": 1}, "by_status": {"Ready": 1},
    "n_with_defects": 1, "n_global_south": 0,
    "models": [{
        "identifier": "eosTEST",
        "model": {"slug": "test-model", "title": "Test Model", "task": "Annotation",
                  "subtask": "Activity prediction", "license": "MIT",
                  "github": "https://github.com/ersilia-os/eosTEST",
                  "source_code": "https://example.invalid/code"},
        "publication": {"doi": "10.0000/test", "doi_url": "https://doi.org/10.0000/test",
                        "journal": "Journal of Tests", "year": 2026},
        "credit": {"authors": [{"name": "Ada Lovelace"}], "lead_institutions": ["Somewhere"]},
        "defects": ["Interpretation is empty"],
        "summary": "A fixture model used only by the publish self-test.",
    }],
}

failures: list[str] = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def run(args, env, stdin=None):
    return subprocess.run([sys.executable, str(HERE / args[0]), *args[1:]],
                          capture_output=True, text=True, env=env, input=stdin)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        binp = tmp / "bin"; binp.mkdir()
        (binp / "gh").write_text(FAKE_GH)
        (binp / "gh").chmod(0o755)
        remote = tmp / "remote"; remote.mkdir()

        env = dict(os.environ)
        env["PATH"] = f"{binp}{os.pathsep}{env['PATH']}"
        env["FAKE_REPO_DIR"] = str(remote)

        ctx = tmp / "context.json"
        ctx.write_text(json.dumps(CONTEXT))

        print("publish self-test (fake gh, no network)")

        # --- the two renders -------------------------------------------------
        internal, public = tmp / "internal.md", tmp / "26-08-31-models-digest.md"
        run(["render_report.py", str(ctx), "--out", str(internal)], env)
        r = run(["render_report.py", str(ctx), "--out", str(public), "--public"], env)
        check("internal render keeps the defects section", "Metadata to fix" in internal.read_text())
        check("public render drops the defects section", "Metadata to fix" not in public.read_text())
        check("public render keeps the credit", "Ada Lovelace" in public.read_text())
        check("--public prints the canonical month-end name",
              "26-08-31-models-digest.md" in r.stderr, r.stderr.strip())

        # --- guard on an empty remote ---------------------------------------
        g = run(["check_remote_digest.py"], env)
        check("guard is silent when nothing is published", g.returncode == 0 and not g.stdout.strip(),
              f"rc={g.returncode} out={g.stdout!r}")

        # --- first upload ----------------------------------------------------
        u = run(["upload_digest.py", "--digest", str(public)], env)
        lines = u.stdout.strip().splitlines()
        check("upload succeeds", u.returncode == 0, u.stderr.strip())
        check("line 1 is the Pages URL",
              bool(lines) and lines[0] == "https://ersilia-os.github.io/digests/models/26-08-31-models-digest.html",
              lines[0] if lines else "<no output>")
        check("published bytes match the public render",
              (remote / "models/26-08-31-models-digest.md").read_bytes() == public.read_bytes())

        # --- refuses to overwrite -------------------------------------------
        u2 = run(["upload_digest.py", "--digest", str(public)], env)
        check("re-upload refused with exit 2", u2.returncode == 2, f"rc={u2.returncode}")

        # --- --force, and the index stays idempotent -------------------------
        u3 = run(["upload_digest.py", "--digest", str(public), "--force"], env)
        readme = (remote / "README.md").read_text()
        check("--force succeeds", u3.returncode == 0, u3.stderr.strip())
        check("README lists the digest exactly once", readme.count("26-08-31-models-digest.md") == 1)
        check("README uses the right heading", "## Model incorporation digests" in readme)

        # --- ordering is date-descending -------------------------------------
        older = tmp / "26-07-31-models-digest.md"
        older.write_text(public.read_text())
        run(["upload_digest.py", "--digest", str(older)], env)
        readme = (remote / "README.md").read_text()
        check("newest digest is listed first",
              readme.index("26-08-31") < readme.index("26-07-31"))

        # --- the guard now blocks --------------------------------------------
        g2 = run(["check_remote_digest.py", "--days", "36500"], env)
        check("guard reports a published digest", "models/26-08-31-models-digest.md" in g2.stdout,
              g2.stdout.strip())

        # --- a non-canonical name never reaches the network ------------------
        bad = tmp / "august.md"; bad.write_text("x")
        b = run(["upload_digest.py", "--digest", str(bad)], env)
        check("non-canonical filename refused", b.returncode == 1 and "non-canonical" in b.stderr)

        # --- a shaped-but-impossible date never reaches the network ----------
        impossible = tmp / "99-99-99-models-digest.md"
        impossible.write_text(public.read_text())
        i = run(["upload_digest.py", "--digest", str(impossible)], env)
        check("impossible date refused", i.returncode == 1 and "not a real date" in i.stderr,
              i.stderr.strip()[:120])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
