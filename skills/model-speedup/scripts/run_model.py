"""Run a model's main.py on one input file, time it, and optionally compare the output.

The model is run the way run.sh runs it (`python code/main.py <input> <output>`),
with the model environment's bin/ first on PATH, so code that calls a bare
`python` or `xtb` in a subprocess finds the right one.

With --cpus N the model (and every process it starts) may only use the first N
CPUs, to time it on a container-sized CPU budget. As with `docker run --cpus`,
`os.cpu_count()` inside the model still reports every core of the machine, so
code that sizes its pools from it oversubscribes the same way it does in production.
Libraries that read the CPU affinity (OpenMP, MKL, OpenBLAS, joblib) start N threads.

Peak memory is the largest total RSS of the model's whole process tree, sampled
every 0.1 s (an upper bound when processes share memory), or the peak of its
largest single process if that is higher (it catches spikes between samples).
peak_pss_mb is the same total in PSS, which splits pages shared between processes
(e.g. model weights inherited by forked workers) among them; it is close to what a
container's memory limit counts, so use it when the model runs worker processes.

Usage
-----
    python run_model.py --python <env>/bin/python --repo <model_path> \
        --input in.csv --output out.csv [--reference ref.csv] [--cpus 2] [--log run.log]

Prints one JSON line: seconds, peak_rss_mb, peak_pss_mb, cpus, return code, output rows and,
with --reference, whether the output is identical (see compare.py). Exit code: 0
if the run succeeded (and matched the reference, when given), 1 otherwise.
"""

import argparse
import json
import os
import resource
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare import compare_files  # noqa: E402

PAGE_KB = os.sysconf("SC_PAGE_SIZE") // 1024


def _tree_mem_kb(root):
    """Total RSS and PSS (kB) of `root` and all its descendants, from /proc."""
    children = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, IndexError, ValueError):
            continue  # the process ended while we looked
        children.setdefault(ppid, []).append(int(name))
    rss, pss, todo = 0, 0, [root]
    while todo:
        pid = todo.pop()
        try:
            with open(f"/proc/{pid}/statm") as f:
                rss_pid = int(f.read().split()[1]) * PAGE_KB
            rss += rss_pid
        except (OSError, IndexError, ValueError):
            rss_pid = 0
        pss += _pss_kb(pid, rss_pid)
        todo.extend(children.get(pid, []))
    return rss, pss


def _pss_kb(pid, fallback):
    """PSS (kB) of one process from smaps_rollup; its RSS if that is not readable."""
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                if line.startswith("Pss:"):
                    return int(line.split()[1])
    except (OSError, IndexError, ValueError):
        pass
    return fallback


def _sample_peak(proc, peak):
    while proc.poll() is None:
        rss, pss = _tree_mem_kb(proc.pid)
        peak[0], peak[1] = max(peak[0], rss), max(peak[1], pss)
        time.sleep(0.1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--python", required=True, help="Python of the model environment")
    parser.add_argument("--repo", required=True, help="Model repository (contains model/framework)")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--reference", help="Output to compare against (e.g. the original model's)")
    parser.add_argument("--cpus", type=int, help="Restrict the model to the first N CPUs (default: all)")
    parser.add_argument("--log", help="File for the model's stdout/stderr (default: <output>.log)")
    args = parser.parse_args()

    main_py = os.path.join(os.path.abspath(args.repo), "model", "framework", "code", "main.py")
    env_bin = os.path.dirname(os.path.abspath(args.python))
    env = {**os.environ, "PATH": env_bin + os.pathsep + os.environ.get("PATH", "")}
    log_path = args.log or args.output + ".log"

    cpus = sorted(os.sched_getaffinity(0))
    if args.cpus:
        if args.cpus > len(cpus):
            sys.exit(f"--cpus {args.cpus}: only {len(cpus)} CPUs available")
        cpus = cpus[: args.cpus]
    restrict = (lambda: os.sched_setaffinity(0, cpus)) if args.cpus else None

    peak = [0, 0]  # RSS, PSS
    start = time.perf_counter()
    with open(log_path, "w") as log:
        proc = subprocess.Popen(
            [args.python, main_py, os.path.abspath(args.input), os.path.abspath(args.output)],
            stdout=log, stderr=subprocess.STDOUT, env=env, preexec_fn=restrict,
        )
        sampler = threading.Thread(target=_sample_peak, args=(proc, peak), daemon=True)
        sampler.start()
        proc.wait()
        sampler.join()
    seconds = round(time.perf_counter() - start, 2)
    # ru_maxrss (kB on Linux): peak of the largest single process among those waited for.
    largest_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    peak_mb = round(max(peak[0], largest_kb) / 1024)
    peak_pss_mb = round(peak[1] / 1024)

    result = {"seconds": seconds, "peak_rss_mb": peak_mb, "peak_pss_mb": peak_pss_mb, "cpus": len(cpus),
              "returncode": proc.returncode, "log": log_path}
    if os.path.exists(args.output):
        with open(args.output) as f:
            result["rows"] = max(0, sum(1 for _ in f) - 1)
    ok = proc.returncode == 0 and os.path.exists(args.output)

    if args.reference and ok:
        report = compare_files(args.reference, args.output)
        result["identical"] = report["identical"]
        if not report["identical"]:
            result["differences"] = report
        ok = report["identical"]

    print(json.dumps(result))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
