"""Circle → 📄 Researchers: following people by name, their new work (preprints first, linked to the published
version), suggestions from what's already read, one batched search for everyone due -- and the phone agreeing."""

import json

import pytest
import requests

import phone
from mygeeky import researchers as rs

TODAY = "2026-10-20"
ADA, ALAN, ME = "A5000000001", "A5000000002", "A5083340569"


def _work(wid, title, day, authors, typ="article", venue="Nature", repo=False, doi=""):
    return {"id": f"https://openalex.org/{wid}", "title": title, "publication_date": day, "type": typ, "doi": doi,
            "primary_location": {"source": {"display_name": venue, "type": "repository" if repo else "journal"},
                                 "landing_page_url": "https://example.org/x"},
            "authorships": [{"author": {"id": f"https://openalex.org/{a}"}} for a in authors]}


ANSWER = {"results": [
    _work("W1000001", "Mapping rare variants in 1 million genomes", "2026-10-18", [ADA, "A9999999"], doi="10.1/pub"),
    _work("W1000002", "Mapping rare variants in 1 million genomes", "2026-03-02", [ADA], typ="preprint", venue="bioRxiv",
          repo=True),
    _work("W1000003", "A new test for selection", "2026-10-10", [ALAN], typ="preprint", venue="arXiv", repo=True),
    _work("W1000004", "Someone else entirely", "2026-10-11", ["A7777777"]),
    _work("W1000005", "<no date>", "", [ADA]),
]}


def test_the_rules():
    assert [rs.interval_days(x) for x in (5, 2, 1, 0.5, 0.1, 0)] == [1, 1, 3, 3, 7, 7]
    assert rs.rate_of(["2026-10-01", "2026-09-01", "2025-01-01", ""], TODAY) == pytest.approx(2 / 12, abs=0.001)
    assert rs.is_due({"checked": ""}, TODAY) and rs.is_due({"checked": "2026-10-13", "rate": 0.1}, TODAY)
    assert not rs.is_due({"checked": "2026-10-19", "rate": 1.0}, TODAY)            # checked yesterday, every 3 days
    assert rs.since(TODAY) == "2026-06-01" and rs.since("2026-10-31") == "2026-07-01"   # steady for a month
    assert rs.works_url([ALAN, ADA], TODAY).count("author.id:" + ADA + "|" + ALAN) == 1  # sorted: one key for one group


def test_new_work_preprints_first_and_one_piece_shows_once():
    found = rs.parse_works(ANSWER, [ADA, ALAN])
    assert [w["id"] for w in found] == ["W1000001", "W1000002", "W1000003"]          # only people you follow, dated
    assert [w["preprint"] for w in found] == [False, True, True] and found[0]["url"] == "https://doi.org/10.1/pub"
    works = rs.merge_works({}, found, TODAY, TODAY)
    assert works["W1000001"]["preprint_of"] == {"venue": "bioRxiv", "date": "2026-03-02", "id": "W1000002"}
    assert works["W1000002"]["published_as"] == "W1000001"
    state = {"following": [{"id": ADA, "name": "Ada"}, {"id": ALAN, "name": "Alan"}], "works": works, "seen": ["W1000003"]}
    f = rs.feed(state, TODAY)
    assert [w["id"] for w in f] == ["W1000001", "W1000003"]                         # the preprint shows once, as published
    assert f[0]["names"] == ["Ada"] and f[0]["new"] and not f[1]["new"]
    old = rs.merge_works(works, [], "2027-12-01", "2027-12-01")                       # past KEEP_DAYS: gone
    assert old == {}


def test_suggestions_come_free_from_what_was_already_read():
    cited = [{"id": "https://openalex.org/A5000000009", "name": "Grace", "institution": "MIT", "count": 3},
             {"id": ADA, "name": "Ada", "count": 1}, {"id": "bad", "name": "No id"}]
    field = [{"openalex": "A5000000009", "name": "Grace", "papers": 2}, {"openalex": "A5000000010", "name": "Linus", "papers": 1},
             {"openalex": ME, "name": "Me", "papers": 4}]
    s = rs.suggestions(cited, field, [ADA], ME)
    assert [p["id"] for p in s] == ["A5000000009", "A5000000010"]
    assert s[0]["why"] == "cites your work (3×); leads 2 of the papers rising in your field" and s[0]["institution"] == "MIT"


class _Net:
    def __init__(self, answer, status=200):
        self.answer, self.status, self.calls = answer, status, []

    def get(self, url, **kw):
        self.calls.append(url)
        r = requests.Response()
        r.status_code, r._content = self.status, json.dumps(self.answer).encode()
        return r


def test_one_search_for_everyone_due_and_each_checked_as_often_as_they_publish():
    rs.follow({"id": ADA, "name": "Ada Lovelace", "institution": "Cambridge", "topics": ["Genomics"]}, TODAY)
    rs.follow({"id": ALAN, "name": "Alan Turing"}, TODAY)
    rs.follow({"id": "not-an-id", "name": "x"}, TODAY)
    assert [p["id"] for p in rs.load()["following"]] == [ADA, ALAN]
    net = _Net(ANSWER)
    out = rs.refresh(session=net, today=TODAY)
    assert out["ok"] and len(net.calls) == 1 and f"author.id:{ADA}|{ALAN}" in net.calls[0]      # one call, both people
    people = {p["id"]: p for p in rs.load()["following"]}
    assert people[ADA]["checked"] == TODAY and people[ADA]["rate"] == pytest.approx(2 / 12, abs=0.001)
    again = _Net(ANSWER)
    rs.refresh(session=again, today="2026-10-21")
    assert again.calls == []                                                          # not due yet: a quiet week
    rs.refresh(session=again, today="2026-10-27")
    assert len(again.calls) == 1
    rs.mark_seen(["W1000001"])
    assert [w["new"] for w in rs.feed(rs.load(), TODAY)] == [False, True]
    rs.unfollow(ALAN)
    assert [w["id"] for w in rs.feed(rs.load(), TODAY)] == ["W1000001"]               # their work goes with them
    busy = rs.refresh(session=_Net({}, status=429), force=True, today="2026-10-28")
    assert busy["busy"] and not busy["ok"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_reads_links_and_suggests_the_same():
    cited = [{"id": "https://openalex.org/A5000000009", "name": "Grace", "institution": "MIT", "count": 3}, {"id": ADA, "name": "Ada", "count": 1}]
    field = [{"openalex": "A5000000009", "name": "Grace", "papers": 2}, {"openalex": "A5000000010", "name": "Linus", "papers": 1}]
    said = phone.run("""
import { feed, intervalDays, isDue, mergeWorks, parseWorks, rateOf, since, suggestions, worksUrl } from './lib/researchers.ts';
const found = parseWorks(INPUT.answer, [INPUT.ada, INPUT.alan]);
const works = mergeWorks({}, found, INPUT.today, INPUT.today);
out({ found, works, feed: feed({ following: [{ id: INPUT.ada, name: 'Ada' }, { id: INPUT.alan, name: 'Alan' }] as any, works, seen: ['W1000003'] }, INPUT.today),
      sug: suggestions(INPUT.cited, INPUT.field, [INPUT.ada], ''), iv: [5, 2, 1, 0.5, 0.1, 0].map(intervalDays),
      rate: rateOf(['2026-10-01', '2026-09-01', '2025-01-01', ''], INPUT.today), since: [since(INPUT.today), since('2026-10-31')],
      due: [isDue({ checked: '', rate: 0 } as any, INPUT.today), isDue({ checked: '2026-10-19', rate: 1 } as any, INPUT.today)],
      url: worksUrl([INPUT.alan, INPUT.ada], INPUT.today) });
""", {"answer": ANSWER, "ada": ADA, "alan": ALAN, "today": TODAY, "cited": cited, "field": field})
    found = rs.parse_works(ANSWER, [ADA, ALAN])
    works = rs.merge_works({}, found, TODAY, TODAY)
    assert said["found"] == json.loads(json.dumps(found)) and said["works"] == json.loads(json.dumps(works))
    assert said["feed"] == json.loads(json.dumps(rs.feed({"following": [{"id": ADA, "name": "Ada"}, {"id": ALAN, "name": "Alan"}],
                                                           "works": works, "seen": ["W1000003"]}, TODAY)))
    assert said["sug"] == rs.suggestions(cited, field, [ADA], "")
    assert said["iv"] == [rs.interval_days(x) for x in (5, 2, 1, 0.5, 0.1, 0)]
    assert said["rate"] == rs.rate_of(["2026-10-01", "2026-09-01", "2025-01-01", ""], TODAY)
    assert said["since"] == [rs.since(TODAY), rs.since("2026-10-31")]
    assert said["due"] == [True, False] and said["url"] == rs.works_url([ALAN, ADA], TODAY)


def test_new_work_can_be_a_notification():
    from mygeeky import notify
    assert "researchers" in notify.ORDER and notify.TAB["researchers"] == "researchers"
    c = notify.candidates(TODAY, works=[{"id": "W1", "title": "New", "seen": "2026-10-19"},
                                        {"id": "W2", "title": "Preprint now published", "seen": "2026-10-19", "published_as": "W1"},
                                        {"id": "W3", "title": "Old", "seen": "2026-09-01"}])
    assert [x["id"] for x in c] == ["work:W1"] and "📄 1 new paper from people you follow" in notify.summary(c)["body"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_counts_who_leads_the_rising_papers():
    said = phone.run("""
import { fieldPeople } from './lib/researchers.ts';
out(fieldPeople(INPUT));
""", [{"leads": [{"name": "Grace", "openalex": "A5000000009"}, {"name": "Linus", "openalex": "A5000000010"}]},
      {"leads": [{"name": "Grace", "openalex": "A5000000009"}, {"name": "No id", "openalex": ""}]}])
    assert said == [{"openalex": "A5000000009", "name": "Grace", "papers": 2}, {"openalex": "A5000000010", "name": "Linus", "papers": 1}]
