"""Circle → Researchers → 🌟 Leading lights: living people who lead a field, a few at a time, picked by your Model.

- **The list** (data/lights.json, drafted by tools/lights_build.py and checked by the maker): each person's OpenAlex
  id, name, why they're on it (a badge: 🏅 Nobel, 🏆 another prize, 📈 most cited, 🛠 a famous tool, with its source),
  their field and topics, and their links (Google Scholar, ORCID, GitHub). It's text from the internet, so it's
  cleaned here: plain text, sizes capped, links only to the sites they belong to.
- **Who you see:** the people whose topics fit your Model best, PER_SET at a time, a new set every EVERY_DAYS days,
  going round the whole fitting list before anyone comes back (nothing to keep: the day decides).
- **Their latest papers:** one OpenAlex search for everyone on show (1 credit), through WISEP.
- **A tap opens a report:** their OpenAlex record by id (free: totals, h-index, papers and citations per year, topics,
  institution) and their five most cited papers (1 credit), cached by WISEP.

The phone does the same (lib/lights.ts); tests/test_lights.py checks both agree.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .files import read_json

DATA_FILE = Path(__file__).resolve().parent / "data" / "lights.json"
OPENALEX = "https://api.openalex.org"
PER_SET = 4
EVERY_DAYS = 3
YEARS = 10                      # the report's chart
MAX_PEOPLE = 2000
BADGES = {"nobel": ("🏅", "Nobel Prize"), "prize": ("🏆", "Prize"), "cited": ("📈", "Most cited"),
          "tool": ("🛠", "Famous tool")}
_AID = re.compile(r"^A\d{4,}$")
_ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_SCHOLAR = re.compile(r"^https://scholar\.google\.com/citations\?user=[\w-]{6,20}$")
_GITHUB = re.compile(r"^[A-Za-z\d](?:[A-Za-z\d-]{0,38})$")
_SOURCE = ("https://www.wikidata.org/wiki/Q", "https://openalex.org/", "https://www.nobelprize.org/",
           "https://amturing.acm.org/")


def _text(value: Any, n: int) -> str:
    return " ".join(str(value or "").split())[:n]


def _int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def clean_person(raw: Any) -> dict[str, Any] | None:
    """One person from the list, or None if it isn't one: only what each field may hold."""
    if not isinstance(raw, dict):
        return None
    aid, name, badge = _text(raw.get("id"), 20), _text(raw.get("name"), 120), _text(raw.get("badge"), 10)
    if not _AID.match(aid) or not name or badge not in BADGES:
        return None
    source = _text(raw.get("source"), 300)
    orcid, scholar, github = _text(raw.get("orcid"), 19), _text(raw.get("scholar"), 80), _text(raw.get("github"), 39)
    topics = raw.get("topics") if isinstance(raw.get("topics"), list) else []
    return {"id": aid, "name": name, "badge": badge, "why": _text(raw.get("why"), 160),
            "source": source if source.startswith(_SOURCE) else "", "field": _text(raw.get("field"), 60),
            "topics": [t for t in (_text(x, 80) for x in topics[:6]) if t], "institution": _text(raw.get("institution"), 160),
            "orcid": orcid if _ORCID.match(orcid) else "", "scholar": scholar if _SCHOLAR.match(scholar) else "",
            "github": github if _GITHUB.match(github) else "", "cited": _int(raw.get("cited")), "h": _int(raw.get("h"))}


def clean(data: Any) -> dict[str, Any]:
    data = data if isinstance(data, dict) else {}
    rows = data.get("people") if isinstance(data.get("people"), list) else []
    people, seen = [], set()
    for p in (clean_person(r) for r in rows[:MAX_PEOPLE]):
        if p and p["id"] not in seen:
            seen.add(p["id"])
            people.append(p)
    version = _text(data.get("version"), 10)
    return {"version": version if re.match(r"^\d{4}-\d{2}-\d{2}$", version) else "", "people": people}


def load() -> dict[str, Any]:
    return clean(read_json(DATA_FILE, {}))


def links(p: dict[str, Any]) -> list[tuple[str, str]]:
    """Where to read more about someone: (label, url)."""
    out = [("Google Scholar", p["scholar"])] if p.get("scholar") else []
    if p.get("orcid"):
        out.append(("ORCID", f"https://orcid.org/{p['orcid']}"))
    out.append(("OpenAlex", f"https://openalex.org/{p['id']}"))
    if p.get("github"):
        out.append(("GitHub", f"https://github.com/{p['github']}"))
    return out


# --------------------------------------------------------------------------- who you see
def fit(p: dict[str, Any], weights: dict[str, float]) -> float:
    """How well someone's topics and field match your Model: the weights of your terms found in them."""
    text = " ".join(p["topics"] + [p["field"]]).lower()
    return round(sum(w for t, w in weights.items() if t and str(t).lower() in text), 4)


def period(today: str, every: int = EVERY_DAYS) -> int:
    return date.fromisoformat(today).toordinal() // every


def next_change(today: str, every: int = EVERY_DAYS) -> str:
    return date.fromordinal((period(today, every) + 1) * every).isoformat()


def pick(people: list[dict[str, Any]], weights: dict[str, float], today: str, n: int = PER_SET,
         every: int = EVERY_DAYS) -> list[dict[str, Any]]:
    """The set on show: the people who fit your Model (best first), n at a time, a new set every `every` days,
    round the whole list before anyone comes back. Without a fit (no Model yet), the most cited and the laureates."""
    scored = [(fit(p, weights), p) for p in people]
    pool = sorted((x for x in scored if x[0] > 0), key=lambda x: (-x[0], x[1]["id"]))
    if len(pool) < n:
        rest = sorted((x for x in scored if x[0] <= 0), key=lambda x: (x[1]["badge"] not in ("nobel", "prize"),
                                                                       -x[1]["cited"], x[1]["id"]))
        pool += rest[:max(n, 12) - len(pool)]
    if not pool:
        return []
    start = (period(today, every) * n) % len(pool)
    return [{**p, "fit": f} for f, p in (pool[(start + i) % len(pool)] for i in range(min(n, len(pool))))]


# --------------------------------------------------------------------------- their latest papers
def since(today: str) -> str:
    """A year back, rounded to the month (so the search's key stays the same all month)."""
    d = date.fromisoformat(today)
    return f"{d.year - 1}-{d.month:02d}-01"


def recent_url(ids: Iterable[str], today: str) -> str:
    return (f"{OPENALEX}/works?filter=author.id:{'|'.join(sorted(ids))},from_publication_date:{since(today)}"
            "&sort=publication_date:desc&per-page=50&select=id,doi,title,publication_date,primary_location,authorships")


def _work(w: dict[str, Any]) -> dict[str, Any]:
    doi = str(w.get("doi") or "")
    src = ((w.get("primary_location") or {}).get("source") or {})
    return {"title": _text(w.get("title"), 300), "url": doi if doi.startswith("https://doi.org/") else
            "https://openalex.org/" + str(w.get("id") or "").rsplit("/", 1)[-1],
            "date": _text(w.get("publication_date"), 10), "venue": _text(src.get("display_name"), 120)}


def parse_recent(data: Any, ids: Iterable[str], per_person: int = 2) -> dict[str, list[dict[str, Any]]]:
    """Each person's newest papers (titles, links, dates, where), from the one search."""
    out: dict[str, list[dict[str, Any]]] = {i: [] for i in ids}
    rows = data.get("results") if isinstance(data, dict) and isinstance(data.get("results"), list) else []
    for w in rows:
        if not isinstance(w, dict) or not w.get("title"):
            continue
        by = {str((a.get("author") or {}).get("id") or "").rsplit("/", 1)[-1] for a in w.get("authorships") or []
              if isinstance(a, dict)}
        for aid in out:
            if aid in by and len(out[aid]) < per_person and all(x["title"] != _text(w["title"], 300) for x in out[aid]):
                out[aid].append(_work(w))
    return out


# --------------------------------------------------------------------------- the report
def author_url(aid: str) -> str:
    return f"{OPENALEX}/authors/{aid}"                  # one record by its id: free


def top_url(aid: str) -> str:
    return (f"{OPENALEX}/works?filter=author.id:{aid}&sort=cited_by_count:desc&per-page=5"
            "&select=id,doi,title,publication_year,cited_by_count,primary_location")


def report(author: Any, top: Any, weights: dict[str, float], today: str) -> dict[str, Any]:
    """What a tap shows: the totals, papers and citations per year, their topics (yours marked), where they work,
    and their most cited papers."""
    a = author if isinstance(author, dict) else {}
    stats = a.get("summary_stats") if isinstance(a.get("summary_stats"), dict) else {}
    year = date.fromisoformat(today).year
    per = {_int(c.get("year")): c for c in a.get("counts_by_year") or [] if isinstance(c, dict)}
    years = [[y, _int((per.get(y) or {}).get("works_count")), _int((per.get(y) or {}).get("cited_by_count"))]
             for y in range(year - YEARS + 1, year + 1)]
    mine = [str(t).lower() for t in weights if t]
    topics = [[_text(t.get("display_name"), 80), any(m in str(t.get("display_name") or "").lower() for m in mine)]
              for t in (a.get("topics") or [])[:8] if isinstance(t, dict) and t.get("display_name")]
    inst = (a.get("last_known_institutions") or [{}])
    rows = top.get("results") if isinstance(top, dict) and isinstance(top.get("results"), list) else []
    best = [{**_work(w), "year": _int(w.get("publication_year")), "cited": _int(w.get("cited_by_count"))}
            for w in rows[:5] if isinstance(w, dict) and w.get("title")]
    return {"works": _int(a.get("works_count")), "cited": _int(a.get("cited_by_count")), "h": _int(stats.get("h_index")),
            "i10": _int(stats.get("i10_index")), "years": years, "topics": topics,
            "institution": _text((inst[0] if inst and isinstance(inst[0], dict) else {}).get("display_name"), 160),
            "top": best}


# --------------------------------------------------------------------------- asking (through WISEP)
def fetch_recent(people: list[dict[str, Any]], today: str | None = None, session=None) -> dict[str, Any]:
    from . import wisep
    today = today or date.today().isoformat()
    ids = [p["id"] for p in people]
    if not ids:
        return {"ok": True, "recent": {}}
    try:
        r = (session or wisep.session("circle:researchers:lights")).get(recent_url(ids, today), timeout=30)
        if r.status_code != 200:
            return {"ok": False, "busy": True, "recent": {}}
        return {"ok": True, "recent": parse_recent(r.json(), ids)}
    except Exception:
        return {"ok": False, "busy": True, "recent": {}}


def fetch_report(aid: str, weights: dict[str, float], today: str | None = None, session=None) -> dict[str, Any]:
    from . import wisep
    today = today or date.today().isoformat()
    if not _AID.match(aid):
        return {"ok": False}
    get = (session or wisep.session("circle:researchers:lights", force=True)).get
    try:
        ra = get(author_url(aid), timeout=30)
        if ra.status_code != 200:
            return {"ok": False, "busy": True}
        rt = get(top_url(aid), timeout=30)
        return {"ok": True, "report": report(ra.json(), rt.json() if rt.status_code == 200 else {}, weights, today)}
    except Exception:
        return {"ok": False, "busy": True}
