"""The four signs on the top strip (GitHub, ORCID, Saving, Beacon): the same states, words and reminders on the
desktop (signs.py) and the phone (lib/signs.ts)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import phone
from mygeeky import signs
from mygeeky.config import MyGeekyConfig
from mygeeky.gui import app as logic

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
CASES = [("on", "on", "on", "on"), ("off", "off", "off", "off"), ("on", "off", "bad", "bad"),
         ("bad", "on", "off", "on"), ("on", "on", "on", "off", "drive"), ("off", "on", "bad", "on", "drive"),
         ("on", "on", "off", "on", "drive"), ("on", "on", "on", "on", "github")]
LASTS = ["", (NOW - timedelta(hours=3)).isoformat(), (NOW - timedelta(hours=30)).isoformat(), "garbage"]


def test_each_sign_is_on_faint_or_red():
    assert signs.state(False) == signs.state(False, True) == "off"     # never set up: faint, even if "broken"
    assert signs.state(True) == "on" and signs.state(True, True) == "bad"
    items = signs.signs("on", "bad", "bad", "off")
    assert [s["key"] for s in items] == ["github", "orcid", "data", "beacon"]
    assert [s["state"] for s in items] == ["on", "on", "bad", "off"]  # ORCID doesn't expire: never red
    assert all(s["tip"] for s in items)


def test_saving_in_google_drive_shows_its_logo():
    data = lambda *a: signs.signs(*a)[2]                              # noqa: E731
    assert data("on", "on", "on", "on", "drive")["icon"] == "drive"
    assert "Google Drive" in data("on", "on", "bad", "on", "drive")["tip"]
    assert data("on", "on", "off", "on", "drive")["icon"] == ""       # not saving: no logo
    assert data("on", "on", "on", "on", "github")["icon"] == "" and data("on", "on", "on", "on")["icon"] == ""


def test_a_red_sign_reminds_at_most_once_a_day():
    red = signs.signs("on", "on", "bad", "on")
    assert "your storage" in signs.reminder(red, "", NOW)
    assert signs.reminder(red, (NOW - timedelta(hours=3)).isoformat(), NOW) == ""
    assert signs.reminder(red, (NOW - timedelta(hours=25)).isoformat(), NOW)
    assert signs.reminder(signs.signs("on", "on", "on", "off"), "", NOW) == ""


def test_the_desktop_reads_them_from_what_it_knows(monkeypatch):
    monkeypatch.setattr(logic, "sync_enabled", lambda cfg: True)
    cfg = MyGeekyConfig(github_username="me", orcid_id="0000-0002-1825-0097", beacon_enabled=True)
    states = lambda items: [s["state"] for s in items]                 # noqa: E731
    assert states(logic.status_signs(cfg, [])) == ["on", "on", "on", "on"]
    warn = [{"name": "beacon", "warn": True}, {"name": "read", "warn": False}]
    assert states(logic.status_signs(cfg, warn, "403 permission denied")) == ["on", "on", "bad", "bad"]
    assert states(logic.status_signs(MyGeekyConfig(), [{"name": "beacon", "warn": True}])) == ["off", "off", "on", "off"]
    assert logic.sync_access_error({"error": "couldn't reach github.com"}) == ""      # offline is not red
    assert logic.sync_access_error({"error": "remote: Permission denied"})


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+")
def test_the_phone_says_the_same():
    said = phone.run("""
import { signs, reminder, state } from './lib/signs.ts';
const now = new Date(INPUT.now);
out({ items: INPUT.cases.map((c) => signs(...c)),
      reminders: INPUT.cases.flatMap((c) => INPUT.lasts.map((l) => reminder(signs(...c), l, now))),
      states: [state(false), state(false, true), state(true), state(true, true)] });
""", {"cases": CASES, "lasts": LASTS, "now": NOW.isoformat()}, name="signs")
    assert said["items"] == [signs.signs(*c) for c in CASES]
    assert said["reminders"] == [signs.reminder(signs.signs(*c), last, NOW) for c in CASES for last in LASTS]
    assert said["states"] == [signs.state(False), signs.state(False, True), signs.state(True), signs.state(True, True)]
