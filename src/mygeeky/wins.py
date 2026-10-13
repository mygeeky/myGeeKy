"""Your wins: new stars, forks and citations on your own work.

Once a day myGeeKy reads two public counts and compares them with yesterday's:

  * your own GitHub repos (stars, forks) -- one call with your token;
  * your papers' citation counts on OpenAlex (from your ORCID) -- no key needed.
    When a paper gained citations, it also asks OpenAlex for the newest paper
    citing it, so a win can say *who* cited you.

The first read only sets the starting point (no flood of "wins" for everything
you already had). Wins are kept for 60 days in wins.json, which also holds the
last counts; your repos' names, topics and languages go to my_repos.json, which
Rising Skills and Learning paths read to see what you already work with.
Nothing is sent anywhere except the two reads above.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import requests

from .config import MY_REPOS_FILE, WINS_FILE, MyGeekyConfig, ensure_dirs
from .files import read_json, write_json

OPENALEX = "https://api.openalex.org"
UA = {"User-Agent": "mygeeky (https://github.com/mygeeky/myGeeKy)"}
REFRESH_HOURS = 20
KEEP_DAYS = 60
STAR_STEPS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000)
_WORK_ID = re.compile(r"^W\d{2,12}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load() -> dict[str, Any]:
    data = read_json(WINS_FILE, {})
    return data if isinstance(data, dict) else {}


def load_my_repos() -> list[dict[str, Any]]:
    data = read_json(MY_REPOS_FILE, {})
    repos = data.get("repos") if isinstance(data, dict) else None
    return [r for r in (repos or []) if isinstance(r, dict) and r.get("name")]


def due(state: dict[str, Any], now: datetime | None = None) -> bool:
    try:
        last = datetime.fromisoformat(state.get("updated_at", ""))
    except (TypeError, ValueError):
        return True
    return ((now or _now()) - last).total_seconds() >= REFRESH_HOURS * 3600


# --------------------------------------------------------------------------- reading the counts
def slim_repo(r: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(r, dict) or not r.get("full_name") or r.get("fork"):
        return None
    return {"name": str(r["full_name"])[:140], "url": f"https://github.com/{r['full_name']}",
            "description": " ".join(str(r.get("description") or "").split())[:300],
            "topics": [str(t)[:50] for t in (r.get("topics") or [])][:20],
            "language": str(r.get("language") or "")[:40],
            "stars": int(r.get("stargazers_count") or 0), "forks": int(r.get("forks_count") or 0),
            "pushed_at": str(r.get("pushed_at") or "")[:20], "created_at": str(r.get("created_at") or "")[:20]}


def read_repos(client, username: str) -> list[dict[str, Any]]:
    return [s for s in (slim_repo(r) for r in client.list_repos(username, max_pages=3)) if s]


def _openalex(path: str, params: dict[str, Any], session: requests.Session) -> dict[str, Any]:
    r = session.get(f"{OPENALEX}{path}", params=params, headers=UA, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, dict) else {}


def read_papers(author_id: str, session: requests.Session) -> dict[str, dict[str, Any]]:
    """{work id: {"title", "cited", "url"}} for your papers on OpenAlex."""
    if not re.match(r"^A\d{2,12}$", author_id or ""):
        return {}
    data = _openalex("/works", {"filter": f"author.id:{author_id}", "per-page": 200,
                                "select": "id,title,cited_by_count,doi"}, session)
    out = {}
    for w in data.get("results") or []:
        wid = str(w.get("id") or "").rsplit("/", 1)[-1]
        if _WORK_ID.match(wid) and w.get("title"):
            out[wid] = {"title": " ".join(str(w["title"]).split())[:200], "cited": int(w.get("cited_by_count") or 0),
                        "url": str(w.get("doi") or f"https://openalex.org/{wid}")}
    return out


def newest_citing(work_id: str, session: requests.Session) -> dict[str, Any] | None:
    """The most recent paper citing `work_id`: its title, first author and link."""
    data = _openalex("/works", {"filter": f"cites:{work_id}", "sort": "publication_date:desc", "per-page": 1,
                                "select": "id,title,publication_date,doi,authorships"}, session)
    for w in data.get("results") or []:
        authors = [((a.get("author") or {}).get("display_name") or "") for a in (w.get("authorships") or [])]
        authors = [a for a in authors if a]
        wid = str(w.get("id") or "").rsplit("/", 1)[-1]
        return {"title": " ".join(str(w.get("title") or "").split())[:200],
                "by": authors[0] + (" et al." if len(authors) > 1 else "") if authors else "",
                "date": str(w.get("publication_date") or "")[:10],
                "url": str(w.get("doi") or (f"https://openalex.org/{wid}" if _WORK_ID.match(wid) else ""))}
    return None


# --------------------------------------------------------------------------- what changed
def _crossed(before: int, after: int) -> int | None:
    """The biggest milestone passed going from `before` to `after` stars, if any."""
    passed = [s for s in STAR_STEPS if before < s <= after]
    return passed[-1] if passed else None


def diff(old: dict[str, Any], repos: list[dict[str, Any]], papers: dict[str, dict[str, Any]],
         when: str) -> list[dict[str, Any]]:
    """New wins between the last counts (`old`) and now. Empty on the first read."""
    wins: list[dict[str, Any]] = []
    old_repos, old_papers = old.get("repos"), old.get("papers")
    if isinstance(old_repos, dict):
        for r in repos:
            before = old_repos.get(r["name"])
            if not isinstance(before, dict):
                continue
            stars, forks = r["stars"] - int(before.get("stars", 0)), r["forks"] - int(before.get("forks", 0))
            if stars > 0:
                step = _crossed(int(before.get("stars", 0)), r["stars"])
                text = (f"{r['name'].split('/')[-1]} reached {step} ⭐" if step and step >= 10
                        else f"{r['name'].split('/')[-1]} got {stars} new ⭐")
                wins.append({"kind": "stars", "id": f"stars:{r['name']}:{r['stars']}", "text": text,
                             "count": stars, "total": r["stars"], "url": r["url"] + "/stargazers", "at": when})
            if forks > 0:
                wins.append({"kind": "forks", "id": f"forks:{r['name']}:{r['forks']}",
                             "text": f"{forks} new fork{'s' if forks > 1 else ''} of {r['name'].split('/')[-1]}",
                             "count": forks, "total": r["forks"], "url": r["url"] + "/forks", "at": when})
    if isinstance(old_papers, dict):
        for wid, p in papers.items():
            before = old_papers.get(wid)
            if not isinstance(before, dict):
                continue
            gained = p["cited"] - int(before.get("cited", 0))
            if gained > 0:
                wins.append({"kind": "citations", "id": f"cited:{wid}:{p['cited']}", "work": wid,
                             "text": f"“{p['title'][:90]}” was cited {gained} more time{'s' if gained > 1 else ''}",
                             "count": gained, "total": p["cited"], "url": p["url"], "at": when})
    return wins


def refresh(cfg: MyGeekyConfig, client=None, force: bool = False, session: requests.Session | None = None,
            log: Callable[[str], None] = lambda m: None) -> dict[str, Any]:
    """Read the counts (if due), add what changed to the wins, and save."""
    state = load()
    if not force and not due(state):
        return state
    now = _now()
    when = now.isoformat(timespec="seconds")
    session = session or requests.Session()
    errors: list[str] = []
    repos: list[dict[str, Any]] = []
    if cfg.github_username and client is not None:
        try:
            repos = read_repos(client, cfg.github_username)
            ensure_dirs()
            write_json(MY_REPOS_FILE, {"updated_at": when, "repos": repos})
        except Exception as exc:
            errors.append(f"GitHub: {exc}")
            repos = []
    papers: dict[str, dict[str, Any]] = {}
    author = ""
    try:
        from . import scholar
        author = ((scholar.load_scholar_profile() or {}).get("openalex") or {}).get("author_id", "")
        if author:
            papers = read_papers(author, session)
    except Exception as exc:
        errors.append(f"OpenAlex: {exc}")
    new = diff(state, repos, papers, when)
    for w in new:
        if w["kind"] == "citations":
            try:
                w["citing"] = newest_citing(w["work"], session)
            except Exception:
                w["citing"] = None
    cutoff = now - timedelta(days=KEEP_DAYS)
    kept = []
    for w in (state.get("wins") or []):
        try:
            if datetime.fromisoformat(w["at"]) >= cutoff:
                kept.append(w)
        except (KeyError, TypeError, ValueError):
            continue
    seen = {w.get("id") for w in kept}
    wins = [w for w in new if w["id"] not in seen] + kept
    out = {"updated_at": when,
           # a failed read keeps the last counts, so a win isn't lost or counted twice
           "repos": ({r["name"]: {"stars": r["stars"], "forks": r["forks"]} for r in repos}
                     if repos or not cfg.github_username else state.get("repos")),
           "papers": ({k: {"cited": v["cited"]} for k, v in papers.items()} if papers or not author
                      else state.get("papers")),
           "wins": wins[:200], "errors": errors}
    ensure_dirs()
    write_json(WINS_FILE, out)
    log(f"wins: {len(new)} new")
    return out


def recent(state: dict[str, Any] | None = None, days: int = 30) -> list[dict[str, Any]]:
    """Wins of the last `days`, newest first."""
    state = state if state is not None else load()
    cutoff = _now() - timedelta(days=days)
    out = []
    for w in state.get("wins") or []:
        try:
            if datetime.fromisoformat(w["at"]) >= cutoff:
                out.append(w)
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda w: w["at"], reverse=True)
