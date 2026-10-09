"""Runtime tracer, loaded through PYTHONPATH by every Python process of a model run.

It is inactive unless OPT_TRACE_DIR is set. When active, each Python process
(the main.py started by run.sh, and any child Python process or
multiprocessing worker) writes one JSON file to OPT_TRACE_DIR when it exits:

- ``modules``: top-level names of every module in sys.modules
- ``files``: every file under the environment prefix that the process touched:
  module files, files opened (audit hook ``open``) and shared libraries mapped
  into memory (/proc/self/maps)
- ``execs``: executables started (subprocess, os.exec*, os.system)
- ``missing_imports``: imports that no finder could resolve. Code that does
  ``try: import x / except ImportError`` leaves a trace here, so a candidate
  that adds names to this list has made the model take a fallback path
- ``covered``: if OPT_TRACE_COVER is set to a directory, the lines executed in
  .py files under it, as {file: [line, ...]}
- ``called_files`` / ``called_modules``: if OPT_TRACE_CALLS is set, the
  environment files whose Python functions ran outside an import, and the
  top-level modules of C functions called outside an import. A package that
  is loaded but appears in neither only ran code while being imported

Standard library only, Python 3.7+ (the audit hook needs 3.8; on 3.7 only
modules, mapped libraries and missing imports are recorded).
"""

import os
import sys

_TRACE_DIR = os.environ.get("OPT_TRACE_DIR")


def _chain_next_sitecustomize():
    """Run the sitecustomize this file shadows, if the environment has one."""
    import importlib.machinery
    import importlib.util

    here = os.path.dirname(os.path.abspath(__file__))
    paths = [p for p in sys.path if os.path.abspath(p or ".") != here]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", paths)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def _start():
    import atexit
    import json
    import threading

    prefixes = tuple(
        sorted({os.path.realpath(p) for p in (sys.prefix, sys.base_prefix, sys.exec_prefix)})
    )
    cover_root = os.environ.get("OPT_TRACE_COVER")
    cover_root = os.path.realpath(cover_root) if cover_root else None

    state = {
        "files": set(),
        "execs": set(),
        "missing": set(),
        "covered": {},
        "busy": False,
        "dumped": False,
    }

    def keep(path):
        try:
            path = os.fsdecode(path)
        except TypeError:
            return
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        path = os.path.realpath(path)
        if path.startswith(prefixes):
            state["files"].add(path)

    def audit(event, args):
        if state["busy"]:
            return
        state["busy"] = True
        try:
            if event == "open":
                if isinstance(args[0], (str, bytes, os.PathLike)):
                    keep(args[0])
            elif event in ("subprocess.Popen", "os.exec", "os.posix_spawn", "os.spawn"):
                exe = args[0]
                argv = args[1] if len(args) > 1 else None
                if exe is None and argv:
                    exe = argv[0] if not isinstance(argv, (str, bytes)) else argv
                if isinstance(exe, (str, bytes, os.PathLike)):
                    state["execs"].add(os.fsdecode(exe))
            elif event == "os.system":
                state["execs"].add(os.fsdecode(args[0]))
        except Exception:
            pass
        finally:
            state["busy"] = False

    class MissingFinder:
        """Last finder on sys.meta_path: only reached when no other finder found the module."""

        def find_spec(self, name, path=None, target=None):
            state["missing"].add(name)
            return None

        def find_module(self, name, path=None):  # Python < 3.4 protocol, harmless
            return None

    sys.meta_path.append(MissingFinder())
    if hasattr(sys, "addaudithook"):
        sys.addaudithook(audit)

    if cover_root:
        covered = state["covered"]

        def local(frame, event, arg):
            if event == "line":
                covered.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
            return local

        inside = {}

        def glob(frame, event, arg):
            fname = frame.f_code.co_filename
            hit = inside.get(fname)
            if hit is None:
                hit = inside[fname] = not fname.startswith("<") and os.path.realpath(fname).startswith(cover_root)
            if hit:
                covered.setdefault(fname, set()).add(frame.f_lineno)
                return local
            return None

        sys.settrace(glob)
        threading.settrace(glob)

    calls_on = bool(os.environ.get("OPT_TRACE_CALLS"))
    called_files, called_mods = set(), set()
    if calls_on:
        # Which packages run code after they are imported. Calls made while an
        # import is in progress (module bodies, decorators, registration) don't
        # count: a package that only runs at import time is import-only.
        depth = threading.local()

        def prof(frame, event, arg):
            if event == "call":
                code = frame.f_code
                if code.co_name == "_find_and_load":
                    depth.n = getattr(depth, "n", 0) + 1
                elif not getattr(depth, "n", 0) and code.co_name != "<module>":
                    called_files.add(code.co_filename)
            elif event == "return":
                # the profiler starts inside the import of this very module, so
                # the first return comes without a matching call: never go below 0
                if frame.f_code.co_name == "_find_and_load" and getattr(depth, "n", 0) > 0:
                    depth.n -= 1
            elif event == "c_call" and not getattr(depth, "n", 0):
                mod = getattr(arg, "__module__", None)
                if not mod:
                    owner = getattr(arg, "__self__", None)
                    if owner is not None:
                        mod = getattr(owner, "__name__", None) if isinstance(owner, type(os)) \
                            else type(owner).__module__
                if mod:
                    called_mods.add(mod.split(".")[0])

        sys.setprofile(prof)
        threading.setprofile(prof)

    def dump():
        if state["dumped"]:
            return
        state["dumped"] = True
        state["busy"] = True
        try:
            if cover_root:
                sys.settrace(None)
            if calls_on:
                sys.setprofile(None)
            called = set()
            for f in called_files:
                if not f.startswith("<"):
                    rp = os.path.realpath(f)
                    if rp.startswith(prefixes):
                        called.add(rp)
            for mod in list(sys.modules.values()):
                f = getattr(mod, "__file__", None)
                if f:
                    keep(f)
            try:
                with open("/proc/self/maps") as fh:
                    for line in fh:
                        parts = line.split(None, 5)
                        if len(parts) == 6 and parts[5].startswith("/"):
                            keep(parts[5].strip())
            except OSError:
                pass
            out = {
                "pid": os.getpid(),
                "argv": list(sys.argv),
                "executable": sys.executable,
                "prefix": sys.prefix,
                "modules": sorted({m.split(".")[0] for m in list(sys.modules)}),
                "files": sorted(state["files"]),
                "execs": sorted(state["execs"]),
                "missing_imports": sorted(state["missing"]),
                "calls_traced": calls_on,
                "called_files": sorted(called),
                "called_modules": sorted(called_mods),
                "covered": {
                    os.path.realpath(k): sorted(v) for k, v in state["covered"].items()
                },
            }
            os.makedirs(_TRACE_DIR, exist_ok=True)
            path = os.path.join(_TRACE_DIR, "trace-%d-%s.json" % (os.getpid(), os.urandom(3).hex()))
            with open(path, "w") as fh:
                json.dump(out, fh)
        except Exception as e:  # never break the model because of the tracer
            sys.stderr.write("[opt-tracer] could not write trace: %r\n" % (e,))

    atexit.register(dump)

    # multiprocessing workers leave through os._exit, which skips atexit
    real_exit = os._exit

    def traced_exit(code):
        dump()
        real_exit(code)

    os._exit = traced_exit


if _TRACE_DIR:
    try:
        _start()
    except Exception as _e:
        sys.stderr.write("[opt-tracer] disabled: %r\n" % (_e,))

try:
    _chain_next_sitecustomize()
except Exception:
    pass
