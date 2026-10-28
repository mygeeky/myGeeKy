"""GEMS (Games: Evidence, Mastery, Signals): how myGeeKy's games are fed, scored and taught from (docs/GEMS.md).

Every game is a row in GAMES: its id, name, icon and the KINDS of content it plays (word sets, pipeline ladders,
questions, code snippets...). The content itself is a pack, data/games.json (the phone has an identical copy),
where every item carries its level, its field terms and the source that proves it; `validate` is the gate a pack
must pass. Adding a game is one row here and its screen on each app; adding content is items in the pack.

This file holds only the rules both apps share, and the phone's lib/gems.ts says the same thing line for line:

- **pick**: which items a round plays. About 70% from your field (your Model's terms), 20% new territory, 10% items
  you got wrong coming back (spaced repetition: a Leitner box per item), never above what your level unlocks,
  shuffled by a seeded generator so both apps pick alike.
- **record**: a round's answers into your progress: points, stars, a best score, XP, the game's level and your player
  level, each item's box, and per topic what you answered right and wrong and how long you played.
- **model_terms**: what the Model learns from a round: the topics played, weighted by right answers and playing
  time. **mastery**: the topics you know and the ones you're learning, for You and Grow.
- **badge_counts**: the Player, Sharp and Level up badges.

Nothing here touches the network or the screen. Progress stays on the device and syncs only to the user's own
storage, like the rest of their settings and progress.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Iterable

# id, name, emoji (until the icon loads), the content it plays, one line about it
GAMES: list[dict[str, Any]] = [
    {"id": "hunter", "title": "Word Hunter", "emoji": "☄️", "kinds": ["wordset", "question"],
     "about": "Shoot the words that belong to the set; let the wrong ones drift past."},
    {"id": "rise", "title": "Rise", "emoji": "\U0001f30a", "kinds": ["ladder"],
     "about": "Climb out of the sea on the right next step of a pipeline."},
    {"id": "maze", "title": "GeeKOc goes home", "emoji": "\U0001f3e0", "kinds": ["question"],
     "about": "Find the way home; doors ask questions from your protocols."},
    {"id": "run", "title": "GeeKOc run", "emoji": "\U0001f3c3", "kinds": ["gate"],
     "about": "Jump the bugs; at a gate, jump for the top answer or stay low for the bottom one."},
    {"id": "flappy", "title": "Flappy GeeKOc", "emoji": "\U0001f419", "kinds": ["gate"],
     "about": "Swim up through the gap of the right answer."},
    {"id": "whack", "title": "Whack-a-bug", "emoji": "\U0001f528", "kinds": ["critter"],
     "about": "Whack the bugs, spare the friends."},
    {"id": "realfake", "title": "Real tool or made up?", "emoji": "\U0001f575️", "kinds": ["realfake"],
     "about": "Which tools really exist?"},
    {"id": "genemon", "title": "Gene or Pokémon?", "emoji": "\U0001f9ec", "kinds": ["genemon"],
     "about": "Sonic hedgehog or Psyduck: gene or Pokémon?"},
    {"id": "reviewer", "title": "Reviewer 2 attacks", "emoji": "\U0001f421", "kinds": ["review"],
     "about": "Answer the grumpy reviewer well and get your paper accepted."},
    {"id": "reef", "title": "Debug reef", "emoji": "\U0001fab8", "kinds": ["snippet"],
     "about": "Tap the line with the bug before the bubble rises."},
    {"id": "catch", "title": "Sort the catch", "emoji": "\U0001f3a3", "kinds": ["sort"],
     "about": "Steer each name into the right net."},
    {"id": "figure", "title": "Fix the figure", "emoji": "\U0001f4ca", "kinds": ["figure"],
     "about": "Spot what's wrong with the plot."},
    {"id": "first", "title": "Which came first?", "emoji": "⚖️", "kinds": ["year"],
     "about": "Two tools, one question: which is older?"},
    {"id": "terminal", "title": "Terminal typing", "emoji": "⌨️", "kinds": ["command"],
     "about": "Two commands do the task, one doesn't: pick a right one (and type it, on the computer)."},
]
GAME_IDS = [g["id"] for g in GAMES]

KINDS = ("wordset", "ladder", "gate", "critter", "realfake", "genemon", "review", "snippet", "sort", "figure", "year",
         "command")
FIGURE_KINDS = ("truncated", "rainbow", "noerror", "dualaxis", "pie3d", "overplot", "spaghetti", "nolabels")

SHARES = {"field": 0.7, "explore": 0.2, "review": 0.1}
INTERVALS = (1, 2, 4, 8, 16, 32)            # days until an item comes back, by its Leitner box
GAME_MAX_LEVEL = 10
TERMS_PER_ROUND = 12


# ---------------------------------------------------------------------------------------------- the same dice
class Dice:
    """mulberry32: a tiny seeded generator, written the same in lib/gems.ts, so a seed picks alike on both apps."""

    def __init__(self, seed: int) -> None:
        self.a = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    def shuffle(self, items: list[Any]) -> list[Any]:
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = int(self.next() * (i + 1))
            out[i], out[j] = out[j], out[i]
        return out


def half_up(x: float, digits: int = 0) -> float:
    """Rounding the same on both apps: halves go up (Python's round() sends 2.5 to 2, JavaScript's to 3)."""
    k = 10 ** digits
    return math.floor(x * k + 0.5) / k


def seed_of(text: str) -> int:
    """A seed from a string (a day and a game, say), the same on both apps."""
    h = 2166136261
    for ch in text:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


# ---------------------------------------------------------------------------------------------- the pack
def _https(url: Any) -> bool:
    return isinstance(url, str) and url.startswith("https://") and len(url) < 300 and " " not in url


def _text(v: Any, most: int = 400) -> bool:
    return isinstance(v, str) and 0 < len(v.strip()) <= most


def validate(pack: dict[str, Any]) -> list[str]:
    """Everything wrong with a pack, as plain sentences; [] means it may be played. The same checks as
    lib/gems.ts, so a pack the computer accepts the phone accepts too."""
    problems: list[str] = []
    seen: set[str] = set()
    items = pack.get("items") if isinstance(pack, dict) else None
    if not isinstance(items, list) or not items:
        return ["the pack has no items"]
    for n, it in enumerate(items):
        where = f"item {n + 1}"
        if not isinstance(it, dict):
            problems.append(f"{where} is not an object")
            continue
        iid, kind = it.get("id"), it.get("kind")
        where = f"{iid or where}"
        if not isinstance(iid, str) or not iid or len(iid) > 60:
            problems.append(f"{where}: no id")
        elif iid in seen:
            problems.append(f"{where}: id used twice")
        seen.add(str(iid))
        if kind not in KINDS:
            problems.append(f"{where}: unknown kind {kind!r}")
            continue
        if it.get("level") not in (1, 2, 3):
            problems.append(f"{where}: level must be 1, 2 or 3")
        terms = it.get("terms")
        if not isinstance(terms, list) or not all(isinstance(t, str) and t == t.lower() and t.strip() for t in terms):
            problems.append(f"{where}: terms must be a list of lower-case words")
        src = it.get("source")
        if not (isinstance(src, dict) and _text(src.get("title"), 160) and _https(src.get("url"))):
            problems.append(f"{where}: needs a source with a title and an https link")
        problems += [f"{where}: {p}" for p in _shape(kind, it)]
    return problems


def _shape(kind: str, it: dict[str, Any]) -> list[str]:
    p: list[str] = []
    if kind == "wordset":
        words, decoys = it.get("words"), it.get("what")
        if not _text(it.get("name"), 80) or not _text(decoys, 80):
            p.append("a word set needs a name and what one of its words is")
        if not isinstance(words, list) or len(words) < 6 or not all(_text(w, 40) for w in words):
            p.append("a word set needs at least 6 words")
    elif kind == "ladder":
        rows = it.get("rows")
        if not _text(it.get("name"), 80) or not isinstance(rows, list) or len(rows) < 4:
            p.append("a ladder needs a name and at least 4 rows")
        else:
            for r in rows:
                if not (isinstance(r, dict) and _text(r.get("right"), 120) and isinstance(r.get("wrong"), list)
                        and r["wrong"] and all(isinstance(w, dict) and _text(w.get("text"), 120) and _text(w.get("why"), 200)
                                               for w in r["wrong"])):
                    p.append("each ladder row needs the right step and wrong ones that say why")
                    break
    elif kind == "gate":
        if not (_text(it.get("q"), 70) and _text(it.get("right"), 18) and _text(it.get("wrong"), 18)):
            p.append("a gate needs a short question and two short answers")
        elif it["right"] == it["wrong"]:
            p.append("a gate's two answers must differ")
    elif kind == "critter":
        if not (_text(it.get("label"), 24) and it.get("bug") in (True, False) and _text(it.get("why"), 160)):
            p.append("a critter needs a short label, whether it's a bug, and why")
    elif kind in ("realfake", "genemon"):
        allowed = (True, False) if kind == "realfake" else ("gene", "pokemon")
        key = "real" if kind == "realfake" else "answer"
        if not (_text(it.get("name"), 40) and it.get(key) in allowed and _text(it.get("fact"), 200)):
            p.append(f"a {kind} card needs a name, its answer and a fact")
    elif kind == "review":
        wrong = it.get("wrong")
        if not (_text(it.get("comment"), 120) and _text(it.get("right"), 120) and isinstance(wrong, list)
                and len(wrong) >= 2 and all(_text(w, 120) for w in wrong)):
            p.append("a review needs a comment, the right reply and two wrong ones")
    elif kind == "snippet":
        lines, bug = it.get("lines"), it.get("bug")
        if not (it.get("lang") in ("Python", "R", "Shell", "SQL") and isinstance(lines, list) and 2 <= len(lines) <= 10
                and all(isinstance(x, str) and len(x) <= 80 for x in lines) and isinstance(bug, int)
                and 0 <= bug < len(lines) and _text(it.get("why"), 200)):
            p.append("a snippet needs a language, 2-10 short lines, the buggy line and why")
    elif kind == "sort":
        bins, things = it.get("bins"), it.get("things")
        if not (_text(it.get("name"), 80) and isinstance(bins, list) and 2 <= len(bins) <= 3
                and all(_text(b, 20) for b in bins) and isinstance(things, list) and len(things) >= 6
                and all(isinstance(t, list) and len(t) == 2 and _text(t[0], 30) and t[1] in range(len(bins))
                        for t in things)):
            p.append("a sort needs 2-3 bins and at least 6 names, each with its bin")
    elif kind == "figure":
        wrong = it.get("wrong")
        if not (it.get("draw") in FIGURE_KINDS and _text(it.get("right"), 140) and isinstance(wrong, list)
                and len(wrong) >= 3 and all(_text(w, 140) for w in wrong)):
            p.append("a figure needs a known drawing, the right flaw and three wrong ones")
    elif kind == "year":
        y = it.get("year")
        if not (_text(it.get("name"), 40) and isinstance(y, int) and 1900 <= y <= 2100 and _text(it.get("event"), 80)):
            p.append("a year card needs a name, a year and what happened that year")
    elif kind == "command":
        right, wrong = it.get("right"), it.get("wrong")
        if not (_text(it.get("task"), 120) and isinstance(right, list) and len(right) == 2
                and all(_text(c, 70) for c in right) and right[0] != right[1] and isinstance(wrong, dict)
                and _text(wrong.get("cmd"), 70) and _text(wrong.get("why"), 200) and wrong["cmd"] not in right):
            p.append("a command needs a task, two right commands and one wrong one that says why")
    return p


def items_of(pack: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [it for it in pack.get("items", []) if isinstance(it, dict) and it.get("kind") == kind]


# ---------------------------------------------------------------------------------------------- picking
def relevance(item: dict[str, Any], weights: dict[str, float]) -> float:
    """How much an item is about your field: the weights of its terms in your Model."""
    return sum(float(weights.get(t, 0.0)) for t in item.get("terms") or [])


def max_item_level(game_level: int) -> int:
    """What a game's level unlocks: easy items at first, medium from level 3, hard from level 6."""
    return 1 if game_level < 3 else 2 if game_level < 6 else 3


def due(entry: dict[str, Any] | None, today: str) -> bool:
    return bool(entry) and str(entry.get("due", "")) <= today


def pick(items: list[dict[str, Any]], n: int, progress: dict[str, Any], weights: dict[str, float], today: str,
         seed: int, game_level: int = 1) -> list[dict[str, Any]]:
    """The round's items: ~70% your field, ~20% new territory, ~10% due again; never above what the level unlocks;
    resting items (seen, not yet due) only if nothing else is left."""
    top = max_item_level(game_level)
    pool = [it for it in items if int(it.get("level", 1)) <= top] or list(items)
    seen = progress.get("items", {}) if isinstance(progress, dict) else {}
    dice = Dice(seed)
    order = {it["id"]: i for i, it in enumerate(dice.shuffle(pool))}
    review = [it for it in pool if due(seen.get(it["id"]), today)]
    fresh = [it for it in pool if it["id"] not in seen]
    field = sorted((it for it in fresh if relevance(it, weights) > 0), key=lambda it: (-relevance(it, weights), order[it["id"]]))
    explore = sorted((it for it in fresh if relevance(it, weights) <= 0), key=lambda it: order[it["id"]])
    review.sort(key=lambda it: (str(seen[it["id"]].get("due", "")), order[it["id"]]))
    resting = sorted((it for it in pool if it["id"] in seen and not due(seen.get(it["id"]), today)),
                     key=lambda it: (str(seen[it["id"]].get("seen", "")), order[it["id"]]))
    want = {"review": int(half_up(n * SHARES["review"])), "explore": int(half_up(n * SHARES["explore"]))}
    want["field"] = n - want["review"] - want["explore"]
    out: list[dict[str, Any]] = []
    taken: set[str] = set()

    def take(src: list[dict[str, Any]], k: int) -> None:
        for it in src:
            if len(out) >= n or k <= 0:
                return
            if it["id"] not in taken:
                out.append(it)
                taken.add(it["id"])
                k -= 1

    take(review, want["review"])
    take(explore, want["explore"])
    take(field, want["field"])
    for src in (field, explore, review, resting):         # short of one kind: fill from the others
        take(src, n - len(out))
    return dice.shuffle(out)


# ---------------------------------------------------------------------------------------------- scoring
def xp_for_level(level: int) -> int:
    """XP a game needs to reach `level` (1 is free): 150, 450, 900, 1500..."""
    return 75 * level * (level - 1)


def level_of(xp: int, cap: int = GAME_MAX_LEVEL) -> int:
    lv = 1
    while lv < cap and xp >= xp_for_level(lv + 1):
        lv += 1
    return lv


def player_level(xp: int) -> int:
    """Your player level, from the XP of every game (no cap): 300, 900, 1800..."""
    lv = 1
    while xp >= 150 * (lv + 1) * lv:
        lv += 1
    return lv


def stars(accuracy: float) -> int:
    return 3 if accuracy >= 0.95 else 2 if accuracy >= 0.8 else 1 if accuracy >= 0.6 else 0


def points(answers: list[dict[str, Any]], bonus: int = 0) -> int:
    """10 per right answer, times the item's level, plus whatever the game adds (speed, a typed command...)."""
    return sum(10 * int(a.get("level", 1)) for a in answers if a.get("right")) + max(0, int(bonus))


def empty_progress() -> dict[str, Any]:
    return {"version": 1, "games": {}, "items": {}, "topics": {}, "xp": 0}


def record(progress: dict[str, Any] | None, game: str, answers: list[dict[str, Any]], seconds: float, today: str,
           bonus: int = 0) -> tuple[dict[str, Any], dict[str, Any]]:
    """A finished round into your progress. `answers`: [{id, right, level, terms}]. Returns (progress, summary)."""
    prog = progress if isinstance(progress, dict) and progress.get("version") == 1 else empty_progress()
    for key in ("games", "items", "topics"):
        prog.setdefault(key, {})
    g = prog["games"].setdefault(game, {"plays": 0, "xp": 0, "best": 0, "seconds": 0, "answered": 0, "right": 0})
    right = sum(1 for a in answers if a.get("right"))
    acc = right / len(answers) if answers else 0.0
    pts = points(answers, bonus)
    before, player_before = level_of(int(g["xp"])), player_level(int(prog.get("xp", 0)))
    new_best = pts > int(g.get("best", 0))
    secs = max(0, int(half_up(seconds)))
    g.update(plays=int(g["plays"]) + 1, xp=int(g["xp"]) + pts, best=max(int(g.get("best", 0)), pts),
             seconds=int(g["seconds"]) + secs, answered=int(g["answered"]) + len(answers), right=int(g["right"]) + right,
             last=today)
    prog["xp"] = int(prog.get("xp", 0)) + pts
    day = date.fromisoformat(today)
    share = secs / max(1, len(answers))
    for a in answers:
        e = prog["items"].setdefault(str(a["id"]), {"box": 0, "right": 0, "wrong": 0})
        if a.get("right"):
            e["box"] = min(int(e.get("box", 0)) + 1, len(INTERVALS) - 1)
            e["right"] = int(e.get("right", 0)) + 1
        else:
            e["box"] = 0
            e["wrong"] = int(e.get("wrong", 0)) + 1
        e["due"] = (day + timedelta(days=INTERVALS[e["box"]])).isoformat()
        e["seen"] = today
        for t in a.get("terms") or []:
            tp = prog["topics"].setdefault(t, {"right": 0, "wrong": 0, "seconds": 0})
            tp["right" if a.get("right") else "wrong"] += 1
            tp["seconds"] = int(tp["seconds"]) + int(half_up(share))
    after = level_of(int(g["xp"]))
    return prog, {"game": game, "points": pts, "right": right, "answered": len(answers), "accuracy": half_up(acc, 3),
                  "stars": stars(acc), "best": int(g["best"]), "new_best": new_best, "level": after,
                  "level_up": after > before, "player_level": player_level(int(prog["xp"])),
                  "player_level_up": player_level(int(prog["xp"])) > player_before,
                  "next_level_xp": xp_for_level(after + 1) if after < GAME_MAX_LEVEL else None, "xp": int(g["xp"])}


# ---------------------------------------------------------------------------------------------- what it teaches
def model_terms(answers: list[dict[str, Any]], seconds: float) -> dict[str, float]:
    """What the Model learns from a round: the topics you played, a right answer counting fully and a wrong one
    (something you're learning) a little less, the whole scaled by how long you played (a minute is a nudge, ten
    minutes a clear signal). The biggest TERMS_PER_ROUND terms; {} for an empty round."""
    raw: dict[str, float] = {}
    for a in answers:
        terms = a.get("terms") or []
        for t in terms:
            raw[t] = raw.get(t, 0.0) + (1.0 if a.get("right") else 0.6) / max(1, len(terms))
    if not raw:
        return {}
    minutes = max(0.0, float(seconds)) / 60
    strength = min(1.5, 0.3 + 0.12 * minutes)
    total = sum(raw.values())
    ranked = sorted(raw.items(), key=lambda kv: (-kv[1], kv[0]))[:TERMS_PER_ROUND]
    return {t: half_up(w / total * strength, 4) for t, w in ranked}


def mastery(progress: dict[str, Any], least: int = 3) -> dict[str, list[str]]:
    """Topics you know (at least `least` answers, 80% right) and ones you're learning (at least 2 wrong, under 60%
    right), each list most-played first."""
    knows, learning = [], []
    for t, tp in (progress.get("topics") or {}).items():
        r, w = int(tp.get("right", 0)), int(tp.get("wrong", 0))
        n = r + w
        if n >= least and r / n >= 0.8:
            knows.append((n, t))
        elif w >= 2 and r / n < 0.6:
            learning.append((n, t))
    return {"knows": [t for _, t in sorted(knows, key=lambda x: (-x[0], x[1]))],
            "learning": [t for _, t in sorted(learning, key=lambda x: (-x[0], x[1]))]}


def badge_counts(progress: dict[str, Any] | None) -> dict[str, int]:
    """For achievements: rounds played (Player), right answers (Sharp), levels gained across games (Level up)."""
    games = (progress or {}).get("games") or {}
    return {"player": sum(int(g.get("plays", 0)) for g in games.values()),
            "sharp": sum(int(g.get("right", 0)) for g in games.values()),
            "levelup": sum(level_of(int(g.get("xp", 0))) - 1 for g in games.values())}


def summary_of(progress: dict[str, Any] | None) -> dict[str, Any]:
    """Each game's level, best, plays and time, and your player level: what the Play page shows."""
    prog = progress or {}
    games = prog.get("games") or {}
    out = []
    for g in GAMES:
        s = games.get(g["id"]) or {}
        xp = int(s.get("xp", 0))
        lv = level_of(xp)
        nxt = xp_for_level(lv + 1) if lv < GAME_MAX_LEVEL else None
        low = xp_for_level(lv)
        out.append({"id": g["id"], "title": g["title"], "level": lv, "xp": xp, "best": int(s.get("best", 0)),
                    "plays": int(s.get("plays", 0)), "seconds": int(s.get("seconds", 0)),
                    "progress": 1.0 if nxt is None else half_up((xp - low) / max(1, nxt - low), 3)})
    xp = int(prog.get("xp", 0))
    return {"games": out, "xp": xp, "player_level": player_level(xp),
            "minutes": int(math.floor(sum(int(g.get("seconds", 0)) for g in games.values()) / 60))}


def round_terms(items: Iterable[dict[str, Any]]) -> list[str]:
    """Every field term of a round's items, once each, in order (what a game passes into its answers)."""
    out: list[str] = []
    for it in items:
        for t in it.get("terms") or []:
            if t not in out:
                out.append(t)
    return out
