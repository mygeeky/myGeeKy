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
 "title": "its title as written on the page",
 "org": "the organisation offering it",
 "place": "city, country (or online)",
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
}}"""

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
    if not curated.english_enough(title, ans.get("summary"), ans.get("who"), ans.get("org")):
        return {"hard_fail": "not in English", "checks": checks, "score": 0.0}
    words = [w for w in _norm(title).split() if len(w) > 2]
    on_page = sum(1 for w in words if w in text) / max(len(words), 1)
    checks.append((on_page >= 0.7, "title is on the page"))
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
    if not quoted and not checks[0][0]:
        return {"hard_fail": "neither the title nor the deadline could be found on the page", "checks": checks,
                "score": 0.0}
    conf = max(0.0, min(1.0, float(ans.get("confidence") or 0)))
    passed = sum(1 for ok, _ in checks if ok) / len(checks)
    return {"hard_fail": "", "checks": checks, "score": round(conf * passed, 3)}


def to_item(kind: str, ans: dict[str, Any], url: str) -> dict[str, Any] | None:
    """DeepSeek's answer as a curated-list item (checked by curated.clean_item, like any other)."""
    title = curated._text(ans.get("title"), 140)
    org = curated._text(ans.get("org"), 100)
    deadline = curated._day(ans.get("deadline"))
    base = re.sub(r"[^a-z0-9]+", "-", f"{org} {title}".lower()).strip("-")[:60].strip("-")
    raw = {"id": f"{base}-{deadline[:4]}" if base else "", "title": title, "url": url, "deadline": deadline,
           "org": org, "place": ans.get("place"), "remote": bool(ans.get("remote")), "type": ans.get("type") or "job",
           "who": ans.get("who"), "amount": ans.get("amount"), "starts": ans.get("starts"), "ends": ans.get("ends"),
           "student": ans.get("student"), "keywords": ans.get("keywords") or [], "summary": ans.get("summary")}
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
