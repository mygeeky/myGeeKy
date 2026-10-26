"""Locked data (datalock.py, the phone's lib/data-lock.ts): what one device locks, only a device with the same key can
open, the phone and the computer read each other's files, and the recovery code gives the key back."""
from __future__ import annotations

import base64

import pytest

import phone
from mygeeky import datalock as dl

KEY = bytes(range(32))


def test_a_locked_file_opens_only_with_its_key_and_its_name():
    blob = dl.seal(KEY, "cv_text.txt", b"my whole CV " * 200)
    assert dl.is_sealed(blob) and b"CV" not in blob and len(blob) < 400          # compressed before it's locked
    assert dl.open_sealed(KEY, "cv_text.txt", blob) == b"my whole CV " * 200
    assert dl.open_sealed(bytes(32), "cv_text.txt", blob) is None                # another key
    assert dl.open_sealed(KEY, "config.synced.json", blob) is None               # passed off as another file
    assert dl.open_sealed(KEY, "cv_text.txt", blob[:-1] + bytes([blob[-1] ^ 1])) is None
    assert dl.open_sealed(KEY, "cv_text.txt", b"{plain json}") is None
    assert dl.seal(KEY, "a", b"x") != dl.seal(KEY, "a", b"x")                    # a fresh nonce every time


def test_the_recovery_code_gives_the_key_back_and_catches_typos():
    code = dl.recovery_code(KEY)
    assert len(code) == 56 + 13 and code.count("-") == 13 and not set("ILOU") & set(code)
    assert dl.key_from_code(code) == KEY
    assert dl.key_from_code(code.lower().replace("-", " ")) == KEY
    assert dl.key_from_code(code.replace("0", "O").replace("1", "l")) == KEY      # read aloud, written down
    wrong = ("Z" if code[5] != "Z" else "Y").join([code[:5], code[6:]])
    assert dl.key_from_code(wrong) is None and dl.key_from_code("") is None and dl.key_from_code(None) is None


def test_names_say_what_a_stored_file_is():
    assert dl.parse_stored("config.synced.json.mgk") == {"kind": "state", "name": "config.synced.json"}
    log = dl.parse_stored("interest_events.2026-10.d3f1a2b4.jsonl.mgk")
    assert log == {"kind": "log", "name": "interest_events.2026-10.d3f1a2b4.jsonl", "stem": "interest_events",
                   "month": "2026-10", "device": "d3f1a2b4"}
    for bad in ("mygeeky.json", "x.json", "../x.json.mgk", "usage.jsonl.mgk", ".git.mgk", "a b.mgk"):
        assert dl.parse_stored(bad) is None
    assert dl.month_of('{"at": "2026-10-26T10:00:00+00:00"}') == "2026-10"
    assert dl.month_of('{"timestamp": "2025-01-02"}') == "2025-01"
    assert dl.month_of("not json") == dl.month_of('{"x": 1}') == dl.UNDATED
    assert dl.format_key_id(dl.format_doc(KEY)) == dl.key_id(KEY)
    assert dl.format_key_id(b"{}") is None and dl.format_key_id(None) is None


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_and_the_computer_read_each_others_files():
    text = "naïve café ☕ " * 50 + "\n" + '{"at": "2026-10-01T00:00:00+00:00", "kind": "paper"}'
    mine = base64.b64encode(dl.seal(KEY, "cv_text.txt", text.encode())).decode()
    said = phone.run("""
import * as L from './lib/data-lock.ts';
import { b64, unb64 } from './lib/signal-crypto.ts';
const key = Uint8Array.from(INPUT.key);
const theirs = L.sealText(key, 'usage.2026-10.0a0b0c0d.jsonl', INPUT.text);
out({
  opened: L.openText(key, 'cv_text.txt', unb64(INPUT.mine)!),
  wrongName: L.openText(key, 'other.txt', unb64(INPUT.mine)!),
  theirs: b64(theirs),
  code: L.recoveryCode(key), back: Array.from(L.keyFromCode(INPUT.code)!), id: L.keyId(key),
  stored: ['config.synced.json.mgk', 'interest_events.2026-10.d3f1a2b4.jsonl.mgk', 'usage.jsonl.mgk', 'mygeeky.json'].map(L.parseStored),
  months: INPUT.lines.map(L.monthOf),
  fmt: L.formatKeyId(L.formatDoc(key)),
  lines: L.linesOf('a\\r\\nb\\n\\nc\\rd'),
});
""", {"key": list(KEY), "text": text, "mine": mine, "code": dl.recovery_code(KEY).lower(),
      "lines": ['{"at": "2026-10-26"}', '{"timestamp": "2025-01-02x"}', "nope", '{"at": "0000-01"}']})
    assert said["opened"] == text and said["wrongName"] is None
    assert dl.open_sealed(KEY, "usage.2026-10.0a0b0c0d.jsonl", base64.b64decode(said["theirs"])).decode() == text
    assert said["code"] == dl.recovery_code(KEY) and bytes(said["back"]) == KEY and said["id"] == dl.key_id(KEY)
    assert said["stored"] == [dl.parse_stored(n) for n in ("config.synced.json.mgk",
                              "interest_events.2026-10.d3f1a2b4.jsonl.mgk", "usage.jsonl.mgk", "mygeeky.json")]
    assert said["months"] == [dl.month_of(x) for x in ['{"at": "2026-10-26"}', '{"timestamp": "2025-01-02x"}', "nope",
                                                        '{"at": "0000-01"}']]
    assert said["fmt"] == dl.key_id(KEY) and said["lines"] == dl.lines_of("a\r\nb\n\nc\rd")
