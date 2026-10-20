"""Who cited you (You → 📑 Cited by): the papers citing your work, the people who cite you most, and where you're read.

For anyone with papers on OpenAlex (from an ORCID, or the author you confirmed with "Is this you?"), even with no
profile tracking their citations. Once a day: your author record (total citations, h-index), your papers' citation
counts, and -- only for papers whose count went up (all of them the first time) -- the newest papers citing them,
in one request for up to 50 of your papers (`cites:W1|W2|...`). So it's a few requests a day. If OpenAlex is busy,
what was found before stays, and it's tried again the next day.

Kept in citedby.json: the counts, the citing papers found (newest 200, each with when it was first seen, so new
ones can be marked), and your totals. `summary()` works out the page; the phone does the same (lib/cited-by.ts),
and tests/test_citedby.py checks both agree on the same answers.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import CITEDBY_FILE, ensure_dirs
from .files import read_json, write_json

OPENALEX = "https://api.openalex.org"
UA = {"User-Agent": "mygeeky (https://github.com/mygeeky/myGeeKy)"}
REFRESH_HOURS = 20
KEEP = 200                 # citing papers kept
PER_CALL = 50              # your papers asked about in one request
NEW_DAYS = 14              # a citing paper first seen this recently is NEW
MONTH_DAYS = 30
TOP = 8
_WORK = re.compile(r"^W\d{2,12}$")
_AUTHOR = re.compile(r"^A\d{2,12}$")


def _id(url: Any) -> str:
    return str(url or "").rsplit("/", 1)[-1]


def _days(a: str, b: str) -> int | None:
    try:
        return (date.fromisoformat(b[:10]) - date.fromisoformat(a[:10])).days
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- reading OpenAlex's answers
def parse_author(data: Any) -> dict[str, Any]:
    d = data if isinstance(data, dict) else {}
    stats = d.get("summary_stats") if isinstance(d.get("summary_stats"), dict) else {}
    return {"name": str(d.get("display_name") or "")[:120], "cited": int(d.get("cited_by_count") or 0),
            "works": int(d.get("works_count") or 0), "h": int(stats.get("h_index") or 0),
            "i10": int(stats.get("i10_index") or 0)}


def parse_citing(data: Any, mine: set[str], me: str, seen_at: str) -> list[dict[str, Any]]:
    """OpenAlex's citing works, each with its first authors, their institutions and countries, and which of your
    papers it cites (from its reference list)."""
    out = []
    for w in (data or {}).get("results") or [] if isinstance(data, dict) else []:
        if not isinstance(w, dict):
            continue
        wid = _id(w.get("id"))
        title = " ".join(str(w.get("title") or "").split())[:220]
        if not _WORK.match(wid) or not title:
            continue
        authors = []
        for a in (w.get("authorships") or [])[:12]:
            if not isinstance(a, dict):
                continue
            au = a.get("author") if isinstance(a.get("author"), dict) else {}
            insts = [i for i in (a.get("institutions") or []) if isinstance(i, dict)]
            inst = insts[0] if insts else {}
            name = str(au.get("display_name") or "").strip()[:80]
            if name:
                authors.append({"name": name, "id": _id(au.get("id")) if _AUTHOR.match(_id(au.get("id"))) else "",
                                "institution": str(inst.get("display_name") or "")[:100],
                                "country": str(inst.get("country_code") or "")[:2].upper()})
        cites = sorted({_id(r) for r in (w.get("referenced_works") or [])} & mine)
        out.append({"id": wid, "title": title, "date": str(w.get("publication_date") or "")[:10],
                    "url": str(w.get("doi") or f"https://openalex.org/{wid}")[:200], "authors": authors,
                    "cites": cites, "self": bool(me) and any(a["id"] == me for a in authors), "seen": seen_at})
    return out


def merge(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The citing papers known so far: new ones added (keeping when an old one was first seen), newest first."""
    by = {c["id"]: c for c in old if isinstance(c, dict) and c.get("id")}
    for c in new:
        if c["id"] in by:
            c = {**c, "seen": by[c["id"]].get("seen", c["seen"]),
                 "cites": sorted(set(by[c["id"]].get("cites") or []) | set(c["cites"]))}
        by[c["id"]] = c
    return sorted(by.values(), key=lambda c: (c.get("date", ""), c["id"]), reverse=True)[:KEEP]


def to_ask(counts: dict[str, int], before: dict[str, int] | None) -> list[str]:
    """Your papers worth asking about: the ones whose citations went up (all cited ones, the first time), most
    cited first, at most two requests' worth."""
    if before is None:
        rose = [w for w, n in counts.items() if n > 0]
    else:
        rose = [w for w, n in counts.items() if n > int(before.get(w, 0))]
    rose.sort(key=lambda w: (-counts[w], w))
    return rose[:2 * PER_CALL]


# --------------------------------------------------------------------------- the page
def summary(state: dict[str, Any], today: str) -> dict[str, Any]:
    """Everything the page shows, from what's kept (no network)."""
    citing = [c for c in state.get("citing") or [] if isinstance(c, dict) and not c.get("self")]
    papers = state.get("papers") or {}
    def within(d: Any, days: int) -> bool:
        n = _days(str(d or ""), today)
        return n is not None and n <= days
    month = [c for c in citing if within(c.get("date"), MONTH_DAYS)]
    new = [c for c in citing if within(c.get("seen"), NEW_DAYS)]
    new_ids = {c["id"] for c in new}
    me = state.get("author", "")
    people: Counter = Counter()
    who: dict[str, dict[str, Any]] = {}
    for c in citing:
        for a in {(x["id"] or x["name"]): x for x in c.get("authors") or []}.values():
            if a.get("id") and a["id"] == me:
                continue
            key = a["id"] or a["name"]
            people[key] += 1
            who.setdefault(key, a)
    countries: Counter = Counter()
    places: Counter = Counter()
    for c in citing:
        countries.update({a["country"] for a in c.get("authors") or [] if a.get("country")})
        places.update({a["institution"] for a in c.get("authors") or [] if a.get("institution")})
    most: Counter = Counter()
    for c in citing:
        most.update(c.get("cites") or [])
    rank = lambda counter: sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP]  # noqa: E731
    return {
        "totals": state.get("totals") or {}, "updated_at": state.get("updated_at", ""),
        "found": len(citing), "this_month": len(month), "new": len(new),
        "citing": [{**c, "new": c["id"] in new_ids, "cites_titles": [papers.get(w, {}).get("title", "") for w in c.get("cites") or []]}
                   for c in citing[:40]],
        "people": [{**who[k], "count": n} for k, n in rank(people)],
        "countries": [{"code": k, "count": n} for k, n in rank(countries)],
        "places": [{"name": k, "count": n} for k, n in rank(places)[:5]],
        "papers": [{"id": w, "title": papers.get(w, {}).get("title", ""), "count": n,
                    "cited": int(papers.get(w, {}).get("cited", 0))} for w, n in rank(most)[:5]],
    }


# --------------------------------------------------------------------------- once a day
def load() -> dict[str, Any]:
    d = read_json(CITEDBY_FILE, {})
    return d if isinstance(d, dict) else {}


def due(state: dict[str, Any], author: str, now: datetime | None = None) -> bool:
    if state.get("author") != author:
        return True
    try:
        last = datetime.fromisoformat(state.get("updated_at", ""))
    except (TypeError, ValueError):
        return True
    return ((now or datetime.now(timezone.utc)) - last) >= timedelta(hours=REFRESH_HOURS)


def busy(status: int) -> bool:
    return status == 429 or status >= 500


def refresh(author: str, session: Any = None, force: bool = False, now: datetime | None = None) -> dict[str, Any]:
    """Read what's new (when due) and keep it. {"ok", "busy"?, "state"}."""
    import requests
    state = load()
    if not _AUTHOR.match(author or ""):
        return {"ok": False, "state": state}
    if not force and not due(state, author, now):
        return {"ok": True, "state": state}
    from . import wisep
    get = (session or wisep.session("you:cited", force=force)).get        # OpenAlex through WISEP
    when = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    fresh_author = state.get("author") != author
    try:
        r = get(f"{OPENALEX}/authors/{author}", params={"select": "id,display_name,cited_by_count,works_count,summary_stats"},
                headers=UA, timeout=30)
        if busy(r.status_code):
            return {"ok": False, "busy": True, "state": state}
        r.raise_for_status()
        totals = parse_author(r.json())
        r = get(f"{OPENALEX}/works", params={"filter": f"author.id:{author}", "per-page": 200,
                                              "select": "id,title,cited_by_count"}, headers=UA, timeout=30)
        if busy(r.status_code):
            return {"ok": False, "busy": True, "state": state}
        r.raise_for_status()
        papers = {}
        for w in (r.json() or {}).get("results") or []:
            wid = _id(w.get("id"))
            if _WORK.match(wid) and w.get("title"):
                papers[wid] = {"title": " ".join(str(w["title"]).split())[:200], "cited": int(w.get("cited_by_count") or 0)}
        counts = {w: p["cited"] for w, p in papers.items()}
        ask = to_ask(counts, None if fresh_author else state.get("counts"))
        found: list[dict[str, Any]] = []
        for i in range(0, len(ask), PER_CALL):
            chunk = ask[i:i + PER_CALL]
            r = get(f"{OPENALEX}/works", params={"filter": "cites:" + "|".join(chunk), "sort": "publication_date:desc",
                                                  "per-page": 50, "select": "id,title,publication_date,doi,authorships,referenced_works"},
                    headers=UA, timeout=30)
            if busy(r.status_code):
                break                                   # what we got so far is kept; the rest next time
            r.raise_for_status()
            # the first read only sets the starting point: what's there already isn't "new" (no flood of NEW)
            found += parse_citing(r.json(), set(papers), author, "" if fresh_author else when)
    except (requests.RequestException, ValueError):
        return {"ok": False, "busy": True, "state": state}
    out = {"author": author, "updated_at": when, "totals": totals, "counts": counts, "papers": papers,
           "citing": merge([] if fresh_author else state.get("citing") or [], found)}
    ensure_dirs()
    write_json(CITEDBY_FILE, out)
    return {"ok": True, "state": out}
