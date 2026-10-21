"""📦 Packs: one to three QR codes that carry part of your setup, read the same on the computer and the phone."""

import json
import random
import zlib

import pytest

from mygeeky import packs
from mygeeky.config import MyGeekyConfig
from tests import phone

SMALL = {"n": "Plant genomics lab, 2026", "k": ["gwas", "plant breeding"], "t": ["genomics"], "f": ["Plant genetics"],
         "r": [["A5000000001", "Ada Lovelace"]]}
BIG = {"n": "A class", "k": [f"keyword number {i} {random.Random(i).random():.6f}" for i in range(40)],
       "t": [f"topic {i} {random.Random(i + 99).random():.6f}" for i in range(20)], "f": ["Statistics"],
       "r": [[f"A50000{i:05d}", f"Researcher {i}"] for i in range(30)]}


def _all(codes):
    pieces, pid = {}, ""
    for c in codes:
        p = packs.part(c)
        pieces[p["i"]], pid = p["piece"], p["id"]
    return packs.assemble(pieces, pid)


def test_a_small_pack_is_one_code_and_comes_back_whole():
    codes = packs.codes(SMALL)
    assert len(codes) == 1 and codes[0].startswith("mygeeky-pack:1:") and ":1/1:" in codes[0]
    assert _all(codes) == packs.clean(SMALL) == {"v": 1, **SMALL}
    assert packs.describe(_all(codes)) == "3 keywords and topics, a research field, 1 researcher to follow"


def test_a_bigger_pack_is_cut_into_numbered_codes_of_equal_size():
    codes = packs.codes(BIG)
    assert 2 <= len(codes) <= 3
    n = len(codes)
    assert [packs.part(c)["i"] for c in codes] == list(range(1, n + 1)) and all(packs.part(c)["n"] == n for c in codes)
    assert len({packs.part(c)["id"] for c in codes}) == 1
    sizes = [len(packs.part(c)["piece"]) for c in codes]
    assert max(sizes) <= packs.CHUNK and max(sizes) - min(sizes) <= 1                  # each as easy to scan
    assert _all(list(reversed(codes))) == packs.clean(BIG)                             # any order


def test_too_much_for_three_codes_says_so():
    rnd = random.Random(3)
    long = lambda: "".join(rnd.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(80))   # noqa: E731
    huge = {"k": [long() for _ in range(40)], "t": [long() for _ in range(40)],
            "r": [[f"A5{random.Random(i).randrange(10 ** 9):09d}", f"{random.Random(i).random():.12f}"] for i in range(30)]}
    assert packs.codes(huge) == []


def test_a_pack_is_untrusted_data():
    dirty = {"n": "  a\n\nnote " + "x" * 300, "k": ["ok", 7, "", "ok", {"x": 1}, "y" * 200], "t": "not a list",
             "f": ["a"] * 3 + [f"f{i}" for i in range(20)], "r": [["A5000000001", "Ada"], ["not an id", "Eve"],
                                                                 ["A5000000001", "again"], "junk", ["A12"]],
             "tok": "ghp_secret", "u": "someone"}
    c = packs.clean(dirty)
    assert set(c) == {"v", "n", "k", "t", "f", "r"} and c["n"].startswith("a note x") and len(c["n"]) == packs.MAX_NOTE
    assert c["k"] == ["ok", "y" * 80] and c["t"] == [] and c["f"][:2] == ["a", "f0"] and len(c["f"]) == packs.MAX_FIELD
    assert c["r"] == [["A5000000001", "Ada"]]
    codes = packs.codes(BIG)
    p = packs.part(codes[0])
    tampered = {p["i"]: p["piece"][:-2] + ("AA" if p["piece"][-2:] != "AA" else "BB")}
    tampered.update({packs.part(x)["i"]: packs.part(x)["piece"] for x in codes[1:]})
    assert packs.assemble(tampered, p["id"]) is None                                   # damaged: never imported
    assert packs.part("mygeeky-pack:1:0000000z:1/1:abc") is None and packs.part("mygeeky-pack:1:00000000:4/4:abc") is None
    assert packs.part("mygeeky-pack:1:00000000:3/2:abc") is None and packs.part("https://example.org") is None
    bomb = zlib.compress(b'{"k":["' + b"a" * 200_000 + b'"]}', 9)
    import base64
    assert packs.assemble({1: base64.urlsafe_b64encode(bomb).decode().rstrip("=")}, f"{zlib.crc32(bomb):08x}") is None


def test_merge_only_adds_and_start_starts_from_the_pack():
    mine = {"keywords": ["GWAS", "rust"], "topics": [], "field": ["Genetics"], "username": "me"}
    pack = packs.clean(SMALL)
    assert packs.apply(mine, pack, "merge") == {"keywords": ["GWAS", "rust", "plant breeding"], "topics": ["genomics"],
                                                "field": ["Genetics", "Plant genetics"], "username": "me"}
    assert packs.apply(mine, pack, "start") == {"keywords": ["gwas", "plant breeding"], "topics": ["genomics"],
                                                "field": ["Plant genetics"], "username": "me"}
    assert packs.apply(mine, packs.clean({"k": ["x"]}), "start")["field"] == ["Genetics"]  # nothing to start from: kept


def test_only_what_you_ticked_goes_in():
    cfg = MyGeekyConfig(github_username="me", keywords=["gwas"], topics=["genomics"])
    people = [{"id": "A5000000001", "name": "Ada"}]
    assert packs.make(cfg, set(), "", people) == {"v": 1, "n": "", "k": [], "t": [], "f": [], "r": []}
    assert packs.make(cfg, {"words", "people"}, "Lab", people) == {"v": 1, "n": "Lab", "k": ["gwas"], "t": ["genomics"],
                                                                  "f": [], "r": [["A5000000001", "Ada"]]}
    assert "me" not in json.dumps(packs.make(cfg, {"words", "field", "people"}, "", people))   # never your account


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_and_the_computer_read_each_others_codes_and_the_phone_counts_them():
    py_codes = packs.codes(BIG)
    said = phone.run("""
import { applyPack, clean, codes, missing, receive } from './lib/packs.ts';
const { py, other, big, small, mine } = INPUT;
const steps = [];
let g = null, pack = null;
for (const text of ['hello', py[1], py[1], other[0], py[0], py[1], ...py.slice(2)]) {
  const out = receive(g, text); g = out.g; steps.push([out.got, missing(g)]); if (out.pack) pack = out.pack;
}
out({ steps, pack, phoneCodes: codes(big), phoneSmall: codes(small), clean: clean(big),
      merge: applyPack(mine, clean(small), 'merge'), start: applyPack(mine, clean(small), 'start') });
""", {"py": py_codes, "other": packs.codes(SMALL), "big": BIG, "small": SMALL,
      "mine": {"keywords": ["GWAS", "rust"], "topics": [], "field": ["Genetics"]}})
    n = len(py_codes)
    want = [["bad", []], ["new", [i for i in range(1, n + 1) if i != 2]], ["again", [i for i in range(1, n + 1) if i != 2]],
            ["done", []]]                                                          # the small pack is one code: done at once
    assert said["steps"][:4] == want
    assert said["steps"][4] == ["other", list(range(2, n + 1))]                     # a different pack: start over
    assert said["steps"][5][0] == ("done" if n == 2 else "new") and said["steps"][-1] == ["done", []]
    assert said["pack"] == packs.clean(BIG)
    assert _all(said["phoneCodes"]) == packs.clean(BIG) and _all(said["phoneSmall"]) == packs.clean(SMALL)
    assert said["clean"] == packs.clean(BIG)
    mine = {"keywords": ["GWAS", "rust"], "topics": [], "field": ["Genetics"]}
    assert said["merge"] == packs.apply(mine, packs.clean(SMALL), "merge")
    assert said["start"] == packs.apply(mine, packs.clean(SMALL), "start")
