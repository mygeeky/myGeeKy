"""Drop a CV, thesis or abstract: find your field's keywords, your methods and tools, and your co-authors.

Everything happens on this computer; the document is never sent anywhere, and only the words you keep are saved.
Keywords are the keyword dictionary's topics found in the text (a single word must come up a few times in a long
document, and the start of the document -- title, abstract -- counts more). Methods and tools come from a short
list (data/docread.json). Co-authors are names that sit next to others in author lists ("Smith J, Doe A", "J. Smith
and A. Doe", "Smith, J."); the most frequent one is you, unless your name is given.

The phone does the same (lib/doc-read.ts, with an identical data/docread.json); tests/test_docread.py runs both
on the same texts.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

DATA = Path(__file__).parent / "data" / "docread.json"
HEAD_WORDS = 250          # the title and abstract: what's found here counts more
SHORT_WORDS = 800         # an abstract or a proposal: one mention of a topic is enough
MAX_GRAM = 4
KEYWORDS, METHODS, COAUTHORS = 15, 12, 10

_rules: dict[str, Any] | None = None


def rules() -> dict[str, Any]:
    global _rules
    if _rules is None:
        _rules = json.loads(DATA.read_text(encoding="utf-8"))
    return _rules


def norm(s: str) -> str:
    """Lowercase ASCII words: 'Single-cell RNA-seq, Ölçer' -> 'single cell rna seq olcer' (+ and # stay, for C++)."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9+#]+", " ", s).split())


def _grams(tokens: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for n in range(1, MAX_GRAM + 1):
        for i in range(len(tokens) - n + 1):
            g = " ".join(tokens[i:i + n])
            out[g] = out.get(g, 0) + 1
    return out


def _covered(tokens: list[str], phrases: Iterable[str]) -> set[int]:
    """The positions inside any of these phrases (two words or more), wherever they occur."""
    out: set[int] = set()
    for ph in {p for p in phrases if " " in p}:
        words = ph.split()
        n = len(words)
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == words:
                out.update(range(i, i + n))
    return out


def find_keywords(tokens: list[str], vocabulary: Iterable[str], skip: set[str],
                  inside: Iterable[str] = ()) -> list[str]:
    """`skip`: forms that are methods, not topics. `inside`: the forms of the methods found. A single word counts
    only where it stands on its own: "rna" inside RNA-seq, or "genetics" inside "statistical genetics", doesn't."""
    r = rules()
    ignore, headings = set(r["ignore"]), set(r["headings"])
    grams, head = _grams(tokens), _grams(tokens[:HEAD_WORDS])
    short = len(tokens) < SHORT_WORDS
    labels: dict[str, str] = {}
    for label in sorted(vocabulary, key=lambda w: (norm(w), w)):
        t = norm(label)
        if t and len(t) > 1 and t not in labels and t not in ignore and t not in skip and t.count(" ") < MAX_GRAM:
            labels[t] = label
    scored = []
    phrases = [t for t in labels if " " in t and grams.get(t, 0)]
    for t in phrases:
        scored.append((-(grams[t] + 2 * head.get(t, 0)) * (1 + 0.5 * (t.count(" "))), t))
    covered = _covered(tokens, phrases + [norm(m) for m in inside])
    alone: dict[str, int] = {}
    alone_head: dict[str, int] = {}
    for i, w in enumerate(tokens):
        if i not in covered:
            alone[w] = alone.get(w, 0) + 1
            if i < HEAD_WORDS:
                alone_head[w] = alone_head.get(w, 0) + 1
    for t in labels:
        if " " in t or not alone.get(t, 0):
            continue
        need = (2 if short else 4) if t in headings else (1 if short else 2)
        if alone[t] >= need:
            scored.append((-(alone[t] + 2 * alone_head.get(t, 0)), t))
    scored.sort()
    return [labels[t] for _, t in scored[:KEYWORDS]]


def find_methods(text: str, tokens: list[str]) -> list[str]:
    grams = _grams(tokens)
    have = set(tokens)
    raw = re.split(r"[^A-Za-z0-9+#]+", text)
    found = []
    for m in rules()["methods"]:
        if m.get("needs") and not any(w in have for w in m["needs"]):
            continue
        if m.get("exact"):                 # R, SAS, Java: as written, and at least twice
            c = sum(1 for w in raw if w == m["name"])
            if c < 2:
                continue
        else:
            c = sum(grams.get(norm(n), 0) for n in [m["name"], *(m.get("also") or [])])
            if c < 1:
                continue
        found.append((-c, m["name"]))
    found.sort()
    return [name for _, name in found[:METHODS]]


_SURNAME = r"[A-Z][a-z]+(?:-[A-Z][a-z]+)?"
_NAME = re.compile(
    rf"\b({_SURNAME}),\s?([A-Z])\.(?:\s?[A-Z]\.)*"                 # Smith, J.   Smith, J. A.
    rf"|\b([A-Z])\.(?:\s?[A-Z]\.)*\s({_SURNAME})\b"                # J. Smith    J.A. Smith
    rf"|\b({_SURNAME})\s([A-Z]{{1,3}})\b(?=[,;.]|\s(?:and|&)\s|$)",  # Smith J,   Smith JA.
    re.ASCII)                              # word edges as the phone sees them (ASCII), so both find the same


_WRAPPED = re.compile(r"(,|&|\band|\b[A-Z]\.)[ ]*\r?\n", re.ASCII)
_SPACES = re.compile("[\t\u00a0\u2000-\u200b\u202f\u205f\u3000]")


def _plain(s: str) -> str:
    """Accents off and odd spaces (a PDF's no-break spaces) plain: 'Müller\u00a0J' -> 'Muller J'."""
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return _SPACES.sub(" ", s)


def _key_of_name(name: str) -> tuple[str, str] | None:
    words = norm(name).split()
    return (words[-1], words[0][0].upper()) if len(words) >= 2 else None


def find_coauthors(text: str, own_name: str = "") -> list[str]:
    counts: dict[tuple[str, str], int] = {}
    shown: dict[tuple[str, str], str] = {}
    # an author list wrapped onto the next line is one list: join after a comma, "&", "and" or a lone initial
    joined = _WRAPPED.sub(r"\1 ", _plain(text))
    for line in joined.split("\n"):
        names = []
        for m in _NAME.finditer(line):
            surname, initial = (m.group(1), m.group(2)) if m.group(1) else \
                (m.group(4), m.group(3)) if m.group(4) else (m.group(5), m.group(6)[0])
            names.append((surname, initial))
        if len(names) < 2:                 # an author list has several names on one line
            continue
        for surname, initial in names:
            key = (surname.lower(), initial)
            counts[key] = counts.get(key, 0) + 1
            shown.setdefault(key, f"{initial}. {surname}")
    me = _key_of_name(own_name) if own_name else None
    if me is None and counts:              # you: the name on most lists, if it clearly leads
        top = sorted(counts.items(), key=lambda kv: (-kv[1], shown[kv[0]]))
        if top[0][1] >= 3 and (len(top) == 1 or top[0][1] > top[1][1]):
            me = top[0][0]
    rows = sorted(((-c, shown[k]) for k, c in counts.items() if k != me))
    return [name for _, name in rows[:COAUTHORS]]


def read(text: str, vocabulary: Iterable[str], own_name: str = "") -> dict[str, Any]:
    """{"keywords", "methods", "coauthors", "words"} found in a document's text."""
    text = str(text or "")
    tokens = norm(text).split()
    methods = find_methods(text, tokens)
    skip = {norm(n) for m in rules()["methods"] for n in [m["name"], *(m.get("also") or [])]}
    found = [n for m in rules()["methods"] if m["name"] in methods for n in [m["name"], *(m.get("also") or [])]]
    return {"keywords": find_keywords(tokens, vocabulary, skip, found), "methods": methods,
            "coauthors": find_coauthors(text, own_name), "words": len(tokens)}


def vocabulary() -> list[str]:
    """The dictionary's topics, as you'd write them (the phone reads the same from data/field-words.json)."""
    from . import keywords
    return list(keywords.phone_words(keywords.load())["related"])


def read_document(text: str, own_name: str = "") -> dict[str, Any]:
    return read(text, vocabulary(), own_name)


def read_from(path: str = "", text: str = "", own_name: str = "") -> dict[str, Any]:
    """A file (or pasted text) to {"ok": True, "found": ...}, or {"ok": False, "error": what to do instead}."""
    from .text_utils import load_cv_text
    try:
        text = load_cv_text(path) if path else str(text or "")
    except Exception as exc:
        return {"ok": False, "error": f"This file couldn't be read ({exc}). Try a PDF or .docx, or paste the text."}
    found = read_document(text, own_name)
    if not (found["keywords"] or found["methods"] or found["coauthors"]):
        return {"ok": False, "error": "Nothing from the dictionary turned up in it. Try your CV or an abstract, or "
                                      "type a few keywords."}
    return {"ok": True, "found": found}


def merge_words(have: Iterable[str], add: Iterable[str]) -> list[str]:
    """What you have, then the new words you kept, without the same word twice ("Single-cell" = "single cell")."""
    seen: set[str] = set()
    out = []
    for w in [*have, *add]:
        k = norm(w)
        if k and k not in seen:
            seen.add(k)
            out.append(w)
    return out
