#!/usr/bin/env python3
"""prepare_paper.py — stage a validated paper for the user to drag into Drive.

    python prepare_paper.py paper.pdf --name eos55vx_eos6a1h.pdf
    python prepare_paper.py --clear --name eos55vx_eos6a1h.pdf --drive-size 2807037

The second form runs after the upload is verified: it deletes the staged copy, but only
when its size equals the ``fileSize`` Drive reported, so the outbox is empty before the
next incorporation and nothing is lost if the wrong file was uploaded. When staging,
other files already in the outbox are listed under ``leftovers`` (earlier papers that
were never confirmed as uploaded) and are never deleted unasked.

Run it after check_pdf.py has passed, with ``--name`` set to paper_target.py's
``canonical_name``. It copies the PDF into an outbox folder under that name and prints
what the user needs for the upload, plus what the skill needs to verify it afterwards:
the staged path, the Drive folder link and the exact size in bytes. The upload itself
is manual: the Drive connector cannot carry a real paper (see lessons-learned).

The outbox is ``$ERSILIA_MODEL_PAPERS_OUTBOX`` if set, else ``ersilia-model-papers``
inside the user's Downloads folder, else inside the home folder. A stable folder
outside the session scratchpad, so the file is easy to find in a file manager and
survives the session. Re-running with the same paper is a no-op; an existing file of
the same name with different content is replaced only with ``--overwrite``.

The Downloads folder is resolved per OS, because it is not always ``~/Downloads``:

* Windows: the Downloads "known folder" (``SHGetKnownFolderPath``), which follows a
  user who moved it, e.g. into OneDrive;
* Linux and other XDG desktops: ``xdg-user-dir DOWNLOAD``, which follows a localised
  name such as ``~/Transferências``;
* macOS, and the fallback everywhere: ``~/Downloads`` (on macOS the folder is always
  named that on disk, whatever the display language).

The JSON also carries ``open_folder`` and ``open_drive``, ready-made commands that open
the outbox in the file manager and the Drive folder in the browser on the current OS.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import PAPERS_FOLDER_URL, die, emit  # noqa: E402

OUTBOX_NAME = "ersilia-model-papers"

# FOLDERID_Downloads, from the Windows SDK's KnownFolders.h.
_FOLDERID_DOWNLOADS = "{374DE290-123F-4565-9164-39C4925E467B}"


def _windows_downloads():
    """The Downloads known folder on Windows, or ``None`` if the lookup fails."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

        guid = GUID()
        ctypes.oledll.ole32.CLSIDFromString(_FOLDERID_DOWNLOADS, ctypes.byref(guid))
        path_ptr = ctypes.c_wchar_p()
        ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path_ptr))
        try:
            return Path(path_ptr.value) if path_ptr.value else None
        finally:
            ctypes.windll.ole32.CoTaskMemFree(path_ptr)
    except (AttributeError, OSError, ValueError):
        return None


def downloads_dir():
    """The user's Downloads folder on this OS, or ``None`` if there is none."""
    candidate = None
    if sys.platform == "win32":
        candidate = _windows_downloads()
    elif sys.platform != "darwin" and shutil.which("xdg-user-dir"):
        out = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True).stdout.strip()
        # xdg-user-dir answers $HOME when the directory is not configured.
        candidate = Path(out) if out and Path(out) != Path.home() else None
    if candidate is None or not candidate.is_dir():
        candidate = Path.home() / "Downloads"
    return candidate if candidate.is_dir() else None


def default_outbox():
    """The outbox folder, from the env var or the user's Downloads directory."""
    if os.environ.get("ERSILIA_MODEL_PAPERS_OUTBOX"):
        return Path(os.environ["ERSILIA_MODEL_PAPERS_OUTBOX"]).expanduser()
    return (downloads_dir() or Path.home()) / OUTBOX_NAME


def open_commands(folder):
    """Commands that open ``folder`` in the file manager and the Drive folder in a browser."""
    if sys.platform == "win32":
        open_folder = f'explorer "{folder}"'
    elif sys.platform == "darwin":
        open_folder = f'open "{folder}"'
    else:
        open_folder = f'xdg-open "{folder}"'
    # The webbrowser module picks the right browser launcher on every OS.
    open_drive = f'"{sys.executable}" -m webbrowser "{PAPERS_FOLDER_URL}"'
    return open_folder, open_drive


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pdf", nargs="?", help="the validated paper (omit with --clear)")
    parser.add_argument("--name", required=True, help="canonical file name from paper_target.py")
    parser.add_argument("--outbox", help="override the outbox folder")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="after the upload is verified: delete the staged copy of --name",
    )
    parser.add_argument(
        "--drive-size",
        type=int,
        help="with --clear: the fileSize Drive reports; the copy is deleted only if it matches",
    )
    args = parser.parse_args()

    if not args.name.endswith(".pdf") or "/" in args.name:
        die(f"--name must be a bare file name ending in .pdf, got {args.name!r}")
    outbox = Path(args.outbox).expanduser() if args.outbox else default_outbox()

    if args.clear:
        clear(outbox, args.name, args.drive_size)
        return

    if not args.pdf:
        die("give the PDF to stage, or --clear to remove a staged copy")
    source = Path(args.pdf)
    if not source.is_file():
        die(f"{source} does not exist")

    outbox.mkdir(parents=True, exist_ok=True)
    # Anything else in the outbox is a paper from an earlier incorporation that was
    # staged but never confirmed as uploaded. Report it; never delete it unasked.
    leftovers = sorted(p.name for p in outbox.iterdir() if p.is_file() and p.name != args.name)
    target = outbox / args.name
    same_file = target.exists() and (
        target.resolve() == source.resolve() or target.read_bytes() == source.read_bytes()
    )
    if target.exists() and not same_file and not args.overwrite:
        die(f"{target} already exists with different content; pass --overwrite to replace it")
    if not same_file:
        shutil.copyfile(source, target)

    data = target.read_bytes()
    emit(
        {
            "staged_path": str(target),
            "outbox": str(outbox),
            "name": args.name,
            "size_bytes": len(data),
            "md5": hashlib.md5(data).hexdigest(),
            "drive_folder_url": PAPERS_FOLDER_URL,
            "instructions": (
                f"Drag {target} into {PAPERS_FOLDER_URL} (keep the name {args.name}), "
                "then tell me when it is done."
            ),
            "open_folder": open_commands(outbox)[0],
            "open_drive": open_commands(outbox)[1],
            "leftovers": leftovers,
        }
    )


def clear(outbox, name, drive_size):
    """Delete the staged copy, but only once Drive holds a file of the same size.

    The size check is the guard: it is what the skill verified with ``search_files``,
    and a mismatch means the file in Drive is not this one, so the local copy is kept.
    """
    target = outbox / name
    if drive_size is None:
        die("--clear needs --drive-size (the fileSize search_files reported for the uploaded file)")
    if not target.is_file():
        emit({"cleared": False, "reason": f"{target} is not staged (already cleared?)", "outbox": str(outbox)})
        return
    local_size = target.stat().st_size
    if local_size != drive_size:
        die(
            f"not deleting {target}: it is {local_size} bytes but the Drive file is {drive_size}. "
            "The uploaded file is not this one; re-check the upload first.",
        )
    target.unlink()
    remaining = sorted(p.name for p in outbox.iterdir() if p.is_file()) if outbox.is_dir() else []
    emit({"cleared": True, "deleted": str(target), "outbox": str(outbox), "outbox_now": remaining})


if __name__ == "__main__":
    main()
