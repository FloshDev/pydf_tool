from __future__ import annotations

import json
import urllib.request
from urllib.error import URLError

from . import __version__

_RELEASES_URL = "https://api.github.com/repos/FloshDev/pydf_tool/releases/latest"
_TIMEOUT = 4


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def fetch_latest_version() -> str | None:
    """Return latest release tag (e.g. 'v1.0.2') if newer than current, else None."""
    tag, error = check_update_status()
    if error:
        return None
    return tag


def check_update_status() -> tuple[str | None, bool]:
    """
    Return (latest_tag, error).
    latest_tag is set when a newer version exists, None otherwise.
    error is True when the check could not be performed.
    """
    try:
        req = urllib.request.Request(
            _RELEASES_URL,
            headers={"User-Agent": f"pydf-tool/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        tag = data.get("tag_name", "")
        if not tag:
            return None, False
        if _parse_version(tag) > _parse_version(__version__):
            return tag, False
        return None, False
    except (URLError, OSError, ValueError, KeyError):
        return None, True
