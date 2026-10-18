# A season is a scholarship, grant or programme that comes back every year.
#
# 🎯 Chances holds listings that die at their deadline. Seasons are the opposite: MEXT through the Japanese
# Embassy in Cairo does not stop being real when it closes in May -- it returns next April. Today, the hour
# a call closes it leaves myGeeKy altogether, and nobody hears of it again until next year's call appears.
# By then it is too late, and that is the whole point of this file:
#
#     the preparing takes longer than the applying.
#
# MEXT wants a research proposal, two recommendation letters, and transcripts certified and apostilled. The
# window is three weeks. Getting an apostille is not a three-week job. So "this opens in about ten weeks"
# is worth more to someone than "this is open now", and a season is what lets myGeeKy say it.
#
# What a season may NOT do is pretend to know next year's date. Everything else in myGeeKy rests on a
# sentence quoted word for word from a page; next year's call has no page yet. So a season carries the
# occurrences it was actually SEEN to have, each with its own quote and link, and the next one is offered
# as an expectation worked out from those -- said as an expectation, never as a fact. A season with one
# year behind it says so; one with four says that too.
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from .curated import _day, _https, _text, _words

LEVELS = ("master", "phd", "postdoc", "undergraduate", "short")
KINDS = ("scholarship", "grant", "fellowship", "programme")
EVERY = {"year": 365, "2-years": 730, "half-year": 182}
LEAST_NOTICE = 15          # the user's floor: never less than a fortnight's warning
MOST_NOTICE = 300          # beyond this it is not news, it is a calendar
_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+){1,9}$")
_MD = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


# --------------------------------------------------------------------------- what a season is
def clean_seen(raw: Any) -> list[dict[str, Any]]:
    """The times this season was actually seen open, newest first.

    This is the evidence, and the only part of a season that is checked against a page. Each entry needs a
    link and the sentence that gave the dates, copied word for word -- without them it is hearsay and is
    dropped, however plausible it looks."""
    from .curated import _https
    out = []
    for r in (raw if isinstance(raw, list) else [])[:12]:
        if not isinstance(r, dict):
            continue
        opens, closes = _day(r.get("opens")), _day(r.get("closes"))
        url, quote = _https(r.get("url")), _text(r.get("quote"), 400)
        if not closes or not url or not quote:
            continue                      # no date, no page, or no sentence: not evidence
        if opens and opens > closes:
            continue                      # opened after it closed: somebody mistyped
        out.append({"cycle": _year(r.get("cycle")), "opens": opens, "closes": closes,
                    "url": url, "quote": quote, "checked": r.get("checked") is True})
    return sorted(out, key=lambda s: s["closes"], reverse=True)


def evidenced(season: dict[str, Any]) -> bool:
    """True once at least one of this season's occurrences has been found on its own page.

    A season the maker has only written down is a claim; one with a checked occurrence has a sentence
    behind it. Only the second kind is shown to people -- the first waits in the admin tab, exactly as an
    accepted-but-unpublished listing does."""
    return any(s.get("checked") for s in season.get("seen") or [])


def _year(v: Any) -> int:
    try:
        n = int(str(v)[:4])
    except (TypeError, ValueError):
        return 0
    return n if 2000 <= n <= 2100 else 0


def clean_season(raw: Any) -> dict[str, Any] | None:
    """One checked season, or None if it isn't usable."""
    if not isinstance(raw, dict) or not _ID.match(str(raw.get("id", ""))):
        return None
    kind = str(raw.get("kind", "scholarship")).lower()
    every = str(raw.get("every", "year")).lower()
    season = {
        "id": raw["id"],
        "title": _text(raw.get("title"), 140),
        "url": _https(raw.get("url")),
        "org": _text(raw.get("org"), 140),
        "through": _text(raw.get("through"), 140),      # the embassy or office you actually apply to
        "kind": kind if kind in KINDS else "scholarship",
        "every": every if every in EVERY else "year",
        "levels": [v for v in _words(raw.get("levels"), 6) if v in LEVELS],
        "for": _places(raw.get("for")),                 # nationalities it is open to; empty means anyone
        "goes_to": _text(raw.get("goes_to"), 60),
        "opens_about": _md(raw.get("opens_about")),
        "closes_about": _md(raw.get("closes_about")),
        "prepare_weeks": _weeks(raw.get("prepare_weeks")),
        "prepare": [_text(p, 90) for p in (raw.get("prepare") or [])[:10] if _text(p, 90)],
        "summary": _text(raw.get("summary"), 400),
        "keywords": _words(raw.get("keywords")),
        "seen": clean_seen(raw.get("seen")),
    }
    if not season["title"] or not season["url"]:
        return None
    # a season with neither a history nor a stated window cannot say when anything happens
    if not season["seen"] and not season["closes_about"]:
        return None
    return season


def _md(v: Any) -> str:
    s = _text(v, 5)
    return s if _MD.match(s) else ""


def _weeks(v: Any) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 4
    return max(1, min(52, n))


def _places(v: Any) -> list[str]:
    if isinstance(v, str):
        v = [v]
    out = []
    for p in (v if isinstance(v, list) else [])[:40]:
        name = _text(p, 60)
        if name and name.lower() not in {x.lower() for x in out}:
            out.append(name)
    return out


# --------------------------------------------------------------------------- when it next comes round
def pattern(season: dict[str, Any]) -> tuple[str, str, int]:
    """(opens month-day, closes month-day, years of evidence) -- what the history says to expect.

    Worked out from the occurrences actually seen, because those are the ones with a page behind them. The
    stated window is only a fallback, for a season found but not yet checked."""
    seen = season.get("seen") or []
    closes = [s["closes"] for s in seen if s.get("closes")]
    opens = [s["opens"] for s in seen if s.get("opens")]
    if closes:
        return (_middle(opens) or season.get("opens_about", ""), _middle(closes), len({c[:4] for c in closes}))
    return (season.get("opens_about", ""), season.get("closes_about", ""), 0)


def _middle(days: list[str]) -> str:
    """The typical month-day of a handful of dates: the middle one, so one odd year cannot drag it."""
    if not days:
        return ""
    return sorted(d[5:] for d in days)[len(days) // 2]


def when(season: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Where this season stands today.

    {"state": open | soon | later | unknown, "opens", "closes", "days_to_open", "days_to_close",
     "confirmed": bool, "years": int, "notice": int}

    `confirmed` is the honest bit: True only while a window myGeeKy actually read on a page is still
    running. Every future date is an expectation, and the interfaces must say so."""
    today = today or date.today()
    open_md, close_md, years = pattern(season)
    notice = max(LEAST_NOTICE, season.get("prepare_weeks", 4) * 7)
    out = {"state": "unknown", "opens": "", "closes": "", "days_to_open": None, "days_to_close": None,
           "confirmed": False, "years": years, "notice": notice}
    if not close_md:
        return out
    # a window myGeeKy actually saw, still running: the one case where nothing is being guessed
    for s in season.get("seen") or []:
        opens = s.get("opens") or s["closes"]
        if opens <= today.isoformat() <= s["closes"]:
            out.update(state="open", opens=s.get("opens", ""), closes=s["closes"], confirmed=True,
                       days_to_open=0, days_to_close=(date.fromisoformat(s["closes"]) - today).days)
            return out
    step = EVERY.get(season.get("every", "year"), 365)
    best = None
    for year in (today.year - 1, today.year, today.year + 1, today.year + 2):
        closes = _on(year, close_md)
        opens = _on(year, open_md) if open_md else None
        if not closes:
            continue
        if opens and opens > closes:                 # a window that straddles new year
            opens = _on(year - 1, open_md)
        if closes < today:
            continue
        if opens and opens <= today <= closes:       # expected to be open right now
            out.update(state="open", opens=opens.isoformat(), closes=closes.isoformat(), days_to_open=0,
                       days_to_close=(closes - today).days)
            return out
        start = opens or closes
        if best is None or start < best[0]:
            best = (start, closes)
    if best is None:
        return out
    start, closes = best
    days = (start - today).days
    if step < 365 or days <= MOST_NOTICE:
        out.update(state="soon" if days <= notice else "later", opens=start.isoformat(),
                   closes=closes.isoformat(), days_to_open=days, days_to_close=(closes - today).days)
    else:
        out.update(state="later", opens=start.isoformat(), closes=closes.isoformat(), days_to_open=days,
                   days_to_close=(closes - today).days)
    return out


def _on(year: int, md: str) -> date | None:
    if not _MD.match(md or ""):
        return None
    month, day = int(md[:2]), int(md[3:])
    while day > 28:                 # 29 February in a year that hasn't got one
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


# --------------------------------------------------------------------------- what to show, and to whom
def fits(season: dict[str, Any], nationality: str = "") -> bool:
    """True if this is open to someone of this nationality.

    It matters more here than anywhere else in myGeeKy: a postdoc in Lyon is open to all comers, while
    MEXT-through-Cairo is for Egyptians and is noise to everyone else. A season that names no country is
    open to anyone, and someone who has not said where they are from is shown everything."""
    who = season.get("for") or []
    if not who or not nationality.strip():
        return True
    want = nationality.strip().lower()
    return any(want == p.lower() or want in p.lower() or p.lower() in want for p in who)


def ranked(seasons: list[dict[str, Any]], today: date | None = None, nationality: str = "",
           levels: list[str] | None = None) -> list[dict[str, Any]]:
    """Seasons worth seeing now: the open ones first, then the ones to start preparing for.

    Open before soon before later, and within each the nearest first -- so the top of the list is always
    the thing to do something about today."""
    today = today or date.today()
    order = {"open": 0, "soon": 1, "later": 2, "unknown": 3}
    out = []
    for season in seasons:
        if not fits(season, nationality):
            continue
        if levels and season.get("levels") and not set(levels) & set(season["levels"]):
            continue
        state = when(season, today)
        out.append({**season, "when": state})
    out.sort(key=lambda s: (order[s["when"]["state"]], s["when"]["days_to_open"] if
                            s["when"]["days_to_open"] is not None else 9999, s["title"]))
    return out


def notice_text(state: dict[str, Any]) -> str:
    """What to say about where a season stands, without ever claiming to know a date it cannot know."""
    days = state.get("days_to_open")
    if state["state"] == "open" and state["confirmed"]:
        left = state.get("days_to_close")
        return "open now" if left is None else f"open now · closes in {left} days"
    if state["state"] == "open":
        return "expected to be open now"
    if days is None:
        return "no dates yet"
    if days <= 0:
        return "expected to open any day"
    if days <= 31:
        return f"expected to open in about {days} days"
    weeks = round(days / 7)
    if weeks <= 12:
        return f"expected in about {weeks} weeks"
    return f"expected in about {round(days / 30.4)} months"


def prepare_now(season: dict[str, Any], today: date | None = None) -> bool:
    """True when it is time to start getting the papers together, rather than time to apply."""
    state = when(season, today)
    if state["state"] == "open":
        return False
    days = state.get("days_to_open")
    return days is not None and days <= state["notice"]


def next_dates(season: dict[str, Any], today: date | None = None) -> tuple[str, str]:
    """(opens, closes) expected next, as plain YYYY-MM-DD, for anything that wants to show a calendar."""
    state = when(season, today)
    return state.get("opens", ""), state.get("closes", "")


def clean(raw: Any) -> list[dict[str, Any]]:
    """Every usable season in a list, with duplicates by id dropped."""
    seen_ids: set[str] = set()
    out = []
    for r in (raw if isinstance(raw, list) else [])[:300]:
        s = clean_season(r)
        if s and s["id"] not in seen_ids:
            seen_ids.add(s["id"])
            out.append(s)
    return out


def days_between(a: str, b: str) -> int | None:
    """Plain day count, for tests and for anything that wants to show a window's length."""
    try:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days
    except (TypeError, ValueError):
        return None


def horizon(seasons: list[dict[str, Any]], today: date | None = None) -> date:
    """The furthest ahead any of these seasons wants to be noticed: the calendar's right-hand edge."""
    today = today or date.today()
    most = max((s.get("prepare_weeks", 4) * 7 for s in seasons), default=LEAST_NOTICE)
    return today + timedelta(days=max(LEAST_NOTICE, most))


# --------------------------------------------------------------------------- the periods people step through
TOGETHER = 45          # programmes opening within this many days of a period's FIRST opening belong to it
                       # (measured from the first, not the last: with many seasons a chain never broke and
                       # everything ran into one year-long "period")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def occurrences(season: dict[str, Any], today: date | None = None, back: int = 1,
                ahead: int = 2) -> list[dict[str, Any]]:
    """Every window this season is believed to have had, or to be about to have, over a span of years.

    A window myGeeKy read on a page comes back marked `confirmed`; the rest are worked out from the
    pattern and are expectations, nothing more."""
    today = today or date.today()
    open_md, close_md, _ = pattern(season)
    if not close_md:
        return []
    known = {s["closes"]: s for s in season.get("seen") or [] if s.get("checked")}
    out = []
    for year in range(today.year - back, today.year + ahead + 1):
        closes = _on(year, close_md)
        opens = _on(year, open_md) if open_md else None
        if not closes:
            continue
        if opens and opens > closes:
            opens = _on(year - 1, open_md)
        seen = known.get(closes.isoformat())
        out.append({"opens": (opens or closes).isoformat(), "closes": closes.isoformat(),
                    "confirmed": bool(seen), "quote": (seen or {}).get("quote", ""),
                    "url": (seen or {}).get("url", "")})
    return sorted(out, key=lambda o: o["opens"])


def _label(start: date, end: date, today: date) -> str:
    """How a period is named in the drop box: short, and honest about which one we are in."""
    if start.year == end.year:
        span = _MONTHS[start.month - 1] if start.month == end.month else \
            f"{_MONTHS[start.month - 1]}/{_MONTHS[end.month - 1]}" if end.month - start.month == 1 else \
            f"{_MONTHS[start.month - 1]}–{_MONTHS[end.month - 1]}"
        return f"{span} {start.year}"
    return f"{_MONTHS[start.month - 1]} {start.year} – {_MONTHS[end.month - 1]} {end.year}"


def windows(seasons_in: list[dict[str, Any]], today: date | None = None, nationality: str = "",
            levels: list[str] | None = None, only_evidenced: bool = True) -> list[dict[str, Any]]:
    """The periods worth stepping through, in time order, each holding what falls in it.

    Only periods that actually have something in them: an empty month is not a season, and a drop box full
    of nothing teaches people the feature is empty. The period we are in is marked `now`, and the one
    before it is kept so there is always a step backwards -- a programme that closed last week is the one
    most worth seeing, because it says when to be ready next time."""
    today = today or date.today()
    rows = []
    for season in seasons_in:
        if not fits(season, nationality):
            continue
        if levels and season.get("levels") and not set(levels) & set(season["levels"]):
            continue
        if only_evidenced and not evidenced(season):
            continue
        for o in occurrences(season, today):
            rows.append((o, season))
    rows.sort(key=lambda r: r[0]["opens"])
    groups: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
    for row in rows:
        if groups and days_between(groups[-1][0][0]["opens"], row[0]["opens"]) <= TOGETHER:
            groups[-1].append(row)
        else:
            groups.append([row])
    out = []
    for group in groups:
        start = min(date.fromisoformat(o["opens"]) for o, _ in group)
        end = max(date.fromisoformat(o["closes"]) for o, _ in group)
        # named by when things OPEN, which is what groups them and what people act on. Naming it by the
        # whole span would read "Oct 2026 - Feb 2027" next to a "Jan/Feb 2027" that overlaps it.
        last_open = max(date.fromisoformat(o["opens"]) for o, _ in group)
        out.append({
            "id": f"{start.isoformat()}-{end.isoformat()}",
            "label": _label(start, last_open, today),
            "from": start.isoformat(), "to": end.isoformat(), "opens_to": last_open.isoformat(),
            "now": start <= today <= end,
            "past": end < today,
            "seasons": [{**s, "occurrence": o, "when": when(s, today)} for o, s in group],
        })
    return out


def current(wins: list[dict[str, Any]], today: date | None = None) -> int:
    """Which period the drop box should start on: the one we are in, else the next one coming."""
    today = today or date.today()
    for i, w in enumerate(wins):
        if w["now"]:
            return i
    for i, w in enumerate(wins):
        if not w["past"]:
            return i
    return max(len(wins) - 1, 0)


def around(wins: list[dict[str, Any]], today: date | None = None, back: int = 1,
           ahead: int = 3) -> list[dict[str, Any]]:
    """The periods to offer: the one we are in, one behind, and a few ahead. Not the whole calendar."""
    if not wins:
        return []
    i = current(wins, today)
    return wins[max(0, i - back):i + ahead + 1]
