"""Sign in with ORCID: proves which ORCID iD is yours, with no myGeeKy server.

ORCID's "implicit" sign-in needs no secret (myGeeKy is open source, so it
couldn't keep one). ORCID only sends people back to a registered https page,
so it returns to https://mygeeky.org/orcid/, a static page that passes the
answer on to this computer (http://127.0.0.1:<port>, where `sign_in` waits).
The answer is a 10-minute token that can only say who you are: myGeeKy asks
ORCID once whose it is, keeps the iD and name, and forgets the token.
"""
from __future__ import annotations

import html
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urlparse

import requests

# The public ORCID API client registered for myGeeKy (public by nature: it is in every copy).
CLIENT_ID = "APP-18BCI2EHRCBFQ3O7"
AUTHORIZE_URL = "https://orcid.org/oauth/authorize"
USERINFO_URL = "https://orcid.org/oauth/userinfo"
RELAY_URL = "https://mygeeky.org/orcid/"
WAIT_SECONDS = 300
ORCID_ID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")


class OrcidLoginError(Exception):
    """A sign-in that didn't finish, in plain words."""


def available() -> bool:
    return bool(CLIENT_ID)


def checksum_ok(orcid: str) -> bool:
    """ORCID's last character is a check digit (ISO 7064 11,2): catches most typos."""
    if not ORCID_ID_RE.match(orcid or ""):
        return False
    digits = orcid.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    return digits[-1] == ("X" if check == 10 else str(check))


def authorize_url(state: str, nonce: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": CLIENT_ID, "response_type": "token", "scope": "openid",
        "redirect_uri": RELAY_URL, "state": state, "nonce": nonce})


def who(token: str) -> dict[str, str]:
    """Ask ORCID whose token this is: {'orcid', 'name'}."""
    try:
        r = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                         timeout=20)
    except requests.RequestException as exc:
        raise OrcidLoginError("Couldn't reach ORCID to finish the sign-in. Check the internet and try again.") from exc
    if r.status_code != 200:
        raise OrcidLoginError("ORCID didn't confirm the sign-in. Try again.")
    info = r.json()
    orcid = str(info.get("sub") or "")
    if not checksum_ok(orcid):
        raise OrcidLoginError("ORCID answered with something that isn't an ORCID iD.")
    name = str(info.get("name") or " ".join(x for x in (info.get("given_name"), info.get("family_name")) if x))
    return {"orcid": orcid, "name": name.strip()}


DONE_PAGE = """<!doctype html><meta charset="utf-8"><title>myGeeKy</title>
<body style="font-family:system-ui,sans-serif;background:#12121c;color:#eee;display:grid;place-items:center;height:90vh">
<div style="text-align:center"><h2 style="color:#ff6fd8">{title}</h2><p>{text}</p></div></body>"""


def _wait_for_answer(secret: str, open_page: Callable[[str], None], timeout: float) -> dict[str, str]:
    """A one-shot listener on 127.0.0.1: the relay page sends the browser here.
    The state says where to (d<port>) and carries a secret only this run knows."""
    answer: dict[str, str] = {}
    got = threading.Event()
    expected: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path != "/orcid" or not secrets.compare_digest(q.get("state", ""), expected["state"]):
                self.send_response(404)
                self.end_headers()
                return
            answer.update(q)
            ok = bool(q.get("access_token"))
            body = DONE_PAGE.format(
                title="Signed in with ORCID" if ok else "Not signed in",
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
    expected["state"] = f"d{server.server_address[1]}-{secret}"
    try:
        open_page(expected["state"])
        deadline = threading.Event()
        timer = threading.Timer(timeout, deadline.set)
        timer.daemon = True
        timer.start()
        while not got.is_set() and not deadline.is_set():
            server.handle_request()
        timer.cancel()
    finally:
        server.server_close()
    if not answer:
        raise OrcidLoginError("The sign-in took too long. Try again.")
    return answer


def sign_in(timeout: float = WAIT_SECONDS, open_browser: Callable[[str], Any] = webbrowser.open) -> dict[str, str]:
    """Open ORCID in the browser, wait for the answer, return {'orcid', 'name'}."""
    if not available():
        raise OrcidLoginError("Sign in with ORCID isn't set up in this version. Type your ORCID iD instead.")
    secret = secrets.token_urlsafe(16)
    nonce = secrets.token_urlsafe(16)

    def open_page(state: str) -> None:
        open_browser(authorize_url(state, nonce))

    answer = _wait_for_answer(secret, open_page, timeout)
    if not answer.get("access_token"):
        if answer.get("error") == "access_denied":
            raise OrcidLoginError("You cancelled the sign-in on ORCID.")
        raise OrcidLoginError(answer.get("error_description") or "ORCID didn't sign you in. Try again.")
    return who(answer["access_token"])
