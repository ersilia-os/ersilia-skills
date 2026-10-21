"""Summarise what a model really used at runtime, and check a candidate's runtime behaviour.

Inputs come from the other scripts:

- an inventory of the environment (env_inventory.py, run with the env's Python)
- one or more trace directories (tracer/sitecustomize.py, written while the
  model ran with OPT_TRACE_DIR set)

summary
-------
    python deps.py summary --repo <model_path> --inventory inv.json \
        --traces <trace_dir> [<trace_dir> ...] [--json summary.json]

Facts only, no proposals: you decide what to change. For every installed
distribution, its size, whether an install line declares it, and its runtime
status:

- ``called``: its code ran after it was imported
- ``imported``: it was imported, but none of its code ran afterwards
  (needs call traces; without them every import counts as ``called``)
- ``files``: none of its modules were imported, but a file of it was opened,
  mapped (a shared library) or executed
- ``metadata``: only its ``*.dist-info`` was read (an entry-point or version
  scan). Not a use: the package can go
- ``unused``: nothing of it was touched

Plus, for every declared pip line, the dependencies only that line installs
(what ``--no-deps`` or removing the line would drop), split into used and
unused with their sizes; the GPU payload, including CUDA libraries bundled
inside the torch wheel; and the imports in code/, with whether each ran and
whether the name it binds is used on any line that ran.

diff
----
    python deps.py diff --base-traces <dir> --cand-traces <dir> \
        --base-inv base.json --cand-inv cand.json [--removed <dist> ...]

Behaviour gate for a candidate that already reproduces the outputs. FAILs if:
a distribution the baseline used is gone (GPU runtime libraries excepted) or
changed version (local tags such as +cpu excepted), or a module the baseline
imported now fails to import (a silent fallback). Distributions passed with
--removed are expected to be gone. Exits 1 on FAIL.
"""

import argparse
import ast
import glob
import json
import os
import re
import shlex
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_env import load_spec  # noqa: E402

GPU_MARKERS = ("nvidia", "cuda", "cudnn", "cublas", "nccl", "triton", "tensorrt", "cupy")
CUDA_LIB = re.compile(r"(cuda|cudnn|cublas|nccl|cufft|cusparse|curand|cusolver|nvrtc|caffe2_.*gpu).*\.so")  # shared libraries only
ALWAYS_KEEP = {"pip", "setuptools", "wheel", "ersilia-pack-utils", "ersilia-pack"}
PIP_VALUE_FLAGS = {"-f", "--find-links", "-i", "--index-url", "--extra-index-url", "-r", "-c",
                   "--requirement", "--constraint", "--trusted-host"}
USED = ("called", "imported", "files")


def canon(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def base_version(v):
    return (v or "").split("+")[0]


def is_gpu(name, version=""):
    n = name.lower()
    return any(m in n for m in GPU_MARKERS) or bool(re.search(r"\+(cu\d+|rocm)", version or ""))


def is_metadata(path):
    return ".dist-info/" in path or ".egg-info/" in path


def load_json(path):
    with open(path) as f:
        return json.load(f)


# ---------------------------------------------------------------- traces


def load_traces(dirs):
    files, modules, missing, execs, covered = set(), set(), set(), set(), {}
    called_files, called_modules, calls = set(), set(), True
    n = 0
    for d in dirs:
        for p in glob.glob(os.path.join(d, "trace-*.json")):
            t = load_json(p)
            n += 1
            files.update(t["files"])
            modules.update(t["modules"])
            missing.update(t["missing_imports"])
            execs.update(t["execs"])
            calls = calls and t.get("calls_traced", False)
            called_files.update(t.get("called_files", []))
            called_modules.update(t.get("called_modules", []))
            for f, lines in t.get("covered", {}).items():
                covered.setdefault(f, set()).update(lines)
    if n == 0:
        sys.exit(f"No trace-*.json files in {dirs}. Was the run made with OPT_TRACE_DIR set?")
    return {"files": files, "modules": modules, "missing": missing, "execs": execs,
            "covered": covered, "n": n, "calls_traced": calls,
            "called_files": called_files, "called_modules": called_modules}


def owners(inv):
    """Map file -> pip dist and file -> conda package, and module name -> dists."""
    by_file, conda_by_file, by_module = {}, {}, {}
    for key, d in inv["dists"].items():
        for f in d["files"]:
            by_file[f] = key
        for m in d["top_level"]:
            by_module.setdefault(m, set()).add(key)
    for name, c in inv.get("conda", {}).items():
        for f in c["files"]:
            conda_by_file[f] = name
    return by_file, conda_by_file, by_module


def resolve_exec(exe, prefix):
    if os.path.isabs(exe):
        return os.path.realpath(exe)
    cand = os.path.join(prefix, "bin", os.path.basename(exe.split()[0]))
    return os.path.realpath(cand) if os.path.exists(cand) else None


def statuses(inv, tr):
    """Runtime status of every pip dist, and the set of conda packages touched."""
    by_file, conda_by_file, by_module = owners(inv)
    imported, touched, meta, used_conda = set(), set(), set(), set()
    for m in tr["modules"]:
        imported.update(by_module.get(m, ()))
    files = set(tr["files"])
    for e in tr["execs"]:
        p = resolve_exec(e, inv["prefix"])
        if p:
            files.add(p)
    for f in files:
        if f in conda_by_file and not is_metadata(f):
            used_conda.add(conda_by_file[f])
        if f in by_file:
            (meta if is_metadata(f) else touched).add(by_file[f])
    called = None
    if tr["calls_traced"]:
        called = {by_file[f] for f in tr["called_files"] if f in by_file}
        for m in tr["called_modules"]:
            called.update(by_module.get(m, ()))
    out = {}
    for k in inv["dists"]:
        if k in imported:
            out[k] = "called" if called is None or k in called else "imported"
        elif k in touched:
            out[k] = "files"
        elif k in meta:
            out[k] = "metadata"
        else:
            out[k] = "unused"
    return out, used_conda


def used_set(inv, tr):
    st, _ = statuses(inv, tr)
    return {k for k, s in st.items() if s in USED}


# ---------------------------------------------------------------- dependency graph


def parse_requirement(req):
    """Return the canonical name of a Requires-Dist entry, or None if it is extra-only."""
    if ";" in req and "extra" in req.split(";", 1)[1]:
        return None
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", req)
    return canon(m.group(1)) if m else None


def graph(inv):
    g = {}
    for key, d in inv["dists"].items():
        g[key] = {n for n in map(parse_requirement, d["requires"])
                  if n and n in inv["dists"] and n != key}
    return g


def closure(g, roots):
    """Dists installed by roots, an iterable of (dist, follow_deps)."""
    roots = [(d, f) for d, f in roots if d in g]
    seen, stack = set(), [d for d, f in roots if f]
    while stack:
        d = stack.pop()
        if d not in seen:
            seen.add(d)
            stack.extend(x for x in g[d] if x not in seen)
    return seen | {d for d, f in roots if not f}


# ---------------------------------------------------------------- install spec


def spec_lines(spec):
    """Each pip/conda install command with the packages it names and whether it uses --no-deps."""
    out = []
    for i, cmd in enumerate(spec.get("commands", [])):
        if isinstance(cmd, list):
            head = str(cmd[0]).lower()
            if head in ("pip", "pip3"):
                pkg = str(cmd[1])
                names = [] if "git+" in pkg or "/" in pkg else [canon(re.split(r"[\[<>=!~]", pkg)[0])]
                out.append({"kind": "pip", "raw": cmd, "names": names, "no_deps": "--no-deps" in map(str, cmd)})
            elif head == "conda":
                names = [str(cmd[1])] if len(cmd) >= 4 and cmd[1] != "install" else conda_tokens(map(str, cmd[2:]))
                out.append({"kind": "conda", "raw": cmd, "names": names, "no_deps": False})
            continue
        toks = shlex.split(cmd)
        if toks and toks[0].startswith("python") and len(toks) > 2 and toks[1] == "-m":
            toks = toks[2:]
        if toks and toks[0] in ("pip", "pip3"):
            names, skip = [], False
            for t in toks[2:]:
                if skip:
                    skip = False
                elif t in PIP_VALUE_FLAGS:
                    skip = True
                elif not (t.startswith("-") or "git+" in t or "/" in t):
                    names.append(canon(re.split(r"[\[<>=!~]", t)[0]))
            out.append({"kind": "pip", "raw": cmd, "names": names, "no_deps": "--no-deps" in toks})
        elif toks and toks[0] == "conda":
            out.append({"kind": "conda", "raw": cmd, "names": conda_tokens(toks[2:]), "no_deps": False})
    return out


def conda_tokens(toks):
    names, skip = [], False
    for t in toks:
        if skip:
            skip = False
        elif t in ("-c", "--channel", "-n", "--name", "-p", "--prefix"):
            skip = True
        elif not t.startswith("-"):
            names.append(re.split(r"[<>=!~ ]", t)[0])
    return names


# ---------------------------------------------------------------- model code


def header_exprs(stmt, lazy_annotations=False):
    """The expressions a statement evaluates on its own line (not its nested body)."""
    if isinstance(stmt, (ast.If, ast.While)):
        return [stmt.test]
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return [stmt.iter, stmt.target]
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return [i.context_expr for i in stmt.items]
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        a = stmt.args
        out = list(stmt.decorator_list) + list(a.defaults) + [d for d in a.kw_defaults if d]
        if not lazy_annotations:  # annotations are evaluated when the def runs
            args = a.args + a.kwonlyargs + getattr(a, "posonlyargs", []) + [x for x in (a.vararg, a.kwarg) if x]
            out += [x.annotation for x in args if x.annotation] + ([stmt.returns] if stmt.returns else [])
        return out
    if isinstance(stmt, ast.ClassDef):
        return list(stmt.decorator_list) + list(stmt.bases) + [k.value for k in stmt.keywords]
    if isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
        return [h.type for h in stmt.handlers if h.type]
    return [stmt]


def names_in(nodes):
    out = set()
    for n in nodes:
        for x in ast.walk(n):
            if isinstance(x, ast.Name):
                out.add(x.id)
            elif isinstance(x, ast.Attribute) and isinstance(x.value, ast.Name):
                out.add(x.value.id)
    return out


def code_imports(code_dir, covered):
    """Static imports in code/: whether each ran, and whether the name it binds is used.

    ``name_used_on_lines_that_ran`` is None without coverage data.
    """
    parsed = []
    for path in sorted(glob.glob(os.path.join(code_dir, "**", "*.py"), recursive=True)):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse(open(path).read(), filename=path)
        except (SyntaxError, UnicodeDecodeError):
            continue
        parsed.append((path, tree, covered.get(os.path.realpath(path))))
    referenced_ran = set()
    for path, tree, ran in parsed:
        if ran:
            lazy = any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                       and any(a.name == "annotations" for a in n.names) for n in tree.body)
            stmts = [n for n in ast.walk(tree) if isinstance(n, ast.stmt)
                     and not isinstance(n, (ast.Import, ast.ImportFrom)) and n.lineno in ran]
            referenced_ran |= names_in(e for st in stmts for e in header_exprs(st, lazy))
    found = []
    for path, tree, ran in parsed:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [(a.name, a.asname or a.name.split(".")[0]) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [(node.module, a.asname or a.name) for a in node.names]
            else:
                continue
            end = getattr(node, "end_lineno", node.lineno)
            for mod, bound in mods:
                executed = None if ran is None else node.lineno in ran
                found.append({
                    "where": f'{os.path.relpath(path, code_dir)}:{node.lineno}'
                             + (f"-{end}" if end != node.lineno else ""),
                    "module": mod.split(".")[0], "name": bound, "ran": executed,
                    "name_used_on_lines_that_ran": None if not covered or bound == "*"
                    else bound in referenced_ran,
                })
    return found


# ---------------------------------------------------------------- summary


def summary(args):
    inv = load_json(args.inventory)
    tr = load_traces(args.traces)
    lines = spec_lines(load_spec(args.repo))
    g = graph(inv)
    st, used_conda = statuses(inv, tr)
    size = {k: d["size_mb"] for k, d in inv["dists"].items()}
    name = lambda k: inv["dists"][k]["name"]  # noqa: E731
    _, _, by_module = owners(inv)

    roots, declared = [], {}
    for ln in lines:
        if ln["kind"] == "pip":
            for n in ln["names"]:
                if n in inv["dists"]:
                    roots.append((n, not ln["no_deps"]))
                    declared[n] = ln
    required_by = {}
    for k, deps in g.items():
        for d in deps:
            required_by.setdefault(d, set()).add(k)

    dists = []
    for k in sorted(inv["dists"], key=lambda k: -size[k]):
        dists.append({
            "name": name(k), "version": inv["dists"][k]["version"], "size_mb": size[k],
            "status": st[k], "declared": k in declared, "gpu": is_gpu(k, inv["dists"][k]["version"]),
            "keep_always": canon(k) in ALWAYS_KEEP,
            "required_by": sorted(name(r) for r in required_by.get(k, ())),
        })

    per_line = []
    for k, ln in declared.items():
        others = closure(g, [(r, f) for r, f in roots if r != k])
        only = closure(g, [(k, True)]) - {k} - others
        used = sorted((x for x in only if st[x] in USED), key=lambda x: -size[x])
        unused = sorted((x for x in only if st[x] not in USED), key=lambda x: -size[x])
        per_line.append({
            "line": ln["raw"], "package": name(k), "status": st[k],
            "deps_only_this_line_installs": {
                "used": [[name(x), inv["dists"][x]["version"], size[x], st[x]] for x in used],
                "unused_mb": round(sum(size[x] for x in unused), 1),
                "unused": [[name(x), size[x], st[x]] for x in unused],
            },
        })

    torch_cuda = 0.0
    if "torch" in inv["dists"]:
        t = inv["dists"]["torch"]
        torch_cuda = t.get("cuda_libs_mb")  # inventories made before this field: measure the files
        if torch_cuda is None:
            torch_cuda = sum(os.path.getsize(f) for f in t["files"]
                             if CUDA_LIB.search(os.path.basename(f)) and os.path.exists(f)) / 1048576
        torch_cuda = round(torch_cuda, 1)
    gpu_dists = [[name(k), size[k]] for k in sorted(inv["dists"], key=lambda k: -size[k])
                 if is_gpu(k, inv["dists"][k]["version"])]

    imports = code_imports(os.path.join(args.repo, "model", "framework", "code"), tr["covered"])
    for rec in imports:
        rec["dists"] = sorted(name(d) for d in by_module.get(rec["module"], ()))

    conda = [{"name": n, "size_mb": inv["conda"][n]["size_mb"], "touched": n in used_conda}
             for ln in lines if ln["kind"] == "conda" for n in ln["names"] if n in inv.get("conda", {})]

    counts = {s: round(sum(size[k] for k in inv["dists"] if st[k] == s), 1)
              for s in ("called", "imported", "files", "metadata", "unused")}
    out = {
        "traces": tr["n"], "call_data": tr["calls_traced"], "coverage_data": bool(tr["covered"]),
        "mb_by_status": counts,
        "gpu_payload": {"gpu_dists_mb": round(sum(s for _, s in gpu_dists), 1),
                        "cuda_libs_inside_torch_mb": torch_cuda, "gpu_dists": gpu_dists},
        "declared_lines": per_line,
        "code_imports": [r for r in imports if r["dists"]],
        "conda_lines": conda,
        "missing_imports": sorted(tr["missing"]),
        "dists": dists,
    }
    text = json.dumps(out, indent=2)
    if args.json:
        with open(args.json, "w") as f:
            f.write(text)
    print(f"{tr['n']} traces; MB by status: {counts}")
    print(f"GPU payload: {out['gpu_payload']['gpu_dists_mb']} MB in GPU dists, "
          f"{torch_cuda} MB of CUDA libs inside torch")
    for p in per_line:
        d = p["deps_only_this_line_installs"]
        print(f"- {p['package']} [{p['status']}]: only it installs {len(d['used'])} used deps, "
              f"{len(d['unused'])} unused ({d['unused_mb']} MB)")
    for r in out["code_imports"]:
        if r["ran"] is False or r["name_used_on_lines_that_ran"] is False:
            print(f"- code/{r['where']} import {r['module']}: ran={r['ran']}, "
                  f"name used={r['name_used_on_lines_that_ran']} -> {r['dists']}")
    if args.json:
        print(f"full summary in {args.json}")


# ---------------------------------------------------------------- diff


def diff(args):
    bi, ci = load_json(args.base_inv), load_json(args.cand_inv)
    bt, ct = load_traces(args.base_traces), load_traces(args.cand_traces)
    bused, cused = used_set(bi, bt), used_set(ci, ct)
    removed = {canon(r) for r in args.removed}
    fails, warns = [], []
    for k in sorted(bused):
        name, bv = bi["dists"][k]["name"], bi["dists"][k]["version"]
        if k not in ci["dists"]:
            if k in removed:
                warns.append(f"{name} {bv} was loaded at baseline and was removed on purpose")
            elif is_gpu(k, bv):
                warns.append(f"GPU dist {name} {bv} was loaded at baseline and is gone (expected for a CPU build)")
            else:
                fails.append(f"{name} {bv} was used at baseline and is not installed in the candidate")
            continue
        cv = ci["dists"][k]["version"]
        if base_version(bv) != base_version(cv):
            fails.append(f"{name} changed version: {bv} -> {cv} (used at runtime)")
        elif bv != cv:
            warns.append(f"{name} local build changed: {bv} -> {cv}")
    for k in sorted(set(bi["dists"]) & set(ci["dists"]) - bused):
        bv, cv = bi["dists"][k]["version"], ci["dists"][k]["version"]
        if base_version(bv) != base_version(cv):
            warns.append(f'{bi["dists"][k]["name"]} changed version {bv} -> {cv} (not used at runtime)')
    _, _, base_by_module = owners(bi)
    for m in sorted(ct["missing"] - bt["missing"]):
        if base_by_module.get(m.split(".")[0], set()) & removed:
            warns.append(f"optional import of {m} (removed on purpose) now fails: "
                         "check in the logs that the fallback is cosmetic (progress bar, logging)")
        elif m.split(".")[0] in bt["modules"]:
            fails.append(f"import of {m} now fails but its package was loaded at baseline: silent fallback")
        else:
            warns.append(f"new failed import probe: {m}")
    for k in sorted(cused - bused):
        if k in ci["dists"] and not is_gpu(k, ci["dists"][k]["version"]):
            warns.append(f'{ci["dists"][k]["name"]} is loaded now but was not at baseline: different code path?')
    out = {"verdict": "FAIL" if fails else "PASS", "fail": fails, "warn": warns,
           "modules_no_longer_loaded": sorted(bt["modules"] - ct["modules"])[:50]}
    print(json.dumps(out, indent=2))
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("summary")
    s.add_argument("--repo", required=True)
    s.add_argument("--inventory", required=True)
    s.add_argument("--traces", nargs="+", required=True)
    s.add_argument("--json")
    d = sub.add_parser("diff")
    d.add_argument("--base-traces", nargs="+", required=True)
    d.add_argument("--cand-traces", nargs="+", required=True)
    d.add_argument("--base-inv", required=True)
    d.add_argument("--cand-inv", required=True)
    d.add_argument("--removed", nargs="*", default=[], help="dists the candidate removes on purpose")
    a = ap.parse_args()
    summary(a) if a.cmd == "summary" else diff(a)


if __name__ == "__main__":
    main()
