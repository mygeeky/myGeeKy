"""Support email (support.py): read support@mygeeky.org's label read-only, keep users' emails on this computer only,
clean every personal detail before DeepSeek sees anything (a crash report never goes), draft and rework replies, and
send -- as support@mygeeky.org, as a proper reply -- only when send() is called, with the switches obeyed."""
from __future__ import annotations

import json
from email.message import EmailMessage

import pytest

from mygeeky import adminaudit, config, support


def message(sender, subject, body, mid="<m1@example.org>"):
    m = EmailMessage()
    m["From"], m["Subject"], m["Date"], m["Message-ID"] = sender, subject, "Tue, 27 Oct 2026 09:00:00 +0000", mid
    m.set_content(body)
    return m


class Box:
    def __init__(self, msgs):
        self.msgs = msgs

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def recent(self, since=None, cap=60):
        return [(m["Message-ID"], m) for m in self.msgs]


class Smtp:
    def __init__(self):
        self.sent, self.logged = [], None

    def login(self, user, pw):
        self.logged = (user, pw)

    def send_message(self, msg, from_addr=None, to_addrs=None):
        self.sent.append((msg, from_addr, to_addrs))

    def quit(self):
        pass


class Resp:
    def __init__(self, js):
        self._js, self.status_code = js, 200

    def json(self):
        return self._js

    def raise_for_status(self):
        pass


def deepseek(reply, seen):
    def post(url, json=None, timeout=None, headers=None):
        seen.append(json)
        return Resp({"choices": [{"message": {"content": __import__("json").dumps({"reply": reply})}}]})
    return post


BODY = ("Hello, the panel doesn't open since 0.38. My email is rana.k@uni.edu and my phone +44 7700 900123. "
        "Log at C:\\Users\\Rana\\AppData\\Local\\myGeeKy\\log.txt and /home/rana/.config/mygeeky, token "
        "github_pat_11ABCDEFGHIJKLMNOPQRSTUV_xyz, server 192.168.1.20.\n\nTraceback (most recent call last):\n"
        "  File \"C:\\Users\\Rana\\app.py\", line 1\nValueError: secret stuff")


def fetch_one(body=BODY):
    return support.fetch(lambda: Box([message("Dr. Rana K. <rana.k@uni.edu>", "The panel doesn't open", body),
                                      message("myGeeKy support <support@mygeeky.org>", "Re: older", "our own",
                                              "<m0@mygeeky.org>")]))


def test_support_emails_are_read_and_kept_on_this_computer_only():
    out = fetch_one()
    assert out == {"new": 1, "threads": 1}                     # our own reply isn't a support email
    t = support.threads()[0]
    assert t["who"] == "Dr. Rana K." and t["tag"] == "Problem" and t["status"] == "new"
    assert str(support.SUPPORT_FILE).startswith(str(config.LOCAL_DIR)) and not str(support.SUPPORT_FILE).startswith(
        str(config.DATA_DIR) + "/")                             # never in the synced data folder
    assert fetch_one()["new"] == 0                              # read once


def test_nothing_personal_or_secret_reaches_deepseek_and_no_crash_report():
    cleaned = support.redact(BODY)
    for secret in ("rana.k@uni.edu", "7700 900123", "C:\\Users\\Rana", "/home/rana", "github_pat_", "192.168.1.20",
                   "ValueError: secret stuff", "Traceback"):
        assert secret not in cleaned, secret
    assert "panel doesn't open" in cleaned and "[removed]" in cleaned and "crash report" in cleaned
    fetch_one()
    seen: list = []
    tid = support.threads()[0]["id"]
    out = support.ai(tid, "draft", key="sk-test", post=deepseek("Hi Rana,\n\nSorry!\n\nAlsamman", seen))
    assert out["reply"].startswith("Hi Rana")
    sent = json.dumps(seen[0])
    assert "rana.k@uni.edu" not in sent and "github_pat_" not in sent and "secret stuff" not in sent
    support.ai(tid, "shorter", draft="Hi, write me at me@private.example", key="sk-test", post=deepseek("Hi!", seen))
    assert "me@private.example" not in json.dumps(seen[1])      # the draft is cleaned too


def test_sending_is_a_proper_reply_as_support_only_when_asked():
    fetch_one()
    support.set_password("abcd efgh ijkl mnop")
    tid = support.threads()[0]["id"]
    smtp = Smtp()
    with pytest.raises(ValueError):
        support.send(tid, "  ", smtp_factory=lambda: smtp)      # nothing to send
    assert smtp.sent == []
    out = support.send(tid, "Hi Rana,\n\nTry Quit then open it again.\n\nAlsamman", smtp_factory=lambda: smtp)
    msg, frm, to = smtp.sent[0]
    assert out["ok"] and frm == "support@mygeeky.org" and to == ["rana.k@uni.edu"]
    assert msg["Subject"] == "Re: The panel doesn't open" and msg["In-Reply-To"] == "<m1@example.org>"
    assert "support@mygeeky.org" in msg["From"] and smtp.logged[0] == "aalsamman100@gmail.com"
    assert support.threads()[0]["status"] == "answered"
    log = adminaudit.recent()
    assert log[0]["what"] == "Replied to a support email (problem)" and "rana" not in json.dumps(log).lower()


def test_the_switches_are_obeyed():
    fetch_one()
    tid = support.threads()[0]["id"]
    support.settings(send=False, ai=False)
    with pytest.raises(PermissionError):
        support.send(tid, "Hi", smtp_factory=Smtp)
    with pytest.raises(PermissionError):
        support.ai(tid, "draft", key="sk-test", post=deepseek("x", []))
    support.settings(read=False)
    with pytest.raises(PermissionError):
        fetch_one()
    with pytest.raises(ValueError):
        support.settings(send_as="not an address")


def test_a_subject_cannot_inject_headers():
    support.fetch(lambda: Box([message("A <a@b.org>", "Hi", "Question?")]))
    st = support.load()
    tid = next(iter(st["threads"]))
    st["threads"][tid]["subject"] = "Hi\r\nBcc: spy@evil.example"
    support.save(st)
    smtp = Smtp()
    support.send(tid, "Hello", smtp_factory=lambda: smtp)
    msg = smtp.sent[0][0]
    assert msg["Bcc"] is None and "\n" not in msg["Subject"] and smtp.sent[0][2] == ["a@b.org"]
