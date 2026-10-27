"""📰 What's new: the AI and technology news the maker accepted from TRACE (trace.py), published in curated.json's
"whatsnew" list and shown first in News on both apps (the phone's lib/whatsnew-shape.ts checks it the same way).

Everything in the published file is checked again when it's read, as untrusted input: text is plain and capped,
links are https with nothing hidden before the host, an item older than KEEP_DAYS is dropped, and at most KEEP are
kept, newest first.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

from .curated import _https, _text, _words

KEEP = 40
KEEP_DAYS = 30
_ID = re.compile(r"^tr-[a-f0-9]{8,32}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean(raw: Any, today: date | None = None) -> dict[str, Any] | None:
    """One item checked and trimmed, or None if it can't be shown."""
    if not isinstance(raw, dict) or not _ID.match(str(raw.get("id", ""))):
        return None
    added = str(raw.get("added", ""))[:10]
    if not _DAY.match(added):
        return None
    try:
        if date.fromisoformat(added) < (today or date.today()) - timedelta(days=KEEP_DAYS):
            return None
    except ValueError:
        return None
    title, url = _text(raw.get("title"), 140), _https(raw.get("url"))
    if not title or not url:
        return None
    sources = [u for u in (_https(s) for s in (raw.get("sources") or [])[:8] if isinstance(s, str)) if u]
    return {"id": raw["id"], "title": title, "summary": _text(raw.get("summary"), 400), "why": _text(raw.get("why"), 200),
            "url": url, "sources": list(dict.fromkeys([url] + sources))[:8], "topic": _text(raw.get("topic"), 40).lower(),
            "keywords": _words(raw.get("keywords")), "added": added}


def clean_all(raw: Any, today: date | None = None) -> list[dict[str, Any]]:
    """What's new to show: checked, one per id, newest first, at most KEEP."""
    seen: set[str] = set()
    out = []
    for r in (raw if isinstance(raw, list) else [])[:200]:
        it = clean(r, today)
        if it and it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    out.sort(key=lambda it: (it["added"], it["id"]), reverse=True)
    return out[:KEEP]


def merge(data: dict[str, Any], items: list[dict[str, Any]], today: date | None = None) -> tuple[dict[str, Any], int]:
    """The curated file with these items added (checked again first). (file, how many were new)."""
    import json
    out = json.loads(json.dumps(data))
    have = clean_all(out.get("whatsnew"), today)
    ids = {h["id"] for h in have}
    added = 0
    for it in items:
        c = clean(it, today)
        if c and c["id"] not in ids and not any(h["url"] == c["url"] for h in have):
            have.append(c)
            ids.add(c["id"])
            added += 1
    out["whatsnew"] = clean_all(have, today)
    return out, added


def ranked(items: list[dict[str, Any]], weights: dict[str, float], today: date | None = None) -> list[dict[str, Any]]:
    """Newest first, nudged by how well each fits your field (your profile's weighted words): a match counts like
    being two days newer."""
    today = today or date.today()

    def score(it: dict[str, Any]) -> float:
        age = (today - date.fromisoformat(it["added"])).days
        text = " ".join([it["title"], it["summary"], it["topic"], " ".join(it["keywords"])]).lower()
        fit = sum(w for k, w in weights.items() if k and k.lower() in text)
        return -age + 2 * min(1.0, fit)
    return sorted(items, key=score, reverse=True)
