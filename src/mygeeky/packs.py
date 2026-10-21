"""📦 Packs: share your setup like a seed, in one to three QR codes.

A pack is a small part of your setup someone else can start from: your keywords, topics and research field, the
researchers you follow (Circle → Researchers) and a short note ("Plant genomics lab, 2026"). You choose what goes in;
nothing else ever does (no tokens, no account, no Model).

It travels only as QR codes, shown on the screen and scanned by the other person's phone, with no internet and no
server. The pack is compressed and, when it doesn't fit one code, cut into up to MAX_CODES parts. Every code says
which pack it belongs to, which part it is and how many there are:

    mygeeky-pack:1:<pack id>:<part>/<parts>:<piece>

so the receiver knows from the first scan how many codes to expect, counts them in any order and asks for the next.
The pack id is the CRC-32 of the compressed pack, so a mixed-up or damaged set is never imported. The phone makes,
shows and receives packs (lib/packs.ts); this computer makes and shows them (it has no camera to scan with).
tests/test_packs.py checks both read each other's codes.

A pack is untrusted data: every field is checked and trimmed on arrival, and nothing in it can run.
"""

from __future__ import annotations

import base64
import json
import re
import zlib
from typing import Any

PREFIX = "mygeeky-pack:1:"
CHUNK = 700                      # characters per code: dense codes are hard to scan off a screen
MAX_CODES = 3
MAX_WORDS, MAX_FIELD, MAX_PEOPLE, MAX_NOTE = 40, 8, 30, 120
_AID = re.compile(r"^A\d{2,12}$")
_PART = re.compile(r"^mygeeky-pack:1:([0-9a-f]{8}):(\d)/(\d):([A-Za-z0-9_-]+)$")


def _words(v: Any, n: int = MAX_WORDS, length: int = 80) -> list[str]:
    out: list[str] = []
    for x in v if isinstance(v, list) else []:
        if isinstance(x, str) and x.strip() and x.strip()[:length] not in out:
            out.append(x.strip()[:length])
    return out[:n]


def clean(raw: Any) -> dict[str, Any]:
    """A pack with every field checked: what arrives from someone else, or what's about to be shared."""
    raw = raw if isinstance(raw, dict) else {}
    people = []
    for p in raw.get("r") if isinstance(raw.get("r"), list) else []:
        if isinstance(p, list) and len(p) >= 2 and isinstance(p[0], str) and _AID.match(p[0]) and isinstance(p[1], str):
            if all(q[0] != p[0] for q in people):
                people.append([p[0], p[1].strip()[:120]])
    note = raw.get("n") if isinstance(raw.get("n"), str) else ""
    return {"v": 1, "n": " ".join(note.split())[:MAX_NOTE], "k": _words(raw.get("k")), "t": _words(raw.get("t")),
            "f": _words(raw.get("f"), MAX_FIELD), "r": people[:MAX_PEOPLE]}


def make(cfg: Any, parts: set[str], note: str = "", following: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """A pack from your setup: `parts` is what you ticked ("words" = keywords and topics, "field", "people")."""
    field: list[str] = []
    if "field" in parts:
        try:
            from .gui import app as logic
            field = list(logic.get_brain(cfg).get("field", []))
        except Exception:
            field = list(getattr(cfg, "field", []) or [])
    return clean({"n": note, "k": list(cfg.keywords) if "words" in parts else [],
                  "t": list(cfg.topics) if "words" in parts else [], "f": field,
                  "r": [[p.get("id", ""), p.get("name", "")] for p in following or []] if "people" in parts else []})


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def codes(pack: dict[str, Any]) -> list[str]:
    """The pack as QR texts, one per code ([] when it's too big for MAX_CODES)."""
    raw = zlib.compress(json.dumps(clean(pack), separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)
    body, pid = _b64(raw), f"{zlib.crc32(raw):08x}"
    n = -(-len(body) // CHUNK)
    if n > MAX_CODES:
        return []
    size = -(-len(body) // n)                          # equal pieces: every code is as easy to scan as the others
    return [f"{PREFIX}{pid}:{i + 1}/{n}:{body[i * size:(i + 1) * size]}" for i in range(n)]


def part(text: str) -> dict[str, Any] | None:
    """One scanned code: {id, i, n, piece}, or None if it isn't a pack code."""
    m = _PART.match(text.strip()) if isinstance(text, str) else None
    if not m:
        return None
    i, n = int(m.group(2)), int(m.group(3))
    return {"id": m.group(1), "i": i, "n": n, "piece": m.group(4)} if 1 <= i <= n <= MAX_CODES else None


def assemble(pieces: dict[int, str], pid: str) -> dict[str, Any] | None:
    """The pack from all its pieces (1..n), or None if one is missing, damaged or from another pack."""
    try:
        raw = _unb64("".join(pieces[i] for i in sorted(pieces)))
        if f"{zlib.crc32(raw):08x}" != pid:
            return None
        d = zlib.decompressobj()
        text = d.decompress(raw, 64_000)                # a pack is small: refuse anything that inflates past this
        if d.unconsumed_tail:
            return None
        return clean(json.loads(text.decode("utf-8")))
    except Exception:
        return None


def describe(pack: dict[str, Any]) -> str:
    """What a pack holds, in one plain line."""
    bits = []
    if pack["k"] or pack["t"]:
        n = len(pack["k"]) + len(pack["t"])
        bits.append(f"{n} keywords and topics" if n != 1 else "1 keyword")
    if pack["f"]:
        bits.append("a research field")
    if pack["r"]:
        bits.append(f"{len(pack['r'])} researcher{'s' if len(pack['r']) != 1 else ''} to follow")
    return ", ".join(bits) or "nothing yet"


def apply(mine: dict[str, Any], pack: dict[str, Any], how: str) -> dict[str, Any]:
    """Your keywords/topics/field after importing: "merge" only adds, "start" starts from the pack's (your other
    settings are untouched either way). The phone does this (lib/packs.ts applyPack); kept here so the rule is one."""
    out = dict(mine)
    for key, src in (("keywords", "k"), ("topics", "t"), ("field", "f")):
        have = list(mine.get(key) or [])
        if how == "start" and pack[src]:
            out[key] = list(pack[src])
        else:
            low = {x.lower() for x in have}
            out[key] = have + [x for x in pack[src] if x.lower() not in low]
    return out
