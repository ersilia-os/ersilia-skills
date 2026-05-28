#!/usr/bin/env python3
"""
Fetch Ersilia model metadata + run_columns from GitHub for one or more eos IDs.

Replaces 2-N WebFetch calls per model with one Bash invocation. Handles the
metadata.json → metadata.yml fallback and the version-pinned URL variant
documented in references/ersilia-metadata-guide.md.

Usage:
    python fetch_model_metadata.py eos4e40 [eos7m30 ...] [--version v1.0.0] [--output <path>]

Output (JSON, written to stdout or --output):
    {
      "<model_id>": {
        "metadata": { ... }            # parsed metadata.json / metadata.yml
        "columns":  [ {"name":..., "type":..., "direction":..., "description":...}, ... ],
        "source":   {"metadata_url": ..., "metadata_format": "json"|"yaml", "columns_url": ...},
        "errors":   [ ... ]            # per-resource error strings; empty when all good
      },
      ...
    }

Errors on a single model do not abort the batch — the per-model "errors" list
captures what failed so Claude can mark that model "metadata unavailable" in
the audit report without crashing the workflow.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.error
import urllib.request
from typing import Any

EOS_PATTERN = re.compile(r"^eos[0-9a-z]{4}$")
BASE = "https://raw.githubusercontent.com/ersilia-os"
TIMEOUT_SEC = 15


def _fetch(url: str) -> tuple[str | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as resp:
            return resp.read().decode("utf-8"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {url}"
    except urllib.error.URLError as e:
        return None, f"URL error {e.reason} {url}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e} ({url})"


def _parse_yaml(text: str) -> tuple[Any | None, str | None]:
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, "PyYAML not installed; cannot parse metadata.yml"
    try:
        return yaml.safe_load(text), None
    except Exception as e:
        return None, f"YAML parse error: {e}"


def _parse_columns(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def fetch_one(model_id: str, version: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "metadata": None,
        "columns": None,
        "source": {"metadata_url": None, "metadata_format": None, "columns_url": None},
        "errors": [],
    }

    ref = version if version else "main"
    json_url = f"{BASE}/{model_id}/{ref}/metadata.json"
    yml_url = f"{BASE}/{model_id}/{ref}/metadata.yml"
    cols_url = f"{BASE}/{model_id}/{ref}/model/framework/columns/run_columns.csv"

    text, err = _fetch(json_url)
    if text is not None:
        try:
            out["metadata"] = json.loads(text)
            out["source"]["metadata_url"] = json_url
            out["source"]["metadata_format"] = "json"
        except json.JSONDecodeError as e:
            out["errors"].append(f"metadata.json invalid JSON: {e}")
    else:
        text, err2 = _fetch(yml_url)
        if text is not None:
            parsed, perr = _parse_yaml(text)
            if parsed is not None:
                out["metadata"] = parsed
                out["source"]["metadata_url"] = yml_url
                out["source"]["metadata_format"] = "yaml"
            else:
                out["errors"].append(f"metadata.yml: {perr}")
        else:
            out["errors"].append(f"metadata fetch failed: {err}; {err2}")

    text, err = _fetch(cols_url)
    if text is not None:
        try:
            out["columns"] = _parse_columns(text)
            out["source"]["columns_url"] = cols_url
        except Exception as e:
            out["errors"].append(f"run_columns.csv parse error: {e}")
    else:
        out["errors"].append(f"run_columns fetch failed: {err}")

    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch Ersilia model metadata from GitHub.")
    p.add_argument("model_ids", nargs="+", help="One or more eos IDs (e.g. eos4e40).")
    p.add_argument("--version", default=None, help="Git ref/tag (default: main). Applied to all model_ids.")
    p.add_argument("--output", default=None, help="Path to write JSON output (default: stdout).")
    args = p.parse_args()

    bad = [m for m in args.model_ids if not EOS_PATTERN.match(m)]
    if bad:
        print(f"Invalid eos IDs: {bad}", file=sys.stderr)
        return 2

    results = {mid: fetch_one(mid, args.version) for mid in args.model_ids}
    payload = json.dumps(results, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(payload)
        n_ok = sum(1 for r in results.values() if r["metadata"] and r["columns"])
        print(f"Wrote {args.output} ({n_ok}/{len(results)} fully fetched)", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
