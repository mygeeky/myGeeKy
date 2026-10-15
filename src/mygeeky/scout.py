"""The maker's listing scout: find jobs, funding and conferences on chosen sites, check them, and publish
the ones the maker accepts to the curated lists everyone gets (curated.py).

Maker side only (the admin tab). It never publishes anything by itself:

  1. **Fetch** each chosen site's listing page (SOURCES, editable in the admin tab).
  2. **Pick** -- DeepSeek reads the page's text and its numbered links, and answers with the *numbers* of
     the links that are single, relevant listings. It never writes a URL, so it can't invent one.
  3. **Read** -- each picked listing's own page is fetched, and DeepSeek extracts its fields (title,
     organisation, place, deadline, who can apply…) and must quote the sentence that gives the deadline.
     Facts not on the page stay empty; nothing is guessed.
  4. **Check** -- myGeeKy checks the answer itself: the page opened, the title is on it, the quote is on it
     and holds the deadline's date, the deadline is still ahead, and it fits the maker's field. A listing
     that fails a hard check is dropped; the rest are ranked by DeepSeek's confidence times the checks.
  5. **Review** -- the maker accepts (or edits, or rejects) each one in the admin tab.
  6. **Publish** -- only when the maker presses it: the accepted listings are added to
     src/mygeeky/data/curated.json on GitHub's main branch, from a fresh temporary copy of it, with the
     maker's own git login. Every myGeeKy then shows them within a few hours (curated.REMOTE_URL).

The DeepSeek key lives in the system's credential store (keyring), never in a file. Everything else
(candidates, what was rejected) is kept in scout.json, on this computer only.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit

import requests

from . import curated
from .config import DATA_DIR, MyGeekyConfig, ensure_dirs
from .files import read_json, write_json

SCOUT_FILE = DATA_DIR / "scout.json"
KEY_SERVICE = "mygeeky-deepseek"
KEY_USER = "maker"
API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
UA = {"User-Agent": "Mozilla/5.0 (compatible; myGeeKy listing scout; +https://mygeeky.org)"}
PAGE_CHARS = 14_000          # text of a page sent to DeepSeek
MAX_LINKS = 160              # numbered links of a listing page sent to DeepSeek
MAX_PICKS = 12               # listings read in full per site, per run
MIN_DAYS_LEFT = 3            # a deadline closer than this isn't worth publishing
KINDS = ("jobs", "funding", "conferences")
DEFAULT_FOCUS = ("genetics, genomics, bioinformatics, computational biology, statistical genetics, biostatistics, "
                 "data science and machine learning for the life sciences")
SOURCES = [
    {"kind": "jobs", "name": "jobs.ac.uk", "url": "https://www.jobs.ac.uk/search/?keywords=bioinformatics"},
    {"kind": "jobs", "name": "Nature Careers", "url": "https://www.nature.com/naturecareers/jobs/?keywords=bioinformatics"},
    {"kind": "jobs", "name": "EURAXESS (bioinformatics)", "url": "https://euraxess.ec.europa.eu/jobs/search?keywords=bioinformatics"},
    {"kind": "jobs", "name": "EURAXESS (genomics)", "url": "https://euraxess.ec.europa.eu/jobs/search?keywords=genomics"},
    # the French bioinformatics society's board: a few hundred posts, each with its own page and a stated
    # closing date. Many are in French, so a listing kept from here reaches people who read French.
    {"kind": "jobs", "name": "SFBI (France)", "url": "https://www.sfbi.fr/en/emplois/offres-en-cours"},
    # Tested before adding: these two answer a plain fetch with real HTML. The big aggregators
    # (Indeed, LinkedIn, Glassdoor, Monster, ZipRecruiter...) either refuse a robot outright or forbid one
    # in their terms, and university portals built on SuccessFactors answer with an empty shell. For all of
    # those there is "Paste a page" in the admin tab instead: a person opens it and copies the text.
    {"kind": "jobs", "name": "Science Careers", "url": "https://jobs.sciencecareers.org/jobs/bioinformatics/"},
    {"kind": "jobs", "name": "Bioinformatics.org", "url": "https://www.bioinformatics.org/jobs/"},
    {"kind": "funding", "name": "EURAXESS funding", "url": "https://euraxess.ec.europa.eu/funding/search"},
    {"kind": "funding", "name": "EMBO fellowships", "url": "https://www.embo.org/funding/fellowships-grants-and-career-support/"},
    {"kind": "funding", "name": "Marie Skłodowska-Curie calls", "url": "https://marie-sklodowska-curie-actions.ec.europa.eu/calls"},
    {"kind": "funding", "name": "Wellcome schemes", "url": "https://wellcome.org/research-funding/schemes"},
    {"kind": "funding", "name": "ERC", "url": "https://erc.europa.eu/apply-grant"},
    {"kind": "conferences", "name": "EMBL events", "url": "https://www.embl.org/events/"},
    {"kind": "conferences", "name": "EMBO conferences", "url": "https://www.embo.org/conferences-training/"},
    {"kind": "conferences", "name": "Wellcome Connecting Science",
     "url": "https://coursesandconferences.wellcomeconnectingscience.org/our-events/"},
    {"kind": "conferences", "name": "ASHG meetings", "url": "https://www.ashg.org/meetings/"},
    {"kind": "conferences", "name": "ISCB", "url": "https://www.iscb.org/"},
]


# --------------------------------------------------------------------------- the key
def get_key() -> str | None:
    try:
        import keyring
        return keyring.get_password(KEY_SERVICE, KEY_USER)
    except Exception:
        return None


def set_key(key: str) -> bool:
    key = (key or "").strip()
    if not re.match(r"^sk-[A-Za-z0-9_-]{16,}$", key):
        return False
    import keyring
    keyring.set_password(KEY_SERVICE, KEY_USER, key)
    return True


def forget_key() -> None:
    try:
        import keyring
        keyring.delete_password(KEY_SERVICE, KEY_USER)
    except Exception:
        pass


# --------------------------------------------------------------------------- state (this computer only)
def load() -> dict[str, Any]:
    data = read_json(SCOUT_FILE, {}) or {}
    data.setdefault("candidates", {})
    data.setdefault("rejected", [])
    data.setdefault("sources", [dict(s, on=True) for s in SOURCES])
    data.setdefault("focus", DEFAULT_FOCUS)
    return data


def save(state: dict[str, Any]) -> None:
    ensure_dirs()
    write_json(SCOUT_FILE, state)


# --------------------------------------------------------------------------- pages as text and numbered links
_DROP = re.compile(r"<(script|style|noscript|svg|head)\b.*?</\1>", re.S | re.I)
_LINK = re.compile(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", text))).strip()


def page(url: str, session: requests.Session | None = None, timeout: float = 25.0) -> dict[str, Any]:
    """{"url" (after redirects), "text", "links": [(text, absolute https url)]} of a web page."""
    s = session or requests
    r = s.get(url, timeout=timeout, headers=UA)
    r.raise_for_status()
    html = _DROP.sub(" ", r.text)
    links, seen = [], set()
    for href, inner in _LINK.findall(html):
        full = urljoin(r.url, unescape(href.strip()))
        label = _clean(inner)[:140]
        if (full.startswith("https://") and "\\" not in full and " " not in full and full not in seen
                and len(label) > 3):
            seen.add(full)
            links.append((label, full))
    return {"url": r.url, "text": _clean(html), "links": links}


# --------------------------------------------------------------------------- DeepSeek
def ask(key: str, system: str, user: str, post: Callable[..., Any] | None = None, timeout: float = 120.0) -> dict[str, Any]:
    """One JSON answer from DeepSeek (temperature 0: the same page gives the same answer)."""
    body = {"model": MODEL, "temperature": 0, "response_format": {"type": "json_object"}, "max_tokens": 2000,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    r = (post or requests.post)(API_URL, json=body, timeout=timeout,
                                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if getattr(r, "status_code", 200) == 401:
        raise PermissionError("DeepSeek didn't accept the key")
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    try:
        out = json.loads(content)
    except ValueError:
        out = {}
    return out if isinstance(out, dict) else {}


WHAT = {"jobs": "a job: a PhD place, postdoc, master's place, research or faculty position, fellowship or internship",
        "funding": "a funding call: a grant, fellowship, scholarship, prize or travel grant people can apply for",
        "conferences": "a conference, meeting, symposium, workshop or summer school people can register or "
                       "submit an abstract to"}

PICK_SYSTEM = """You help myGeeKy's maker find opportunities for early-career researchers.
You get a listing page: its text, and its links, numbered. Pick the links that each lead to ONE specific {what}
that fits this field: {focus}.
Rules:
- Only links that clearly lead to a single opportunity (not search pages, categories, news, login, or about pages).
- Only opportunities that look open now (today is {today}); skip anything that says closed or expired.
- Only ones that fit the field. When unsure, leave it out: accuracy matters more than finding many.
Answer as JSON: {{"picks": [{{"n": <link number>, "why": "<a few words>"}}]}}, at most {max_picks}, best first."""

READ_SYSTEM = """You read ONE web page for myGeeKy's maker and extract a single {what}.
Today is {today}. The field is: {focus}.
Use ONLY facts written on the page. Never guess: if something isn't on the page, use "" (or [] / false).
Answer as JSON with exactly these keys:
{{
 "is_listing": true if the page is about ONE specific {kind_word} that is open now, else false,
 "title": "its title EXACTLY as written on the page, in the page's own language, word for word",
 "language": "the language the page is written in, in English: English, French, German, Spanish...",
 "title_en": "the title in English. If the page is already in English, repeat it unchanged",
 "summary_en": "the summary below, in English (repeat it unchanged if the page is in English)",
 "who_en": "'who' below, in English (funding only; '' if empty)",
 "amount_en": "'amount' below, in English, keeping the currency and the numbers as they are",
 "translations": {{"ar": {{"title": "", "summary": "", "who": "", "amount": "", "student": ""}},
                  "fr": {{...}}, "de": {{...}}, "es": {{...}}, "zh": {{...}}}},
 "org": "the organisation offering it",
 "place": "city, country -- ALWAYS end with the country, spelled out in English, even where the page
          gives only a region, a state or a two-letter code. 'online' if it is not anywhere",
 "remote": true only if the page says it can be done remotely,
 "type": "one of: phd, postdoc, master, job, internship, fellowship, faculty, engineer (jobs only, else '')",
 "deadline": "YYYY-MM-DD: the last day to apply (jobs, funding) or to submit an abstract or register (conferences)",
 "deadline_quote": "the exact sentence or phrase from the page that gives that deadline, copied word for word",
 "starts": "YYYY-MM-DD the conference starts (conferences only)",
 "ends": "YYYY-MM-DD the conference ends (conferences only)",
 "who": "who can apply, in a few words, if the page says (funding only)",
 "amount": "how much, if the page says (funding only)",
 "student": "student discounts or travel awards, if the page says (conferences only)",
 "keywords": ["3 to 8 lowercase topic words from the page"],
 "summary": "one or two plain sentences on what it is, from the page",
 "relevance": a number 0-1: how well it fits the field,
 "confidence": a number 0-1: how sure you are that it is real, open, and every field above is right
}}

Translate faithfully: say what the page says, in plain English, and never add a fact that is not there.
"title" and "deadline_quote" stay in the page's own language, word for word, because myGeeKy checks them
against the page itself.

"translations" is the English above said again in each of these five languages, so that someone who does not
read English can still tell what the listing is: ar Arabic, fr French, de German, es Spanish, zh Chinese
(Simplified). Leave dates, numbers, currencies, the organisation's name and the technical words of the field
(RNA-seq, GWAS, BLAST, PhD, postdoc) as they are, and use "" for any field that is empty above."""

KIND_WORD = {"jobs": "job", "funding": "funding call", "conferences": "conference or meeting"}


def pick(key: str, kind: str, listing: dict[str, Any], focus: str, today: date, post=None) -> list[str]:
    """The links on a listing page that are single, relevant listings (DeepSeek answers with numbers)."""
    links = listing["links"][:MAX_LINKS]
    numbered = "\n".join(f"[{i}] {label} -> {url}" for i, (label, url) in enumerate(links, 1))
    out = ask(key, PICK_SYSTEM.format(what=WHAT[kind], focus=focus, today=today.isoformat(), max_picks=MAX_PICKS),
              f"PAGE: {listing['url']}\n\nTEXT:\n{listing['text'][:PAGE_CHARS]}\n\nLINKS:\n{numbered}", post)
    urls = []
    for p in out.get("picks") or []:
        try:
            n = int(p.get("n") if isinstance(p, dict) else p)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= len(links) and links[n - 1][1] not in urls:
            urls.append(links[n - 1][1])
    return urls[:MAX_PICKS]


def read(key: str, kind: str, detail: dict[str, Any], focus: str, today: date, post=None) -> dict[str, Any]:
    return ask(key, READ_SYSTEM.format(what=WHAT[kind], kind_word=KIND_WORD[kind], focus=focus, today=today.isoformat()),
               f"PAGE: {detail['url']}\n\nTEXT:\n{detail['text'][:PAGE_CHARS]}", post)


# --------------------------------------------------------------------------- the alerts in your mailbox
# A third way in, BESIDE the sites myGeeKy reads and the pages the maker pastes -- none of them replaces
# another. Nature Careers, Science Careers, jobs.ac.uk and EURAXESS will email their listings to anyone who
# asks, and so will LinkedIn, Indeed and Glassdoor, which refuse a robot on their own sites. Subscribing is
# therefore the way to reach exactly the boards that cannot be read.
#
# The email is the DISCOVERY step and not the evidence. An alert wraps its links so the sender can count
# clicks, and a deadline quoted out of an email is not a deadline quoted from the employer -- so each link
# is unwrapped, the employer's own page is fetched, and that page is what `read` and `check` are held
# against, exactly as for a site myGeeKy found by itself. When a page truly cannot be fetched, the email's
# own words stand in for it, the way a pasted page does: weaker evidence, and the maker sees which it was.
def resolve_link(url: str, session: requests.Session | None = None) -> str:
    """Where a tracking link actually leads. Follows redirects without downloading the page."""
    s = session or requests
    try:
        r = s.head(url, allow_redirects=True, timeout=15, headers=UA)
        if getattr(r, "status_code", 500) < 400 and getattr(r, "url", ""):
            return str(r.url)
    except requests.RequestException:
        pass
    return url


def from_alerts(cfg_kind: str = "jobs", key: str | None = None, today: date | None = None,
                progress: Callable[[str], None] | None = None,
                session: requests.Session | None = None, post=None, mailbox=None) -> dict[str, Any]:
    """Listings out of the alert emails in the maker's chosen folder.

    Everything goes through the same `read`, `check` and `to_item` as any other route, and lands in the
    same review queue, so an emailed listing is held to the standard a fetched one is. Messages already
    looked at are remembered, because the folder is opened read-only and myGeeKy will not mark anybody's
    mail as read."""
    from . import mailbox as mail
    key = key or get_key()
    if not key:
        raise PermissionError("Add your DeepSeek key first")
    if cfg_kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    today = today or date.today()
    say = progress or (lambda m: None)
    state = load()
    box = state.get("mailbox") or {}
    if not box.get("address"):
        raise PermissionError("Tell myGeeKy which mailbox and folder to read first")
    password = mail.get_password()
    if not password:
        raise PermissionError("Add your mailbox password first (for Gmail, an App Password)")
    session = session or requests.Session()
    focus = state.get("focus") or DEFAULT_FOCUS
    done = set(state.setdefault("mail_seen", []))
    known = {c["item"]["url"] for c in state["candidates"].values()}
    known |= {it["url"] for k in KINDS for it in curated.load().get(k, [])}
    opened = mailbox or mail.Mailbox(box["address"], password, box.get("host", ""),
                                     box.get("folder", "INBOX"))
    added, dropped, read_count, errors, why = 0, 0, 0, [], []
    with opened as inbox:
        messages = inbox.recent()
        say(f"{len(messages)} alert(s) in {box.get('folder', 'INBOX')}; "
            f"{sum(1 for mid, _ in messages if mid in done)} already looked at")
        for mid, message in messages:
            if mid in done:
                continue
            about = mail.describe(message)
            say(f"Reading: {about['subject'][:58]}")
            found = mail.links(message, resolve=lambda u: resolve_link(u, session))
            for url in found[:MAX_PICKS]:
                if url in known:
                    continue
                try:
                    detail = page(url, session)
                except PermissionError:
                    raise
                except Exception:
                    # the employer's page cannot be had: the email's own words stand in for it
                    detail = {"url": url, "text": mail.text_of(message), "links": []}
                try:
                    answer = read(key, cfg_kind, detail, focus, today, post)
                    out = check(cfg_kind, answer, detail, url, today)
                except PermissionError:
                    raise
                except Exception as exc:
                    errors.append(f"{type(exc).__name__}")
                    continue
                read_count += 1
                if out["hard_fail"]:
                    dropped += 1
                    why.append(f"{curated._text(answer.get('title_en') or answer.get('title'), 44)}: "
                               f"{out['hard_fail']}")
                    continue
                item = to_item(cfg_kind, answer, url)
                if not item or item["url"] in known:
                    dropped += 1
                    continue
                state["candidates"][item["id"]] = {
                    "kind": cfg_kind, "item": item, "score": out["score"], "checks": out["checks"],
                    "status": "new", "from": "emailed", "source": url,
                    "alert": about["subject"][:120], "seen": today.isoformat()}
                known.add(item["url"])
                added += 1
            done.add(mid)
    state["mail_seen"] = sorted(done)[-400:]
    save(state)
    return {"added": added, "dropped": dropped, "read": read_count, "messages": len(messages),
            "why": why[:10], "errors": sorted(set(errors))}


def mailbox_settings(address: str = "", host: str = "", folder: str = "") -> dict[str, Any]:
    """Read, or change, which mailbox and folder the alerts are read from.

    Kept in scout.json, which never leaves this computer and is never committed -- the same file the
    sources and the review queue live in."""
    from . import mailbox as mail
    state = load()
    box = dict(state.get("mailbox") or {})
    if address or host or folder:
        if address:
            box["address"] = curated._text(address, 200).strip()
            box.setdefault("host", "")
        if host:
            box["host"] = curated._text(host, 200).strip()
        if folder:
            box["folder"] = curated._text(folder, 120).strip()
        state["mailbox"] = box
        save(state)
    box.setdefault("folder", "INBOX")
    box.setdefault("host", "")
    return {**box, "guessed_host": mail.host_for(box.get("address", "")),
            "has_password": bool(mail.get_password())}


# --------------------------------------------------------------------------- a page somebody pasted in
# Most of the big job boards cannot be read by a robot, and should not be: Indeed, SimplyHired, Monster,
# ZipRecruiter and CareerBuilder all answer a plain fetch with 403, and LinkedIn and Glassdoor answer but
# forbid it in their terms. University portals built on SuccessFactors answer with an empty shell, because
# the listings arrive later by JavaScript. Between them that is most of the web's jobs.
#
# A person opening one of those pages in a browser and copying the text is doing none of that. So this is
# the way in: the maker pastes what they are looking at, says which page it came from, and DeepSeek reads
# it. Nothing is fetched, so nothing is blocked -- and the checking is unharmed, because the pasted text
# IS the page. The quote still has to be found in it, word for word, exactly as for a page myGeeKy read
# itself. What the paste cannot carry is each listing's own link, so a board full of titles gives thin
# results; one listing's own page gives a good one.
PASTE_SYSTEM = """You read text that somebody copied out of ONE web page, for myGeeKy's maker.
Today is {today}. The field is: {focus}.
Find every {what} in it that is open now. There may be one, several, or none.
Use ONLY what is in the text. Never guess, and never add a listing that is not there.
Answer as JSON:
{{
 "listings": [
   {{
    "title": "its title EXACTLY as written in the text, word for word",
    "language": "the language the text is written in, in English",
    "title_en": "the title in English (repeat it unchanged if it is already English)",
    "summary_en": "one or two plain sentences on what it is, in English",
    "org": "the organisation offering it",
    "place": "city, country -- ALWAYS end with the country, spelled out in English. 'online' if nowhere",
    "remote": true only if the text says it can be done remotely,
    "type": "one of: phd, postdoc, master, job, internship, fellowship, faculty, engineer (jobs only)",
    "deadline": "YYYY-MM-DD: the last day to apply",
    "deadline_quote": "the exact sentence or phrase from the text giving that deadline, word for word",
    "link": "the listing's own full https link IF the text contains one, else ''",
    "who": "who can apply, in a few words (funding only)",
    "amount": "how much (funding only)",
    "starts": "YYYY-MM-DD it starts (conferences only)",
    "ends": "YYYY-MM-DD it ends (conferences only)",
    "student": "student discounts or travel awards (conferences only)",
    "keywords": ["3 to 8 lowercase topic words"],
    "relevance": a number 0-1: how well it fits the field,
    "confidence": a number 0-1: how sure you are it is real, open, and every field above is right
   }}
 ]
}}

Leave out anything with no closing date in the text: myGeeKy cannot publish a listing it cannot date.
"title" and "deadline_quote" stay in the text's own language, word for word, because myGeeKy checks them
against the pasted text itself."""


def read_paste(key: str, kind: str, text: str, focus: str, today: date, post=None) -> list[dict[str, Any]]:
    """Every listing DeepSeek can find in text somebody pasted in."""
    out = ask(key, PASTE_SYSTEM.format(what=WHAT[kind], focus=focus, today=today.isoformat()),
              "TEXT:\n" + text[:PAGE_CHARS], post)
    found = out.get("listings")
    return [a for a in (found if isinstance(found, list) else [])[:40] if isinstance(a, dict)]


def from_paste(kind: str, text: str, url: str, key: str | None = None, focus: str | None = None,
               today: date | None = None, post=None,
               progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Listings out of a pasted page, checked and queued for the maker exactly like any the scout found.

    `url` is the page it was copied from, and is used for any listing that did not carry its own link --
    so a reader can always get back to something real. Everything goes through the same `check` and the
    same `to_item`, so a pasted listing is held to the standard a fetched one is, and lands in the same
    accepted/rejected queue rather than straight onto the lists."""
    key = key or get_key()
    if not key:
        raise PermissionError("Add your DeepSeek key first")
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    text = (text or "").strip()
    if len(text) < 200:
        raise ValueError("That looks too short to be a page. Copy the whole listing and paste it again.")
    page_url = curated._https(url)
    if not page_url:
        raise ValueError("Paste the page's https link too, so each listing has somewhere to point at.")
    today = today or date.today()
    say = progress or (lambda m: None)
    state = load()
    focus = focus or state.get("focus") or DEFAULT_FOCUS
    known = {c["item"]["url"] for c in state["candidates"].values()}
    known |= {it["url"] for k in KINDS for it in curated.load().get(k, [])}
    # the pasted text stands in for the page, for the checks and for the quote
    pretend = {"url": page_url, "text": text, "links": []}
    say("Reading what you pasted…")
    answers = read_paste(key, kind, text, focus, today, post)
    say(f"{len(answers)} listing(s) found; checking each against what you pasted…")
    added, dropped, why = 0, 0, []
    for ans in answers:
        link = curated._https(ans.get("link")) or page_url
        # being in the "listings" array IS the claim that this is one, so it is not asked for twice. The
        # checks that matter are untouched: the title and the quote must still be found in the text.
        ans.setdefault("is_listing", True)
        out = check(kind, ans, pretend, page_url, today)
        if out["hard_fail"]:
            dropped += 1
            why.append(f"{curated._text(ans.get('title_en') or ans.get('title'), 50)}: {out['hard_fail']}")
            continue
        item = to_item(kind, ans, link)
        if not item or item["url"] in known:
            dropped += 1
            continue
        state["candidates"][item["id"]] = {"kind": kind, "item": item, "score": out["score"],
                                           "checks": out["checks"], "status": "new", "from": "pasted",
                                           "source": page_url, "seen": today.isoformat()}
        known.add(item["url"])
        added += 1
    save(state)
    return {"added": added, "dropped": dropped, "why": why[:10], "found": len(answers)}


# --------------------------------------------------------------------------- seasons: confirming the past
# A season (seasons.py) claims a scholarship comes back every year, and offers the next one as an
# expectation. The expectation is only worth as much as the history behind it, so DeepSeek is not asked
# when the next round opens -- no page can say that. It is asked to open the page of a round that has
# ALREADY happened and find the sentence that gave its dates. myGeeKy then checks that sentence against
# the page itself, exactly as it does for a listing's deadline. That is a small, cheap job on a page that
# exists, rather than a search across the web.
SEASON_SYSTEM = """You read ONE web page about a scholarship, grant or funding programme for myGeeKy.
The page is said to be about a round that has already happened. Find what the page says about WHEN that
round opened and closed.
Use ONLY what is written on the page. Never guess a date, and never work one out from another year.
Answer as JSON with exactly these keys:
{{
 "found": true if this page really is about this programme and gives its dates, else false,
 "recurring": true if the page shows this comes back regularly (yearly, "annual", "every year", a round
              number such as 2026/2027, or a named past round), else false,
 "opens": "YYYY-MM-DD the day applications opened, or '' if the page gives only a closing date",
 "closes": "YYYY-MM-DD the last day to apply",
 "quote": "the exact sentence or phrase from the page that gives those dates, copied word for word",
 "cycle": "the award year the round was for, as four digits, or ''",
 "note": "at most 15 words: anything a reader must know, such as each course setting its own deadline"
}}

The quote must be on the page, word for word, in the page's own language. myGeeKy checks it against the
page and throws the answer away if it is not there."""


def read_season(key: str, season: dict[str, Any], detail: dict[str, Any], post=None) -> dict[str, Any]:
    """What one page says about a round of this season that has already been and gone."""
    asked = (f"PROGRAMME: {season.get('title', '')}\n"
             f"OFFERED BY: {season.get('org', '')}\n\nPAGE: {detail['url']}\n\nTEXT:\n"
             f"{detail['text'][:PAGE_CHARS]}")
    return ask(key, SEASON_SYSTEM, asked, post)


def check_season(season: dict[str, Any], ans: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    """myGeeKy's own checks on what DeepSeek read. {"ok", "why", "checks", "seen"}.

    `seen` is the occurrence to keep if it passes -- taken from the PAGE, not from what the maker wrote
    down. Where the two disagree the page wins and the record is corrected, because the page is the only
    thing either of them can point at."""
    from . import seasons as _seasons
    checks: list[tuple[bool, str]] = []
    text = _norm(detail["text"])
    if not ans.get("found"):
        return {"ok": False, "why": "the page does not give this programme's dates", "checks": checks,
                "seen": None}
    closes = curated._day(ans.get("closes"))
    if not closes:
        return {"ok": False, "why": "no closing date on the page", "checks": checks, "seen": None}
    quote = curated._text(ans.get("quote"), 400)
    quoted = bool(quote) and _norm(quote) in text
    checks.append((quoted, "the sentence is on the page"))
    if not quoted:
        return {"ok": False, "why": "the sentence it quoted is not on the page", "checks": checks,
                "seen": None}
    checks.append((date_in(quote, closes), "that sentence holds the closing date"))
    opens = curated._day(ans.get("opens"))
    if opens:
        checks.append((date_in(quote, opens) or opens <= closes, "the opening date fits the same sentence"))
    same_site = (urlsplit(detail["url"]).netloc.split(".")[-2:]
                 == urlsplit(season.get("url", "")).netloc.split(".")[-2:])
    checks.append((same_site, "on the programme's own site"))
    checks.append((bool(ans.get("recurring")), "the page shows it comes back"))
    if not all(ok for ok, _ in checks[:2]):
        return {"ok": False, "why": "the dates and the sentence do not agree", "checks": checks, "seen": None}
    seen = _seasons.clean_seen([{"cycle": ans.get("cycle") or closes[:4], "opens": opens, "closes": closes,
                                 "url": detail["url"], "quote": quote, "checked": True}])
    if not seen:
        return {"ok": False, "why": "what came back was not a usable occurrence", "checks": checks,
                "seen": None}
    return {"ok": True, "why": "", "checks": checks, "seen": seen[0]}


def confirm_seasons(seasons_in: list[dict[str, Any]], key: str | None = None,
                    progress: Callable[[str], None] | None = None,
                    session: requests.Session | None = None, post=None) -> dict[str, Any]:
    """Open the page behind every unchecked occurrence and either confirm it or throw it away.

    This is the only thing that turns a season the maker wrote down into one anybody else is shown. It
    costs one page and one short DeepSeek answer per occurrence, so the whole list is pennies."""
    key = key or get_key()
    if not key:
        raise PermissionError("Add your DeepSeek key first")
    say = progress or (lambda m: None)
    session = session or requests.Session()
    confirmed, refused, errors = 0, 0, []
    for season in seasons_in:
        for i, occurrence in enumerate(season.get("seen") or []):
            if occurrence.get("checked"):
                continue
            say(f"Checking {season.get('title', season.get('id'))}…")
            try:
                detail = page(occurrence["url"], session)
                ans = read_season(key, season, detail, post)
                out = check_season(season, ans, detail)
            except PermissionError:
                raise
            except Exception as exc:
                errors.append(f"{season.get('id')}: {type(exc).__name__}")
                continue
            if out["ok"]:
                season["seen"][i] = out["seen"]
                confirmed += 1
                say(f"  confirmed {out['seen']['opens'] or '?'} to {out['seen']['closes']}")
            else:
                refused += 1
                say(f"  refused: {out['why']}")
    return {"confirmed": confirmed, "refused": refused, "errors": errors}


# --------------------------------------------------------------------------- seasons: finding a few more
SEASON_PICK_SYSTEM = """You help myGeeKy's maker find scholarships and funding that come back EVERY YEAR.
You get a page's text and its links, numbered. Pick the links that each lead to ONE programme that
recurs -- a government or embassy scholarship, a national grant scheme, a funded Master's or PhD
programme with a yearly intake.
Rules:
- Pick a programme, never a news item, a list of many, a login page or a past-results page.
- A recurring programme only. Skip anything that happens once.
- At most {max_picks} links, best first.
- Answer as JSON: {{"links": [numbers]}} and nothing else."""


def pick_seasons(key: str, listing: dict[str, Any], post=None) -> list[str]:
    """The links on a page that each look like a programme coming back every year."""
    links = listing["links"][:MAX_LINKS]
    numbered = "\n".join(f"[{i}] {label} -> {url}" for i, (label, url) in enumerate(links, 1))
    out = ask(key, SEASON_PICK_SYSTEM.format(max_picks=MAX_PICKS),
              f"PAGE: {listing['url']}\n\nTEXT:\n{listing['text'][:PAGE_CHARS]}\n\nLINKS:\n{numbered}",
              post)
    picked = []
    for n in (out.get("links") or [])[:MAX_PICKS]:
        try:
            picked.append(links[int(n) - 1][1])
        except (TypeError, ValueError, IndexError):
            continue
    return list(dict.fromkeys(picked))


SEASON_SOURCES = [
    {"name": "DAAD scholarship database", "url": "https://www2.daad.de/deutschland/stipendium/datenbank/en/"
                                                 "21148-scholarship-database/"},
    {"name": "Erasmus Mundus Joint Masters catalogue",
     "url": "https://www.eacea.ec.europa.eu/scholarships/emjmd-catalogue_en"},
    {"name": "Commonwealth Scholarship Commission",
     "url": "https://cscuk.fcdo.gov.uk/scholarships/"},
    {"name": "Swiss Government Excellence Scholarships",
     "url": "https://www.sbfi.admin.ch/sbfi/en/home/education/scholarships-and-grants/"
            "swiss-government-excellence-scholarships.html"},
]


# --------------------------------------------------------------------------- saying it in other languages
SAY_LANGUAGES = {"ar": "Arabic", "fr": "French", "de": "German", "es": "Spanish", "zh": "Chinese (Simplified)"}
SAY_FIELDS = ("title", "summary", "who", "amount", "student")
SAY_SYSTEM = """You translate one research opportunity for myGeeKy, so that someone who does not read English
can still tell what it is and whether to apply.
Answer as JSON with exactly these keys: {codes}.
Each is an object holding these keys, translated into that language: {fields}.
Rules:
- Say exactly what the English says. Never add a fact, drop one, or soften one.
- Leave dates, numbers, currencies, the organisation's name and the words of the field itself as they are:
  RNA-seq, GWAS, BLAST, PhD, postdoc, bioinformatics, single-cell.
- Translate nothing else into English, and answer with no commentary."""


def say_in(item: dict[str, Any], key: str, post=None) -> dict[str, dict[str, Any]]:
    """One listing in the other languages myGeeKy offers, ready for `curated.clean_translations`.

    Only the words people read are translated. The deadline, the link and the organisation are untouched,
    and nothing here can change the listing itself: a translation that comes back wrong, short or not at
    all costs the listing nothing. Listings found by `find` are translated as they are read, so this is for
    the ones that were already on the lists before myGeeKy could do it."""
    english = {f: item[f] for f in SAY_FIELDS if item.get(f)}
    if not english.get("title"):
        return {}
    system = SAY_SYSTEM.format(codes=", ".join(f'"{c}" ({name})' for c, name in SAY_LANGUAGES.items()),
                               fields=", ".join(english))
    return curated.clean_translations(ask(key, system, json.dumps(english, ensure_ascii=False), post))


# --------------------------------------------------------------------------- checking what DeepSeek said
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december"]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def date_in(quote: str, day: str) -> bool:
    """Does the quote hold this date, written any common way (2026-12-01, 1 December 2026, Dec 1st, 01/12/2026…)?"""
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return False
    q = (quote or "").lower()
    if day in q:
        return True
    month, short = _MONTHS[d.month - 1], _MONTHS[d.month - 1][:3]
    has_month = month in q or re.search(rf"\b{short}\b", q) is not None
    has_day = re.search(rf"(?<!\d)0?{d.day}(st|nd|rd|th)?(?!\d)", q) is not None
    if has_month and has_day:
        return True
    return re.search(rf"(?<!\d)0?{d.day}[./-]0?{d.month}[./-](\d\d)?{d.year % 100:02d}(?!\d)", q) is not None or \
        re.search(rf"(?<!\d)0?{d.month}[./-]0?{d.day}[./-](\d\d)?{d.year % 100:02d}(?!\d)", q) is not None


def check(kind: str, ans: dict[str, Any], detail: dict[str, Any], listing_url: str, today: date) -> dict[str, Any]:
    """myGeeKy's own checks on DeepSeek's answer. {"hard_fail": reason or "", "checks": [(ok, text)], "score"}."""
    checks: list[tuple[bool, str]] = []
    text = _norm(detail["text"])
    title = curated._text(ans.get("title"), 140)
    if not ans.get("is_listing") or not title:
        return {"hard_fail": "not a single open listing", "checks": checks, "score": 0.0}
    # The title and the quote are checked in the page's own language; what people are shown is the English
    # that came back with them. A page in another language is translated, never dropped for it.
    english = curated._text(ans.get("title_en"), 140) or title
    if not curated.english_enough(english, ans.get("summary_en")):
        return {"hard_fail": "no English translation came back", "checks": checks, "score": 0.0}
    if _norm(english) != _norm(title):
        checks.append((True, f"translated from {curated._text(ans.get('language'), 30) or 'another language'}"))
    words = [w for w in _norm(title).split() if len(w) > 2]
    on_page = sum(1 for w in words if w in text) / max(len(words), 1)
    title_found = on_page >= 0.7           # held in its own name: `checks` no longer starts with this one
    checks.append((title_found, "title is on the page"))
    deadline = curated._day(ans.get("deadline"))
    if not deadline:
        return {"hard_fail": "no deadline on the page", "checks": checks, "score": 0.0}
    left = (date.fromisoformat(deadline) - today).days
    if left < MIN_DAYS_LEFT:
        return {"hard_fail": f"deadline {deadline} has passed or is too close", "checks": checks, "score": 0.0}
    quote = curated._text(ans.get("deadline_quote"), 400)
    quoted = bool(quote) and _norm(quote) in text
    checks.append((quoted, "deadline sentence is on the page"))
    checks.append((date_in(quote, deadline), "that sentence holds the date"))
    same_site = urlsplit(detail["url"]).netloc.split(".")[-2:] == urlsplit(listing_url).netloc.split(".")[-2:]
    checks.append((same_site, "on the site it was listed on"))
    relevance = max(0.0, min(1.0, float(ans.get("relevance") or 0)))
    checks.append((relevance >= 0.5, f"fits your field ({round(relevance * 100)}%)"))
    if kind == "conferences" and curated._day(ans.get("starts")):
        checks.append((curated._day(ans.get("starts")) >= deadline, "starts after its deadline"))
    if not quoted and not title_found:
        return {"hard_fail": "neither the title nor the deadline could be found on the page", "checks": checks,
                "score": 0.0}
    conf = max(0.0, min(1.0, float(ans.get("confidence") or 0)))
    passed = sum(1 for ok, _ in checks if ok) / len(checks)
    return {"hard_fail": "", "checks": checks, "score": round(conf * passed, 3)}


def to_item(kind: str, ans: dict[str, Any], url: str) -> dict[str, Any] | None:
    """DeepSeek's answer as a curated-list item (checked by curated.clean_item, like any other).

    People read the English; the title as printed on the page is kept beside it, so anyone can hold the
    listing against its own source."""
    original = curated._text(ans.get("title"), 140)
    title = curated._text(ans.get("title_en"), 140) or original
    org = curated._text(ans.get("org"), 100)
    deadline = curated._day(ans.get("deadline"))
    base = re.sub(r"[^a-z0-9]+", "-", f"{org} {title}".lower()).strip("-")[:60].strip("-")
    language = curated._text(ans.get("language"), 30)
    translated = bool(original) and _norm(title) != _norm(original)
    raw = {"id": f"{base}-{deadline[:4]}" if base else "", "title": title, "url": url, "deadline": deadline,
           "org": org, "place": ans.get("place"), "remote": bool(ans.get("remote")), "type": ans.get("type") or "job",
           "who": ans.get("who_en") or ans.get("who"), "amount": ans.get("amount_en") or ans.get("amount"),
           "starts": ans.get("starts"), "ends": ans.get("ends"), "student": ans.get("student"),
           "keywords": ans.get("keywords") or [], "summary": ans.get("summary_en") or ans.get("summary"),
           "language": language if translated else "", "original_title": original if translated else "",
           "translations": ans.get("translations")}
    return curated.clean_item(kind, raw)


# --------------------------------------------------------------------------- a run
def find(cfg: MyGeekyConfig, key: str | None = None, progress: Callable[[str], None] | None = None,
         session: requests.Session | None = None, post=None, today: date | None = None,
         sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Look through the chosen sites for new listings. Returns {"added", "dropped", "errors", "seen"}."""
    key = key or get_key()
    if not key:
        raise PermissionError("Add your DeepSeek key first")
    today = today or date.today()
    say = progress or (lambda m: None)
    state = load()
    focus = state.get("focus") or DEFAULT_FOCUS
    known = set(state["candidates"]) | set(state["rejected"])
    published = {it["url"] for k in KINDS for it in curated.load().get(k, [])}
    known_urls = {c["item"]["url"] for c in state["candidates"].values()} | published
    session = session or requests.Session()
    added, dropped, errors, seen = 0, 0, [], 0
    for src in [s for s in (sources or state["sources"]) if s.get("on", True) and s.get("kind") in KINDS]:
        kind = src["kind"]
        say(f"Reading {src.get('name') or src['url']}…")
        try:
            listing = page(src["url"], session)
            urls = pick(key, kind, listing, focus, today, post)
        except PermissionError:
            raise
        except Exception as exc:  # noqa: BLE001 - one site down shouldn't stop the run
            errors.append(f"{src.get('name') or src['url']}: {type(exc).__name__}")
            continue
        for url in urls:
            if url in known_urls:
                continue
            seen += 1
            say(f"Checking a {KIND_WORD[kind]} from {src.get('name')}…")
            try:
                detail = page(url, session)
                ans = read(key, kind, detail, focus, today, post)
            except PermissionError:
                raise
            except Exception:  # noqa: BLE001
                dropped += 1
                continue
            verdict = check(kind, ans, detail, src["url"], today)
            item = to_item(kind, ans, detail["url"]) if not verdict["hard_fail"] else None
            if not item or item["id"] in known:
                dropped += 1
                continue
            known.add(item["id"])
            known_urls.add(url)
            state["candidates"][item["id"]] = {
                "kind": kind, "item": item, "status": "new", "score": verdict["score"],
                "checks": [[ok, t] for ok, t in verdict["checks"]], "quote": curated._text(ans.get("deadline_quote"), 300),
                "source": src.get("name") or src["url"], "found_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            added += 1
    state["last_run"] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "added": added,
                         "dropped": dropped, "errors": errors}
    save(state)
    return {"added": added, "dropped": dropped, "errors": errors, "seen": seen}


# --------------------------------------------------------------------------- reviewing
def candidates(status: str = "new", today: date | None = None) -> list[dict[str, Any]]:
    """Candidates to review (best first), without any whose deadline has passed meanwhile."""
    today = today or date.today()
    out = []
    for cid, c in load()["candidates"].items():
        if c.get("status") != status:
            continue
        left = curated.days_left(c["item"], today)
        if left is not None and left < 0:
            continue
        out.append({**c, "id": cid, "days_left": left})
    return sorted(out, key=lambda c: (-c.get("score", 0), c.get("days_left") or 9999))


def set_status(cid: str, status: str, item: dict[str, Any] | None = None) -> bool:
    """accepted / rejected / new (undo). An edited item replaces the found one (checked again)."""
    state = load()
    c = state["candidates"].get(cid)
    if not c or status not in ("new", "accepted", "rejected"):
        return False
    if item is not None:
        fixed = curated.clean_item(c["kind"], {**c["item"], **item})
        if not fixed:
            return False
        c["item"] = fixed
        c["edited"] = True
    c["status"] = status
    if status == "rejected":
        state["rejected"] = list(dict.fromkeys(state["rejected"] + [cid]))[-2000:]
    save(state)
    return True


def set_sources(sources: list[dict[str, Any]]) -> None:
    state = load()
    clean = []
    for s in sources:
        url = curated._https(s.get("url"))
        if url and s.get("kind") in KINDS:
            clean.append({"kind": s["kind"], "name": curated._text(s.get("name"), 60) or urlsplit(url).netloc,
                          "url": url, "on": s.get("on", True) is not False})
    state["sources"] = clean
    save(state)


def set_focus(text: str) -> None:
    state = load()
    state["focus"] = curated._text(text, 300) or DEFAULT_FOCUS
    save(state)


# --------------------------------------------------------------------------- publishing (only when pressed)
REPO_URL = "https://github.com/mygeeky/myGeeKy.git"
CURATED_PATH = "src/mygeeky/data/curated.json"


def merge(data: dict[str, Any], accepted: list[dict[str, Any]], today: date | None = None) -> tuple[dict[str, Any], int]:
    """The curated file with the accepted listings added (and anything past its deadline pruned)."""
    out = json.loads(json.dumps(data))
    added = 0
    for c in accepted:
        lst = out.setdefault(c["kind"], [])
        if any(x.get("id") == c["item"]["id"] or x.get("url") == c["item"]["url"] for x in lst if isinstance(x, dict)):
            continue
        lst.append(c["item"])
        added += 1
    out, _ = curated.prune(out, today)
    out["version"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return out, added


def _git(args: list[str], cwd: Path) -> str:
    from . import winproc         # no console window flashing up on Windows
    r = winproc.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


def publish(dry_run: bool = False, repo_url: str = REPO_URL) -> dict[str, Any]:
    """Add every accepted listing to curated.json on GitHub's main branch: a fresh shallow copy of main in
    a temporary folder, one commit, one push, with your own git login. Your own checkouts aren't touched.
    {"published": n, "commit": sha} -- or, with dry_run, the change without pushing."""
    accepted = candidates("accepted")
    if not accepted:
        return {"published": 0, "commit": ""}
    tmp = Path(tempfile.mkdtemp(prefix="mygeeky-publish-"))
    try:
        _git(["clone", "--depth", "1", "--branch", "main", repo_url, str(tmp / "repo")], tmp)
        repo = tmp / "repo"
        path = repo / CURATED_PATH
        if not path.exists():
            raise FileNotFoundError("The curated lists aren't on GitHub's main branch yet: merge the Grow and "
                                    "Chances work into main first, then publish.")
        data = json.loads(path.read_text(encoding="utf-8"))
        merged, added = merge(data, accepted)
        problems = curated.problems(merged)
        if problems:
            raise ValueError("The file wouldn't pass its check: " + "; ".join(problems[:3]))
        if not added:
            raise ValueError("They're all on the lists already")
        path.write_text(json.dumps(merged, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        counts = {k: sum(1 for c in accepted if c["kind"] == k) for k in KINDS}
        summary = ", ".join(f"{n} {k}" for k, n in counts.items() if n)
        if dry_run:
            return {"published": 0, "would_add": added, "summary": summary}
        _git(["add", CURATED_PATH], repo)
        _git(["commit", "-m", f"Curated lists: add {summary}"], repo)
        _git(["push", "origin", "main"], repo)
        sha = _git(["rev-parse", "--short", "HEAD"], repo).strip()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    state = load()
    for c in accepted:
        if c["id"] in state["candidates"]:
            state["candidates"][c["id"]]["status"] = "published"
            state["candidates"][c["id"]]["published_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    save(state)
    return {"published": added, "commit": sha, "summary": summary}
