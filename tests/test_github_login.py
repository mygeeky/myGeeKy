import pytest

from mygeeky import github_login as gl
from mygeeky import setup_api, token_check
from mygeeky.config import MyGeekyConfig, load_config, save_config


class R:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data


def test_start_asks_for_no_scopes(monkeypatch):
    sent = {}

    def post(url, data=None, headers=None, timeout=None):
        sent.update(url=url, data=data)
        return R({"device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
                  "interval": 5, "expires_in": 900})
    monkeypatch.setattr(gl.requests, "post", post)
    flow = gl.start()
    assert flow["user_code"] == "ABCD-1234" and sent["data"] == {"client_id": gl.CLIENT_ID, "scope": ""}


def test_poll_waits_slows_down_and_returns_the_token(monkeypatch):
    answers = iter([{"error": "authorization_pending"}, {"error": "slow_down", "interval": 10},
                    {"error": "authorization_pending"}, {"access_token": "gho_abc"}])
    monkeypatch.setattr(gl.requests, "post", lambda *a, **k: R(next(answers)))
    waits = []
    assert gl.poll("dc", 5, 900, sleep=waits.append) == "gho_abc"
    assert waits == [5, 5, 10, 10]                 # GitHub's "slow down" is respected


@pytest.mark.parametrize("error, message", [("access_denied", "cancelled"), ("expired_token", "expired"),
                                            ("incorrect_client_credentials", "failed")])
def test_poll_explains_why_it_stopped(monkeypatch, error, message):
    monkeypatch.setattr(gl.requests, "post", lambda *a, **k: R({"error": error}))
    with pytest.raises(gl.LoginError, match=message):
        gl.poll("dc", 1, 900, sleep=lambda s: None)


def test_setup_stores_the_sign_in_for_the_right_account_only(monkeypatch):
    save_config(MyGeekyConfig(github_username="me"))
    monkeypatch.setattr(gl, "poll_grant", lambda *a, **k: {"access_token": "gho_abc"})
    stored = []
    monkeypatch.setattr(gl, "store", lambda token, login: stored.append((token, login)))
    monkeypatch.setattr(gl, "who", lambda token: "someone-else")
    r = setup_api.github_login_finish({"device_code": "dc"})
    assert not r["ok"] and "someone-else" in r["error"] and not stored
    monkeypatch.setattr(gl, "who", lambda token: "Me")
    r = setup_api.github_login_finish({"device_code": "dc"})
    assert r["ok"] and r["login"] == "Me" and stored == [({"access_token": "gho_abc"}, "Me")]
    assert "gho_abc" not in str(r)                 # the token never comes back to the installer


def test_sign_in_fills_in_the_username_when_none_is_set(monkeypatch):
    save_config(MyGeekyConfig())
    monkeypatch.setattr(gl, "poll_grant", lambda *a, **k: {"access_token": "gho_abc"})
    monkeypatch.setattr(gl, "who", lambda token: "newbie")
    monkeypatch.setattr(gl, "store", lambda token, login: None)
    assert setup_api.github_login_finish({"device_code": "dc"})["ok"]
    assert load_config().github_username == "newbie"


def test_a_no_scope_sign_in_token_is_a_clean_token_1():
    caps = {"valid": True, "login": "me", "kind": "OAuth", "scopes": [], "can_follow": False,
            "beacon_write": False, "other_repo": "me/x", "other_write": False}
    v = token_check.judge("read", caps, "me")
    assert v["ok"] and v["warnings"] == []
    broad = dict(caps, scopes=["repo"], other_write=True)                # the GitHub CLI's token
    assert not token_check.judge("read", broad, "me")["ok"]


# ---------------------------------------------------------------- 8-hour tokens that renew themselves
class _FakeKeyring:
    def __init__(self):
        self.store = {}

    def get_password(self, s, u):
        return self.store.get((s, u))

    def set_password(self, s, u, v):
        self.store[(s, u)] = v

    def delete_password(self, s, u):
        self.store.pop((s, u), None)


def _keyring(monkeypatch):
    import keyring
    fake = _FakeKeyring()
    for name in ("get_password", "set_password", "delete_password"):
        monkeypatch.setattr(keyring, name, getattr(fake, name))
    return fake


def test_signing_in_keeps_the_refresh_token_and_the_token_renews_itself(monkeypatch):
    import json, time
    from mygeeky import auth
    fake = _keyring(monkeypatch)
    gl.store({"access_token": "gho_first", "refresh_token": "ghr_one", "expires_in": 28800,
              "refresh_token_expires_in": 15897600}, "me")
    record = json.loads(fake.store[(gl.REFRESH_SERVICE, "me")])
    assert record["refresh_token"] == "ghr_one" and record["expires_at"] > time.time() + 28000
    assert auth.get_token("me") == "gho_first"                       # hours left: no renewal

    record["expires_at"] = time.time() + 60                          # almost over
    fake.store[(gl.REFRESH_SERVICE, "me")] = json.dumps(record)
    sent = []

    class R:
        def json(self):
            return {"access_token": "gho_second", "refresh_token": "ghr_two", "expires_in": 28800,
                    "refresh_token_expires_in": 15897600}
    monkeypatch.setattr(gl.requests, "post", lambda url, **kw: sent.append(kw["data"]) or R())
    assert auth.get_token("me") == "gho_second"
    assert sent == [{"client_id": gl.CLIENT_ID, "grant_type": "refresh_token", "refresh_token": "ghr_one"}]
    assert "client_secret" not in sent[0]                            # the device flow needs no secret
    assert json.loads(fake.store[(gl.REFRESH_SERVICE, "me")])["refresh_token"] == "ghr_two"   # rotated


def test_a_refused_refresh_token_is_forgotten_and_offline_keeps_the_old_token(monkeypatch):
    import json, time
    from mygeeky import auth
    fake = _keyring(monkeypatch)
    gl.store({"access_token": "gho_old", "refresh_token": "ghr_x", "expires_in": 30}, "me")

    def offline(url, **kw):
        raise gl.requests.ConnectionError("offline")
    monkeypatch.setattr(gl.requests, "post", offline)
    assert auth.get_token("me") == "gho_old" and gl.refresh_record("me")        # try again next time

    class Refused:
        def json(self):
            return {"error": "bad_refresh_token"}
    monkeypatch.setattr(gl.requests, "post", lambda url, **kw: Refused())
    auth.get_token("me")
    assert gl.refresh_record("me") is None                           # sign in again


def test_two_processes_never_renew_at_once(monkeypatch, tmp_path):
    import threading, time
    monkeypatch.setattr("mygeeky.config.DATA_DIR", tmp_path)
    inside, overlap = [], []

    def worker():
        with gl._RenewLock():
            if inside:
                overlap.append(True)
            inside.append(1)
            time.sleep(0.2)
            inside.pop()
    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not overlap and not (tmp_path / "signin-renew.lock").exists()


def test_a_token_that_renews_itself_never_goes_to_the_phone(monkeypatch):
    from mygeeky import auth, pairing
    _keyring(monkeypatch)
    gl.store({"access_token": "gho_x", "refresh_token": "ghr_y", "expires_in": 28800}, "me")
    monkeypatch.setattr(auth, "get_token", lambda u: "gho_x")
    token, why = pairing.shareable_token(MyGeekyConfig(github_username="me"))
    assert token is None and "signs in" in why
