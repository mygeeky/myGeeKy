"""Collaborator match: people whose skills complement yours.

A good collaborator shares your field but brings what you don't have -- and
you bring what they don't. Among fellow myGeeKy users on Signals (their
beacon's public interest tags are all myGeeKy knows about them), each is
scored on your own computer:

    field overlap (beacon.people's `fit`)
      x  what they bring: skills in their tags that you don't show (Rising Skills you lack count double)
      x  what you bring: skills you show that their tags don't,

tilted by your 👍/👎 (taste.py; 👎 hides them from this list).

Asking uses the existing 🤝 collaborate signal, which is mutual-only by design
(beacon.py): it's sealed so only they can open it, and they never see it at
all unless they choose 🤝 for you too. Then you both get "you both want to
collaborate" -- and only then does either of you learn anything. Nothing
about who you looked at or skipped leaves this computer.
"""

from __future__ import annotations

from typing import Any, Iterable

from . import skills, taste


def complement(person: dict[str, Any], have: set[str], wanted: set[str],
               strengths: Iterable[str] = ()) -> dict[str, Any]:
    """What they bring (the Rising Skills you lack first) and what you bring (your rising strengths first)."""
    strong = list(strengths)
    theirs = skills.skills_in(" ; ".join(person.get("interests") or []))
    bring = sorted(theirs - have, key=lambda s: (s not in wanted, s))
    give = sorted(have - theirs, key=lambda s: (strong.index(s) if s in strong else len(strong), s))
    return {"theirs": sorted(theirs), "they_bring": bring, "you_bring": give}


def matches(people: Iterable[dict[str, Any]], have: set[str], wanted: Iterable[str],
            collab_sent: set[str] | None = None, top: int = 12, strengths: Iterable[str] = ()) -> dict[str, Any]:
    """{"people": [...best first], "hidden": n}. `people` are beacon.people() rows."""
    wanted = set(wanted)
    sent = {s.lower() for s in (collab_sent or set())}
    votes = taste.load()
    lean_w = taste.weights(["collaborator"])
    out, hidden = [], 0
    for p in people:
        login = p.get("login", "")
        if not login or p.get("muted"):
            continue
        v = int(votes.get(taste.key_of("collaborator", login), {}).get("vote", 0))
        if v < 0:
            hidden += 1
            continue
        c = complement(p, have, wanted, strengths)
        bring = len(c["they_bring"]) + sum(1 for s in c["they_bring"] if s in wanted)
        if not (c["they_bring"] or p.get("shared")):
            continue                     # nothing in common and nothing new: not a match
        fit = float(p.get("fit") or 0.0)
        score = (0.25 + fit) * (0.5 + 0.5 * min(1.0, bring / 3)) * (0.6 + 0.4 * min(1.0, len(c["you_bring"]) / 3))
        score *= 1 + 0.4 * taste.lean(" ; ".join(p.get("interests") or []), [], lean_w)
        if v > 0:
            score *= 1.3
        out.append({**p, **c, "score": round(score, 4), "vote": v, "asked": login.lower() in sent})
    out.sort(key=lambda x: x["score"], reverse=True)
    return {"people": out[:top], "hidden": hidden}
