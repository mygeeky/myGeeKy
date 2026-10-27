"""The maker's admin actions made on the phone, applied here.

The phone never edits admin_prospects.json or scout.json itself: those are whole JSON files that every
computer also writes, and sync settles them with "the newer copy wins" -- so a phone write could quietly
undo something done on a computer that had not synced yet. Instead the phone appends one line per action
to admin_actions.jsonl ("invited ccsosa", "accepted listing X"), which, like every .jsonl here, merges line
by line between all devices. Each computer applies the lines it has not applied before and records them in
admin_actions_applied.jsonl (synced too), so an action is applied once -- and an Undo made later on a
computer is never overwritten by replaying an older phone action.

Every action is a plain status change, so applying the same one twice (two computers at once) changes
nothing. Only the maker's computers apply anything; the lines are checked like any other input.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .config import DATA_DIR, MyGeekyConfig
from .files import append_jsonl, read_jsonl

ACTIONS_FILE = DATA_DIR / "admin_actions.jsonl"
APPLIED_FILE = DATA_DIR / "admin_actions_applied.jsonl"

PROSPECT = ("invited", "declined", "new")
LISTING = ("accepted", "rejected", "new")
_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_LOGIN = re.compile(r"^[A-Za-z0-9-]{1,39}$")


def _apply_one(action: dict[str, Any]) -> bool:
    kind, status = action.get("kind"), action.get("status")
    if kind == "prospect" and status in PROSPECT and _LOGIN.match(str(action.get("login", ""))):
        from . import admin
        state = admin.load()
        entry = state.setdefault("people", {}).get(str(action["login"]).lower())
        if entry is None:
            return False
        if status == "invited":          # when it was done on the phone, so today's count stays honest
            entry["invited_at"] = str(action.get("at") or datetime.now(timezone.utc).isoformat())[:40]
        elif status == "new":
            entry.pop("invited_at", None)
        entry["status"] = status
        admin.save(state)
        return True
    if kind == "listing" and status in LISTING and isinstance(action.get("id_listing"), str):
        from . import scout                  # a status only: what gets published is edited on the computer
        return scout.set_status(action["id_listing"], status)
    return False


def apply(cfg: MyGeekyConfig | None = None) -> int:
    """Apply the phone's admin actions not applied yet, oldest first. Returns how many were new."""
    from . import admin
    from .config import load_config
    if not admin.is_admin(cfg or load_config()):
        return 0
    done = {r.get("id") for r in read_jsonl(APPLIED_FILE) if isinstance(r, dict)}
    fresh = [a for a in read_jsonl(ACTIONS_FILE) if isinstance(a, dict) and _ID.match(str(a.get("id", "")))
             and a["id"] not in done]
    for action in sorted(fresh, key=lambda a: str(a.get("at", ""))):
        try:
            ok = _apply_one(action)
        except Exception:  # noqa: BLE001 -- one odd line never stops the others
            ok = False
        append_jsonl(APPLIED_FILE, {"id": action["id"], "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                    "ok": ok})
        done.add(action["id"])
    return len(fresh)
