"""WISEP: the rules, the store, asking through it, backing off, the evening top-up -- and a simulation that checks it
asks less than fixed timers while showing answers no staler."""

import json
import math
import random
from datetime import datetime

import pytest
import requests

import phone
from mygeeky import wisep

NOON = datetime(2026, 10, 20, 12, 0).timestamp()


def test_the_rules():
    assert wisep.change_rate(0, 0, 24) == pytest.approx(1 / 24)
    assert wisep.change_rate(9, 216, 24) == pytest.approx(10 / 240)          # its own history wins over the prior
    assert wisep.p_changed(1 / 24, 0) == 0 and 0.6 < wisep.p_changed(1 / 24, 24) < 0.65
    flat = [1.0] * 24
    assert wisep.care(flat, 12, 24.0) == 1.0                                   # your most-opened page, any hour
    assert wisep.care([0.0] * 24, 12, 24.0) == 0.1                             # a page you never open
    assert wisep.care([0.0] * 24, 12, 0.0) == 0.5                              # nothing learned yet
    evening = [0.0] * 24
    evening[20] = 5.0
    assert wisep.care(evening, 19, 5.0) > wisep.care(evening, 8, 5.0)          # you look at it in the evening
    assert wisep.threshold(0, 100, 0.5) == 0.15 and wisep.threshold(100, 100, 0.5) == math.inf
    assert wisep.threshold(80, 100, 0.5) > wisep.threshold(20, 100, 0.5)       # spending ahead of the day: a higher bar


def test_decide_says_why():
    d = wisep.decide
    assert d(None, "search", 0, 0, 0.5, 0, 100, 0.5)["action"] == "fetch"
    assert d(0.2, "search", 0, 0, 1.0, 0, 100, 0.5)["why"] == "asked moments ago"
    assert d(100, "search", 0, 0, 0.1, 0, 100, 0.5)["action"] == "fetch"           # older than a search may be
    assert d(10, "entity", 0, 300, 0.1, 0, 100, 0.5)["action"] == "cache"         # never changes, rarely looked at
    assert d(10, "search", 20, 100, 1.0, 0, 100, 0.5)["action"] == "fetch"        # changes often, looked at a lot
    assert d(10, "search", 20, 100, 1.0, 100, 100, 0.5)["action"] == "cache"      # ... but the budget is spent
    assert d(10, "search", 0, 0, 0.1, 50, 100, 0.5, forced=True)["action"] == "fetch"
    assert d(10, "search", 0, 0, 1.0, 0, 100, 0.5, paused=True)["action"] == "cache"
    assert d(None, "search", 0, 0, 1.0, 0, 100, 0.5, paused=True)["action"] == "none"


class _Net(requests.Session):
    """Stands in for the network, counting what reached it."""

    def __init__(self, bodies=None, status=200, headers=None):
        super().__init__()
        self.calls, self.bodies, self.status, self.extra = [], list(bodies or []), status, headers or {}

    def request(self, method, url, params=None, headers=None, timeout=None, **kw):
        self.calls.append((url, dict(params or {})))
        r = requests.Response()
        r.status_code, r.url = self.status, url
        r._content = json.dumps(self.bodies.pop(0) if self.bodies else {"n": len(self.calls)}).encode()
        r.headers.update(self.extra)
        return r


def test_asking_through_wisep_keeps_answers_and_learns_how_often_they_change(monkeypatch):
    monkeypatch.setattr(wisep, "_space", lambda source, st: None)
    net = _Net(bodies=[{"a": 1}, {"a": 1}, {"a": 2}])
    url = "https://api.openalex.org/works"
    r1 = wisep.get(url, {"filter": "cites:W1"}, page="you:cited", now=NOON, base=net)
    assert r1.json() == {"a": 1} and net.calls[0][1]["mailto"] == wisep.CONTACT     # the polite pool
    r2 = wisep.get(url, {"filter": "cites:W1"}, page="you:cited", now=NOON + 600, base=net)
    assert r2.json() == {"a": 1} and len(net.calls) == 1 and r2.headers["X-Wisep"].startswith("cache")
    wisep.get(url, {"filter": "cites:W1"}, page="you:cited", now=NOON + 3600 * 200, base=net)   # too old: asked
    wisep.get(url, {"filter": "cites:W1"}, page="you:cited", now=NOON + 3600 * 400, force=True, base=net)
    kept = wisep.store().get(wisep.key_of(url, {"filter": "cites:W1"}))
    assert kept["checks"] == 3 and kept["changes"] == 1 and kept["kind"] == "citations"
    s = wisep.stats(NOON)
    assert s["today"]["openalex"]["asked"] == 1 and s["today"]["openalex"]["saved"] == 1
    other = wisep.get("https://example.org/x", None, base=net)                      # not managed: straight through
    assert other.status_code == 200 and net.calls[-1][0] == "https://example.org/x"


def test_a_busy_source_is_left_alone_and_the_kept_answer_served(monkeypatch):
    monkeypatch.setattr(wisep, "_space", lambda source, st: None)
    url = "https://api.openalex.org/authors/A1"
    wisep.get(url, page="you", now=NOON, base=_Net(bodies=[{"name": "Ada"}]))
    busy = _Net(status=429, headers={"Retry-After": "120"})
    r = wisep.get(url, page="you", now=NOON + 3600 * 400, base=busy)
    assert r.json() == {"name": "Ada"} and r.headers["X-Wisep"] == "stale:busy"
    assert wisep.store().paused_until["openalex"] >= NOON + 3600 * 400 + 120
    again = _Net()
    wisep.get(url, page="you", now=NOON + 3600 * 400 + 10, base=again)
    assert again.calls == []                                                         # resting: not asked


def test_the_session_is_a_drop_in(monkeypatch):
    monkeypatch.setattr(wisep, "_space", lambda source, st: None)
    sent = []
    monkeypatch.setattr(wisep, "fetch_raw", lambda url, params, headers, timeout, base=None:
                        sent.append(url) or _Net(bodies=[{"ok": True}]).request("GET", url))
    s = wisep.session("world:papers")
    assert s.get("https://api.openalex.org/works", params={"search": "gwas"}).json() == {"ok": True}
    assert s.get("https://api.openalex.org/works", params={"search": "gwas"}).json() == {"ok": True}
    assert len(sent) == 1


def test_what_you_open_is_learned_and_fades():
    for _ in range(5):
        wisep.opened("you:cited", NOON)
    wisep.opened("world:news", NOON)
    assert wisep.care_for("you:cited", NOON) > wisep.care_for("world:news", NOON) > wisep.care_for("chances:jobs", NOON)
    later = wisep.store().opens(NOON + 86400 * 14)
    assert sum(later["you:cited"]) == pytest.approx(2.5)                              # a two-week half-life


def test_the_evening_top_up_spends_what_is_left_on_what_you_will_want(monkeypatch):
    monkeypatch.setattr(wisep, "_space", lambda source, st: None)
    for _ in range(6):
        wisep.opened("you:cited", NOON)
    for i, page in enumerate(["you:cited", "never:opened"]):
        wisep.get(f"https://api.openalex.org/works?filter=cites:W{i}", page=page, now=NOON - 3600 * 60,
                  base=_Net(bodies=[{"i": i}]))
    assert wisep.top_up(NOON) == {}                                                  # not evening yet
    net = _Net()
    spent = wisep.top_up(NOON + 9 * 3600, base=net)
    assert spent == {"openalex": 1} and "W0" in net.calls[0][0]                      # the one you open, not the other


# --------------------------------------------------------------------------- the evaluation: a simulation
_simulate = wisep.simulate


def test_wisep_asks_far_less_than_fixed_timers_and_shows_answers_no_staler():
    timers, wise = _simulate("timers"), _simulate("wisep")
    assert wise["calls"] < 0.5 * timers["calls"], (wise, timers)
    assert wise["stale_share"] <= timers["stale_share"] + 0.05, (wise, timers)


# --------------------------------------------------------------------------- the phone decides the same
@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_decides_the_same():
    rng = random.Random(3)
    cases = [{"age": rng.choice([None, 0.3, 5, 20, 80, 400]), "kind": rng.choice(list(wisep.KINDS)),
              "changes": rng.randint(0, 20), "watched": rng.uniform(0, 500), "care": round(rng.random(), 3),
              "used": rng.randint(0, 120), "budget": 100, "frac": round(rng.random(), 3),
              "forced": rng.random() < 0.2, "paused": rng.random() < 0.1} for _ in range(60)]
    opens = [[round(rng.random() * 3, 2) for _ in range(24)] for _ in range(5)]
    urls = ["https://api.openalex.org/works?filter=cites:W1|W2", "https://api.openalex.org/authors/A5",
            "https://api.openalex.org/topics?search=x", "https://api.openalex.org/works?search=gwas",
            "https://api.openalex.org/authors?search=ada", "https://zenodo.org/api/records?q=x", "https://example.org/"]
    said = phone.run("""
import { care, decide, kindOf, sourceOf } from './lib/wisep.ts';
out({ d: INPUT.cases.map((c: any) => decide(c.age, c.kind, c.changes, c.watched, c.care, c.used, c.budget, c.frac, c.forced, c.paused)),
      c: INPUT.opens.flatMap((o: number[]) => [0, 7, 19].map((h) => care(o, h, 40))),
      k: INPUT.urls.map((u: string) => [sourceOf(u), sourceOf(u) ? kindOf(sourceOf(u)!, u) : null]) });
""", {"cases": cases, "opens": opens, "urls": urls})
    want = [wisep.decide(c["age"], c["kind"], c["changes"], c["watched"], c["care"], c["used"], c["budget"], c["frac"],
                         c["forced"], c["paused"]) for c in cases]
    assert said["d"] == json.loads(json.dumps(want).replace("Infinity", "null"))
    assert said["c"] == [wisep.care(o, h, 40) for o in opens for h in (0, 7, 19)]
    assert said["k"] == [[wisep.source_of(u), wisep.kind_of(wisep.source_of(u), u) if wisep.source_of(u) else None]
                         for u in urls]


# --------------------------------------------------------------------------- it tunes itself, and takes over once proven
def test_priors_are_tuned_from_what_this_device_watched():
    assert wisep.tuned_prior(3, 100, 10, "search") is None                     # too little watched
    assert wisep.tuned_prior(3, 400, 4, "search") is None                      # too few answers
    assert wisep.tuned_prior(9, 400, 6, "search") == pytest.approx((400 + 24) / 10, abs=0.01)
    assert wisep.tuned_prior(0, 5000, 6, "search") == 4 * 72                   # never changed: capped at 4x the "always by"
    assert wisep.tuned_prior(400, 400, 6, "static") == 168                     # changed often: never below "never sooner"
    st = wisep.store()
    for i in range(6):
        st.put(f"k{i}", "openalex", "search", f"u{i}", b"a", "p", NOON)
        st.put(f"k{i}", "openalex", "search", f"u{i}", b"b", "p", NOON + 3600 * 40)
        st.put(f"k{i}", "openalex", "search", f"u{i}", b"b", "p", NOON + 3600 * 80)
    priors = wisep.tune(NOON + 3600 * 80, force=True)
    assert priors["search"] == wisep.tuned_prior(6, 6 * 80, 6, "search") and "entity" not in priors
    d = wisep.decide(10, "search", 0, 0, 1.0, 0, 100, 0.5, prior_hours=1000)
    assert d["action"] == "cache"                                                # a slow-changing kind, learned


def test_wisep_takes_over_from_the_old_timers_only_once_proven():
    day = lambda i: f"2026-10-{i + 1:02d}"  # noqa: E731
    good = [{"day": day(i), "asked": 4, "saved": 6, "stale": 0, "failed": 0} for i in range(14)]
    assert wisep.proven_by(good)["proven"] is True
    assert wisep.proven_by(good[:10])["proven"] is False                         # not enough days yet
    poor = [dict(r, saved=1) for r in good]
    assert wisep.proven_by(poor)["proven"] is False                              # the cache isn't saving enough
    shaky = [dict(r, failed=2) for r in good]
    assert wisep.proven_by(shaky)["proven"] is False                             # too many failures
    assert wisep.timer_due(True) is True and wisep.timer_due(False, 5.0) is False   # not proven: the module's own timer
    wisep.set_mode("on")
    assert wisep.timer_due(False, 5.0) is True and wisep.timer_due(False, 0.2) is False   # at most every half hour
    wisep.set_mode("off")
    assert wisep.timer_due(False, 99.0) is False
    wisep.set_mode("nonsense")
    assert wisep.mode() == "auto"
    s = wisep.stats(NOON)
    assert "github" in s and s["proven"]["mode"] == "auto" and s["proven"]["alone"] is False


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_tunes_and_judges_the_same():
    tunes = [[c, h, n, k] for c, h, n, k in [(3, 100, 10, "search"), (9, 400, 6, "search"), (0, 5000, 6, "search"),
                                              (400, 400, 6, "static"), (7, 1200, 9, "entity"), (2, 336, 5, "citations")]]
    day = lambda i: f"2026-10-{i + 1:02d}"  # noqa: E731
    tallies = [[{"day": day(i), "asked": 4, "saved": s, "stale": 0, "failed": f} for i in range(n)]
               for n, s, f in [(14, 6, 0), (10, 6, 0), (14, 1, 0), (14, 6, 2), (0, 0, 0)]]
    said = phone.run("""
import { decide, provenBy, tunedPrior } from './lib/wisep.ts';
out({ t: INPUT.tunes.map((x: any) => tunedPrior(x[0], x[1], x[2], x[3])), p: INPUT.tallies.map(provenBy),
      d: [decide(10, 'search', 0, 0, 1.0, 0, 100, 0.5, false, false, 1000), decide(10, 'search', 0, 0, 1.0, 0, 100, 0.5, false, false, 2)] });
""", {"tunes": tunes, "tallies": tallies})
    assert said["t"] == [wisep.tuned_prior(*x) for x in tunes]
    assert said["p"] == [wisep.proven_by(t) for t in tallies]
    assert said["d"] == [wisep.decide(10, "search", 0, 0, 1.0, 0, 100, 0.5, prior_hours=1000),
                         wisep.decide(10, "search", 0, 0, 1.0, 0, 100, 0.5, prior_hours=2)]


def test_every_user_sees_their_own_wisep_in_settings_and_can_forget_what_it_learned(qapp_offscreen):
    from mygeeky.gui.app import THEMES
    from mygeeky.gui.wisep_ui import WisepSection
    for _ in range(3):
        wisep.opened("model:cited", NOON)
    wisep.store().set_meta("priors", {"search": 40.0, "_day": "2026-10-20"})
    box = WisepSection(lambda: THEMES["midnight"])
    assert "You open most: you:cited" in box.numbers.text() and "search about every 40 hours" in box.numbers.text()
    assert box.mode_btn.text().endswith("Auto")
    box.mode_btn.click()
    assert wisep.mode() == "on" and box.mode_btn.text().endswith("Always")
    box.forget_btn.click()
    assert wisep.store().opens(NOON) == {} and wisep.priors() == {}
    assert "You open most" not in box.numbers.text()
    assert wisep.mode() == "on"                                                  # forgetting doesn't touch your choice


# --------------------------------------------------------------------------- the source's own budget (OpenAlex credits)
def test_a_search_costs_a_credit_and_one_record_by_id_costs_nothing():
    c = wisep.credit_cost
    assert c("openalex", "https://api.openalex.org/works?filter=cites:W1") == 1
    assert c("openalex", "https://api.openalex.org/authors?search=ada") == 1
    assert c("openalex", "https://api.openalex.org/topics?search=x") == 1
    assert c("openalex", "https://api.openalex.org/authors/A5083340569?select=id,topics") == 0
    assert c("openalex", "https://api.openalex.org/works/W123") == 0
    assert c("openalex", "https://api.openalex.org/works/doi:10.1/x") == 0
    assert c("zenodo", "https://zenodo.org/api/records/1") == 1
    assert wisep.server_budget(0, 0, 0, 7, 900, 0.5) == (7, 900, 0.5)          # no word from the source: our own count
    assert wisep.server_budget(1000, 400, 43200, 7, 900, 0.9) == (600, 950, 0.5)   # its numbers: everyone on the network


def _oa_net(remaining, status=200, retry=None):
    h = {"X-RateLimit-Limit": "1000", "X-RateLimit-Remaining": str(remaining), "X-RateLimit-Reset": "7200"}
    if retry:
        h["Retry-After"] = str(retry)
    return _Net(status=status, headers=h)


def test_wisep_paces_itself_to_what_openalex_says_is_left_and_rests_when_it_is_spent(monkeypatch):
    monkeypatch.setattr(wisep, "_space", lambda source, st: None)
    wisep.get("https://api.openalex.org/works", {"filter": "cites:W1"}, page="you:cited", now=NOON, base=_oa_net(600))
    srv = wisep.server_of("openalex", NOON)
    assert srv["limit"] == 1000 and srv["remaining"] == 600
    assert wisep.store().used("openalex", wisep._day(NOON)) == 1                    # a search: one credit
    wisep.get("https://api.openalex.org/authors/A1", page="you", now=NOON, base=_oa_net(600))
    assert wisep.store().used("openalex", wisep._day(NOON)) == 1                    # one record by id: free
    spent = _oa_net(0, status=429, retry=7063)
    r = wisep.get("https://api.openalex.org/works", {"search": "gwas"}, page="world:papers", now=NOON + 10, base=spent)
    assert r.status_code == 429 and wisep.store().paused_until["openalex"] == pytest.approx(NOON + 10 + 7063)
    after = _Net()
    wisep.get("https://api.openalex.org/works", {"search": "other"}, page="world:papers", now=NOON + 600, base=after)
    assert after.calls == []                                                         # resting until OpenAlex's reset
    s = wisep.stats(NOON + 600)
    assert s["server"]["openalex"]["remaining"] == 0 and s["key"] is False


def test_a_free_openalex_key_goes_with_every_ask_and_can_be_requested_by_email(monkeypatch):
    monkeypatch.setattr(wisep, "_space", lambda source, st: None)
    kept = {}
    monkeypatch.setattr(wisep, "get_key", lambda: kept.get("k"))
    monkeypatch.setattr(wisep, "set_key", lambda k: kept.__setitem__("k", k) or True)

    class Post:
        def post(self, url, json=None, **kw):
            assert url == "https://api.openalex.org/api-keys" and json == {"email": "ada@uni.edu"}
            r = requests.Response()
            r.status_code, r._content = 200, b'{"api_key": "oa-free-123456"}'
            return r

    assert wisep.request_key("not an email")["ok"] is False
    out = wisep.request_key("ada@uni.edu", session=Post())
    assert out["ok"] and out["key"] and kept["k"] == "oa-free-123456" and "click" in out["message"]
    net = _Net()
    sent = {}
    orig = net.request
    net.request = lambda method, url, params=None, headers=None, timeout=None, **kw: (sent.update(headers or {}), orig(method, url, params, headers, timeout))[1]
    wisep.get("https://api.openalex.org/works", {"search": "x"}, page="world:papers", now=NOON, base=net)
    assert sent.get("Authorization") == "Bearer oa-free-123456"


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_counts_credits_and_reads_the_budget_the_same():
    urls = ["https://api.openalex.org/works?filter=cites:W1", "https://api.openalex.org/authors?search=ada",
            "https://api.openalex.org/authors/A5083340569?select=id,topics", "https://api.openalex.org/works/W123",
            "https://api.openalex.org/works/doi:10.1/x", "https://api.openalex.org/topics?search=x",
            "https://api.openalex.org/works", "https://zenodo.org/api/records/1"]
    cases = [[0, 0, 0, 7, 900, 0.5], [1000, 400, 43200, 7, 900, 0.9], [1000, 0, 7063, 0, 900, 0.2], [500, 999, 10, 1, 900, 0.1]]
    said = phone.run("""
import { creditCost, serverBudget, sourceOf } from './lib/wisep.ts';
out({ c: INPUT.urls.map((u: string) => creditCost(sourceOf(u) ?? '', u)), b: INPUT.cases.map((x: number[]) => serverBudget(x[0], x[1], x[2], x[3], x[4], x[5])) });
""", {"urls": urls, "cases": cases})
    assert said["c"] == [wisep.credit_cost(wisep.source_of(u) or "", u) for u in urls]
    assert said["b"] == [list(wisep.server_budget(*x)) for x in cases]
