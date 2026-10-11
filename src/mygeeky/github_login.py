"""Sign in with GitHub: no token to create or copy.

GitHub's device flow, made for apps that can't keep a secret (myGeeKy is open
source, so it can't): myGeeKy asks GitHub for a short code, you open
github.com/login/device, type the code and click Authorize, and myGeeKy
receives a token by itself.

The sign-in asks for NO scopes, so the token can only read public data -- the
same thing token 1 does -- and can never follow, star or write anything. It's
stored in your OS keyring like any token 1. You can revoke it any time in
GitHub -> Settings -> Applications -> Authorized OAuth Apps -> myGeeKy.
Signals still uses its own single-repo token.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable

import requests

CLIENT_ID = "Ov23liNyUzK9THj5uAyH"          # the myGeeKy OAuth app (public; there is no secret)
DEVICE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
HEADERS = {"Accept": "application/json", "User-Agent": "mygeeky"}


class LoginError(RuntimeError):
    pass


def start() -> dict[str, Any]:
    """{"user_code", "verification_uri", "device_code", "interval", "expires_in"}."""
    try:
        r = requests.post(DEVICE_URL, data={"client_id": CLIENT_ID, "scope": ""}, headers=HEADERS, timeout=20)
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise LoginError(f"Couldn't reach GitHub to sign in ({exc}).") from exc
    if not data.get("device_code") or not data.get("user_code"):
        raise LoginError(f"GitHub didn't start the sign-in: {data.get('error_description') or data}")
    return {"device_code": data["device_code"], "user_code": data["user_code"],
            "verification_uri": data.get("verification_uri") or "https://github.com/login/device",
            "interval": int(data.get("interval") or 5), "expires_in": int(data.get("expires_in") or 900)}


def poll(device_code: str, interval: int = 5, expires_in: int = 900,
         sleep: Callable[[float], None] = time.sleep, cancelled: Callable[[], bool] = lambda: False) -> str:
    """Wait for you to authorize on github.com; returns the token."""
    return poll_grant(device_code, interval, expires_in, sleep, cancelled)["access_token"]


def poll_grant(device_code: str, interval: int = 5, expires_in: int = 900,
               sleep: Callable[[float], None] = time.sleep,
               cancelled: Callable[[], bool] = lambda: False) -> dict[str, Any]:
    """Wait for you to authorize on github.com; returns GitHub's whole answer: the
    token, and -- since GitHub made 8-hour tokens the default for new apps -- the
    refresh token and lifetimes that keep it working."""
    deadline = time.monotonic() + expires_in
    wait = max(interval, 1)
    while time.monotonic() < deadline:
        if cancelled():
            raise LoginError("Sign-in cancelled.")
        sleep(wait)
        try:
            data = requests.post(TOKEN_URL, headers=HEADERS, timeout=20, data={
                "client_id": CLIENT_ID, "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}).json()
        except (requests.RequestException, ValueError):
            continue                                   # a network hiccup: just try again
        if data.get("access_token"):
            return data
        error = data.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            wait = int(data.get("interval") or wait + 5)
            continue
        if error == "expired_token":
            raise LoginError("The code expired before it was used. Start the sign-in again.")
        if error == "access_denied":
            raise LoginError("You cancelled the sign-in on GitHub.")
        raise LoginError(f"GitHub sign-in failed: {data.get('error_description') or error}")
    raise LoginError("The code expired before it was used. Start the sign-in again.")


def who(token: str) -> str:
    """The username the token belongs to."""
    r = requests.get("https://api.github.com/user", timeout=20,
                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    if r.status_code != 200:
        raise LoginError("GitHub didn't accept the new sign-in. Please try again.")
    return r.json().get("login", "")


def store(grant: "str | dict[str, Any]", username: str) -> None:
    """Keep it as this computer's token 1 (OS keyring only). With a refresh token,
    that goes in the keyring too, so the 8-hour token can renew itself."""
    import keyring
    from . import auth, tokens
    grant = {"access_token": grant} if isinstance(grant, str) else grant
    keyring.set_password(auth.SERVICE_NAME, username, grant["access_token"])
    if grant.get("refresh_token"):
        now = time.time()
        record = {"refresh_token": grant["refresh_token"],
                  "expires_at": now + float(grant.get("expires_in") or 8 * 3600),
                  "refresh_expires_at": now + float(grant.get("refresh_token_expires_in") or 182 * 86400)}
        keyring.set_password(REFRESH_SERVICE, username, json.dumps(record))
    else:
        forget_refresh(username)                       # a token that doesn't expire: nothing to renew
    tokens.forget()


# --------------------------------------------------------------------------- renewing (8-hour tokens)
# Since 2026-08-14 GitHub gives new OAuth apps 8-hour access tokens plus a refresh
# token (valid 6 months, renewed at every use). Tokens from the device flow can be
# renewed without the app's secret, which an open-source app can't keep.
REFRESH_SERVICE = "mygeeky-github-refresh"
RENEW_BEFORE = 10 * 60          # renew when less than this many seconds are left


def refresh_record(username: str) -> dict[str, Any] | None:
    try:
        import keyring
        raw = keyring.get_password(REFRESH_SERVICE, username)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def forget_refresh(username: str) -> None:
    try:
        import keyring
        keyring.delete_password(REFRESH_SERVICE, username)
    except Exception:
        pass


def needs_renewal(record: dict[str, Any] | None, now: float | None = None) -> bool:
    return bool(record) and float(record.get("expires_at", 0)) - (now or time.time()) < RENEW_BEFORE


class _RenewLock:
    """One renewal at a time across myGeeKy's processes (the panel, the weekly run, a
    command): GitHub replaces the refresh token at every use, so two renewals at once
    would leave one of them holding a dead token, and you signed out."""

    def __init__(self, stale_after: float = 60.0) -> None:
        from .config import DATA_DIR
        self.path, self.stale_after, self.held = DATA_DIR / "signin-renew.lock", stale_after, False

    def __enter__(self) -> "_RenewLock":
        import os
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > self.stale_after:   # left by a crash
                        self.path.unlink()
                        continue
                except OSError:
                    pass
                time.sleep(0.2)
        return self                                        # couldn't get it: go ahead rather than hang

    def __exit__(self, *exc) -> None:
        if self.held:
            try:
                self.path.unlink()
            except OSError:
                pass


def renew(username: str) -> str | None:
    """A fresh access token if this computer's sign-in token is about to expire (or
    has); None when there's nothing to renew or GitHub couldn't be reached. When the
    refresh token itself is no longer accepted, it's forgotten (sign in again)."""
    import keyring
    from . import auth, tokens
    with _RenewLock():
        record = refresh_record(username)                  # again, inside the lock: another
        if not needs_renewal(record):                      # process may have just renewed it
            return None if record is None else keyring.get_password(auth.SERVICE_NAME, username)
        try:
            data = requests.post(TOKEN_URL, headers=HEADERS, timeout=20, data={
                "client_id": CLIENT_ID, "grant_type": "refresh_token",
                "refresh_token": record["refresh_token"]}).json()
        except (requests.RequestException, ValueError):
            return None                                    # offline: try again next time
        if not data.get("access_token"):
            if data.get("error") in ("bad_refresh_token", "invalid_grant", "unauthorized_client"):
                forget_refresh(username)                   # expired or replaced: sign in again
            return None
        store(data, username)
        tokens.forget()
        return data["access_token"]
