"""My month's eight drawings, each with GeekOc: what you did this month, told in pictures.

  1. your GitHub work: a glowing calendar of contributions        5. what you explored: a compass of topics
  2. the languages you used: GeekOc with one arm per language     6. your habits: a sky clock and your medals
  3. your wins: a ribbon through the month                        7. people: what you gave and what you got
  4. what you learned: your protocols as constellations           8. how your interests moved: rising ribbons

The counting (`stats`) is pure and the drawings are plain SVG (shapes, gradients and text: no filters, which
QtSvg can't draw), the same on the phone (lib/month-viz.ts); tests/test_phone_month_match_desktop.py runs
both on the same records and compares the numbers and the drawings. Inputs are what the apps already keep:
the usage log, your interest events (terms only), wins, your GitHub events and repos, your protocols, your
badges, and the signals you sent and received. Nothing is sent anywhere.
"""

from __future__ import annotations

import math
from typing import Any, Iterable

from .month import MONTHS, STAR, _DAY, _n, _text

W = 320
INK, MUTED, FAINT = "#eef0ff", "#a9b0d6", "#6f78a8"
SERIES = ("#8a72f2", "#169a7e", "#b98410", "#e255ad", "#4a92dd")     # validated on this dark
GOLD, PINK, CYAN, VIOLET = "#ffd24a", "#ff6fd8", "#7fd8ff", "#8a72f2"
TIERS = {"bronze": "#d58a5a", "silver": "#c9d1e8", "gold": "#ffd24a"}
CONTRIB = {"PushEvent", "PullRequestEvent", "IssuesEvent", "PullRequestReviewEvent", "CreateEvent"}
INVITES = {"collab", "join"}
TOPIC_KINDS = {"repo", "news", "star", "fork", "paper", "join"}   # what you read and keep: not follows (names)


def _r(v: float) -> str:
    """One decimal, .05 rounded up: the phone rounds the same way, so both write the same drawing."""
    return _n(math.floor(v * 10 + 0.5) / 10)


def _r2(v: float) -> str:
    return _n(math.floor(v * 100 + 0.5) / 100)


def _in(day: str, y: int, m: int) -> bool:
    return bool(_DAY.match(day)) and day[:7] == f"{y:04d}-{m:02d}"


def _ndays(y: int, m: int) -> int:
    return [31, 29 if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def _first(y: int, m: int) -> int:
    """The weekday of the 1st, Sunday = 0 (Zeller's, so it needs no calendar module)."""
    yy, mm = (y - 1, m + 12) if m < 3 else (y, m)
    h = (1 + (13 * (mm + 1)) // 5 + yy % 100 + (yy % 100) // 4 + (yy // 100) // 4 + 5 * (yy // 100)) % 7
    return (h + 6) % 7


# --------------------------------------------------------------------------- the counting
def github_month(events: Iterable[dict[str, Any]], y: int, m: int) -> dict[str, Any]:
    """Contributions per day from your GitHub events ({at, type, repo, n, action}): a push counts its commits,
    an opened pull request or issue, a review and a new repo or branch count one each."""
    days, prs = [0] * _ndays(y, m), [False] * _ndays(y, m)
    by_repo: dict[str, int] = {}
    for e in events:
        if not isinstance(e, dict) or e.get("type") not in CONTRIB or not _in(str(e.get("at", ""))[:10], y, m):
            continue
        kind, action = e["type"], e.get("action", "")
        if kind in ("PullRequestEvent", "IssuesEvent") and action != "opened":
            continue
        n = max(int(e.get("n") or 1), 1) if kind == "PushEvent" else 1
        i = int(str(e["at"])[8:10]) - 1
        days[i] += n
        prs[i] = prs[i] or kind == "PullRequestEvent"
        repo = str(e.get("repo", ""))
        by_repo[repo] = by_repo.get(repo, 0) + n
    return {"days": days, "prs": prs, "total": sum(days), "by_repo": by_repo, "first": _first(y, m)}


def languages(by_repo: dict[str, int], repo_langs: dict[str, str]) -> list[list[Any]]:
    """Your month's languages, as [name, percent], from the repos you contributed to (top four, then Other)."""
    weight: dict[str, int] = {}
    for repo, n in by_repo.items():
        lang = repo_langs.get(repo) or "Other"
        weight[lang] = weight.get(lang, 0) + n
    total = sum(weight.values())
    if not total:
        return []
    ranked = sorted(weight.items(), key=lambda kv: (kv[0] == "Other", -kv[1], kv[0]))
    top = [kv for kv in ranked if kv[0] != "Other"][:4]
    rest = total - sum(n for _, n in top)
    out = [[name, math.floor(100 * n / total + 0.5)] for name, n in top]
    if rest:
        out.append(["Other", math.floor(100 * rest / total + 0.5)])
    return out


def wins_month(wins: Iterable[dict[str, Any]], y: int, m: int) -> list[list[int]]:
    """[day, stars, forks, citations] for each day something came in."""
    per: dict[int, list[int]] = {}
    slot = {"stars": 1, "forks": 2, "citations": 3}
    for w in wins:
        if not isinstance(w, dict) or w.get("kind") not in slot or not _in(str(w.get("at", ""))[:10], y, m):
            continue
        d = int(str(w["at"])[8:10])
        row = per.setdefault(d, [d, 0, 0, 0])
        row[slot[w["kind"]]] += max(int(w.get("count") or 1), 1)
    return [per[d] for d in sorted(per)]


def _term_weights(events: Iterable[dict[str, Any]], start: str, end: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in events:
        if not isinstance(e, dict) or not isinstance(e.get("terms"), dict) or e.get("kind") not in TOPIC_KINDS:
            continue
        day = str(e.get("at", ""))[:10]
        if _DAY.match(day) and start <= day < end:
            for t, w in e["terms"].items():
                if isinstance(w, (int, float)):
                    out[t] = out.get(t, 0.0) + float(w)
    return out


def _bounds(y: int, m: int) -> tuple[str, str]:
    return f"{y:04d}-{m:02d}-01", f"{y + m // 12:04d}-{m % 12 + 1:02d}-01"


def topics(events: list[dict[str, Any]], y: int, m: int, n: int = 8) -> list[list[Any]]:
    """[term, 0..100, new] for what you read about most this month; new = never before this month."""
    start, end = _bounds(y, m)
    now = _term_weights(events, start, end)
    before = _term_weights(events, "0000-00-00", start)
    top = sorted(now.items(), key=lambda kv: (-kv[1], kv[0]))[:n]
    if not top:
        return []
    mx = top[0][1]
    return [[t, math.floor(100 * w / mx + 0.5), t not in before] for t, w in top]


def shift(events: list[dict[str, Any]], y: int, m: int, n: int = 6) -> list[list[Any]]:
    """[term, last month 0..1, this month 0..1] for the terms that mattered most in either month."""
    start, end = _bounds(y, m)
    py, pm = (y - 1, 12) if m == 1 else (y, m - 1)
    now = _term_weights(events, start, end)
    was = _term_weights(events, _bounds(py, pm)[0], start)
    if not now and not was:
        return []
    mn, mw = max(now.values(), default=0.0) or 1.0, max(was.values(), default=0.0) or 1.0
    terms = set(now) | set(was)
    level = {t: (math.floor(100 * was.get(t, 0.0) / mw + 0.5) / 100, math.floor(100 * now.get(t, 0.0) / mn + 0.5) / 100)
             for t in terms}
    top = sorted(terms, key=lambda t: (-max(level[t]), t))[:n]
    return [[t, level[t][0], level[t][1]] for t in top]


def hours(usage: Iterable[dict[str, Any]], y: int, m: int, tz_minutes: int = 0) -> list[int]:
    """How many things you did at each hour of your day (your clock: `tz_minutes` east of UTC)."""
    out = [0] * 24
    for e in usage:
        at = str(e.get("at", "")) if isinstance(e, dict) else ""
        if len(at) < 16 or not _in(at[:10], y, m) or not at[11:13].isdigit() or not at[14:16].isdigit():
            continue
        out[((int(at[11:13]) * 60 + int(at[14:16]) + tz_minutes) // 60) % 24] += 1
    return out


def give_get(sent: Iterable[dict[str, Any]], received: Iterable[dict[str, Any]], events: Iterable[dict[str, Any]],
             y: int, m: int) -> list[list[Any]]:
    """[what, you gave, you got] for thank-yous and invites (Signals), and people you followed."""
    def count(items: Iterable[dict[str, Any]], invites: bool) -> int:
        return sum(1 for g in items if isinstance(g, dict) and _in(str(g.get("at", ""))[:10], y, m)
                   and (g.get("type") in INVITES) == invites)
    sent, received = list(sent), list(received)
    follows = sum(1 for e in events if isinstance(e, dict) and e.get("kind") == "follow"
                  and _in(str(e.get("at", ""))[:10], y, m))
    return [["thank-yous", count(sent, False), count(received, False)],
            ["invites", count(sent, True), count(received, True)],
            ["follows", follows, None]]


def stats(inputs: dict[str, Any], y: int, m: int, tz_minutes: int = 0) -> dict[str, Any]:
    """Everything the eight drawings show, from what the app keeps (see the module's docstring)."""
    gh = github_month(inputs.get("github") or [], y, m)
    events = [e for e in inputs.get("events") or [] if isinstance(e, dict)]
    return {
        "month_name": MONTHS[m - 1], "has_github": bool(inputs.get("has_github")),
        "github": gh, "languages": languages(gh["by_repo"], inputs.get("repo_langs") or {}),
        "wins": wins_month(inputs.get("wins") or [], y, m), "ndays": _ndays(y, m),
        "protocols": [p for p in inputs.get("protocols") or [] if isinstance(p, dict)][:2],
        "topics": topics(events, y, m), "shift": shift(events, y, m),
        "hours": hours(inputs.get("usage") or [], y, m, tz_minutes),
        "badges": [b for b in inputs.get("badges") or [] if isinstance(b, list) and len(b) == 3][:5],
        "give": give_get(inputs.get("sent") or [], inputs.get("received") or [], events, y, m),
    }


# --------------------------------------------------------------------------- the drawings
def _frame(uid: str, h: int, body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}">'
            f'<defs><linearGradient id="{uid}bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d2b5e"/>'
            f'<stop offset="1" stop-color="#0b1130"/></linearGradient>{defs}</defs>'
            f'<rect width="{W}" height="{h}" rx="18" fill="url(#{uid}bg)"/>{body}</svg>')


def _geek(markup: str, x: float, y: float, scale: str) -> str:
    return f'<g transform="translate({_r(x)},{_r(y)}) scale({scale})">{markup}</g>' if markup else ""


def _empty(uid: str, line: str, markup: str = "") -> str:
    return _frame(uid, 120, _geek(markup, 14, 14, "0.1452") + _text(116, 58, line, 12, MUTED, 700)
                  + _text(116, 76, "It fills in as you go.", 11, FAINT))


def _trim(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def github_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    g = s["github"]
    if not s["has_github"]:
        return _empty("gh", "Add GitHub to see your work", gk.get("wave", ""))
    if not g["total"]:
        return _empty("gh", "No GitHub work yet", gk.get("wave", ""))
    c, ch, gap, x0, y0 = 36, 26, 6, 18, 86
    rows = (g["first"] + len(g["days"]) + 6) // 7
    h = y0 + rows * (ch + gap) + 22
    mx = max(g["days"])
    out = [_geek(gk.get("wave", ""), 214, -6, "0.1355"),
           _text(18, 42, g["total"], 30, INK, 800), _text(18, 60, f"GitHub contributions in {s['month_name']}", 11, MUTED)]
    for col, d in enumerate("SMTWTFS"):
        out.append(_text(x0 + col * (c + gap) + c / 2, y0 - 6, d, 9, FAINT, 700, "middle"))
    for i, n in enumerate(g["days"]):
        p = g["first"] + i
        x, y = x0 + (p % 7) * (c + gap), y0 + (p // 7) * (ch + gap)
        if n:
            if n * 4 >= mx * 3:
                out.append(f'<rect x="{x - 3}" y="{y - 3}" width="{c + 6}" height="{ch + 6}" rx="10" fill="{PINK}" opacity="0.22"/>')
            out.append(f'<rect x="{x}" y="{y}" width="{c}" height="{ch}" rx="8" fill="url(#ghc)" opacity="{_r2(0.3 + 0.7 * n / mx)}"/>')
        else:
            out.append(f'<rect x="{x}" y="{y}" width="{c}" height="{ch}" rx="8" fill="#ffffff" fill-opacity="0.06"/>')
        if g["prs"][i]:
            out.append(f'<circle cx="{x + c - 6}" cy="{y + 6}" r="3" fill="#ffffff"/>')
    out.append(f'<circle cx="22" cy="{h - 12}" r="3" fill="#ffffff"/>')
    out.append(_text(30, h - 9, "a day with a pull request", 9.5, MUTED))
    defs = (f'<linearGradient id="ghc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PINK}"/>'
            '<stop offset="1" stop-color="#7a5cff"/></linearGradient>')
    return _frame("gh", h, "".join(out), defs)


def languages_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    langs = s["languages"]
    if not langs:
        return _empty("lg", "Languages come with GitHub", gk.get("think", ""))
    cx, cy, h = 160, 96, 250
    out, defs = [], []
    for i, (name, v) in enumerate(langs):
        a = math.pi * (0.06 + i * 0.22)
        ca, sa = math.cos(a), math.sin(a)
        length = 58 + v * 1.1
        right, left = ca > 0.05, ca < -0.05
        ex, ey = cx + ca * length * 0.9, cy + 22 + sa * length * 0.72
        mx, my = cx + ca * length * 0.45 - sa * 14, cy + 40 + sa * length * 0.55
        curl, w = (1 if right else -1), 5 + v / 5
        d = f"M{_r(cx + ca * 14)},{cy + 24} Q{_r(mx)},{_r(my)} {_r(ex)},{_r(ey)} q{curl * 9},4 {curl * 7},-6"
        defs.append(f'<linearGradient id="lga{i}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8b45e0"/>'
                    f'<stop offset="0.45" stop-color="{SERIES[i]}"/></linearGradient>')
        out.append(f'<path d="{d}" stroke="url(#lga{i})" stroke-width="{_r(w)}" stroke-linecap="round" fill="none"/>')
        out.append(f'<path d="{d}" stroke="#ffffff" stroke-opacity="0.28" stroke-width="{_r(max(1.5, w / 5))}" '
                   'stroke-linecap="round" fill="none" stroke-dasharray="1 7"/>')
        far = right and ex + 12 + len(f"{name} {v}%") * 6.2 > 314       # no room after the tip: above it
        lx = ex + 6 if far else ex + (12 if right else -12 if left else 0)
        ly = ey - 14 if far else ey + (4 if right or left else 22)
        anchor = "end" if far else "start" if right else "end" if left else "middle"
        out.append(_text(float(_r(lx)), float(_r(ly)), f"{name} {v}%", 11, INK, 700, anchor))
    out.append(_geek(gk.get("head", ""), cx - 80, cy - 74, "0.2581"))
    return _frame("lg", h, "".join(out), "".join(defs))


def wins_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    rows = s["wins"]
    if not rows:
        return _empty("wn", "No stars or citations yet", gk.get("swim", ""))
    h, base = 220, 124

    def ry(x: float) -> float:
        return base + math.sin(x / 38) * 14

    d = " ".join(f"{'M' if x == 8 else 'L'}{x},{_r(ry(x))}" for x in range(8, 313, 4))
    out = [_geek(gk.get("swim", ""), 232, -8, "0.1355"),
           f'<path d="{d}" stroke="url(#wnr)" stroke-width="10" fill="none" stroke-linecap="round" opacity="0.85"/>']
    for lane, (day, stars, forks, cites) in enumerate(rows):
        x = 12 + (day - 1) * 9.8
        y0 = ry(x)
        off = 26 if lane % 4 < 2 else 52
        y = y0 + off if lane % 2 else y0 - off
        col = PINK if cites else GOLD if stars else CYAN
        out.append(f'<line x1="{_r(x)}" y1="{_r(y0)}" x2="{_r(x)}" y2="{_r(y)}" stroke="{col}" stroke-opacity="0.5"/>')
        out.append(f'<rect x="{_r(x - 11)}" y="{_r(y - 8)}" width="22" height="16" rx="8" fill="#101a40" stroke="{col}" '
                   'stroke-width="1.5"/>')
        label = "“" if cites else str(stars) if stars else "Y"
        out.append(_text(float(_r(x)), float(_r(y + 4)), label, 9.5, col, 700, "middle"))
    out.append(_text(8, h - 30, f"{s['month_name'][:3]} 1", 9.5, FAINT))
    out.append(_text(312, h - 30, f"{s['month_name'][:3]} {s['ndays']}", 9.5, FAINT, 400, "end"))
    for i, (col, word) in enumerate(((GOLD, "new stars"), (CYAN, "forks"), (PINK, "citations"))):
        out.append(f'<circle cx="{110 + i * 66}" cy="{h - 12}" r="3.5" fill="{col}"/>')
        out.append(_text(117 + i * 66, h - 9, word, 9.5, MUTED))
    defs = ('<linearGradient id="wnr" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7a5cff"/>'
            f'<stop offset="1" stop-color="{PINK}"/></linearGradient>')
    return _frame("wn", h, "".join(out), defs)


def _sky(seed: int, n: int, w: int, h: int) -> str:
    out = []
    for _ in range(n):
        seed = seed * 16807 % 2147483647
        x = (seed - 1) / 2147483646 * w
        seed = seed * 16807 % 2147483647
        y = (seed - 1) / 2147483646 * h
        out.append(f'<circle cx="{_r(x)}" cy="{_r(y)}" r="0.8" fill="#ffffff" opacity="0.5"/>')
    return "".join(out)


def constellation_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    protos = s["protocols"]
    if not protos:
        return _empty("cs", "Start a protocol in Grow", gk.get("point", ""))
    h = 50 + 96 * len(protos)
    out = [_sky(11, 40, W, h), _geek(gk.get("point", ""), 244, -6, "0.1129")]
    for pi, p in enumerate(protos):
        steps = [st for st in p.get("steps") or [] if isinstance(st, list) and len(st) == 2][:7]
        base = 86 + pi * 96
        known = sum(1 for _, k in steps if k)
        out.append(_text(18, base - 40, _trim(str(p.get("title", "")), 30), 11.5, INK, 700))
        out.append(_text(18, base - 26, f"{known} of {len(steps)} steps", 9.5, MUTED))
        pts = [(30 + j * (260 / (len(steps) - 1)) if len(steps) > 1 else 160.0, base + (-12 if j % 2 else 12))
               for j in range(len(steps))]
        for j in range(1, len(pts)):
            lit = steps[j][1] and steps[j - 1][1]
            out.append(f'<line x1="{_r(pts[j - 1][0])}" y1="{pts[j - 1][1]}" x2="{_r(pts[j][0])}" y2="{pts[j][1]}" '
                       f'stroke="{VIOLET}" stroke-width="1.5" opacity="{1 if lit else 0.35}"/>')
        for (x, y), (name, k) in zip(pts, steps):
            if k:
                out.append(f'<circle cx="{_r(x)}" cy="{y}" r="11" fill="{GOLD}" opacity="0.18"/>')
                out.append(f'<path d="{STAR}" fill="{GOLD}" transform="translate({_r(x)},{y}) scale(0.3)"/>')
            else:
                out.append(f'<path d="{STAR}" fill="none" stroke="{FAINT}" stroke-width="4" '
                           f'transform="translate({_r(x)},{y}) scale(0.26)"/>')
            out.append(_text(float(_r(x)), y + 22, _trim(str(name), 14), 8.5, INK if k else FAINT, 400, "middle"))
    return _frame("cs", h, "".join(out))


def compass_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    tops = s["topics"]
    if not tops:
        return _empty("cp", "Open papers, news, repos", gk.get("idle", ""))
    cx, cy, h = 160, 118, 250
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#a0b4ff" stroke-opacity="0.12"/>' for r in (40, 70, 95)]
    for i, (term, v, new) in enumerate(tops):
        a = i / len(tops) * math.pi * 2 - math.pi / 2
        length = 30 + 70 * v / 100

        def p(ang: float, rr: float) -> str:
            return f"{_r(cx + math.cos(ang) * rr)},{_r(cy + math.sin(ang) * rr)}"

        out.append(f'<path d="M{p(a - 0.16, 14)} L{p(a, length)} L{p(a + 0.16, 14)}Z" fill="{PINK if new else VIOLET}" opacity="0.9"/>')
        ca = math.cos(a)
        anchor = "middle" if abs(ca) < 0.3 else "start" if ca > 0 else "end"
        out.append(_text(float(_r(cx + ca * (length + 12))), float(_r(cy + math.sin(a) * (length + 12) + 4)),
                         _trim(term, 18), 10, INK, 400, anchor))
    out.append(_geek(gk.get("idle", ""), cx - 27, cy - 30, "0.0871"))
    for i, (col, word) in enumerate(((VIOLET, "your usual"), (PINK, "new territory"))):
        out.append(f'<circle cx="{100 + i * 80}" cy="{h - 12}" r="3.5" fill="{col}"/>')
        out.append(_text(107 + i * 80, h - 9, word, 9.5, MUTED))
    return _frame("cp", h, "".join(out))


def _when(hrs: list[int]) -> str:
    peak = max(range(24), key=lambda i: (hrs[i], -i))
    return "mornings" if 5 <= peak < 12 else "afternoons" if peak < 17 and peak >= 12 else "evenings" if 17 <= peak < 22 else "nights"


def habits_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    hrs, badges = s["hours"], s["badges"]
    h, cx, cy = 376, 160, 168
    out = [f'<path d="M{cx - 150},{cy} A150,150 0 0 1 {cx + 150},{cy}" stroke="url(#hbs)" stroke-width="10" fill="none" '
           'stroke-linecap="round"/>']
    mx = max(hrs) or 1
    for hr, v in enumerate(hrs):
        a = math.pi + hr / 23 * math.pi
        r1 = 60 + v / mx * 74
        out.append(f'<line x1="{_r(cx + math.cos(a) * 56)}" y1="{_r(cy + math.sin(a) * 56)}" x2="{_r(cx + math.cos(a) * r1)}" '
                   f'y2="{_r(cy + math.sin(a) * r1)}" stroke="{VIOLET if hr >= 20 or hr < 6 else "#f6b25e"}" '
                   'stroke-width="6" stroke-linecap="round"/>')
    out += [_text(cx - 152, cy + 16, "0h", 10, FAINT, 400, "middle"), _text(cx, cy - 158, "12h", 10, FAINT, 400, "middle"),
            _text(cx + 152, cy + 16, "24h", 10, FAINT, 400, "middle"), _geek(gk.get("sleep", ""), cx - 31, cy - 64, "0.1")]
    out.append(_text(cx, cy + 18, f"mostly {_when(hrs)}" if any(hrs) else "no visits yet", 12, INK, 700, "middle"))
    out.append('<line x1="40" y1="198" x2="280" y2="198" stroke="#ffffff" stroke-opacity="0.1" stroke-dasharray="2 5"/>')
    if not badges:
        out.append(_text(cx, 290, "Your badges hang here as you earn them", 11, MUTED, 400, "middle"))
    for i, (icon, name, tier) in enumerate(badges):
        x, col = 34 + i * 63, TIERS.get(tier, TIERS["bronze"])
        rib = SERIES[i % 5]
        out.append(f'<path d="M{x - 11},210 V248 L{x},256 L{x + 11},248 V210Z" fill="{rib}"/>')
        out.append(f'<rect x="{x - 2.5}" y="210" width="5" height="42" fill="#ffffff" fill-opacity="0.3"/>')
        out.append(f'<line x1="{x}" y1="256" x2="{x}" y2="268" stroke="{col}" stroke-width="2"/>')
        for side in (-1, 1):
            for k in range(7):
                ang = math.pi / 2 + side * (0.42 + k * 0.33)
                rr = 24 + (2.5 if k % 2 else -1)
                px, py = x + math.cos(ang) * rr, 294 + math.sin(ang) * rr
                deg = ang * 180 / math.pi + 90 + side * 25
                out.append(f'<ellipse cx="0" cy="0" rx="6.5" ry="2.6" fill="{col}" opacity="{_r2(0.9 - k * 0.05)}" '
                           f'transform="translate({_r(px)},{_r(py)}) rotate({_r(deg)})"/>')
        out.append(_text(x, 304, icon, 26, INK, 400, "middle"))
        out.append(f'<rect x="{x - 30}" y="332" width="60" height="20" rx="10" fill="#ffffff" fill-opacity="0.07" '
                   f'stroke="{col}" stroke-opacity="0.6"/>')
        out.append(_text(x, 346, _trim(name, 12), 9, INK, 700, "middle"))
    defs = ('<linearGradient id="hbs" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#1b2a6b"/>'
            '<stop offset="0.3" stop-color="#f6b25e"/><stop offset="0.55" stop-color="#7fd8ff"/>'
            '<stop offset="0.8" stop-color="#e2669e"/><stop offset="1" stop-color="#1b2a6b"/></linearGradient>')
    return _frame("hb", h, "".join(out), defs)


def givegot_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    rows = s["give"]
    mx = max([v for _, a, b in rows for v in (a, b) if v is not None] + [1])
    unit = min(14.0, 120 / mx)
    h = 70 + len(rows) * 44 + 24
    out = [_geek(gk.get("wave", ""), 12, -2, "0.1129"),
           f'<line x1="160" y1="66" x2="160" y2="{h - 34}" stroke="#ffffff" stroke-opacity="0.2"/>']
    for i, (what, gave, got) in enumerate(rows):
        y = 78 + i * 44
        out.append(_text(160, y - 2, what, 11, INK, 700, "middle"))
        if gave:
            out.append(f'<rect x="{_r(160 - gave * unit)}" y="{y + 4}" width="{_r(gave * unit)}" height="18" rx="9" fill="{VIOLET}"/>')
        out.append(_text(float(_r(150 - gave * unit)) if gave else 154, y + 17, gave or 0, 10, INK, 700, "end"))
        if got is None:
            out.append(_text(166, y + 17, "—", 10, FAINT))
        else:
            if got:
                out.append(f'<rect x="162" y="{y + 4}" width="{_r(got * unit)}" height="18" rx="9" fill="#169a7e"/>')
            out.append(_text(float(_r(172 + got * unit)) if got else 166, y + 17, got, 10, INK, 700))
    out.append(_text(150, h - 12, "← you gave", 10, MUTED, 400, "end"))
    out.append(_text(170, h - 12, "you got →", 10, MUTED))
    return _frame("gg", h, "".join(out))


def ribbons_svg(s: dict[str, Any], gk: dict[str, str]) -> str:
    rows = s["shift"]
    if not rows:
        return _empty("rb", "Your interests show here", gk.get("think", ""))
    h = 220

    def y(v: float) -> float:
        return 196 - v * 140

    out = [_geek(gk.get("think", ""), 252, -6, "0.1129"),
           _text(70, 30, MONTHS[(MONTHS.index(s["month_name"]) - 1) % 12], 10, MUTED, 400, "middle"),
           _text(220, 30, s["month_name"], 10, MUTED, 400, "middle")]
    label_y: dict[str, float] = {}
    prev = 60.0                                          # the first name sits below GeekOc
    for t, _, b in sorted(rows, key=lambda r: (-r[2], r[0])):
        label_y[t] = max(y(b), prev + 14)
        prev = label_y[t]
    for t, a, b in rows:
        up = b > a
        d = f"M70,{_r(y(a))} C145,{_r(y(a))} 145,{_r(y(b))} 220,{_r(y(b))}"
        if up:
            out.append(f'<path d="{d}" stroke="#169a7e" stroke-opacity="0.25" stroke-width="10" fill="none"/>')
        out.append(f'<path d="{d}" stroke="{"#169a7e" if up else "#ffffff"}" stroke-opacity="{1 if up else 0.25}" '
                   f'stroke-width="{4 if up else 2}" fill="none"/>')
        out.append(f'<circle cx="220" cy="{_r(y(b))}" r="4.5" fill="{"#7fe6c8" if up else FAINT}"/>')
        out.append(_text(230, float(_r(label_y[t] + 4)), _trim(t, 14), 10, INK, 400))
    return _frame("rb", h, "".join(out))


DIVES = [
    ("github", "Your GitHub work", "cheer", github_svg),
    ("languages", "The languages you used", "proud", languages_svg),
    ("wins", "Your wins", "proud", wins_svg),
    ("learning", "What you learned", "think", constellation_svg),
    ("exploring", "What you explored", "swim", compass_svg),
    ("habits", "Your habits", "cheer", habits_svg),
    ("people", "People and signals", "wave", givegot_svg),
    ("shift", "How your interests moved", "think", ribbons_svg),
]


def say(s: dict[str, Any], key: str) -> str:
    """GeekOc's line for one drawing."""
    if key == "github":
        g = s["github"]
        return f"You made {g['total']} contributions on GitHub in {s['month_name']}!" if g["total"] else \
            "Your GitHub work shows here when there is some."
    if key == "languages":
        return f"{s['languages'][0][0]} was your favourite arm this month." if s["languages"] else \
            "Your languages come from the repos you work on."
    if key == "wins":
        stars = sum(r[1] for r in s["wins"])
        cites = sum(r[3] for r in s["wins"])
        return f"{stars} new stars and {cites} citation{'' if cites == 1 else 's'}. I caught them all!" if s["wins"] else \
            "Stars and citations on your work land here."
    if key == "learning":
        known = sum(1 for p in s["protocols"] for st in p.get("steps") or [] if isinstance(st, list) and st[1:2] == [True])
        return f"{known} steps lit up in your protocols. Clever!" if known else "Each step you know lights a star."
    if key == "exploring":
        new = [t for t, _, n in s["topics"] if n]
        return f"You swam into new waters: {', '.join(new[:3])}!" if new else \
            ("You went deeper into your field." if s["topics"] else "What you open shows where you explored.")
    if key == "habits":
        return f"You come by mostly in the {_when(s['hours'])[:-1]}, like a real geek." if any(s["hours"]) else \
            "Your hours show as you use myGeeKy."
    if key == "people":
        gave = sum(r[1] for r in s["give"])
        return f"You gave {gave} time{'' if gave == 1 else 's'} to the people around you. Making friends!" if gave else \
            "Thank someone or follow a person, and it shows here."
    up = [t for t, a, b in s["shift"] if b > a]
    return f"{up[0]} grew the most in you this month." if up else "Your interests show as you open things."
