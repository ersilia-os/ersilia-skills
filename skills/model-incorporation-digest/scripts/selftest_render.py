#!/usr/bin/env python3
"""selftest_render.py — check what the digest renders, without network or fixtures on disk.

    python selftest_render.py

Everything a reader sees comes out of `render_report.py`, and its riskiest behaviours are
invisible in a normal run: the public copy silently keeping the defects section, the task
grouping putting a model under the wrong heading, a licence nobody needed appearing on
every row, or an unfinished digest rendering clean because a summary was quietly skipped.

So this drives the renderer over a synthetic month covering the cases that have actually
gone wrong, and asserts on the markdown it produces. Hermetic and deterministic: the
context is built here rather than read from `reports/`, so the test does not break when a
real month is re-rendered.

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


def model(identifier, task, subtask, *, title=None, licence="MIT", summary="A fixture model.",
          authors=None, institutions=None, journal="Journal of Tests", year=2026,
          defects=None, source_code="https://example.invalid/code"):
    return {
        "identifier": identifier,
        "model": {
            "slug": identifier, "title": title or f"{identifier} model", "task": task,
            "subtask": subtask, "license": licence, "source_code": source_code,
            "github": f"https://github.com/ersilia-os/{identifier}",
        },
        "publication": {
            "doi": "10.0000/test", "doi_url": "https://doi.org/10.0000/test",
            "journal": journal, "year": year, "type": "Peer reviewed",
        },
        "credit": {
            "authors": [{"name": n} for n in (authors or ["Ada Lovelace"])],
            "lead_institutions": institutions if institutions is not None else ["Somewhere"],
        },
        "defects": defects or [],
        "summary": summary,
    }


CONTEXT = {
    "month": "2026-08", "month_label": "August 2026", "catalog_size": 999,
    "hub_size_at_month_end": 248, "month_last_day": "2026-08-31",
    "n_models": 5, "by_task": {"Representation": 2, "Annotation": 2, "Sampling": 1},
    "by_status": {"Ready": 5}, "n_with_defects": 1, "n_global_south": 0,
    "models": [
        # deliberately out of order, and Sampling first, to prove the renderer sorts
        model("eosSAMP", "Sampling", "Generation", licence="Apache-2.0"),
        model("eosANN2", "Annotation", "Property calculation or prediction",
              licence="GPL-3.0-or-later", defects=["Interpretation is empty"]),
        model("eosREP1", "Representation", "Featurization",
              authors=["Núria Duran-Frigola", "Second Author"],
              institutions=["Denovo Sciences Inc (Yerevan)"]),
        model("eosANN1", "Annotation", "Activity prediction", authors=["Solo Author"]),
        model("eosREP2", "Representation", "Projection", journal=None, year=2025,
              institutions=[]),
    ],
}

failures: list[str] = []


def check(label, condition, detail=""):
    print(f"  {'ok  ' if condition else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(label)


def render(ctx, out, *, public=False):
    args = [sys.executable, str(HERE / "render_report.py"), str(ctx), "--out", str(out)]
    if public:
        args.append("--public")
    return subprocess.run(args, capture_output=True, text=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ctx = tmp / "context.json"
        ctx.write_text(json.dumps(CONTEXT))
        internal, public = tmp / "internal.md", tmp / "public.md"

        print("renderer self-test (synthetic month, no network)")

        r1 = render(ctx, internal)
        r2 = render(ctx, public, public=True)
        check("internal render exits 0", r1.returncode == 0, r1.stderr.strip())
        check("public render exits 0", r2.returncode == 0, r2.stderr.strip())
        text, pub = internal.read_text(), public.read_text()

        # --- the public/internal split -------------------------------------
        check("internal keeps the defects section", "## Metadata to fix" in text)
        check("public drops the defects section", "## Metadata to fix" not in pub)
        check("public keeps everything else",
              pub.split("## Metadata to fix")[0].strip() == text.split("## Metadata to fix")[0].strip())

        # --- task grouping and order ---------------------------------------
        order = [ln for ln in text.splitlines() if ln.startswith("### ")]
        check("groups are Annotation, Representation, Sampling",
              order == ["### Annotation — 2 models", "### Representation — 2 models",
                        "### Sampling — 1 model"], str(order))
        check("singular for a one-model group", "1 model\n" in text + "\n")
        ann = text.split("### Annotation")[1].split("### Representation")[0]
        check("models sit under their own task", "eosANN1" in ann and "eosANN2" in ann
              and "eosREP1" not in ann)

        # --- the licence rule ----------------------------------------------
        # The digest names no licence at all, restrictive ones included. The row links to
        # the model and its page carries the terms. Asserted rather than assumed because
        # dropping it was a deliberate call with a real cost, and a silent re-introduction
        # would put "MIT" back on every row.
        check("no licence is named, permissive or not",
              not any(t in text for t in ("MIT", "Apache-2.0", "GPL-3.0-or-later")))

        # --- cells -----------------------------------------------------------
        check("et al. when the list continues", "Núria Duran-Frigola et al." in text)
        check("no et al. for a single author", "Solo Author et al." not in text
              and "Solo Author" in text)
        check("diacritics survive", "Núria" in text)
        check("institution is trimmed", "Denovo Sciences<" in text.replace("<br>", "<")
              and "(Yerevan)" not in text)
        check("no journal renders as a preprint", "preprint 2025" in text)
        check("the Hub total is the month's, not the catalogue's",
              "248 models incorporated by 2026-08-31" in text and "999" not in text)
        check("tag column carries the task emoji", "🎯 Activity prediction" in text)

        # --- the guard against an unfinished digest -------------------------
        half = dict(CONTEXT)
        half["models"] = [dict(m) for m in CONTEXT["models"]]
        half["models"][0] = {**half["models"][0], "summary": ""}
        bad = tmp / "bad.json"
        bad.write_text(json.dumps(half))
        r3 = render(bad, tmp / "bad.md")
        check("a missing summary exits non-zero", r3.returncode != 0, f"rc={r3.returncode}")
        check("a missing summary leaves a visible TODO", "TODO" in (tmp / "bad.md").read_text())

        # --- an empty month is a valid digest -------------------------------
        empty = dict(CONTEXT)
        empty["models"], empty["n_models"], empty["by_task"] = [], 0, {}
        none = tmp / "empty.json"
        none.write_text(json.dumps(empty))
        r4 = render(none, tmp / "empty.md")
        check("an empty month renders and exits 0", r4.returncode == 0, r4.stderr.strip())
        check("an empty month says so",
              "No models were incorporated" in (tmp / "empty.md").read_text())

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
