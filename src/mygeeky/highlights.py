"""The maker's Highlights: research articles told as short stories in plain words, in every language
myGeeKy offers, for Grow -> Highlights (highlight_shape.py says what one is).

Maker side only (the admin tab). It never publishes anything by itself:

  1. **Find** -- the maker pastes DOIs or links; "Open the articles" opens each one's page in the browser.
  2. **Facts** -- what can be looked up is looked up, on OpenAlex by DOI: the title, journal, date, authors,
     the team leader (the last author) and the corresponding author, institutions, countries, open access and
     the abstract. DeepSeek is never asked for a fact it could get wrong.
  3. **Text** -- the maker pastes the articles' text (all of them in one box: it is split at each
     article's title) or drops a PDF, or ticks "abstract only" when short of time.
  4. **Write** -- DeepSeek retells each article as a short news article (a headline, a standfirst and a few
     paragraphs, one idea each) with the article skill (data/article_skill.md),
     then says it again in each language, one language per call.
  5. **Check** -- myGeeKy checks the story itself: every number in the article and every tool name must be
     in the text it was given (or in the looked-up facts), and the team leader must be named. What fails is listed beside the draft for the maker to look at.
  6. **Review and publish** -- the maker reads, edits, accepts or rejects; accepted ones go out with the
     curated lists when the maker presses Publish (scout.publish), like accepted jobs and funding.

The DeepSeek key is scout's (the system's credential store). Drafts are kept in highlights.json, on this
computer only.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

from . import highlight_shape as shape
from .config import DATA_DIR, ensure_dirs
from .files import read_json, write_json

STATE_FILE = DATA_DIR / "highlights.json"
SKILL_FILE = Path(__file__).resolve().parent / "data" / "article_skill.md"
OPENALEX = "https://api.openalex.org"
UA = {"User-Agent": "mygeeky (https://github.com/mygeeky/myGeeKy)"}
from .scout import SAY_LANGUAGES as LANGUAGES     # the same languages as Chances (tests/test_highlights.py)
TEXT_CHARS = 60_000             # of an article's text sent to DeepSeek
MIN_TEXT = 1500                 # less pasted text than this for an article: its abstract is used instead
_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?:\s?%)?")
COUNTRIES = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany", "FR": "France", "CN": "China", "JP": "Japan",
    "CA": "Canada", "AU": "Australia", "IT": "Italy", "ES": "Spain", "NL": "Netherlands", "CH": "Switzerland",
    "SE": "Sweden", "DK": "Denmark", "NO": "Norway", "FI": "Finland", "BE": "Belgium", "AT": "Austria",
    "IE": "Ireland", "PT": "Portugal", "PL": "Poland", "CZ": "Czechia", "GR": "Greece", "IL": "Israel",
    "TR": "Turkey", "IN": "India", "KR": "South Korea", "SG": "Singapore", "TW": "Taiwan", "HK": "Hong Kong",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CL": "Chile", "CO": "Colombia", "ZA": "South Africa",
    "EG": "Egypt", "NG": "Nigeria", "KE": "Kenya", "ET": "Ethiopia", "MA": "Morocco", "TN": "Tunisia",
    "SA": "Saudi Arabia", "AE": "United Arab Emirates", "QA": "Qatar", "JO": "Jordan", "LB": "Lebanon",
    "SY": "Syria", "IQ": "Iraq", "IR": "Iran", "PK": "Pakistan", "BD": "Bangladesh", "TH": "Thailand",
    "VN": "Vietnam", "MY": "Malaysia", "ID": "Indonesia", "PH": "Philippines", "NZ": "New Zealand",
    "RU": "Russia", "UA": "Ukraine", "HU": "Hungary", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia",
    "HR": "Croatia", "RS": "Serbia", "BG": "Bulgaria", "EE": "Estonia", "LV": "Latvia", "LT": "Lithuania",
    "IS": "Iceland", "LU": "Luxembourg", "CY": "Cyprus", "GH": "Ghana", "UG": "Uganda", "TZ": "Tanzania",
}


# --------------------------------------------------------------------------- the skill
def skill() -> tuple[str, str]:
    """The article skill: (how to write the story, how to translate it), from data/article_skill.md."""
    text = SKILL_FILE.read_text(encoding="utf-8")
    write, _, translate = text.partition("## Translating (the second step)")
    head = write.split("## What you write")[0]
    return write.strip(), (head + "## Translating\n" + translate).strip()


# --------------------------------------------------------------------------- finding the articles
def find_dois(text: str) -> list[str]:
    """Every DOI in what the maker pasted (bare, or inside a doi.org or publisher link), once each."""
    out: list[str] = []
    for m in _DOI.finditer(text or ""):
        doi = m.group(0).rstrip(".,;:)]}>'\"").lower()
        for tail in ("/full", "/abstract", "/pdf", "/epdf"):         # publisher pages add these to the DOI
            if doi.endswith(tail):
                doi = doi[: -len(tail)]
        if doi not in out:
            out.append(doi)
    return out


def links(text: str) -> list[str]:
    """The pages to open in the browser: each DOI's doi.org page, and any other link as pasted."""
    out = [f"https://doi.org/{d}" for d in find_dois(text)]
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("https://") and not _DOI.search(line) and line not in out:
            out.append(line)
    return out


def _abstract(inverted: Any) -> str:
    if not isinstance(inverted, dict):
        return ""
    at: dict[int, str] = {}
    for word, places in inverted.items():
        for p in places if isinstance(places, list) else []:
            if isinstance(p, int):
                at[p] = word
    return " ".join(at[i] for i in sorted(at))


def facts(work: dict[str, Any], doi: str) -> dict[str, Any]:
    """What an OpenAlex work says about an article, in the shape a Highlight's meta takes."""
    ships = [a for a in work.get("authorships") or [] if isinstance(a, dict)]
    name = lambda a: str((a.get("author") or {}).get("display_name") or "")       # noqa: E731
    lead = name(ships[-1]) if ships else ""                       # in most fields the last author leads the lab
    corresponding = next((name(a) for a in ships if a.get("is_corresponding")), "")
    institutions: list[str] = []
    countries: list[str] = []
    for a in ships:
        for inst in a.get("institutions") or []:
            n = str((inst or {}).get("display_name") or "")
            if n and n not in institutions:
                institutions.append(n)
            code = str((inst or {}).get("country_code") or "").upper()
            c = COUNTRIES.get(code, code)
            if c and c not in countries:
                countries.append(c)
    loc = work.get("primary_location") or {}
    return {
        "doi": doi, "title": str(work.get("title") or work.get("display_name") or ""),
        "journal": str((loc.get("source") or {}).get("display_name") or ""),
        "published": str(work.get("publication_date") or "")[:10],
        "url": f"https://doi.org/{doi}",
        "open_access": bool((work.get("open_access") or {}).get("is_oa")),
        "authors": [name(a) for a in ships if name(a)][:8], "author_count": len(ships), "lead": lead,
        "corresponding": corresponding, "institutions": institutions[:8], "institution_count": len(institutions),
        "countries": countries[:12], "country_count": len(countries),
        "abstract": _abstract(work.get("abstract_inverted_index")),
    }


def look_up(doi: str, session: requests.Session | None = None) -> dict[str, Any]:
    """The facts about one article, from OpenAlex (no key needed). Raises when OpenAlex doesn't know it."""
    from . import wisep
    get = (session or wisep.session("you:admin")).get                     # OpenAlex through WISEP
    r = get(f"{OPENALEX}/works/https://doi.org/{doi}", headers=UA, timeout=25)
    if r.status_code == 404:
        raise LookupError(f"OpenAlex doesn't know {doi} (yet). Check the DOI.")
    r.raise_for_status()
    return facts(r.json(), doi)


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", s.lower()).split())


def split_text(text: str, found: list[dict[str, Any]]) -> dict[str, str]:
    """Pasted text for several articles, cut into each one's part: each starts where its title first appears.
    With one article it is all its own; an article whose title can't be found gets nothing (its abstract
    is used instead)."""
    if not text.strip() or not found:
        return {}
    if len(found) == 1:
        return {found[0]["doi"]: text}
    starts = []
    for f in found:
        words = re.findall(r"\w+", f["title"])[:8]           # the title's first words, whatever is between them
        m = re.search(r"\W+".join(map(re.escape, words)), text, re.I) if words else None
        if m:
            starts.append((m.start(), f["doi"]))
    starts.sort()
    out = {}
    for i, (at, doi) in enumerate(starts):
        out[doi] = text[at: starts[i + 1][0] if i + 1 < len(starts) else len(text)]
    return out


# --------------------------------------------------------------------------- writing and checking
def write(key: str, fact: dict[str, Any], text: str, coverage: str, post=None) -> dict[str, Any]:
    """The story in English, by DeepSeek with the article skill."""
    from .scout import ask
    system, _ = skill()
    given = {k: v for k, v in fact.items() if k != "abstract"}
    user = json.dumps({"FACTS": given, "TEXT_IS": "the full article" if coverage == "full" else "the abstract only",
                       "TEXT": text[:TEXT_CHARS]}, ensure_ascii=False)
    return ask(key, system, user, post, timeout=240, max_tokens=3000)


def translate(key: str, story: dict[str, Any], code: str, post=None) -> dict[str, Any]:
    """The story said again in one language: title, standfirst and the same paragraphs, in order."""
    from .scout import ask
    _, system = skill()
    english = {"title": story.get("title", ""), "hook": story.get("hook", ""), "body": list(story.get("body") or [])}
    ans = ask(key, f"{system}\n\nThe language: {LANGUAGES.get(code, code)}.", json.dumps(english, ensure_ascii=False),
              post, timeout=240, max_tokens=4000)
    return {"title": ans.get("title", ""), "hook": ans.get("hook", ""),
            "body": ans.get("body") if isinstance(ans.get("body"), list) else []}


def checks(story: dict[str, Any], text: str, fact: dict[str, Any]) -> list[str]:
    """What in the story the text doesn't back up, in plain words (empty: nothing found)."""
    looked_up = " ".join(str(fact.get(k, "")) for k in ("published", "author_count", "institution_count", "country_count"))
    source = " ".join(f"{text} {fact.get('abstract', '')} {looked_up}".split()).lower()
    body = " ".join(str(p) for p in story.get("body") or [])
    out = []
    for n in dict.fromkeys(_NUMBER.findall(body)):
        if n.replace(" ", "").lower() not in source.replace(" ", ""):
            out.append(f"the number {n} isn't in the text")
    for tool in story.get("tool_names") or []:
        if isinstance(tool, str) and tool.strip() and tool.lower() not in source:
            out.append(f"the tool '{tool}' isn't in the text")
    if fact.get("lead") and fact["lead"].split()[-1].lower() not in body.lower():
        out.append(f"the article doesn't name the team leader ({fact['lead']})")
    if len(story.get("body") or []) < 4:
        out.append(f"only {len(story.get('body') or [])} paragraphs: the text may be too short")
    return out


MIN_PARAGRAPH_WORDS = 35        # shorter than this is a line, not a paragraph: it joins the next one


def paragraphs(body: list[Any]) -> list[str]:
    """Whole paragraphs: one that is only a line or two is joined to the next (the last to the one before), so
    a story always reads as an article, never as a list of lines -- whatever came back from DeepSeek."""
    out: list[str] = []
    carry = ""
    for p in (" ".join(str(x).split()) for x in body if str(x).strip()):
        p = f"{carry} {p}".strip()
        if len(p.split()) < MIN_PARAGRAPH_WORDS:
            carry = p
            continue
        out.append(p)
        carry = ""
    if carry:
        if out:
            out[-1] = f"{out[-1]} {carry}"
        else:
            out.append(carry)
    return out


def _slug(text: str) -> str:
    return "-".join(_norm(text).split()[:6])[:48].strip("-") or "article"


def item(fact: dict[str, Any], story: dict[str, Any], said: dict[str, dict[str, Any]], coverage: str,
         today: date | None = None) -> dict[str, Any] | None:
    """The Highlight as it goes into the curated lists (checked by highlight_shape.clean)."""
    hid = f"hl-{_slug(story.get('title') or fact['title'])}-{hashlib.sha1(fact['doi'].encode()).hexdigest()[:6]}"
    raw = {
        "id": hid, "kind": "article", "title": story.get("title", ""), "hook": story.get("hook", ""),
        "url": fact["url"], "doi": fact["doi"], "added": (today or date.today()).isoformat(), "coverage": coverage,
        "meta": {k: fact.get(k) for k in ("journal", "published", "lead", "authors", "institutions", "countries",
                                          "open_access")},
        "body": paragraphs(list(story.get("body") or [])),
        "tools": story.get("tool_names") or [], "skills": story.get("skills") or [],
        "keywords": story.get("keywords") or [],
        "translations": {c: {"name": shape.NAMES[c][0], "rtl": shape.NAMES[c][1], **v} for c, v in said.items()
                         if c in shape.NAMES},
    }
    return shape.clean(raw)


# --------------------------------------------------------------------------- drafts (this computer only)
def load() -> dict[str, Any]:
    data = read_json(STATE_FILE, {})
    data = data if isinstance(data, dict) else {}
    data.setdefault("drafts", {})
    return data


def save(state: dict[str, Any]) -> None:
    ensure_dirs()
    write_json(STATE_FILE, state, indent=1, ensure_ascii=False)


def draft(pasted_links: str, text: str = "", abstract_only: bool = False, key: str | None = None,
          progress: Callable[[str], None] | None = None, post=None, session: requests.Session | None = None,
          languages: tuple[str, ...] = tuple(LANGUAGES)) -> dict[str, Any]:
    """Write a draft Highlight for every DOI in `pasted_links`. {"drafts": [ids], "errors": [lines]}."""
    from .scout import get_key
    key = key or get_key()
    if not key:
        raise PermissionError("Add your DeepSeek key in Admin → ⚙ Settings first (the same one the scout uses), or paste an answer written elsewhere in ✍ Write.")
    say = progress or (lambda _m: None)
    dois = find_dois(pasted_links)
    if not dois:
        raise ValueError("Paste at least one DOI or a link that holds one (doi.org, a journal's page...).")
    found, errors = [], []
    for doi in dois:
        say(f"Looking up {doi} on OpenAlex…")
        try:
            found.append(look_up(doi, session))
        except Exception as exc:                  # one unknown DOI doesn't stop the others
            errors.append(f"{doi}: {exc}")
    parts = {} if abstract_only else split_text(text, found)
    state, made = load(), []
    for f in found:
        own = parts.get(f["doi"], "")
        coverage, body = ("full", own) if len(own) >= MIN_TEXT else ("abstract", f["abstract"])
        if not body.strip():
            errors.append(f"{f['doi']}: no text pasted for it, and OpenAlex has no abstract")
            continue
        say(f"Writing “{f['title'][:60]}”…")
        try:
            story = write(key, f, body, coverage, post)
            story["body"] = paragraphs(list(story.get("body") or []))    # whole paragraphs before translating,
                                                                          # so each language lines up with them
            said = {}
            for code in languages:
                say(f"…in {LANGUAGES.get(code, code)}")
                try:
                    said[code] = translate(key, story, code, post)
                except Exception as exc:          # a missing translation costs the story nothing
                    errors.append(f"{f['doi']}: no {LANGUAGES.get(code, code)} ({exc})")
        except Exception as exc:
            errors.append(f"{f['doi']}: {exc}")
            continue
        it = item(f, story, said, coverage)
        if not it:
            errors.append(f"{f['doi']}: DeepSeek's answer was too short to make a story from")
            continue
        state["drafts"][it["id"]] = {"id": it["id"], "status": "new", "item": it, "warnings": checks(story, body, f),
                                     "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        made.append(it["id"])
    save(state)
    return {"drafts": made, "errors": errors}


def drafts(status: str = "new") -> list[dict[str, Any]]:
    """Drafts in one state (new, accepted, rejected, published), newest first."""
    out = [d for d in load()["drafts"].values() if isinstance(d, dict) and d.get("status") == status]
    return sorted(out, key=lambda d: d.get("made_at", ""), reverse=True)


def set_status(hid: str, status: str, edited: dict[str, Any] | None = None) -> bool:
    """Accept, reject or reset a draft; `edited` replaces its story (checked again)."""
    state = load()
    d = state["drafts"].get(hid)
    if not d:
        return False
    if edited is not None:
        it = shape.clean(edited)
        if not it:
            return False
        d["item"] = it
    d["status"] = status
    save(state)
    return True


def accepted() -> list[dict[str, Any]]:
    return [d["item"] for d in drafts("accepted")]


def merge(data: dict[str, Any], items: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
    """The curated file with these Highlights added (one per id; the newest shape.KEEP kept)."""
    out = json.loads(json.dumps(data))
    have = [h for h in out.get("highlights") or [] if isinstance(h, dict)]
    added = 0
    for it in items:
        it = shape.clean(it)                  # checked again before it goes to everyone
        if not it:
            continue
        if any(h.get("id") == it["id"] or (it.get("doi") and h.get("doi") == it["doi"]) for h in have):
            continue
        have.append(it)
        added += 1
    have.sort(key=lambda h: (str(h.get("added", "")), str(h.get("id", ""))), reverse=True)
    out["highlights"] = have[: shape.KEEP]
    return out, added


def mark_published(ids: list[str]) -> None:
    state = load()
    for hid in ids:
        if hid in state["drafts"]:
            state["drafts"][hid]["status"] = "published"
            state["drafts"][hid]["published_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save(state)
