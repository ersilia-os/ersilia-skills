"""Build a scratch conda environment from a model's install.yml and report its size.

The install.yml commands are translated to shell commands the same way
ersilia-pack does it (see ersilia_pack/parsers/install_parser.py), so the
scratch environment matches what `ersilia fetch` would build, minus the
serving layer.

Legacy models with a Dockerfile and no install.yml are handled the way
`ersilia test` does it (DockerfileInstallParser in
ersilia/publish/test/services/parser.py): the Python version comes from the
`pyXY` tag on the FROM line and every `RUN` line is an install command. The
BentoML base image itself is not reproduced.

Usage
-----
    python build_env.py --repo <model_path> --name <env_name> [--recreate]
    python build_env.py --name <env_name> --report-only

Prints a JSON summary: env prefix, total size in MB, the 25 largest entries
in site-packages and any GPU/CUDA payload found.
"""

import argparse
import glob
import json
import os
import re
import shlex
import subprocess
import sys

import yaml

GPU_MARKERS = ("nvidia", "cuda", "cudnn", "cublas", "nccl", "triton", "tensorrt")


def run(cmd):
    print(f"$ {cmd}", file=sys.stderr, flush=True)
    # stdout goes to stderr too, so only the JSON report ends up on stdout
    subprocess.run(cmd, shell=True, check=True, stdout=sys.stderr)


def env_prefix(name):
    out = subprocess.run(
        ["conda", "env", "list", "--json"], capture_output=True, text=True, check=True
    )
    for prefix in json.loads(out.stdout)["envs"]:
        if os.path.basename(prefix) == name:
            return prefix
    return None


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp):
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    pass
    return total


def pip_line(python_exe, command):
    if isinstance(command, str):
        parts = shlex.split(command)
        return f"{python_exe} -m pip " + " ".join(parts[1:])
    if len(command) == 2:
        return f"{python_exe} -m pip install {command[1]}"
    pkg, ver = command[1], command[2]
    spec = pkg if (ver == "" or "git+" in pkg) else f"{pkg}=={ver}"
    flags = command[2:] if "git+" in pkg else command[3:]
    return f"{python_exe} -m pip install {spec}" + (" " + " ".join(flags) if flags else "")


def conda_line(name, command):
    if isinstance(command, str):
        parts = shlex.split(command)
        return "conda install -n " + name + " " + " ".join(parts[2:])
    if len(command) >= 4 and command[1] != "install":
        _, pkg, ver, *rest = command
        channels = [x for x in rest if x != "-y"] or ["default"]
        chans = " ".join(f"-c {c}" for c in channels)
        return f"conda install -n {name} -y {chans} {pkg}={ver}"
    parts = [p for p in command[2:] if p != "-y"]
    return f"conda install -n {name} -y " + " ".join(parts)


def load_dockerfile(path):
    python, commands = None, []
    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("FROM") and python is None:
                m = re.search(r"py(\d+\.\d+|\d{2,3})", s)
                if m:
                    v = m.group(1)
                    python = v if "." in v else f"{v[0]}.{v[1:]}"
            elif s.startswith("RUN "):
                commands.append(s[4:].strip())
    if python is None:
        sys.exit(f"No pyXY tag on the FROM line of {path}")
    return {"python": python, "commands": commands}


def load_spec(repo):
    yml = os.path.join(repo, "install.yml")
    if os.path.exists(yml):
        with open(yml) as f:
            return yaml.safe_load(f)
    dockerfile = os.path.join(repo, "Dockerfile")
    if os.path.exists(dockerfile):
        return load_dockerfile(dockerfile)
    sys.exit(f"Neither install.yml nor Dockerfile found in {repo}")


def build(repo, name, recreate):
    data = load_spec(repo)
    if env_prefix(name) and recreate:
        run(f"conda env remove -n {name} -y")
    if not env_prefix(name):
        run(f"conda create -n {name} -y python={data['python']}")
    prefix = env_prefix(name)
    python_exe = os.path.join(prefix, "bin", "python")
    for cmd in data.get("commands", []):
        head = (cmd[0] if isinstance(cmd, list) else shlex.split(cmd)[0]).lower()
        if head in ("pip", "pip3"):
            run(pip_line(python_exe, cmd))
        elif head == "conda":
            run(conda_line(name, cmd))
        else:
            # other commands (e.g. "lazyqsar setup ...") run inside the env, as ersilia-pack does
            line = " ".join(map(str, cmd)) if isinstance(cmd, list) else cmd
            run(f'PATH="{os.path.join(prefix, "bin")}:$PATH" CONDA_PREFIX="{prefix}" {line}')
    return prefix


def report(name):
    prefix = env_prefix(name)
    if prefix is None:
        sys.exit(f"Environment {name} not found")
    sites = glob.glob(os.path.join(prefix, "lib", "python*", "site-packages"))
    site = sites[0] if sites else None
    entries = []
    if site:
        for entry in os.listdir(site):
            p = os.path.join(site, entry)
            size = dir_size(p) if os.path.isdir(p) else os.path.getsize(p)
            entries.append((entry, size))
    entries.sort(key=lambda x: -x[1])
    mb = lambda b: round(b / 1024 / 1024, 1)  # noqa: E731
    gpu = [(e, mb(s)) for e, s in entries if any(m in e.lower() for m in GPU_MARKERS)]
    return {
        "env": name,
        "prefix": prefix,
        "env_size_mb": mb(dir_size(prefix)),
        "site_packages_mb": mb(sum(s for _, s in entries)),
        "largest_site_packages": [(e, mb(s)) for e, s in entries[:25]],
        "gpu_payload": gpu,
        "gpu_payload_mb": round(sum(s for _, s in gpu), 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="Path to the model repository")
    ap.add_argument("--name", required=True, help="Scratch conda env name")
    ap.add_argument("--recreate", action="store_true", help="Remove the env first")
    ap.add_argument("--report-only", action="store_true", help="Skip the build")
    args = ap.parse_args()
    if not args.report_only:
        if not args.repo:
            sys.exit("--repo is required unless --report-only")
        build(args.repo, args.name, args.recreate)
    print(json.dumps(report(args.name), indent=2))


if __name__ == "__main__":
    main()
