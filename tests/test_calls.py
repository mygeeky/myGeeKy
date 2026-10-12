"""Calls for contributors: a public invitation in your beacon, matched on each reader's own
computer, answered with a sealed "I'm in" that carries the skills that matched."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from mygeeky import beacon as bc
from mygeeky import signal_crypto as sc
from mygeeky.config import MyGeekyConfig

TODAY = datetime.now(timezone.utc).date()


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch):
    import keyring
    store: dict = {}
    monkeypatch.setattr(keyring, "get_password", lambda svc, user: store.get((svc, user)))
    monkeypatch.setattr(keyring, "set_password", lambda svc, user, pw: store.__setitem__((svc, user), pw))
    return store


def _cfg(user="me", **kw) -> MyGeekyConfig:
    return MyGeekyConfig(github_username=user, beacon_enabled=True, **kw)


def _call(**kw):
    c = {"id": "a1b2c3d4", "repo": "finemap-lite", "note": "Port the SuSiE step to Snakemake so it runs anywhere.",
         "skills": ["snakemake", "fine-mapping", "python"], "level": "experienced", "time": "weeks",
         "created": TODAY.isoformat(), "until": (TODAY + timedelta(days=60)).isoformat()}
    c.update(kw)
    return c


class Writer:
    """Stands in for BeaconWriter: holds 'what's published' in memory."""

    def __init__(self, remote=None):
        self.remote = remote
        self.published = []

    def read(self):
        return json.loads(json.dumps(self.remote)) if self.remote else None

    def publish(self, beacon):
        self.remote = beacon
        self.published.append(beacon)

    def write(self, path, text, message):
        pass


def _cache_with(*users):
    return {"fetched_at": datetime.now(timezone.utc).isoformat(),
            "users": {login: {"raw": raw, "avatar_url": f"av/{login}", "pushed_at": "x"} for login, raw in users}}


def _beacon(pub, calls=(), interests=(), sealed=()):
    return {"mygeeky_beacon": 2, "keys": [pub], "status": "", "quiet": False, "interests": list(interests),
            "sealed": list(sealed), "calls": list(calls)}


# --------------------------------------------------------------------------- reading calls (untrusted)
def test_only_well_formed_open_calls_are_read():
    good = _call()
    bad = [
        _call(id="nothex!!"), _call(repo="../evil"), _call(repo="a b"),
        _call(note="see https://evil.example for details please"), _call(note="ping @someone about it please"),
        _call(note="www.spam.com is where it lives"), _call(note="short"), _call(note="x" * 201),
        _call(skills=[]), _call(skills=["<script>"]), _call(level="boss"), _call(time="forever"),
        _call(until=(TODAY - timedelta(days=1)).isoformat()),                     # expired
        _call(until=(TODAY + timedelta(days=400)).isoformat()),                   # longer than any call can be
        _call(created="yesterday"), "not a call", None,
    ]
    calls = bc.calls_in({"calls": [good, *bad]})
    assert [c["id"] for c in calls] == ["a1b2c3d4"]
    assert calls[0]["skills"] == ["snakemake", "fine-mapping", "python"] and calls[0]["filled"] is False
    many = [_call(id=f"0000000{i}", created=(TODAY - timedelta(days=i)).isoformat()) for i in range(6)]
    assert [c["id"] for c in bc.calls_in({"calls": many})] == ["00000000", "00000001", "00000002"]   # newest 3
    noisy = bc.calls_in({"calls": [_call(note="  Port\tthe ‮SuSiE​ step   to Snakemake. ")]})
    assert noisy[0]["note"] == "Port the SuSiE step to Snakemake."                # one plain line


def test_a_new_call_says_what_to_fix():
    c = bc.new_call("gwas-qc", "A second pair of eyes on LD pruning.", ["PLINK", "gwas", "plink"], "any", "hours", 30)
    assert bc.valid_call_id(c["id"]) and c["skills"] == ["plink", "gwas"] and c["until"] == (TODAY + timedelta(days=30)).isoformat()
    for args, says in [(("", "A second pair of eyes.", ["x"], "any", "hours", 30), "repos"),
                       (("r", "see www.x.com now please", ["x"], "any", "hours", 30), "no links"),
                       (("r", "A second pair of eyes.", [], "any", "hours", 30), "skill"),
                       (("r", "A second pair of eyes.", ["x"], "boss", "hours", 30), "level"),
                       (("r", "A second pair of eyes.", ["x"], "any", "hours", 45), "days")]:
        with pytest.raises(bc.BeaconError, match=says):
            bc.new_call(*args)


# --------------------------------------------------------------------------- posting your calls
def test_calls_survive_every_publish_and_the_limits_hold():
    cfg = _cfg(topics=["gwas"])
    _, my_pub = bc.my_keypair("me")
    phone_call = _call(id="0a0a0a0a", repo="from-the-phone")
    w = Writer(_beacon(my_pub, calls=[phone_call]))
    first = bc.create_call(cfg, "gwas-qc", "A second pair of eyes on LD pruning.", ["plink"], "any", "hours", 60, writer=w)
    assert [c["id"] for c in w.remote["calls"]] == [first["id"], "0a0a0a0a"]      # the phone's call stays
    bc.publish(cfg, bc.load_my_beacon(), w)                                         # e.g. after a signal
    assert len(w.remote["calls"]) == 2                                              # calls ride along
    with pytest.raises(bc.BeaconError, match="already an open call"):
        bc.create_call(cfg, "gwas-qc", "Another one for the same repo please.", ["x"], "any", "hours", 30, writer=w)
    bc.create_call(cfg, "third", "Help with the third thing please.", ["x"], "any", "hours", 30, writer=w)
    with pytest.raises(bc.BeaconError, match="3 open calls"):
        bc.create_call(cfg, "fourth", "Help with the fourth thing please.", ["x"], "any", "hours", 30, writer=w)
    bc.close_call(cfg, first["id"], filled=True, writer=w)
    assert next(c for c in w.remote["calls"] if c["id"] == first["id"])["filled"] is True
    bc.close_call(cfg, "0a0a0a0a", writer=w)
    assert "0a0a0a0a" not in {c["id"] for c in w.remote["calls"]}
    assert bc.load_my_beacon()["my_calls"] == w.remote["calls"]                     # a local copy, for the panel


# --------------------------------------------------------------------------- answering a call, end to end
def test_im_in_reaches_only_the_caller_with_the_skills_that_matched():
    me = _cfg("me", topics=["snakemake", "gwas"], keywords=["python"])
    _, me_pub = bc.my_keypair("me")
    bob_cfg = _cfg("bob")
    bob_priv, bob_pub = sc.new_keypair()
    eve_priv, _ = sc.new_keypair()
    call = _call()
    cache = _cache_with(("bob", _beacon(bob_pub, calls=[call], interests=["fine mapping"])))

    shown = bc.calls_for_me(cache, me, bc.load_my_beacon(), weights={"snakemake": 1.0, "python": 0.4, "gwas": 1.0})
    assert len(shown) == 1 and shown[0]["full_name"] == "bob/finemap-lite" and not shown[0]["explore"]
    assert shown[0]["matched"] == ["snakemake", "python"] and shown[0]["fit"] > 0.5

    w = Writer(_beacon(me_pub))
    bc.join_call(me, "bob", call["id"], shown[0]["matched"], writer=w, cache=cache)
    assert bc.calls_for_me(cache, me, bc.load_my_beacon(), weights={"snakemake": 1.0})[0]["joined"]
    with pytest.raises(bc.BeaconError, match="already said you're in"):
        bc.join_call(me, "bob", call["id"], ["snakemake"], writer=w, cache=cache)

    # what bob reads in my beacon: one box, only bob opens it, and it names the call
    mine = bc.parse_beacon(w.remote, "me", ttl_days=90)
    got = bc.open_signals(mine, "bob", bob_priv, ttl_days=90)
    assert got and got[0]["type"] == "join" and got[0]["call"] == call["id"] and got[0]["skills"] == ["snakemake", "python"]
    assert bc.open_signals(mine, "eve", eve_priv, ttl_days=90) == []
    assert "finemap" not in json.dumps(w.remote) and "snakemake" not in json.dumps(w.remote["sealed"])

    # bob's panel: the inbox names the repo, and "Your calls" lists me with my skills
    bob_cache = {**_cache_with(("me", w.remote)), "mine": _beacon(bob_pub, calls=[call])}
    rows = bc.inbox(bob_cache, bob_cfg, bc.empty_beacon(), bob_priv)
    assert rows[0]["text"] == "🙋 would like to help with bob/finemap-lite" and rows[0]["skills"] == ["snakemake", "python"]
    calls = bc.my_calls(bob_cache, bob_cfg, rows)
    assert [r["login"] for r in calls[0]["responders"]] == ["me"] and calls[0]["responders"][0]["skills"] == ["snakemake", "python"]

    # changed my mind: the box leaves my beacon
    assert bc.leave_call(me, "bob", call["id"], writer=w) == 1
    assert bc.open_signals(bc.parse_beacon(w.remote, "me", ttl_days=90), "bob", bob_priv, ttl_days=90) == []


def test_a_closed_or_filled_call_cant_be_answered_and_the_box_always_fits():
    me = _cfg("me")
    bob_priv, bob_pub = sc.new_keypair()
    filled = _cache_with(("bob", _beacon(bob_pub, calls=[_call(filled=True)])))
    with pytest.raises(bc.BeaconError, match="isn't open"):
        bc.add_signal(bc.empty_beacon(), "me", "bob", "join", None, me, bc.parse_beacon(filled["users"]["bob"]["raw"], "bob", 90),
                      call="a1b2c3d4", skills=["x"])
    with pytest.raises(bc.BeaconError, match="isn't open"):
        bc.add_signal(bc.empty_beacon(), "me", "bob", "join", None, me,
                      bc.parse_beacon(_beacon(bob_pub, calls=[_call()]), "bob", 90), call="ffffffff", skills=["x"])
    long_me, long_bob = "m" * 39, "b" * 39
    b = bc.add_signal(bc.empty_beacon(), long_me, long_bob, "join", None, _cfg(long_me),
                      bc.parse_beacon(_beacon(bob_pub, calls=[_call()]), long_bob, 90),
                      call="a1b2c3d4", skills=["a" * 40, "b" * 40, "c" * 40, "d" * 40])
    box = b["sent"][0]["boxes"][0]
    assert len(box) == sc.BOX_LEN and json.loads(sc.open_box(bob_priv, box).rstrip(b"\0"))["call"] == "a1b2c3d4"


def test_answering_calls_doesnt_count_as_reaching_out_to_new_people():
    me = _cfg("me", beacon_weekly_new_people=1)
    callers = []
    for i in range(3):
        _, pub = sc.new_keypair()
        callers.append((f"caller{i}", bc.parse_beacon(_beacon(pub, calls=[_call()]), f"caller{i}", 90)))
    beacon = bc.empty_beacon()
    for login, parsed in callers:
        beacon = bc.add_signal(beacon, "me", login, "join", None, me, parsed, call="a1b2c3d4", skills=["x"])
    assert len(beacon["sent"]) == 3


# --------------------------------------------------------------------------- what you're shown
def test_calls_are_matched_here_with_room_for_new_territory():
    me = _cfg("me", explore_share=0.2)
    users = []
    for i, (skills, note) in enumerate([(["snakemake"], "Snakemake help wanted for our pipeline."),
                                        (["gwas", "plink"], "GWAS quality control with PLINK, please."),
                                        (["single cell"], "Benchmark single-cell deconvolution methods."),
                                        (["rust"], "Port the parser to Rust for speed please.")]):
        _, pub = sc.new_keypair()
        users.append((f"u{i}", _beacon(pub, calls=[_call(id=f"0000000{i}", skills=skills, note=note)])))
    _, quiet_pub = sc.new_keypair()
    quiet = {**_beacon(quiet_pub, calls=[_call(id="0000000a")]), "quiet": True}
    cache = _cache_with(*users, ("quiet-one", quiet))
    weights = {"snakemake": 1.0, "gwas": 1.0, "plink": 0.8}
    shown = bc.calls_for_me(cache, me, bc.load_my_beacon(), weights=weights, seed=1)
    fits = [c["owner"] for c in shown if not c["explore"]]
    assert fits == ["u1", "u0"] or fits == ["u0", "u1"]
    assert len([c for c in shown if c["explore"]]) == 1                              # one from outside your work
    assert "quiet-one" not in {c["owner"] for c in shown}                            # not taking signals: no calls
    bc.hide_call("u0", "00000000")
    assert "u0" not in {c["owner"] for c in bc.calls_for_me(cache, me, bc.load_my_beacon(), weights=weights, seed=1)}
    me.beacon_muted = ["u1"]
    assert "u1" not in {c["owner"] for c in bc.calls_for_me(cache, me, bc.load_my_beacon(), weights=weights, seed=1)}
    no_explore = bc.calls_for_me(cache, _cfg("me", explore_share=0), bc.load_my_beacon(), weights=weights)
    assert no_explore and not any(c["explore"] for c in no_explore)                 # discovery off: fits only
