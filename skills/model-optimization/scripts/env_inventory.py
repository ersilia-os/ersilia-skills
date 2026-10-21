"""Inventory of an environment: every installed distribution, its files, size and requirements.

Run it with the Python of the environment to inventory (it uses only the
standard library, Python 3.8+):

    <env>/bin/python env_inventory.py > inventory.json

Output (JSON):

- ``prefix``: sys.prefix of the environment
- ``dists``: {canonical name: {name, version, installer, requires, top_level,
  size_mb, cuda_libs_mb, files}} for every Python distribution (pip and conda-installed);
  ``cuda_libs_mb`` counts CUDA libraries bundled inside a wheel (torch < 2 ships them in torch/lib)
- ``conda``: {name: {version, depends, size_mb, files}} from conda-meta, which also
  covers non-Python files (executables, shared libraries, data) that no
  Python distribution owns

``files`` are absolute real paths. deps.py maps traced files to their
owners with them.
"""

import glob
import json
import os
import re
import sys
try:
    from importlib import metadata
except ImportError:  # Python 3.7: needs the importlib-metadata backport
    import importlib_metadata as metadata


def canon(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def real(path):
    return os.path.realpath(path)


CUDA_LIB = re.compile(r"(cuda|cudnn|cublas|nccl|cufft|cusparse|curand|cusolver|nvrtc|caffe2_.*gpu).*\.so")  # shared libraries only


def file_size(path):
    try:
        return 0 if os.path.islink(path) else os.path.getsize(path)
    except OSError:
        return 0


def python_dists():
    out = {}
    for dist in metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        files = []
        for f in dist.files or []:
            p = real(str(dist.locate_file(f)))
            if os.path.exists(p):
                files.append(p)
        top = dist.read_text("top_level.txt") or ""
        top_level = sorted({t.strip() for t in top.splitlines() if t.strip()})
        if not top_level:
            # no top_level.txt (common for wheels built without setuptools):
            # derive the importable names from the installed files
            names = set()
            for f in dist.files or []:
                parts = f.parts
                if not parts or parts[0].endswith((".dist-info", ".egg-info", ".data")) or parts[0] in ("..", "bin"):
                    continue
                head = parts[0]
                if head.endswith(".py"):
                    head = head[:-3]
                elif "." in head and head.endswith((".so", ".pyd")):
                    head = head.split(".")[0]
                elif len(parts) == 1:
                    continue
                if head.isidentifier():
                    names.add(head)
            top_level = sorted(names)
        installer = (dist.read_text("INSTALLER") or "").strip() or None
        key = canon(name)
        # a name can appear twice (stale dist-info); keep the one with files
        if key in out and len(out[key]["files"]) >= len(files):
            continue
        out[key] = {
            "name": name,
            "version": dist.version,
            "installer": installer,
            "requires": list(dist.requires or []),
            "top_level": top_level,
            "size_mb": round(sum(file_size(p) for p in files) / 1048576, 2),
            "cuda_libs_mb": round(sum(file_size(p) for p in files
                                      if CUDA_LIB.search(os.path.basename(p))) / 1048576, 2),
            "files": files,
        }
    return out


def conda_packages(prefix):
    out = {}
    for meta in glob.glob(os.path.join(prefix, "conda-meta", "*.json")):
        try:
            with open(meta) as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        files = [real(os.path.join(prefix, f)) for f in data.get("files", [])]
        out[data.get("name", os.path.basename(meta))] = {
            "version": data.get("version"),
            "depends": [d.split()[0] for d in data.get("depends", [])],
            "size_mb": round(sum(file_size(p) for p in files) / 1048576, 2),
            "files": files,
        }
    return out


def main():
    prefix = sys.prefix
    print(json.dumps({
        "prefix": prefix,
        "python": "%d.%d" % sys.version_info[:2],
        "dists": python_dists(),
        "conda": conda_packages(prefix),
    }))


if __name__ == "__main__":
    main()
