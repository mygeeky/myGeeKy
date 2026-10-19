"""My month and your rank: what you did this month, worked out on this device from records it already keeps.

  * the usage log (usage.jsonl, see achievements.py): days you came by, what you opened (papers, news, repos),
    ideas sent, protocol steps done, protocols built and shared, quizzes, skills learned, chances saved;
  * your interest events: people you followed (new friends);
  * your wins (wins.py): new stars and citations on your own work.

Points come only from what you do yourself (data/ranks.json says how many each), counted over all your time in
myGeeKy, so a rank never goes down and a quiet month never takes anything away. Wins from others show on your
card but earn no points. Nothing here is sent anywhere. The phone works it out the same way (lib/month.ts);
tests/test_phone_month_match_desktop.py runs both on the same records.
"""

from __future__ import annotations

import calendar
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any, Iterable

RULES_FILE = Path(__file__).resolve().parent / "data" / "ranks.json"
RULES: dict[str, Any] = json.loads(RULES_FILE.read_text(encoding="utf-8"))
RANKS: list[tuple[str, int]] = [(name, need) for name, need in RULES["ranks"]]
POINTS: dict[str, int] = RULES["points"]
KINDS: dict[str, list[str]] = RULES["kinds"]
FAMILIES: list[tuple[str, str]] = [(name, colour) for name, colour in RULES["families"]]
ORDER = list(KINDS)                      # kinds in the order they're listed and drawn

# what opening something counts as (achievements.log's kinds); "person" and "launch" earn nothing here
CLICK_KINDS = {"headline": "news", "news": "news", "paper": "paper", "repo": "repo", "model": "repo"}
DONE = ("idea", "step", "build", "share", "quiz", "skill", "chance")    # usage lines that are a thing done
WIN_KINDS = {"stars": "star", "citations": "cite"}
WIN_WEIGHT = {"star": 2, "cite": 15}     # only to choose the highlights; wins earn no points
HIGHLIGHTS = 3
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")                       # not calendar.month_name: that follows the computer's language
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def entries(usage: Iterable[dict[str, Any]], events: Iterable[dict[str, Any]] = ()) -> list[tuple[str, str]]:
    """Every dated thing you did, as (YYYY-MM-DD, kind); "day" marks a day you came by."""
    out: list[tuple[str, str]] = []
    for e in usage:
        day = str(e.get("at", ""))[:10] if isinstance(e, dict) else ""
        if not _DAY.match(day):
            continue
        what = e.get("what")
        if what == "click":
            kind = CLICK_KINDS.get(str(e.get("kind", "")))
            if kind:
                out.append((day, kind))
            if e.get("explore"):
                out.append((day, "topic"))
        elif what == "open":
            out.append((day, "day"))
        elif what in DONE:
            out.append((day, what))
    for e in events:
        day = str(e.get("at", ""))[:10] if isinstance(e, dict) else ""
        if _DAY.match(day) and e.get("kind") == "follow":
            out.append((day, "friend"))
    return sorted(out)


def points(done: Iterable[tuple[str, str]], before: str = "9999-99-99") -> int:
    """Points for everything done before the day `before` (all of it by default)."""
    return sum(POINTS.get(kind, 0) for day, kind in done if day < before)


def rank_of(pts: int) -> int:
    """The index in RANKS of the rank that many points reaches."""
    return max(i for i, (_, need) in enumerate(RANKS) if pts >= need)


def summary(usage: Iterable[dict[str, Any]], events: Iterable[dict[str, Any]], wins: Iterable[dict[str, Any]],
            year: int, month: int) -> dict[str, Any]:
    """Your month: a list of kinds for each day, the counts, three highlights (firsts first), and your rank."""
    done = entries(usage, events)
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year + month // 12:04d}-{month % 12 + 1:02d}-01"
    ndays = calendar.monthrange(year, month)[1]
    days: list[set[str]] = [set() for _ in range(ndays)]
    active: set[int] = set()
    counts: Counter[str] = Counter()
    for day, kind in done:
        if start <= day < end:
            i = int(day[8:10]) - 1
            if kind != "day":                    # a day you only came by isn't counted: the card lights what you did
                active.add(i)
                days[i].add(kind)
                counts[kind] += 1
    for w in wins:
        if not isinstance(w, dict):
            continue
        kind = WIN_KINDS.get(str(w.get("kind", "")))
        day = str(w.get("at", ""))[:10]
        if kind and _DAY.match(day) and start <= day < end:
            n = max(int(w.get("count", 1) or 1), 1)
            days[int(day[8:10]) - 1].add(kind)
            counts[kind] += n
    seen = {kind for day, kind in done if day < start}
    first = {k for k in counts if k not in seen and k not in WIN_WEIGHT}
    worth = lambda k: POINTS.get(k, WIN_WEIGHT.get(k, 0))           # noqa: E731
    picked = sorted(counts, key=lambda k: (k not in first, -worth(k), -counts[k], ORDER.index(k)))[:HIGHLIGHTS]
    before, total = points(done, start), points(done, end)
    rank, was = rank_of(total), rank_of(before)
    nxt = RANKS[rank + 1] if rank + 1 < len(RANKS) else None
    return {
        "year": year, "month": month, "month_name": MONTHS[month - 1], "starter": not seen,
        "days": [[k for k in ORDER if k in d] for d in days],
        "active": len(active),
        "counts": {k: counts[k] for k in ORDER if counts[k]},
        "highlights": [[k, counts[k], k in first] for k in picked],
        "points": total, "month_points": total - before,
        "rank": rank, "rank_name": RANKS[rank][0], "promoted": rank > was,
        "next": nxt[0] if nxt else None, "to_next": nxt[1] - total if nxt else None,
    }


def first_month(usage: Iterable[dict[str, Any]], events: Iterable[dict[str, Any]] = ()) -> tuple[int, int] | None:
    """The month of your first record, as (year, month): how far back ‹ can go."""
    done = entries(usage, events)
    return (int(done[0][0][:4]), int(done[0][0][5:7])) if done else None


# --------------------------------------------------------------------------- the card (an SVG, the same on the phone)
STAR = "M0,-30 L9,-9 L32,-9 L13,5 L20,28 L0,14 L-20,28 L-13,5 L-32,-9 L-9,-9Z"
CARD_W, CARD_H = 400, 500
FONT = "Helvetica, Arial, sans-serif"


def _n(v: float) -> str:
    """A number as the phone writes it (JavaScript's String): 3 not 3.0, 4.5 as it is."""
    return str(int(v)) if v == int(v) else str(v)


def _text(x: float, y: float, txt: Any, size: float, fill: str, weight: int = 400, anchor: str = "start",
          extra: str = "") -> str:
    return (f'<text x="{_n(x)}" y="{_n(y)}" font-family="{FONT}" font-size="{_n(size)}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(str(txt))}</text>')


def insignia(i: int, x: float, y: float, k: float = 1, uid: str = "ins") -> str:
    """A rank's shield: chevrons for the first three ranks, then one to five stars."""
    officer = i >= 3
    top, bottom = ("#5b33d6", "#24104f") if officer else ("#2a3f8f", "#121c45")
    g = (f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
         f'<stop offset="1" stop-color="{bottom}"/></linearGradient></defs>'
         f'<path d="M-20,-24 H20 V4 Q20,22 0,31 Q-20,22 -20,4Z" fill="url(#{uid})" stroke="#ffd24a" stroke-width="2.5"/>')
    if not officer:
        for c in range(i + 1):
            yy = -6 + c * 9 - i * 4.5
            g += (f'<path d="M-12,{_n(yy + 6)} L0,{_n(yy - 3)} L12,{_n(yy + 6)}" stroke="#ffd24a" stroke-width="4" '
                  f'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    else:
        n = i - 2
        rows = [n] if n <= 3 else [2, 2] if n == 4 else [3, 2]
        for r, m in enumerate(rows):
            for c in range(m):
                g += (f'<path d="{STAR}" fill="#ffd24a" transform="translate({_n((c - (m - 1) / 2) * 12)},'
                      f'{_n((r - (len(rows) - 1) / 2) * 12 - 2)}) scale(0.17)"/>')
    return f'<g transform="translate({_n(x)},{_n(y)}) scale({_n(k)})">{g}</g>'


def cheer(s: dict[str, Any]) -> str:
    if s["promoted"]:
        return f"Promoted to {s['rank_name']}! Keep growing"
    if s["starter"] and s["active"]:
        return "Every expert started here. Well done"
    if s["active"] >= 15:
        return "Small steps add up. Keep growing"
    if s["active"]:
        return "Every day counts. Keep growing"
    return "A quiet month. GeekOc is waiting for you"


def card_svg(s: dict[str, Any], geekoc: str = "", hidden: Iterable[str] = ()) -> str:
    """The month card, 400 x 500 (4:5). `geekoc` is GeekOc's drawing (620 square, from data/geekoc.json);
    `hidden` are kinds you chose to leave off. Only shapes, gradients and text, so Qt and the phone draw it alike."""
    hide = set(hidden)
    fam_colour = dict(FAMILIES)
    colour = lambda k: fam_colour[KINDS[k][0]]               # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" width="{CARD_W}" height="{CARD_H}">',
           '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fdfbff"/>'
           '<stop offset="1" stop-color="#efe9ff"/></linearGradient>'
           '<radialGradient id="pk" cx="0.95" cy="0.02" r="0.55"><stop offset="0" stop-color="#ff9fe0" stop-opacity="0.55"/>'
           '<stop offset="1" stop-color="#ff9fe0" stop-opacity="0"/></radialGradient>'
           '<radialGradient id="bl" cx="0.02" cy="0.98" r="0.6"><stop offset="0" stop-color="#9fd8ff" stop-opacity="0.5"/>'
           '<stop offset="1" stop-color="#9fd8ff" stop-opacity="0"/></radialGradient></defs>',
           f'<rect width="{CARD_W}" height="{CARD_H}" fill="url(#bg)"/>',
           f'<rect width="{CARD_W}" height="{CARD_H}" fill="url(#pk)"/>',
           f'<rect width="{CARD_W}" height="{CARD_H}" fill="url(#bl)"/>']
    if geekoc:
        out.append(f'<g transform="translate(14,8) scale(0.1129)">{geekoc}</g>')
    out.append(_text(90, 40, f"My {s['month_name']}", 27, "#1d1a2e", 800))
    out.append(_text(92, 60, f"{s['active']} day{'' if s['active'] == 1 else 's'} of growing · {s['year']}", 13, "#6c6488"))
    out.append(insignia(s["rank"], 352, 36, 0.95))
    out.append(_text(352, 82, s["rank_name"].upper(), 10, "#3a2a7a", 800, "middle", ' letter-spacing="1"'))
    if s["promoted"]:
        out.append('<rect x="318" y="2" width="68" height="15" rx="7.5" fill="#ff4fb8"/>')
        out.append(_text(352, 13, "PROMOTED!", 8.5, "#ffffff", 800, "middle"))

    # the calendar: one dot per family for each day you did something
    first = (calendar.weekday(s["year"], s["month"], 1) + 1) % 7           # Sunday first
    cw, ch, gx, gy, x0, y0 = 44, 36, 6, 6, 28, 104
    for c, d in enumerate("SMTWTFS"):
        out.append(_text(x0 + c * (cw + gx) + cw / 2, 96, d, 10, "#9a93b5", 700, "middle"))
    for i, kinds in enumerate(s["days"]):
        kinds = [k for k in kinds if k not in hide]
        p = first + i
        x, y = x0 + (p % 7) * (cw + gx), y0 + (p // 7) * (ch + gy)
        busy = bool(kinds)
        out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="10" '
                   + ('fill="#ffffff" stroke="#6a4be0" stroke-opacity="0.18"/>' if busy else 'fill="#6a4be0" fill-opacity="0.05"/>'))
        out.append(_text(x + 6, y + 13, i + 1, 9.5, "#3a3352" if busy else "#b8b2cf", 700))
        fams = [f for f, _ in FAMILIES if any(KINDS[k][0] == f for k in kinds)]
        for n, f in enumerate(fams[:4]):
            out.append(f'<circle cx="{x + 9 + n * 9}" cy="{y + 26}" r="3.6" fill="{fam_colour[f]}"/>')
        if len(fams) > 4:
            out.append(_text(x + cw - 5, y + 29, "+", 10, "#6c6488", 800, "end"))
    rows = (first + len(s["days"]) + 6) // 7
    ly = y0 + rows * (ch + gy) + 6
    for n, (f, col) in enumerate(FAMILIES):
        x = 30 + n * 58
        out.append(f'<circle cx="{x + 4}" cy="{ly}" r="3.6" fill="{col}"/>')
        out.append(_text(x + 11, ly + 3, f, 9.5, "#6c6488", 700))

    # three highlights, firsts first
    hy = 336
    shown = [h for h in s["highlights"] if h[0] not in hide]
    if not shown:
        out.append(_text(200, hy + 40, "Open something, take a quiz or build a protocol:", 12, "#6c6488", 400, "middle"))
        out.append(_text(200, hy + 58, "it all shows here next month.", 12, "#6c6488", 400, "middle"))
    for n, (k, count, is_first) in enumerate(shown):
        x, col = 28 + n * 116, colour(k)
        label = KINDS[k][2] if count == 1 else KINDS[k][1]
        out.append(f'<rect x="{x}" y="{hy}" width="108" height="72" rx="16" fill="#ffffff" stroke="{col}" '
                   f'stroke-opacity="0.4" stroke-width="1.5"/>')
        out.append(f'<circle cx="{x + 20}" cy="{hy + 20}" r="7" fill="{col}"/>')
        out.append(_text(x + 12, hy + 52, count, 22, "#1d1a2e", 800))
        out.append(_text(x + 12, hy + 65, label, 10.5, "#6c6488"))
        if is_first:
            out.append(f'<rect x="{x + 56}" y="{hy - 8}" width="46" height="18" rx="9" fill="#ff4fb8"/>')
            out.append(_text(x + 79, hy + 5, "FIRST!", 9.5, "#ffffff", 800, "middle"))

    # every count, small: nothing done this month is left out
    counts = [(k, v) for k, v in s["counts"].items() if k not in hide][:12]
    for n, (k, v) in enumerate(counts):
        x, y = 28 + (n % 3) * 118, 424 + (n // 3) * 15
        out.append(f'<circle cx="{x + 5}" cy="{y - 4}" r="3.6" fill="{colour(k)}"/>')
        out.append(_text(x + 13, y, f"{v} {KINDS[k][2] if v == 1 else KINDS[k][1]}", 10, "#3a3352", 700))
    out.append(_text(28, 488, cheer(s), 13, "#6a4be0", 800))
    out.append(_text(372, 488, "mygeeky.org", 10, "#9a93b5", 400, "end"))
    out.append("</svg>")
    return "".join(out)


GEEKOC_FILE = Path(__file__).resolve().parent / "data" / "geekoc.json"   # written by tools/geekoc_poses.py
_geekoc: dict[str, str] = {}


def card_pose(s: dict[str, Any]) -> str:
    """Which GeekOc goes on the card: cheering a promotion or a busy month, waving at a first one."""
    if s["promoted"]:
        return "cheer"
    if not s["active"]:
        return "sleep"
    if s["starter"]:
        return "wave"
    return "cheer" if s["active"] >= 15 else "think"


def geekoc(pose: str) -> str:
    """GeekOc in that pose, as the inside of a 620-square drawing ("" if the file is missing)."""
    if not _geekoc:
        try:
            _geekoc.update(json.loads(GEEKOC_FILE.read_text(encoding="utf-8"))["poses"])
        except (OSError, ValueError, KeyError):
            return ""
    return _geekoc.get(pose, "")


def ladder_svg(pts: int, light: bool = False) -> str:
    """The ranks from Soldier to General, yours big, the line filled as far as your points reach (640 x 170).
    `light` for a light background (the text goes dark)."""
    ink, soft, faint, track = (("#241f1a", "#5b5470", "#7a7390", "#000000") if light
                               else ("#ffffff", "#b9b0e8", "#8f86c6", "#ffffff"))
    at = rank_of(pts)
    nxt = RANKS[at + 1][1] if at + 1 < len(RANKS) else None
    part = min((pts - RANKS[at][1]) / (nxt - RANKS[at][1]), 1.0) if nxt else 0.0
    x = lambda i: 40 + i * 80                                # noqa: E731
    y = 70
    reach = int(x(at) + part * 80 + 0.5) if nxt else x(at)      # rounds .5 up, as the phone's Math.round
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 170" width="640" height="170">',
           f'<line x1="{x(0)}" y1="{y}" x2="{x(len(RANKS) - 1)}" y2="{y}" stroke="{track}" stroke-opacity="0.14" '
           'stroke-width="6" stroke-linecap="round"/>',
           f'<line x1="{x(0)}" y1="{y}" x2="{reach}" y2="{y}" stroke="#ffd24a" stroke-width="6" stroke-linecap="round"/>']
    for i, (name, need) in enumerate(RANKS):
        cur = i == at
        body = insignia(i, x(i), y, 1.4 if cur else 0.9, f"lad{i}")
        out.append(body if i <= at else f'<g opacity="0.38">{body}</g>')
        out.append(_text(x(i), y + (62 if cur else 46), name, 14 if cur else 11, ink if cur else soft, 700, "middle"))
        out.append(_text(x(i), y + (78 if cur else 60), need, 9.5, faint, 400, "middle"))
    out.append(_text(reach, 18, f"you: {pts}", 11, ink, 700, "middle"))
    out.append("</svg>")
    return "".join(out)
