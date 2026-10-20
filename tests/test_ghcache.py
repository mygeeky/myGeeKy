"""The GitHub cache: conditional requests, one ask per run, and an app that survives an outage."""

import json
import os
import time

import pytest
import requests

from mygeeky import ghcache
from mygeeky.github_client import GitHubClient


class Reply:
    """What the session hands back, without a network."""

    def __init__(self, status=200, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = text or ""

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    """Counts what actually went out, and answers 304 when the request says it already has the answer."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.sent: list[dict] = []
        self.headers: dict[str, str] = {}

    def get(self, url, params=None, headers=None, timeout=None):
        self.sent.append({"url": url, "params": params, "headers": headers or {}})
        return self.replies.pop(0) if self.replies else Reply(200, {})


def client(replies, **kw):
    c = GitHubClient(None, rate_limit_sleep=0, search_pause=0, **kw)
    c.session = FakeSession(replies)
    return c


# --------------------------------------------------------------------------- the point of it all
def test_the_second_ask_carries_the_etag_and_a_304_costs_nothing():
    c = client([Reply(200, {"login": "ada"}, {"ETag": 'W/"abc"'}),
                Reply(304, None, {"ETag": 'W/"abc"'})])
    first = c._get("/users/ada/repos")
    assert first.json()["login"] == "ada"
    time.sleep(0)                                  # a second refresh, later
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada/repos")).at -= 60
    second = c._get("/users/ada/repos")
    assert c.session.sent[1]["headers"]["If-None-Match"] == 'W/"abc"'
    assert second.json()["login"] == "ada", "a 304 still answers with what we already had"
    assert second.from_cache and second.fresh, "fresh: GitHub confirmed it just now"
    assert c.stats.not_modified == 1 and c.stats.saved == 1


def test_last_modified_is_sent_when_there_is_no_etag():
    when = "Mon, 13 Oct 2026 10:00:00 GMT"
    c = client([Reply(200, [1, 2], {"Last-Modified": when}), Reply(304, None, {})])
    c._get("/users/ada/repos")
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada/repos")).at -= 60
    c._get("/users/ada/repos")
    assert c.session.sent[1]["headers"]["If-Modified-Since"] == when


def test_the_same_question_twice_in_one_refresh_only_goes_out_once():
    """Three features ask about the same person; GitHub hears it once."""
    c = client([Reply(200, {"login": "ada"}, {"ETag": '"1"'})])
    for _ in range(3):
        assert c._get("/users/ada").json()["login"] == "ada"
    assert len(c.session.sent) == 1
    assert c.stats.requests == 1 and c.stats.from_cache == 2


def test_two_different_questions_are_not_confused():
    c = client([Reply(200, {"login": "ada"}), Reply(200, {"login": "lin"})])
    assert c._get("/users/ada").json()["login"] == "ada"
    assert c._get("/users/lin").json()["login"] == "lin"
    assert len(c.session.sent) == 2


def test_the_same_path_with_different_parameters_is_a_different_question():
    c = client([Reply(200, [1]), Reply(200, [2])])
    c._get("/users/ada/repos", params={"page": 1})
    c._get("/users/ada/repos", params={"page": 2})
    assert len(c.session.sent) == 2


# --------------------------------------------------------------------------- when GitHub isn't there
def test_an_outage_is_answered_from_the_cache_rather_than_an_empty_tab():
    c = client([Reply(200, {"login": "ada"}, {"ETag": '"1"'})])
    c._get("/users/ada/repos")
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada/repos")).at -= 60

    def dead(*a, **k):
        raise requests.ConnectionError("no network")
    c.session.get = dead
    out = c._get("/users/ada/repos")
    assert out.json()["login"] == "ada" and out.from_cache and not out.fresh
    assert c.stats.offline == 1


def test_without_anything_cached_a_dead_network_is_still_an_error():
    c = client([])

    def dead(*a, **k):
        raise requests.ConnectionError("no network")
    c.session.get = dead
    with pytest.raises(requests.ConnectionError):
        c._get("/users/ada")


def test_a_spent_rate_limit_serves_what_we_know():
    c = client([Reply(200, {"login": "ada"})])
    c._get("/users/ada")
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada")).at -= 60
    c._blocked_until = time.time() + 600
    out = c._get("/users/ada")
    assert out.json()["login"] == "ada" and out.from_cache


def test_github_having_a_bad_day_falls_back_to_the_last_good_answer():
    c = client([Reply(200, {"login": "ada"}), Reply(500, {"message": "oops"})])
    c._get("/users/ada")
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada")).at -= 60
    out = c._get("/users/ada")
    assert out.status_code == 200 and out.json()["login"] == "ada"


# --------------------------------------------------------------------------- not asking twice for nothing
def test_a_deleted_account_is_not_asked_about_again_today():
    c = client([Reply(404, {"message": "Not Found"})])
    first = c._get("/users/ghost")
    assert first.status_code == 404
    second = c._get("/users/ghost")
    assert second.status_code == 404 and len(c.session.sent) == 1, "once is enough"


def test_a_404_is_asked_again_after_a_while():
    c = client([Reply(404, {}), Reply(200, {"login": "back"})])
    c._get("/users/ghost")
    c.cache.get(ghcache.key_of("https://api.github.com/users/ghost")).at -= ghcache.MISSING_SECONDS + 10
    assert c._get("/users/ghost").json()["login"] == "back"


# --------------------------------------------------------------------------- the file itself
def test_what_is_kept_survives_a_restart(tmp_path):
    path = tmp_path / "cache.json"
    first = client([Reply(200, {"login": "ada"}, {"ETag": '"x"'})], cache=ghcache.Store(path))
    first._get("/users/ada/repos")
    first.done()                                      # written once, at the end of a refresh
    later = client([Reply(304, None, {})], cache=ghcache.Store(path))
    later.cache.get(ghcache.key_of("https://api.github.com/users/ada/repos")).at -= 60
    out = later._get("/users/ada/repos")
    assert out.json()["login"] == "ada" and later.stats.not_modified == 1


def test_the_file_does_not_grow_without_end(tmp_path):
    store = ghcache.Store(tmp_path / "cache.json", max_entries=10)
    for i in range(40):
        store.put(f"https://api.github.com/users/u{i}", {"login": f"u{i}"})
    store.save()
    assert store.entries() == 10, "the least recently used go first"


def test_big_answers_cannot_swell_the_cache(tmp_path):
    store = ghcache.Store(tmp_path / "cache.sqlite", max_bytes=50_000)
    for i in range(20):                               # search answers are big: ~10 KB each here
        store.put(f"https://api.github.com/search/q{i}", {"items": ["x" * 100] * 100})
        store.get(f"https://api.github.com/search/q{i}").used = i
        store._used[f"https://api.github.com/search/q{i}"] = i
    store.save()
    assert store.entries() < 6 and store.size() <= 50_000
    assert store.get("https://api.github.com/search/q19") is not None, "the most recently used stay"
    assert store.get("https://api.github.com/search/q0") is None


def test_one_answer_is_one_row_not_a_rewrite(tmp_path):
    path = tmp_path / "cache.sqlite"
    store = ghcache.Store(path)
    for i in range(300):
        store.put(f"https://api.github.com/users/u{i}", {"login": f"u{i}", "bio": "x" * 2000})
    before = path.stat().st_size
    store.put("https://api.github.com/users/new", {"login": "new"})
    assert path.stat().st_size - before < 64_000, "adding one answer doesn't rewrite the others"
    again = ghcache.Store(path)                       # what was written is there for the next run, unsaved or not
    assert again.get("https://api.github.com/users/u7").body["login"] == "u7"


def test_the_old_json_cache_moves_in_once_and_is_removed(tmp_path):
    old = tmp_path / "github_cache.json"
    old.write_text(json.dumps({"entries": {"https://api.github.com/users/ada": {
        "body": {"login": "ada"}, "status": 200, "etag": '"e"', "at": time.time(), "used": time.time()}},
        "calls": {time.strftime("%Y-%m-%d"): {"requests": 3}}}))
    half = tmp_path / ".github_cache.json.123.456.tmp"
    half.write_text("half")
    store = ghcache.Store(tmp_path / "github_cache.sqlite")
    row = store.get("https://api.github.com/users/ada")
    assert row.body == {"login": "ada"} and row.etag == '"e"' and store.today()["requests"] == 3
    assert not old.exists() and not half.exists()


def test_a_huge_old_json_cache_is_not_read_just_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(ghcache, "LEGACY_IMPORT_MAX", 100)
    old = tmp_path / "github_cache.json"
    old.write_text(json.dumps({"entries": {"k": {"body": "x" * 500}}}))
    store = ghcache.Store(tmp_path / "github_cache.sqlite")
    assert store.entries() == 0 and not old.exists()


def test_a_damaged_database_is_set_aside_and_a_new_one_started(tmp_path):
    path = tmp_path / "cache.sqlite"
    path.write_bytes(b"this is not a database" * 100)
    store = ghcache.Store(path)
    store.put("https://api.github.com/users/ada", {"login": "ada"})
    assert store.get("https://api.github.com/users/ada").body == {"login": "ada"}
    assert list(tmp_path.glob("cache.sqlite.broken-*"))


def test_two_threads_and_two_stores_can_write_at_once(tmp_path):
    import threading
    path = tmp_path / "cache.sqlite"
    a, b = ghcache.Store(path), ghcache.Store(path)   # the panel and a scheduled refresh

    def fill(store, who):
        for i in range(100):
            store.put(f"https://api.github.com/{who}/{i}", {"i": i})
            store.count("requests")
    threads = [threading.Thread(target=fill, args=(s, w)) for s, w in ((a, "a"), (a, "b"), (b, "c"))]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    a.save()
    b.save()
    assert ghcache.Store(path).entries() == 300 and ghcache.Store(path).today()["requests"] == 300


def test_the_tally_says_what_was_saved(tmp_path):
    c = client([Reply(200, {"a": 1}, {"ETag": '"1"'}), Reply(304, None, {})],
               cache=ghcache.Store(tmp_path / "c.json"))
    c._get("/users/ada/repos")
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada/repos")).at -= 60
    c._get("/users/ada/repos")
    c._get("/users/ada/repos")                              # same run: never goes out
    today = c.done() and c.cache.today()
    assert today["requests"] == 2 and today["not_modified"] == 1 and today["from_cache"] == 1
    assert c.stats.saved == 2


def test_a_search_is_counted_as_a_search():
    c = client([Reply(200, {"items": []})])
    c._get("/search/repositories", params={"q": "r"}, is_search=True)
    assert c.stats.searches == 1 and c.cache.today()["searches"] == 1


def test_the_cache_can_be_turned_off():
    c = client([Reply(200, {"login": "ada"}), Reply(200, {"login": "ada"})], use_cache=False)
    c._get("/users/ada")
    c._get("/users/ada")
    assert len(c.session.sent) == 2 and c.cache is None


def test_each_data_folder_gets_its_own_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ghcache, "CACHE_FILE", tmp_path / "one.json")
    one = ghcache.store()
    monkeypatch.setattr(ghcache, "CACHE_FILE", tmp_path / "two.json")
    two = ghcache.store()
    assert one is not two, "a second profile must not read the first one's answers"


# --------------------------------------------------------------------------- it changes nothing for callers
def test_the_callers_see_the_same_answers_they_always_did():
    """Every caller uses status_code and json(); a cached answer behaves the same way."""
    c = client([Reply(200, [{"login": "a"}, {"login": "b"}], {"ETag": '"1"'}), Reply(304, None, {})])
    assert c.list_followers("ada", max_pages=1) == ["a", "b"]
    c.cache.get(ghcache.key_of("https://api.github.com/users/ada/followers",
                               {"per_page": 100, "page": 1})).at -= 60
    assert c.list_followers("ada", max_pages=1) == ["a", "b"], "a 304 gives the same list back"
    assert c.stats.not_modified == 1


def test_a_cached_answer_can_be_raised_for_status_like_any_other():
    c = client([Reply(404, {})])
    first = c._get("/users/ghost")
    assert first.status_code == 404
    cached = c._get("/users/ghost")
    with pytest.raises(requests.HTTPError):
        cached.raise_for_status()


# --------------------------------------------------------------------------- slow numbers wait a day
def test_stars_and_commit_activity_are_asked_once_a_day():
    c = client([Reply(200, {"stargazers_count": 5}, {"ETag": '"r"'}), Reply(200, [{"total": 3}], {"ETag": '"s"'})])
    c._get("/repos/ada/tool")
    c._get("/repos/ada/tool/stats/commit_activity")
    for key in ("https://api.github.com/repos/ada/tool", "https://api.github.com/repos/ada/tool/stats/commit_activity"):
        c.cache.get(key).at -= 6 * 3600              # six hours later: switching tabs
    assert c._get("/repos/ada/tool").json()["stargazers_count"] == 5
    assert c._get("/repos/ada/tool/stats/commit_activity").json() == [{"total": 3}]
    assert len(c.session.sent) == 2, "nothing went out the second time"


def test_after_a_day_slow_numbers_are_asked_again():
    c = client([Reply(200, {"followers": 1}, {"ETag": '"u"'}), Reply(304, None, {})])
    c._get("/users/ada")
    c.cache.get("https://api.github.com/users/ada").at -= 25 * 3600
    c._get("/users/ada")
    assert len(c.session.sent) == 2 and c.session.sent[1]["headers"].get("If-None-Match") == '"u"'


def test_fast_things_are_still_asked_each_time():
    c = client([Reply(200, [{"id": 1}], {"ETag": '"e"'}), Reply(304, None, {})])
    c._get("/users/ada/events/public")
    c.cache.get("https://api.github.com/users/ada/events/public").at -= 60
    c._get("/users/ada/events/public")
    assert len(c.session.sent) == 2


@pytest.mark.parametrize("url,slow", [
    ("/repos/a/b", True), ("https://api.github.com/repos/a/b", True), ("/repos/a/b/stats/commit_activity", True),
    ("/repos/a/b/contributors?per_page=30", True), ("/users/ada", True), ("/users/ada/social_accounts", True),
    ("/repos/a/b/issues", False), ("/users/ada/events/public", False), ("/search/repositories", False),
    ("/users/ada/repos", False), ("/user", False), ("/repos/a/b/contents/x.json", False)])
def test_which_answers_are_slow(url, slow):
    assert (ghcache.slow_seconds(url) == ghcache.SLOW_SECONDS) is slow


@pytest.mark.skipif(not __import__("phone").node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_waits_a_day_for_the_same_answers():
    import phone
    urls = ["/repos/a/b", "https://api.github.com/repos/a/b", "/repos/a/b/stats/commit_activity",
            "/repos/a/b/contributors?per_page=30", "/users/ada", "/users/ada/social_accounts", "/repos/a/b/issues",
            "/users/ada/events/public", "/search/repositories?q=x", "/users/ada/repos?per_page=100", "/user",
            "/repos/a/b/contents/x.json", "/users/ada/following?per_page=100&page=1"]
    said = phone.run("""
import { isSlow, SLOW_MS } from './lib/github.ts';
out({ slow: INPUT.map((u: string) => isSlow(u)), ms: SLOW_MS });
""", urls)
    assert said["slow"] == [ghcache.slow_seconds(u) > 0 for u in urls]
    assert said["ms"] == ghcache.SLOW_SECONDS * 1000


@pytest.mark.skipif(not __import__("phone").node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_asks_github_once_a_day_for_stars():
    import phone
    said = phone.run("""
import { gh } from './lib/github.ts';
const sent: string[] = [];
(globalThis as any).fetch = async (url: string) => { sent.push(url);
  return new Response(JSON.stringify({ stargazers_count: sent.length }), { status: 200 }); };
const a = await gh('/repos/ada/tool', null), b = await gh('/repos/ada/tool', null);
const e1 = await gh('/users/ada/events/public', null), e2 = await gh('/users/ada/events/public', null);
const realNow = Date.now; Date.now = () => realNow() + 25 * 3600 * 1000;
const c = await gh('/repos/ada/tool', null);
out({ a, b, c, events: [e1, e2], sent: sent.length });
""")
    assert said["a"] == said["b"] == {"stargazers_count": 1}, "the second ask came from the phone"
    assert said["events"] == [{"stargazers_count": 2}, {"stargazers_count": 3}], "fast things are asked each time"
    assert said["c"] == {"stargazers_count": 4} and said["sent"] == 4, "a day later it's asked again"


def test_a_busy_database_is_waited_for_never_called_damaged(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "cache.sqlite"
    ghcache.Store(path).put("https://api.github.com/users/ada", {"login": "ada"})
    real, calls = ghcache.Store._prepare, []

    def busy_twice(db, new):
        calls.append(1)
        if len(calls) <= 2:
            raise sqlite3.OperationalError("database is locked")
        return real(db, new)
    monkeypatch.setattr(ghcache.Store, "_prepare", staticmethod(busy_twice))
    store = ghcache.Store(path)
    assert store.get("https://api.github.com/users/ada").body == {"login": "ada"}
    assert not list(tmp_path.glob("*.broken-*")) and len(calls) == 3
