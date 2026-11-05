"""Profile a model's main.py: where the time goes, including subprocesses.

cProfile only sees the Python process it runs in. Many Ersilia models spend most
of their time in subprocesses (a second Python script, xtb, mordred, a bash
file), which cProfile reports only as time spent waiting. So this script also
records every subprocess the model starts (subprocess.Popen and os.system), with
its command line and how long it ran.

Run it with the model environment's Python:

    <env>/bin/python profile_model.py --repo <model_path> --input in.csv \
        [--output out.csv] [--top 30] [--stats prof.out]

Prints the top functions by cumulative time and a table of subprocess calls
(count and total seconds per command, longest first). To see inside a slow
subprocess, rerun its command under `python -m cProfile -s cumtime`.
"""

import argparse
import cProfile
import os
import pstats
import re
import runpy
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

calls = []  # (seconds, command)


def _command_text(cmd):
    return cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)


def _patch_subprocess():
    original_init = subprocess.Popen.__init__
    original_wait = subprocess.Popen.wait
    original_system = os.system

    def init(self, args, *a, **k):
        self._profile_start = time.perf_counter()
        self._profile_cmd = _command_text(args)
        original_init(self, args, *a, **k)

    def wait(self, *a, **k):
        code = original_wait(self, *a, **k)
        if not getattr(self, "_profile_logged", False):
            self._profile_logged = True
            calls.append((time.perf_counter() - self._profile_start, self._profile_cmd))
        return code

    def system(cmd):
        start = time.perf_counter()
        code = original_system(cmd)
        calls.append((time.perf_counter() - start, cmd))
        return code

    subprocess.Popen.__init__ = init
    subprocess.Popen.wait = wait
    os.system = system


def _shorten(cmd, repo):
    """Group calls that differ only in temporary paths."""
    cmd = cmd.replace(repo, "<repo>")
    cmd = re.sub(r"/tmp/\S+", "<tmp>", cmd)
    return cmd[:160]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repo", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", help="Model output (default: a temporary file)")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--stats", help="Also save the raw cProfile stats here")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    main_py = os.path.join(repo, "model", "framework", "code", "main.py")
    output = args.output or os.path.join(tempfile.mkdtemp(), "out.csv")
    env_bin = os.path.dirname(sys.executable)
    os.environ["PATH"] = env_bin + os.pathsep + os.environ.get("PATH", "")

    _patch_subprocess()
    sys.argv = [main_py, os.path.abspath(args.input), output]
    sys.path.insert(0, os.path.dirname(main_py))

    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    try:
        runpy.run_path(main_py, run_name="__main__")
    except SystemExit:
        pass
    finally:
        profiler.disable()
    total = time.perf_counter() - start

    print(f"\nTotal: {total:.1f} s (output: {output})\n")
    stats = pstats.Stats(profiler).strip_dirs().sort_stats("cumulative")
    stats.print_stats(args.top)
    if args.stats:
        profiler.dump_stats(args.stats)

    if calls:
        grouped = defaultdict(lambda: [0, 0.0])
        for seconds, cmd in calls:
            key = _shorten(cmd, repo)
            grouped[key][0] += 1
            grouped[key][1] += seconds
        print(f"Subprocesses: {len(calls)} calls, {sum(s for s, _ in calls):.1f} s in total")
        for cmd, (count, seconds) in sorted(grouped.items(), key=lambda kv: -kv[1][1])[:20]:
            print(f"  {seconds:8.1f} s  x{count:<5} {cmd}")
    else:
        print("Subprocesses: none")


if __name__ == "__main__":
    main()
