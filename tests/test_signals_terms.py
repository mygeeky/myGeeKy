"""The Signals terms (website/terms.html): agreed to before turning Signals on or posting a call, on every app, in the
same words; and the beacons myGeeKy's maker hides from everyone for breaking them (the curated lists' signals_hidden)."""

import pytest

from mygeeky import beacon as bc
from mygeeky.config import MyGeekyConfig
from tests import phone


def test_turning_signals_on_or_posting_a_call_needs_the_terms():
    cfg = MyGeekyConfig(github_username="me")
    with pytest.raises(bc.BeaconError, match="Signals terms"):
        bc.go_live(cfg, writer=object())
    assert not cfg.beacon_enabled
    with pytest.raises(bc.BeaconError, match="Signals terms"):
        bc.create_call(cfg, "me/tool", "Help with docs", ["python"], "any", "hours", 30, writer=object())
    bc.accept_terms(cfg)
    assert bc.terms_accepted(cfg) and cfg.signals_terms == bc.TERMS_VERSION


def test_a_beacon_already_on_can_renew_its_token_without_asking_again(monkeypatch):
    cfg = MyGeekyConfig(github_username="me", beacon_enabled=True)          # on before the terms existed

    class Writer:
        def write(self, *a, **kw):
            pass
    monkeypatch.setattr(bc, "publish", lambda cfg, beacon, writer=None: None)
    bc.go_live(cfg, Writer())                                                 # no BeaconError
    assert cfg.beacon_enabled


def test_setup_ticking_join_signals_is_agreeing(monkeypatch):
    from mygeeky import auth, setup_api
    from mygeeky.config import load_config, save_config
    save_config(MyGeekyConfig(github_username="me"))
    monkeypatch.setattr(auth, "get_beacon_token", lambda user: "github_pat_x")
    monkeypatch.setattr(auth, "get_token", lambda user: "ghp_read")
    monkeypatch.setattr(setup_api, "_ensure_gh_on_path", lambda: None)
    monkeypatch.setattr(bc, "ensure_repo", lambda cfg, client, create=False: [])
    lived = []
    monkeypatch.setattr(bc, "go_live", lambda cfg, writer=None: lived.append(cfg.signals_terms))
    assert setup_api.beacon_init({}) == {"ok": False, "error": bc.TERMS_NEEDED} and not lived
    assert setup_api.beacon_init({"agree": True})["ok"] and lived == [bc.TERMS_VERSION]
    assert load_config().signals_terms == bc.TERMS_VERSION


def test_a_beacon_the_maker_hid_shows_nowhere(monkeypatch):
    from mygeeky import curated
    raw = {"version": "1", "signals_hidden": ["Spammer", "not a login!", 7, "fine-user"]}
    assert curated.clean(raw)["signals_hidden"] == ["Spammer", "fine-user"]
    monkeypatch.setattr(curated, "load", lambda force=False: {"signals_hidden": ["Spammer"]})
    assert bc.hidden_by_maker() == {"spammer"}
    cache = {"users": {"spammer": {"raw": {}}, "alice": {"raw": {}}}}
    seen = []
    monkeypatch.setattr(bc, "parse_beacon", lambda raw, login, ttl: seen.append(login) or {"login": login})
    users = bc._parsed_users(cache, MyGeekyConfig(github_username="me"))
    assert [u["login"] for u in users] == ["alice"] and seen == ["alice"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_asks_the_same_and_hides_the_same():
    said = phone.run("""
import { TERMS_NEEDED, TERMS_POINTS, TERMS_URL, TERMS_VERSION } from './lib/signals-core.ts';
import { clean } from './lib/curated.ts';
import { acceptTerms, createCall, setUp, termsAccepted } from './lib/signals.ts';
const before = await termsAccepted();
let refused = '';
try { await setUp('me', 'github_pat_x'); } catch (e) { refused = e.message; }
let refusedCall = '';
try { await createCall('me', { repo: 'me/tool', note: 'n', skills: [], level: 'any', time: 'hours', days: 30 }); } catch (e) { refusedCall = e.message; }
await acceptTerms();
out({ version: TERMS_VERSION, url: TERMS_URL, points: TERMS_POINTS, needed: TERMS_NEEDED, before, after: await termsAccepted(),
      refused, refusedCall, hidden: clean(INPUT.raw).signals_hidden });
""", {"raw": {"version": "1", "signals_hidden": ["Spammer", "not a login!", 7, "fine-user"]}})
    assert (said["version"], said["url"], said["needed"]) == (bc.TERMS_VERSION, bc.TERMS_URL, bc.TERMS_NEEDED)
    assert said["points"] == list(bc.TERMS_POINTS)
    assert said["before"] is False and said["after"] is True
    assert said["refused"] == bc.TERMS_NEEDED and said["refusedCall"] == bc.TERMS_NEEDED
    assert said["hidden"] == ["Spammer", "fine-user"]
