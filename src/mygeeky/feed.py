"""🏠 Home: one scrolling feed of everything myGeeKy already found for you (the first page on both apps).

Built only from what the other pages already keep (WISEP's answers, the curated lists, your circle's new work...):
scrolling never asks the internet, and works offline. Each card is a plain dict:

    {"id", "kind", "title", "sub", "url", "at" (YYYY-MM-DD...), "terms": [..], "source", "page" (where "more" goes)}

The order is decided here, the same way on the phone (mobile/src/lib/feed.ts; tests/test_feed.py checks both agree):

- **fit**: how well the card matches you -- your Model's terms with their weights (interests.profile_terms, which
  already holds your keywords, field, CV, what you click and your 👍/👎), matched as whole words;
- **freshness**: new things first, each kind fading at its own pace (a headline in two days, a paper in two weeks);
- **what you've seen**: a card seen without a tap sinks a little each time; one you opened moves to "older";
- **what kinds you enjoy**: a small bandit (UCB1) over the card kinds, learned from taps, time on screen and quick
  skips, so papers get more room if you read papers -- with an optimistic bonus that keeps trying every kind;
- **variety**: at most two of a kind in any four cards, no source taking more than three of any ten, and one card in five
  kept for new territory 🔭 (cards that match nothing of yours), like explore_share elsewhere.

Every card carries a short "why" ("matches GWAS · new today"). Deterministic (no randomness): the same inputs give
the same feed on both apps. What it learns is kept in feed.json (synced with your other computers, like your Model).
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any

# kind -> (label, emoji, days for its freshness to halve)
KINDS: dict[str, tuple[str, str, float]] = {
    "work": ("New work from your circle", "📄", 21),
    "paper": ("Rising in your field", "🔬", 14),
    "news": ("Papers & discussions", "💬", 4),
    "headline": ("Headline", "🗞", 2),
    "job": ("Job", "💼", 21),
    "funding": ("Funding", "💶", 30),
    "conference": ("Conference", "🎤", 30),
    "dataset": ("Dataset", "🗂", 30),
    "repo": ("Repo to help", "📦", 14),
    "rising": ("Rising repo", "📈", 7),
    "person": ("Someone to meet", "👥", 14),
    "model": ("AI model", "🤗", 7),
    "highlight": ("Highlight", "✨", 30),
    "skill": ("Rising skill", "🧠", 30),
    "quiz": ("Quiz", "🏆", 3650),
}
# each kind's colour: the outline and glow of its card (Neon), the same on both apps
KIND_COLORS: dict[str, str] = {
    "work": "#ff8fab", "paper": "#eab308", "news": "#2dd4bf", "headline": "#a5b4fc", "job": "#f87171",
    "funding": "#fb923c", "conference": "#f472b6", "dataset": "#4ade80", "repo": "#7fd8ff", "rising": "#38bdf8",
    "person": "#ff6fd8", "model": "#c084fc", "highlight": "#facc15", "skill": "#34d399", "quiz": "#ffd24a",
}
DEADLINE_KINDS = ("job", "funding", "conference")
RING_DAYS = 60               # a deadline's ring is full at this many days left
SAVED_KEEP = 100
EXPLORE_EVERY = 5            # one card in five: new territory
SAME_KIND_RUN = 2            # at most two of a kind in any four cards in a row
SOURCE_WINDOW, SOURCE_MAX = 10, 3
STATS_HALF_LIFE = 30.0       # days for what it learned about a kind to count half
READ_SECONDS, SKIP_SECONDS = 4.0, 1.0
SEEN_KEEP = 2000


def r4(x: float) -> float:
    """Rounded as JavaScript's Math.round does, so both apps rank identically."""
    return math.floor(x * 10000 + 0.5) / 10000


def _text(card: dict[str, Any]) -> str:
    raw = " ".join([str(card.get("title") or ""), str(card.get("sub") or ""), *[str(t) for t in card.get("terms") or []]])
    return " " + re.sub(r"[^a-z0-9+#]+", " ", raw.lower()) + " "


def fit(card: dict[str, Any], weights: dict[str, float]) -> tuple[float, list[str]]:
    """(0..1, the terms that matched, best first): the best match counts fully, the next ones a little."""
    text = _text(card)
    hits: list[tuple[float, str]] = []
    for term, w in weights.items():
        key = " " + re.sub(r"[^a-z0-9+#]+", " ", term.lower()).strip() + " "
        if len(key) > 3 and key in text:
            hits.append((float(w), term))
    hits.sort(key=lambda h: (-h[0], h[1]))
    score = sum(w * f for (w, _), f in zip(hits, (1.0, 0.3, 0.15)))
    return r4(min(1.0, score)), [t for _, t in hits[:3]]


def age_days(card: dict[str, Any], today: str) -> int:
    try:
        return max(0, (date.fromisoformat(today[:10]) - date.fromisoformat(str(card.get("at") or "")[:10])).days)
    except ValueError:
        return 30                    # no date: treated as a month old


def freshness(card: dict[str, Any], today: str) -> float:
    half = KINDS.get(card.get("kind", ""), ("", "", 14))[2]
    return r4(0.5 ** (age_days(card, today) / half))


def seen_factor(seen: dict[str, Any], cid: str) -> float:
    s = seen.get(cid) or {}
    if s.get("opened"):
        return 0.15                  # you opened it: it moves to "older"
    return r4(0.6 ** int(s.get("n") or 0))


def kind_pref(stats: dict[str, dict[str, float]], kind: str) -> float:
    """UCB1 over the kinds: how often this kind pleased you, plus a bonus for kinds tried little."""
    total = sum(float(v.get("s", 0)) + float(v.get("f", 0)) for v in stats.values())
    k = stats.get(kind) or {}
    s, f = float(k.get("s", 0)), float(k.get("f", 0))
    mean = (s + 1) / (s + f + 2)
    bonus = 0.25 * math.sqrt(2 * math.log(total + 2) / (s + f + 1))
    return r4(min(1.25, mean + bonus))


def _one(x: float) -> str:
    v = math.floor(x * 10 + 0.5) / 10
    return str(int(v)) if v == int(v) else f"{v:.1f}"


def short_num(n: Any) -> str:
    """1234 -> "1.2k", 25300 -> "25k", 2100000 -> "2.1M" (the same on the phone)."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    if n < 1000:
        return str(int(n))
    if n < 10000:
        return _one(n / 1000) + "k"
    if n < 1000000:
        return str(int(math.floor(n / 1000 + 0.5))) + "k"
    return _one(n / 1000000) + "M"


def _num(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) and v > 0 else 0.0


def facts_line(card: dict[str, Any]) -> list[str]:
    """The few numbers that make a card worth a look, as short chips ("★ 2.1k", "▲ 40 this week", "3.4 MB")."""
    f = card.get("facts") or {}
    if not isinstance(f, dict):
        return []
    k, out = card.get("kind"), []
    if k == "paper" and _num(f.get("cited")):
        out.append(f"{short_num(f['cited'])} citations")
    elif k in ("rising", "repo"):
        if _num(f.get("stars")):
            out.append(f"★ {short_num(f['stars'])}")
        if k == "rising" and _num(f.get("stars_week")):
            out.append(f"▲ {short_num(f['stars_week'])} this week")
        if f.get("lang"):
            out.append(str(f["lang"])[:20])
        n = int(_num(f.get("starters")))
        if k == "repo" and n:
            out.append(f"{n} starter issue{'s' if n > 1 else ''}")
    elif k == "dataset":
        mb = _num(f.get("size_mb"))
        if mb:
            out.append(f"{_one(mb * 1000)} KB" if mb < 1 else f"{_one(mb)} MB" if mb < 1024 else f"{_one(mb / 1024)} GB")
        if f.get("license"):
            out.append(str(f["license"]).upper()[:20])
    elif k == "model":
        if _num(f.get("downloads")):
            out.append(f"⬇ {short_num(f['downloads'])}")
        if _num(f.get("likes")):
            out.append(f"♡ {short_num(f['likes'])}")
    elif k == "person":
        if _num(f.get("followers")):
            out.append(f"{short_num(f['followers'])} followers")
        if _num(f.get("repos")):
            out.append(f"{short_num(f['repos'])} repos")
    return out


def days_left(card: dict[str, Any]) -> int | None:
    d = (card.get("facts") or {}).get("days") if isinstance(card.get("facts"), dict) else None
    return int(d) if isinstance(d, (int, float)) and not isinstance(d, bool) and d >= 0 else None


def milestone(cards: list[dict[str, Any]], today: str) -> dict[str, str] | None:
    """One thing worth celebrating at the top of Home, or None: your circle's new papers, deadlines this week, a
    batch of new datasets."""
    work = [c for c in cards if c.get("kind") == "work" and age_days(c, today) <= 7]
    if len(work) >= 2:
        return {"emoji": "🎉", "title": f"{len(work)} new papers from your circle this week",
                "sub": "See them all in Researchers", "page": "researchers:new"}
    due = sorted((c for c in cards if c.get("kind") in DEADLINE_KINDS and (days_left(c) is not None and days_left(c) <= 7)),
                 key=lambda c: (days_left(c), c.get("id", "")))
    if due:
        first, d = due[0], days_left(due[0])
        when = "today" if d == 0 else "tomorrow" if d == 1 else f"in {d} days"
        return {"emoji": "⏳", "title": f"{len(due)} deadline{'s' if len(due) > 1 else ''} this week",
                "sub": f"The first closes {when}: {str(first.get('title') or '')[:70]}", "page": first.get("page", "")}
    data = [c for c in cards if c.get("kind") == "dataset" and age_days(c, today) <= 1]
    if len(data) >= 3:
        return {"emoji": "🗂", "title": f"{len(data)} new datasets for you today", "sub": "See them in Data",
                "page": "grow:data:new"}
    return None


def caught_up(new: int, liked: int = 0, saved: int = 0) -> str:
    bits = [f"{new} new"] + ([f"{liked} liked"] if liked else []) + ([f"{saved} saved"] if saved else [])
    return "✓ You're all caught up · " + ", ".join(bits)


def _why(card: dict[str, Any], terms: list[str], age: int, explore: bool, pref: float) -> str:
    bits = []
    if explore:
        bits.append("new territory \U0001f52d")
    elif terms:
        bits.append("matches " + ", ".join(terms[:2]))
    bits.append("new today" if age == 0 else "yesterday" if age == 1 else f"{age} days ago" if age < 30 else "older")
    if pref >= 0.85 and not explore:
        bits.append(f"you often open {KINDS.get(card.get('kind', ''), ('these',))[0].lower()}")
    return " · ".join(bits)


def score_all(cards: list[dict[str, Any]], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Every card with its score, fit, freshness and why (not yet arranged)."""
    today, weights = ctx["today"], ctx.get("weights") or {}
    seen, stats = ctx.get("seen") or {}, ctx.get("stats") or {}
    out = []
    for c in cards:
        f, terms = fit(c, weights)
        fr = freshness(c, today)
        pref = kind_pref(stats, c.get("kind", ""))
        sf = seen_factor(seen, c["id"])
        explore = f == 0
        score = r4((0.6 * f + 0.4 * fr) * (0.5 + pref) * sf) if not explore else r4(fr * sf * 0.6)
        out.append({"card": c, "score": score, "fit": f, "fresh": fr, "explore": explore,
                    "seen": bool((seen.get(c["id"]) or {}).get("n") or (seen.get(c["id"]) or {}).get("opened")),
                    "why": _why(c, terms, age_days(c, today), explore, pref)})
    return out


def arrange(cards: list[dict[str, Any]], ctx: dict[str, Any], n: int = 60) -> list[dict[str, Any]]:
    """The feed: unseen cards first (best first, with variety and one in five new territory), then -- after
    "You're all caught up" -- what you've already seen, best first. Each item: {card, score, why, explore, seen}."""
    key = lambda x: (-x["score"], x["card"]["id"])             # noqa: E731
    scored, titles = [], set()
    for x in sorted(score_all(cards, ctx), key=key):         # the same story from two places shows once (the better)
        t = re.sub(r"[^a-z0-9]+", " ", str(x["card"].get("title") or "").lower()).strip()[:80]
        if t and t in titles:
            continue
        titles.add(t)
        scored.append(x)
    fresh_main = sorted([x for x in scored if not x["seen"] and not x["explore"]], key=key)
    fresh_explore = sorted([x for x in scored if not x["seen"] and x["explore"]], key=key)
    older = sorted([x for x in scored if x["seen"]], key=key)
    picked: list[dict[str, Any]] = []
    while len(picked) < n and (fresh_main or fresh_explore):
        if fresh_explore and (len(picked) + 1) % EXPLORE_EVERY == 0 or not fresh_main:
            picked.append(fresh_explore.pop(0))
            continue
        kinds = [x["card"]["kind"] for x in picked[-(SAME_KIND_RUN + 1):]]
        window = [x["card"].get("source", "") for x in picked[-(SOURCE_WINDOW - 1):]]
        choice = 0
        for i, x in enumerate(fresh_main):
            run = kinds.count(x["card"]["kind"]) >= SAME_KIND_RUN
            crowded = window.count(x["card"].get("source", "")) >= SOURCE_MAX
            if not run and not crowded:
                choice = i
                break
        picked.append(fresh_main.pop(choice))
    return picked + older[: max(0, n - len(picked))]


def learn(stats: dict[str, dict[str, float]], kind: str, what: str, dwell: float = 0.0,
          days_since: float = 0.0) -> dict[str, dict[str, float]]:
    """What a card taught: `what` is "open", "up", "down" or "view" (with `dwell` seconds on screen). Older lessons
    fade with STATS_HALF_LIFE (`days_since` the last one)."""
    decay = 0.5 ** (max(0.0, days_since) / STATS_HALF_LIFE)
    out = {k: {"s": r4(float(v.get("s", 0)) * decay), "f": r4(float(v.get("f", 0)) * decay)} for k, v in stats.items()}
    k = out.setdefault(kind, {"s": 0.0, "f": 0.0})
    if what in ("open", "up", "save"):
        k["s"] = r4(k["s"] + 1)
    elif what == "down":
        k["f"] = r4(k["f"] + 1)
    elif what == "view":
        if dwell >= READ_SECONDS:
            k["s"] = r4(k["s"] + 0.5)
        elif dwell < SKIP_SECONDS:
            k["f"] = r4(k["f"] + 0.25)
    return out


def mark_seen(seen: dict[str, Any], cid: str, opened: bool, today: str) -> dict[str, Any]:
    out = dict(seen)
    s = dict(out.get(cid) or {})
    s["n"] = int(s.get("n") or 0) + (0 if opened else 1)
    s["opened"] = bool(s.get("opened") or opened)
    s["at"] = today[:10]
    out[cid] = s
    if len(out) > SEEN_KEEP:                                    # the oldest go first
        for old in sorted(out, key=lambda k: (out[k].get("at", ""), k))[: len(out) - SEEN_KEEP]:
            out.pop(old, None)
    return out


def interest_kind(card: dict[str, Any]) -> str:
    """How much an opened card teaches the Model (interests.KIND_WEIGHTS)."""
    return "repo" if card.get("kind") in ("repo", "rising", "model") else "person" if card.get("kind") == "person" else "news"


def interest_text(card: dict[str, Any]) -> str:
    """What an opened card teaches the Model: its title -- not the authors' names or "closes in 9 days" under it -- and
    for a person, why they were suggested, never their name."""
    return str(card.get("sub") or "") if card.get("kind") == "person" else str(card.get("title") or "")


# --------------------------------------------------------------------------- the store (feed.json)
def load() -> dict[str, Any]:
    from . import files
    from .config import DATA_DIR
    d = files.read_json(DATA_DIR / "feed.json", {})
    d = d if isinstance(d, dict) else {}
    return {"stats": d.get("stats") if isinstance(d.get("stats"), dict) else {},
            "seen": d.get("seen") if isinstance(d.get("seen"), dict) else {},
            "saved": [x for x in d.get("saved") or [] if isinstance(x, dict) and isinstance(x.get("card"), dict)
                      and x["card"].get("id") and x["card"].get("title")][:SAVED_KEEP],
            "learned_at": str(d.get("learned_at") or ""),
            "dwell": d.get("dwell", True) is not False}


def save(state: dict[str, Any]) -> None:
    from .config import DATA_DIR, ensure_dirs
    from .files import write_json
    ensure_dirs()
    write_json(DATA_DIR / "feed.json", state)


def record(kind: str, cid: str, what: str, dwell: float = 0.0, today: str | None = None) -> dict[str, Any]:
    """A tap, a vote, or a card leaving the screen after `dwell` seconds: learn from it and remember it was seen."""
    today = today or date.today().isoformat()
    state = load()
    if what == "view" and not state["dwell"]:
        return state                                            # time on screen switched off
    since = 0.0
    if state["learned_at"]:
        try:
            since = float((date.fromisoformat(today) - date.fromisoformat(state["learned_at"])).days)
        except ValueError:
            since = 0.0
    state["stats"] = learn(state["stats"], kind, what, dwell, since)
    state["learned_at"] = today
    if what in ("open", "view"):
        state["seen"] = mark_seen(state["seen"], cid, what == "open", today)
    save(state)
    return state


def toggle_save(card: dict[str, Any], today: str | None = None) -> bool:
    """🔖: keep a card in Saved (newest first), or take it out. Saving teaches like ♡. Returns whether it's saved now."""
    today = today or date.today().isoformat()
    state = load()
    saved = [x for x in state["saved"] if x["card"].get("id") != card.get("id")]
    now = len(saved) == len(state["saved"])
    if now:
        saved.insert(0, {"card": {k: card[k] for k in card if k != "why"}, "at": today[:10]})
        state["stats"] = learn(state["stats"], str(card.get("kind") or ""), "save")
    state["saved"] = saved[:SAVED_KEEP]
    save(state)
    return now


def set_dwell(on: bool) -> None:
    state = load()
    state["dwell"] = bool(on)
    save(state)


# --------------------------------------------------------------------------- the cards (computer): read, never fetch
def _clip(s: Any, n: int = 200) -> str:
    return " ".join(str(s or "").split())[:n]


def _cards_from(rows: Any, limit: int, make) -> list[dict[str, Any]]:
    out = []
    for r in (rows or [])[: limit * 2]:
        if isinstance(r, dict):
            try:
                c = make(r)
            except Exception:
                c = None
            if c and c.get("id") and c.get("title"):
                out.append(c)
        if len(out) >= limit:
            break
    return out


def _quiz_facts(q: dict[str, Any]) -> dict[str, Any]:
    """A choice question can be answered right on its card: its options, which is right, and why."""
    opts = q.get("options")
    ans = q.get("answer")
    if not (isinstance(opts, list) and 2 <= len(opts) <= 6 and isinstance(ans, int) and not isinstance(ans, bool)
            and 0 <= ans < len(opts) and not q.get("code")):
        return {}
    return {"options": [_clip(o, 160) for o in opts], "answer": ans, "why": _clip(q.get("why"), 300)}


def candidates(cfg: Any, today: str | None = None) -> list[dict[str, Any]]:
    """Everything the other pages already keep, as cards (at most a few dozen per source). Nothing here goes online:
    each source is read from its file, and one that can't be read is simply left out."""
    today = today or date.today().isoformat()
    cards: list[dict[str, Any]] = []

    def add(fn) -> None:
        try:
            cards.extend(fn())
        except Exception:
            pass

    def work():
        from . import researchers
        return _cards_from(researchers.feed(researchers.load(), today), 15, lambda w: {
            "id": f"work:{w['id']}", "kind": "work", "title": _clip(w.get("title")), "url": w.get("url", ""),
            "sub": _clip(" · ".join(x for x in [w.get("venue", ""), ", ".join((w.get("names") or [])[:2])] if x)),
            "at": w.get("date", ""), "terms": [], "source": "researchers", "page": "researchers:new"})

    def papers_():
        from . import papers
        return _cards_from(papers.load_trends().get("rising"), 15, lambda p: {
            "id": f"paper:{p['id']}", "kind": "paper", "title": _clip(p.get("title")), "url": p.get("url", ""),
            "sub": _clip(p.get("venue")), "at": p.get("date", ""), "terms": list(p.get("match") or []),
            "source": "openalex", "page": "market:research", "facts": {"cited": _num(p.get("cited"))}})

    def news_():
        from . import news
        return _cards_from(news.load_state().get("items"), 15, lambda n: {
            "id": f"news:{n['id']}", "kind": "news", "title": _clip(n.get("title")), "url": n.get("url", ""),
            "sub": _clip(n.get("source")), "at": str(n.get("published", ""))[:10], "terms": list(n.get("match") or []),
            "source": str(n.get("source") or "news"), "page": "news:papers"})

    def headlines_():
        from . import headlines
        return _cards_from(headlines.load_state().get("items"), 20, lambda h: {
            "id": f"headline:{h['id']}", "kind": "headline", "title": _clip(h.get("title")), "url": h.get("link", ""),
            "sub": _clip(h.get("source")), "at": str(h.get("published", ""))[:10], "terms": list(h.get("match") or []),
            "source": str(h.get("source") or "headlines"), "page": "news:headlines"})

    def chances():
        from . import curated
        data = curated.load()
        out = []
        for kind, page in (("jobs", "chances:jobs"), ("funding", "chances:funding"), ("conferences", "chances:conferences")):
            k = {"jobs": "job", "funding": "funding", "conferences": "conference"}[kind]

            def make(it, k=k, page=page):
                left = curated.days_left(it)
                where = " · ".join(x for x in [it.get("org", ""), it.get("place", "")] if x)
                return {"id": f"{k}:{it['id']}", "kind": k, "title": _clip(it.get("title")), "url": it.get("url", ""),
                        "sub": _clip(where),                       # the days left are on the card's ring
                        "at": str(it.get("added") or it.get("checked") or ""), "terms": list(it.get("keywords") or []),
                        "source": "curated", "page": page, "facts": {} if left is None else {"days": left}}
            out += _cards_from(curated.live(data.get(kind) or []), 12, make)
        out += _cards_from(data.get("highlights"), 6, lambda h: {
            "id": f"highlight:{h['id']}", "kind": "highlight", "title": _clip(h.get("title")), "url": h.get("url", ""),
            "sub": _clip(h.get("hook"), 160), "at": str(h.get("added") or ""),
            "terms": list(h.get("keywords") or []) + list(h.get("skills") or []), "source": "highlights",
            "page": "grow:highlights"})
        return out

    def radar():
        from . import datasets
        return _cards_from(datasets.radar_load().get("items"), 12, lambda d: {
            "id": f"dataset:{d['id']}", "kind": "dataset", "title": _clip(d.get("title")), "url": d.get("url", ""),
            "sub": _clip(" · ".join(x for x in [d.get("source", ""), d.get("term", "")] if x)),
            "at": str(d.get("found") or d.get("date") or ""), "terms": [d.get("term", "")] if d.get("term") else [],
            "source": str(d.get("source") or "datasets"), "page": "grow:data:new",
            "facts": {"size_mb": _num(d.get("size_mb")), "license": _clip(d.get("license"), 20)}})

    def repos():
        from . import storage
        return _cards_from(storage.contribution_pool(), 12, lambda r: {
            "id": f"repo:{r['full_name']}", "kind": "repo", "title": _clip(r.get("full_name")), "url": r.get("repo_url", ""),
            "sub": _clip(r.get("description"), 160), "at": str(r.get("pushed_at") or r.get("timestamp") or "")[:10],
            "terms": list(r.get("topics") or []) + list(r.get("matched_terms") or []), "source": "github", "page": "repos",
            "facts": {"stars": _num(r.get("stars")), "lang": _clip(r.get("language"), 20),
                      "starters": len(r.get("starter_issues") or []) if isinstance(r.get("starter_issues"), list) else 0}})

    def rising():
        from . import market
        return _cards_from(market.compute_board(market.load_state()), 10, lambda r: {
            "id": f"rising:{r['repo']}", "kind": "rising", "title": _clip(r.get("repo")), "url": r.get("url", ""),
            "sub": _clip(r.get("description"), 160), "at": str(r.get("pushed_at") or "")[:10],
            "terms": [r.get("language", "")] if r.get("language") else [], "source": "market", "page": "market:repos",
            "facts": {"stars": _num(r.get("stars")), "stars_week": _num(r.get("stars_week")), "lang": _clip(r.get("language"), 20)}})

    def people():
        from . import storage
        return _cards_from(storage.suggestion_pool("domain"), 10, lambda p: {
            "id": f"person:{p['username']}", "kind": "person", "title": _clip(p.get("username")),
            "url": p.get("profile_url", ""), "sub": _clip(p.get("bio"), 160), "at": str(p.get("timestamp") or "")[:10],
            "terms": [], "source": "people", "page": "suggestions",
            "facts": {"followers": _num(p.get("followers")), "repos": _num(p.get("public_repos"))}})

    def models():
        from . import hfmodels
        return _cards_from(hfmodels.load_state().get("field"), 8, lambda m: {
            "id": f"model:{m['id']}", "kind": "model", "title": _clip(m.get("id")), "url": m.get("url", ""),
            "sub": _clip(m.get("pipeline")), "at": str(m.get("created") or ""), "terms": list(m.get("match") or m.get("tags") or [])[:8],
            "source": "huggingface", "page": "market:models",
            "facts": {"downloads": _num(m.get("downloads")), "likes": _num(m.get("likes"))}})

    def quiz_():
        from . import quiz
        qs = [q for q in quiz.bank().get("questions") or [] if isinstance(q, dict) and q.get("q")]
        if not qs:
            return []
        day = date.fromisoformat(today).toordinal()
        picks = [qs[(day * 7 + i * 13) % len(qs)] for i in range(2)]          # two a day, the same on every start
        return [{"id": f"quiz:{q.get('id', i)}:{today}", "kind": "quiz", "title": _clip(q.get("q"), 220),
                 "sub": _clip(q.get("protocol")), "url": "", "at": today, "terms": [str(q.get("protocol") or "")],
                 "source": "quiz", "page": "grow:quiz", "facts": _quiz_facts(q)} for i, q in enumerate(picks)]

    for fn in (work, papers_, news_, headlines_, chances, radar, repos, rising, people, models, quiz_):
        add(fn)
    seen, unique = set(), []
    for c in cards:
        if c["id"] not in seen:
            seen.add(c["id"])
            unique.append(c)
    return unique


def build(cfg: Any, n: int = 60, today: str | None = None) -> list[dict[str, Any]]:
    """The Home feed, ready to show: your weights (profile_terms, once), what it learned, what you've seen."""
    today = today or date.today().isoformat()
    try:
        from . import interests
        weights = interests.profile_terms(cfg)
    except Exception:
        weights = {}
    state = load()
    return arrange(candidates(cfg, today), {"today": today, "weights": weights, "seen": state["seen"],
                                            "stats": state["stats"]}, n)
