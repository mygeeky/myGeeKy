"""The maker's listing scout: pick by number, read, check, review, publish (DeepSeek and the web are faked)."""

import json
from datetime import date
from pathlib import Path

import pytest

from mygeeky import config, curated, scout
from mygeeky.config import MyGeekyConfig

TODAY = date(2026, 10, 13)

LISTING = """<html><body><h1>Jobs</h1>
<a href="/job/1/postdoc-statistical-genetics">Postdoc in statistical genetics</a>
<a href="/job/2/chef">Head chef</a>
<a href="/about">About us</a>
<a href="https://\\content.example.org/edit">Edit</a>
</body></html>"""

JOB1 = """<html><body><h1>Postdoc in statistical genetics</h1><p>University of Oslo, Norway.</p>
<p>Work on fine-mapping of GWAS loci.</p><p>Applications close on 1 December 2026.</p></body></html>"""


class FakeResponse:
    def __init__(self, text="", url="", status=200, payload=None):
        self.text, self.url, self.status_code, self._payload = text, url, status, payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self._payload


class FakeWeb:
    pages = {"https://jobs.example.org/search": LISTING, "https://jobs.example.org/job/1/postdoc-statistical-genetics": JOB1}

    def get(self, url, timeout=0, headers=None):
        if url not in self.pages:
            return FakeResponse("", url, 404)
        return FakeResponse(self.pages[url], url)


def fake_deepseek(answers):
    """DeepSeek, faked: the pick prompt gets answers["pick"], a read gets answers[url]."""
    calls = []

    def post(url, json=None, timeout=0, headers=None):
        calls.append(json)
        system, user = json["messages"][0]["content"], json["messages"][1]["content"]
        if "Pick the links" in system:
            out = answers["pick"]
        else:
            page_url = user.split("\n", 1)[0].removeprefix("PAGE: ")
            out = answers.get(page_url, {"is_listing": False})
        return FakeResponse(payload={"choices": [{"message": {"content": __import__("json").dumps(out)}}]})
    post.calls = calls
    return post


GOOD = {"is_listing": True, "title": "Postdoc in statistical genetics", "org": "University of Oslo", "place": "Oslo, Norway",
        "type": "postdoc", "deadline": "2026-12-01", "deadline_quote": "Applications close on 1 December 2026.",
        "keywords": ["gwas", "fine-mapping"], "summary": "Fine-mapping of GWAS loci.", "relevance": 0.9, "confidence": 0.9}
SOURCE = [{"kind": "jobs", "name": "Example jobs", "url": "https://jobs.example.org/search", "on": True}]


def run(answers):
    post = fake_deepseek(answers)
    out = scout.find(MyGeekyConfig(), key="sk-test", session=FakeWeb(), post=post, today=TODAY, sources=SOURCE)
    return out, post


def test_links_are_picked_by_number_so_none_is_invented():
    out, post = run({"pick": {"picks": [{"n": 1}, {"n": 99}, {"n": "x"}]},
                     "https://jobs.example.org/job/1/postdoc-statistical-genetics": GOOD})
    assert out["added"] == 1 and out["seen"] == 1
    listing_prompt = post.calls[0]["messages"][1]["content"]
    assert "[1] Postdoc in statistical genetics -> https://jobs.example.org/job/1/postdoc-statistical-genetics" in listing_prompt
    assert "content.example.org" not in listing_prompt                      # broken links never offered
    assert post.calls[0]["temperature"] == 0
    [c] = scout.candidates(today=TODAY)
    assert c["item"]["url"] == "https://jobs.example.org/job/1/postdoc-statistical-genetics"
    assert c["item"]["deadline"] == "2026-12-01" and c["item"]["org"] == "University of Oslo"
    assert all(ok for ok, _ in c["checks"]) and c["score"] == pytest.approx(0.9)


@pytest.mark.parametrize("change, reason", [
    ({"is_listing": False}, "not a single open listing"),
    ({"deadline": ""}, "no deadline"),
    ({"deadline": "2026-10-14"}, "too close"),
    ({"title": "Something else entirely", "deadline_quote": "made up sentence"}, "neither the title"),
])
def test_failed_checks_drop_the_listing(change, reason):
    out, _ = run({"pick": {"picks": [{"n": 1}]}, "https://jobs.example.org/job/1/postdoc-statistical-genetics": {**GOOD, **change}})
    assert out["added"] == 0 and out["dropped"] == 1


def test_a_quote_that_isnt_on_the_page_lowers_the_score():
    run({"pick": {"picks": [{"n": 1}]},
         "https://jobs.example.org/job/1/postdoc-statistical-genetics": {**GOOD, "deadline_quote": "Deadline: 1 Dec 2026"}})
    [c] = scout.candidates(today=TODAY)
    failed = [t for ok, t in c["checks"] if not ok]
    assert failed == ["deadline sentence is on the page"] and c["score"] < 0.9


def test_dates_are_found_however_they_are_written():
    for q in ("Closing date: 2026-12-01", "1 December 2026", "December 1st, 2026", "deadline 01/12/2026", "Dec 1, 2026"):
        assert scout.date_in(q, "2026-12-01"), q
    assert not scout.date_in("1 November 2026", "2026-12-01")


def test_nothing_is_offered_twice_and_rejects_stay_rejected():
    answers = {"pick": {"picks": [{"n": 1}]}, "https://jobs.example.org/job/1/postdoc-statistical-genetics": GOOD}
    run(answers)
    [c] = scout.candidates(today=TODAY)
    assert scout.set_status(c["id"], "rejected")
    out, _ = run(answers)
    assert out["added"] == 0 and scout.candidates(today=TODAY) == []


def test_accept_with_an_edit_and_merge_into_the_lists():
    run({"pick": {"picks": [{"n": 1}]}, "https://jobs.example.org/job/1/postdoc-statistical-genetics": GOOD})
    [c] = scout.candidates(today=TODAY)
    assert not scout.set_status(c["id"], "accepted", {"url": "http://not-https.org"})     # an edit is checked too
    assert scout.set_status(c["id"], "accepted", {"place": "Oslo"})
    accepted = scout.candidates("accepted", today=TODAY)
    assert accepted[0]["item"]["place"] == "Oslo"
    data = {"version": "2026-01-01T00:00:00Z", "jobs": [
        {"id": "old-job", "title": "Old", "url": "https://x.org/old", "deadline": "2026-01-01"}],
        "funding": [], "conferences": [], "resources": []}
    merged, added = scout.merge(data, accepted, TODAY)
    assert added == 1 and [j["id"] for j in merged["jobs"]] == [accepted[0]["item"]["id"]]   # the past one pruned
    assert curated.problems(merged) == [] and merged["version"] > data["version"]
    again, added = scout.merge(merged, accepted, TODAY)
    assert added == 0 and len(again["jobs"]) == 1


def test_publish_pushes_one_commit_from_a_fresh_copy(tmp_path, monkeypatch):
    run({"pick": {"picks": [{"n": 1}]}, "https://jobs.example.org/job/1/postdoc-statistical-genetics": GOOD})
    [c] = scout.candidates(today=TODAY)
    scout.set_status(c["id"], "accepted")
    git = []

    def fake_git(args, cwd):
        git.append(args[0])
        if args[0] == "clone":
            repo = Path(args[-1])
            (repo / "src/mygeeky/data").mkdir(parents=True)
            (repo / scout.CURATED_PATH).write_text(json.dumps(
                {"version": "2026-01-01T00:00:00Z", "jobs": [], "funding": [], "conferences": [], "resources": []}),
                encoding="utf-8")
        return "abc1234\n"
    monkeypatch.setattr(scout, "_git", fake_git)
    monkeypatch.setattr(scout, "date", type("D", (), {"today": staticmethod(lambda: TODAY)}))
    out = scout.publish()
    assert git == ["clone", "add", "commit", "push", "rev-parse"] and out["published"] == 1
    assert scout.candidates("accepted", today=TODAY) == []
    assert scout.load()["candidates"][c["id"]]["status"] == "published"


def test_the_key_must_look_like_one_and_stays_out_of_files(monkeypatch):
    stored = {}
    import keyring
    monkeypatch.setattr(keyring, "set_password", lambda s, u, k: stored.__setitem__((s, u), k))
    assert not scout.set_key("not a key")
    assert scout.set_key("sk-0123456789abcdef0123")
    assert stored == {(scout.KEY_SERVICE, scout.KEY_USER): "sk-0123456789abcdef0123"}
    path = config.DATA_DIR / "scout.json"
    assert not path.exists() or "sk-" not in path.read_text(encoding="utf-8")


def test_without_a_key_it_says_so():
    with pytest.raises(PermissionError):
        scout.find(MyGeekyConfig(), key="", session=FakeWeb(), post=fake_deepseek({}), sources=SOURCE)
