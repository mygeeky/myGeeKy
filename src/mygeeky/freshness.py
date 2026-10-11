"""What you've already seen, so every tab keeps feeling new.

A card counts as *seen* once it has been mostly on screen for a moment while
the panel was open (the panel reports that), or when you clicked it. Seen
things make room for ones you haven't seen; each kind has its own rule:

* people, repos: rest for a few days, then may come back (a clicked person
  never comes back: clicking already excludes them for good);
* Market rows: move down for a few days instead of disappearing;
* news, headlines, papers, models: read once, never shown as new again;
* the Activity feed: a timeline, nothing moves; seen entries are just dimmed.

Something seen several times and never clicked rests much longer: you're
clearly not interested. Nothing here talks to GitHub; it only reorders and
labels what the tabs already have, and says when a tab is running low on new
things (the panel then searches again in the background).

Stored in seen.json (synced with your other computers like the rest).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from .config import SEEN_FILE, MyGeekyConfig
from .files import read_json, write_json

NEVER = None                    # rest period meaning "never comes back as new"
KEEP_DAYS = 120                 # forget entries not seen for this long (keeps the file small)

# kind -> how a seen item is treated
HIDE, SINK, DIM = "hide", "sink", "dim"
MODES = {"person": HIDE, "repo": HIDE, "market": SINK, "headline": HIDE, "news": HIDE,
         "paper": HIDE, "model": HIDE, "activity": DIM}


def rest_days(cfg: MyGeekyConfig, kind: str) -> float | None:
    return {"person": cfg.fresh_people_days, "repo": cfg.fresh_repos_days,
            "market": cfg.fresh_market_days}.get(kind, NEVER)


def item_key(kind: str, item: dict[str, Any]) -> str:
    """A stable identity for a card's item."""
    for field in ("username", "full_name", "repo", "id", "doi", "url", "link", "title"):
        value = item.get(field)
        if value:
            return f"{kind}:{str(value).lower()}"
    return ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(stamp: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp) if stamp else None
    except ValueError:
        return None


# --------------------------------------------------------------------------- the seen.json store
def load() -> dict[str, Any]:
    data = read_json(SEEN_FILE, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("items", {})
    data.setdefault("meta", {})
    return data


def save(data: dict[str, Any]) -> None:
    cutoff = _now() - timedelta(days=KEEP_DAYS)
    data["items"] = {k: v for k, v in data.get("items", {}).items()
                     if (_parse(v.get("last")) or _now()) >= cutoff}
    write_json(SEEN_FILE, data)


def mark_seen(keys: Iterable[str], clicked: bool = False, data: dict[str, Any] | None = None,
              now: datetime | None = None) -> dict[str, Any]:
    """Record that these cards were seen (or clicked). Saves unless `data` is given."""
    own = data is None
    data = load() if own else data
    stamp = (now or _now()).isoformat()
    for key in keys:
        if not key:
            continue
        entry = data["items"].setdefault(key, {"first": stamp, "count": 0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last"] = stamp
        if clicked:
            entry["clicked"] = True
    if own:
        save(data)
    return data


def state(cfg: MyGeekyConfig, key: str, data: dict[str, Any], now: datetime | None = None) -> str:
    """'new' (never seen), 'again' (seen, rest is over), or 'resting'."""
    entry = data["items"].get(key)
    if not entry:
        return "new"
    kind = key.split(":", 1)[0]
    days = rest_days(cfg, kind)
    if days is NEVER:
        return "resting"
    if entry.get("clicked") and kind == "person":
        return "resting"
    if int(entry.get("count", 0)) >= cfg.fresh_ignored_after:     # seen often, never clicked
        days = max(days, cfg.fresh_ignored_days)
    last = _parse(entry.get("last")) or (now or _now())
    return "again" if (now or _now()) - last >= timedelta(days=days) else "resting"


def arrange(cfg: MyGeekyConfig, kind: str, items: list[dict[str, Any]], limit: int | None = None,
            data: dict[str, Any] | None = None, now: datetime | None = None,
            key: Callable[[dict[str, Any]], str] | None = None, keep_seen: bool = False) -> list[dict[str, Any]]:
    """The items to show, each copied with `_fresh` ('new' / 'again' / 'seen') and `_key`.

    New ones first, keeping their own order (their score); then ones whose rest
    is over. Resting ones: hidden for 'hide' kinds (Market sinks them to the
    bottom, the Activity feed keeps its order and just labels them 'seen').
    `keep_seen` puts a 'hide' kind's seen ones at the end instead (the panel shows a
    few, dimmed, so a tab you've read to the end isn't empty)."""
    data = data if data is not None else load()
    key = key or (lambda it: item_key(kind, it))
    labelled = []
    for item in items:
        k = key(item)
        s = state(cfg, k, data, now) if k else "new"
        labelled.append({**item, "_key": k, "_fresh": "seen" if s == "resting" else s})
    new = [i for i in labelled if i["_fresh"] == "new"]
    again = [i for i in labelled if i["_fresh"] == "again"]
    seen = [i for i in labelled if i["_fresh"] == "seen"]
    mode = MODES.get(kind, HIDE)
    shown = labelled if mode == DIM else new + again + seen if (mode == SINK or keep_seen) else new + again
    return shown[:limit] if limit else shown


def count_new(shown: list[dict[str, Any]]) -> int:
    return sum(1 for i in shown if i.get("_fresh") == "new")


def running_low(shown: list[dict[str, Any]], limit: int) -> bool:
    """Fewer than half a list's worth of new things: time to look for more."""
    return count_new(shown) < max(1, limit // 2)


def top_up_due(kind: str, hours: float, data: dict[str, Any] | None = None, now: datetime | None = None) -> bool:
    """At most one background search per `hours` for a kind (GitHub's limits)."""
    data = data if data is not None else load()
    last = _parse(data["meta"].get(f"topup:{kind}"))
    return last is None or (now or _now()) - last >= timedelta(hours=hours)


def note_top_up(kind: str, now: datetime | None = None) -> None:
    data = load()
    data["meta"][f"topup:{kind}"] = (now or _now()).isoformat()
    save(data)
