# Reading the job alerts the maker already subscribes to.
#
# Nature Careers, Science Careers, jobs.ac.uk, EURAXESS -- and LinkedIn, Indeed and Glassdoor, which refuse
# a robot on their sites -- will all email you their listings if you ask them to. That email was sent TO
# you, because you subscribed, so nothing about reading it is blocked or forbidden: no 403, no CAPTCHA, no
# terms about robots on somebody's site. It is a third way in beside the sites myGeeKy can read and the
# pages the maker pastes, not a replacement for either.
#
# This is the maker's own mailbox, on the maker's own machine, feeding the same review queue everything
# else feeds. It never runs for anyone else, and users only ever see what the maker publishes -- which is
# what keeps "nobody learns what you looked at" true of myGeeKy itself.
#
# Three rules hold it in:
#
#   1. ONE FOLDER. myGeeKy opens the label you point it at and nothing else. Make a mail filter that sends
#      the alerts there; if the filter is wrong, myGeeKy sees nothing, rather than everything.
#   2. READ-ONLY, always. The mailbox is selected with readonly=True, so myGeeKy cannot mark, move or
#      delete a message even by accident. Which is why messages already read are remembered here instead.
#   3. THE PASSWORD LIVES IN THE KEYRING. Never in a file, never in the lists, never printed.
from __future__ import annotations

import email
import imaplib
import re
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.message import Message
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

KEY_SERVICE = "mygeeky-mailbox"
KEY_USER = "maker"
MAX_MESSAGES = 60          # one run reads at most this many, newest first
MAX_LINKS = 40             # links taken from any one message
LOOK_BACK_DAYS = 21        # older alerts are about listings that have closed
HOSTS = {                  # the usual ones, so nobody has to know what IMAP is
    "gmail.com": "imap.gmail.com", "googlemail.com": "imap.gmail.com",
    "outlook.com": "outlook.office365.com", "hotmail.com": "outlook.office365.com",
    "live.com": "outlook.office365.com", "office365.com": "outlook.office365.com",
    "yahoo.com": "imap.mail.yahoo.com", "icloud.com": "imap.mail.me.com",
    "me.com": "imap.mail.me.com", "proton.me": "127.0.0.1",      # Proton needs its local bridge
}
# Links in an alert that are never a listing
_SKIP = re.compile(r"unsubscribe|email-preferences|manage-alerts|privacy|terms|\.(png|gif|jpe?g|css)$"
                   r"|mailto:|/account|/login|/signin|facebook\.com|twitter\.com|x\.com|linkedin\.com/shar",
                   re.I)
_HREF = re.compile(r"""href\s*=\s*["']([^"'>\s]+)["']""", re.I)
_BARE = re.compile(r"https://[^\s<>\"')\]]+")             # links written out in a plain-text email
_TAG = re.compile(r"<[^>]+>")
_DROP = re.compile(r"<(script|style|head)\b.*?</\1>", re.S | re.I)


# --------------------------------------------------------------------------- the password
# each mailbox myGeeKy reads has its own entry: the job alerts (this one), TRACE's trigger inbox (trace.py) and
# support@ (support.py)
def get_password(service: str = KEY_SERVICE) -> str | None:
    try:
        import keyring
        return keyring.get_password(service, KEY_USER)
    except Exception:
        return None


def set_password(password: str, service: str = KEY_SERVICE) -> bool:
    """Keep the mailbox password in this computer's credential store. Never anywhere else."""
    password = (password or "").strip().replace(" ", "")      # Google prints app passwords in four blocks
    if len(password) < 8:
        return False
    import keyring
    keyring.set_password(service, KEY_USER, password)
    return True


def forget_password(service: str = KEY_SERVICE) -> None:
    try:
        import keyring
        keyring.delete_password(service, KEY_USER)
    except Exception:
        pass


def sender_address(message: Message) -> str:
    """The bare address a message says it is from, lower case ("" if none)."""
    from email.utils import parseaddr
    return parseaddr(_words(message.get("From")))[1].strip().lower()


def host_for(address: str) -> str:
    """The IMAP server an address most likely uses, so the maker need not look it up."""
    domain = str(address or "").rpartition("@")[2].strip().lower()
    return HOSTS.get(domain, f"imap.{domain}" if domain else "")


# --------------------------------------------------------------------------- what a message gives us
def _words(value: Any) -> str:
    try:
        return str(make_header(decode_header(str(value or ""))))
    except Exception:
        return str(value or "")


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", _DROP.sub(" ", html))).strip()


def text_of(message: Message) -> str:
    """Everything a message says, as plain words.

    Whichever part says MORE wins, rather than the plain-text one on principle: plenty of alerts put a
    stub there ("Your job alert — view it in your browser") and the listings themselves in the HTML, and
    taking the stub would throw the message away while appearing to read it."""
    said: list[str] = []
    for part in message.walk() if message.is_multipart() else [message]:
        kind = (part.get_content_type() or "").lower()
        if kind not in ("text/plain", "text/html"):
            continue
        try:
            body = part.get_payload(decode=True)
            body = body.decode(part.get_content_charset() or "utf-8", "replace") if body else ""
        except Exception:
            continue
        said.append(re.sub(r"\s+", " ", body).strip() if kind == "text/plain" else _plain(body))
    return max(said, key=len).strip() if said else ""


def real_url(url: str) -> str:
    """The listing behind a tracking link, where it can be had without asking anyone.

    Alert emails wrap every link so the sender can count the clicks. Most of them carry the real address
    in a query parameter, which costs nothing to read; the rest have to be followed, which `links` does."""
    for key in ("url", "u", "target", "dest", "destination", "redirect", "r", "link", "l"):
        for value in parse_qs(urlsplit(url).query).get(key, []):
            candidate = unquote(value)
            if candidate.startswith("https://") and not _SKIP.search(candidate):
                return candidate
    return url


def links(message: Message, resolve=None, cap: int = MAX_LINKS) -> list[str]:
    """The https links in a message that might each be a listing, in the order they appear.

    `resolve` follows a tracking link that hides its target; left out, such links are returned as they
    are, and whatever myGeeKy fetches will be the page the redirect lands on anyway."""
    out: list[str] = []
    parts = [p for p in (message.walk() if message.is_multipart() else [message])
             if (p.get_content_type() or "").lower() in ("text/html", "text/plain")]
    has_html = any((p.get_content_type() or "").lower() == "text/html" for p in parts)
    for part in parts:
        html = (part.get_content_type() or "").lower() == "text/html"
        if has_html and not html:
            continue                                   # the HTML part has the real links (plain text may be a stub)
        try:
            body = part.get_payload(decode=True)
            body = body.decode(part.get_content_charset() or "utf-8", "replace") if body else ""
        except Exception:
            continue
        for href in (_HREF.findall(body) if html else _BARE.findall(body)):
            url = href.replace("&amp;", "&").strip()
            if not url.startswith("https://") or _SKIP.search(url):
                continue
            url = real_url(url)
            if resolve is not None and _looks_tracked(url):
                try:
                    url = resolve(url) or url
                except Exception:
                    pass
            if _SKIP.search(url) or url in out:
                continue
            out.append(url)
            if len(out) >= cap:
                return out
    return out


def _looks_tracked(url: str) -> bool:
    """A link whose host is about counting clicks rather than about a job."""
    host = urlsplit(url).netloc.lower()
    return bool(re.search(r"click|track|link|email|mandrill|sendgrid|mailchimp|sparkpost|list-manage",
                          host))


# --------------------------------------------------------------------------- the mailbox itself
class Mailbox:
    """One folder of one mailbox, opened read-only.

    Used as a context manager so the connection is always closed, including when something goes wrong
    half-way through a run."""

    def __init__(self, address: str, password: str, host: str = "", folder: str = "INBOX",
                 port: int = 993, connect=None) -> None:
        self.address = address
        self.host = host or host_for(address)
        self.folder = folder or "INBOX"
        self._password = password
        self.port = port
        self._connect = connect or (lambda h, p: imaplib.IMAP4_SSL(h, p))
        self.imap: Any = None

    def __enter__(self) -> Mailbox:
        if not self.address or not self._password:
            raise PermissionError("Add your mailbox address and password first")
        if not self.host:
            raise ValueError("myGeeKy could not work out your mail server; type it in")
        self.imap = self._connect(self.host, self.port)
        try:
            self.imap.login(self.address, self._password)
        except Exception as exc:
            raise PermissionError("The mailbox did not accept that address and password. For Gmail you "
                                  "need an App Password, not your everyday one.") from exc
        ok, _ = self.imap.select(self.folder, readonly=True)      # read-only: nothing can be changed
        if ok != "OK":
            raise ValueError(f"There is no folder called {self.folder!r} in that mailbox")
        return self

    def __exit__(self, *_: Any) -> None:
        for step in ("close", "logout"):
            try:
                getattr(self.imap, step)()
            except Exception:
                pass

    def recent(self, since: date | None = None, cap: int = MAX_MESSAGES) -> list[tuple[str, Message]]:
        """(message id, message) for the newest alerts in the folder, newest first.

        Everything is bounded: a date to look back to and a count, so a folder somebody pointed at their
        whole archive cannot turn into an afternoon's work."""
        since = since or (date.today() - timedelta(days=LOOK_BACK_DAYS))
        ok, data = self.imap.search(None, "SINCE", since.strftime("%d-%b-%Y"))
        if ok != "OK" or not data or not data[0]:
            return []
        out = []
        for num in reversed(data[0].split()[-cap * 2:]):
            ok, raw = self.imap.fetch(num, "(RFC822)")
            if ok != "OK" or not raw or not isinstance(raw[0], tuple):
                continue
            try:
                message = email.message_from_bytes(raw[0][1])
            except Exception:
                continue
            mid = _words(message.get("Message-ID")) or f"{self.folder}:{num.decode('ascii', 'replace')}"
            out.append((mid, message))
            if len(out) >= cap:
                break
        return out


def describe(message: Message) -> dict[str, str]:
    """Who sent an alert and what it was called, for the maker to see what a listing came out of."""
    return {"from": _words(message.get("From")), "subject": _words(message.get("Subject")),
            "date": _words(message.get("Date"))}
