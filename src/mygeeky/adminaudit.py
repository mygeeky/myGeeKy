"""The admin console's activity log: every accept, reject, publish, invite and support email, with when and where.

One line per action in admin_activity.jsonl in the data folder, so it travels with the maker's other data and, like
every .jsonl there, merges line by line between devices. It holds what was done ("Published 5 listings", "Replied to
a support email"), never anyone's email address or message.
"""
from __future__ import annotations

import platform
from datetime import datetime, timezone
from typing import Any

from .config import DATA_DIR
from .files import append_jsonl, read_jsonl

LOG_FILE = DATA_DIR / "admin_activity.jsonl"
KEEP = 2000


def log(what: str, where: str = "computer") -> None:
    """Note one action. Never raises: the log must not get in the way of the action itself."""
    try:
        append_jsonl(LOG_FILE, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "what": " ".join(str(what).split())[:200], "where": where,
                                "device": (platform.node() or "")[:40]})
    except Exception:
        pass


def recent(n: int = 50) -> list[dict[str, Any]]:
    """The newest `n` actions, newest first."""
    rows = [r for r in read_jsonl(LOG_FILE) if isinstance(r, dict) and r.get("at") and r.get("what")]
    rows.sort(key=lambda r: str(r["at"]), reverse=True)
    return rows[:n]
