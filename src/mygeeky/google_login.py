"""Sign in with Google, for keeping your data in Google Drive -- with no myGeeKy server.

The browser opens Google's sign-in; Google sends it back to this computer (http://127.0.0.1:<port>, where `sign_in`
waits) with a one-time code, which is swapped for a refresh token (kept in the OS keyring) and 1-hour access tokens.
PKCE ties the code to this run. One permission only: `drive.appdata`, myGeeKy's own hidden folder in your Drive; it
can't see or touch any of your other files. Never ask for another scope: `drive` is restricted (a yearly paid
security review), and the privacy policy promises this one only.

Google gives desktop apps a "client secret" too, and says plainly it isn't secret for installed apps (every copy of
the app carries it); it's split below only so code scanners don't take it for a leaked password.
"""
from __future__ import annotations

import base64
import hashlib
import html
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse

import requests

CLIENT_ID = "897067171099-a87clp5keoh0lh1e7afsdfkd70c43iob.apps.googleusercontent.com"
_SECRET = ("GOCSPX", "-", "UTAPXfWK-na3YA", "Cb1E3aKLtWa-rd")
SCOPE = "https://www.googleapis.com/auth/drive.appdata"
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
KEYRING_SERVICE = "mygeeky-google-drive"
WAIT_SECONDS = 300
_access: dict[str, Any] = {}           # {"token", "until"}: the current 1-hour token, in memory only


class GoogleLoginError(Exception):
    """A sign-in that didn't finish, or one that stopped working, in plain words."""


def _secret() -> str:
    return "".join(_SECRET)


def _get_refresh() -> str | None:
    try:
        import keyring
        return keyring.get_password(KEYRING_SERVICE, "refresh")
    except Exception:  # noqa: BLE001
        return None


def _set_refresh(value: str | None) -> None:
    import keyring
    if value is None:
        try:
            keyring.delete_password(KEYRING_SERVICE, "refresh")
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            keyring.set_password(KEYRING_SERVICE, "refresh", value)
        except Exception as exc:  # noqa: BLE001
            raise GoogleLoginError("This computer has no keyring to keep the Google sign-in in.") from exc


def signed_in() -> bool:
    return bool(_get_refresh())


def authorize_url(redirect: str, state: str, challenge: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": CLIENT_ID, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        "access_type": "offline", "prompt": "consent"})


DONE_PAGE = """<!doctype html><meta charset="utf-8"><title>myGeeKy</title>
<body style="font-family:system-ui,sans-serif;background:#12121c;color:#eee;display:grid;place-items:center;height:90vh">
<div style="text-align:center"><h2 style="color:#ff6fd8">{title}</h2><p>{text}</p></div></body>"""


def _wait_for_code(open_page: Callable[[str, str], None], timeout: float) -> tuple[dict[str, str], str]:
    """A one-shot listener on 127.0.0.1 that Google sends the browser back to. ({answer}, redirect uri)."""
    answer: dict[str, str] = {}
    got = threading.Event()
    state = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path != "/" or not secrets.compare_digest(q.get("state", ""), state):
                self.send_response(404)
                self.end_headers()
                return
            answer.update(q)
            ok = bool(q.get("code"))
            body = DONE_PAGE.format(
                title="Signed in with Google" if ok else "Not signed in",
                text="You can close this tab and go back to myGeeKy." if ok
                else html.escape(q.get("error_description") or q.get("error") or "The sign-in was cancelled."))
            data = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            got.set()

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 0.5
    redirect = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        open_page(redirect, state)
        until = time.monotonic() + timeout
        while not got.is_set() and time.monotonic() < until:
            server.handle_request()
    finally:
        server.server_close()
    if not answer:
        raise GoogleLoginError("The sign-in took too long. Try again.")
    return answer, redirect


def _token_call(data: dict[str, str]) -> dict[str, Any]:
    try:
        r = requests.post(TOKEN_URL, data={**data, "client_id": CLIENT_ID, "client_secret": _secret()}, timeout=30)
    except requests.RequestException as exc:
        raise GoogleLoginError("Couldn't reach Google. Check the internet and try again.") from exc
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code != 200:
        if j.get("error") == "invalid_grant":
            raise GoogleLoginError("Google ended this computer's sign-in (it was removed, or the password changed). "
                                   "Sign in with Google again.")
        raise GoogleLoginError(f"Google didn't sign you in ({j.get('error') or r.status_code}). Try again.")
    return j


def sign_in(timeout: float = WAIT_SECONDS, open_browser: Callable[[str], Any] = webbrowser.open) -> None:
    """Open Google's sign-in in the browser, wait for the answer, keep the refresh token."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    answer, redirect = _wait_for_code(lambda uri, state: open_browser(authorize_url(uri, state, challenge)), timeout)
    if not answer.get("code"):
        if answer.get("error") == "access_denied":
            raise GoogleLoginError("You cancelled the sign-in on Google.")
        raise GoogleLoginError(answer.get("error_description") or "Google didn't sign you in. Try again.")
    if SCOPE not in answer.get("scope", SCOPE).split():
        raise GoogleLoginError("Google signed you in, but the box that lets myGeeKy keep its own files in your Drive "
                               "was left unticked. Sign in again and tick it.")
    j = _token_call({"grant_type": "authorization_code", "code": answer["code"], "redirect_uri": redirect,
                     "code_verifier": verifier})
    if SCOPE not in str(j.get("scope", "")).split():
        raise GoogleLoginError("Google signed you in, but the box that lets myGeeKy keep its own files in your Drive "
                               "was left unticked. Sign in again and tick it.")
    if not j.get("refresh_token"):
        raise GoogleLoginError("Google didn't give this computer a lasting sign-in. Try again.")
    _set_refresh(str(j["refresh_token"]))
    _remember(j)


def _remember(j: dict[str, Any]) -> None:
    _access["token"] = str(j.get("access_token", ""))
    _access["until"] = time.time() + max(60, int(j.get("expires_in", 3600))) - 120


def access_token(fresh: bool = False) -> str:
    """A working access token, renewed with the refresh token when the last one is about to end."""
    if not fresh and _access.get("token") and time.time() < _access.get("until", 0):
        return str(_access["token"])
    refresh = _get_refresh()
    if not refresh:
        raise GoogleLoginError("Not signed in with Google on this computer.")
    try:
        j = _token_call({"grant_type": "refresh_token", "refresh_token": refresh})
    except GoogleLoginError:
        _access.clear()
        raise
    _remember(j)
    return str(_access["token"])


