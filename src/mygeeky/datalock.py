"""Your saved data, locked: every file myGeeKy keeps in your storage (Google Drive or a GitHub repo) is encrypted on
the device first, so the storage holds only unreadable bytes. The phone does the same (mobile/src/lib/data-lock.ts),
byte for byte, so either reads what the other wrote.

One key per person (32 random bytes), made on the first device and kept in its keyring; the other devices get it from
the "Connect your phone" QR code or the recovery code. Lose every device and the code, and the data can't be read.

A locked file:

    b"MGK1" | nonce (12 random bytes) | ChaCha20-Poly1305(key, nonce, raw deflate(plaintext), AAD = LABEL + name)

The name in the AAD ties the bytes to their file, so a file can't be passed off as another one.

What's in the storage (docs/STORAGE.md):

    mygeeky.json                                   plain: which key the files are locked with (its id, never the key)
    config.synced.json.mgk                         a state file: the latest copy wins
    interest_events.2026-10.d3f1a2b4.jsonl.mgk     a log, split by month and by the device that wrote it

Each device writes only its own log files, so two devices never write the same file at once, and a sync moves only
this month's small file, not the whole history.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zlib
from typing import Iterable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

MAGIC = b"MGK1"
LABEL = b"mygeeky-data-v1:"
SUFFIX = ".mgk"
FORMAT_FILE = "mygeeky.json"
UNDATED = "0000-00"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CODE_LEN = 56                                  # 32 key bytes + 3 check bytes = 280 bits = 56 letters
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
_LOG = re.compile(r"^(?P<stem>[A-Za-z0-9_-]{1,60})\.(?P<month>\d{4}-\d{2})\.(?P<dev>[0-9a-f]{8})\.jsonl$")
_MONTH = re.compile(r"^(\d{4}-\d{2})")


def new_key() -> bytes:
    return os.urandom(32)


def new_device_id() -> str:
    return os.urandom(4).hex()


def key_id(key: bytes) -> str:
    """A short name for the key that gives nothing away: two devices with the same id have the same key."""
    return hashlib.sha256(b"mygeeky-key-id:" + key).hexdigest()[:16]


def _deflate(data: bytes) -> bytes:
    c = zlib.compressobj(6, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def _inflate(data: bytes, limit: int = 256 * 1024 * 1024) -> bytes:
    d = zlib.decompressobj(-15)
    out = d.decompress(data, limit)
    if d.unconsumed_tail:
        raise ValueError("too big")
    return out + d.flush()


def seal(key: bytes, name: str, plaintext: bytes) -> bytes:
    nonce = os.urandom(12)
    return MAGIC + nonce + ChaCha20Poly1305(key).encrypt(nonce, _deflate(plaintext), LABEL + name.encode("ascii"))


def open_sealed(key: bytes, name: str, blob: bytes) -> bytes | None:
    """The plaintext, or None if this isn't a locked file, it was locked with another key, or it was changed."""
    if not is_sealed(blob) or len(blob) < 4 + 12 + 16:
        return None
    try:
        return _inflate(ChaCha20Poly1305(key).decrypt(blob[4:16], blob[16:], LABEL + name.encode("ascii")))
    except (InvalidTag, ValueError, zlib.error):
        return None


def is_sealed(blob: bytes) -> bool:
    return blob[:4] == MAGIC


# ---- the recovery code: the key, written out to keep on paper
def _b32(data: bytes) -> str:
    bits = int.from_bytes(data, "big")
    n = len(data) * 8 // 5
    return "".join(CROCKFORD[(bits >> (5 * (n - 1 - i))) & 31] for i in range(n))


def _check(key: bytes) -> bytes:
    return hashlib.sha256(b"mygeeky-recovery:" + key).digest()[:3]


def recovery_code(key: bytes) -> str:
    """56 letters and digits in groups of four, e.g. 7K2M-…; easy to read aloud (no I, L, O or U)."""
    text = _b32(key + _check(key))
    return "-".join(text[i:i + 4] for i in range(0, len(text), 4))


def key_from_code(text: object) -> bytes | None:
    """The key a recovery code holds, or None if it's mistyped (its last letters check the rest)."""
    if not isinstance(text, str):
        return None
    s = re.sub(r"[\s-]", "", text.upper()).translate(str.maketrans("OIL", "011"))
    if len(s) != CODE_LEN or any(c not in CROCKFORD for c in s):
        return None
    bits = 0
    for c in s:
        bits = (bits << 5) | CROCKFORD.index(c)
    raw = bits.to_bytes(35, "big")
    key, check = raw[:32], raw[32:]
    return key if _check(key) == check else None


# ---- what goes where
def format_doc(key: bytes) -> bytes:
    return json.dumps({"format": 2, "key": key_id(key), "app": "myGeeKy",
                       "note": "Your myGeeKy data, encrypted on your devices. Only your devices can read it."},
                      indent=1).encode("utf-8")


def format_key_id(text: bytes | str | None) -> str | None:
    """The key id a storage's mygeeky.json names, or None (no file, or not ours)."""
    try:
        doc = json.loads(text or "null")
    except (ValueError, TypeError):
        return None
    kid = doc.get("key") if isinstance(doc, dict) and doc.get("format") == 2 else None
    return kid if isinstance(kid, str) and re.fullmatch(r"[0-9a-f]{16}", kid) else None


def moved_to(text: bytes | str | None) -> str | None:
    """Where another device moved the data ("drive" or "github:owner/name"), as a storage's mygeeky.json says."""
    try:
        doc = json.loads(text or "null")
    except (ValueError, TypeError):
        return None
    m = doc.get("moved_to") if isinstance(doc, dict) else None
    ok = isinstance(m, str) and re.fullmatch(r"drive|github:[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}", m)
    return m if ok else None


def valid_name(name: str) -> bool:
    return bool(_NAME.match(name)) and ".." not in name


def is_log(name: str) -> bool:
    return name.endswith(".jsonl")


def log_chunk(stem: str, month: str, device: str) -> str:
    return f"{stem}.{month}.{device}.jsonl"


def parse_stored(stored: str) -> dict | None:
    """What a stored file is: {"kind": "state", "name"} or {"kind": "log", "stem", "month", "device", "name"};
    None for anything else (mygeeky.json, someone else's file, a name that isn't safe)."""
    if not stored.endswith(SUFFIX):
        return None
    name = stored[:-len(SUFFIX)]
    if not valid_name(name):
        return None
    m = _LOG.match(name)
    if m:
        return {"kind": "log", "name": name, "stem": m["stem"], "month": m["month"], "device": m["dev"]}
    if is_log(name):
        return None
    return {"kind": "state", "name": name}


def month_of(line: str) -> str:
    """The month a log line belongs to, from its time ("at", "timestamp"...); UNDATED if it has none."""
    try:
        rec = json.loads(line)
    except ValueError:
        return UNDATED
    if isinstance(rec, dict):
        for k in ("at", "timestamp", "time", "date", "ts"):
            v = rec.get(k)
            if isinstance(v, str):
                m = _MONTH.match(v)
                if m and "1970-01" <= m[1] <= "2999-12":
                    return m[1]
    return UNDATED


def lines_of(text: str) -> list[str]:
    return [line for line in re.split(r"\r\n|\r|\n", text) if line.strip()]


def by_month(lines: Iterable[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for line in lines:
        out.setdefault(month_of(line), []).append(line)
    return out


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
