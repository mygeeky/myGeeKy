"""Local persistence: suggestion history, training data, follow snapshots.

Everything here is plain JSON/JSONL under the user's data directory
(see config.py). None of it is a secret -- usernames, public counts, and
derived scores -- but none of it lives inside the project/repo either.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import (
    ACTIVITY_CACHE_FILE,
    CONTRIBUTE_LOG,
    EXCLUDED_FILE,
    FOLLOWING_SNAPSHOT,
    MODEL_HISTORY_LOG,
    SUGGESTIONS_LOG,
    TRAINING_LOG,
    ensure_dirs,
)
from . import files
from .files import write_json


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_dirs()
    files.append_jsonl(path, record)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    # a line cut short by a crash (or a sync merge) is skipped, not fatal for the whole history
    return [r for r in files.read_jsonl(path) if isinstance(r, dict)]


def log_suggestions(records: Iterable[dict[str, Any]]) -> None:
    for r in records:
        append_jsonl(SUGGESTIONS_LOG, r)
    rotate_jsonl(SUGGESTIONS_LOG)


# --------------------------------------------------------------------------- history files don't grow forever
KEEP_DAYS = 120     # what the suggestion and repo histories keep live: nothing reads past POOL_DAYS (90) of them
ROTATE_SLACK_DAYS = 30   # rotate in monthly batches, so the synced file isn't rewritten every day


def rotate_jsonl(path: Path, keep_days: int = KEEP_DAYS, now: datetime | None = None) -> int:
    """Move lines older than `keep_days` out of a history file into compressed monthly archives on this computer
    (`archive/<name>-<YYYY-MM>.jsonl.gz`, kept, not synced), once the oldest line is a month past that. Returns how
    many lines moved. Lines without a readable `timestamp` stay. Both computers trimming the same top lines, or one
    trimming while the other appends, merge cleanly (the .jsonl files merge by union)."""
    path = Path(path)
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=keep_days)).isoformat()
    try:
        with path.open(encoding="utf-8") as fh:
            first = fh.readline()
        oldest = str(json.loads(first).get("timestamp") or "")
    except (OSError, ValueError, AttributeError):
        return 0
    if not oldest or oldest >= (now - timedelta(days=keep_days + ROTATE_SLACK_DAYS)).isoformat():
        return 0
    keep, old = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            stamp = str(json.loads(line).get("timestamp") or "")
        except (ValueError, AttributeError):
            stamp = ""
        if stamp and stamp < cutoff:
            old.setdefault(stamp[:7], []).append(line)
        elif line.strip():
            keep.append(line)
    archive = path.parent / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    for month, lines in old.items():
        gz = archive / f"{path.stem}-{month}.jsonl.gz"
        have = gzip.decompress(gz.read_bytes()).decode("utf-8").splitlines() if gz.exists() else []
        seen = set(have)
        merged = have + [x for x in lines if x not in seen]
        gz.write_bytes(gzip.compress(("\n".join(merged) + "\n").encode("utf-8"), mtime=0))
    files.write_text_atomic(path, "\n".join(keep) + ("\n" if keep else ""))
    return sum(len(v) for v in old.values())


def log_training_example(record: dict[str, Any]) -> None:
    append_jsonl(TRAINING_LOG, record)


def load_training_examples() -> list[dict[str, Any]]:
    return read_jsonl(TRAINING_LOG)


def load_following_snapshot() -> set[str]:
    data = files.read_json(FOLLOWING_SNAPSHOT, [])
    return set(data) if isinstance(data, list) else set()


def save_following_snapshot(usernames: Iterable[str]) -> None:
    ensure_dirs()
    write_json(FOLLOWING_SNAPSHOT, sorted(set(usernames)))


def load_excluded() -> set[str]:
    data = files.read_json(EXCLUDED_FILE, [])     # a damaged file is kept aside, not lost
    return set(data) if isinstance(data, list) else set()


def add_excluded(usernames: Iterable[str]) -> None:
    ensure_dirs()
    current = load_excluded()
    current.update(usernames)
    write_json(EXCLUDED_FILE, sorted(current))


def last_suggestions(limit: int = 15, list_type: str | None = None,
                     exclude: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """The newest `limit` logged suggestions, oldest first.

    `exclude` (lowercase usernames) is applied BEFORE the cut, and each person
    appears once (their newest record) -- otherwise, once everyone in the
    latest run has been clicked or followed, the result is empty even though
    older runs still hold people you haven't seen."""
    records = read_jsonl(SUGGESTIONS_LOG)
    if list_type:
        records = [r for r in records if r.get("list") == list_type]
    if exclude is None:
        return records[-limit:]
    skip = set(exclude)
    picked: list[dict[str, Any]] = []
    for r in reversed(records):
        name = (r.get("username") or "").lower()
        if name in skip:
            continue
        skip.add(name)
        picked.append(r)
        if len(picked) >= limit:
            break
    return picked[::-1]


def last_suggestion_time(list_type: str | None = None) -> datetime | None:
    """When the newest logged suggestion was produced, or None if there are none."""
    records = read_jsonl(SUGGESTIONS_LOG)
    if list_type:
        records = [r for r in records if r.get("list") == list_type]
    for r in reversed(records):
        try:
            ts = datetime.fromisoformat(r["timestamp"])
        except (KeyError, TypeError, ValueError):
            continue
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    return None


def log_model_history(record: dict[str, Any]) -> None:
    append_jsonl(MODEL_HISTORY_LOG, record)


def load_model_history(limit: int = 100) -> list[dict[str, Any]]:
    return read_jsonl(MODEL_HISTORY_LOG)[-limit:]


def load_activity_cache() -> dict[str, Any] | None:
    if not ACTIVITY_CACHE_FILE.exists():
        return None
    try:
        return json.loads(ACTIVITY_CACHE_FILE.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return None


def save_activity_cache(events: list[dict[str, Any]], fetched_at: str,
                        following: Iterable[str] | None = None) -> None:
    ensure_dirs()
    payload: dict[str, Any] = {"fetched_at": fetched_at, "events": events}
    if following is not None:
        payload["following"] = sorted(following)
    write_json(ACTIVITY_CACHE_FILE, payload)


def log_contributions(records: Iterable[dict[str, Any]]) -> None:
    for r in records:
        append_jsonl(CONTRIBUTE_LOG, r)
    rotate_jsonl(CONTRIBUTE_LOG)


POOL_DAYS = 90      # older suggestions are too stale to bring back


def _pool(records: list[dict[str, Any]], key: str, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Each one once (its newest record): newest run first; within a run, the order it
    was saved in (runs are saved best first -- no need to know what a score looks like)."""
    from datetime import timedelta, timezone
    cutoff = (datetime.now(timezone.utc) - timedelta(days=POOL_DAYS)).isoformat()
    skip, picked = {e.lower() for e in exclude}, []
    for index in range(len(records) - 1, -1, -1):  # newest record of each one
        r = records[index]
        name = str(r.get(key) or "").lower()
        if not name or name in skip:
            continue
        stamp = str(r.get("timestamp") or "")
        if stamp and stamp < cutoff:
            continue
        skip.add(name)
        picked.append((index, r))
    runs: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, r in picked:
        runs.setdefault(str(r.get("timestamp") or ""), []).append((index, r))
    ordered = []
    for stamp in sorted(runs, reverse=True):
        ordered += [r for _, r in sorted(runs[stamp], key=lambda pair: pair[0])]
    return ordered


def suggestion_pool(list_type: str, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    """Everyone suggested lately who isn't excluded: what the People tab can rotate through."""
    records = [r for r in read_jsonl(SUGGESTIONS_LOG) if r.get("list") == list_type]
    return _pool(records, "username", exclude)


def contribution_pool() -> list[dict[str, Any]]:
    """Every repo suggested lately (newest run first): what the Repos tab can rotate through."""
    return _pool(read_jsonl(CONTRIBUTE_LOG), "full_name")


def last_contributions(limit: int = 10) -> list[dict[str, Any]]:
    """The most recent `mygeeky contribute` run's results, best first."""
    records = read_jsonl(CONTRIBUTE_LOG)
    if not records:
        return []
    latest = records[-1].get("timestamp")
    return [r for r in records if r.get("timestamp") == latest][:limit]
