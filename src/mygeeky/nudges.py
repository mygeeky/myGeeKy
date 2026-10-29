"""Cards that ask again, gently, for what setup skipped: saving your data (Google Drive recommended, or a GitHub repo),
your ORCID, GitHub. Each shows on the pages it would improve, never in the first week, and fades out:

- it first appears after a week of use (7 days you opened myGeeKy, not 7 calendar days);
- "Not now": back after 2 more days of use; after 3 "Not now"s, once a week of use;
- two months after it first appeared it stops for good; "Don't ask again" stops it at once;
- at most one kind of card a day, across every page (saving first, then ORCID, then GitHub);
- linked: never.

What it remembers stays on this device (nudges.json beside config.json). The phone has the same rules, line for line
(mobile/src/lib/nudges.ts); tests/test_nudges.py holds both to the same answers. Settings -> Accounts always offers
all three, whatever the cards do.
"""
from __future__ import annotations

import json
from datetime import date as Date
from typing import Any

KEYS = ("data", "orcid", "github")                 # which card first, when more than one is due the same day
START = 7                                           # days of use before a first card
AGAIN = 2                                           # days of use after a "Not now"
WEEKLY_AFTER = 3                                    # "Not now"s after which it comes once a week of use
WEEK = 7
GIVE_UP = 60                                        # calendar days after it first appeared

# where each card shows: the pages it makes better (a place is the same on both apps, whatever the page's id)
PLACES = {
    "data": ("month", "model"),
    "orcid": ("cited", "researchers", "highlights", "jobs"),
    "github": ("repos", "rising", "month"),
}
# each app's page ids -> places (the computer's ids, then the phone's; Researchers' parts by their prefix)
PAGE_PLACE = {
    "model:month": "month", "you:month": "month", "model:model": "model", "you:model": "model",
    "model:cited": "cited", "you:cited": "cited", "grow:highlights": "highlights", "chances:jobs": "jobs",
    "repos": "repos", "repos:help": "repos", "market:repos": "rising", "repos:rising": "rising",
}


def place_of(page: str) -> str:
    if page == "researchers" or page.startswith("researchers:"):
        return "researchers"
    return PAGE_PLACE.get(page, "")


def text(key: str, device: str) -> dict[str, str]:
    """What a card says (device: "computer" or "phone")."""
    if key == "data":
        return {"title": "Keep your progress safe",
                "text": f"What myGeeKy has learned about you lives only on this {device}. Save it in your own Google "
                        "Drive (recommended) or a private GitHub repo: your other devices share it, and nothing is lost "
                        f"if this {device} is.",
                "go": "Choose where to save"}
    if key == "orcid":
        return {"title": "Add your ORCID",
                "text": "With your ORCID, myGeeKy finds your papers, shows who cites you, and fits researchers and jobs "
                        "to your own work.",
                "go": "Add ORCID"}
    return {"title": "Link GitHub",
            "text": "Read-only: myGeeKy sees your repos and activity to suggest projects to help and people to follow. "
                    "It never posts for you.",
            "go": "Link GitHub"}


def fresh() -> dict[str, Any]:
    return {"days": 0, "last": "", "cards": {}, "today": {"date": "", "key": ""}}


def _card(state: dict[str, Any], key: str) -> dict[str, Any]:
    return state["cards"].setdefault(key, {"first": "", "skips": 0, "next": 0, "never": False})


def _between(a: str, b: str) -> int:
    return (Date.fromisoformat(b) - Date.fromisoformat(a)).days


def used(state: dict[str, Any], today: str) -> None:
    """You opened myGeeKy today: a day of use (once a day)."""
    if state["last"] != today:
        state["last"] = today
        state["days"] += 1


def due(state: dict[str, Any], key: str, today: str) -> bool:
    c = state["cards"].get(key) or {"first": "", "skips": 0, "next": 0, "never": False}
    if c["never"] or state["days"] < START or state["days"] < c["next"]:
        return False
    if c["first"] and _between(c["first"], today) >= GIVE_UP:
        return False
    t = state["today"]
    return not (t["date"] == today and t["key"] not in ("", key))


def pick(state: dict[str, Any], page: str, today: str, missing: list[str] | set[str]) -> str:
    """The card for this page today, if any: the first due one this page is a place of, among what's missing.
    Picking it counts as showing it (its two months start, and no other kind shows today)."""
    used(state, today)
    place = place_of(page)
    for key in KEYS:
        if key in missing and place in PLACES[key] and due(state, key, today):
            c = _card(state, key)
            c["first"] = c["first"] or today
            state["today"] = {"date": today, "key": key}
            return key
    return ""


def skip(state: dict[str, Any], key: str) -> None:
    """Not now: back after 2 days of use, or a week of use after the third time."""
    c = _card(state, key)
    c["skips"] += 1
    c["next"] = state["days"] + (AGAIN if c["skips"] < WEEKLY_AFTER else WEEK)


def never(state: dict[str, Any], key: str) -> None:
    _card(state, key)["never"] = True


# ---- where it's kept: this device only
def _path():
    from . import config
    return config.CONFIG_DIR / "nudges.json"


def load() -> dict[str, Any]:
    try:
        state = json.loads(_path().read_text(encoding="utf-8"))
        return state if isinstance(state, dict) and "cards" in state else fresh()
    except (OSError, ValueError):
        return fresh()


def save(state: dict[str, Any]) -> None:
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass
