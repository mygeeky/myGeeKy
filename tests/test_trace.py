"""TRACE (trace.py): its statistics on their own, then whole runs against fake feeds, a fake inbox and a fake
DeepSeek -- a new video becomes one checked item in Review, the same story again corroborates instead of costing, a
link the AI made up never gets in, only allowed senders count, the budget holds (and what's left waits), the maker's
decisions teach the sources and the model, and accepted news is published into What's new."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from mygeeky import scout, trace, whatsnew_shape

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
CHANNEL = "UC" + "a" * 22

YT_FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
 <entry><id>yt:video:abc123</id><title>A 1B model beats 70B models at maths</title>
  <link rel="alternate" href="https://www.youtube.com/watch?v=abc123"/>
  <published>2026-10-27T10:00:00+00:00</published>
  <media:group><media:description>A new small language model release from Example Labs beats much larger models on maths benchmarks.</media:description></media:group>
 </entry>
</feed>""".encode()
PAGE = ("<html><body><h1>A 1B model beats 70B models at maths</h1><p>Example Labs released a small language model "
        "that beats 70B models at maths benchmarks.</p></body></html>")


class Resp:
    def __init__(self, body=b"", status=200, js=None, url=""):
        self.content = body if isinstance(body, bytes) else body.encode()
        self.text = self.content.decode("utf-8", "replace")
        self.status_code, self._js, self.url = status, js, url

    def json(self):
        return self._js if self._js is not None else json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class Web:
    """The internet, faked: the channel's feed, the video page, Hacker News and arXiv."""

    def __init__(self, feed=YT_FEED):
        self.feed, self.calls = feed, []

    def get(self, url, params=None, timeout=None, headers=None, **kw):
        self.calls.append(url)
        if "youtube.com/feeds" in url:
            return Resp(self.feed)
        if url.startswith("https://www.youtube.com/watch"):
            return Resp(PAGE, url=url)
        if "hn.algolia.com" in url:
            return Resp(js={"hits": [{"title": "A 1B model beats 70B models at maths, says Example Labs",
                                      "url": "https://example-labs.ai/blog/small-model", "objectID": "1"}]})
        if "export.arxiv.org" in url:
            return Resp(b"<feed xmlns='http://www.w3.org/2005/Atom'></feed>")
        return Resp(b"", status=404)


def deepseek(answer: dict, seen: list | None = None):
    def post(url, json=None, timeout=None, headers=None):
        if seen is not None:
            seen.append(json)
        return Resp(js={"choices": [{"message": {"content": __import__("json").dumps(answer)}}]})
    return post


GOOD = {"is_news": True, "title": "A 1B model beats 70B models at maths",
        "summary": "Example Labs released a small language model.", "why": "Small models are cheaper to run.",
        "topic": "small language models", "keywords": ["llm", "small models"],
        "links": ["https://www.youtube.com/watch?v=abc123", "https://example-labs.ai/blog/small-model",
                  "https://phish.example/claim"]}


# ---- the statistics
def test_a_feed_is_checked_as_often_as_it_posts():
    weekly = trace.post_rate(posts=4, hours=24 * 28)
    hourly = trace.post_rate(posts=300, hours=300)
    assert trace.check_every(weekly) == trace.CHECK_MAX_H and trace.check_every(hourly) == trace.CHECK_MIN_H
    assert trace.CHECK_MIN_H < trace.check_every(trace.post_rate(10, 100)) < trace.CHECK_MAX_H


def test_a_source_earns_trust_and_its_range_narrows():
    new, proven = trace.record(0, 0), trace.record(40, 10)
    assert new["mean"] == 0.5 and new["hi"] - new["lo"] > 0.5
    assert 0.75 < proven["mean"] < 0.82 and proven["hi"] - proven["lo"] < 0.25 and proven["n"] == 50


def test_same_story_and_grounding():
    assert trace.same_story("OpenAI releases GPT-6 model", "GPT-6 model released by OpenAI")
    assert not trace.same_story("OpenAI releases GPT-6", "AlphaFold 4 predicts protein complexes")
    assert trace.grounded("Small model beats giants at maths", "a small model beats the giants on maths") == 1.0
    assert trace.grounded("Quantum computer breaks RSA", "a small model beats giants") == 0.0


def test_it_searches_on_a_titles_key_terms():
    assert trace.key_terms("Gemini 4 Argon Is Not What I Expected") == ["Gemini", "4", "Argon"]
    assert trace.key_terms("A 1B model beats 70B models at maths") == ["1B", "70B"]
    assert trace.key_terms("the and of") == []


def test_the_model_learns_from_decisions():
    w = dict(trace.START_WEIGHTS)
    good = {"grounded": 1.0, "corroboration": 0.7, "source": 0.8, "fresh": 1.0, "linked": 1.0, "duplicate": 0.0}
    bad = {"grounded": 0.2, "corroboration": 0.0, "source": 0.3, "fresh": 1.0, "linked": 1.0, "duplicate": 0.0}
    before = trace.p_accept(good, w) - trace.p_accept(bad, w)
    for _ in range(30):
        w = trace.learn(w, good, True)
        w = trace.learn(w, bad, False)
    assert trace.p_accept(good, w) > 0.8 and trace.p_accept(bad, w) < 0.25
    assert trace.p_accept(good, w) - trace.p_accept(bad, w) > before


def test_the_budget_goes_to_the_best_with_a_share_for_new_sources():
    sources = {"old": {"acc": 30, "rej": 3}, "weak": {"acc": 2, "rej": 30}, "new": {}}
    trig = [{"id": str(i), "sid": sid, "worth": trace.worth(sources[sid], 1.0)} for i, sid in
            enumerate(["old", "old", "weak", "new", "weak", "old"])]
    picked = trace.allocate(trig, 3, 0.34, sources, random.Random(1))
    assert len(picked) == 3 and any(t["sid"] == "new" for t in picked) and sum(t["sid"] == "old" for t in picked) == 2
    assert trace.allocate(trig, 0, 0.1, sources) == []


def test_rising_and_calibration():
    counts = {f"2026-10-{d:02d}": 2 for d in range(13, 26)}
    counts["2026-10-26"] = 9
    r = trace.rising(counts, "2026-10-26")
    assert r["ratio"] > 3 and r["z"] > 3
    assert trace.rising(counts, "2026-10-25")["ratio"] == pytest.approx(1.0, abs=0.01)
    dec = [{"p": 0.9, "accepted": True}] * 9 + [{"p": 0.9, "accepted": False}] + [{"p": 0.1, "accepted": False}] * 10
    cal = {round(c["p"], 1): c["actual"] for c in trace.calibration(dec)}
    assert cal[0.9] == 0.9 and cal[0.1] == 0.0


def test_urgency_and_freshness():
    assert trace.urgency("jobs", "2026-10-28", NOW) == 0.0            # gone (or too close) is worth nothing
    assert trace.urgency("jobs", "2026-11-05", NOW) > trace.urgency("jobs", "2027-03-01", NOW) >= 1.0
    assert trace.urgency("news") == 1.0


# ---- feeds are untrusted
def test_feeds_parse_and_refuse_tricks():
    entries = trace.parse_feed(YT_FEED)
    assert entries[0]["url"] == "https://www.youtube.com/watch?v=abc123" and "small language model" in entries[0]["summary"]
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
    assert trace.parse_feed(bomb) == []
    js = b"<rss><channel><item><title>x</title><link>javascript:alert(1)</link></item></channel></rss>"
    assert trace.parse_feed(js) == []
    assert trace.parse_feed(b"x" * (trace.MAX_FEED_BYTES + 1)) == []
    with pytest.raises(ValueError):
        trace.feed_url("youtube", "not-a-channel")
    assert trace.feed_url("arxiv", "cs.LG").startswith("https://export.arxiv.org/")


# ---- whole runs
def _setup():
    trace.add_feed("youtube", CHANNEL, "Two Minute Papers", "news")


def test_a_new_video_becomes_one_checked_item_and_a_made_up_link_never_gets_in():
    _setup()
    seen: list = []
    out = trace.run(key="sk-test", now=NOW, session=Web(), post=deepseek(GOOD, seen), rng=random.Random(0))
    assert out["triggers"] == 1 and out["items"] == 1 and out["spent"] == 1
    item = trace.queue()[0]
    assert item["title"] == GOOD["title"] and "https://phish.example/claim" not in item["sources"]
    assert {trace.host(u) for u in item["sources"]} == {"youtube.com", "example-labs.ai"}       # corroborated
    assert item["grounded"] >= 0.8 and 0 < item["p"] < 1 and all(ok for ok, _ in item["checks"][:3])
    prompt = seen[0]["messages"][1]["content"]
    assert "phish" not in prompt and "LINKS:" in prompt                     # only links myGeeKy fetched are offered
    again = trace.run(key="sk-test", now=NOW + timedelta(hours=2), session=Web(), post=deepseek(GOOD), rng=random.Random(0))
    assert again["triggers"] == 0 and again["spent"] == 1                   # nothing new: nothing spent


def test_an_ad_is_dropped_and_the_same_story_corroborates_for_free(monkeypatch):
    _setup()
    trace.run(key="sk-test", now=NOW, session=Web(), post=deepseek(GOOD), rng=random.Random(0))
    second = YT_FEED.replace(b"abc123", b"def456").replace(b"A 1B model beats 70B models at maths",
                                                         b"1B model beats 70B models at maths, explained")
    trace.add_feed("youtube", "UC" + "b" * 22, "Another channel", "news")
    st = trace.load()
    for sid, s in st["sources"].items():
        s["checked"] = ""                                                    # due again
    trace.save(st)
    web = Web(second)
    out = trace.run(key="sk-test", now=NOW + timedelta(hours=3), session=web, post=deepseek({"is_news": False}),
                    rng=random.Random(0))
    assert out["items"] == 0 and len(trace.queue()) == 1                    # merged, not a second item
    assert any("def456" in u for u in trace.queue()[0]["sources"])
    log = trace.load()["triggers"]
    assert any("merged" in t["result"] for t in log)


def test_only_allowed_senders_trigger_and_listings_go_to_the_scouts_review(monkeypatch):
    from email.message import EmailMessage
    trace.set_inbox("bioresearch3000@gmail.com", ["mygeeky/jobs"])
    trace.add_sender("noreply@jobs.ac.uk", "jobs.ac.uk", "jobs")

    def mail(sender, subject, body):
        m = EmailMessage()
        m["From"], m["Subject"], m["Date"] = sender, subject, "Tue, 27 Oct 2026 09:00:00 +0000"
        m.set_content(body)
        return m
    job_page = ("Postdoc in statistical genetics. Wellcome Sanger Institute, Hinxton, UK. We are hiring a postdoc to "
                "work on GWAS of complex traits. Closing date: 30 November 2026. " * 3)
    msgs = [("<1@x>", mail("jobs.ac.uk <noreply@jobs.ac.uk>", "New jobs", f"Apply at https://www.sanger.ac.uk/jobs/1\n{job_page}")),
            ("<2@x>", mail("Promo <deals@spam.example>", "Buy now", "https://spam.example/x"))]

    class Box:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def recent(self, since=None, cap=60):
            return msgs

    class Site(Web):
        def get(self, url, params=None, timeout=None, headers=None, **kw):
            if "sanger.ac.uk" in url:
                return Resp(f"<html><body>{job_page}</body></html>", url=url)
            return super().get(url, params, timeout, headers)
    listing = {"listings": [{"title": "Postdoc in statistical genetics", "title_en": "Postdoc in statistical genetics",
                             "org": "Wellcome Sanger Institute", "place": "Hinxton, UK", "type": "postdoc",
                             "deadline": "2026-11-30", "deadline_quote": "Closing date: 30 November 2026.",
                             "link": "https://www.sanger.ac.uk/jobs/1", "keywords": ["gwas"], "relevance": 0.9,
                             "confidence": 0.9, "summary_en": "A postdoc on GWAS.", "language": "English"}]}
    out = trace.run(key="sk-test", now=NOW, session=Site(), post=deepseek(listing), mailbox_factory=lambda label: Box(),
                    rng=random.Random(0))
    assert out["triggers"] == 1 and out["listings"] == 1                    # the spam sender never counted
    st = trace.load()
    assert st["inbox_ignored"] == 1
    cands = list(scout.load()["candidates"].values())
    assert cands[0]["from"].startswith("trace:") and cands[0]["item"]["url"] == "https://www.sanger.ac.uk/jobs/1"
    # the maker accepts it in the scout's queue: the sender's record learns
    trace.listing_decided(cands[0], True, NOW)
    sid = cands[0]["from"][6:]
    assert trace.load()["sources"][sid]["acc"] == 1


def test_the_budget_holds_and_what_is_left_waits_for_tomorrow():
    _setup()
    trace.set_budget(0)
    out = trace.run(key="sk-test", now=NOW, session=Web(), post=deepseek(GOOD), rng=random.Random(0))
    assert out["items"] == 0 and out["skipped"] == 1 and len(trace.load()["backlog"]) == 1
    trace.set_budget(10)
    later = trace.run(key="sk-test", now=NOW + timedelta(days=1), session=Web(), post=deepseek(GOOD), rng=random.Random(0))
    assert later["items"] == 1 and trace.load()["backlog"] == []


def test_decisions_teach_and_accepted_news_is_published_into_whats_new():
    _setup()
    trace.run(key="sk-test", now=NOW, session=Web(), post=deepseek(GOOD), rng=random.Random(0))
    item = trace.queue()[0]
    w_before = dict(trace.load()["model"]["w"])
    assert trace.decide(item["id"], True, NOW + timedelta(hours=5))
    st = trace.load()
    assert st["sources"][item["sid"]]["acc"] == 1 and st["model"]["n"] == 1 and st["model"]["w"] != w_before
    news = trace.accepted_for_publish()
    data, added = whatsnew_shape.merge({"whatsnew": []}, news, today=NOW.date())
    assert added == 1 and data["whatsnew"][0]["title"] == GOOD["title"]
    s = trace.stats(NOW + timedelta(hours=6))
    funnel = dict(s["funnel"])
    assert funnel["Triggers"] == 1 and funnel["Items written"] == 1 and funnel["You accepted"] == 1
    assert s["sources"][0]["n"] == 1 and s["heat"][0]["topic"] == "small language models"
    assert s["speed"]["to_decision_h"] == pytest.approx(5.0, abs=0.01)


def test_without_a_key_nothing_is_spent_and_the_trigger_waits():
    _setup()
    out = trace.run(key=None, now=NOW, session=Web(), post=deepseek(GOOD), rng=random.Random(0))
    assert out["followed"] == 0 and out["spent"] == 0 and len(trace.load()["backlog"]) == 1
