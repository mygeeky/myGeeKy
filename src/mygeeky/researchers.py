"""Circle → 📄 Researchers: people who publish, not only people on GitHub.

- **Following by name.** Anyone, picked from OpenAlex's author search with the "is this the right one?" check
  (whois.search: institution, topics, recent titles). The list stays on this device; nobody is told.
- **Suggestions, for free.** Who cites you (citedby.py) and who leads the papers rising in your field (papers.py
  trends): both already read, so suggesting costs no request.
- **New work, preprints first.** One batched OpenAlex search for everyone due (`author.id:A1|A2|…`, up to 50, through
  WISEP: one credit, not one per person), each person checked about as often as they publish (`interval_days`). A
  preprint (arXiv, bioRxiv, medRxiv…) shows the day it appears; when its published version arrives (same title, by
  the same people), the two show as one: "now published in …". Linking costs nothing (it's found among what was read).

- **🕸️ Network (step 2).** You in the middle, your co-authors around you, their co-authors (one introduction away)
  outside, the people you follow marked, lines where people have written together, and who connects you to anyone.
  Two searches a week through WISEP: your own works with their authors, then one batch for your co-authors' and the
  people you follow's recent works. At most MAX_NODES people, so it reads on a phone.
- **Your Model learns from your circle.** The topics your co-authors and the people you follow publish on gently join
  your interest weights (`blend_circle`, never above 0.6, below what you typed); You → Model shows it, and it can be
  switched off.

The phone does the same (lib/researchers.ts); tests/test_researchers.py checks both agree.
"""

from __future__ import annotations

import math
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
MAX_NODES = 60                  # people on the map: it has to read on a phone
RING1 = 24                      # your co-authors shown (the most frequent)
NETWORK_DAYS = 7                # the map is rebuilt weekly: networks change slowly
CIRCLE_MAX = 0.6                # a topic from your circle never weighs more than this (what you typed is 1.0)
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


# --------------------------------------------------------------------------- 🕸️ the network
def my_works_url(me: str) -> str:
    return (f"{OPENALEX}/works?filter=author.id:{me}&per-page=200&sort=publication_date:desc"
            "&select=id,publication_year,authorships,primary_topic")


def ring_url(ids: list[str], today: str) -> str:
    """One batched search: the recent works of your co-authors and the people you follow (three years back, rounded
    to the year so the search stays the same all year)."""
    start = f"{int(today[:4]) - 3}-01-01"
    return (f"{OPENALEX}/works?filter=author.id:{'|'.join(sorted(ids))},from_publication_date:{start}&per-page=200"
            "&sort=publication_date:desc&select=id,publication_year,authorships,primary_topic")


def _authors(work: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for a in work.get("authorships") or []:
        au = (a or {}).get("author") or {}
        aid = str(au.get("id") or "").rsplit("/", 1)[-1]
        if _AID.match(aid) and all(x["id"] != aid for x in out):
            inst = next((i for i in (a or {}).get("institutions") or [] if isinstance(i, dict)), {})
            out.append({"id": aid, "name": str(au.get("display_name") or "")[:120],
                        "institution": str(inst.get("display_name") or "")[:160]})
    return out


def _results(data: Any) -> list[dict[str, Any]]:
    return [w for w in (data or {}).get("results") or [] if isinstance(w, dict)] if isinstance(data, dict) else []


def build_network(mine: Any, ring: Any, me: str, following: Iterable[str]) -> dict[str, Any]:
    """The map from two answers (your works; your co-authors' and followed people's works): {"nodes": [{id, name,
    institution, ring (0 you, 1 co-author, 2 one introduction away), n (works together), followed}], "edges": [[a, b,
    works together]], "topics": {topic: count over the circle's works}}."""
    follow = set(following)
    people: dict[str, dict[str, str]] = {}
    with_me: dict[str, int] = {}
    for w in _results(mine):
        names = _authors(w)
        if not any(a["id"] == me for a in names):
            continue
        for a in names:
            people.setdefault(a["id"], a)
            if a["id"] != me:
                with_me[a["id"]] = with_me.get(a["id"], 0) + 1
    ring1 = [a for a, _ in sorted(with_me.items(), key=lambda kv: (-kv[1], kv[0]))[:RING1]]
    pairs: dict[tuple[str, str], int] = {}
    reach: dict[str, int] = {}
    topics: dict[str, int] = {}
    for w in _results(ring):
        names = _authors(w)
        ids = [a["id"] for a in names]
        inner = [i for i in ids if i in ring1 or i in follow]
        if not inner:
            continue
        topic = str(((w.get("primary_topic") or {}) if isinstance(w.get("primary_topic"), dict) else {}).get("display_name") or "")
        if topic:
            topics[topic] = topics.get(topic, 0) + 1
        for a in names:
            people.setdefault(a["id"], a)
        if len(ids) <= 30:                           # a consortium's 500-author paper says nothing about who knows whom
            for i, a in enumerate(sorted(ids)):
                for b in sorted(ids)[i + 1:]:
                    if a in inner or b in inner:
                        pairs[(a, b)] = pairs.get((a, b), 0) + 1
            for x in ids:
                if x != me and x not in ring1 and x not in follow:
                    reach[x] = reach.get(x, 0) + 1
    room = MAX_NODES - 1 - len(ring1) - len([f for f in follow if f not in ring1 and f != me])
    ring2 = [x for x, _ in sorted(reach.items(), key=lambda kv: (-kv[1], kv[0]))[:max(0, room)]]
    shown = [me] + ring1 + [f for f in sorted(follow) if f not in ring1 and f != me] + ring2
    nodes = []
    for x in shown:
        p = people.get(x, {"id": x, "name": "", "institution": ""})
        nodes.append({"id": x, "name": p["name"] or ("You" if x == me else x), "institution": p["institution"],
                      "ring": 0 if x == me else 1 if x in ring1 else 2, "n": with_me.get(x, reach.get(x, 0)),
                      "followed": x in follow})
    keep = set(shown)
    edges = [[a, me, n] for a, n in sorted(with_me.items()) if a in keep]
    edges += [[a, b, n] for (a, b), n in sorted(pairs.items()) if a in keep and b in keep and me not in (a, b)]
    return {"nodes": nodes, "edges": edges, "topics": dict(sorted(topics.items(), key=lambda kv: (-kv[1], kv[0]))[:30])}


def path_to(net: dict[str, Any], target: str) -> list[str]:
    """Who connects you to `target` (shortest path along written-together lines), you first; [] if nobody does."""
    nodes = [n["id"] for n in net.get("nodes") or []]
    if not nodes or target not in nodes:
        return []
    me = nodes[0]
    nbr: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b, _ in net.get("edges") or []:
        if a in nbr and b in nbr:
            nbr[a].append(b)
            nbr[b].append(a)
    prev, queue = {me: ""}, [me]
    while queue:
        x = queue.pop(0)
        if x == target:
            break
        for y in sorted(nbr[x]):
            if y not in prev:
                prev[y] = x
                queue.append(y)
    if target not in prev:
        return []
    out = [target]
    while prev[out[-1]]:
        out.append(prev[out[-1]])
    return out[::-1]


def _r4(x: float) -> float:
    """Rounded as JavaScript's Math.round does, so both apps place everyone in the same spot."""
    return math.floor(x * 10000 + 0.5) / 10000


def layout(net: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """Where each person sits, in -1..1: you at the centre, co-authors on the inner ring (most frequent at the top),
    the outer ring beside the co-author they're closest to. The same on both apps."""
    nodes = net.get("nodes") or []
    pos: dict[str, tuple[float, float]] = {}
    if not nodes:
        return pos
    pos[nodes[0]["id"]] = (0.0, 0.0)
    inner = [n["id"] for n in nodes if n["ring"] == 1]
    angle: dict[str, float] = {}
    for i, x in enumerate(inner):
        a = -math.pi / 2 + 2 * math.pi * i / max(len(inner), 1)
        angle[x] = a
        pos[x] = (_r4(0.45 * math.cos(a)), _r4(0.45 * math.sin(a)))
    strongest: dict[str, tuple[int, str]] = {}
    for a, b, w in net.get("edges") or []:
        for x, y in ((a, b), (b, a)):
            if y in angle and (x not in strongest or (w, y) > strongest[x]):
                strongest[x] = (w, y)
    outer = [n["id"] for n in nodes if n["ring"] == 2]
    outer.sort(key=lambda x: (angle.get(strongest.get(x, (0, ""))[1], 10.0), x))
    for i, x in enumerate(outer):
        a = -math.pi / 2 + 2 * math.pi * (i + 0.5) / max(len(outer), 1)
        pos[x] = (_r4(0.9 * math.cos(a)), _r4(0.9 * math.sin(a)))
    return pos


def circle_weights(topics: dict[str, int]) -> dict[str, float]:
    """Your circle's topics as interest weights: the most frequent at CIRCLE_MAX, the rest in proportion (at least 0.2)."""
    if not topics:
        return {}
    top = max(topics.values())
    return {k.lower(): math.floor((0.2 + (CIRCLE_MAX - 0.2) * v / top) * 1000 + 0.5) / 1000 for k, v in topics.items()}


def blend_circle(weights: dict[str, float], circle: dict[str, float]) -> dict[str, float]:
    """Your weights with your circle's topics joined in: never lowering anything you have."""
    out = dict(weights)
    for k, w in circle.items():
        out[k] = max(out.get(k, 0.0), w)
    return out


def network_due(state: dict[str, Any], today: str) -> bool:
    built = (state.get("network") or {}).get("built", "")
    if not built:
        return True
    from . import wisep
    age = (date.fromisoformat(today) - date.fromisoformat(built[:10])).days
    return wisep.timer_due(age >= NETWORK_DAYS, age * 24.0)


def refresh_network(me: str, session=None, force: bool = False, today: str | None = None) -> dict[str, Any]:
    """Rebuild the map (weekly): your works, then one batch for your co-authors and the people you follow."""
    from . import wisep
    today = today or date.today().isoformat()
    state = load()
    if not me or not _AID.match(me):
        return {"ok": False, "why": "no author", "state": state}
    if not force and not network_due(state, today):
        return {"ok": True, "state": state}
    get = (session or wisep.session("circle:researchers", force=force)).get
    try:
        r = get(my_works_url(me), timeout=30)
        if r.status_code != 200:
            return {"ok": False, "busy": True, "state": state}
        mine = r.json()
        first = build_network(mine, {}, me, [p["id"] for p in state["following"]])
        ids = [n["id"] for n in first["nodes"] if n["ring"] == 1] + [p["id"] for p in state["following"]]
        ring: Any = {}
        if ids:
            r2 = get(ring_url(list(dict.fromkeys(ids))[:BATCH], today), timeout=30)
            if r2.status_code == 200:
                ring = r2.json()
    except Exception:
        return {"ok": False, "busy": True, "state": state}
    net = build_network(mine, ring, me, [p["id"] for p in state["following"]])
    state["network"] = {**net, "built": today, "me": me}
    save(state)
    return {"ok": True, "state": state}


def circle_on(state: dict[str, Any] | None = None) -> bool:
    return (state or load()).get("model_circle", True) is not False


def set_circle(on: bool) -> None:
    state = load()
    state["model_circle"] = bool(on)
    save(state)


def model_weights() -> dict[str, float]:
    """What your circle adds to your Model now (empty when switched off or not built yet)."""
    state = load()
    return circle_weights((state.get("network") or {}).get("topics") or {}) if circle_on(state) else {}


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
