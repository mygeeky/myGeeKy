"""Settings → Accounts: the same cards, words and to-do count on the desktop (accounts.py) and the phone
(lib/accounts.ts)."""
from __future__ import annotations

import pytest

import phone
from mygeeky import accounts

DETAILS = {"user": "ada", "orcid": "0000-0002-1825-0097", "repo": "ada/mygeeky-data"}
CASES = [
    {},
    {"github": "on", "orcid": "on", "data": "on", "beacon": "on", "device": "on"},
    {"github": "on", "orcid": "off", "data": "bad", "beacon": "on"},
    {"github": "bad", "orcid": "bad", "data": "off", "beacon": "bad", "device": "weird"},
]


def test_order_and_the_optional_ones_never_nag():
    c = accounts.cards({}, "phone")
    assert [x["key"] for x in c] == ["github", "orcid", "data", "beacon", "device"]
    assert [x["pill"] for x in c] == ["Optional", "Optional", "Not set up", "Optional", "Optional"]
    assert accounts.todo(c) == 1                                      # only saving your data
    assert "keywords are enough" in c[1]["why"] and c[0]["why"].startswith("Why link it")
    on = accounts.cards({k: "on" for k in accounts.ORDER}, "phone", DETAILS)
    assert all(x["folded"] and x["pill"] == "Connected" for x in on) and accounts.todo(on) == 0
    assert "ada/mygeeky-data" in on[2]["why"] and "Signed in as ada" in on[0]["why"]
    mixed = accounts.cards(CASES[2], "desktop", DETAILS)
    assert accounts.todo(mixed) == 1 and mixed[2]["pill"] == "Needs renewing"
    assert accounts.cards({"orcid": "bad"})[1]["state"] == "on"     # ORCID doesn't expire
    assert accounts.cards({"device": "on"})[4]["state"] == "off"    # the computer can't know about a phone
    assert accounts.todo_text(0) == "" and accounts.todo_text(2).startswith("2 things")
    for c in accounts.cards({}, "phone") + accounts.cards({}, "desktop"):
        assert "learn" not in c["why"].replace("learns", "")       # plain words: never "what I learn about you"


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_says_the_same():
    said = phone.run("""
import { cards, todo, todoText } from './lib/accounts.ts';
out(INPUT.cases.flatMap((c) => ['phone', 'desktop'].map((p) => { const x = cards(c, p, INPUT.details); return { x, n: todo(x), t: todoText(todo(x)) }; })));
""", {"cases": CASES, "details": DETAILS}, name="accounts")
    want = []
    for c in CASES:
        for p in ("phone", "desktop"):
            x = accounts.cards(c, p, DETAILS)
            want.append({"x": x, "n": accounts.todo(x), "t": accounts.todo_text(accounts.todo(x))})
    assert said == want
    # where the data is saved, and what went wrong, read the same on both
    variants = [{"where": w, "repo": "ada/d"} for w in ("drive", "github", "")]
    said = phone.run("""
import { cards } from './lib/accounts.ts';
out(INPUT.v.flatMap((d) => ['on', 'bad', 'off'].flatMap((s) => ['phone', 'desktop'].map((p) => cards({ data: s }, p, d)[2].why))));
""", {"v": variants}, name="accounts2")
    assert said == [accounts.cards({"data": s}, p, d)[2]["why"] for d in variants for s in ("on", "bad", "off")
                    for p in ("phone", "desktop")]


def test_the_saving_card_names_the_place_and_never_both():
    off = accounts.cards({}, "desktop")[2]["why"]
    assert "Google Drive (recommended)" in off and "choose one" in off and "encrypt" not in off
    drive = accounts.cards({"data": "on"}, "phone", {"where": "drive"})[2]["why"]
    assert drive.startswith("Saving to Google Drive.")
    repo = accounts.cards({"data": "on"}, "desktop", {"where": "github", "repo": "ada/d"})[2]["why"]
    assert repo.startswith("Saving to ada/d.")
    assert "Sign in with Google again" in accounts.cards({"data": "bad"}, "desktop", {"where": "drive"})[2]["why"]
