""""Is this you?": find your OpenAlex author record from your name and institution, with no ORCID.

You type a name and an institution (or an institutional email, or a co-author's name); myGeeKy shows the
researchers OpenAlex knows by that name -- each with their institution, country, a few recent paper titles and
main topics -- and you confirm one ("That's me") or none. The confirmed author id (A...) then works like an ORCID:
your works' topics feed your profile, your citations count as Wins, your field's papers are found from yours.

At most three calls: the authors by name, the institution (to rank by it), and the top candidates' recent works.
If OpenAlex is busy (its shared daily budget is used up), setup carries on the regular way, with keywords, and the
search is kept as *pending*: it is tried again quietly later (after OpenAlex's Retry-After), and when it works,
myGeeKy asks "Is this you?". Nothing is saved until you confirm. The phone does the same (lib/whois.ts);
tests/test_whois.py runs both on the same answers.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

OPENALEX = "https://api.openalex.org"
UA = {"User-Agent": "mygeeky (https://github.com/mygeeky/myGeeKy)"}
SHOWN = 5                      # candidates shown
TITLES = 3                     # recent titles shown for each
RETRY_MIN_SECONDS = 1800       # a pending search is tried again at most this often
_ID = re.compile(r"^A\d{2,12}$")


def norm(s: str) -> str:
    """Lowercase, accents off, only letters and spaces: 'Ölçer-Šmíd' -> 'olcer smid'."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z]+", " ", s).split())


def domain_hint(text: str) -> str:
    """An institution hint from an email: 'a.b@med.uni-heidelberg.de' -> 'uni heidelberg'."""
    m = re.search(r"@([A-Za-z0-9.-]+)", text or "")
    if not m:
        return text or ""
    parts = [p for p in m.group(1).lower().split(".") if p not in ("ac", "edu", "com", "org", "net", "gov", "www")]
    parts = [p for p in parts if len(p) > 2 and p not in ("mail", "med", "cs", "bio", "dept", "student", "students")]
    return " ".join(norm(p) for p in parts[:2])


def name_score(query: str, candidate: str) -> float:
    """0..1: how well a candidate's name fits what was typed. The last word must match; initials count."""
    q, c = norm(query).split(), norm(candidate).split()
    if not q or not c or q[-1] not in c:
        return 0.0
    hits = 0.0
    for w in q:
        if w in c:
            hits += 1
        elif len(w) == 1 and any(x.startswith(w) for x in c):
            hits += 0.8
        elif any(len(x) == 1 and w.startswith(x) for x in c):
            hits += 0.8
    return round(hits / max(len(q), len(c)), 4)


def place_score(hint: str, institution: str) -> float:
    """0..1: how many of the hint's words are in the institution's name."""
    h, i = set(norm(hint).split()) - {"of", "the", "and", "de", "university", "institute"}, set(norm(institution).split())
    if not h:
        return 0.0
    return round(len(h & i) / len(h), 4)


def parse_authors(data: Any) -> list[dict[str, Any]]:
    """OpenAlex's /authors answer, as candidates: id, name, institution, country, works, cited, topics."""
    out = []
    for a in (data or {}).get("results") or [] if isinstance(data, dict) else []:
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or "").rsplit("/", 1)[-1]
        if not _ID.match(aid):
            continue
        insts = [i for i in a.get("last_known_institutions") or [] if isinstance(i, dict)]
        inst = insts[0] if insts else {}
        out.append({
            "id": aid, "name": str(a.get("display_name") or ""),
            "institution": str(inst.get("display_name") or ""), "country": str(inst.get("country_code") or ""),
            "works": int(a.get("works_count") or 0), "cited": int(a.get("cited_by_count") or 0),
            "topics": [str(t.get("display_name")) for t in (a.get("topics") or [])[:3]
                       if isinstance(t, dict) and t.get("display_name")],
            "orcid": str(a.get("orcid") or "").rsplit("/", 1)[-1],
            "titles": [],
        })
    return out


def rank(cands: list[dict[str, Any]], name: str, hint: str = "") -> list[dict[str, Any]]:
    """Best first: the name fits, the institution fits, then a little for having works. Names that don't fit go."""
    scored = []
    for c in cands:
        n = name_score(name, c["name"])
        if n <= 0:
            continue
        score = 0.6 * n + 0.3 * place_score(hint, c["institution"]) + 0.1 * min(math.log10(1 + c["works"]) / 3, 1)
        scored.append({**c, "score": round(score, 4)})
    scored.sort(key=lambda c: (-c["score"], -c["works"], c["id"]))
    return scored[:SHOWN]


def add_titles(cands: list[dict[str, Any]], works: Any) -> list[dict[str, Any]]:
    """Each candidate's few most recent titles, from one /works answer for all of them."""
    by: dict[str, list[tuple[int, str]]] = {c["id"]: [] for c in cands}
    for w in (works or {}).get("results") or [] if isinstance(works, dict) else []:
        title = str((w or {}).get("title") or "").strip()
        year = int((w or {}).get("publication_year") or 0)
        for a in (w or {}).get("authorships") or []:
            aid = str(((a or {}).get("author") or {}).get("id") or "").rsplit("/", 1)[-1]
            if aid in by and title and all(t != title for _, t in by[aid]):
                by[aid].append((year, title))
    out = []
    for c in cands:
        recent = sorted(by[c["id"]], key=lambda x: (-x[0], x[1]))[:TITLES]
        out.append({**c, "titles": [f"{t} ({y})" if y else t for y, t in recent]})
    return out


def authors_url(name: str) -> str:
    from urllib.parse import quote
    return (f"{OPENALEX}/authors?search={quote(norm(name))}&per-page=25"
            "&select=id,display_name,last_known_institutions,works_count,cited_by_count,topics,orcid")


def works_url(ids: list[str]) -> str:
    return (f"{OPENALEX}/works?filter=author.id:{'|'.join(ids)}&sort=publication_date:desc&per-page=50"
            "&select=title,publication_year,authorships")


def busy(status: int) -> bool:
    """OpenAlex refused for now (its budget, or it's down): try again later, carry on without it."""
    return status == 429 or status >= 500


def search(name: str, hint: str = "", session: Any = None) -> dict[str, Any]:
    """{"status": "found" | "none" | "busy", "candidates": [...], "retry_after": seconds}."""
    import requests

    from . import wisep
    get = (session or wisep.session("you:whois", force=True)).get         # a search you typed: asked now, counted
    hint = domain_hint(hint) if "@" in (hint or "") else hint
    if len(norm(name).split()) < 2:
        return {"status": "none", "candidates": [], "why": "Type your first and last name."}
    try:
        r = get(authors_url(name), headers=UA, timeout=20)
        if busy(r.status_code):
            return {"status": "busy", "candidates": [], "retry_after": int(r.headers.get("retry-after") or 0)}
        r.raise_for_status()
        cands = rank(parse_authors(r.json()), name, hint)
        if not cands:
            return {"status": "none", "candidates": []}
        w = get(works_url([c["id"] for c in cands]), headers=UA, timeout=20)
        if w.status_code == 200:
            cands = add_titles(cands, w.json())
        return {"status": "found", "candidates": cands}
    except (requests.RequestException, ValueError):
        return {"status": "busy", "candidates": [], "retry_after": 0}


def next_try(now: float, retry_after: int = 0) -> float:
    """When a pending search may be tried again (seconds since the epoch)."""
    return now + max(RETRY_MIN_SECONDS, int(retry_after or 0))
