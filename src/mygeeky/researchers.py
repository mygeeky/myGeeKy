"""Circle → 📄 Researchers: people who publish, not only people on GitHub.

- **Following by name.** Anyone, picked from OpenAlex's author search with the "is this the right one?" check
  (whois.search: institution, topics, recent titles). The list stays on this device; nobody is told.
- **Suggestions, for free.** Who cites you (citedby.py) and who leads the papers rising in your field (papers.py
  trends): both already read, so suggesting costs no request.
- **New work, preprints first.** One batched OpenAlex search for everyone due (`author.id:A1|A2|…`, up to 50, through
  WISEP: one credit, not one per person), each person checked about as often as they publish (`interval_days`). A
  preprint (arXiv, bioRxiv, medRxiv…) shows the day it appears; when its published version arrives (same title, by
  the same people), the two show as one: "now published in …". Linking costs nothing (it's found among what was read).

The phone does the same (lib/researchers.ts); tests/test_researchers.py checks both agree.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

STATE_FILE = DATA_DIR / "researchers.json"
OPENALEX = "https://api.openalex.org"
BATCH = 50                       # authors in one search (OpenAlex allows up to 100 values; 50 keeps URLs short)
KEEP_DAYS = 400                  # kept this long: a preprint often comes 6-12 months before its journal version
LOOK_BACK_DAYS = 120             # how far back a search looks (rounded to the month, so its key stays steady)
MAX_FOLLOWING = 200
MAX_WORKS = 400
_AID = re.compile(r"^A\d{4,}$")
_WID = re.compile(r"^W\d{4,}$")
PREPRINT_SERVERS = ("arxiv", "biorxiv", "medrxiv", "chemrxiv", "ssrn", "research square", "preprints.org", "osf",
                    "zenodo", "authorea", "psyarxiv", "socarxiv", "eartharxiv", "techrxiv", "sciety")


# --------------------------------------------------------------------------- the rules (the phone has the same)
def interval_days(works_per_month: float) -> int:
    """How often to look for someone's new work: daily for the prolific, weekly for the quiet."""
    if works_per_month >= 2:
        return 1
    if works_per_month >= 0.5:
        return 3
    return 7


def rate_of(dates: Iterable[str], today: str) -> float:
    """Works a month over the last year, from the publication dates seen."""
    t = date.fromisoformat(today)
    n = sum(1 for d in dates if d and 0 <= (t - date.fromisoformat(d[:10])).days <= 365)
    return round(n / 12, 3)


def is_due(person: dict[str, Any], today: str) -> bool:
    last = person.get("checked") or ""
    if not last:
        return True
    return (date.fromisoformat(today) - date.fromisoformat(last[:10])).days >= interval_days(person.get("rate") or 0.0)


def since(today: str) -> str:
    """The first day of the month LOOK_BACK_DAYS ago: a search's date filter that changes once a month, not daily."""
    d = date.fromisoformat(today) - timedelta(days=LOOK_BACK_DAYS)
    return d.replace(day=1).isoformat()


def works_url(ids: list[str], today: str) -> str:
    return (f"{OPENALEX}/works?filter=author.id:{'|'.join(sorted(ids))},from_publication_date:{since(today)}"
            "&sort=publication_date:desc&per-page=100"
            "&select=id,doi,title,publication_date,type,primary_location,authorships")


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def is_preprint(work: dict[str, Any]) -> bool:
    if str(work.get("type") or "") == "preprint":
        return True
    src = ((work.get("primary_location") or {}).get("source") or {}) if isinstance(work.get("primary_location"), dict) else {}
    name = str(src.get("display_name") or "").lower()
    return src.get("type") == "repository" and any(s in name for s in PREPRINT_SERVERS)


def parse_works(data: Any, following: Iterable[str]) -> list[dict[str, Any]]:
    """OpenAlex's answer as feed items: id, title, date, venue, preprint?, url, doi, and which of the people you
    follow wrote it (`by`)."""
    mine = set(following)
    out = []
    for w in (data or {}).get("results") or [] if isinstance(data, dict) else []:
        if not isinstance(w, dict):
            continue
        wid = str(w.get("id") or "").rsplit("/", 1)[-1]
        title = " ".join(str(w.get("title") or "").split())[:300]
        day = str(w.get("publication_date") or "")[:10]
        if not _WID.match(wid) or not title or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            continue
        by = []
        for a in w.get("authorships") or []:
            aid = str(((a or {}).get("author") or {}).get("id") or "").rsplit("/", 1)[-1]
            if aid in mine and aid not in by:
                by.append(aid)
        if not by:
            continue
        loc = w.get("primary_location") if isinstance(w.get("primary_location"), dict) else {}
        src = (loc or {}).get("source") or {}
        doi = str(w.get("doi") or "").replace("https://doi.org/", "")[:200]
        url = f"https://doi.org/{doi}" if doi else str((loc or {}).get("landing_page_url") or f"https://openalex.org/{wid}")
        out.append({"id": wid, "title": title, "date": day, "venue": str(src.get("display_name") or "")[:120],
                    "preprint": is_preprint(w), "url": url if url.startswith("https://") else f"https://openalex.org/{wid}",
                    "doi": doi, "by": by, "authors": len(w.get("authorships") or [])})
    return out


def merge_works(kept: dict[str, dict[str, Any]], found: list[dict[str, Any]], today: str,
                first_seen: str) -> dict[str, dict[str, Any]]:
    """The feed with new finds added (each with the day it was first seen), old ones dropped, and every preprint linked
    to its published version when both are here (same title, a shared author you follow): the published one carries
    `preprint_of` (the preprint's venue and date), the preprint `published_as`, and the feed shows them as one."""
    works = {k: dict(v) for k, v in kept.items()}
    for w in found:
        old = works.get(w["id"])
        works[w["id"]] = {**w, "seen": (old or {}).get("seen") or first_seen}
    t = date.fromisoformat(today)
    works = {k: v for k, v in works.items() if (t - date.fromisoformat(v["date"])).days <= KEEP_DAYS}
    by_title: dict[str, list[dict[str, Any]]] = {}
    for w in works.values():
        w.pop("preprint_of", None)
        w.pop("published_as", None)
        by_title.setdefault(_norm_title(w["title"]), []).append(w)
    for group in by_title.values():
        pre = sorted((w for w in group if w["preprint"]), key=lambda w: w["date"])
        pub = sorted((w for w in group if not w["preprint"]), key=lambda w: w["date"])
        if pre and pub and set(pre[0]["by"]) & set(pub[-1]["by"]):
            pub[-1]["preprint_of"] = {"venue": pre[0]["venue"], "date": pre[0]["date"], "id": pre[0]["id"]}
            pre[0]["published_as"] = pub[-1]["id"]
    keep = sorted(works.values(), key=lambda w: (w["date"], w["id"]), reverse=True)[:MAX_WORKS]
    return {w["id"]: w for w in keep}


def feed(state: dict[str, Any], today: str) -> list[dict[str, Any]]:
    """New work, newest first, each piece once (a preprint with a published version shows as the published one),
    with the names of the people you follow who wrote it and whether it's new to you."""
    names = {p["id"]: p["name"] for p in state.get("following") or []}
    seen = set(state.get("seen") or [])
    out = []
    for w in sorted((state.get("works") or {}).values(), key=lambda w: (w["date"], w["id"]), reverse=True):
        if w.get("published_as"):
            continue
        out.append({**w, "names": [names[a] for a in w["by"] if a in names], "new": w["id"] not in seen})
    return out


def suggestions(cited_people: list[dict[str, Any]], field_people: list[dict[str, Any]],
                following: Iterable[str], me: str = "") -> list[dict[str, Any]]:
    """People worth following, from what's already read: who cites you, and who leads your field's rising papers.
    [{id, name, institution, why, score}], best first, without anyone you follow (or you)."""
    skip = set(following) | {me}
    out: dict[str, dict[str, Any]] = {}
    for p in cited_people:
        aid = str(p.get("id") or "").rsplit("/", 1)[-1]
        if _AID.match(aid) and aid not in skip:
            out[aid] = {"id": aid, "name": str(p.get("name") or ""), "institution": str(p.get("institution") or ""),
                        "why": f"cites your work ({int(p.get('count') or 0)}×)", "score": 2.0 + int(p.get("count") or 0)}
    for p in field_people:
        aid = str(p.get("openalex") or "").rsplit("/", 1)[-1]
        if not _AID.match(aid) or aid in skip:
            continue
        n = int(p.get("papers") or 0)
        why = f"leads {n} of the papers rising in your field" if n > 1 else "leads a paper rising in your field"
        if aid in out:
            out[aid]["why"] += f"; {why}"
            out[aid]["score"] += 1.0 + n
        else:
            out[aid] = {"id": aid, "name": str(p.get("name") or ""), "institution": "", "why": why, "score": 1.0 + n}
    return sorted(out.values(), key=lambda p: (-p["score"], p["name"]))[:20]


# --------------------------------------------------------------------------- the state
def load() -> dict[str, Any]:
    data = read_json(STATE_FILE, {}) or {}
    data = data if isinstance(data, dict) else {}
    data.setdefault("following", [])
    data.setdefault("works", {})
    data.setdefault("seen", [])
    return data


def save(state: dict[str, Any]) -> None:
    ensure_dirs()
    write_json(STATE_FILE, state)


def follow(person: dict[str, Any], today: str | None = None) -> dict[str, Any]:
    """Follow someone picked from the author search (id, name, institution, country, topics)."""
    state = load()
    aid = str(person.get("id") or "")
    if not _AID.match(aid) or any(p["id"] == aid for p in state["following"]):
        return state
    state["following"] = (state["following"] + [{
        "id": aid, "name": str(person.get("name") or "")[:120], "institution": str(person.get("institution") or "")[:160],
        "country": str(person.get("country") or "")[:2], "topics": [str(t)[:80] for t in person.get("topics") or []][:3],
        "added": today or date.today().isoformat(), "checked": "", "rate": 0.0}])[-MAX_FOLLOWING:]
    save(state)
    return state


def unfollow(aid: str) -> dict[str, Any]:
    state = load()
    state["following"] = [p for p in state["following"] if p["id"] != aid]
    state["works"] = {k: {**w, "by": [a for a in w["by"] if a != aid]} for k, w in state["works"].items()}
    state["works"] = {k: w for k, w in state["works"].items() if w["by"]}
    save(state)
    return state


def mark_seen(ids: Iterable[str]) -> None:
    state = load()
    seen = list(state["seen"])
    seen += [i for i in ids if i not in seen]
    state["seen"] = seen[-MAX_WORKS * 2:]
    save(state)


def refresh(session=None, force: bool = False, today: str | None = None) -> dict[str, Any]:
    """Look for new work by everyone due: one batched search per 50 people, through WISEP. {"ok", "busy"?, "state"}."""
    from . import wisep
    today = today or date.today().isoformat()
    state = load()
    due = [p for p in state["following"] if force or is_due(p, today)]
    if not due:
        return {"ok": True, "state": state}
    get = (session or wisep.session("circle:researchers", force=force)).get
    busy = False
    for i in range(0, len(due), BATCH):
        chunk = due[i:i + BATCH]
        try:
            r = get(works_url([p["id"] for p in chunk], today), timeout=30)
        except Exception:
            busy = True
            break
        if r.status_code != 200:
            busy = True
            break
        found = parse_works(r.json(), [p["id"] for p in state["following"]])
        state["works"] = merge_works(state["works"], found, today, today)
        for p in chunk:
            p["checked"] = today
            p["rate"] = rate_of([w["date"] for w in state["works"].values() if p["id"] in w["by"]], today)
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save(state)
    return {"ok": not busy, "busy": busy, "state": state}


def search(name: str, session=None) -> dict[str, Any]:
    """Find someone to follow by name: whois's search, through WISEP (a search you typed: asked now, counted)."""
    from . import whois, wisep
    return whois.search(name, "", session or wisep.session("circle:researchers", force=True))
