"""The small protocol model: is this repo or article good learning material, and for which stage?

A protocol (protocols.py) is a skill turned into ordered stages, e.g. *R for
data analysis*: R basics -> statistics with R -> data analysis -> a real
project -> your own work. When myGeeKy has no reviewed protocol for a skill,
the app builds one: it searches GitHub (course, tutorial, workshop, book and
awesome-list repos) and OpenAlex (tutorial and review articles), and this
model sorts what comes back into

    none     not learning material (a library, someone's homework, unrelated)
    basics   an introduction: first steps, beginner courses, cheat sheets
    deeper   in depth: methods and theory, advanced books, reviews, best practice
    applied  the skill used on a real task: "RNA-seq analysis in R", case studies
    project  a real analysis or pipeline to read and rerun, an example project

It is a multinomial logistic regression over words (and word pairs) of the
name, description, topics, title and abstract, plus a few binned facts
(stars, age, kind, article type). The skill's own name is masked as
`__skill`, so what it learns carries over to skills it never saw. It's
trained on the maker's computer (tools/protocol_model/train.py) from
labelled candidates and from protocols users published, and ships as plain
JSON weights (data/protocol_model.json): no dependencies, and the phone runs
the same numbers (mobile/src/lib/protomodel.ts).

Fetching uses only fields the search APIs return (no README, no extra
requests), so the app and the training see the same thing.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

BUNDLED = Path(__file__).parent / "data" / "protocol_model.json"
ROLES = ["none", "basics", "deeper", "applied", "project"]
OPENALEX = "https://api.openalex.org"
UA = {"User-Agent": "mygeeky (https://github.com/mygeeky/myGeeKy)"}
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#]*")
_model: dict[str, Any] | None = None


# --------------------------------------------------------------------------- what to search
def _term(name: str) -> str:
    return f'"{name}"' if " " in name else name


def github_queries(name: str, kind: str = "", goal: str = "") -> list[str]:
    """Search queries for learning material about a skill (and a goal, e.g. "data analysis")."""
    t = _term(name)
    qs = [f"{t} tutorial", f"{t} course", f"{t} workshop", f"awesome {t}", f"{t} book"]
    if goal:
        qs.insert(1, f"{t} {goal}")
    qs.append(f"{t} {goal or 'analysis'} example" if kind != "language" else f"{goal or 'analysis'} language:{name}")
    return qs


def article_queries(name: str, goal: str = "") -> list[tuple[str, str]]:
    """(search, filter) pairs for OpenAlex: tutorial/primer articles, and reviews."""
    words = f"{name} {goal}".strip()
    return [(f"{words} tutorial", ""), (words, "type:review")]


# Free step-by-step pages that aren't papers: a tool's or a project's own guide. Only software: myGeeKy
# does not teach bench work, and the sites that publish bench protocols are refused outright (safety.py).
GUIDE_SITES = ("imagej.net", "docs.github.com", "developer.mozilla.org", "docs.python.org", "cran.r-project.org",
               "quarto.org", "owasp.org", "12factor.net", "google.github.io", "opensource.guide",
               "kubernetes.io", "docs.docker.com", "cellprofiler.org")


def is_guide(url: str) -> bool:
    """A free how-to page from a project's or a tool's own documentation."""
    from . import safety
    if safety.blocked_source(url):
        return False
    host = str(url or "").lower().split("/")[2] if str(url or "").startswith("https://") else ""
    return any(host == s or host.endswith("." + s) for s in GUIDE_SITES)


# --------------------------------------------------------------------------- what comes back
def from_repo(r: dict[str, Any]) -> dict[str, Any] | None:
    """A GitHub search hit as a candidate (only the fields search returns)."""
    from . import safety
    if not isinstance(r, dict) or not r.get("full_name") or r.get("fork"):
        return None
    if safety.is_bench(f"{r.get('full_name', '')} {r.get('description') or ''}"):
        return None                      # a repo of bench protocols is not learning material here
    return {"kind": "repo", "id": f"gh:{str(r['full_name']).lower()}",
            "title": str(r["full_name"])[:140], "url": f"https://github.com/{r['full_name']}",
            "text": " ".join(str(r.get("description") or "").split())[:400],
            "topics": [str(t)[:50] for t in (r.get("topics") or [])][:20],
            "language": str(r.get("language") or "")[:40], "stars": int(r.get("stargazers_count") or 0),
            "updated": str(r.get("pushed_at") or "")[:10], "pages": bool(r.get("has_pages")),
            "archived": bool(r.get("archived"))}


def _abstract(inv: Any, limit: int = 600) -> str:
    if not isinstance(inv, dict):
        return ""
    spots = sorted((p, w) for w, ps in inv.items() if isinstance(ps, list) for p in ps if isinstance(p, int))
    return " ".join(w for _, w in spots)[:limit]


def from_work(w: dict[str, Any]) -> dict[str, Any] | None:
    """An OpenAlex work as a candidate."""
    if not isinstance(w, dict) or not w.get("title"):
        return None
    wid = str(w.get("id") or "").rsplit("/", 1)[-1]
    if not re.match(r"^W\d{2,12}$", wid):
        return None
    doi = str(w.get("doi") or "")
    oa = w.get("open_access") or {}
    src = ((w.get("primary_location") or {}).get("source") or {}) if isinstance(w.get("primary_location"), dict) else {}
    sid = str(src.get("id") or "").rsplit("/", 1)[-1]
    url = doi if doi.startswith("https://") else f"https://openalex.org/{wid}"
    from . import safety
    if safety.blocked_source(url, sid):        # a bench-protocol journal is never a candidate at all
        return None
    return {"kind": "article", "id": f"oa:{wid}", "title": " ".join(str(w["title"]).split())[:200],
            "url": url, "text": _abstract(w.get("abstract_inverted_index")), "topics": [],
            "type": str(w.get("type") or "")[:20], "year": int(w.get("publication_year") or 0),
            "cited": int(w.get("cited_by_count") or 0), "oa": bool(oa.get("is_oa")),
            "venue": str(src.get("display_name") or "")[:80], "source_id": sid}


WORK_FIELDS = ("id,title,doi,type,publication_year,cited_by_count,open_access,abstract_inverted_index,"
               "primary_location")


def search_github(client, query: str, per_page: int = 20) -> list[dict[str, Any]]:
    resp = client._get("/search/repositories", params={"q": query, "per_page": per_page, "sort": "stars"},
                       is_search=True)
    if resp.status_code != 200:
        return []
    return [c for c in (from_repo(r) for r in resp.json().get("items") or []) if c]


def search_openalex(session, search: str, filt: str = "", per_page: int = 15) -> list[dict[str, Any]]:
    params = {"search": search, "per-page": per_page, "select": WORK_FIELDS}
    if filt:
        params["filter"] = filt
    r = session.get(f"{OPENALEX}/works", params=params, headers=UA, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    return [c for c in (from_work(w) for w in (data.get("results") or [])) if c]


# --------------------------------------------------------------------------- features
def _years(day: str, today: date) -> float | None:
    try:
        return (today - datetime.fromisoformat(day[:10]).date()).days / 365.25
    except (TypeError, ValueError):
        return None


def _bin(n: float, edges: Iterable[float]) -> int:
    return sum(1 for e in edges if n >= e)


def mask(text: str, aliases: Iterable[str]) -> str:
    """The skill's own names become one placeholder word (`__skill` once tokenized), so the model learns what *learning material* looks like."""
    out = text.lower()
    for a in sorted({a.lower() for a in aliases if a}, key=len, reverse=True):
        out = re.sub(r"(^|[^a-z0-9])" + re.escape(a) + r"s?(?![a-z0-9])", r"\1 qqskillqq ", out)
    return out


def tokens(c: dict[str, Any], aliases: Iterable[str] = (), today: date | None = None) -> set[str]:
    """The features of a candidate: words, word pairs and binned facts."""
    today = today or date.today()
    name = re.sub(r"[-_./]+", " ", str(c.get("title") or ""))
    raw = " ; ".join([name, str(c.get("text") or ""), " ".join(c.get("topics") or [])])
    words = [w if w != "qqskillqq" else "__skill" for w in _TOKEN.findall(mask(raw, aliases))]
    out = set(words) | {f"{a}_{b}" for a, b in zip(words, words[1:])}
    kind = c.get("kind", "repo")
    out.add(f"__kind_{kind}")
    if not (c.get("text") or "").strip():
        out.add("__no_text")
    if kind == "repo":
        out.add(f"__stars_{_bin(int(c.get('stars') or 0), (10, 100, 1000, 10000))}")
        age = _years(str(c.get("updated") or ""), today)
        if age is not None:
            out.add(f"__updated_{_bin(age, (1, 3, 6))}")
        if c.get("pages"):
            out.add("__pages")
        if c.get("archived"):
            out.add("__archived")
        lang = str(c.get("language") or "").lower()
        out.add(f"__lang_{lang}" if lang else "__lang_none")
    else:
        out.add(f"__type_{c.get('type') or 'other'}")
        out.add(f"__cited_{_bin(int(c.get('cited') or 0), (10, 100, 1000))}")
        if c.get("oa"):
            out.add("__oa")
        age = today.year - int(c.get("year") or today.year)
        out.add(f"__age_{_bin(age, (3, 8, 15))}")
    return out


# --------------------------------------------------------------------------- the model
def load(path: Path | None = None) -> dict[str, Any]:
    global _model
    if path is not None or _model is None:
        from .files import read_json
        data = read_json(path or BUNDLED, {}) or {}
        model = {"version": str(data.get("version") or ""), "roles": list(data.get("roles") or ROLES),
                 "bias": [float(x) for x in data.get("bias") or [0.0] * len(ROLES)],
                 "weights": {str(k): [float(x) for x in v] for k, v in (data.get("weights") or {}).items()
                             if isinstance(v, list)}}
        if path is not None:
            return model
        _model = model
    return _model


def predict(c: dict[str, Any], aliases: Iterable[str] = (), model: dict[str, Any] | None = None,
            today: date | None = None) -> dict[str, float]:
    """{role: probability} for a candidate."""
    m = model or load()
    z = list(m["bias"])
    for t in tokens(c, aliases, today):
        w = m["weights"].get(t)
        if w:
            for i, x in enumerate(w):
                z[i] += x
    top = max(z)
    e = [math.exp(x - top) for x in z]
    s = sum(e)
    return {r: e[i] / s for i, r in enumerate(m["roles"])}
