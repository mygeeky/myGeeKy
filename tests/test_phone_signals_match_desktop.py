"""The phone app's Signals (mobile/src/lib/signal-crypto.ts, signals-core.ts) must read and
write exactly what the desktop does: same encryption, same beacon. These run the phone's
real TypeScript in Node against this Python. Skipped where Node or the phone app's
packages aren't installed (they are on a developer's machine)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mygeeky import beacon as bc, signal_crypto as sc
from mygeeky.config import MyGeekyConfig

MOBILE = Path(__file__).resolve().parents[1] / "mobile"
WORK = MOBILE / ".crosscheck"


def _ready() -> bool:
    if not shutil.which("node") or not (MOBILE / "node_modules" / "@noble" / "curves").exists():
        return False
    major = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")[0]
    return major.isdigit() and int(major) >= 23           # runs TypeScript directly


pytestmark = pytest.mark.skipif(not _ready(), reason="needs Node 23+ and mobile/node_modules")


@pytest.fixture(scope="module")
def harness():
    WORK.mkdir(exist_ok=True)
    for name in ("signal-crypto", "signals-core"):          # the real files, with Node's randomness
        src = (MOBILE / "src" / "lib" / f"{name}.ts").read_text(encoding="utf-8")
        src = src.replace("import { getRandomValues } from 'expo-crypto';",
                          "const getRandomValues = (a: Uint8Array) => globalThis.crypto.getRandomValues(a);")
        src = re.sub(r"from '\./signal-crypto'", "from './signal-crypto.ts'", src)
        (WORK / f"{name}.ts").write_text(src, encoding="utf-8")
    for name in ("core-side.ts", "node-side.ts"):
        shutil.copy(MOBILE / "crosscheck" / name, WORK / name)
    yield
    shutil.rmtree(WORK, ignore_errors=True)


def _node(script, *args):
    r = subprocess.run(["node", script, *args], capture_output=True, text=True, cwd=WORK)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout)


def _node_with(script, step, data, tmp_path):
    f = tmp_path / f"{step}.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return _node(script, step, str(f))


def test_the_phone_and_the_desktop_open_each_others_boxes(harness):
    phone = _node("node-side.ts", "keys")
    assert phone["BOX_LEN"] == sc.BOX_LEN and sc.valid_public_key(phone["pub"])
    for i in range(5):
        py_priv, py_pub = sc.new_keypair()
        msg = json.dumps({"from": "desktop", "to": "phone", "type": "learn", "n": i}).encode()
        res = _node("node-side.ts", "open-and-reply", phone["priv"], sc.seal(phone["pub"], msg), py_pub)
        assert res["opened"] == msg.decode()
        assert sc.open_box(py_priv, res["reply"]) == b'{"from":"phone","to":"desktop","type":"thanks"}'
        assert not res["tamperedOpens"] and not res["wrongKeyOpens"]


def test_phone_and_desktop_signals_work_both_ways_and_keep_each_other(harness, tmp_path):
    alice_cfg = MyGeekyConfig(github_username="alice", beacon_status="open-to-collab", topics=["gwas"])
    bob_cfg = MyGeekyConfig(github_username="bob", topics=["gwas"])
    alice_desk_priv, alice_desk_pub = sc.new_keypair()
    bob_priv, bob_pub = sc.new_keypair()
    alice_published = bc.public_beacon(bc.empty_beacon(), alice_cfg, alice_desk_pub)
    four = [sc.new_keypair()[1] for _ in range(4)]

    # the phone joins Alice's beacon and sends Bob a thanks
    out = _node_with("core-side.ts", "phone-joins-and-sends",
                     {"aliceBeacon": alice_published, "bobKeys": [bob_pub], "fourKeys": four}, tmp_path)
    merged = bc.parse_beacon(out["merged"], "alice", 90)
    assert set(merged["keys"]) == {alice_desk_pub, out["phonePub"]} and merged["status"] == "open-to-collab"
    assert [g["type"] for g in bc.open_signals(merged, "bob", bob_priv, 90)] == ["thanks"]
    assert out["refusedWhenFull"]                       # never pushes a computer's key out

    # Bob's desktop sends Alice a signal: both her phone and her computer open it
    bob_local = bc.add_signal(bc.empty_beacon(), "bob", "alice", "learn", None, bob_cfg, merged)
    bob_published = bc.public_beacon(bob_local, bob_cfg, bob_pub)
    res = _node_with("core-side.ts", "phone-reads", {"bobBeacon": bob_published, "phonePriv": out["phonePriv"]}, tmp_path)
    assert [g["type"] for g in res["got"]] == ["learn"] and res["copiedBoxOpens"] == 0
    assert [g["type"] for g in bc.open_signals(bc.parse_beacon(bob_published, "bob", 90), "alice", alice_desk_priv, 90)] == ["learn"]

    # Alice's computer publishes again: the phone's key and its signal survive
    again = bc.public_beacon(bc.empty_beacon(), alice_cfg, alice_desk_pub, remote=out["merged"])
    assert out["phonePub"] in again["keys"]
    assert [g["type"] for g in bc.open_signals(bc.parse_beacon(again, "alice", 90), "bob", bob_priv, 90)] == ["thanks"]


def test_phone_and_desktop_agree_on_calls_and_im_in(harness, tmp_path):
    from datetime import datetime, timedelta, timezone
    today = datetime.now(timezone.utc).date()

    def call(**kw):
        c = {"id": "a1b2c3d4", "repo": "finemap-lite", "note": "Port the SuSiE step to Snakemake so it runs anywhere.",
             "skills": ["snakemake", "fine-mapping", "python"], "level": "experienced", "time": "weeks",
             "created": today.isoformat(), "until": (today + timedelta(days=60)).isoformat()}
        c.update(kw)
        return c

    candidates = [call(), call(id="nothex!!"), call(repo="../evil"), call(note="see https://evil.example now please"),
                  call(note="ping @someone about it, please"), call(note="short"), call(note="x" * 201),
                  call(skills=[]), call(level="boss"), call(until=(today - timedelta(days=1)).isoformat()),
                  call(until=(today + timedelta(days=400)).isoformat()), call(created="2026-13-45"),
                  call(note="  Tabs\tand ‮spaces​ are   cleaned up. "), call(filled=True), "nope", None]
    alice_priv, alice_pub = sc.new_keypair()          # Alice's phone
    bob_priv, bob_pub = sc.new_keypair()
    alice_cfg = MyGeekyConfig(github_username="alice", beacon_enabled=True)
    alice_beacon = bc.public_beacon(bc.empty_beacon(), alice_cfg, sc.new_keypair()[1])   # her computer's key
    bob_beacon = {**bc.public_beacon(bc.empty_beacon(), MyGeekyConfig(github_username="bob"), bob_pub), "calls": [call()]}

    # Bob has a call open; Alice's phone reads it, makes a call of her own, and says she's in on Bob's
    out = _node_with("core-side.ts", "calls", {"candidates": candidates, "aliceBeacon": alice_beacon, "alicePhonePub": alice_pub,
                                               "alicePhonePriv": alice_priv, "bobBeacon": bob_beacon,
                                               "bobJoined": bob_beacon}, tmp_path)
    # 1. the same calls pass on both sides
    assert out["verdicts"] == [len(bc.calls_in({"calls": [c]})) == 1 for c in candidates]
    # 2. a call made on the phone is exactly what the desktop reads, and the desktop keeps it
    assert bc.calls_in(out["withCall"]) == [out["made"]] and out["made"]["skills"] == ["plink", "gwas"]
    assert out["made"]["note"] == "A second pair of eyes on LD pruning." and bc.valid_call_id(out["made"]["id"])
    kept = bc.public_beacon(bc.empty_beacon(), alice_cfg, sc.new_keypair()[1], remote=out["withCall"])
    assert [c["id"] for c in kept["calls"]] == [out["made"]["id"]]
    assert out["tooMany"] and "already an open call" in out["tooMany"]
    assert out["bobCalls"] == bc.calls_in(bob_beacon)
    # 3. the phone's "I'm in" opens on Bob's desktop, naming the call, with the skills trimmed to fit a box
    alice_with_join = {**alice_beacon, "sealed": [{"at": today.isoformat(), "box": b} for b in out["joinBoxes"]]}
    got = bc.open_signals(bc.parse_beacon(alice_with_join, "alice", 90), "bob", bob_priv, 90)
    assert got[0]["type"] == "join" and got[0]["call"] == "a1b2c3d4" and got[0]["skills"][:3] == ["snakemake", "python", "r"]
    # 4. Bob's desktop "I'm in" to a call of Alice's opens on her phone
    alice_parsed = bc.parse_beacon({**alice_beacon, "keys": [alice_pub], "calls": [call(id="0f0f0f0f")]}, "alice", 90)
    bob_local = bc.add_signal(bc.empty_beacon(), "bob", "alice", "join", None, MyGeekyConfig(github_username="bob"),
                              alice_parsed, call="0f0f0f0f", skills=["snakemake"])
    bob_published = bc.public_beacon(bob_local, MyGeekyConfig(github_username="bob"), bob_pub)
    res = _node_with("core-side.ts", "calls", {"candidates": [], "aliceBeacon": alice_beacon, "alicePhonePub": alice_pub,
                                               "alicePhonePriv": alice_priv, "bobBeacon": bob_beacon,
                                               "bobJoined": bob_published}, tmp_path)
    assert [(g["type"], g.get("call"), g.get("skills")) for g in res["opened"]] == [("join", "0f0f0f0f", ["snakemake"])]
