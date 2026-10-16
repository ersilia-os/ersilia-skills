"""Shared helpers for the model-incorporation-release scripts.

Standard library only, plus the ``gh`` CLI for GitHub. stdout is reserved for
machine-readable JSON; everything advisory goes to stderr.
"""

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request

OWNER = "ersilia-os"

MODEL_ID_RE = re.compile(r"^eos[0-9][a-z0-9]{3}$")

# The Hub publishes its whole catalogue here; post-upload and the retag workflow sync it.
CATALOG_URL = "https://ersilia-model-hub.s3.eu-central-1.amazonaws.com/models.json"

# Drive folder `ersilia_models_articles`, where each model's paper lives as <id>.pdf.
PAPERS_FOLDER_ID = "1_3ZY6-sFZnW0gWanxn9uHOHgkyfgmBHU"
PAPERS_FOLDER_URL = f"https://drive.google.com/drive/folders/{PAPERS_FOLDER_ID}"

# Workflow names as they appear in every eos repo (thin wrappers around
# ersilia-os/ersilia-model-workflows).
WF_PR = "Test model on PR"
WF_UPLOAD = "Test and upload model"
WF_IMAGE = "Test model image"
WF_RETAG = "Retag image on release"

BOT_COMMITTER = "ersilia-bot"
BOT_RELEASER = "github-actions[bot]"

POLITE_MAILTO = "hello@ersilia.io"
USER_AGENT = f"ersilia-skills/model-incorporation-release (mailto:{POLITE_MAILTO})"


def warn(message):
    """Print a WARNING to stderr (stdout is reserved for machine-readable output)."""
    print(f"WARNING: {message}", file=sys.stderr)


def die(message, code=1):
    """Print an ERROR to stderr and exit with ``code``."""
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def check_model_id(model_id):
    """Exit unless ``model_id`` looks like an Ersilia identifier (eos + 4 characters)."""
    if not MODEL_ID_RE.match(model_id or ""):
        die(f"{model_id!r} is not an Ersilia model identifier (expected e.g. eos88ir)")
    return model_id


def emit(data):
    """Print ``data`` as pretty JSON on stdout."""
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def gh_api(path, allow_404=False):
    """Call ``gh api <path>`` and return the parsed JSON.

    Model repos hold a few dozen runs and a handful of tags, so callers ask for
    ``per_page=100`` instead of paginating. Returns ``None`` for a 404 when
    ``allow_404`` is set (a missing tag or release is an answer, not an error). Any
    other failure exits, because every verdict depends on reading GitHub correctly.
    """
    result = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if result.returncode != 0:
        if allow_404 and "404" in (result.stderr + result.stdout):
            return None
        die(f"gh api {path} failed: {result.stderr.strip() or result.stdout.strip()}")
    text = result.stdout.strip()
    return json.loads(text) if text else None


def gh_text(args):
    """Run ``gh <args>`` and return stdout, or ``""`` on failure (used for logs)."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def fetch(url, timeout=30, binary=False):
    """GET ``url``; return the body (bytes when ``binary``) or ``None`` on any error."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return body if binary else body.decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        warn(f"fetch failed for {url}: {exc}")
        return None


def fetch_json(url, timeout=30):
    """GET ``url`` and parse it as JSON, or return ``None`` if either step fails."""
    body = fetch(url, timeout=timeout)
    if body is None:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        warn(f"response from {url} is not JSON: {exc}")
        return None


def catalog_entry(model_id, catalog=None):
    """Return the model's row from the Hub catalogue, or ``None`` if it is not listed."""
    rows = catalog if catalog is not None else (fetch_json(CATALOG_URL) or [])
    for row in rows:
        if row.get("Identifier") == model_id:
            return row
    return None


def read_metadata_fields(text):
    """Parse the top-level scalar fields of a metadata.yml without a YAML library.

    Only ``Key: value`` lines at column 0 are read; list fields are skipped. Indented
    continuation lines are folded back in, because long values wrap (eos2e3s's Title runs
    onto a second line). That covers every field this skill checks (Title, Publication,
    Publication Type, Status, Release, DockerHub).
    """
    fields = {}
    key = None
    for line in (text or "").splitlines():
        match = re.match(r"^([A-Z][A-Za-z ]*):\s*(.*)$", line)
        if match:
            key = None
            value = match.group(2).strip()
            if value and not value.startswith("-"):
                key = match.group(1).strip()
                fields[key] = value
        elif key and line[:1].isspace() and line.strip() and not line.strip().startswith("-"):
            fields[key] += " " + line.strip()
        else:
            key = None
    return {k: v.strip().strip("'\"") for k, v in fields.items()}


def remote_metadata(model_id):
    """Fetch and parse ``metadata.yml`` from the model repo's main branch."""
    import base64

    payload = gh_api(f"repos/{OWNER}/{model_id}/contents/metadata.yml", allow_404=True)
    if not payload or "content" not in payload:
        return {}
    return read_metadata_fields(base64.b64decode(payload["content"]).decode("utf-8", "replace"))


# arXiv mints a DOI for every submission; a Publication field often carries the abs/pdf URL.
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<id>\d{4}\.\d{4,5})(?:v\d+)?", re.I)
ARXIV_DOI_RE = re.compile(r"10\.48550/arxiv\.(?P<id>\d{4}\.\d{4,5})", re.I)


def normalise_doi(value):
    """Reduce any DOI form (bare, ``doi:``, ``https://doi.org/``, arXiv URL) to ``10.x/y``.

    Lower-cased, because DOIs are case-insensitive and two models citing one paper must
    compare equal. Returns ``None`` when the value carries no recognisable DOI.
    """
    text = str(value or "").strip()
    arxiv = ARXIV_RE.search(text)
    if arxiv:
        return f"10.48550/arxiv.{arxiv.group('id')}"
    text = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", text, flags=re.I)
    text = text.strip().rstrip(".")
    return text.lower() if text.startswith("10.") and "/" in text else None


def arxiv_id(value):
    """Return the arXiv identifier carried by a URL or arXiv DOI, or ``None``."""
    text = str(value or "")
    match = ARXIV_RE.search(text) or ARXIV_DOI_RE.search(text)
    return match.group("id") if match else None
