"""Lists myGeeKy's maker curates by hand: jobs, funding, conferences and learning resources.

Every item is added by the maker after checking it's real -- that's the
promise of "Verified jobs". There is no server: the lists are one file in
the public repo, `src/mygeeky/data/curated.json`. Each myGeeKy downloads the
whole file (at most every few hours) and matches it to you on your own
computer, with your model (interests.profile_terms) and your 👍/👎 (taste.py).
Nobody -- not the maker, not the poster -- learns who matched what, or that
you looked.

Anything with a deadline disappears by itself the day after it: the app hides
it straight away, and a daily job in the repo removes it from the file
(`python -m mygeeky.curated prune`).

    {"version": "2026-10-13T12:00:00Z",
     "jobs":        [{"id", "title", "org", "place", "url", "deadline", "type", "keywords", "summary"}],
     "funding":     [{"id", "title", "org", "url", "deadline", "who", "amount", "keywords", "summary"}],
     "conferences": [{"id", "title", "place", "url", "deadline", "starts", "ends", "student", "keywords", "summary"}],
     "resources":   [{"id", "title", "url", "type", "skills", "keywords", "level", "free", "summary"}],
     "protocols":   [{"id", "skill", "goal", "title", "summary", "stages": [...]}]}   # see protocols.py

The file is someone else's text by the time it reaches you: every field is
checked, lengths are capped, and only https links survive.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urlsplit

import requests

from . import taste
from .config import CURATED_FILE, MyGeekyConfig, ensure_dirs
from .files import read_json, write_json

BUNDLED = Path(__file__).parent / "data" / "curated.json"
REMOTE_URL = "https://raw.githubusercontent.com/mygeeky/myGeeKy/main/src/mygeeky/data/curated.json"
CHECK_EVERY_HOURS = 6
LISTS = ("jobs", "funding", "conferences", "resources")
DATED = ("jobs", "funding", "conferences")       # these disappear after their deadline
VOTE_KIND = {"jobs": "job", "funding": "funding", "conferences": "conference", "resources": "resource"}
JOB_TYPES = {"phd": "PhD", "postdoc": "Postdoc", "master": "Master's", "job": "Job", "internship": "Internship",
             "fellowship": "Fellowship", "faculty": "Faculty", "engineer": "Research engineer"}
RESOURCE_TYPES = {"repo": "📦", "website": "🌐", "course": "🎓", "book": "📖", "tutorial": "🧭", "video": "🎬"}
LEVELS = ("beginner", "intermediate", "advanced")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REPORT_EMAIL = "support@mygeeky.org"
REPORT_REPO = "mygeeky/myGeeKy-ideas"

_loaded: dict[str, Any] | None = None


# --------------------------------------------------------------------------- reading the file safely
def _text(value: Any, n: int) -> str:
    return " ".join(str(value or "").split())[:n] if isinstance(value, (str, int, float)) else ""


def _https(value: Any) -> str:
    url = str(value or "").strip()
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    return url[:500] if parts.scheme == "https" and parts.netloc and " " not in url else ""


def _day(value: Any) -> str:
    s = str(value or "")[:10]
    if not _DATE.match(s):
        return ""
    try:
        date.fromisoformat(s)
    except ValueError:
        return ""
    return s


def _words(values: Any, n: int = 12) -> list[str]:
    if not isinstance(values, list):
        return []
    out = []
    for v in values:
        t = _text(v, 40).lower()
        if t and t not in out:
            out.append(t)
    return out[:n]


# Words that give a language away. A listing board may be in any language -- the French bioinformatics
# society's is -- but what reaches people here is in English, so anything else is left on its own site.
_ENGLISH = {"the", "and", "for", "with", "from", "this", "that", "will", "your", "you", "are", "our", "has",
            "in", "of", "at", "on", "to", "an", "by", "is", "we", "as", "it", "or", "be", "its",
            "have", "who", "what", "about", "within", "under", "into", "position", "research", "researcher",
            "fellowship", "grant", "funding", "university", "institute", "school", "department", "deadline",
            "applications", "apply", "candidate", "candidates", "postdoc", "postdoctoral", "student",
            "phd", "scientist", "engineer", "conference", "workshop", "meeting", "closing", "date", "years"}
_OTHER = {  # French, German, Spanish, Italian, Portuguese, Dutch -- the function words, which are everywhere
    "de", "en", "au", "le", "la", "les", "des", "du", "une", "pour", "dans", "avec", "sur", "aux", "par",
    "chez", "sont", "ses", "ont", "dont", "sein", "recrute",
    "nous", "vous", "leur", "cette", "poste", "stage", "emploi", "offre", "candidature", "laboratoire",
    "und", "für", "mit", "der", "die", "das", "den", "dem", "ein", "eine", "einen", "bei", "nicht", "sind",
    "para", "con", "los", "las", "del", "por", "una", "como", "sobre", "investigación", "plaza",
    "della", "delle", "degli", "nel", "sono", "questo", "ricerca", "borsa",
    "para", "pelo", "pela", "dos", "das", "não", "sao",
    "van", "het", "een", "voor", "met", "zijn"}


def english_enough(*parts: Any) -> bool:
    """True if this reads as English. Used on every listing, whatever route it came in by.

    It counts function words rather than guessing from accents: a London post at the Université de Paris is
    still English, while a French listing is full of "de", "pour", "la". When nothing marks either language
    (a short title like "Explainable AI for Protein Folding"), it is taken as English rather than dropped."""
    import re as _re
    words = _re.findall(r"[a-zà-öø-ÿ']+", " ".join(str(p or "") for p in parts).lower())
    if not words:
        return False
    english = sum(1 for w in words if w in _ENGLISH)
    other = sum(1 for w in words if w in _OTHER)
    return english >= other


# The languages a listing can also be read in. Each entry is (its own name, right-to-left), and the name
# is written into the lists beside every translation -- so a language added later arrives with the lists
# themselves, within hours, rather than waiting for everyone to install a new myGeeKy.
LANGUAGES = {"ar": ("العربية", True), "fr": ("Français", False), "de": ("Deutsch", False),
             "es": ("Español", False), "zh": ("中文", False)}
_CODE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")
_SAID = {"title": 140, "summary": 400, "who": 160, "amount": 60, "student": 160}


def clean_translations(raw: Any) -> dict[str, dict[str, Any]]:
    """The same listing in other languages: {code: {"name", "rtl", "title", "summary", ...}}.

    A translation is only ever a reading aid: nothing here can drop a listing, and one that arrives without
    a title is simply left out. Each entry carries its own language name and its own direction, so a code
    myGeeKy has never heard of still shows up with the right name on the button."""
    out: dict[str, dict[str, Any]] = {}
    for code, val in list(raw.items())[:20] if isinstance(raw, dict) else []:
        code = str(code).strip().lower()
        if not _CODE.match(code) or not isinstance(val, dict):
            continue
        known = LANGUAGES.get(code)
        name = _text(val.get("name"), 30) or (known[0] if known else "")
        said = {f: _text(val.get(f), n) for f, n in _SAID.items()}
        if not name or not said["title"]:
            continue
        out[code] = {"name": name, "rtl": bool(val.get("rtl", known[1] if known else False)),
                     **{f: v for f, v in said.items() if v}}
    return out


def languages_of(item: dict[str, Any]) -> list[str]:
    """The codes a listing is translated into, the known ones first, in the order people are offered them."""
    known = list(LANGUAGES)
    tr = item.get("translations") or {}
    return sorted(tr, key=lambda c: (known.index(c) if c in known else len(known), c))


# Where a listing is, in a form something can filter on. The place DeepSeek reads off a page is written
# the way people write it -- "Lyon, France", "Cambridge, UK", "Doha, Qatar" -- so the country is the last
# part of it that is actually a country. A place that names only a city, or says "remote", has no country,
# and that is the right answer rather than a guess.
_COUNTRY_ALIAS = {
    "uk": "United Kingdom", "u.k.": "United Kingdom", "england": "United Kingdom",
    "scotland": "United Kingdom", "wales": "United Kingdom", "britain": "United Kingdom",
    "great britain": "United Kingdom", "northern ireland": "United Kingdom",
    "usa": "United States", "u.s.a.": "United States", "us": "United States", "u.s.": "United States",
    "america": "United States", "united states of america": "United States",
    "uae": "United Arab Emirates", "ksa": "Saudi Arabia", "korea": "South Korea",
    "republic of korea": "South Korea", "czechia": "Czech Republic", "holland": "Netherlands",
    "the netherlands": "Netherlands", "deutschland": "Germany", "espana": "Spain", "turkey": "Türkiye",
    "turkiye": "Türkiye", "swiss": "Switzerland", "russia": "Russian Federation", "ivory coast": "Côte d'Ivoire",
}
COUNTRIES = (
    "Algeria", "Argentina", "Australia", "Austria", "Bahrain", "Bangladesh", "Belgium", "Brazil", "Bulgaria",
    "Canada", "Chile", "China", "Colombia", "Croatia", "Cyprus", "Czech Republic", "Côte d'Ivoire",
    "Denmark", "Egypt", "Estonia", "Ethiopia", "Finland", "France", "Germany", "Ghana", "Greece", "Hong Kong",
    "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Japan",
    "Jordan", "Kenya", "Kuwait", "Latvia", "Lebanon", "Libya", "Lithuania", "Luxembourg", "Malaysia",
    "Mexico", "Morocco", "Netherlands", "New Zealand", "Nigeria", "Norway", "Oman", "Pakistan", "Palestine",
    "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russian Federation", "Rwanda",
    "Saudi Arabia", "Senegal", "Serbia", "Singapore", "Slovakia", "Slovenia", "South Africa", "South Korea",
    "Spain", "Sudan", "Sweden", "Switzerland", "Syria", "Taiwan", "Tanzania", "Thailand", "Tunisia",
    "Türkiye", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay",
    "Uzbekistan", "Vietnam", "Yemen", "Zambia", "Zimbabwe",
)
_BY_NAME = {c.lower(): c for c in COUNTRIES}
_NOWHERE = {"remote", "online", "anywhere", "worldwide", "virtual", "hybrid", "europe", "eu", "global"}
# Boards write the country as a two-letter code in brackets -- "Dortmund, Nordrhein-Westfalen (DE)" --
# and American ones leave it off entirely, naming only the state. Both are common enough to be worth
# reading rather than losing.
_CODES = {"de": "Germany", "us": "United States", "gb": "United Kingdom", "uk": "United Kingdom",
          "fr": "France", "nl": "Netherlands", "ch": "Switzerland", "se": "Sweden", "no": "Norway",
          "dk": "Denmark", "fi": "Finland", "at": "Austria", "be": "Belgium", "es": "Spain", "it": "Italy",
          "pt": "Portugal", "ie": "Ireland", "pl": "Poland", "cz": "Czech Republic", "cn": "China",
          "jp": "Japan", "kr": "South Korea", "sg": "Singapore", "au": "Australia", "nz": "New Zealand",
          "ca": "Canada", "il": "Israel", "ae": "United Arab Emirates", "sa": "Saudi Arabia",
          "qa": "Qatar", "eg": "Egypt", "za": "South Africa", "in": "India", "br": "Brazil", "tr": "Türkiye"}
_US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee",
    "texas", "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming",
}
_TAIL_CODE = re.compile(r"\(([A-Za-z]{2})\)\s*$")


def country_of(place: Any) -> str:
    """The country a place names, or '' when it names none.

    Read from the end, because that is where people put the country: "Lyon, France" and
    "Cambridge, Cambridgeshire, UK" both give the right answer, and "Lyon" alone gives nothing rather
    than inventing a country called Lyon."""
    text = _text(place, 120)
    if not text or text.lower().strip() in _NOWHERE:
        return ""
    tail = _TAIL_CODE.search(text)          # "... (DE)" -- the country, written as a code
    if tail and tail.group(1).lower() in _CODES:
        return _CODES[tail.group(1).lower()]
    for part in reversed([p.strip(" .") for p in _TAIL_CODE.sub("", text).split(",")]):
        low = part.lower()
        if low in _BY_NAME:
            return _BY_NAME[low]
        if low in _COUNTRY_ALIAS:
            return _COUNTRY_ALIAS[low]
        if low in _US_STATES:               # an American board naming only the state
            return "United States"
    return ""


def countries_in(items: list[dict[str, Any]]) -> list[str]:
    """Every country these listings are actually in, in order, for a filter to offer.

    Built from the listings themselves, so the filter can never offer a country with nothing behind it."""
    return sorted({it.get("country", "") for it in items if it.get("country")})


def clean_item(kind: str, raw: Any) -> dict[str, Any] | None:
    """One checked item, or None if it isn't usable."""
    if not isinstance(raw, dict) or not _ID.match(str(raw.get("id", ""))):
        return None
    item = {"id": raw["id"], "title": _text(raw.get("title"), 140), "url": _https(raw.get("url")),
            "keywords": _words(raw.get("keywords")), "summary": _text(raw.get("summary"), 400)}
    # a listing from a board in another language is translated, and says so, with its own title kept
    original, language = _text(raw.get("original_title"), 140), _text(raw.get("language"), 30)
    if original and language:
        item["original_title"], item["language"] = original, language
    if not item["title"] or not item["url"]:
        return None
    if kind in DATED and not english_enough(item["title"], item["summary"]):
        return None           # the boards may be in any language; what people are shown is English
    if kind in DATED:
        said = clean_translations(raw.get("translations"))
        if said:
            item["translations"] = said
    if kind in DATED:
        item["deadline"] = _day(raw.get("deadline"))
        if not item["deadline"]:
            return None           # a dated list without a date would never leave
    if kind == "jobs":
        t = str(raw.get("type", "job")).lower()
        item.update(org=_text(raw.get("org"), 100), place=_text(raw.get("place"), 80),
                    type=t if t in JOB_TYPES else "job", remote=bool(raw.get("remote")),
                    country=country_of(raw.get("place")))
    elif kind == "funding":
        item.update(org=_text(raw.get("org"), 100), who=_text(raw.get("who"), 160), amount=_text(raw.get("amount"), 60))
    elif kind == "conferences":
        item.update(place=_text(raw.get("place"), 80), starts=_day(raw.get("starts")), ends=_day(raw.get("ends")),
                    student=_text(raw.get("student"), 160), country=country_of(raw.get("place")))
    elif kind == "resources":
        t = str(raw.get("type", "website")).lower()
        level = str(raw.get("level", "")).lower()
        item.update(type=t if t in RESOURCE_TYPES else "website", skills=_words(raw.get("skills")),
                    level=level if level in LEVELS else "", free=raw.get("free", True) is not False)
    return item


def clean(data: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"version": _text((data or {}).get("version") if isinstance(data, dict) else "", 40)}
    for kind in LISTS:
        raw = data.get(kind) if isinstance(data, dict) else None
        seen: set[str] = set()
        items = []
        for r in (raw if isinstance(raw, list) else [])[:500]:
            it = clean_item(kind, r)
            if it and it["id"] not in seen:
                seen.add(it["id"])
                items.append(it)
        out[kind] = items
    from .highlight_shape import clean_all as clean_highlights   # the maker's stories (highlight_shape.py)
    out["highlights"] = clean_highlights(data.get("highlights") if isinstance(data, dict) else None)
    from .seasons import clean as clean_seasons   # scholarships that come back every year (seasons.py)
    out["seasons"] = clean_seasons(data.get("seasons") if isinstance(data, dict) else None)
    from .protocols import clean_protocol     # reviewed protocols: a skill as ordered stages (protocols.py)
    seen = set()
    out["protocols"] = []
    for r in ((data.get("protocols") if isinstance(data, dict) else None) or [])[:200]:
        p = clean_protocol(r, reviewed=True) if isinstance(data.get("protocols"), list) else None
        if p and p["id"] not in seen:
            seen.add(p["id"])
            out["protocols"].append(p)
    return out


def load(force: bool = False) -> dict[str, Any]:
    """The newest lists we have: the ones shipped with myGeeKy, or newer ones fetched since."""
    global _loaded
    if _loaded is not None and not force:
        return _loaded
    candidates = []
    for fetched, path in ((False, BUNDLED), (True, CURATED_FILE)):
        data = read_json(path, None)
        if isinstance(data, dict):
            candidates.append((clean(data.get("lists") if fetched else data), fetched))
    # the newest version wins; on a tie the fetched copy (the maker may have edited without a new version)
    _loaded = max(candidates, key=lambda c: (c[0].get("version", ""), c[1]))[0] if candidates else clean({})
    return _loaded


def refresh_if_due(force: bool = False, now: datetime | None = None, timeout: float = 20.0) -> bool:
    """Fetch the maker's newest lists, at most every CHECK_EVERY_HOURS. True if they changed."""
    global _loaded
    now = now or datetime.now(timezone.utc)
    cached = read_json(CURATED_FILE, {}) or {}
    if not force:
        try:
            checked = datetime.fromisoformat(cached.get("checked_at", ""))
            if (now - checked).total_seconds() < CHECK_EVERY_HOURS * 3600:
                return False
        except (TypeError, ValueError):
            pass
    r = requests.get(REMOTE_URL, timeout=timeout, headers={"User-Agent": "mygeeky"})
    if getattr(r, "status_code", 200) == 404:   # nothing published yet: the lists shipped with myGeeKy are all there is
        ensure_dirs()
        write_json(CURATED_FILE, {**(cached if isinstance(cached, dict) else {}),
                                  "checked_at": now.isoformat(timespec="seconds")})
        return False
    r.raise_for_status()
    if len(r.content) > 2_000_000:
        raise ValueError("the curated lists are unexpectedly large")
    lists = clean(r.json())
    changed = lists != clean(cached.get("lists")) if isinstance(cached, dict) else True
    ensure_dirs()
    write_json(CURATED_FILE, {"checked_at": now.isoformat(timespec="seconds"), "lists": lists})
    _loaded = None
    return changed


# --------------------------------------------------------------------------- matching, on your computer
def days_left(item: dict[str, Any], today: date | None = None) -> int | None:
    if not item.get("deadline"):
        return None
    return (date.fromisoformat(item["deadline"]) - (today or date.today())).days


def live(items: Iterable[dict[str, Any]], today: date | None = None) -> list[dict[str, Any]]:
    """Only what's still open: the deadline day itself still counts."""
    out = []
    for it in items:
        left = days_left(it, today)
        if left is None or left >= 0:
            out.append(it)
    return out


def _text_of(item: dict[str, Any]) -> str:
    return " ; ".join([item.get("title", ""), item.get("summary", ""), item.get("org", ""),
                       " ".join(item.get("keywords", [])), " ".join(item.get("skills", []))])


def ranked(cfg: MyGeekyConfig, kind: str, weights: dict[str, float] | None = None,
           lean: dict[str, float] | None = None, today: date | None = None,
           data: dict[str, Any] | None = None, extra_terms: dict[str, float] | None = None) -> dict[str, Any]:
    """{"items": [...best first], "hidden": n}. Each item gains `score`, `match` (why it
    fits you), `days_left` and `vote`. Items you gave 👎 are hidden (counted in `hidden`)."""
    from . import interests
    data = data or load()
    w = dict(weights if weights is not None else interests.profile_terms(cfg))
    for t, v in (extra_terms or {}).items():
        w[t] = max(w.get(t, 0.0), v)
    lean_w = lean if lean is not None else taste.weights([VOTE_KIND[kind]])
    votes = taste.load()
    items, hidden = [], 0
    for it in live(data.get(kind, []), today):
        v = int(votes.get(taste.key_of(VOTE_KIND[kind], it["id"]), {}).get("vote", 0))
        if v < 0:
            hidden += 1
            continue
        fit, why = interests.match(_text_of(it), w)
        tilt = taste.lean(_text_of(it), it.get("keywords", []) + it.get("skills", []), lean_w)
        score = 0.15 + 0.6 * fit + 0.35 * tilt + (0.3 if v > 0 else 0.0)
        items.append({**it, "score": round(score, 4), "match": why, "days_left": days_left(it, today), "vote": v})
    items.sort(key=lambda x: (x["score"], -(x["days_left"] if x["days_left"] is not None else 9999)), reverse=True)
    return {"items": items, "hidden": hidden}


def for_skill(skill: str, aliases: Iterable[str] = (), data: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Learning resources that teach this skill (its own tag first, then a mention)."""
    names = {skill.lower(), *(a.lower() for a in aliases)}
    tagged, mentioned = [], []
    for r in (data or load()).get("resources", []):
        if names & set(r.get("skills", [])):
            tagged.append(r)
        elif any(re.search(r"(?<![a-z0-9])" + re.escape(n) + r"(?![a-z0-9])", _text_of(r).lower()) for n in names):
            mentioned.append(r)
    return tagged + mentioned


# --------------------------------------------------------------------------- telling the maker
def report_links(kind: str, item: dict[str, Any], reason: str = "") -> dict[str, str]:
    """Two ways to report a listing that looks fake: a prefilled GitHub issue (submitted
    by you, with your own account) or an email to support (for people without GitHub)."""
    from . import ideas
    what = {"jobs": "job", "funding": "funding call", "conferences": "conference", "resources": "resource"}[kind]
    title = f"Looks fake: {item.get('title', '')}"[:110]
    body = (f"This {what} on myGeeKy looks fake or is no longer real.\n\n"
            f"- id: `{item.get('id', '')}`\n- link: {item.get('url', '')}\n\n"
            f"Why I think so: {reason or ''}\n")
    issue = ideas.issue_url("report", title, body, include_version=False)
    mail = (f"mailto:{REPORT_EMAIL}?subject={quote(title)}&body={quote(body)}")
    return {"issue": issue, "email": mail}


# --------------------------------------------------------------------------- the maker's side
def prune(data: dict[str, Any], today: date | None = None) -> tuple[dict[str, Any], int]:
    """The file without anything past its deadline (raw items kept as written)."""
    today = today or date.today()
    out, removed = dict(data), 0
    for kind in DATED:
        keep = []
        for raw in data.get(kind) or []:
            d = _day(raw.get("deadline")) if isinstance(raw, dict) else ""
            if d and date.fromisoformat(d) < today:
                removed += 1
                continue
            keep.append(raw)
        out[kind] = keep
    return out, removed


def problems(data: Any) -> list[str]:
    """What's wrong with a hand-edited file, in plain words (empty: all good)."""
    if not isinstance(data, dict):
        return ["The file must hold one JSON object."]
    out = []
    for kind in LISTS:
        ids: set[str] = set()
        for i, raw in enumerate(data.get(kind) or []):
            label = f"{kind}[{i}]"
            if not isinstance(raw, dict):
                out.append(f"{label} is not an object")
                continue
            label = f"{kind} '{raw.get('id', '?')}'"
            if not _ID.match(str(raw.get("id", ""))):
                out.append(f"{label}: id must be 3-80 lowercase letters, digits or dashes")
            elif raw["id"] in ids:
                out.append(f"{label}: the same id appears twice")
            ids.add(str(raw.get("id")))
            if not _text(raw.get("title"), 140):
                out.append(f"{label}: no title")
            if not _https(raw.get("url")):
                out.append(f"{label}: the url must start with https://")
            if kind in DATED and not _day(raw.get("deadline")):
                out.append(f"{label}: deadline must be a date like 2026-12-31")
    from .highlight_shape import problems as highlight_problems
    out += highlight_problems(data.get("highlights"))
    from .protocols import clean_protocol, clean_stage, clean_item as clean_link
    ids = set()
    for i, raw in enumerate(data.get("protocols") or []):
        label = f"protocols '{raw.get('id', i) if isinstance(raw, dict) else i}'"
        p = clean_protocol(raw, reviewed=True)
        if not p:
            out.append(f"{label}: needs a skill, a title and at least one stage with a title")
            continue
        if not _ID.match(str(raw.get("id", ""))):
            out.append(f"{label}: id must be 3-80 lowercase letters, digits or dashes")
        elif p["id"] in ids:
            out.append(f"{label}: the same id appears twice")
        ids.add(p["id"])
        for j, s in enumerate(raw.get("stages") or []):
            if not clean_stage(s, j):
                out.append(f"{label}: stage {j + 1} has no title")
                continue
            for it in s.get("items") or []:
                if not clean_link(it):
                    out.append(f"{label}, stage '{s.get('title')}': every link needs a title and an https:// url")
            for q in s.get("quiz") or []:
                opts = q.get("options") if isinstance(q, dict) else None
                if not (isinstance(q, dict) and isinstance(opts, list) and isinstance(q.get("answer"), int)
                        and 0 <= q["answer"] < len(opts)):
                    out.append(f"{label}, stage '{s.get('title')}': a quiz question needs options and the answer's "
                               "position (0 = the first option)")
    return out


def tidy_file(path: Path, today: date | None = None) -> tuple[int, list[str]]:
    """Prune past deadlines and stamp a new version if anything changed. (removed, problems)"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    errs = problems(raw)
    pruned, removed = prune(raw, today)
    if removed:
        pruned["version"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        Path(path).write_text(json.dumps(pruned, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return removed, errs


def main(argv: list[str] | None = None) -> int:
    """python -m mygeeky.curated [check|prune|stamp] [path]"""
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "check"
    path = Path(args[1]) if len(args) > 1 else BUNDLED
    if cmd == "prune":
        removed, errs = tidy_file(path)
        print(f"removed {removed} past their deadline")
    elif cmd == "stamp":           # after adding items by hand: a new version, so every app takes it
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["version"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        path.write_text(json.dumps(raw, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        errs = problems(raw)
        print(f"version {raw['version']}")
    else:
        errs = problems(json.loads(path.read_text(encoding="utf-8")))
    for e in errs:
        print("problem:", e)
    if not errs:
        print("ok")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
