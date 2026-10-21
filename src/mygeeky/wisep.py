"""WISEP -- Wisely, a Systematic Statistically adapted system for API calling.

Every call myGeeKy makes to an open database or repository (OpenAlex first; arXiv, bioRxiv, Zenodo, NCBI, Figshare,
Crossref, Hugging Face as they join) goes through here. WISEP decides *whether* a call is worth making now, balancing a
fresh, fast screen against asking aimlessly:

1. **One cache.** Every answer is kept (SQLite, `wisep.sqlite`) with when it was asked, how often it was checked, and how
   often it had changed. The screen is always drawn from it at once.
2. **Statistics, not fixed timers.** Each answer's change rate is estimated from its own history (changes over the hours
   watched, with a prior per kind of answer: a Gamma-Poisson estimate). The chance it changed since it was fetched is
   `1 - exp(-rate * age)`. A query that never moves is asked rarely; one that moves daily, daily.
3. **Learns from use, on this device.** Which pages you open and at what hour (counts that fade with a two-week
   half-life). A page you open often, and soon, is worth a fresh answer; one you never open is asked rarely.
   Worth asking now = chance it changed x how much you care -- compared with a bar that rises as the day's budget is
   spent faster than the day goes by.
4. **Budgets and manners.** A daily budget per source well under its published limits, spaced calls, backing off on
   429/503 (honouring Retry-After), OpenAlex's polite pool (a contact address), and a stale answer served rather than
   nothing when a source is down or the budget is spent.
5. **It tunes itself.** Each kind of answer starts from a prior (KINDS); once this device has watched enough of
   them change (14 days, 5 answers of a kind), the prior becomes what was actually seen (`tuned_prior`), daily.
6. **It takes over from the old timers once proven.** Modules used to keep their own "once a day" timers; after 14
   days of use with the cache saving at least 40% and few failures (`proven_by`), those timers stop gating and
   WISEP decides alone (`timer_due`). Admin → Settings can say Always or Never instead of Auto.
7. **The source's own budget wins.** OpenAlex now gives every network (IP address) without a key a free daily budget
   of 1,000 credits ($0.10), shared by everyone on it: a text search costs 10 credits, a filtered list 1, one record by its id
   nothing. Every answer says what's left (X-RateLimit-Remaining, -Limit, -Reset); WISEP paces itself to those real
   numbers (`server_budget`), counts credits rather than requests (`credit_cost`), keeps a reserve, and rests until
   the reset when they're spent. A free OpenAlex key (Settings) gives the person a budget of their own.
8. **The evening top-up.** Budget left at the end of the day is spent wisely: the answers most worth having fresh
   tomorrow (by the same measure) are refreshed in the evening, using at most half of what is left.

The decision rules (`change_rate`, `p_changed`, `care`, `threshold`, `decide`) are pure and the phone runs the same ones
(lib/wisep.ts; tests/test_wisep.py checks both agree). Nothing here leaves the device: no telemetry, only the requests
themselves. The rules for adding a call are in .claude/skills/mygeeky-wisep/SKILL.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlencode, urlsplit

import requests

from . import config
from .config import LOCAL_DIR, ensure_dirs

DB_FILE = LOCAL_DIR / "wisep.sqlite"      # never in the synced data folder (config.LOCAL_DIR)
CONTACT = "support@mygeeky.org"      # OpenAlex's polite pool: requests with a contact get the faster, steadier lane
UA = {"User-Agent": f"mygeeky (https://mygeeky.org; mailto:{CONTACT})"}
MAX_ENTRIES = 3000
MAX_BYTES = 40_000_000
HALF_LIFE_DAYS = 14.0                # how fast a page's opens fade
TOP_UP_HOUR = 20                     # the evening top-up starts at this local hour
TOP_UP_SHARE = 0.5                   # ... and spends at most this share of what's left
TOP_UP_MAX = 40
TOP_UP_FLOOR = 0.15                  # the same bar as a call on pace: a page you never open isn't topped up
FORCE_ALLOWANCE = 1.2                # a refresh you asked for may go this far over the day's budget
KEEP_DAYS = 30                       # the call tally kept for the admin view
TUNE_MIN_ANSWERS = 5                 # a kind's prior is tuned from this many answers of it ...
TUNE_MIN_HOURS = 14 * 24             # ... watched this long in all
PROVEN_DAYS = 14                     # WISEP takes over from the modules' own timers after this many days of use ...
PROVEN_LOOKS = 100                   # ... this many answers given ...
PROVEN_SAVED = 0.4                   # ... this share of them from the cache ...
PROVEN_FAILED = 0.15                 # ... and failures (or stale answers) under this share of the asks
MODULE_GAP_HOURS = 0.5              # even when WISEP decides alone, a module refreshes at most this often
MODES = ("auto", "on", "off")
RESERVE = 0.05                       # of a source's real budget kept back for what you ask for yourself
KEY_SERVICE, KEY_USER = "mygeeky-openalex", "key"   # a free OpenAlex key, in the system's credential store        # Admin → Settings: WISEP decides alone when proven / always / never

# per source: (daily budget, seconds between calls, hosts) -- the budget is WISEP's own guess, used only until the
# source says what it really allows (OpenAlex's rate-limit headers; server_budget)
SOURCES: dict[str, tuple[int, float, tuple[str, ...]]] = {
    "openalex": (900, 0.12, ("api.openalex.org",)),
    "crossref": (500, 0.2, ("api.crossref.org",)),
    "arxiv": (300, 3.1, ("export.arxiv.org",)),
    "biorxiv": (300, 0.5, ("api.biorxiv.org",)),
    "zenodo": (300, 2.1, ("zenodo.org",)),
    "ncbi": (500, 0.35, ("eutils.ncbi.nlm.nih.gov",)),
    "figshare": (300, 0.3, ("api.figshare.com",)),
    "huggingface": (300, 0.2, ("huggingface.co",)),
}

# kinds of answer: (prior hours between changes, never sooner than, always by) -- all in hours
KINDS: dict[str, tuple[float, float, float]] = {
    "search": (24.0, 1.0, 72.0),       # lists of new or rising work
    "citations": (48.0, 6.0, 168.0),   # who cites what
    "entity": (72.0, 6.0, 336.0),      # an author, a work's counts
    "static": (720.0, 168.0, 2160.0),  # a topic, a paper's metadata
}


# --------------------------------------------------------------------------- the rules (the phone has the same)
def _r(x: float, places: int = 4) -> float:
    """Rounded as JavaScript's Math.round does, so both apps agree."""
    k = 10 ** places
    return math.floor(x * k + 0.5) / k


def change_rate(changes: int, watched_hours: float, prior_hours: float) -> float:
    """Changes per hour: a Gamma-Poisson estimate -- one change in `prior_hours` until its own history says more."""
    return (changes + 1.0) / (max(watched_hours, 0.0) + prior_hours)


def p_changed(rate: float, age_hours: float) -> float:
    """The chance an answer that changes `rate` times an hour has changed since it was fetched `age_hours` ago."""
    return 1.0 - math.exp(-rate * max(age_hours, 0.0))


def care(opens: list[float], hour: int, most: float) -> float:
    """How much you care about a page now (0.1..1): how often you open it against your most-opened page, and whether
    your opens of it fall in the next three hours. A page never seen yet: 0.5 (unknown, not unwanted)."""
    total = 0.0
    for v in opens:                 # added one by one, as JavaScript does (Python's sum() adds more exactly)
        total += v
    if most <= 0:
        return 0.5
    if total <= 0:
        return 0.1
    soon = 0.0
    for i in range(3):
        soon += opens[(hour + i) % 24]
    soon /= total
    return _r(0.1 + 0.9 * min(1.0, total / most) * (0.5 + 0.5 * min(1.0, soon / 0.125)))


def threshold(used: int, budget: int, day_frac: float) -> float:
    """The bar a call's worth must reach: low while spending is on pace for the day, rising as it runs ahead."""
    if used >= budget:
        return math.inf
    pace = used / max(1.0, budget * max(day_frac, 0.02))
    return _r(0.15 * (1.0 + 3.0 * max(0.0, pace - 0.5)))


SEARCH_CREDITS = 10             # OpenAlex: a text search costs ten credits (measured 2026-10-21, its own headers)


def credit_cost(source: str, url: str) -> int:
    """What an ask costs against the source's budget. OpenAlex (its X-RateLimit-Credits-Used header, measured): a
    text search (`search=`, or a `*.search:` filter) costs SEARCH_CREDITS, a filtered list one credit, and one record
    by its id (/works/W…, /authors/A…, /works/doi:…) nothing; other sources count each ask as one."""
    if source != "openalex":
        return 1
    parts = urlsplit(url)
    path, query = unquote(parts.path), unquote(parts.query)
    if re.search(r"(^|&)search=|\.search:", query):
        return SEARCH_CREDITS
    if any(k in query for k in ("filter=", "sort=", "group_by=", "sample=")):
        return 1
    one = path.count("/") >= 2 and not path.endswith("/") and path.split("/")[1] in (
        "works", "authors", "sources", "institutions", "topics", "concepts", "funders", "publishers")
    return 0 if one else 1


def server_budget(limit: int, remaining: int, reset_seconds: float, used_here: int, guess: int,
                  day_frac_here: float) -> tuple[int, int, float]:
    """(used, budget, day_frac) to decide with: the source's own numbers when it gave them (`limit` > 0) -- everyone on
    the network counts, a reserve is kept back, and the day is the source's day (it resets in `reset_seconds`) --
    else this device's count against WISEP's guess."""
    if limit <= 0:
        return used_here, guess, day_frac_here
    budget = max(1, int(limit * (1 - RESERVE)))
    used = max(0, limit - max(remaining, 0))
    frac = min(1.0, max(0.0, 1 - reset_seconds / 86400))
    return used, budget, _r(frac)


def tuned_prior(changes: int, hours: float, answers: int, kind: str) -> float | None:
    """A kind's prior hours between changes, from what this device watched (`changes` over `hours`, pooled over
    `answers` of that kind) -- or None while there's too little to go on. Kept within the kind's limits."""
    default, least, most = KINDS.get(kind, KINDS["entity"])
    if answers < TUNE_MIN_ANSWERS or hours < TUNE_MIN_HOURS:
        return None
    return _r(min(max((hours + default) / (changes + 1.0), least), 4 * most), 2)


def proven_by(days: list[dict[str, Any]]) -> dict[str, Any]:
    """Has WISEP earned the right to decide alone? From the daily tallies (asked, saved, stale, failed per day):
    {"proven", "days", "looks", "saved", "failed"} -- the numbers shown in Admin either way."""
    used = sorted({d["day"] for d in days if (d.get("asked") or 0) + (d.get("saved") or 0)})
    asked = sum(d.get("asked") or 0 for d in days)
    saved = sum(d.get("saved") or 0 for d in days)
    bad = sum((d.get("failed") or 0) + (d.get("stale") or 0) for d in days)
    looks = asked + saved
    share = _r(saved / looks, 3) if looks else 0.0
    failed = _r(bad / asked, 3) if asked else 0.0
    return {"proven": len(used) >= PROVEN_DAYS and looks >= PROVEN_LOOKS and share >= PROVEN_SAVED
            and failed < PROVEN_FAILED, "days": len(used), "looks": looks, "saved": share, "failed": failed}


def decide(age_hours: float | None, kind: str, changes: int, watched_hours: float, care_now: float, used: int,
           budget: int, day_frac: float, forced: bool = False, paused: bool = False,
           prior_hours: float | None = None) -> dict[str, Any]:
    """{"action": "fetch" | "cache" | "none", "why": ..., "worth", "bar"}. `age_hours` None: nothing cached yet.
    `prior_hours`: the kind's tuned prior, when this device has one."""
    prior, least, most = KINDS.get(kind, KINDS["entity"])
    prior = prior_hours or prior
    if age_hours is None:
        if paused or used >= budget * FORCE_ALLOWANCE:
            return {"action": "none", "why": "nothing kept, and the source is resting", "worth": 0.0, "bar": 0.0}
        return {"action": "fetch", "why": "nothing kept yet", "worth": 1.0, "bar": 0.0}
    if paused:
        return {"action": "cache", "why": "the source asked us to wait", "worth": 0.0, "bar": 0.0}
    if age_hours < least:
        return {"action": "cache", "why": "asked moments ago", "worth": 0.0, "bar": 0.0}
    if forced:
        ok = used < budget * FORCE_ALLOWANCE
        return {"action": "fetch" if ok else "cache", "why": "you asked" if ok else "you asked, but the day's budget is spent",
                "worth": 1.0, "bar": 0.0}
    if age_hours >= most:
        ok = used < budget
        return {"action": "fetch" if ok else "cache", "why": "too old to trust", "worth": 1.0, "bar": 0.0}
    worth = _r(p_changed(change_rate(changes, watched_hours, prior), age_hours) * care_now)
    bar = threshold(used, budget, day_frac)
    if worth >= bar:
        return {"action": "fetch", "why": "likely changed, and you'll look", "worth": worth, "bar": _r(bar) if bar != math.inf else bar}
    return {"action": "cache", "why": "probably unchanged, or not wanted now", "worth": worth,
            "bar": _r(bar) if bar != math.inf else bar}


def kind_of(source: str, url: str) -> str:
    """The kind of answer a URL gives (KINDS), from its shape."""
    path = unquote(urlsplit(url).path)
    query = unquote(urlsplit(url).query)
    if source == "openalex":
        if path.startswith("/works") and "cites:" in query:
            return "citations"
        if path.startswith("/topics") or "/doi:" in path or path.startswith("/works/https://doi.org"):
            return "static"
        if path.startswith("/authors") and "search=" not in query:
            return "entity"
        return "search"
    return "search"


def source_of(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower()
    for name, (_, _, hosts) in SOURCES.items():
        if host in hosts:
            return name
    return None


# --------------------------------------------------------------------------- the store
class Store:
    """The answers, the day's tally and what you open -- one small SQLite database, safe across threads."""

    def __init__(self, path=None) -> None:
        self.path = str(path or DB_FILE)
        self.lock = threading.Lock()
        self.last_call: dict[str, float] = {}
        self.paused_until: dict[str, float] = {}
        if self.path != ":memory:":
            ensure_dirs()
            if Path(self.path).parent == config.LOCAL_DIR:    # moved once from the data folder older versions used
                config.local_db(Path(self.path).name)
        self.db = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL") if self.path != ":memory:" else None
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, source TEXT, kind TEXT, url TEXT, body BLOB,
              digest TEXT, fetched REAL, first REAL, checks INTEGER, changes INTEGER, watched REAL, used REAL, page TEXT,
              size INTEGER);
            CREATE TABLE IF NOT EXISTS calls (day TEXT, source TEXT, asked INTEGER, saved INTEGER, stale INTEGER,
              failed INTEGER, topup INTEGER, PRIMARY KEY (day, source));
            CREATE TABLE IF NOT EXISTS opens (page TEXT, hour INTEGER, n REAL, at REAL, PRIMARY KEY (page, hour));
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        """)
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(calls)").fetchall()}
        if "credits" not in cols:                   # a file from before credits were counted
            self.db.execute("ALTER TABLE calls ADD COLUMN credits INTEGER DEFAULT 0")
        self.db.commit()

    # ---- the answers
    def get(self, key: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute("SELECT key, source, kind, url, body, digest, fetched, first, checks, changes, watched, "
                                  "page FROM answers WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        names = ("key", "source", "kind", "url", "body", "digest", "fetched", "first", "checks", "changes", "watched", "page")
        return dict(zip(names, row))

    def put(self, key: str, source: str, kind: str, url: str, body: bytes, page: str, now: float) -> bool:
        """Keep a fresh answer; True if it differs from the one kept before (its history learns from that)."""
        digest = hashlib.sha1(body).hexdigest()
        old = self.get(key)
        changed = bool(old) and old["digest"] != digest
        watched = (old["watched"] + max(0.0, (now - old["fetched"]) / 3600)) if old else 0.0
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO answers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, source, kind, url, body, digest, now, old["first"] if old else now, (old["checks"] + 1) if old else 1,
                 (old["changes"] + (1 if changed else 0)) if old else 0, watched, now, page or (old or {}).get("page", ""),
                 len(body)))
            self.db.commit()
        self._trim()
        return changed

    def touch(self, key: str, now: float) -> None:
        with self.lock:
            self.db.execute("UPDATE answers SET used=? WHERE key=?", (now, key))
            self.db.commit()

    def _trim(self) -> None:
        with self.lock:
            n, size = self.db.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM answers").fetchone()
            if n <= MAX_ENTRIES and size <= MAX_BYTES:
                return
            for key, s in self.db.execute("SELECT key, size FROM answers ORDER BY used ASC").fetchall():
                if n <= MAX_ENTRIES * 0.9 and size <= MAX_BYTES * 0.9:
                    break
                self.db.execute("DELETE FROM answers WHERE key=?", (key,))
                n, size = n - 1, size - (s or 0)
            self.db.commit()

    # ---- the day's tally
    def count(self, source: str, field: str, day: str, n: int = 1) -> None:
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO calls (day, source, asked, saved, stale, failed, topup, credits) "
                            "VALUES (?,?,0,0,0,0,0,0)", (day, source))
            self.db.execute(f"UPDATE calls SET {field}={field}+? WHERE day=? AND source=?", (n, day, source))
            self.db.commit()

    def used(self, source: str, day: str) -> int:
        """Credits spent here today (for OpenAlex, searches only; one record by id is free)."""
        with self.lock:
            row = self.db.execute("SELECT credits FROM calls WHERE day=? AND source=?", (day, source)).fetchone()
        return int(row[0] or 0) if row else 0

    def tally(self, days: int = 7) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.db.execute("SELECT day, source, asked, saved, stale, failed, topup FROM calls ORDER BY day DESC, "
                                   "source").fetchall()
        keep = sorted({r[0] for r in rows}, reverse=True)[:days]
        names = ("day", "source", "asked", "saved", "stale", "failed", "topup")
        return [dict(zip(names, r)) for r in rows if r[0] in keep]

    # ---- small settings and what was learned (tuned priors, the mode)
    def meta(self, key: str, default: Any = None) -> Any:
        with self.lock:
            row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        try:
            return json.loads(row[0]) if row else default
        except ValueError:
            return default

    def set_meta(self, key: str, value: Any) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, json.dumps(value)))
            self.db.commit()

    def pooled(self) -> dict[str, tuple[int, float, int]]:
        """Per kind: (changes, hours watched, answers) over the answers checked at least three times."""
        with self.lock:
            rows = self.db.execute("SELECT kind, SUM(changes), SUM(watched), COUNT(*) FROM answers WHERE checks >= 3 "
                                   "GROUP BY kind").fetchall()
        return {k: (int(c or 0), float(w or 0.0), int(n)) for k, c, w, n in rows}

    # ---- what you open
    def opened(self, page: str, now: float, hour: int) -> None:
        with self.lock:
            row = self.db.execute("SELECT n, at FROM opens WHERE page=? AND hour=?", (page, hour)).fetchone()
            n = (_fade(row[0], now - row[1]) if row else 0.0) + 1.0
            self.db.execute("INSERT OR REPLACE INTO opens VALUES (?,?,?,?)", (page, hour, n, now))
            self.db.commit()

    def opens(self, now: float) -> dict[str, list[float]]:
        with self.lock:
            rows = self.db.execute("SELECT page, hour, n, at FROM opens").fetchall()
        out: dict[str, list[float]] = {}
        for page, hour, n, at in rows:
            out.setdefault(page, [0.0] * 24)[int(hour) % 24] += _fade(n, now - at)
        return out


def _fade(n: float, seconds: float) -> float:
    return n * 0.5 ** (max(seconds, 0.0) / 86400 / HALF_LIFE_DAYS)


_store: Store | None = None
_store_lock = threading.Lock()


def store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            _store = Store()
        return _store


def reset(path=None) -> Store:
    """A fresh store (tests use ':memory:' or a temporary file)."""
    global _store
    with _store_lock:
        _store = Store(path)
        return _store


# --------------------------------------------------------------------------- deciding, asking, answering
def _day(now: float) -> str:
    return datetime.fromtimestamp(now).strftime("%Y-%m-%d")


def _day_frac(now: float) -> float:
    t = datetime.fromtimestamp(now)
    return (t.hour * 3600 + t.minute * 60 + t.second) / 86400


# what you open, as WISEP names it: the navigation's page ids (they differ between the apps) -> the page the answers
# are kept under (the `page` modules ask with). The phone has the same map (lib/wisep.ts PAGES).
PAGES = {"model:cited": "you:cited", "you:cited": "you:cited", "model:model": "you:model", "you:model": "you:model",
         "market:research": "world:papers", "papers": "world:papers", "market:repos": "repos:rising",
         "repos:rising": "repos:rising", "grow:wins": "grow:wins", "grow:paths": "grow:paths",
         "grow:data:new": "grow:data:new", "you:month": "you:model", "model:month": "you:model",
         "researchers:new": "circle:researchers", "researchers:following": "circle:researchers",
         "researchers:suggested": "circle:researchers", "researchers:network": "circle:researchers"}


def canonical(page: str) -> str:
    """A navigation page id as WISEP keeps it (Admin's parts are all one page)."""
    if page.startswith("admin:") or page.startswith("you:admin"):
        return "you:admin"
    return PAGES.get(page, page)


def tune(now: float | None = None, force: bool = False) -> dict[str, float]:
    """Retune each kind's prior from what this device has watched, at most once a day. Returns the priors in use."""
    now = now or time.time()
    st = store()
    kept = st.meta("priors", {}) or {}
    if not force and kept.get("_day") == _day(now):
        return {k: v for k, v in kept.items() if not k.startswith("_")}
    pooled = st.pooled()
    priors = {k: p for k in KINDS if (p := tuned_prior(*pooled.get(k, (0, 0.0, 0)), k)) is not None}
    st.set_meta("priors", {**priors, "_day": _day(now)})
    return priors


def priors() -> dict[str, float]:
    kept = store().meta("priors", {}) or {}
    return {k: v for k, v in kept.items() if not k.startswith("_")}


def mode() -> str:
    m = store().meta("mode", "auto")
    return m if m in MODES else "auto"


def set_mode(m: str) -> str:
    store().set_meta("mode", m if m in MODES else "auto")
    return mode()


def forget_learned() -> None:
    """Forget what WISEP learned about you: the pages you open (and when) and the tuned priors. The answers it kept
    are public data and stay; the call tally stays too (it's how "proven" is judged)."""
    st = store()
    with st.lock:
        st.db.execute("DELETE FROM opens")
        st.db.execute("DELETE FROM meta WHERE key='priors'")
        st.db.commit()


def proven(now: float | None = None) -> dict[str, Any]:
    """Whether WISEP decides alone now, and why: Admin's mode, else proven_by on the last month's tallies."""
    m = mode()
    p = proven_by(store().tally(KEEP_DAYS))
    return {**p, "mode": m, "alone": m == "on" or (m == "auto" and p["proven"])}


def timer_due(own_due: bool, age_hours: float | None = None) -> bool:
    """A module's own "is it time?" -- unless WISEP has taken over: then a refresh may run every half hour (`age_hours`
    since the module's last one) and WISEP decides which answers are worth asking for."""
    if own_due:
        return True
    try:
        return proven()["alone"] and (age_hours is None or age_hours >= MODULE_GAP_HOURS)
    except Exception:
        return False


def care_for(page: str, now: float | None = None) -> float:
    now = now or time.time()
    opens = store().opens(now)
    most = max((sum(v) for v in opens.values()), default=0.0)
    return care(opens.get(page, [0.0] * 24), datetime.fromtimestamp(now).hour, most)


def opened(page: str, now: float | None = None) -> None:
    """You opened a page (a tab, a part): what WISEP learns your day from."""
    if page:
        now = now or time.time()
        store().opened(canonical(page), now, datetime.fromtimestamp(now).hour)


def get_key() -> str | None:
    try:
        import keyring
        return keyring.get_password(KEY_SERVICE, KEY_USER) or None
    except Exception:
        return None


def set_key(key: str) -> bool:
    key = (key or "").strip()
    if not (8 <= len(key) <= 200) or any(c.isspace() for c in key):
        return False
    import keyring
    keyring.set_password(KEY_SERVICE, KEY_USER, key)
    return True


def forget_key() -> None:
    try:
        import keyring
        keyring.delete_password(KEY_SERVICE, KEY_USER)
    except Exception:
        pass


def request_key(email: str, session: requests.Session | None = None) -> dict[str, Any]:
    """Ask OpenAlex for a free key for this person (only when they ask): OpenAlex emails them a link, and the key works
    once they click it. {"ok", "key"?, "message"}. The address goes to OpenAlex only."""
    email = (email or "").strip()
    if "@" not in email or " " in email or len(email) > 200:
        return {"ok": False, "message": "That doesn't look like an email address."}
    try:
        r = (session or requests).post("https://api.openalex.org/api-keys", json={"email": email}, headers=UA, timeout=30)
        data = r.json() if r.content else {}
    except Exception as exc:
        return {"ok": False, "message": f"OpenAlex didn't answer ({type(exc).__name__}). Try again later."}
    key = next((str(v) for k, v in (data.items() if isinstance(data, dict) else []) if k in ("key", "api_key") and v), "")
    if r.status_code >= 400:
        return {"ok": False, "message": str((data or {}).get("message") or f"OpenAlex said {r.status_code}.")[:300]}
    if key:
        set_key(key)
    return {"ok": True, "key": bool(key), "message": "Check your email and click OpenAlex's link: the key works after "
            "that." + ("" if key else " Then paste the key here.")}


def _note_server(source: str, resp: requests.Response, now: float) -> None:
    """Keep what the source says is left of its budget (OpenAlex's rate-limit headers)."""
    h = resp.headers
    try:
        limit, remaining = int(h.get("X-RateLimit-Limit") or 0), int(h.get("X-RateLimit-Remaining") or 0)
        reset = float(h.get("X-RateLimit-Reset") or 0)
    except (TypeError, ValueError):
        return
    if limit > 0:
        store().set_meta(f"server:{source}", {"limit": limit, "remaining": remaining, "reset_at": now + reset,
                                              "key": bool(get_key())})


def server_of(source: str, now: float) -> dict[str, Any] | None:
    """What the source last said is left of its budget, while that day lasts."""
    s = store().meta(f"server:{source}")
    return s if isinstance(s, dict) and s.get("reset_at", 0) > now else None


def key_of(url: str, params: dict[str, Any] | None = None) -> str:
    q = urlencode(sorted((k, str(v)) for k, v in (params or {}).items() if k != "mailto"))
    return f"{url}?{q}" if q else url


def _response(url: str, body: bytes, status: int = 200, note: str = "") -> requests.Response:
    r = requests.Response()
    r.status_code, r._content, r.url, r.encoding = status, body, url, "utf-8"
    r.headers["Content-Type"] = "application/json"
    if note:
        r.headers["X-Wisep"] = note
    return r


def _pause(source: str, resp: requests.Response | None, st: Store, now: float) -> None:
    """Rest a source: as long as it asks (Retry-After: OpenAlex says until its budget resets), doubling up to an hour
    for one that just says it's busy."""
    if resp is not None and resp.status_code == 429:
        try:
            wait = float(resp.headers.get("Retry-After") or 0)
        except (TypeError, ValueError):
            wait = 0
        if wait > 0:
            st.paused_until[source] = now + min(wait, 86400.0)
            return
    wait = 60.0
    try:
        wait = float((resp.headers.get("Retry-After") if resp is not None else None) or wait)
    except (TypeError, ValueError):
        pass
    before = st.paused_until.get(source, 0.0)
    st.paused_until[source] = now + min(3600.0, max(wait, (before - now) * 2 if before > now else wait))


def _space(source: str, st: Store) -> None:
    gap = SOURCES[source][1]
    last = st.last_call.get(source, 0.0)
    wait = last + gap - time.time()
    if wait > 0:
        time.sleep(min(wait, 5.0))
    st.last_call[source] = time.time()


def fetch_raw(url: str, params: dict[str, Any] | None, headers: dict[str, str] | None, timeout: float,
              base: requests.Session | None = None) -> requests.Response:
    params = dict(params or {})
    extra: dict[str, str] = {}
    if source_of(url) == "openalex":
        params.setdefault("mailto", CONTACT)
        key = get_key()
        if key:                                     # the person's own free key: their own budget, not the network's
            extra["Authorization"] = f"Bearer {key}"
    sess = base or requests.Session()
    asked = {"params": params, "headers": {**UA, **(headers or {}), **extra}, "timeout": timeout}
    if isinstance(sess, Session):                   # WISEP's own session: past its gate, or it would ask itself
        return requests.Session.request(sess, "GET", url, **asked)
    return sess.request("GET", url, **asked)


def get(url: str, params: dict[str, Any] | None = None, page: str = "", kind: str | None = None, force: bool = False,
        headers: dict[str, str] | None = None, timeout: float = 30.0, now: float | None = None,
        base: requests.Session | None = None) -> requests.Response:
    """A GET through WISEP: the kept answer when it is good enough, a fresh one when it is worth it."""
    source = source_of(url)
    if source is None:                              # not a source WISEP manages: straight through
        sess = base or requests.Session()
        if isinstance(sess, Session):
            return requests.Session.request(sess, "GET", url, params=params, headers=headers, timeout=timeout)
        return sess.request("GET", url, params=params, headers=headers, timeout=timeout)
    now = now or time.time()
    st, day = store(), _day(now)
    key = key_of(url, params)
    kind = kind or kind_of(source, key)
    kept = st.get(key)
    age = (now - kept["fetched"]) / 3600 if kept else None
    cost = credit_cost(source, key)
    srv = server_of(source, now) or {}
    used, budget, frac = server_budget(int(srv.get("limit") or 0), int(srv.get("remaining") or 0),
                                       float(srv.get("reset_at", now)) - now, st.used(source, day), SOURCES[source][0],
                                       _day_frac(now))
    if cost == 0:                                   # a free record by id: only the spacing and the kept answer matter
        used, budget = 0, max(budget, 1)
    resting = st.paused_until.get(source, 0.0) > now or (cost > 0 and srv and int(srv.get("remaining") or 0) <= 0)
    d = decide(age, kind, kept["changes"] if kept else 0, kept["watched"] if kept else 0.0, care_for(page, now),
               used, budget, frac, force, bool(resting), priors().get(kind))
    if d["action"] == "cache":
        st.count(source, "saved", day)
        st.touch(key, now)
        return _response(key, kept["body"], note=f"cache:{d['why']}")
    if d["action"] == "none":
        st.count(source, "failed", day)
        return _response(key, b"{}", 503, "resting")
    _space(source, st)
    st.count(source, "asked", day)
    if cost:
        st.count(source, "credits", day, cost)
    try:
        resp = fetch_raw(url, params, headers, timeout, base)
    except requests.RequestException:
        if kept:
            st.count(source, "stale", day)
            return _response(key, kept["body"], note="stale:offline")
        st.count(source, "failed", day)
        raise
    _note_server(source, resp, now)
    if resp.status_code in (429, 503):
        _pause(source, resp, st, now)
        if kept:
            st.count(source, "stale", day)
            return _response(key, kept["body"], note="stale:busy")
        return resp
    if resp.status_code == 200:
        st.put(key, source, kind, url + ("?" + urlencode(sorted((k, str(v)) for k, v in (params or {}).items()))
                                         if params else ""), resp.content, page, now)
    return resp


class Session(requests.Session):
    """A drop-in requests.Session: GETs to the sources WISEP manages go through it; anything else goes straight out."""

    def __init__(self, page: str = "", force: bool = False) -> None:
        super().__init__()
        self.page, self.force = page, force

    def request(self, method, url, params=None, headers=None, timeout=None, **kw):  # noqa: D401
        if str(method).upper() == "GET" and source_of(str(url)) and not kw.get("stream") and not kw.get("data"):
            return get(str(url), params, self.page, None, self.force, headers, timeout or 30.0, base=self)
        return super().request(method, url, params=params, headers=headers, timeout=timeout, **kw)


def session(page: str = "", force: bool = False) -> Session:
    """The session every module asks with: `page` names what the answers are for (what you open), `force` is a
    refresh you asked for."""
    return Session(page, force)


# --------------------------------------------------------------------------- the evening top-up
def top_up(now: float | None = None, limit: int = TOP_UP_MAX, base: requests.Session | None = None) -> dict[str, int]:
    """Budget left at the end of the day, spent on the answers most worth having fresh tomorrow."""
    now = now or time.time()
    tune(now)                                       # the hourly look is also when the priors are retuned (daily)
    if datetime.fromtimestamp(now).hour < TOP_UP_HOUR:
        return {}
    st, day = store(), _day(now)
    opens = st.opens(now)
    most = max((sum(v) for v in opens.values()), default=0.0)
    tomorrow = (datetime.fromtimestamp(now).hour + 12) % 24          # care about the morning, not this minute
    with st.lock:
        rows = st.db.execute("SELECT key, source, kind, url, fetched, changes, watched, page FROM answers").fetchall()
    ranked = []
    for key, source, kind, url, fetched, changes, watched, page in rows:
        if source not in SOURCES or st.paused_until.get(source, 0.0) > now:
            continue
        prior, least, _ = KINDS.get(kind, KINDS["entity"])
        prior = priors().get(kind) or prior
        age = (now - fetched) / 3600
        if age < least:
            continue
        worth = p_changed(change_rate(changes, watched, prior), age + 10) * care(opens.get(page, [0.0] * 24), tomorrow, most)
        ranked.append((worth, key, source, url, page, kind))
    ranked.sort(reverse=True)
    spent: dict[str, int] = {}
    for worth, key, source, url, page, kind in ranked:
        left = SOURCES[source][0] - st.used(source, day)
        if worth < TOP_UP_FLOOR or spent.get(source, 0) >= int(left * TOP_UP_SHARE) or sum(spent.values()) >= limit:
            continue
        srv = server_of(source, now)
        if credit_cost(source, url) and srv and int(srv.get("remaining") or 0) <= int(srv.get("limit", 0) * RESERVE * 2):
            continue                                # the network's own budget is nearly spent: leave it for the day
        _space(source, st)
        st.count(source, "asked", day)
        st.count(source, "topup", day)
        if credit_cost(source, url):
            st.count(source, "credits", day, credit_cost(source, url))
        try:
            resp = fetch_raw(url, None, None, 30.0, base)
        except requests.RequestException:
            continue
        _note_server(source, resp, now)
        if resp.status_code in (429, 503):
            _pause(source, resp, st, now)
            continue
        if resp.status_code == 200:
            st.put(key, source, kind, url, resp.content, page, now)
            spent[source] = spent.get(source, 0) + 1
    return spent


# --------------------------------------------------------------------------- what the admin view shows
def stats(now: float | None = None) -> dict[str, Any]:
    now = now or time.time()
    st, day = store(), _day(now)
    tally = st.tally()
    today = [t for t in tally if t["day"] == day]
    opens = st.opens(now)
    pages = sorted(((p, sum(v)) for p, v in opens.items()), key=lambda kv: -kv[1])[:8]
    with st.lock:
        n, size = st.db.execute("SELECT COUNT(*), COALESCE(SUM(size), 0) FROM answers").fetchone()
    asked = sum(t["asked"] for t in today)
    saved = sum(t["saved"] for t in today)
    try:                                            # GitHub keeps its own cache (ghcache.py): shown beside WISEP's sources
        from . import ghcache
        g = ghcache.store().today()
        github = {"asked": int(g.get("requests") or 0), "saved": int(g.get("not_modified") or 0) + int(g.get("from_cache") or 0)}
    except Exception:
        github = {"asked": 0, "saved": 0}
    return {"today": {t["source"]: {**t, "budget": SOURCES.get(t["source"], (0,))[0]} for t in today}, "github": github,
            "priors": priors(), "proven": proven(now), "key": bool(get_key()),
            "server": {s: {"limit": v["limit"], "remaining": v["remaining"], "reset_in": int(v["reset_at"] - now)}
                       for s in SOURCES if (v := server_of(s, now))},
            "asked": asked, "saved": saved, "share_saved": _r(saved / (asked + saved), 3) if asked + saved else 0.0,
            "pages": [{"page": p, "opens": _r(v, 2)} for p, v in pages], "answers": n, "bytes": size,
            "resting": {s: int(u - now) for s, u in st.paused_until.items() if u > now}, "week": tally}


def explain(url: str, params: dict[str, Any] | None = None, page: str = "", now: float | None = None) -> dict[str, Any]:
    """Why WISEP would (or wouldn't) ask for this right now: the numbers behind the decision."""
    now = now or time.time()
    source = source_of(url) or ""
    key = key_of(url, params)
    kept = store().get(key)
    kind = kind_of(source, key) if source else "search"
    age = (now - kept["fetched"]) / 3600 if kept else None
    d = decide(age, kind, kept["changes"] if kept else 0, kept["watched"] if kept else 0.0, care_for(page, now),
               store().used(source, _day(now)) if source else 0, SOURCES.get(source, (1,))[0], _day_frac(now))
    return {**d, "kind": kind, "age_hours": _r(age, 2) if age is not None else None,
            "changes": kept["changes"] if kept else 0, "checks": kept["checks"] if kept else 0}


# --------------------------------------------------------------------------- the evaluation (docs/WISEP.md)
def simulate(policy: str, seed: int = 1, days: int = 30) -> dict[str, float]:
    """One person over a month: 20 answers, each changing at its own rate (some daily, some monthly), and pages opened
    on a daily rhythm (two often, the rest rarely). Fixed timers ask each answer every 6 hours, whether or not anyone
    looks; WISEP asks when it decides to. Measured: calls, and how stale what was shown on screen was (the share of
    looks that showed an answer older than its last real change)."""
    import random
    rng = random.Random(seed)
    reset(":memory:")
    rates = [rng.choice([1 / 12, 1 / 24, 1 / 72, 1 / 240, 1 / 720]) for _ in range(20)]   # changes per hour
    pages = [f"p{i % 5}" for i in range(20)]
    looks_per_day = {"p0": 6, "p1": 3, "p2": 0.5, "p3": 0.2, "p4": 0.05}
    version = [0] * 20
    shown_version = [-1] * 20
    fetched_at = [-1e9] * 20
    calls = stale = looks = 0
    t0 = datetime(2026, 10, 20, 0, 0).timestamp()
    for hour in range(days * 24):
        now = t0 + hour * 3600
        for i, rate in enumerate(rates):                     # the world changes
            if rng.random() < rate:
                version[i] += 1
        for page, per_day in looks_per_day.items():          # the person looks, mostly in the day
            h = datetime.fromtimestamp(now).hour
            if 8 <= h <= 22 and rng.random() < per_day / 15:
                opened(page, now)
                for i in [i for i, p in enumerate(pages) if p == page]:
                    looks += 1
                    if policy == "timers":
                        if now - fetched_at[i] >= 6 * 3600:
                            calls += 1
                            fetched_at[i], shown_version[i] = now, version[i]
                    else:
                        st = store()
                        key = f"k{i}"
                        kept = st.get(key)
                        age = (now - kept["fetched"]) / 3600 if kept else None
                        d = decide(age, "search", kept["changes"] if kept else 0, kept["watched"] if kept else 0.0,
                                         care_for(page, now), st.used("openalex", _day(now)), 1500,
                                         _day_frac(now))
                        if d["action"] == "fetch":
                            calls += 1
                            st.count("openalex", "asked", _day(now))
                            st.put(key, "openalex", "search", key, str(version[i]).encode(), page, now)
                            shown_version[i] = version[i]
                    stale += shown_version[i] != version[i]
        if policy == "timers":                               # fixed timers also refresh in the background
            for i in range(20):
                if now - fetched_at[i] >= 6 * 3600:
                    calls += 1
                    fetched_at[i], shown_version[i] = now, version[i]
    return {"calls": calls, "stale_share": stale / max(looks, 1), "looks": looks}


def json_of(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return json.loads(resp.content or b"{}")


def iter_sources() -> Iterable[str]:
    return iter(SOURCES)
