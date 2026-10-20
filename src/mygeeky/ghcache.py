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

4. **Slow numbers wait a day.** Stars, forks, commit activity, a profile's
   follower counts: a repo or a person asked about less than a day ago is
   answered from here without asking at all (SLOW, `slow_seconds`), so
   switching tabs reads them at once. Everything else is still asked each time.

The answers live in a small SQLite database, `github_cache.sqlite` in the data
folder: one row per answer, written when it changes, so a refresh never rewrites
the whole cache (the JSON file it replaced reached ~400 MB and was rewritten
every few seconds). It is capped at MAX_ENTRIES and MAX_BYTES by dropping what
was used longest ago. It holds only public data that GitHub served, so it is
never synced to anyone's private repository, and deleting it only means the next
refresh asks GitHub for everything again.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ensure_dirs

CACHE_FILE = DATA_DIR / "github_cache.sqlite"
MAX_ENTRIES = 4000            # the oldest-used go first
MAX_BYTES = 60_000_000        # and the answers stay this small together, whatever they weigh
LEGACY_IMPORT_MAX = 30_000_000   # a bigger old JSON cache isn't read in (too slow): it is simply asked again
SAME_RUN_SECONDS = 20.0       # the same URL twice in one refresh is asked once
MISSING_SECONDS = 6 * 3600    # a 404 (deleted account, no beacon) isn't re-asked for a while
SLOW_SECONDS = 24 * 3600      # stars, forks, commit activity, profiles: asked at most once a day
KEEP_DAYS = 14                # how many days of the call tally to keep

# What moves slowly: a repo's own page (stars, forks, language), its year of commit activity and contributors,
# a person's profile (follower counts) and links. The phone keeps the same list (lib/github.ts, SLOW).
SLOW = [re.compile(p) for p in (
    r"^/repos/[^/]+/[^/]+$",
    r"^/repos/[^/]+/[^/]+/stats/commit_activity$",
    r"^/repos/[^/]+/[^/]+/contributors$",
    r"^/users/[^/]+$",
    r"^/users/[^/]+/social_accounts$",
)]
API_ROOT = "https://api.github.com"


def slow_seconds(url: str) -> float:
    """How long an answer for this URL holds without asking again: a day for slow numbers, else 0."""
    path = url[len(API_ROOT):] if url.startswith(API_ROOT) else url
    path = path.split("?")[0].rstrip("/")
    return SLOW_SECONDS if any(p.match(path) for p in SLOW) else 0.0


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


def _busy(exc: BaseException) -> bool:
    """Locked or busy: someone else is writing. Never a reason to call the file damaged."""
    return isinstance(exc, sqlite3.OperationalError) and any(w in str(exc).lower() for w in ("locked", "busy"))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, body TEXT, status INTEGER, etag TEXT, modified TEXT,
                                    at REAL, used REAL, size INTEGER);
CREATE INDEX IF NOT EXISTS answers_used ON answers(used);
CREATE TABLE IF NOT EXISTS calls (day TEXT, what TEXT, n INTEGER, PRIMARY KEY (day, what));
"""


class Store:
    """The cache itself, in SQLite. Rows read this run are kept in memory too (so a refresh asking the same thing
    twice doesn't read the disk twice); writes go straight to their own row.

    Nothing here is precious: if the database can't be opened (a damaged file, a read-only folder), it is set
    aside and a new one started, or the cache simply works in memory for this run."""

    def __init__(self, path=None, max_entries: int = MAX_ENTRIES, save_every: float = 10.0,
                 max_bytes: int = MAX_BYTES) -> None:
        path = Path(path or CACHE_FILE)
        self.path = path.with_suffix(".sqlite") if path.suffix == ".json" else path
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.save_every = save_every       # the read times and the tally are written at most this often
        self._rows: dict[str, Cached] = {}
        self._used: dict[str, float] = {}  # read times not yet written
        self._tally: dict[str, dict[str, int]] = {}   # counts not yet written
        self._saved_at = time.time()
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = None
        self._opened = False

    # ---- the database
    def _conn(self) -> sqlite3.Connection | None:
        with self._lock:                         # two threads asking at once open it once
            if not self._opened:
                self._connect()
            return self._db

    def _connect(self) -> None:
        self._opened = True
        try:
            ensure_dirs()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = self._open_waiting()
        except sqlite3.DatabaseError as exc:
            if _busy(exc):                       # another program holds it for longer: memory only, this run
                self._db = None
            else:
                try:                             # a damaged file: set it aside, start again
                    if self.path.exists():
                        os.replace(self.path, self.path.with_name(self.path.name + f".broken-{int(time.time())}"))
                    self._db = self._open_waiting()
                except (sqlite3.DatabaseError, OSError):
                    self._db = None
        except OSError:
            self._db = None                      # a read-only folder: memory only, this run
        if self._db is not None:
            self._import_legacy()

    def _open_waiting(self) -> sqlite3.Connection:
        """Open it, waiting while another program (the panel, a scheduled refresh) is setting it up."""
        for attempt in range(40):
            try:
                return self._open()
            except sqlite3.OperationalError as exc:
                if not _busy(exc) or attempt == 39:
                    raise
                time.sleep(0.05 + 0.01 * attempt)
        raise sqlite3.OperationalError("database is locked")

    def _open(self) -> sqlite3.Connection:
        new = not self.path.exists()
        db = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False, isolation_level=None)
        try:
            return self._prepare(db, new)
        except BaseException:
            db.close()
            raise

    @staticmethod
    def _prepare(db: sqlite3.Connection, new: bool) -> sqlite3.Connection:
        if new:
            db.execute("PRAGMA auto_vacuum = INCREMENTAL")   # space from pruned rows is given back
        db.execute("PRAGMA journal_mode = WAL")              # the panel and a scheduled refresh can share it
        db.execute("PRAGMA synchronous = NORMAL")
        db.executescript(_SCHEMA)
        db.execute("SELECT count(*) FROM answers").fetchone()
        return db

    def _import_legacy(self) -> None:
        """The JSON cache it replaces: read in once if it's small, then removed (with any half-written copies)."""
        old = self.path.with_suffix(".json")
        leftovers = list(self.path.parent.glob(f".{old.name}.*.tmp"))
        if not old.exists() and not leftovers:
            return
        try:
            if old.exists() and old.stat().st_size <= LEGACY_IMPORT_MAX:
                data = json.loads(old.read_text(encoding="utf-8-sig"))
                rows = (data.get("entries") if isinstance(data, dict) else None) or {}
                with self._lock, self._db:
                    for k, v in rows.items():
                        if isinstance(v, dict):
                            body = json.dumps(v.get("body"))
                            self._db.execute(
                                "INSERT OR IGNORE INTO answers VALUES (?,?,?,?,?,?,?,?)",
                                (k, body, int(v.get("status") or 200), str(v.get("etag") or ""),
                                 str(v.get("modified") or ""), float(v.get("at") or 0), float(v.get("used") or 0),
                                 len(body)))
                    for day, counts in ((data.get("calls") or {}) if isinstance(data, dict) else {}).items():
                        for what, n in (counts or {}).items():
                            self._db.execute("INSERT OR IGNORE INTO calls VALUES (?,?,?)", (day, what, int(n)))
                self._prune()
        except (OSError, ValueError, sqlite3.DatabaseError):
            pass
        for f in [old, *leftovers]:
            try:
                f.unlink()
            except OSError:
                pass

    # ---- writing what isn't written yet
    def maybe_save(self) -> None:
        if time.time() - self._saved_at >= self.save_every:
            self.save()

    def save(self) -> None:
        """Write the read times and the tally, and keep the database within its limits."""
        self._saved_at = time.time()
        db = self._conn()
        if db is None:
            return
        with self._lock:
            used, self._used = self._used, {}
            tally, self._tally = self._tally, {}
            try:
                with db:
                    db.executemany("UPDATE answers SET used = ? WHERE key = ?", [(u, k) for k, u in used.items()])
                    for day, counts in tally.items():
                        for what, n in counts.items():
                            db.execute("INSERT INTO calls VALUES (?,?,?) ON CONFLICT(day, what) DO UPDATE SET "
                                       "n = n + excluded.n", (day, what, n))
                    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - KEEP_DAYS * 86400))
                    db.execute("DELETE FROM calls WHERE day < ?", (cutoff,))
                self._prune()
            except sqlite3.DatabaseError:
                pass

    def _prune(self) -> None:
        """Drop what was read longest ago, until both the count and the size fit."""
        db = self._db
        n, size = db.execute("SELECT count(*), coalesce(sum(size), 0) FROM answers").fetchone()
        if n <= self.max_entries and size <= self.max_bytes:
            return
        with db:
            db.execute("""DELETE FROM answers WHERE key IN (
                            SELECT key FROM (SELECT key, row_number() OVER w AS i, sum(size) OVER w AS total
                                             FROM answers WINDOW w AS (ORDER BY used DESC, key))
                            WHERE i > ? OR (total > ? AND i > 1))""", (self.max_entries, self.max_bytes))
        db.execute("PRAGMA incremental_vacuum")
        self._rows = {k: c for k, c in self._rows.items()
                      if db.execute("SELECT 1 FROM answers WHERE key = ?", (k,)).fetchone()}

    # ---- what a request needs
    def get(self, key: str) -> Cached | None:
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                db = self._conn()
                r = db.execute("SELECT body, status, etag, modified, at, used FROM answers WHERE key = ?",
                               (key,)).fetchone() if db is not None else None
                if r is None:
                    return None
                try:
                    body = json.loads(r[0]) if r[0] is not None else None
                except ValueError:
                    return None
                row = self._rows[key] = Cached(body=body, status=int(r[1]), etag=r[2] or "", modified=r[3] or "",
                                               at=float(r[4] or 0), used=float(r[5] or 0))
            row.used = self._used[key] = time.time()
            return row

    def _write(self, key: str, row: Cached, body_changed: bool = True) -> None:
        db = self._conn()
        if db is None:
            return
        try:
            with self._lock, db:
                if body_changed:
                    body = json.dumps(row.body)
                    db.execute("INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?,?,?)",
                               (key, body, row.status, row.etag, row.modified, row.at, row.used, len(body)))
                else:
                    db.execute("UPDATE answers SET etag = ?, modified = ?, at = ?, used = ? WHERE key = ?",
                               (row.etag, row.modified, row.at, row.used, key))
        except sqlite3.DatabaseError:
            pass

    def put(self, key: str, body: Any, status: int = 200, etag: str = "", modified: str = "") -> Cached:
        now = time.time()
        row = Cached(body=body, status=status, etag=etag, modified=modified, at=now, used=now)
        with self._lock:
            self._rows[key] = row
            self._used.pop(key, None)
        self._write(key, row)
        self.maybe_save()
        return row

    def touch(self, key: str, etag: str = "", modified: str = "") -> Cached | None:
        """GitHub said 304: the answer we hold is current, so keep it and note it was checked now."""
        row = self.get(key)
        if row is None:
            return None
        row.at = row.used = time.time()
        if etag:
            row.etag = etag
        if modified:
            row.modified = modified
        self._write(key, row, body_changed=False)
        self.maybe_save()
        return row

    def forget(self, key: str) -> None:
        with self._lock:
            self._rows.pop(key, None)
            self._used.pop(key, None)
            db = self._conn()
            if db is not None:
                with db:
                    db.execute("DELETE FROM answers WHERE key = ?", (key,))

    # ---- the tally, so the saving can be seen rather than assumed
    def count(self, what: str, n: int = 1) -> None:
        day = time.strftime("%Y-%m-%d")
        with self._lock:
            self._tally.setdefault(day, {})
            self._tally[day][what] = self._tally[day].get(what, 0) + n

    def tally(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        db = self._conn()
        if db is not None:
            for day, what, n in db.execute("SELECT day, what, n FROM calls"):
                out.setdefault(day, {})[what] = int(n)
        with self._lock:
            for day, counts in self._tally.items():
                for what, n in counts.items():
                    out.setdefault(day, {})[what] = out.get(day, {}).get(what, 0) + n
        return {d: out[d] for d in sorted(out, reverse=True)}

    def today(self) -> dict[str, int]:
        return dict(self.tally().get(time.strftime("%Y-%m-%d"), {}))

    def entries(self) -> int:
        db = self._conn()
        if db is None:
            return len(self._rows)
        return int(db.execute("SELECT count(*) FROM answers").fetchone()[0])

    def size(self) -> int:
        """How many bytes the answers take together."""
        db = self._conn()
        return int(db.execute("SELECT coalesce(sum(size), 0) FROM answers").fetchone()[0]) if db is not None else 0

    def clear(self) -> None:
        with self._lock:
            self._rows, self._used = {}, {}
            db = self._conn()
            if db is not None:
                with db:
                    db.execute("DELETE FROM answers")
                db.execute("PRAGMA incremental_vacuum")

    def close(self) -> None:
        self.save()
        with self._lock:
            if self._db is not None:
                self._db.close()
            self._db, self._opened = None, False


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


def _db_path(path) -> str:
    path = Path(path)
    return str(path.with_suffix(".sqlite") if path.suffix == ".json" else path)


def store() -> Store:
    """The cache for the data folder in use right now.

    Keyed by path on purpose: a test (or a second profile) points CACHE_FILE somewhere else, and must
    get its own store rather than another one's answers."""
    key = _db_path(CACHE_FILE)
    st = _stores.get(key)
    if st is None:
        st = _stores[key] = Store(CACHE_FILE)
    return st


def reset(path=None) -> Store:
    """A fresh store, forgetting every one this process had. Tests, and `mygeeky cache clear`."""
    for old in list(_stores.values()):
        try:
            old.close()
        except Exception:  # noqa: BLE001 -- closing a cache must never stop anything
            pass
    _stores.clear()
    st = Store(path or CACHE_FILE)
    _stores[str(st.path)] = st
    return st
