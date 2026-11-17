"""HTTP requests with the skill's User-Agent (standard library only).

``request`` raises; ``get_json`` and ``get_text`` retry and return None, for the corpus
builders, where one missing page must not stop the run. check_references.py keeps its
own cached lookup, because there the HTTP status is the answer.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from lib.common import USER_AGENT, warn


def request(
    url: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: int = 60,
) -> str:
    """GET ``url``, or POST ``body`` as JSON; return the response text. An HTTP error
    raises RuntimeError with the status and the start of the response."""
    req = urllib.request.Request(
        url,
        data=None if body is None else json.dumps(body).encode(),
        headers={
            "User-Agent": USER_AGENT,
            **({} if body is None else {"Content-Type": "application/json"}),
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"HTTP {e.code}: {e.read().decode(errors='replace')[:200]}"
        ) from e


def post_json(url: str, body: dict, headers: dict | None = None) -> dict:
    """POST JSON, return JSON; raises on failure."""
    return json.loads(request(url, body, headers, timeout=120) or "{}")


def get_text(url: str, headers: dict | None = None) -> str | None:
    """GET text, trying three times; None (with a warning) when all fail."""
    for attempt in range(3):
        try:
            return request(url, headers=headers)
        except Exception as e:  # noqa: BLE001 - network: retry then give up
            if attempt == 2:
                warn(f"{url[:100]}: {e}")
                return None
            time.sleep(3)
    return None


def get_json(url: str) -> dict | None:
    """GET JSON, trying three times; None (with a warning) when all fail."""
    text = get_text(url, {"Accept": "application/json"})
    try:
        return None if text is None else json.loads(text)
    except json.JSONDecodeError as e:
        warn(f"{url[:100]}: {e}")
        return None
