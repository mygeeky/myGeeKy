"""Rising Skills and Learning paths: what to learn next, and the steps to get there.

**Rising Skills.** myGeeKy already reads what's moving in your field: rising
papers and tools with papers (OpenAlex), discussions and headlines, trending
repos and Hugging Face models, repos you could contribute to, the people it
suggests and the activity of people you follow, and fellow myGeeKy users'
interests. This module counts how often each skill in a small dictionary
(data/skills.json: tools, languages and methods, with the names people use
for them) shows up there -- and compares it with what *you* already show:
your topics and keywords, your CV, your papers (ORCID/OpenAlex) and your own
repos. A skill is suggested when it's

    present in your field  x  rising (more mentions lately than before)
                           x  close to your work  x  missing from your profile,

tilted by your 👍/👎 (taste.py). 👎 hides a skill for good (until you take it
back). Every suggestion says why: "in 4 rising papers, 3 trending repos; not
in your profile yet". Counts are kept per day (skills_history.json), so
"rising" gets sharper the longer myGeeKy runs.

**Learning paths.** Start a path on any skill and it becomes four steps: learn
the basics, go deeper (both from the curated learning resources), practise on
a real project in your field, and use it in your own work. The last step
ticks itself when one of your own repos (or your CV/papers) shows the skill;
the others you tick when you've done them.

Everything here is local: it reads files myGeeKy already saved, and sends
nothing.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote_plus

from . import curated, taste
from .config import (ACTIVITY_CACHE_FILE, BEACON_CACHE_FILE, CV_TEXT_FILE, DATA_DIR, HEADLINES_FILE, HF_MODELS_FILE,
                     MARKET_FILE, NEWS_FILE, PATHS_FILE, SKILLS_HISTORY_FILE, TRENDS_FILE, MyGeekyConfig, ensure_dirs)
from .files import read_json, read_jsonl, write_json

BUNDLED = Path(__file__).parent / "data" / "skills.json"
CONTRIBUTE_LOG = DATA_DIR / "contribute_history.jsonl"
SUGGESTIONS_LOG = DATA_DIR / "suggestions_history.jsonl"
RECENT_DAYS = 45
HISTORY_DAYS = 120
TOP = 12
MIN_DOCS = 2                # a skill seen in a single place isn't a trend

# where a mention comes from: (one, several, weight)
SOURCES = {
    "paper": ("rising paper", "rising papers", 1.0),
    "tool": ("tool with a paper", "tools with papers", 1.0),
    "repo": ("trending repo", "trending repos", 0.8),
    "contribute": ("repo near your work", "repos near your work", 0.7),
    "model": ("trending model", "trending models", 0.6),
    "discussion": ("discussion", "discussions", 0.6),
    "news": ("headline", "headlines", 0.5),
    "people": ("person near you", "people near you", 0.4),
    "activity": ("project of people you follow", "projects of people you follow", 0.3),
    "users": ("myGeeKy user near you", "myGeeKy users near you", 0.5),
}


def _said(source: str, n: int) -> str:
    one, many, _ = SOURCES[source]
    return f"in {n} {one if n == 1 else many}"

_vocab: list[dict[str, Any]] | None = None


# --------------------------------------------------------------------------- the dictionary
def vocabulary() -> list[dict[str, Any]]:
    """[{"name", "kind", "aliases", "pattern"}] -- aliases shorter than 3 letters are
    left out ("r", "go" would match inside half the words in a text)."""
    global _vocab
    if _vocab is None:
        data = read_json(BUNDLED, {}) or {}
        out = []
        for s in data.get("skills") or []:
            if not isinstance(s, dict) or not s.get("name"):
                continue
            aliases = sorted({a.lower() for a in s.get("aliases") or [] if isinstance(a, str) and len(a) >= 3},
                             key=len, reverse=True)
            if not aliases:
                continue
            pat = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a).replace(r"\ ", r"[\s_-]+")
                                                            .replace(r"\-", r"[\s_-]?") for a in aliases)
                             + r")s?(?![a-z0-9])", re.I)
            out.append({"name": s["name"], "kind": s.get("kind", ""), "aliases": aliases, "pattern": pat})
        _vocab = out
    return _vocab


def find(name: str) -> dict[str, Any] | None:
    n = (name or "").strip().lower()
    for s in vocabulary():
        if s["name"].lower() == n or n in s["aliases"]:
            return s
    return None


def skills_in(text: str) -> set[str]:
    if not text:
        return set()
    return {s["name"] for s in vocabulary() if s["pattern"].search(text)}


# --------------------------------------------------------------------------- what your field is talking about
def _when(value: Any) -> datetime | None:
    s = str(value or "")
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = datetime.fromisoformat(s[:10])
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def field_documents() -> list[dict[str, Any]]:
    """Everything myGeeKy saved about your field: [{"text", "when", "source", "url", "title"}]."""
    docs: list[dict[str, Any]] = []

    def add(text: str, when: Any, source: str, url: str = "", title: str = "") -> None:
        if text and text.strip():
            docs.append({"text": text[:3000], "when": _when(when), "source": source, "url": url, "title": title[:140]})

    trends = read_json(TRENDS_FILE, {}) or {}
    for kind, source in (("rising", "paper"), ("tools", "tool")):
        for p in trends.get(kind) or []:
            if isinstance(p, dict):
                add(f"{p.get('title', '')} ; {str(p.get('abstract', ''))[:1500]}", p.get("date"), source,
                    p.get("url", ""), p.get("title", ""))
    news = read_json(NEWS_FILE, {}) or {}
    for n in news.get("items") or []:
        if isinstance(n, dict):
            add(f"{n.get('title', '')} ; {n.get('summary', '')}", n.get("published"), "discussion",
                n.get("url", ""), n.get("title", ""))
    heads = read_json(HEADLINES_FILE, {}) or {}
    for h in heads.get("items") or []:
        if isinstance(h, dict) and h.get("match"):          # only headlines that matched your field
            add(h.get("title", ""), h.get("published"), "news", h.get("link", ""), h.get("title", ""))
    hf = read_json(HF_MODELS_FILE, {}) or {}
    for m in hf.get("field") or []:
        if isinstance(m, dict):
            add(f"{m.get('id', '')} ; {' '.join(m.get('tags') or [])} ; {m.get('pipeline', '')}", m.get("created"),
                "model", m.get("url", ""), m.get("id", ""))
    market = read_json(MARKET_FILE, {}) or {}
    for name, r in (market.get("repos") or {}).items():
        if isinstance(r, dict):
            add(f"{name} ; {r.get('description', '')} ; {r.get('language', '')}", r.get("pushed_at"), "repo",
                r.get("url", ""), name)
    for c in read_jsonl(CONTRIBUTE_LOG)[-200:]:
        if isinstance(c, dict):
            add(f"{c.get('full_name', '')} ; {c.get('description', '')} ; {' '.join(c.get('topics') or [])} ; "
                f"{c.get('language', '')}", c.get("pushed_at"), "contribute", c.get("repo_url", ""), c.get("full_name", ""))
    for s in read_jsonl(SUGGESTIONS_LOG)[-300:]:
        if isinstance(s, dict) and s.get("bio"):
            add(s["bio"], s.get("timestamp"), "people", s.get("profile_url", ""), s.get("username", ""))
    act = read_json(ACTIVITY_CACHE_FILE, {}) or {}
    for e in act.get("events") or []:
        if isinstance(e, dict) and e.get("repo"):
            repo = str(e["repo"])
            hint = " julia" if repo.endswith(".jl") else ""
            add(repo.replace("-", " ").replace("_", " ") + hint, e.get("created_at"), "activity",
                e.get("repo_url", ""), repo)
    beacons = read_json(BEACON_CACHE_FILE, {}) or {}
    for owner, u in (beacons.get("users") or {}).items():
        raw = (u or {}).get("raw") if isinstance(u, dict) else None
        if isinstance(raw, dict):
            add(" ; ".join(str(i) for i in (raw.get("interests") or [])[:12]), u.get("pushed_at"), "users",
                f"https://github.com/{owner}", owner)
    return docs


# --------------------------------------------------------------------------- what you already show
def own_text(cfg: MyGeekyConfig) -> str:
    """Your profile as text: topics, keywords, languages, CV, papers and your own repos."""
    parts = [" ; ".join(cfg.topics + cfg.keywords + cfg.languages)]
    try:
        parts.append(CV_TEXT_FILE.read_text(encoding="utf-8", errors="ignore")[:200_000])
    except OSError:
        pass
    try:
        from . import scholar
        parts.append(scholar.scholar_corpus(scholar.load_scholar_profile()))
    except Exception:
        pass
    parts.append(repos_text())
    return "\n".join(p for p in parts if p)


def repos_text(repos: Iterable[dict[str, Any]] | None = None) -> str:
    from . import wins
    rows = list(repos) if repos is not None else wins.load_my_repos()
    return "\n".join(f"{r.get('name', '')} ; {r.get('description', '')} ; {' '.join(r.get('topics') or [])} ; "
                     f"{r.get('language', '')}" for r in rows)


# --------------------------------------------------------------------------- rising
def _history() -> dict[str, dict[str, float]]:
    data = read_json(SKILLS_HISTORY_FILE, {}) or {}
    days = data.get("days") if isinstance(data, dict) else None
    return {d: v for d, v in (days or {}).items() if isinstance(v, dict)}


def _save_history(today: date, counts: dict[str, float]) -> None:
    days = _history()
    days[today.isoformat()] = {k: round(v, 3) for k, v in counts.items() if v > 0}
    cutoff = (today - timedelta(days=HISTORY_DAYS)).isoformat()
    days = {d: v for d, v in days.items() if d >= cutoff}
    ensure_dirs()
    write_json(SKILLS_HISTORY_FILE, {"days": days})


def _earlier_level(history: dict[str, dict[str, float]], skill: str, today: date) -> float | None:
    """The skill's average daily count 3-8 weeks ago, if myGeeKy ran then."""
    lo, hi = (today - timedelta(days=56)).isoformat(), (today - timedelta(days=21)).isoformat()
    values = [v.get(skill, 0.0) for d, v in history.items() if lo <= d <= hi]
    return sum(values) / len(values) if len(values) >= 3 else None


def rising(cfg: MyGeekyConfig, docs: list[dict[str, Any]] | None = None, mine: str | None = None,
           weights: dict[str, float] | None = None, today: date | None = None, save: bool = True,
           top: int = TOP) -> dict[str, Any]:
    """{"skills": [...suggested, best first], "strengths": [...rising skills you already have],
        "hidden": n, "documents": n}. Each skill: name, kind, score, reasons, examples, vote."""
    from . import interests
    today = today or date.today()
    now = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) + timedelta(hours=12)
    docs = field_documents() if docs is None else docs
    mine_text = own_text(cfg) if mine is None else mine
    have = skills_in(mine_text)
    if cfg.github_username:
        have.add("Git")                    # you're on GitHub: Git is yours already
    w = interests.profile_terms(cfg) if weights is None else weights
    lean_w = taste.weights(["skill", "resource"])
    votes = taste.load()

    recent: dict[str, float] = defaultdict(float)
    older: dict[str, float] = defaultdict(float)
    close: dict[str, float] = defaultdict(float)
    hits: dict[str, int] = defaultdict(int)
    by_source: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    examples: dict[str, list[dict[str, str]]] = defaultdict(list)
    for d in docs:
        found = skills_in(d["text"])
        if not found:
            continue
        weight = SOURCES.get(d["source"], ("", "", 0.5))[2]
        age = (now - d["when"]).days if d["when"] else None
        fit = interests.match(d["text"], w)[0] if w else 0.5
        for s in found:
            hits[s] += 1
            by_source[s][d["source"]] += 1
            close[s] += fit
            if age is None or age <= RECENT_DAYS:
                recent[s] += weight
            else:
                older[s] += weight * min(1.0, RECENT_DAYS / max(age, 1))
            if (d.get("url") and len(examples[s]) < 3 and d["source"] in ("paper", "tool", "repo", "contribute")
                    and all(e["url"] != d["url"] for e in examples[s])):
                examples[s].append({"title": d["title"], "url": d["url"], "source": SOURCES[d["source"]][0]})

    history = _history()
    if save and docs:
        _save_history(today, dict(recent))

    def score_of(s: str) -> tuple[float, float, bool]:
        momentum = math.log1p(recent[s] + 0.5 * older[s])
        growth = (recent[s] + 1.0) / (older[s] + 1.0)
        before = _earlier_level(history, s, today)
        if before is not None:
            growth = 0.5 * growth + 0.5 * (recent[s] + 1.0) / (before + 1.0)
        growth = max(0.5, min(growth, 3.0))
        closeness = close[s] / max(hits[s], 1)
        # "rising" is only claimed against something earlier: older mentions, or past days' counts
        up = growth >= 1.3 and (before is not None or older[s] > 0)
        return momentum * growth * (0.4 + 0.6 * closeness), growth, up

    out, strengths, hidden = [], [], 0
    for s in vocabulary():
        name = s["name"]
        if hits[name] < MIN_DOCS:
            continue
        v = int(votes.get(taste.key_of("skill", name), {}).get("vote", 0))
        base, growth, up = score_of(name)
        tilt = taste.lean(name, s["aliases"][:3], lean_w)
        score = base * (1 + 0.5 * tilt) * (1.3 if v > 0 else 1.0)
        reasons = [_said(src, n) for src, n in sorted(by_source[name].items(), key=lambda kv: kv[1], reverse=True)[:3]]
        row = {"name": name, "kind": s["kind"], "score": round(score, 4), "growth": round(growth, 2),
               "mentions": hits[name], "reasons": reasons, "examples": examples[name], "vote": v,
               "rising": up}
        if name in have:
            strengths.append(row)
        elif v < 0:
            hidden += 1
        else:
            out.append(row)
    out.sort(key=lambda r: r["score"], reverse=True)
    strengths.sort(key=lambda r: r["score"], reverse=True)
    return {"skills": out[:top], "strengths": strengths[:8], "hidden": hidden, "documents": len(docs),
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


# --------------------------------------------------------------------------- learning paths
def _paths() -> dict[str, dict[str, Any]]:
    data = read_json(PATHS_FILE, {}) or {}
    paths = data.get("paths") if isinstance(data, dict) else None
    return {k: v for k, v in (paths or {}).items() if isinstance(v, dict)}


def _save_paths(paths: dict[str, dict[str, Any]]) -> None:
    ensure_dirs()
    write_json(PATHS_FILE, {"paths": paths}, indent=1)


def start_path(skill: str) -> bool:
    s = find(skill)
    if not s:
        return False
    paths = _paths()
    paths.setdefault(s["name"], {"started_at": date.today().isoformat(), "done": []})
    _save_paths(paths)
    return True


def stop_path(skill: str) -> None:
    paths = _paths()
    paths.pop(skill, None)
    _save_paths(paths)


def tick(skill: str, step: str, done: bool = True) -> None:
    paths = _paths()
    if skill not in paths:
        return
    steps = [x for x in paths[skill].get("done") or [] if x != step]
    if done:
        steps.append(step)
    paths[skill]["done"] = steps
    _save_paths(paths)


def _search(skill: str, what: str) -> str:
    return f"https://github.com/search?q={quote_plus(skill + ' ' + what)}&type=repositories&s=stars"


def path_steps(cfg: MyGeekyConfig, skill: str, data: dict[str, Any] | None = None,
               mine: str | None = None, docs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The four steps for `skill`: [{"id", "title", "detail", "url", "done", "auto"}]."""
    s = find(skill) or {"name": skill, "aliases": [skill.lower()], "pattern": re.compile(re.escape(skill), re.I)}
    state = _paths().get(s["name"], {})
    done = set(state.get("done") or [])
    resources = curated.for_skill(s["name"], s["aliases"], data)
    basics = next((r for r in resources if r.get("level") in ("beginner", "")), resources[0] if resources else None)
    deeper = next((r for r in resources if r is not basics and r.get("level") in ("intermediate", "advanced")),
                  next((r for r in resources if r is not basics), None))
    docs = field_documents() if docs is None else docs
    project = next((d for d in docs if d["source"] in ("repo", "contribute", "tool") and d.get("url")
                    and s["pattern"].search(d["text"])), None)
    yours = s["pattern"].search(repos_text()) is not None
    in_profile = s["pattern"].search(own_text(cfg) if mine is None else mine) is not None
    steps = [
        {"id": "basics", "title": "Learn the basics",
         "detail": basics["title"] if basics else f"Find a beginner tutorial on {s['name']}",
         "url": basics["url"] if basics else _search(s["name"], "tutorial"), "auto": False},
        {"id": "deeper", "title": "Go deeper",
         "detail": deeper["title"] if deeper else f"Read how experienced people use {s['name']}",
         "url": deeper["url"] if deeper else _search(s["name"], "awesome"), "auto": False},
        {"id": "practice", "title": "Practise on a real project",
         "detail": (f"Read and run {project['title']}" if project else f"Run a small {s['name']} project from your field"),
         "url": project["url"] if project else _search(s["name"], "example"), "auto": False},
        {"id": "use", "title": "Use it in your own work",
         "detail": ("Done: it's in one of your repos" if yours else
                    "Done: it's in your profile" if in_profile else
                    f"Push a repo that uses {s['name']} (ticks itself), then add it to your CV"),
         "url": "", "auto": True},
    ]
    for st in steps:
        st["done"] = (yours or in_profile) if st["auto"] else st["id"] in done
    return steps


def paths(cfg: MyGeekyConfig, data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Your started paths with their steps and progress, the least finished first."""
    docs = field_documents()
    mine = own_text(cfg)
    out = []
    for name, st in _paths().items():
        steps = path_steps(cfg, name, data, mine=mine, docs=docs)
        n = sum(1 for x in steps if x["done"])
        out.append({"skill": name, "started_at": st.get("started_at", ""), "steps": steps,
                    "done": n, "total": len(steps), "finished": n == len(steps)})
    return sorted(out, key=lambda p: (p["finished"], p["started_at"]))
