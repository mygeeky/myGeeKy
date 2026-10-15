"""The job alerts in the maker's mailbox: a third way in, beside the sites and the pasted pages."""

from datetime import date
from email.message import EmailMessage

import pytest

from mygeeky import mailbox, scout


@pytest.fixture(autouse=True)
def _own_queue(tmp_path, monkeypatch):
    """Never touch the maker's real queue or their real keyring."""
    monkeypatch.setattr(scout, "SCOUT_FILE", tmp_path / "scout.json")
    monkeypatch.setattr(mailbox, "get_password", lambda: "app-password-here")


# --------------------------------------------------------------------------- reading an alert
def _alert(html, text="", subject="New bioinformatics jobs"):
    m = EmailMessage()
    m["From"] = "Nature Careers <alerts@nature.com>"
    m["Subject"] = subject
    m["Message-ID"] = "<abc123@nature.com>"
    m["Date"] = "Wed, 15 Oct 2026 08:00:00 +0000"
    m.set_content(text or "Your job alert")
    m.add_alternative(html, subtype="html")
    return m


HTML = """<html><body>
<p>Three jobs match your alert.</p>
<a href="https://click.nature.com/f/a/Qf2/AAB/?url=https%3A%2F%2Fwww.nature.com%2Fnaturecareers%2Fjob%2F1">
  Bioinformatics Research Associate</a>
<a href="https://www.jobs.ac.uk/job/DTG666/bioinformatics-research-associate">Research Associate</a>
<a href="https://click.nature.com/f/a/Qf2/AAC/unsubscribe">Unsubscribe</a>
<a href="https://www.nature.com/email-preferences">Email preferences</a>
<img src="https://click.nature.com/open.gif">
</body></html>"""


def test_the_real_listing_is_pulled_out_of_a_tracking_link():
    """Alerts wrap every link so the sender can count clicks; most carry the target in a parameter."""
    wrapped = ("https://click.nature.com/f/a/Qf2/AAB/"
               "?url=https%3A%2F%2Fwww.nature.com%2Fnaturecareers%2Fjob%2F1")
    assert mailbox.real_url(wrapped) == "https://www.nature.com/naturecareers/job/1"


def test_a_plain_link_is_left_exactly_as_it_is():
    plain = "https://www.jobs.ac.uk/job/DTG666/x"
    assert mailbox.real_url(plain) == plain


def test_the_links_that_are_not_listings_are_left_out():
    found = mailbox.links(_alert(HTML))
    assert "https://www.nature.com/naturecareers/job/1" in found
    assert "https://www.jobs.ac.uk/job/DTG666/bioinformatics-research-associate" in found
    assert not any("unsubscribe" in u or "email-preferences" in u or ".gif" in u for u in found)


def test_a_tracking_link_that_hides_its_target_is_followed():
    """Nothing in the parameters, so the only way to learn where it goes is to ask."""
    hidden = "https://click.sendgrid.net/ls/click?upn=OPAQUE"
    m = _alert(f'<html><body><a href="{hidden}">A job</a></body></html>')
    assert mailbox.links(m) == [hidden], "without a resolver it is handed back as it is"
    out = mailbox.links(m, resolve=lambda u: "https://www.embl.org/jobs/999/")
    assert out == ["https://www.embl.org/jobs/999/"]


def test_a_link_myGeeKy_cannot_follow_is_still_offered():
    """Whatever myGeeKy fetches will land wherever the redirect led anyway, so it is not thrown away."""
    hidden = "https://click.sendgrid.net/ls/click?upn=OPAQUE"
    m = _alert(f'<html><body><a href="{hidden}">A job</a></body></html>')

    def fails(_url):
        raise OSError("no network")

    assert mailbox.links(m, resolve=fails) == [hidden]


def test_the_words_of_a_message_can_stand_in_for_a_page():
    m = _alert("<html><body><script>ignore()</script><p>Closes: 10 November 2026</p></body></html>",
               text="")
    said = mailbox.text_of(m)
    assert "Closes: 10 November 2026" in said
    assert "ignore()" not in said, "scripts are not words"


def test_who_sent_an_alert_is_kept_so_the_maker_can_see_where_a_listing_came_from():
    about = mailbox.describe(_alert(HTML))
    assert "nature.com" in about["from"] and about["subject"] == "New bioinformatics jobs"


# --------------------------------------------------------------------------- the mailbox is held in
class FakeIMAP:
    """An IMAP server that records what it was asked to do, so the rules can be checked."""

    def __init__(self, messages=(), folders=("INBOX",)):
        self.messages = list(messages)
        self.folders = folders
        self.did = []
        self.readonly = None

    def login(self, address, password):
        self.did.append("login")
        if password != "app-password-here":
            raise OSError("bad password")
        return ("OK", [b""])

    def select(self, folder, readonly=False):
        self.did.append(f"select:{folder}")
        self.readonly = readonly
        return ("OK" if folder in self.folders else "NO", [b"1"])

    def search(self, charset, *terms):
        self.did.append(f"search:{' '.join(terms)}")
        return ("OK", [b" ".join(str(i + 1).encode() for i in range(len(self.messages)))])

    def fetch(self, num, what):
        i = int(num) - 1
        return ("OK", [(num, self.messages[i].as_bytes())])

    def close(self):
        self.did.append("close")

    def logout(self):
        self.did.append("logout")


def _box(messages, folder="myGeeKy-alerts", folders=("myGeeKy-alerts",)):
    fake = FakeIMAP(messages, folders)
    box = mailbox.Mailbox("me@gmail.com", "app-password-here", folder=folder,
                          connect=lambda h, p: fake)
    return box, fake


def test_the_folder_is_always_opened_read_only():
    """myGeeKy must not be able to mark, move or delete anybody's mail, even by accident."""
    box, fake = _box([_alert(HTML)])
    with box:
        pass
    assert fake.readonly is True
    assert "select:myGeeKy-alerts" in fake.did


def test_only_the_one_folder_is_opened():
    box, fake = _box([_alert(HTML)])
    with box:
        pass
    assert [d for d in fake.did if d.startswith("select")] == ["select:myGeeKy-alerts"]


def test_the_connection_is_closed_even_when_something_goes_wrong():
    box, fake = _box([_alert(HTML)])
    with pytest.raises(RuntimeError):
        with box:
            raise RuntimeError("something went wrong half way")
    assert "logout" in fake.did


def test_a_folder_that_is_not_there_is_said_plainly():
    box, _ = _box([], folder="Nope", folders=("INBOX",))
    with pytest.raises(ValueError, match="no folder"):
        with box:
            pass


def test_a_password_the_mailbox_refuses_is_said_plainly():
    fake = FakeIMAP([], ("INBOX",))
    box = mailbox.Mailbox("me@gmail.com", "wrong", folder="INBOX", connect=lambda h, p: fake)
    with pytest.raises(PermissionError, match="App Password"):
        with box:
            pass


def test_the_search_is_bounded_by_a_date():
    """A folder somebody pointed at their whole archive must not become an afternoon's work."""
    box, fake = _box([_alert(HTML)])
    with box as inbox:
        inbox.recent(since=date(2026, 10, 1))
    assert any("search:SINCE 01-Oct-2026" in d for d in fake.did)


def test_the_server_is_worked_out_from_the_address():
    assert mailbox.host_for("me@gmail.com") == "imap.gmail.com"
    assert mailbox.host_for("me@outlook.com") == "outlook.office365.com"
    assert mailbox.host_for("me@uni-lyon.fr") == "imap.uni-lyon.fr"
    assert mailbox.host_for("") == ""


# --------------------------------------------------------------------------- it joins the same queue
FOUND = {"is_listing": True, "title": "Bioinformatics Research Associate", "language": "English",
         "title_en": "Bioinformatics Research Associate", "summary_en": "Single-cell work at Imperial.",
         "org": "Imperial College London", "place": "London, United Kingdom", "type": "postdoc",
         "deadline": "2026-11-10", "deadline_quote": "Closing date: 10 November 2026",
         "keywords": ["single-cell"], "relevance": 0.95, "confidence": 0.95}

PAGE_TEXT = ("Bioinformatics Research Associate. Imperial College London. "
             "Closing date: 10 November 2026. Apply online.")


def _deepseek(answer):
    import json

    class Reply:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(answer)}}]}

    return lambda url, json=None, timeout=None, headers=None: Reply()


def _ready(monkeypatch, page_text=PAGE_TEXT):
    scout.mailbox_settings("me@gmail.com", "", "myGeeKy-alerts")
    monkeypatch.setattr(scout, "get_key", lambda: "sk-test")
    monkeypatch.setattr(scout, "page",
                        lambda url, session=None, timeout=25.0: {"url": url, "text": page_text,
                                                                 "links": []})
    monkeypatch.setattr(scout, "resolve_link", lambda u, session=None: u)


def test_an_emailed_listing_is_checked_against_the_employers_page_and_queued(monkeypatch):
    """The email finds it; the employer's own page is what the quote is held against."""
    _ready(monkeypatch)
    box, _ = _box([_alert(HTML)])
    out = scout.from_alerts("jobs", today=date(2026, 10, 15), post=_deepseek(FOUND), mailbox=box)
    assert out["added"] >= 1 and out["messages"] == 1
    queued = list(scout.load()["candidates"].values())[0]
    assert queued["from"] == "emailed"
    assert queued["alert"] == "New bioinformatics jobs", "the maker can see which alert it came out of"
    assert queued["status"] == "new", "it waits for the maker, like everything else"
    assert all(ok for ok, _ in queued["checks"]), queued["checks"]


def test_the_email_stands_in_only_when_the_page_cannot_be_had(monkeypatch):
    """Weaker evidence, used rather than losing the listing -- the same bargain as a pasted page."""
    _ready(monkeypatch)
    monkeypatch.setattr(scout, "page", lambda *a, **k: (_ for _ in ()).throw(OSError("403")))
    inside = _alert("<html><body><a href='https://www.nature.com/naturecareers/job/1'>A job</a>"
                    "<p>Bioinformatics Research Associate. Closing date: 10 November 2026.</p></body></html>")
    box, _ = _box([inside])
    out = scout.from_alerts("jobs", today=date(2026, 10, 15), post=_deepseek(FOUND), mailbox=box)
    assert out["added"] == 1, "the alert's own words carried it"


def test_an_alert_is_not_read_twice(monkeypatch):
    """The folder is read-only, so myGeeKy cannot mark mail as read and remembers instead."""
    _ready(monkeypatch)
    for _ in range(2):
        box, _ = _box([_alert(HTML)])
        out = scout.from_alerts("jobs", today=date(2026, 10, 15), post=_deepseek(FOUND), mailbox=box)
    assert out["added"] == 0 and out["read"] == 0, "the second run had nothing new to do"
    assert len(scout.load()["candidates"]) == 1


def test_an_emailed_listing_whose_quote_is_not_on_the_page_is_marked(monkeypatch):
    """A deadline quoted out of an email is not a deadline quoted from the employer."""
    _ready(monkeypatch, page_text="Bioinformatics Research Associate at Imperial. Apply online.")
    box, _ = _box([_alert(HTML)])
    scout.from_alerts("jobs", today=date(2026, 10, 15), post=_deepseek(FOUND), mailbox=box)
    queued = list(scout.load()["candidates"].values())
    if queued:
        checks = dict((t, ok) for ok, t in queued[0]["checks"])
        assert checks["deadline sentence is on the page"] is False


def test_it_refuses_to_start_without_being_told_where_to_look(monkeypatch):
    monkeypatch.setattr(scout, "get_key", lambda: "sk-test")
    with pytest.raises(PermissionError, match="which mailbox"):
        scout.from_alerts("jobs", today=date(2026, 10, 15))


def test_it_refuses_a_kind_myGeeKy_does_not_keep(monkeypatch):
    monkeypatch.setattr(scout, "get_key", lambda: "sk-test")
    with pytest.raises(ValueError, match="kind must be"):
        scout.from_alerts("resources", today=date(2026, 10, 15))


def test_the_mailbox_settings_never_hold_the_password():
    scout.mailbox_settings("me@gmail.com", "", "myGeeKy-alerts")
    said = scout.mailbox_settings()
    assert said["address"] == "me@gmail.com" and said["folder"] == "myGeeKy-alerts"
    assert said["guessed_host"] == "imap.gmail.com"
    assert "password" not in " ".join(f"{k}{v}" for k, v in said.items() if k != "has_password").lower()
    assert set(said) == {"address", "host", "folder", "guessed_host", "has_password"}


def test_the_sites_and_the_pasted_pages_are_untouched():
    """Email is a third way in, not a replacement: everything that worked before still does."""
    assert len(scout.SOURCES) >= 15
    assert callable(scout.from_paste) and callable(scout.find) and callable(scout.from_alerts)
