"""The world's skill trends: one shared file that keeps Rising skills honest.

What myGeeKy reads for you is picked by your interests, so on its own it can't tell "the field is moving" from "you
started reading about it". This file is the same for everyone and picked by no one: once a day a GitHub Action
(.github/workflows/skill-trends.yml) takes an even sample of new preprints across broad bioRxiv, medRxiv and arXiv
categories in three windows -- the last 45 days, the 45 before, and the same 45 days a year ago -- and counts, for each skill in data/skills.json,
how many of them mention it, and which skills appear together in the same preprint (so a direction rising
across the field can be tied to the skills you have: skills.directions). Each source gives the same number of documents to both windows, so the counts compare
directly. The two recent windows say what is rising now; the year-ago one shows the big shifts a few weeks can't
(a direction can be large and flat lately but many times bigger than a year ago). skills.py (and the phone's
lib/skills.ts) measure growth on this plus your own explore picks, and use what
you chose to read only for "is it for you?" -- see skills.corrected().

Every myGeeKy reads the file from GitHub at most once a day (`refresh_if_due`), falling back to the copy it shipped
with. No key and no server.
"""

from __future__ import annotations

import json
import random
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

BUNDLED = Path(__file__).parent / "data" / "skill_trends.json"
PHONE_COPY = Path(__file__).resolve().parents[2] / "mobile" / "src" / "data" / "skill_trends.json"
CACHE_FILE = DATA_DIR / "skill_trends.json"
REMOTE_URL = "https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/skill_trends.json"
CHECK_EVERY_HOURS = 24
WINDOW_DAYS = 45
SOURCES = ("bioRxiv", "medRxiv", "arXiv")
RXIV_PAGES = {"biorxiv": 40, "medrxiv": 15}       # pages of 30, spread evenly over a window
ARXIV_CATS = ("q-bio.GN", "q-bio.QM", "q-bio.BM", "q-bio.NC", "stat.ML", "stat.AP", "stat.ME", "cs.LG", "cs.CL",
              "cs.CV", "cs.CE", "cs.DC")
ARXIV_PER_CAT = 150                               # per window, in three slices of 50
MIN_TOGETHER = 2                                  # pairs seen together fewer times aren't kept
UA = {"User-Agent": "mygeeky-skill-trends (https://mygeeky.org)"}
_DATE_LEN = 10


# --------------------------------------------------------------------------- building it (the daily Action)
def windows(today: date) -> tuple[tuple[date, date], ...]:
    """(older, newer, a year ago): two back-to-back windows of WINDOW_DAYS, the newer ending yesterday, and the
    newer one's dates a year earlier."""
    end = today - timedelta(days=1)
    mid = end - timedelta(days=WINDOW_DAYS)
    newer = (mid + timedelta(days=1), end)
    return (mid - timedelta(days=WINDOW_DAYS - 1), mid), newer, (newer[0] - timedelta(days=365), newer[1] - timedelta(days=365))


def _get(session, url: str, **kw):
    """GET with three tries: these free APIs are slow now and then."""
    for attempt in range(3):
        try:
            r = session.get(url, headers=UA, timeout=60, **kw)
            if r.status_code == 200:
                return r
        except Exception:
            if attempt == 2:
                raise
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{url}: no answer after three tries")


def _rxiv(server: str, lo: date, hi: date, session, pages: int) -> list[str]:
    base = f"https://api.biorxiv.org/details/{server}/{lo.isoformat()}/{hi.isoformat()}"
    first = _get(session, f"{base}/0").json()
    msg = (first.get("messages") or [{}])[0]
    total = int(msg.get("total") or msg.get("count") or 0)
    per = max(1, int(msg.get("count") or 30))
    cursors = sorted({int(i * max(total - per, 0) / max(pages - 1, 1)) for i in range(pages)}) if total > per else [0]
    out = []
    for c in cursors:
        data = first if c == 0 else _get(session, f"{base}/{c}").json()
        out += [f"{p.get('title', '')} ; {p.get('abstract', '')}" for p in data.get("collection") or []]
    return out


def _arxiv(cat: str, lo: date, hi: date, session) -> list[str]:
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    span = (hi - lo).days + 1
    for k in range(3):                              # three slices, so the whole window is sampled
        a = lo + timedelta(days=k * span // 3)
        b = lo + timedelta(days=(k + 1) * span // 3 - 1)
        q = f"cat:{cat} AND submittedDate:[{a:%Y%m%d}0000 TO {b:%Y%m%d}2359]"
        for wait in (0, 30, 90):                    # when busy, arXiv answers with an empty list: wait, ask again
            time.sleep(wait)
            r = _get(session, "https://export.arxiv.org/api/query",
                     params={"search_query": q, "start": 0, "max_results": ARXIV_PER_CAT // 3,
                             "sortBy": "submittedDate", "sortOrder": "descending"})
            entries = ET.fromstring(r.content).findall("a:entry", ns)
            time.sleep(3.1)                         # arXiv asks for one request every 3 seconds
            if entries:
                break
        out += [f"{e.findtext('a:title', '', ns)} ; {e.findtext('a:summary', '', ns)}" for e in entries]
    return out


def fetch(today: date, session) -> dict[str, tuple[list[str], ...]]:
    """{source: (older texts, newer texts, year-ago texts)} -- each source trimmed to the same number in every window."""
    wins = windows(today)
    got: dict[str, tuple[list[str], ...]] = {}
    for server, pages in RXIV_PAGES.items():
        name = "bioRxiv" if server == "biorxiv" else "medRxiv"
        got[name] = tuple(_rxiv(server, lo, hi, session, pages) for lo, hi in wins)
    arxiv: tuple[list[str], ...] = ([], [], [])
    for cat in ARXIV_CATS:
        try:                                        # a category counts only with every window read
            parts = [_arxiv(cat, lo, hi, session) for lo, hi in wins]
        except Exception as exc:
            print(f"skill trends: skipped arXiv {cat} ({exc})", file=sys.stderr)
            continue
        k = min(len(x) for x in parts)              # the same number from each category in every window
        for side, x in zip(arxiv, parts):
            side += x[:k]
    got["arXiv"] = arxiv
    rng = random.Random(today.toordinal())
    for name, parts in got.items():
        k = min(len(x) for x in parts)
        got[name] = tuple(rng.sample(x, k) for x in parts)
    return got


def count(texts: dict[str, tuple[list[str], ...]], today: date) -> dict[str, Any]:
    from . import skills
    totals = [0, 0, 0]
    per_skill: dict[str, list[int]] = {}
    together: dict[str, int] = {}
    per_source = {}
    for name, pair in texts.items():
        per_source[name] = [len(x) for x in pair]
        for side, docs in enumerate(pair):
            totals[side] += len(docs)
            for t in docs:
                found = sorted(skills.skills_in(t))
                for s in found:
                    per_skill.setdefault(s, [0, 0, 0])[side] += 1
                for i, a in enumerate(found):
                    for b in found[i + 1:]:
                        together[f"{a}|{b}"] = together.get(f"{a}|{b}", 0) + 1
    return {"version": today.isoformat(), "windows": [[lo.isoformat(), hi.isoformat()] for lo, hi in windows(today)],
            "docs": totals, "sources": per_source, "skills": dict(sorted(per_skill.items())),
            "pairs": {k: v for k, v in sorted(together.items()) if v >= MIN_TOGETHER}}


def build(today: date | None = None, session=None) -> dict[str, Any]:
    import requests
    today = today or date.today()
    return count(fetch(today, session or requests.Session()), today)


def save(data: dict[str, Any], path: Path = BUNDLED) -> Path:
    """Write the file, and the phone's identical copy next to it."""
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    if path == BUNDLED and PHONE_COPY.parent.is_dir():
        PHONE_COPY.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- reading it (untrusted: from the internet)
def _int(x: Any) -> int:
    return int(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x < 10**8 else 0


def clean(data: Any) -> dict[str, Any]:
    """{"version", "docs": [older, newer, a year ago], "skills": {name: [older, newer, a year ago]},
    "pairs": {"A|B": together}} with only
    known skills (A before B) and sane numbers."""
    from . import skills
    data = data if isinstance(data, dict) else {}
    known = {s["name"] for s in skills.vocabulary()}
    docs = data.get("docs") if isinstance(data.get("docs"), list) and len(data["docs"]) in (2, 3) else [0, 0]
    out = {}
    raw = data.get("skills") if isinstance(data.get("skills"), dict) else {}
    for name, pair in raw.items():
        if name in known and isinstance(pair, list) and len(pair) in (2, 3):        # an older file has no year-ago count
            out[name] = [_int(pair[0]), _int(pair[1]), _int(pair[2]) if len(pair) == 3 and len(docs) == 3 else 0]
    pairs = {}
    raw = data.get("pairs") if isinstance(data.get("pairs"), dict) else {}
    for key, k in list(raw.items())[:20000]:
        a, _, b = str(key).partition("|")
        if a in known and b in known and a < b and _int(k):
            pairs[f"{a}|{b}"] = _int(k)
    version = str(data.get("version") or "")
    return {"version": version if len(version) == _DATE_LEN and version[4] == "-" else "",
            "docs": [_int(docs[0]), _int(docs[1]), _int(docs[2]) if len(docs) == 3 else 0], "skills": out, "pairs": pairs}


_loaded: dict[str, Any] | None = None


def load(force: bool = False) -> dict[str, Any]:
    """The newest trends we have: the copy shipped with myGeeKy, or a newer one fetched since."""
    global _loaded
    if _loaded is not None and not force:
        return _loaded
    shipped = clean(read_json(BUNDLED, {}))
    fetched = clean((read_json(CACHE_FILE, {}) or {}).get("data"))
    _loaded = fetched if fetched["docs"][1] and fetched["version"] >= shipped["version"] else shipped
    return _loaded


def refresh_if_due(force: bool = False, now: datetime | None = None, timeout: float = 20.0) -> bool:
    """Fetch the newest trends from GitHub, at most once a day. True if a newer one arrived."""
    global _loaded
    import requests
    now = now or datetime.now(timezone.utc)
    cached = read_json(CACHE_FILE, {}) or {}
    if not force:
        try:
            if (now - datetime.fromisoformat(cached.get("checked_at", ""))).total_seconds() < CHECK_EVERY_HOURS * 3600:
                return False
        except (TypeError, ValueError):
            pass
    r = requests.get(REMOTE_URL, timeout=timeout, headers={"User-Agent": "mygeeky"})
    ensure_dirs()
    if getattr(r, "status_code", 200) != 200 or len(r.content) > 1_000_000:
        write_json(CACHE_FILE, {**(cached if isinstance(cached, dict) else {}), "checked_at": now.isoformat(timespec="seconds")})
        return False
    data = clean(r.json())
    old = clean(cached.get("data")) if isinstance(cached, dict) else clean({})
    write_json(CACHE_FILE, {"checked_at": now.isoformat(timespec="seconds"), "data": data})
    _loaded = None
    return data["version"] > old["version"]


if __name__ == "__main__":
    if sys.argv[1:] == ["build"]:
        d = build()
        save(d)
        print(f"skill trends: {d['docs']} documents, {len(d['skills'])} skills, {d['sources']}")
    else:
        print("usage: python -m mygeeky.skilltrends build")
