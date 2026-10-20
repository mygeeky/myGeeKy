"""Rising Skills: what to learn next (protocols.py turns a skill into stages).

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

**Protocols** (protocols.py) turn a skill into ordered stages, with a level
check; they replace the four-step learning paths that used to live here.

**Is it really rising?** What myGeeKy reads for you is mostly picked by your
interests, so counting it alone can't tell "the field is moving" from "you
started reading about it". Growth is therefore measured only on documents no
one picked for you -- the explore share of your feeds and the shared world
file (skilltrends.py) -- and a skill counts as rising only when that growth is
clear for how few mentions it has (`corrected`). What you chose to read decides
only what's close to you. A skill busy mostly in your own feed is "rising in
your feed only"; one rising in the world but rare in your feed is "rising
beyond your usual". `shapes` turns the result into the four views.

Everything here is local: it reads files myGeeKy already saved (and the world
file), and sends nothing.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from . import taste
from .config import (ACTIVITY_CACHE_FILE, BEACON_CACHE_FILE, CV_TEXT_FILE, DATA_DIR, HEADLINES_FILE, HF_MODELS_FILE,
                     MARKET_FILE, NEWS_FILE, SKILLS_HISTORY_FILE, TRENDS_FILE, MyGeekyConfig, ensure_dirs)
from .files import read_json, read_jsonl, write_json

BUNDLED = Path(__file__).parent / "data" / "skills.json"
CONTRIBUTE_LOG = DATA_DIR / "contribute_history.jsonl"
SUGGESTIONS_LOG = DATA_DIR / "suggestions_history.jsonl"
RECENT_DAYS = 45
HISTORY_DAYS = 120
TOP = 12
MIN_DOCS = 2                # a skill seen in a single place isn't a trend
SURE_Z = 1.28               # "sure it's rising": the lower edge of an 80% interval on its growth ...
SURE_ABOVE = 1.1            # ... is above 1.1x
MIN_EVIDENCE = 3            # world mentions needed before its growth counts at all
LENS_LOW, LENS_HIGH = 0.7, 2.0   # your feed's share of a skill against the world's: rare / mostly yours

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


# What you said you mostly do (cfg.work_style) tilts which *kinds* of skill come up first. It never
# hides a kind: someone who mostly analyses data should still see a language rising, and the other way
# round. myGeeKy only ever covers work at a computer (safety.py), so these are kinds of that work.
STYLE_TILT = {
    "code": {"language": 1.15, "tool": 1.1, "method": 1.0},
    "analysis": {"method": 1.15, "language": 1.05, "tool": 1.0},
    "both": {"language": 1.05, "method": 1.05, "tool": 1.0},
}


def style_weight(style: str, kind: str) -> float:
    return STYLE_TILT.get(style or "", {}).get(kind, 1.0)

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

    def add(text: str, when: Any, source: str, url: str = "", title: str = "", wide: bool = False) -> None:
        if text and text.strip():
            docs.append({"text": text[:3000], "when": _when(when), "source": source, "url": url, "title": title[:140],
                         "pick": "wide" if wide else "mine"})

    trends = read_json(TRENDS_FILE, {}) or {}
    for kind, source in (("rising", "paper"), ("tools", "tool")):
        for p in trends.get(kind) or []:
            if isinstance(p, dict):
                add(f"{p.get('title', '')} ; {str(p.get('abstract', ''))[:1500]}", p.get("date"), source,
                    p.get("url", ""), p.get("title", ""), p.get("explore") is True)
    news = read_json(NEWS_FILE, {}) or {}
    for n in news.get("items") or []:
        if isinstance(n, dict):
            add(f"{n.get('title', '')} ; {n.get('summary', '')}", n.get("published"), "discussion",
                n.get("url", ""), n.get("title", ""), n.get("explore") is True)
    heads = read_json(HEADLINES_FILE, {}) or {}
    for h in heads.get("items") or []:
        if isinstance(h, dict) and (h.get("match") or h.get("explore") is True):   # yours, or picked to widen it
            add(h.get("title", ""), h.get("published"), "news", h.get("link", ""), h.get("title", ""),
                h.get("explore") is True)
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
                f"{c.get('language', '')}", c.get("pushed_at"), "contribute", c.get("repo_url", ""), c.get("full_name", ""),
                c.get("explore") is True)
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


# --------------------------------------------------------------------------- is it really rising?
def _round(x: float, places: int = 4) -> float:
    """Rounded as JavaScript's Math.round does (halves up), so both apps agree."""
    k = 10 ** places
    return math.floor(x * k + 0.5) / k


def corrected(docs: list[dict[str, Any]], trends: dict[str, Any], feed_growth: dict[str, float]) -> dict[str, dict[str, Any]]:
    """Growth measured where no one picked for you. `docs`: [{"skills": names, "pick": "mine"|"wide", "recent": bool}];
    `trends`: the shared world file (skilltrends.clean); `feed_growth`: growth over everything you read.
    For each skill: growth (x, with an 80% interval lo..hi), sure (rising for certain), how often it shows in your
    feed and in the world (share of documents), lens (yours / world's), self_made and beyond."""
    t_old, t_new = trends.get("docs") or [0, 0]
    n = {"old": t_old, "new": t_new, "mine": 0}
    old: dict[str, float] = defaultdict(float)
    new: dict[str, float] = defaultdict(float)
    mine: dict[str, int] = defaultdict(int)
    for name, (o, r) in (trends.get("skills") or {}).items():
        old[name] += o
        new[name] += r
    for d in docs:
        if d["pick"] == "wide":
            side = new if d["recent"] else old
            n["new" if d["recent"] else "old"] += 1
            for s in d["skills"]:
                side[s] += 1
        else:
            n["mine"] += 1
            for s in d["skills"]:
                mine[s] += 1
    out = {}
    world_n = n["old"] + n["new"]
    for s in sorted(set(old) | set(new) | set(mine)):
        o, r = old[s], new[s]
        lg = math.log(((r + 0.5) / (n["new"] + 1)) / ((o + 0.5) / (n["old"] + 1)))
        se = math.sqrt(1 / (r + 0.5) + 1 / (o + 0.5))
        world = (o + r) / world_n if world_n else 0.0
        yours = mine[s] / n["mine"] if n["mine"] else 0.0
        lens = yours / max(world, 0.5 / (world_n + 1)) if n["mine"] else 1.0
        evidence = o + r >= MIN_EVIDENCE
        sure = evidence and lg - SURE_Z * se > math.log(SURE_ABOVE)
        out[s] = {"growth": _round(math.exp(lg), 2) if evidence else None,
                  "lo": _round(math.exp(lg - SURE_Z * se), 2), "hi": _round(math.exp(lg + SURE_Z * se), 2),
                  "sure": sure, "mine": _round(yours), "world": _round(world), "lens": _round(lens, 2),
                  "self_made": not sure and feed_growth.get(s, 1.0) >= 1.3 and lens >= LENS_HIGH,
                  "beyond": sure and lens < LENS_LOW}
    return out


def note(s: dict[str, Any]) -> str:
    """One line on whether a skill is really rising, under its card (the same words on the phone)."""
    g = s.get("growth")
    if s.get("beyond"):
        return f"🌍 Rising beyond your usual: ×{g:g} in new preprints across the field, rare in your feed"
    if s.get("rising"):
        return f"📈 Sure it's rising: ×{g:g} in new preprints across the field (×{s['lo']:g} to ×{s['hi']:g})"
    if s.get("self_made"):
        return "🪞 Busy in your feed only: it follows what you chose to read, not the field"
    return ""


def _ratio(r: dict[str, Any]) -> float:
    return (r["mine"] + 0.002) / (r["world"] + 0.002)


def shapes(result: dict[str, Any]) -> dict[str, Any]:
    """The four views of Rising skills, from `rising()`'s answer:
    next   -- for each suggestion, the skill of yours that leads there (and how many more of yours do);
    flow   -- bands from your skills to suggestions, as wide as the documents they share;
    ladder -- your rising strengths joined to the suggestions they appear with;
    lens   -- skills you see more than the world does, and the other way round."""
    sug, strong = result.get("skills") or [], result.get("strengths") or []
    names = [s["name"] for s in sug]
    links = result.get("links") or []
    nxt = []
    for s in sug[:6]:
        ls = [lk for lk in links if lk[1] == s["name"]]
        nxt.append({"name": s["name"], "via": ls[0][0] if ls else "", "more": max(0, len(ls) - 1),
                    "weight": sum(lk[2] for lk in ls), "sure": bool(s.get("rising")), "beyond": bool(s.get("beyond"))})
    total: dict[str, int] = defaultdict(int)
    for h, s, k in links:
        if s in names[:8]:
            total[h] += k
    left = [h for h, _ in sorted(total.items(), key=lambda kv: (-kv[1], kv[0]))[:6]]
    right = [s for s in names if any(lk[1] == s and lk[0] in left for lk in links)][:7]
    flow = {"left": left, "right": right, "bands": [lk for lk in links if lk[0] in left and lk[1] in right]}
    l_left, l_right = [s["name"] for s in strong[:7]], names[:10]
    ladder = {"left": l_left, "right": l_right, "links": [lk for lk in links if lk[0] in l_left and lk[1] in l_right]}
    rows = [{"name": s["name"], "mine": s.get("mine", 0.0), "world": s.get("world", 0.0), "yours": i < len(strong)}
            for i, s in enumerate(strong + sug) if s.get("mine", 0.0) + s.get("world", 0.0) > 0]
    more_mine = sorted((r for r in rows if r["mine"] > r["world"]), key=lambda r: (-_ratio(r), r["name"]))[:5]
    more_world = sorted((r for r in rows if r["world"] > r["mine"]), key=lambda r: (_ratio(r), r["name"]))[:5]
    return {"next": nxt, "flow": flow, "ladder": ladder, "lens": {"mine": more_mine, "world": more_world}}


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
           top: int = TOP, trends: dict[str, Any] | None = None) -> dict[str, Any]:
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
    seen: list[dict[str, Any]] = []
    pairs: dict[tuple[str, str], int] = defaultdict(int)
    for d in docs:
        found = skills_in(d["text"])
        age = (now - d["when"]).days if d["when"] else None
        seen.append({"skills": found, "pick": d.get("pick", "mine"), "recent": age is None or age <= RECENT_DAYS})
        if not found:
            continue
        for h in found & have:
            for s in found - have:
                pairs[(h, s)] += 1
        weight = SOURCES.get(d["source"], ("", "", 0.5))[2]
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

    from . import skilltrends
    feed = {s["name"]: score_of(s["name"])[1] for s in vocabulary() if hits[s["name"]]}
    world = corrected(seen, skilltrends.load() if trends is None else trends, feed)
    out, strengths, hidden = [], [], 0
    for s in vocabulary():
        name = s["name"]
        if hits[name] < MIN_DOCS:
            continue
        v = int(votes.get(taste.key_of("skill", name), {}).get("vote", 0))
        base, growth, _ = score_of(name)
        c = world.get(name) or {}
        if c.get("growth") is not None:          # the world's growth replaces your feed's in the score
            base = base / growth * max(0.5, min(c["growth"], 3.0))
        if c.get("self_made"):
            base *= 0.6
        tilt = taste.lean(name, s["aliases"][:3], lean_w)
        score = base * (1 + 0.5 * tilt) * (1.3 if v > 0 else 1.0) * style_weight(cfg.work_style, s["kind"])
        reasons = [_said(src, n) for src, n in sorted(by_source[name].items(), key=lambda kv: kv[1], reverse=True)[:3]]
        row = {"name": name, "kind": s["kind"], "score": round(score, 4),
               "growth": c["growth"] if c.get("growth") is not None else round(growth, 2),
               "lo": c.get("lo"), "hi": c.get("hi"), "world": c.get("world", 0.0), "mine": c.get("mine", 0.0),
               "mentions": hits[name], "reasons": reasons, "examples": examples[name], "vote": v,
               "rising": bool(c.get("sure")), "self_made": bool(c.get("self_made")), "beyond": bool(c.get("beyond"))}
        if name in have:
            strengths.append(row)
        elif v < 0:
            hidden += 1
        else:
            out.append(row)
    out.sort(key=lambda r: r["score"], reverse=True)
    strengths.sort(key=lambda r: r["score"], reverse=True)
    shown = {r["name"] for r in out[:top]}
    links = sorted(([h, s, k] for (h, s), k in pairs.items() if s in shown), key=lambda x: (-x[2], x[0], x[1]))[:80]
    return {"skills": out[:top], "strengths": strengths[:8], "hidden": hidden, "documents": len(docs), "links": links,
            "have": sorted(have),                  # the skills you already show (Collaborators reuses them)
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
