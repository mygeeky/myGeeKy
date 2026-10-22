"""GeeKOc's tours and Help: which tour to show, when, and what each stop says (data/tour.json).

A tour is a list of stops. A stop opens a page (its "at" for this app: a place in the navigation, "settings", a
part of ⚙ like "settings:cv", or "help") and GeeKOc says one thing about it, in the language picked for the tours.
The general tour depends on what the user gave at setup -- GitHub, ORCID, both, a CV, or none -- and every one
visits Seasons and Jobs right after Home, ends with what more there is, the five never-dos and the motto. Help
starts any tour again: the general one, Settings', or one for each main.

When it opens by itself: the first time after setup, and after an update that brings new stops (only those).
Never under tests or on CI, so nothing waits on a bubble (blocked()).

The phone has the same rules (mobile/src/lib/tour.ts) and an identical copy of the data; tests/test_tour.py checks
both.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

DATA = Path(__file__).parent / "data" / "tour.json"
KINDS = ("github", "orcid", "both", "cv", "none")
MAINS = ("home", "you", "grow", "world", "circle", "repos", "chances")      # Help has a tour for each (not itself)
# the parts of Settings a stop can point at ("settings:cv"); each app finds its own section for each
SETTINGS_PARTS = ("look", "place", "papers", "cv", "wisep", "packs", "setup", "sync")
FALLBACK = "en"


@lru_cache(maxsize=1)
def load() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def version() -> int:
    return int(load()["version"])


def kind(github: bool, orcid: bool, cv: bool) -> str:
    """What the user gave at setup, as one word. ORCID counts for an OpenAlex id found by name too."""
    if github and orcid:
        return "both"
    if github:
        return "github"
    if orcid:
        return "orcid"
    return "cv" if cv else "none"


def kind_for(cfg: Any) -> str:
    return kind(bool(getattr(cfg, "github_username", "")),
                bool(getattr(cfg, "orcid_id", "") or getattr(cfg, "openalex_id", "")),
                bool(getattr(cfg, "cv_path", "")))


def lang_of(lang: str) -> str:
    return lang if lang in load()["langs"] else FALLBACK


def rtl(lang: str) -> bool:
    return lang_of(lang) in load()["rtl"]


def at(stop: str, platform: str) -> str:
    """Where a stop takes this app ("" for a stop that only talks, like the welcome)."""
    return (load()["stops"][stop].get("at") or {}).get(platform, "")


def shown_on(stop: str, platform: str) -> bool:
    """A stop that opens a page exists on an app only if that app has the page."""
    s = load()["stops"][stop]
    return "at" not in s or platform in s["at"]


def stops(name: str, kind_: str, platform: str) -> list[str]:
    """The stops of a tour: "start" (the general one, by kind), "settings", or a main ("grow")."""
    t = load()["tours"][name]
    ids = t[kind_ if kind_ in t else "none"] if isinstance(t, dict) else t
    return [s for s in ids if shown_on(s, platform)]


def text(stop: str, lang: str, kind_: str = "none") -> str:
    s, lang = load()["stops"][stop], lang_of(lang)
    words = s["by_kind"].get(kind_, s["by_kind"]["none"]) if "by_kind" in s else s["t"]
    return words.get(lang) or words[FALLBACK]


def phrase(stop: str, lang: str) -> str:
    """The motto under the last stop's words ("" for the others)."""
    p = load()["stops"][stop].get("phrase") or {}
    return p.get(lang_of(lang)) or p.get(FALLBACK, "")


def ui(key: str, lang: str, **fill: str) -> str:
    words = load()["ui"][key]
    out = words.get(lang_of(lang)) or words[FALLBACK]
    for k, v in fill.items():
        out = out.replace("{" + k + "}", v)
    return out


def blocked(env: Mapping[str, str] | None = None) -> bool:
    """Never by itself under tests, on CI (GitHub Actions sets CI) or with MYGEEKY_NO_TOUR=1 (the screenshot,
    theme and resource scripts set it): a bubble nobody clicks would sit over every page."""
    env = os.environ if env is None else env
    return any(env.get(k, "") not in ("", "0", "false") for k in ("CI", "MYGEEKY_NO_TOUR", "PYTEST_CURRENT_TEST"))


def auto(seen: int, kind_: str, platform: str, env: Mapping[str, str] | None = None) -> list[str]:
    """The tour that opens by itself, or []: all of it the first time (seen 0), only the newer stops after an
    update that brought some, nothing otherwise."""
    if blocked(env) or seen >= version():
        return []
    full = stops("start", kind_, platform)
    if seen <= 0:
        return full
    s = load()["stops"]
    new = [x for x in full if int(s[x].get("since", 1)) > seen and x not in ("welcome", "end")]
    return ["welcome_new", *new, "end"] if new else []


def faq(lang: str) -> list[tuple[str, str]]:
    lang = lang_of(lang)
    return [(e["q"].get(lang) or e["q"][FALLBACK], e["a"].get(lang) or e["a"][FALLBACK]) for e in load()["faq"]]
