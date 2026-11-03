"""Turn one section of a model's install.yml into the shell commands that install it.

Mirrors how ersilia-pack converts install.yml entries, so the scratch env gets what the
image would get:

- ["pip", pkg, ver, *flags]          -> <python> -m pip install pkg==ver *flags
- ["pip", "git+https://...", *flags] -> <python> -m pip install git+https://... *flags
- ["conda", pkg, ver, *channels]     -> conda install -y -c <ch> ... pkg=ver
- ["conda", "install", *args]        -> conda install *args -y
- "pip install ..." / "conda ..."    -> as written (pip run with <python> -m)
- anything else                      -> as written

Usage
-----
    python render_install.py <install.yml> <commands|gpu> <env_python> [<env_name>]

Prints the commands, one per line. conda lines get `-n <env_name>` when given.
Pipe into bash to run them: `python render_install.py ... | bash -e`.
Standard library only: reads the install.yml format (top-level keys, `- ` entries that
are flow lists or strings, trailing `#` comments).
"""

import ast
import re
import shlex
import sys


def pip_line(entry, python):
    if isinstance(entry, str):
        parts = shlex.split(entry)
        return f"{python} -m " + " ".join(["pip"] + parts[1:])
    entry = [str(x) for x in entry]
    pkg = entry[1]
    if pkg.startswith("git+"):
        spec, flags = pkg, entry[2:]
    elif len(entry) == 2:
        raise ValueError(f"pip entry without version: {entry}")
    else:
        ver = entry[2]
        spec = pkg if ver == "" else f"{pkg}=={ver}"
        flags = entry[3:]
    return f"{python} -m pip install " + " ".join([spec] + flags)


def conda_line(entry, env_name):
    target = ["-n", env_name] if env_name else []
    if isinstance(entry, str):
        parts = shlex.split(entry)
        if len(parts) > 1 and parts[1] == "install" and env_name and "-n" not in parts:
            parts = parts[:2] + target + parts[2:]
        return " ".join(parts)
    entry = [str(x) for x in entry]
    if entry[1] == "install":
        args = [a for a in entry[2:] if a != "-y"]
        return " ".join(["conda", "install", "-y"] + target + args)
    _, pkg, ver, *rest = entry
    channels = [c for c in rest if c != "-y"] or ["defaults"]
    flags = []
    for c in channels:
        flags += ["-c", c]
    return " ".join(["conda", "install", "-y"] + target + flags + [f"{pkg}={ver}"])


def strip_comment(line):
    # drop a trailing "# ..." that is not inside quotes
    quote = None
    for i, ch in enumerate(line):
        if quote:
            quote = None if ch == quote else quote
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line.rstrip()


def load_sections(path):
    sections, current = {}, None
    with open(path) as f:
        for raw in f:
            line = strip_comment(raw)
            if not line.strip():
                continue
            key = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
            if key:
                current = key.group(1)
                sections[current] = [] if not key.group(2) else key.group(2)
                continue
            item = re.match(r"^\s*-\s+(.*)$", line)
            if item and isinstance(sections.get(current), list):
                text = item.group(1).strip()
                if text[:1] in "[\"'":
                    sections[current].append(ast.literal_eval(text))
                else:
                    sections[current].append(text)
    return sections


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    path, section, python = sys.argv[1:4]
    env_name = sys.argv[4] if len(sys.argv) > 4 else None
    data = load_sections(path)
    if section not in data:
        sys.exit(f"No '{section}' section in {path}")
    for entry in data[section]:
        head = (entry[0] if isinstance(entry, list) else shlex.split(entry)[0]).lower()
        if head in ("pip", "pip3"):
            print(pip_line(entry, python))
        elif head == "conda":
            print(conda_line(entry, env_name))
        else:
            print(" ".join(map(str, entry)) if isinstance(entry, list) else entry)


if __name__ == "__main__":
    main()
