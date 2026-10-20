"""Your 👍 and 👎: the part of your model you teach by hand.

Every suggestion in the growth features (Rising Skills, learning resources,
jobs, funding, conferences, collaborators) has a thumb up and a thumb down.
A vote remembers the item and a handful of its terms (its keywords and
skills, a few words of its title -- never more), so it teaches more than
that one item: 👎 on three wet-lab postdocs pushes wet-lab jobs down, 👍 on a
Nextflow tutorial lifts Nextflow everywhere.

Votes fade with a half-life (a year: tastes change slowly, but they change),
live in taste.json -- synced to your private data repo, like everything you
teach myGeeKy -- and never leave your own computers. Pressing the same thumb
again takes the vote back.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import TASTE_FILE, ensure_dirs
from .files import read_json, write_json

HALF_LIFE_DAYS = 365
MAX_TERMS = 10
MAX_VOTES = 2000            # the oldest go first; plenty for years of use
KINDS = ("skill", "resource", "job", "funding", "conference", "collaborator", "dataset")
_WORD = re.compile(r"[a-z][a-z0-9+#.-]{2,}")
_SKIP = set("""
the and for with from into this that your their our are was were has have had not but all any can
new using use based via about over under more most other some such than then them they its
position positions job jobs phd postdoc postdoctoral master masters student students fellow fellowship
research researcher scientist university institute department lab laboratory group center centre
program programme course courses tutorial tutorials learn learning conference conferences annual
international workshop call grant grants funding award awards apply application deadline open
""".split())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def key_of(kind: str, item_id: str) -> str:
    return f"{kind}:{str(item_id).strip().lower()}"


def terms_of(text: str = "", tags: Iterable[str] = ()) -> list[str]:
    """What a vote teaches: the item's tags first (keywords, skills), then a few title words."""
    out: list[str] = []
    for t in tags:
        t = " ".join(str(t).lower().replace("_", " ").split())
        if 2 <= len(t) <= 40 and t not in out:
            out.append(t)
    for w in _WORD.findall((text or "").lower()):
        w = w.strip(".-")
        if w not in _SKIP and w not in out and len(w) >= 3:
            out.append(w)
    return out[:MAX_TERMS]


def load() -> dict[str, dict[str, Any]]:
    data = read_json(TASTE_FILE, {})
    votes = data.get("votes") if isinstance(data, dict) else None
    return {k: v for k, v in (votes or {}).items()
            if isinstance(k, str) and isinstance(v, dict) and v.get("vote") in (1, -1)}


def _save(votes: dict[str, dict[str, Any]]) -> None:
    if len(votes) > MAX_VOTES:
        keep = sorted(votes.items(), key=lambda kv: str(kv[1].get("at", "")), reverse=True)[:MAX_VOTES]
        votes = dict(keep)
    ensure_dirs()
    write_json(TASTE_FILE, {"votes": votes}, indent=1)


def vote_of(kind: str, item_id: str) -> int:
    """1 (👍), -1 (👎) or 0 (no vote)."""
    return int(load().get(key_of(kind, item_id), {}).get("vote", 0))


def vote(kind: str, item_id: str, up: bool, text: str = "", tags: Iterable[str] = ()) -> int:
    """Record 👍 (up=True) or 👎. The same thumb again takes the vote back.
    Returns the vote now in place: 1, -1 or 0."""
    if kind not in KINDS or not str(item_id).strip():
        return 0
    votes = load()
    key = key_of(kind, item_id)
    value = 1 if up else -1
    if votes.get(key, {}).get("vote") == value:
        votes.pop(key)
        _save(votes)
        return 0
    votes[key] = {"vote": value, "kind": kind, "terms": terms_of(text, tags),
                  "at": _now().isoformat(timespec="seconds")}
    _save(votes)
    return value


def clear(kind: str, value: int | None = None) -> int:
    """Take back the votes on one kind of thing (only the 👎 ones with value=-1). Returns how many."""
    votes = load()
    drop = [k for k, v in votes.items() if v.get("kind") == kind and (value is None or v["vote"] == value)]
    for k in drop:
        votes.pop(k)
    if drop:
        _save(votes)
    return len(drop)


def weights(kinds: Iterable[str] | None = None, now: datetime | None = None) -> dict[str, float]:
    """term -> how much your votes like it (+) or don't (-), fading with time.
    `kinds` limits it to votes on those kinds of things (None: all of them)."""
    now = now or _now()
    wanted = set(kinds) if kinds is not None else None
    out: dict[str, float] = {}
    for v in load().values():
        if wanted is not None and v.get("kind") not in wanted:
            continue
        try:
            age = (now - datetime.fromisoformat(v["at"])).total_seconds() / 86400
        except (KeyError, TypeError, ValueError):
            age = 0.0
        fade = 0.5 ** (max(age, 0.0) / HALF_LIFE_DAYS)
        terms = v.get("terms") or []
        for i, term in enumerate(terms):
            share = 1.0 if i < 3 else 0.5      # the item's own tags count most
            out[term] = out.get(term, 0.0) + v["vote"] * share * fade
    return out


def _hit(term: str, text: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"s?(?![a-z0-9])", text) is not None


def lean(text: str, tags: Iterable[str], w: dict[str, float]) -> float:
    """-1..1: how your votes lean on something with this text and these tags."""
    if not w:
        return 0.0
    hay = " ".join([(text or "").lower(), *(str(t).lower().replace("_", " ") for t in tags)])
    total = sum(v for t, v in w.items() if _hit(t, hay))
    return math.tanh(total / 2.0)


def counts() -> dict[str, int]:
    """How many 👍 and 👎 you've given, all kinds together (shown on the Model tab)."""
    votes = load().values()
    return {"up": sum(1 for v in votes if v["vote"] == 1), "down": sum(1 for v in votes if v["vote"] == -1)}
