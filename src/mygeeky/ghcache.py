"""What GitHub already told us, kept on this computer, so we ask for it at most once.

GitHub's rate limit is **per person**, not per app: your own token gets 5,000
requests an hour, and the phone without a token gets 60. So this is about your
own refreshes staying quick and never running out, not about being polite to
GitHub's servers.

Three things happen here, in order of how much they save:

1. **Conditional requests.** Every answer is stored with its `ETag` (and
   `Last-Modified`). Next time, the request carries `If-None-Match`, and when
   nothing has changed GitHub replies **304 Not Modified** -- which costs
   nothing against the rate limit and no bandwidth. A profile that hasn't
   changed since yesterday is therefore free to re-read. This is why the cache
   never makes anything stale: we still ask, every time.
2. **One ask per run.** Within a few seconds, the same URL asked for twice (the
   same person looked at by three different features) is answered once.
3. **It still works when GitHub doesn't.** If the network fails, or GitHub is
   down, or the limit really is spent, a cached answer is served instead and
   marked `from_cache`, so the panel shows what it knows with an honest "updated
   N hours ago" rather than an empty tab.

Also kept: a small tally per day (how many requests, how many came back 304,
how many were served from the cache), which is what the admin tab shows and the
only way to tell whether any of this is working.

The file is `github_cache.json` in the data folder, capped at MAX_ENTRIES by
dropping what was used longest ago. It holds only public data that GitHub
served, so it is never synced to anyone's private repository.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

CACHE_FILE = DATA_DIR / "github_cache.json"
MAX_ENTRIES = 4000            # a few MB at most; the oldest-used go first
SAME_RUN_SECONDS = 20.0       # the same URL twice in one refresh is asked once
MISSING_SECONDS = 6 * 3600    # a 404 (deleted account, no beacon) isn't re-asked for a while
KEEP_DAYS = 14                # how many days of the call tally to keep


def key_of(url: str, params: dict[str, Any] | None = None) -> str:
    """One entry per URL and query, in a stable order so the same ask hits the same entry."""
    if not params:
        return url
    bits = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] is not None)
    return f"{url}?{bits}" if bits else url


@dataclass
class Cached:
    """What we have for one URL: the answer, and what GitHub said about its freshness."""
    body: Any = None
    status: int = 200
    etag: str = ""
    modified: str = ""
    at: float = 0.0            # when it was stored
    used: float = 0.0          # when it was last read (how entries are pruned)

    @property
    def age(self) -> float:
        return max(0.0, time.time() - self.at)

    def headers(self) -> dict[str, str]:
        """The conditional headers to send, so GitHub can answer 304 instead of resending."""
        out = {}
        if self.etag:
            out["If-None-Match"] = self.etag
        if self.modified:
            out["If-Modified-Since"] = self.modified
        return out


class Store:
    """The cache itself: load once, keep in memory, write when it changes.

    It is deliberately a plain file. Nothing here is precious -- deleting it only
    means the next refresh asks GitHub for everything again."""

    def __init__(self, path=None, max_entries: int = MAX_ENTRIES, save_every: float = 10.0) -> None:
        self.path = path or CACHE_FILE
        self.max_entries = max_entries
        self.save_every = save_every       # written at most this often, so a long refresh isn't all I/O
        self._rows: dict[str, Cached] | None = None
        self._tally: dict[str, dict[str, int]] = {}
        self._dirty = False
        self._saved_at = 0.0

    # ---- reading and writing the file
    def _load(self) -> dict[str, Cached]:
        if self._rows is None:
            data = read_json(self.path, {}) or {}
            rows = data.get("entries") if isinstance(data, dict) else None
            self._rows = {}
            for k, v in (rows or {}).items():
                if isinstance(v, dict):
                    self._rows[k] = Cached(body=v.get("body"), status=int(v.get("status") or 200),
                                           etag=str(v.get("etag") or ""), modified=str(v.get("modified") or ""),
                                           at=float(v.get("at") or 0.0), used=float(v.get("used") or 0.0))
            tally = data.get("calls") if isinstance(data, dict) else None
            self._tally = {d: dict(v) for d, v in (tally or {}).items() if isinstance(v, dict)}
        return self._rows

    def maybe_save(self) -> None:
        """Write now and then, so what GitHub told us survives even if nothing calls done()."""
        if self._dirty and time.time() - self._saved_at >= self.save_every:
            self.save()

    def save(self) -> None:
        if not self._dirty or self._rows is None:
            return
        self._saved_at = time.time()
        rows = self._rows
        if len(rows) > self.max_entries:            # drop what was read longest ago
            keep = sorted(rows.items(), key=lambda kv: kv[1].used, reverse=True)[:self.max_entries]
            rows = dict(keep)
            self._rows = rows
        today = time.strftime("%Y-%m-%d")
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - KEEP_DAYS * 86400))
        self._tally = {d: v for d, v in self._tally.items() if d >= cutoff or d == today}
        ensure_dirs()
        write_json(self.path, {"entries": {k: {"body": c.body, "status": c.status, "etag": c.etag,
                                               "modified": c.modified, "at": c.at, "used": c.used}
                                           for k, c in rows.items()},
                               "calls": self._tally})
        self._dirty = False

    # ---- what a request needs
    def get(self, key: str) -> Cached | None:
        row = self._load().get(key)
        if row is not None:
            row.used = time.time()
            self._dirty = True
        return row

    def put(self, key: str, body: Any, status: int = 200, etag: str = "", modified: str = "") -> Cached:
        now = time.time()
        row = Cached(body=body, status=status, etag=etag, modified=modified, at=now, used=now)
        self._load()[key] = row
        self._dirty = True
        self.maybe_save()
        return row

    def touch(self, key: str, etag: str = "", modified: str = "") -> Cached | None:
        """GitHub said 304: the answer we hold is current, so keep it and note it was checked now."""
        row = self._load().get(key)
        if row is None:
            return None
        row.at = row.used = time.time()
        if etag:
            row.etag = etag
        if modified:
            row.modified = modified
        self._dirty = True
        self.maybe_save()
        return row

    def forget(self, key: str) -> None:
        if self._load().pop(key, None) is not None:
            self._dirty = True

    # ---- the tally, so the saving can be seen rather than assumed
    def count(self, what: str, n: int = 1) -> None:
        day = time.strftime("%Y-%m-%d")
        self._tally.setdefault(day, {})
        self._tally[day][what] = self._tally[day].get(what, 0) + n
        self._dirty = True

    def today(self) -> dict[str, int]:
        self._load()
        return dict(self._tally.get(time.strftime("%Y-%m-%d"), {}))

    def tally(self) -> dict[str, dict[str, int]]:
        self._load()
        return {d: dict(v) for d, v in sorted(self._tally.items(), reverse=True)}

    def entries(self) -> int:
        return len(self._load())

    def clear(self) -> None:
        self._rows = {}
        self._dirty = True
        self.save()


class CachedResponse:
    """A cached answer, shaped like the `requests` response the callers already handle.

    `from_cache` says it didn't come down the wire just now, and `fresh` says GitHub
    confirmed it this moment with a 304 -- which is the difference between "this is
    current" and "this is the best we have while the network is away"."""

    def __init__(self, row: Cached, from_cache: bool = True, fresh: bool = False) -> None:
        self._row = row
        self.status_code = int(row.status)
        self.from_cache = from_cache
        self.fresh = fresh
        self.headers: dict[str, str] = {}
        self.age = row.age

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> Any:
        return self._row.body

    @property
    def text(self) -> str:
        return json.dumps(self._row.body)

    @property
    def content(self) -> bytes:
        return self.text.encode()

    def raise_for_status(self) -> None:
        if not self.ok:
            import requests
            raise requests.HTTPError(f"{self.status_code} (from the cache)", response=None)


@dataclass
class Stats:
    """What one client did: asked, got told nothing changed, or never went out at all."""
    requests: int = 0          # answers that actually travelled (200s and the rest)
    not_modified: int = 0      # 304: free, and the point of the whole file
    from_cache: int = 0        # served without asking (same run, a known 404, or offline)
    searches: int = 0
    offline: int = 0
    by_path: dict[str, int] = field(default_factory=dict)

    @property
    def saved(self) -> int:
        """Calls that would have counted against the limit, and didn't."""
        return self.not_modified + self.from_cache

    def note(self, path: str) -> None:
        head = path.split("?")[0]
        self.by_path[head] = self.by_path.get(head, 0) + 1


_stores: dict[str, Store] = {}


def store() -> Store:
    """The cache for the data folder in use right now.

    Keyed by path on purpose: a test (or a second profile) points CACHE_FILE somewhere else, and must
    get its own store rather than another one's answers."""
    key = str(CACHE_FILE)
    st = _stores.get(key)
    if st is None:
        st = _stores[key] = Store(CACHE_FILE)
    return st


def reset(path=None) -> Store:
    """A fresh store, forgetting every one this process had. Tests, and `mygeeky cache clear`."""
    _stores.clear()
    st = Store(path or CACHE_FILE)
    _stores[str(st.path)] = st
    return st
