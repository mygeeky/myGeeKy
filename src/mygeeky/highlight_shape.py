"""What a Highlight is, and how one is read safely from the curated lists: a research article (later news or
an AI model) retold as a short science news article -- a headline, a standfirst and a few paragraphs, each
carrying one idea -- by the maker, in every language myGeeKy offers.

A Highlight comes from the maker's admin tab (highlights.py, with the article skill in
data/article_skill.md) and reaches everyone with the curated lists (curated.py). Here it is only checked
and trimmed, the same way on the phone (lib/highlight-shape.ts; tests/test_highlights.py runs both): a
damaged or partial entry is dropped or trimmed, never shown half-broken.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

KINDS = ("article",)                                        # news and models come later, with their own skill
COVERAGE = ("full", "abstract")
KEEP = 60                                                   # the newest this many are shown
PARAGRAPHS = 9                                              # at most, each one idea
PARAGRAPH_MAX = 900
MIN_PARAGRAPHS = 3
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,79}$")
_DOI = re.compile(r"^10\.\d{4,9}/\S{1,200}$")
_CODE = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# The few words around a story, in each language the stories are written in (the stories carry their own
# translations; these are only the button and the line saying what the story was written from).
LABELS: dict[str, dict[str, str]] = {
    "en": {"read": "Read the article", "full": "From the full article", "abstract": "From the abstract only",
           "learn": "Learn these tools"},
    "ar": {"read": "اقرأ المقال", "full": "من المقال كاملًا", "abstract": "من الملخص فقط", "learn": "تعلّم هذه الأدوات"},
    "fr": {"read": "Lire l'article", "full": "D'après l'article complet", "abstract": "D'après le résumé seulement",
           "learn": "Apprendre ces outils"},
    "de": {"read": "Den Artikel lesen", "full": "Aus dem ganzen Artikel", "abstract": "Nur aus der Zusammenfassung",
           "learn": "Diese Werkzeuge lernen"},
    "es": {"read": "Leer el artículo", "full": "Del artículo completo", "abstract": "Solo del resumen",
           "learn": "Aprender estas herramientas"},
    "zh": {"read": "阅读文章", "full": "根据全文", "abstract": "仅根据摘要", "learn": "学习这些工具"},
}
NAMES = {"ar": ("العربية", True), "fr": ("Français", False), "de": ("Deutsch", False), "es": ("Español", False),
         "zh": ("中文", False)}


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


def _names(values: Any, n: int, size: int) -> list[str]:
    """A short list of names as written (people, institutions, tools): case kept, repeats dropped."""
    out: list[str] = []
    for v in values if isinstance(values, list) else []:
        t = _text(v, size)
        if t and t.lower() not in (o.lower() for o in out):
            out.append(t)
    return out[:n]


def _words(values: Any, n: int) -> list[str]:
    return [w.lower() for w in _names(values, n, 40)]


def _body(raw: Any) -> list[str]:
    """The article's paragraphs: text only, empty ones dropped, at most PARAGRAPHS."""
    return [t for t in (_text(p, PARAGRAPH_MAX) for p in (raw if isinstance(raw, list) else [])[:PARAGRAPHS * 2]) if t][:PARAGRAPHS]


def clean_translations(raw: Any) -> dict[str, dict[str, Any]]:
    """{code: {"name", "rtl", "title", "hook", "body"}}: a story said again in another language.
    One without a title is left out; the English story is never touched by a bad translation."""
    out: dict[str, dict[str, Any]] = {}
    for code, val in list(raw.items())[:20] if isinstance(raw, dict) else []:
        code = str(code).strip().lower()
        if not _CODE.match(code) or not isinstance(val, dict):
            continue
        known = NAMES.get(code)
        name = _text(val.get("name"), 30) or (known[0] if known else "")
        title = _text(val.get("title"), 140)
        if not name or not title:
            continue
        out[code] = {"name": name, "rtl": bool(val.get("rtl", known[1] if known else False)), "title": title,
                     "hook": _text(val.get("hook"), 220), "body": _body(val.get("body"))}
    return out


def clean(raw: Any) -> dict[str, Any] | None:
    """One Highlight checked and trimmed, or None if it can't be shown."""
    if not isinstance(raw, dict) or not _ID.match(str(raw.get("id", ""))):
        return None
    kind = str(raw.get("kind", "article"))
    body = _body(raw.get("body"))
    item = {"id": raw["id"], "kind": kind if kind in KINDS else "article", "title": _text(raw.get("title"), 140),
            "hook": _text(raw.get("hook"), 220), "url": _https(raw.get("url")), "added": _day(raw.get("added")),
            "coverage": raw.get("coverage") if raw.get("coverage") in COVERAGE else "abstract",
            "body": body}
    if not item["title"] or not item["url"] or not item["added"] or len(body) < MIN_PARAGRAPHS:
        return None
    doi = _text(raw.get("doi"), 220)
    item["doi"] = doi if _DOI.match(doi) else ""
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    item["meta"] = {"journal": _text(meta.get("journal"), 120), "published": _day(meta.get("published")),
                    "lead": _text(meta.get("lead"), 100), "authors": _names(meta.get("authors"), 8, 80),
                    "institutions": _names(meta.get("institutions"), 8, 120),
                    "countries": _names(meta.get("countries"), 12, 60),
                    "open_access": meta.get("open_access") is True}
    item["tools"] = _names(raw.get("tools"), 12, 60)
    item["skills"] = _words(raw.get("skills"), 6)
    item["keywords"] = _words(raw.get("keywords"), 8)
    said = clean_translations(raw.get("translations"))
    if said:
        item["translations"] = said
    return item


def clean_all(raw: Any) -> list[dict[str, Any]]:
    """The Highlights to show: checked, one per id, newest first, at most KEEP."""
    seen: set[str] = set()
    out = []
    for r in (raw if isinstance(raw, list) else [])[:300]:
        h = clean(r)
        if h and h["id"] not in seen:
            seen.add(h["id"])
            out.append(h)
    out.sort(key=lambda h: (h["added"], h["id"]), reverse=True)
    return out[:KEEP]


def problems(raw: Any) -> list[str]:
    """What's wrong with the file's Highlights, in plain words (empty: all good)."""
    out, ids = [], set()
    for i, r in enumerate(raw if isinstance(raw, list) else []):
        label = f"highlights '{r.get('id', i) if isinstance(r, dict) else i}'"
        if clean(r) is None:
            out.append(f"{label}: needs an id, a title, an https:// url, the date it was added and "
                       f"{MIN_PARAGRAPHS} paragraphs")
        elif r["id"] in ids:
            out.append(f"{label}: the same id appears twice")
        if isinstance(r, dict):
            ids.add(r.get("id"))
    return out


def read_in(item: dict[str, Any], code: str) -> dict[str, Any]:
    """The story in one language: its title, standfirst and paragraphs. A translation with a different number
    of paragraphs (they no longer line up) gives way to the English body."""
    tr = (item.get("translations") or {}).get(code) if code != "en" else None
    if not tr:
        return {"code": "en", "rtl": False, "title": item["title"], "hook": item["hook"], "body": item["body"],
                "labels": LABELS["en"]}
    body = tr["body"] if len(tr["body"]) == len(item["body"]) else item["body"]
    return {"code": code, "rtl": tr["rtl"], "title": tr["title"], "hook": tr.get("hook") or item["hook"],
            "body": body, "labels": LABELS.get(code, LABELS["en"])}


def languages(item: dict[str, Any]) -> list[tuple[str, str]]:
    """The languages a story can be read in: English first, then its translations in the order offered."""
    known = list(NAMES)
    tr = item.get("translations") or {}
    codes = sorted(tr, key=lambda c: (known.index(c) if c in known else 99, c))
    return [("en", "English")] + [(c, tr[c]["name"]) for c in codes]
