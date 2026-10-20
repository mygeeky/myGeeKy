"""Bring your own answer: everything the admin tab asks DeepSeek for can also be pasted or imported by hand.

An answer written anywhere -- another AI, a colleague, by hand -- goes through exactly the checks a DeepSeek
answer does and lands in the same review list:

- a **Highlight**: the facts are looked up on OpenAlex from its DOI, the numbers and tools in the story must be in
  the article's text (or its abstract), and it becomes a draft beside the ones DeepSeek writes (highlights.py);
- **listings** (jobs, funding calls, conferences): read out of a page the maker pasted; the title and the deadline
  quote must be found in that text word for word (scout.queue_listings);
- **quiz questions** for a reviewed protocol: each must quote its source page, follow the rules and, for code, do
  what it says (quizwriter.keep_one); with no blind DeepSeek second opinion, every one is marked for the maker.

`prompt(kind)` is the very prompt myGeeKy gives DeepSeek, so any AI can be asked the same way, and `shape(kind)` is
the JSON it must answer with. No DeepSeek key is needed for any of it.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from typing import Any

KINDS = {"highlight": "✨ Highlight", "jobs": "💼 Jobs", "funding": "💶 Funding", "conferences": "🎤 Conferences",
         "quiz": "📝 Quiz questions"}
# what the maker pastes beside the answer, per kind: (label, required?)
NEEDS = {"highlight": [("The article's DOI or link (if the answer doesn't carry it)", False),
                       ("The article's text, so its numbers can be checked (else its abstract is used)", False)],
         "jobs": [("The page's https link", True), ("The page's text, copied from your browser", True)],
         "funding": [("The page's https link", True), ("The page's text, copied from your browser", True)],
         "conferences": [("The page's https link", True), ("The page's text, copied from your browser", True)],
         "quiz": [("The protocol (its id) and the source page's https link", True), ("", False)]}

SHAPES = {
    "highlight": {"doi": "10.1038/s41586-0xx-xxxx-x", "title": "a headline in plain words, at most 12 words",
                  "hook": "one sentence, at most 30 words", "body": ["paragraph", "paragraph", "paragraph", "paragraph"],
                  "tool_names": ["each software or technique named, as written in the text"],
                  "skills": ["up to 6 lowercase skills"], "keywords": ["3 to 8 lowercase topic words"],
                  "translations": {"fr": {"title": "", "hook": "", "body": ["..."]}}},
    "listings": {"listings": [{"title": "its title exactly as written", "language": "English", "title_en": "",
                               "summary_en": "", "org": "", "place": "city, Country", "remote": False, "type": "postdoc",
                               "deadline": "YYYY-MM-DD", "deadline_quote": "the sentence giving the deadline, word for word",
                               "link": "https://...", "keywords": ["..."], "relevance": 0.8, "confidence": 0.9}]},
    "quiz": {"questions": [{"q": "...", "options": ["..", "..", "..", ".."], "answer": 0, "why": "...",
                            "quote": "the sentence from the source proving it, word for word",
                            "level": "easy|medium|tricky", "kind": "choice|code", "code": ""}]},
}


def shape(kind: str) -> str:
    """The JSON an answer of this kind must have, pretty-printed for the admin tab."""
    key = "listings" if kind in ("jobs", "funding", "conferences") else kind
    return json.dumps(SHAPES[key], ensure_ascii=False, indent=1)


def prompt(kind: str, focus: str = "", today: date | None = None) -> str:
    """The prompt myGeeKy gives DeepSeek for this kind, ready to paste into any AI (with what to paste after it)."""
    from . import highlights, quizwriter, safety, scout
    today = today or date.today()
    if kind == "highlight":
        system, _ = highlights.skill()
        return (f"{system}\n\nAlso put the article's DOI in \"doi\". Below come the FACTS (journal, date, authors and "
                f"where they work, from OpenAlex if you can) and the TEXT of the article.\n\nFACTS:\n\nTEXT:\n")
    if kind in scout.KINDS:
        focus = focus or scout.load().get("focus") or scout.DEFAULT_FOCUS
        return scout.PASTE_SYSTEM.format(what=scout.WHAT[kind], focus=focus, today=today.isoformat()) + "\n\nTEXT:\n"
    if kind == "quiz":
        return (quizwriter.WRITE_SYSTEM.format(n=quizwriter.PER_CALL, rules=safety.prompt_rules())
                + "\n\nSKILL:\nSTEP:\nSOURCE:\n\nTEXT:\n")
    raise ValueError(f"kind must be one of {list(KINDS)}")


def extract_json(text: str) -> Any:
    """The JSON in an answer: the whole text, a ```json block in it, or the first object or list it holds."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Paste the answer first.")
    try:
        return json.loads(text)
    except ValueError:
        pass
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S | re.I)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except ValueError:
            pass
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return dec.raw_decode(text[i:])[0]
            except ValueError:
                continue
    raise ValueError("No JSON found in what you pasted. It should look like the shape shown.")


def _rows(data: Any, key: str) -> list[dict[str, Any]]:
    rows = data.get(key) if isinstance(data, dict) and isinstance(data.get(key), list) else \
        data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    return [r for r in rows[:40] if isinstance(r, dict)]


def import_highlights(answer: str, link: str = "", text: str = "", session=None) -> dict[str, Any]:
    from . import highlight_shape as shape_, highlights
    stories, made, why = _rows(extract_json(answer), "highlights"), [], []
    state = highlights.load()
    for story in stories:
        dois = highlights.find_dois(f"{story.get('doi', '')} {link}")
        if not dois:
            why.append(f"{str(story.get('title', ''))[:50]}: no DOI in the answer or the link")
            continue
        try:
            fact = highlights.look_up(dois[0], session)
        except Exception as exc:
            why.append(f"{dois[0]}: not found on OpenAlex ({exc})")
            continue
        coverage, body_text = ("full", text) if len(text) >= highlights.MIN_TEXT else ("abstract", fact["abstract"])
        story["body"] = highlights.paragraphs(list(story.get("body") or []))
        said = {}
        for code, tr in (story.get("translations") or {}).items() if isinstance(story.get("translations"), dict) else []:
            if code in shape_.NAMES and isinstance(tr, dict) and tr.get("title") and tr.get("body"):
                said[code] = {"title": str(tr["title"]), "hook": str(tr.get("hook") or ""),
                              "body": highlights.paragraphs(list(tr["body"]))}
        it = highlights.item(fact, story, said, coverage)
        if not it:
            why.append(f"{dois[0]}: too short to make a story from")
            continue
        state["drafts"][it["id"]] = {"id": it["id"], "status": "new", "item": it, "from": "imported",
                                     "warnings": highlights.checks(story, body_text, fact),
                                     "made_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        made.append(it["id"])
    highlights.save(state)
    return {"added": len(made), "dropped": len(stories) - len(made), "why": why[:10], "found": len(stories)}


def import_listings(kind: str, answer: str, link: str, text: str, today: date | None = None) -> dict[str, Any]:
    from . import curated, scout
    page_url = curated._https(link)
    if not page_url:
        raise ValueError("Paste the page's https link too, so each listing has somewhere to point at.")
    if len((text or "").strip()) < 200:
        raise ValueError("Paste the page's text too: the titles and deadlines are checked against it.")
    answers = _rows(extract_json(answer), "listings")
    return scout.queue_listings(kind, answers, text, page_url, today, came_from="imported")


def import_quiz(answer: str, pid: str, link: str, session=None) -> dict[str, Any]:
    import requests
    from . import curated, protocols, quiz, quizwriter
    proto = next((p for p in protocols.reviewed(curated.load()) if p["id"] == pid), None)
    if not proto:
        raise ValueError("No reviewed protocol with that id.")
    pair = next(((st, src) for st, src in quizwriter.sources_of(proto) if src["url"] == link.strip()), None)
    if not pair:
        raise ValueError("That link isn't one of this protocol's sources: questions must come from one of them.")
    step, source = pair
    with requests.Session() as s:
        text = quizwriter._page_text(source["url"], session or s)
    if len(text) < 400:
        raise ValueError("The source page gave no usable text to check the quotes against.")
    state = quizwriter.load()
    old = state["batches"].get(pid) or {}
    kept = list(old.get("questions") or []) if old and not old.get("verdict") else []
    texts = [q["q"] for q in quiz.bank()["questions"] if q["protocol"] == pid] + [q["q"] for q in kept]
    dropped: list[tuple[str, str]] = []
    rows = _rows(extract_json(answer), "questions")
    before = len(kept)
    for raw in rows:
        quizwriter.keep_one(raw, proto, step, source, text, None, texts, kept, dropped)
    batch = {"questions": kept, "dropped": dropped, "spot_check": quizwriter.spot_check(kept), "asked": 0}
    quizwriter.keep_batch(pid, batch)
    return {"added": len(kept) - before, "dropped": len(dropped), "why": [f"{q}: {w}" for w, q in dropped[:10]],
            "found": len(rows)}


def import_answer(kind: str, answer: str, link: str = "", text: str = "", pid: str = "",
                  today: date | None = None, session=None) -> dict[str, Any]:
    """Check a pasted answer and queue what passes. {"added", "dropped", "why", "found"} or {"error"}."""
    try:
        if kind == "highlight":
            return import_highlights(answer, link, text, session)
        if kind in ("jobs", "funding", "conferences"):
            return import_listings(kind, answer, link, text, today)
        if kind == "quiz":
            return import_quiz(answer, pid, link, session)
        return {"error": f"kind must be one of {list(KINDS)}"}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:                       # a network failure, said plainly
        from .errors import describe
        return {"error": f"Couldn't finish: {describe(exc)}"}
