"""Careful notifications: only what's worth it, only what you switched on, at most once a day (or a week).

Everything is off until you turn a kind on, in setup or in Settings -> Notifications. When one is on, myGeeKy
looks at what it already has on this device -- Seasons, the jobs, funding and conferences ranked for you,
the papers rising in your field, new Highlights -- and keeps only what is really worth telling:

  * a Season that is open (seen on its page) or expected to open within SEASON_DAYS;
  * a job, funding call or conference that fits you very well (its fit score at least FIT_MIN);
  * one of the TOP_PAPERS papers rising in your field, out in the last NEW_DAYS["papers"] days;
  * a Highlight added in the last NEW_DAYS["highlights"] days.

Each thing is told once (`told` remembers it), and everything due goes into ONE short line ("🗓 A Season
opens in 12 days · 💼 2 jobs that fit you"), never one notification per item; never in your quiet hours.
Nothing is sent anywhere: the apps notify themselves. The phone works the same way (lib/notify.ts;
tests/test_notify.py runs both).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

# id, emoji, what the switch says, a few words under it, the short name in "On: ..."
KINDS: list[tuple[str, str, str, str, str]] = [
    ("seasons", "🗓", "A Season opening", "Scholarships and calls that come back every year", "Seasons"),
    ("jobs", "💼", "A job that fits you very well", "PhD places, postdocs and research jobs", "jobs"),
    ("funding", "💶", "Funding that fits you very well", "Grants, fellowships and travel money", "funding"),
    ("conferences", "🎤", "A conference that fits you very well", "Meetings, workshops and summer schools", "conferences"),
    ("papers", "📄", "An important new paper in your field", "One of the papers rising fastest, just out", "papers"),
    ("highlights", "✨", "A new Highlight", "A research article retold in plain words", "Highlights"),
    ("cited", "📑", "Someone cited your work", "A new paper citing one of yours", "citations"),
    ("datasets", "🗂", "New data on your topics", "Public datasets just out, matching your keywords", "datasets"),
]
ORDER = [k[0] for k in KINDS]
TAB = {"seasons": "chances", "jobs": "chances", "funding": "chances", "conferences": "chances",
       "papers": "papers", "highlights": "grow", "cited": "you", "datasets": "grow"}
EVERY = {"daily": 1, "weekly": 7}
FIT_MIN = 0.7
SEASON_DAYS = 21
NEW_DAYS = {"papers": 45, "highlights": 14, "cited": 14, "datasets": 7}
TOP_PAPERS = 3
MAX_TOLD = 600


def default() -> dict[str, Any]:
    return {"kinds": [], "every": "daily", "quiet": [22, 8]}


def clean_settings(raw: Any) -> dict[str, Any]:
    """Your choices, checked: only known kinds (in their usual order), daily or weekly, quiet hours 0-23."""
    raw = raw if isinstance(raw, dict) else {}
    kinds = raw.get("kinds") if isinstance(raw.get("kinds"), list) else []
    quiet = raw.get("quiet") if isinstance(raw.get("quiet"), list) and len(raw["quiet"]) == 2 else [22, 8]
    hours = [h if isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23 else d for h, d in zip(quiet, (22, 8))]
    return {"kinds": [k for k in ORDER if k in kinds], "every": raw.get("every") if raw.get("every") in EVERY else "daily",
            "quiet": hours}


def in_quiet(s: dict[str, Any], hour: int) -> bool:
    start, end = s["quiet"]
    if start == end:
        return False
    return start <= hour < end if start < end else (hour >= start or hour < end)


def due(s: dict[str, Any], last_sent: str, now: str, hour: int) -> bool:
    """Time to look: something is switched on, it isn't your quiet hours, and a day (or a week) has passed."""
    if not s["kinds"] or in_quiet(s, hour):
        return False
    if not last_sent:
        return True
    try:
        days = (date.fromisoformat(now[:10]) - date.fromisoformat(last_sent[:10])).days
    except ValueError:
        return True
    return days >= EVERY[s["every"]]


def _age(today: str, day: str) -> int | None:
    try:
        return (date.fromisoformat(today[:10]) - date.fromisoformat(str(day)[:10])).days
    except ValueError:
        return None


def candidates(today: str, seasons: Iterable[dict[str, Any]] = (), ranked: dict[str, list[dict[str, Any]]] | None = None,
               papers: Iterable[dict[str, Any]] = (), highlights: Iterable[dict[str, Any]] = (),
               cited: Iterable[dict[str, Any]] = (), datasets: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """Everything worth telling today, as {id, kind, title, days} (days: until it opens or closes, if known)."""
    out: list[dict[str, Any]] = []
    for s in seasons:
        w = s.get("when") or {}
        if w.get("state") == "open":
            if not w.get("confirmed"):
                continue                       # "expected to be open" is a guess, not news
            days = 0
        elif isinstance(w.get("days_to_open"), int) and 0 <= w["days_to_open"] <= SEASON_DAYS:
            days = w["days_to_open"]
        else:
            continue
        out.append({"id": f"season:{s.get('id', '')}:{w.get('opens', '')}", "kind": "seasons",
                    "title": str(s.get("title", "")), "days": days})
    for kind in ("jobs", "funding", "conferences"):
        for it in (ranked or {}).get(kind) or []:
            if isinstance(it.get("score"), (int, float)) and it["score"] >= FIT_MIN:
                out.append({"id": f"{kind}:{it.get('id', '')}", "kind": kind, "title": str(it.get("title", "")),
                            "days": it.get("days_left") if isinstance(it.get("days_left"), int) else None})
    for p in list(papers)[:TOP_PAPERS]:
        age = _age(today, p.get("date", ""))
        if age is not None and 0 <= age <= NEW_DAYS["papers"]:
            out.append({"id": f"paper:{p.get('id', '')}", "kind": "papers", "title": str(p.get("title", "")), "days": None})
    for h in highlights:
        age = _age(today, h.get("added", ""))
        if age is not None and 0 <= age <= NEW_DAYS["highlights"]:
            out.append({"id": f"highlight:{h.get('id', '')}", "kind": "highlights", "title": str(h.get("title", "")),
                        "days": None})
    for c in cited:                           # a paper citing yours, first seen lately (citedby.py)
        age = _age(today, str(c.get("seen", ""))[:10])
        if not c.get("self") and age is not None and 0 <= age <= NEW_DAYS["cited"]:
            out.append({"id": f"cited:{c.get('id', '')}", "kind": "cited", "title": str(c.get("title", "")), "days": None})
    for d in datasets:                        # a dataset on your topics, found lately (datasets.radar_*)
        age = _age(today, str(d.get("found", ""))[:10])
        if age is not None and 0 <= age <= NEW_DAYS["datasets"]:
            out.append({"id": f"dataset:{d.get('id', '')}", "kind": "datasets", "title": str(d.get("title", "")),
                        "days": None})
    return out


def pick(cands: Iterable[dict[str, Any]], told: Iterable[str], s: dict[str, Any]) -> list[dict[str, Any]]:
    """What to tell now: only the kinds you switched on, nothing told before, the most urgent first."""
    seen = set(told)
    chosen = [c for c in cands if c["kind"] in s["kinds"] and c["id"] not in seen]
    return sorted(chosen, key=lambda c: (c["days"] is None, c["days"] if c["days"] is not None else 0,
                                         ORDER.index(c["kind"]), c["title"]))


def _n(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def summary(chosen: list[dict[str, Any]]) -> dict[str, str] | None:
    """One short line for everything chosen, and the tab a tap opens. None when there's nothing."""
    if not chosen:
        return None
    groups: dict[str, list[dict[str, Any]]] = {}
    for c in chosen:
        groups.setdefault(c["kind"], []).append(c)
    pieces = []
    for kind, items in groups.items():
        n = len(items)
        if kind == "seasons":
            if n == 1:
                t, d = items[0]["title"], items[0]["days"]
                t = t if len(t) <= 40 else t[:39] + "…"
                pieces.append(f"🗓 {t} {'is open now' if d == 0 else f'opens in {d} days'}")
            else:
                pieces.append(f"🗓 {n} Seasons open soon")
        elif kind == "jobs":
            pieces.append(f"💼 {_n(n, 'job fits', 'jobs fit')} you")
        elif kind == "funding":
            pieces.append(f"💶 {_n(n, 'funding call fits', 'funding calls fit')} you")
        elif kind == "conferences":
            pieces.append(f"🎤 {_n(n, 'conference fits', 'conferences fit')} you")
        elif kind == "papers":
            pieces.append(f"📄 {_n(n, 'new paper', 'new papers')} rising in your field")
        elif kind == "cited":
            pieces.append(f"📑 {_n(n, 'new paper cites', 'new papers cite')} your work")
        elif kind == "datasets":
            pieces.append(f"🗂 {_n(n, 'new dataset', 'new datasets')} on your topics")
        else:
            pieces.append(f"✨ {_n(n, 'new Highlight', 'new Highlights')}")
    body = " · ".join(pieces[:3]) + (" · and more" if len(pieces) > 3 else "")
    return {"title": "myGeeKy", "body": body, "tab": TAB[chosen[0]["kind"]], "kind": chosen[0]["kind"]}


def remember(told: Iterable[str], chosen: Iterable[dict[str, Any]]) -> list[str]:
    """What's been told, with these added (the newest MAX_TOLD kept)."""
    out = list(told)
    for c in chosen:
        if c["id"] not in out:
            out.append(c["id"])
    return out[-MAX_TOLD:]


def describe(s: dict[str, Any]) -> str:
    """What you agreed to, in one line: 'On: Seasons and jobs, at most once a day · quiet 22:00-08:00'."""
    if not s["kinds"]:
        return "All off: myGeeKy never notifies you."
    names = [k[4] for k in KINDS if k[0] in s["kinds"]]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    often = "at most once a day" if s["every"] == "daily" else "at most once a week"
    start, end = s["quiet"]
    quiet = f" · quiet {start:02d}:00-{end:02d}:00" if start != end else ""
    return f"On: {listed}, {often}{quiet}."
