"""Sign in with ORCID, and myGeeKy without a GitHub account."""
import threading
import urllib.request

import pytest

from mygeeky import orcid_login, setup_api
from mygeeky.config import MyGeekyConfig, load_config, profile_ready, save_config


def test_the_check_digit_catches_typos():
    assert orcid_login.checksum_ok("0000-0002-1825-0097")
    assert orcid_login.checksum_ok("0000-0002-1694-233X")          # X stands for 10
    assert not orcid_login.checksum_ok("0000-0002-1825-0098")      # one digit off
    assert not orcid_login.checksum_ok("0000-0002-1825-009")


def test_the_authorize_link_asks_only_who_you_are(monkeypatch):
    monkeypatch.setattr(orcid_login, "CLIENT_ID", "APP-TEST")
    url = orcid_login.authorize_url("d5555-secret", "n0nce")
    assert url.startswith("https://orcid.org/oauth/authorize?")
    assert "response_type=token" in url and "scope=openid" in url and "client_id=APP-TEST" in url
    assert "redirect_uri=https%3A%2F%2Fmygeeky.org%2Forcid%2F" in url and "state=d5555-secret" in url


def test_without_a_client_id_it_says_to_type_the_id(monkeypatch):
    monkeypatch.setattr(orcid_login, "CLIENT_ID", "")
    assert not orcid_login.available()
    with pytest.raises(orcid_login.OrcidLoginError, match="Type your ORCID iD"):
        orcid_login.sign_in()


def test_the_listener_takes_only_its_own_answer():
    """What the relay page does: send the browser to 127.0.0.1:<port>/orcid?... with the same state."""
    def open_page(state):
        port = state.split("-")[0][1:]
        def browser():
            base = f"http://127.0.0.1:{port}/orcid?"
            for q in ("access_token=forged&state=d1-wrong", f"access_token=tok-1&state={state}"):
                try:
                    urllib.request.urlopen(base + q, timeout=5).read()
                except Exception:
                    pass                                                   # the forged one gets a 404
        threading.Thread(target=browser, daemon=True).start()
    answer = orcid_login._wait_for_answer("s3cret-abcdefghij", open_page, 10)
    assert answer["access_token"] == "tok-1"


def test_signing_in_asks_orcid_whose_token_it_is(monkeypatch):
    monkeypatch.setattr(orcid_login, "CLIENT_ID", "APP-TEST")
    monkeypatch.setattr(orcid_login, "_wait_for_answer", lambda secret, open_page, timeout: {"access_token": "t"})

    class Answer:
        status_code = 200
        def json(self):
            return {"sub": "0000-0002-1825-0097", "given_name": "Josiah", "family_name": "Carberry"}
    seen = {}
    monkeypatch.setattr(orcid_login.requests, "get", lambda url, headers, timeout: seen.update(h=headers) or Answer())
    assert orcid_login.sign_in() == {"orcid": "0000-0002-1825-0097", "name": "Josiah Carberry"}
    assert seen["h"]["Authorization"] == "Bearer t"


def test_a_cancelled_sign_in_says_so(monkeypatch):
    monkeypatch.setattr(orcid_login, "CLIENT_ID", "APP-TEST")
    monkeypatch.setattr(orcid_login, "_wait_for_answer", lambda *a: {"error": "access_denied"})
    with pytest.raises(orcid_login.OrcidLoginError, match="cancelled"):
        orcid_login.sign_in()


def test_setup_keeps_the_signed_in_orcid(monkeypatch):
    monkeypatch.setattr(orcid_login, "sign_in", lambda: {"orcid": "0000-0002-1825-0097", "name": "J. Carberry"})
    r = setup_api.orcid_login({})
    assert r == {"ok": True, "orcid": "0000-0002-1825-0097", "name": "J. Carberry"}
    assert load_config().orcid_id == "0000-0002-1825-0097"


def test_github_is_optional_but_something_is_needed():
    assert setup_api.save_profile({"github_username": ""})["ok"] is False
    r = setup_api.save_profile({"github_username": "", "orcid_id": "https://orcid.org/0000-0002-1825-0097"})
    assert r["ok"] and load_config().orcid_id == "0000-0002-1825-0097" and load_config().github_username == ""
    assert setup_api.save_profile({"github_username": "", "topics": "gwas, single cell"})["ok"]
    bad = setup_api.save_profile({"github_username": "", "orcid_id": "0000-0002-1825-0098"})
    assert not bad["ok"] and "mistyped" in bad["error"]


def test_profile_ready_and_research_without_github(monkeypatch):
    from mygeeky import papers
    from mygeeky.gui import app as logic
    assert not profile_ready(MyGeekyConfig())
    cfg = MyGeekyConfig(orcid_id="0000-0002-1825-0097")
    assert profile_ready(cfg)
    monkeypatch.setattr(papers, "trends_due", lambda cfg, trends: True)
    assert logic.trends_due(cfg)                                     # research runs on OpenAlex, not GitHub
    save_config(cfg)
    status = logic.get_status(cfg)
    assert status["profile_ready"] and not status["configured"] and status["orcid_id"] == cfg.orcid_id
