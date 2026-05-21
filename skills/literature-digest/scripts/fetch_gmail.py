"""Normalise raw Gmail threads into literature-digest item schema.

Gmail data flow (same shape as Slack):
    Claude (via the Gmail MCP) → raw JSON file → this script → canonical JSON file.

Three classes of inbox content matter:

1. **Google Scholar alerts** — sender `scholaralerts-noreply@google.com`. Each thread
   contains 1+ paper items in the snippet/body. The subject is the alert name
   (e.g. "Kelly Chibale - new articles"); the body has author lists and links.

2. **Newsletters** — Substack, Mailchimp, etc. Senders like
   `*@substack.com`, `*@mailchimp.com`, plus a curated allow-list of newsletter
   sources (Decoding Bio, Asimov Press, Pat Walters, Owl Posting).

3. **Collaborator mentions** — any other thread where a URL to a paper/preprint/
   GitHub/HuggingFace was shared. The sender is the collaborator.

The script does not call Gmail itself. SKILL.md tells Claude to collect threads via
the MCP and dump them to a raw JSON file matching the schema below, then invoke
this script.

The expected `--raw` file is a JSON list of thread dicts. Each thread should have:
    {
        "id": "...",
        "subject": "...",
        "sender": "scholaralerts-noreply@google.com",
        "sender_name": "Google Scholar Alerts",
        "date": "2026-05-20T15:00:00Z" or "2026-05-20",
        "body_text": "...",
        "snippet": "...",
        "thread_url": "https://mail.google.com/..."  (optional)
    }

We emit one canonical item per URL discovered in subject/snippet/body. Privacy: we
**never** include the recipient's email address in the output.

Usage:
    python fetch_gmail.py --raw /tmp/gmail_raw.json --out /tmp/gmail.json
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from typing import Any

from _common import (
    extract_arxiv_ids,
    extract_dois,
    normalise_url,
    read_json,
    validate_item,
    warn,
    write_json,
)

URL_REGEX = re.compile(r"https?://[^\s\)\"<>|\]]+")

# Senders we treat as Scholar alerts.
SCHOLAR_SENDERS = {
    "scholaralerts-noreply@google.com",
    "scholarcitations-noreply@google.com",
}

# Curated allow-list of newsletter senders. Add to this as we onboard more newsletters.
NEWSLETTER_SENDERS = {
    # Wildcards are evaluated as `sender.endswith(domain)`.
    "@substack.com",
    "@mail.beehiiv.com",
    "@mailchimp.com",
    "@mailerlite.com",
    # Specific known newsletters:
    "decodingbio@substack.com",
    "newsletter@asimov.press",
    "patwalters@substack.com",
    "owlposting@substack.com",
}

# URL hosts to strip out before counting "interesting" links — these are tracking
# wrappers, unsubscribe links, etc., not papers.
SKIP_URL_HOSTS = {
    "list-manage.com",
    "lists.substack.com",
    "sg.beehiiv.com",
    "doubleclick.net",
    "googleadservices.com",
    "facebook.com/tr",
    "twitter.com/i/redirect",
}

# Scholar alert redirects look like https://scholar.google.com/scholar_url?url=ENCODED
SCHOLAR_REDIRECT_RE = re.compile(
    r"https?://scholar\.google\.[^/]+/scholar_url\?(?:[^&]+&)*?url=([^&]+)"
)


def classify_sender(sender: str | None) -> str:
    s = (sender or "").lower().strip()
    if s in SCHOLAR_SENDERS:
        return "scholar"
    for pattern in NEWSLETTER_SENDERS:
        if pattern.startswith("@") and s.endswith(pattern):
            return "newsletter"
        if pattern == s:
            return "newsletter"
    return "collaborator"


def should_skip_url(url: str) -> bool:
    nu = normalise_url(url) or ""
    return any(host in nu for host in SKIP_URL_HOSTS)


def unwrap_scholar_redirect(url: str) -> str:
    """If `url` is a scholar.google redirect, return the underlying target URL."""
    m = SCHOLAR_REDIRECT_RE.match(url)
    if not m:
        return url
    from urllib.parse import unquote
    return unquote(m.group(1))


def extract_urls(text: str) -> list[str]:
    """Pull every URL out of the message body, after unwrapping Scholar redirects."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in URL_REGEX.findall(text or ""):
        unwrapped = unwrap_scholar_redirect(raw)
        nu = normalise_url(unwrapped)
        if not nu or nu in seen or should_skip_url(unwrapped):
            continue
        seen.add(nu)
        out.append(unwrapped)
    return out


def guess_venue_from_url(url: str) -> str:
    u = url.lower()
    if "biorxiv.org" in u:
        return "bioRxiv"
    if "chemrxiv.org" in u:
        return "chemRxiv"
    if "medrxiv.org" in u:
        return "medRxiv"
    if "arxiv.org" in u:
        return "arXiv"
    if "doi.org" in u or "europepmc.org" in u or "pubmed.ncbi" in u:
        return "Peer-reviewed (resolve via DOI)"
    if "github.com" in u:
        return "GitHub"
    if "huggingface.co" in u:
        return "Hugging Face"
    if "ersilia.io" in u:
        return "Ersilia"
    return "Web link"


def thread_date(thread: dict[str, Any]) -> str:
    """Return YYYY-MM-DD from whatever date shape the thread carried."""
    raw = thread.get("date") or ""
    if not raw:
        return ""
    # Try a few common shapes; the MCP usually returns ISO 8601 with `Z`.
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:len(fmt) - fmt.count("%")], fmt).date().isoformat()
        except ValueError:
            continue
    # Fall back: just take the first 10 characters if they look like YYYY-MM-DD.
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10]
    return ""


def title_for_item(thread: dict[str, Any], classification: str, url: str) -> str:
    """Best available title for the emitted item. Never includes the recipient address."""
    subject = (thread.get("subject") or "").strip()
    snippet = (thread.get("snippet") or "").strip()
    if classification == "scholar":
        # Scholar alerts: subject is "{Author} - new articles" — keep the snippet.
        if snippet:
            t = re.sub(r"\s+", " ", snippet)[:200]
            return t.rstrip(".") + ("..." if len(t) == 200 else "")
        return subject or f"Scholar alert ({guess_venue_from_url(url)})"
    if classification == "newsletter":
        return subject or f"Newsletter item ({guess_venue_from_url(url)})"
    # Collaborator share: prefer subject, fall back to snippet.
    return subject or (re.sub(r"\s+", " ", snippet)[:160]).rstrip(".") or f"Shared link ({guess_venue_from_url(url)})"


def sharer_display_name(thread: dict[str, Any], classification: str) -> str:
    """Public-safe attribution. Never expose the recipient's address."""
    sender_name = (thread.get("sender_name") or "").strip()
    sender = (thread.get("sender") or "").strip()
    if classification == "scholar":
        # Try to recover the author whose alert this is from the subject.
        subject = (thread.get("subject") or "").strip()
        m = re.match(r"^(.*?)\s*-\s*new articles?$", subject, re.IGNORECASE)
        if m:
            return f"Scholar alert: {m.group(1).strip()}"
        return "Scholar alert"
    if classification == "newsletter":
        # Use the human-friendly sender name; never the email address.
        if sender_name:
            return f"Newsletter: {sender_name}"
        # If only the domain is available, surface the domain (not the user part).
        if "@" in sender:
            return f"Newsletter ({sender.split('@', 1)[1]})"
        return "Newsletter"
    # Collaborator: prefer the display name; never expose an email address.
    if sender_name:
        return sender_name
    if "@" in sender:
        return f"Collaborator ({sender.split('@', 1)[1]})"
    return "Collaborator"


def normalise_thread(thread: dict[str, Any]) -> list[dict[str, Any]]:
    text = " ".join([
        thread.get("subject") or "",
        thread.get("snippet") or "",
        thread.get("body_text") or "",
    ])
    urls = extract_urls(text)
    if not urls:
        return []

    classification = classify_sender(thread.get("sender"))
    date = thread_date(thread) or datetime.utcnow().date().isoformat()
    sharer = sharer_display_name(thread, classification)
    venue_suffix = {
        "scholar": "Gmail / Scholar alerts",
        "newsletter": "Gmail / newsletters",
        "collaborator": "Gmail / collaborator share",
    }[classification]

    items: list[dict[str, Any]] = []
    for url in urls:
        dois = extract_dois(url) + extract_dois(text)
        doi = dois[0] if dois else None
        arxiv_ids = extract_arxiv_ids(url) + extract_arxiv_ids(text)
        arxiv_id = arxiv_ids[0] if arxiv_ids else None

        title = title_for_item(thread, classification, url)
        venue = guess_venue_from_url(url)
        if venue == "Web link":
            venue = venue_suffix

        item = {
            "title": title,
            "authors": [{"name": sharer, "affiliation": "Ersilia inbox", "country": None}],
            "venue": venue,
            "date": date,
            "doi": doi,
            "arxiv_id": arxiv_id,
            "url": url,
            "abstract": None,
            "source": "gmail",
            "source_subtype": classification,
            "raw": {
                "id": thread.get("id"),
                "subject": thread.get("subject"),
                "sender_name": thread.get("sender_name"),
                # NOTE: we deliberately drop `sender` (the raw email address) to avoid
                # leaking PII into committed digests. Re-add it locally if you need it
                # for debugging.
                "snippet": thread.get("snippet"),
                "thread_url": thread.get("thread_url"),
            },
        }
        errs = validate_item(item)
        if errs:
            warn(f"gmail item dropped: {'; '.join(errs)} — {title[:80]}")
            continue
        items.append(item)
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw", required=True,
                   help="Path to JSON file with raw Gmail threads collected via the MCP.")
    p.add_argument("--out", required=True, help="Output JSON path.")
    args = p.parse_args(argv)

    try:
        raw = read_json(args.raw)
    except (FileNotFoundError, ValueError) as e:
        warn(f"could not read raw gmail file: {e}")
        write_json(args.out, [])
        return 0

    items: list[dict[str, Any]] = []
    for thread in raw:
        if not isinstance(thread, dict):
            continue
        items.extend(normalise_thread(thread))

    write_json(args.out, items)
    print(f"gmail: wrote {len(items)} items to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
