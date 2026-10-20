"""Starting myGeeKy from your field alone -- no ORCID, no GitHub, no account anywhere.

Most of myGeeKy only ever needed to know what your field is: the verified jobs, funding, conferences and
seasons, the rising skills, the quiz, the news, the papers, the market board and the repos worth improving
are all picked by matching your field against public pages. None of them look you up. So the shortest
honest way in is to ask what you work on and nothing else.

Asking is the hard part. "Type ten keywords" is a blank page, and a blank page at the door is why people
leave. Instead myGeeKy offers five, learns from whichever you take, and offers five more -- and the
dictionary it offers them from (keywords.json: 300 topics, each with up to twelve weighted related ones)
is already the graph that makes this work, so nothing new had to be trained.

Two things keep the rounds from funnelling you into a cul-de-sac:

  * NEAR AND FAR. Three of each five are near what you have picked (they confirm), two are deliberately
    far from it (they discover). All-near would mean one tap on "16s" leaves you looking at amplicon
    sequencing for the rest of your life, with no way back.
  * DISMISSING COUNTS. A chip you wave away is taken as a no for its whole neighbourhood, not just itself.

And when the dictionary simply does not have your word -- it was built from software topics, so it is
thinner on the bench than at the terminal -- you are not stuck with ours: `alternatives` offers the nearest
things it does know, `topics_like` asks OpenAlex for the research-side name, and a word we have never
heard of is still kept exactly as you typed it. An unknown keyword ranks on itself; a known one also
brings its relations. Nothing is lost by typing something we do not know.
"""
from __future__ import annotations

import difflib
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from . import keywords
from .config import MyGeekyConfig

PER_ROUND = 5                 # chips offered at a time: more is a wall of text, fewer is a slow start
NEAR = 3                      # of those, how many are related to what you already picked
FAR = PER_ROUND - NEAR        # ... and how many are deliberately somewhere else
ENOUGH_PICKS = 6              # the fewest that can describe a field at all
ENOUGH_AREAS = 3              # ... spread over at least this many separate areas
GOAL = 10                     # what the bar fills up to: a good profile, not a required one
SHOW_RELATED = 4              # related terms printed under a chip, so a bare slug can be judged
MAX_ALTERNATIVES = 6

# The nudge to make a real account: four asks over three months, then never again. A keyword-only user is
# a real user, not a lapsed signup, so this never takes anything away -- see `nudge`.
ASK_ON_DAYS = (7, 21, 45, 90)
_OPENALEX_TOPICS = "https://api.openalex.org/autocomplete/topics"


# --------------------------------------------------------------------------- the graph behind the chips
def _terms() -> dict[str, Any]:
    return keywords.load().get("terms") or {}


def _neighbours(topic: str) -> set[str]:
    entry = _terms().get(topic) or {}
    return {str(rel) for rel, _ in entry.get("related") or []}


def _degree() -> dict[str, int]:
    """How many other topics point at each one. A hub term covers more ground than a leaf, which is what
    makes it a good opening question ("which of these worlds is yours?") and a good far suggestion."""
    terms = _terms()
    counted: dict[str, int] = {t: 0 for t in terms}
    for entry in terms.values():
        for rel, _ in entry.get("related") or []:
            if rel in counted:
                counted[rel] += 1
    return counted


def _spread(candidates: Iterable[str], avoid: set[str], want: int) -> list[str]:
    """The most-connected candidates that are not neighbours of each other or of anything in `avoid`.

    Sorted by degree then name so the same picks always give the same chips: a picker that reshuffled on
    every repaint would be unusable, and untestable."""
    degree = _degree()
    out: list[str] = []
    taken = set(avoid)
    for topic in sorted(candidates, key=lambda t: (-degree.get(t, 0), t)):
        if topic in taken or topic in keywords.GENERIC:
            continue
        if _neighbours(topic) & taken:
            continue
        out.append(topic)
        taken |= _neighbours(topic) | {topic}
        if len(out) >= want:
            break
    return out


def opening() -> list[dict[str, Any]]:
    """The first five, before anything is known: hub topics as far apart as the dictionary allows."""
    return [_chip(t) for t in _spread(_terms(), set(), PER_ROUND)]


def _chip(topic: str) -> dict[str, Any]:
    """One offered keyword, with enough of its meaning to be judged.

    The dictionary holds related terms rather than definitions, which reads better anyway: nobody can say
    whether "16s" is them, and everybody can say whether "microbiome, metagenomics, dada2" is."""
    entry = _terms().get(topic) or {}
    related = [keywords.label_of(str(rel)) for rel, _ in (entry.get("related") or [])[:SHOW_RELATED]]
    return {"topic": topic, "label": entry.get("label") or keywords.label_of(topic), "related": related,
            "means": ", ".join(related)}


# --------------------------------------------------------------------------- a round of suggestions
def _topics_of(terms: Iterable[str]) -> set[str]:
    """What the user picked or waved away, as dictionary topics (their own words stay their own)."""
    out = set()
    for term in terms or ():
        entry = keywords.lookup(term)
        if entry:
            out.add(str(entry["topic"]))
    return out


def suggest(picked: Iterable[str] = (), dismissed: Iterable[str] = (), shown: Iterable[str] = (),
            want: int = PER_ROUND) -> list[dict[str, Any]]:
    """The next chips to offer, given everything that has happened so far.

    `picked` pulls NEAR suggestions out of its own neighbourhood. `dismissed` pushes a whole neighbourhood
    away, not just the word itself -- someone waving off "webgl" does not want "threejs" next. `shown`
    keeps a chip from being offered twice, so a round always says something new.
    """
    mine = _topics_of(picked)
    if not mine:
        return [c for c in opening() if c["topic"] not in _topics_of(shown)][:want]

    no = set()
    for topic in _topics_of(dismissed):
        no |= _neighbours(topic) | {topic}
    seen = mine | no | _topics_of(shown)

    # Near: the strongest relations of what was picked, by weight -- NOT spread apart. Near chips are
    # meant to be in one neighbourhood; running them through _spread left only one survivor, because
    # everything around "machine learning" is also around everything else there.
    strength: dict[str, float] = {}
    known = _terms()
    for topic in mine:
        for rel, weight in (known.get(topic) or {}).get("related") or []:
            if rel in seen or rel in keywords.GENERIC:
                continue
            # Only terms the dictionary has an ENTRY for. A related term need not itself be an entry --
            # only 21% are -- and offering one of those gave a chip with no meaning to judge it by, no
            # neighbourhood to wave away, and nothing for `areas` to place it in. Every term's twelve
            # neighbours include at least five real entries, and a round needs three.
            if rel not in known:
                continue
            strength[str(rel)] = max(strength.get(str(rel), 0.0), float(weight))
    near = sorted(strength, key=lambda t: (-strength[t], t))[:min(NEAR, want)]

    # Far: hubs that touch nothing you have picked OR dismissed, so a wrong first tap is recoverable and a
    # second field (everyone has one) can still be found.
    away = seen | {rel for topic in mine for rel in _neighbours(topic)}
    far = _spread(_terms(), away | set(near), want - len(near))

    out = [_chip(t) for t in near + far]
    if len(out) < want:              # a narrow dictionary corner: fill from anything still unseen
        out += [_chip(t) for t in _spread(_terms(), seen | {c["topic"] for c in out}, want - len(out))]
    return out[:want]


def areas(picked: Iterable[str]) -> int:
    """How many separate parts of the field the picks cover.

    Six keywords from one corner say less than three from three corners, which is why this and not a count
    decides when there is enough. Two picks share an area when either lists the other, or they lean on the
    same relations."""
    topics = sorted(_topics_of(picked))
    if not topics:
        return 0
    parent = {t: t for t in topics}

    def root(t: str) -> str:
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t

    for i, a in enumerate(topics):
        for b in topics[i + 1:]:
            near_a, near_b = _neighbours(a) | {a}, _neighbours(b) | {b}
            if b in near_a or a in near_b or len(near_a & near_b) >= 3:
                parent[root(a)] = root(b)
    return len({root(t) for t in topics})


def ready(picked: Iterable[str]) -> dict[str, Any]:
    """Whether the picks describe a field well enough to start, and how full the bar looks.

    Deliberately not "ten keywords". Ten taps is a long door to walk through, and ten words from one
    corner rank worse than six across three areas -- so the bar is spread, with ten kept as the mark of a
    good profile rather than the price of entry. Nothing stops anyone going past it."""
    got = [t for t in (picked or ()) if str(t).strip()]
    spread = areas(got)
    vocabulary = keywords.expand(got)
    return {"ok": len(got) >= ENOUGH_PICKS and spread >= ENOUGH_AREAS,
            "picks": len(got), "areas": spread, "goal": GOAL,
            "terms": len(vocabulary),           # what the picks actually became, after their relations
            "bar": min(1.0, round(len(got) / GOAL, 3)),
            "need": _need(len(got), spread)}


def _need(picks: int, spread: int) -> str:
    if picks < ENOUGH_PICKS:
        left = ENOUGH_PICKS - picks
        return f"{left} more keyword{'s' if left > 1 else ''}"
    if spread < ENOUGH_AREAS:
        return "something from another part of your work"
    if picks < GOAL:
        return f"good — {GOAL - picks} more would sharpen it"
    return ""


# --------------------------------------------------------------------------- words we do not know
def alternatives(typed: str, want: int = MAX_ALTERNATIVES) -> list[dict[str, Any]]:
    """The nearest things the dictionary does know, for a word it does not.

    The dictionary was built from software topics, so it is thinner on the bench than at the terminal. A
    plant breeder typing "marker assisted selection" should not be told no -- they should be shown what we
    have that is close, and keep their own words either way."""
    word = " ".join(str(typed or "").lower().split())
    if not word:
        return []
    entry = keywords.lookup(word)
    if entry:
        return [_chip(str(entry["topic"]))]

    terms = _terms()
    parts = [p for p in re.split(r"[\s\-_/]+", word) if len(p) > 2]
    scored: dict[str, float] = {}
    for topic, meta in terms.items():
        label = str(meta.get("label") or topic)
        text = f"{topic} {label}".lower()
        hit = sum(1.0 for p in parts if p in text)
        ratio = difflib.SequenceMatcher(None, word, topic.replace("-", " ")).ratio()
        # A shared word, or a near-spelling of the whole phrase. A wrong answer is worse than admitting
        # we have nothing, because a wrong one gets picked and then ranks everything against it: a loose
        # ratio offered "image classification" for "marker assisted selection", and "health" for "wheat"
        # (0.727 -- they share h, e, a, t). Spelling alone has to be a near-identity, and only for a word
        # long enough for that to mean something; a shared whole word is the honest signal.
        if hit or (ratio >= 0.85 and len(word) >= 6):
            scored[topic] = hit * 2 + ratio
    best = sorted(scored, key=lambda t: (-scored[t], t))[:want]
    return [_chip(t) for t in best]


def topics_like(typed: str, want: int = MAX_ALTERNATIVES, timeout: float = 8.0) -> list[dict[str, Any]]:
    """What the research world calls it, when we have nothing close.

    OpenAlex names topics the way papers do rather than the way repositories do, which is exactly the gap
    in our own dictionary. Needs the network, so it is the last resort and never the first, and a failure
    here is silent: the typed word is kept regardless."""
    word = " ".join(str(typed or "").lower().split())
    if not word:
        return []
    try:
        from . import wisep
        resp = wisep.session("setup").get(_OPENALEX_TOPICS, params={"q": word}, timeout=timeout,
                                          headers={"User-Agent": "mygeeky"})
        if resp.status_code != 200:
            return []
        found = resp.json().get("results") or []
    except Exception:
        return []
    out = []
    for item in found[:want]:
        name = str(item.get("display_name") or "").strip()
        if not name:
            continue
        # OpenAlex hints are whole paragraphs. A chip needs a line: the first sentence, cut to fit.
        hint = " ".join(str(item.get("hint") or "").split())
        hint = hint.split(". ")[0]
        if len(hint) > 110:
            hint = hint[:107].rsplit(" ", 1)[0] + "…"
        out.append({"topic": keywords.slug(name), "label": name, "related": [], "means": hint,
                    "from": "openalex"})
    return out


def offer_for(typed: str, online: bool = False) -> dict[str, Any]:
    """Everything myGeeKy can say about a word somebody typed.

    `keep` is the answer either way: a keyword we have never heard of still ranks on itself (see
    keywords.expand), so an unknown word is a thinner match, never a refused one."""
    word = " ".join(str(typed or "").strip().split())
    known = keywords.lookup(word)
    near = alternatives(word)
    if not known and not near and online:
        near = topics_like(word)
    return {"typed": word, "known": bool(known), "keep": word, "alternatives": near,
            "note": "" if known else ("myGeeKy doesn't know this one — it still counts, just on its own. "
                                      "These are the nearest it does know:" if near else
                                      "myGeeKy doesn't know this one — it still counts, on its own.")}


# --------------------------------------------------------------------------- the ask for a real account
def started(cfg: MyGeekyConfig) -> str:
    return str(getattr(cfg, "field_started_at", "") or "")


def begin(cfg: MyGeekyConfig, today: date | None = None) -> MyGeekyConfig:
    """Remember when someone started from keywords alone, so the asking can end on time."""
    if not started(cfg):
        cfg.field_started_at = (today or _today()).isoformat()
    return cfg


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _as_date(said: str) -> date | None:
    try:
        return date.fromisoformat(str(said)[:10])
    except ValueError:
        return None


def nudge(cfg: MyGeekyConfig, today: date | None = None, wall: str = "") -> dict[str, Any]:
    """Whether to ask for an ORCID or GitHub account now, and what to say.

    Three choices worth stating, because each is the opposite of the obvious one:

      * FOUR ASKS, NOT TWELVE. Weekly for three months is twelve interruptions about one decision. Day 7,
        21, 45, 90 covers the same ground and respects the answer in between.
      * ASK WHERE THE WALL IS. Someone who just tapped Signals is asking the question themselves; a
        Monday pop-up is an advert. A wall is asked about once, ever, and then left alone.
      * AFTER THREE MONTHS, STOP ASKING -- AND KEEP WORKING. Nothing is withdrawn, ever. If it stopped
        working it would be a trial, and "yours, on your computer" would stop being true. The last ask is
        the honest one: an account is where your saved chances and wins survive this computer.
    """
    if getattr(cfg, "github_username", "") or getattr(cfg, "orcid_id", ""):
        return {"ask": False, "why": "", "last": False, "reason": "already signed in"}
    today = today or _today()
    asked = list(getattr(cfg, "account_walls_asked", []) or [])
    if wall:
        if wall in asked:
            return {"ask": False, "why": "", "last": False, "reason": "this wall was asked about already"}
        return {"ask": True, "wall": wall, "why": _WALLS.get(wall, _WALLS["backup"]), "last": False,
                "reason": "they just reached for something an account is needed for"}

    begun = _as_date(started(cfg))
    if begun is None:
        return {"ask": False, "why": "", "last": False, "reason": "no start date yet"}
    days = (today - begun).days
    done = int(getattr(cfg, "account_asks", 0) or 0)
    if done >= len(ASK_ON_DAYS):
        return {"ask": False, "why": "", "last": False, "reason": "asked enough; myGeeKy keeps working"}
    if days < ASK_ON_DAYS[done]:
        return {"ask": False, "why": "", "last": False, "reason": f"next ask on day {ASK_ON_DAYS[done]}"}
    last = done == len(ASK_ON_DAYS) - 1
    return {"ask": True, "wall": "", "last": last, "days": days,
            "why": _WALLS["backup"] if last else _WALLS["more"],
            "reason": "the last time myGeeKy brings it up" if last else "scheduled"}


_WALLS = {
    "signals": "Signals is how people thank each other for the code they use, so it needs an account to "
               "be thanked at. Everything else on this panel keeps working without one.",
    "collab": "Finding people whose skills complement yours works through Signals, which needs an account.",
    "followback": "Who would likely follow you back is scored against your own account. The researchers "
                  "below, found by searching your field, need nothing.",
    "activity": "Activity is the feed of people you follow, so there has to be an account doing the "
                "following.",
    "phone": "Your phone and this computer pass data through your own private GitHub repo, so carrying "
             "myGeeKy to a second device needs an account.",
    "more": "myGeeKy is working from your keywords. An ORCID iD would add your own papers to what it "
            "matches against, and a GitHub account adds Activity, Signals and Collab. Neither is "
            "required, and this stays yours either way.",
    "backup": "Everything you have saved lives on this computer and nowhere else. An account is how it "
              "survives a new laptop -- that, and nothing else, is what myGeeKy cannot do without one.",
}


def asked(cfg: MyGeekyConfig, wall: str = "", today: date | None = None) -> MyGeekyConfig:
    """Write down that the ask happened, so it does not happen again today."""
    if wall:
        walls = list(getattr(cfg, "account_walls_asked", []) or [])
        if wall not in walls:
            walls.append(wall)
        cfg.account_walls_asked = walls
        return cfg
    cfg.account_asks = int(getattr(cfg, "account_asks", 0) or 0) + 1
    cfg.account_asked_at = (today or _today()).isoformat()
    return cfg


def keep(cfg: MyGeekyConfig, picked: Iterable[str]) -> MyGeekyConfig:
    """Add the picked keywords to the profile, keeping whatever is already there.

    Merged, never replaced: somebody who later signs in with ORCID must not watch the field they spent
    five rounds describing get overwritten by their publication list. profile_terms adds both up."""
    had = [str(k) for k in (cfg.keywords or [])]
    seen = {k.lower() for k in had}
    for term in picked or ():
        word = " ".join(str(term).lower().split())
        if word and word not in seen:
            had.append(word)
            seen.add(word)
    cfg.keywords = had
    return begin(cfg)


def summary(cfg: MyGeekyConfig, today: date | None = None) -> dict[str, Any]:
    """What the panel shows about a keyword-only profile: where it stands, and what it cannot do."""
    state = ready(cfg.keywords or [])
    ask = nudge(cfg, today=today)
    return {**state, "keywords": list(cfg.keywords or []), "started": started(cfg),
            "has_account": bool(cfg.github_username or cfg.orcid_id),
            "asks_left": max(0, len(ASK_ON_DAYS) - int(getattr(cfg, "account_asks", 0) or 0)),
            "ask": ask, "needs_account": sorted(k for k in _WALLS if k not in ("more", "backup"))}


def days_left(cfg: MyGeekyConfig, today: date | None = None) -> int | None:
    """Days until myGeeKy stops bringing an account up at all. None once it already has."""
    begun = _as_date(started(cfg))
    if begun is None:
        return None
    left = (begun + timedelta(days=ASK_ON_DAYS[-1]) - (today or _today())).days
    return max(0, left)
