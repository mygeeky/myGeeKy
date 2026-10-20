"""Who cited you: reading OpenAlex's answers, what's asked and when, the page, and the phone agreeing."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import phone
from mygeeky import citedby

ME = "A111"
MINE = {"W100", "W200", "W300"}


def work(wid, title, when, authors, refs):
    return {"id": f"https://openalex.org/{wid}", "title": title, "publication_date": when, "doi": None,
            "authorships": [{"author": {"id": f"https://openalex.org/{a}", "display_name": n},
                             "institutions": [{"display_name": i, "country_code": c}] if i else []}
                            for a, n, i, c in authors],
            "referenced_works": [f"https://openalex.org/{r}" for r in refs]}


CITING = {"results": [
    work("W901", "Fine-mapping lupus", "2026-10-10", [("A505", "Ada Doe", "Lund University", "se"), ("A606", "Bo Lee", "Oxford", "gb")], ["W100", "W999"]),
    work("W902", "Lupus GWAS again", "2026-09-01", [("A505", "Ada Doe", "Lund University", "se")], ["W100", "W200"]),
    work("W903", "My own follow-up", "2026-10-01", [(ME, "Me Myself", "Lund University", "se")], ["W300"]),
    work("W904", "Immune traits", "2025-01-05", [("A707", "Cy Kim", "", ""), ("A505", "Ada Doe", "Lund University", "se")], ["W200"]),
    {"id": "junk"}, "x",
]}
AUTHOR = {"display_name": "Me Myself", "cited_by_count": 321, "works_count": 12, "summary_stats": {"h_index": 7, "i10_index": 5}}


def test_reading_citing_papers():
    got = citedby.parse_citing(CITING, MINE, ME, "2026-10-19T00:00:00+00:00")
    assert [c["id"] for c in got] == ["W901", "W902", "W903", "W904"]
    assert got[0]["cites"] == ["W100"] and got[1]["cites"] == ["W100", "W200"]
    assert got[0]["authors"][1] == {"name": "Bo Lee", "id": "A606", "institution": "Oxford", "country": "GB"}
    assert got[2]["self"] is True and got[0]["self"] is False
    assert citedby.parse_author(AUTHOR) == {"name": "Me Myself", "cited": 321, "works": 12, "h": 7, "i10": 5}


def test_only_papers_whose_count_rose_are_asked_about():
    assert citedby.to_ask({"W1": 5, "W2": 0, "W3": 9}, None) == ["W3", "W1"], "the first time: every cited one"
    assert citedby.to_ask({"W1": 5, "W2": 1, "W3": 9}, {"W1": 5, "W2": 0, "W3": 8}) == ["W3", "W2"]
    assert citedby.to_ask({"W1": 5}, {"W1": 5}) == [], "nothing new: no request at all"


def test_merging_keeps_when_a_paper_was_first_seen():
    old = citedby.parse_citing(CITING, MINE, ME, "2026-09-01T00:00:00+00:00")[:2]
    new = citedby.parse_citing(CITING, MINE, ME, "2026-10-19T00:00:00+00:00")
    merged = citedby.merge(old, new)
    assert {c["id"]: c["seen"][:10] for c in merged}["W901"] == "2026-09-01"
    assert {c["id"]: c["seen"][:10] for c in merged}["W904"] == "2026-10-19"
    assert [c["id"] for c in merged] == ["W901", "W903", "W902", "W904"], "newest first"


def state():
    return {"author": ME, "updated_at": "2026-10-19T00:00:00+00:00", "totals": citedby.parse_author(AUTHOR),
            "papers": {"W100": {"title": "GWAS of lupus", "cited": 40}, "W200": {"title": "Immune genes", "cited": 9},
                       "W300": {"title": "Old paper", "cited": 3}},
            "citing": citedby.merge(citedby.parse_citing(CITING, MINE, ME, "2026-09-01T00:00:00+00:00")[:1],
                                    citedby.parse_citing(CITING, MINE, ME, "2026-10-15T00:00:00+00:00"))}


def test_the_page():
    s = citedby.summary(state(), "2026-10-19")
    assert s["found"] == 3, "your own papers citing you don't count"
    assert s["this_month"] == 1 and s["new"] == 2
    assert [c["id"] for c in s["citing"]] == ["W901", "W902", "W904"] and s["citing"][0]["new"] is False
    assert s["citing"][1]["cites_titles"] == ["GWAS of lupus", "Immune genes"]
    assert s["people"][0] == {"name": "Ada Doe", "id": "A505", "institution": "Lund University", "country": "SE", "count": 3}
    assert all(p["id"] != ME for p in s["people"])
    assert s["countries"] == [{"code": "SE", "count": 3}, {"code": "GB", "count": 1}]
    assert s["papers"][0] == {"id": "W100", "title": "GWAS of lupus", "count": 2, "cited": 40}
    assert s["totals"]["h"] == 7


class Reply:
    def __init__(self, status, body):
        self.status_code, self._b = status, body

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise __import__("requests").HTTPError(str(self.status_code))


class Session:
    def __init__(self, replies):
        self.replies, self.asked = list(replies), []

    def get(self, url, params=None, **kw):
        self.asked.append((url, dict(params or {})))
        return self.replies.pop(0)


def test_a_daily_read_asks_little_and_keeps_what_it_found(tmp_path, monkeypatch):
    monkeypatch.setattr(citedby, "CITEDBY_FILE", tmp_path / "citedby.json")
    works = {"results": [{"id": f"https://openalex.org/{w}", "title": t, "cited_by_count": n}
                         for w, t, n in (("W100", "GWAS of lupus", 40), ("W200", "Immune genes", 9), ("W300", "Old", 0))]}
    s = Session([Reply(200, AUTHOR), Reply(200, works), Reply(200, CITING)])
    out = citedby.refresh(ME, session=s, now=datetime(2026, 10, 19, tzinfo=timezone.utc))
    assert out["ok"] and len(s.asked) == 3
    assert s.asked[2][1]["filter"] == "cites:W100|W200", "only cited papers, most cited first"
    assert len(out["state"]["citing"]) == 4
    assert all(c["seen"] == "" for c in out["state"]["citing"]), "the first read sets the starting point: nothing NEW"
    assert citedby.summary(out["state"], "2026-10-19")["new"] == 0
    # the next day: nothing rose, so two requests and no citing search
    s2 = Session([Reply(200, AUTHOR), Reply(200, works)])
    out2 = citedby.refresh(ME, session=s2, now=datetime(2026, 10, 20, 2, tzinfo=timezone.utc))
    assert out2["ok"] and len(s2.asked) == 2 and len(out2["state"]["citing"]) == 4


def test_a_busy_openalex_keeps_what_was_found(tmp_path, monkeypatch):
    monkeypatch.setattr(citedby, "CITEDBY_FILE", tmp_path / "citedby.json")
    (tmp_path / "citedby.json").write_text(json.dumps(state()))
    out = citedby.refresh(ME, session=Session([Reply(429, {})]), force=True)
    assert out.get("busy") and len(out["state"]["citing"]) == len(state()["citing"])
    assert not citedby.refresh("not-an-id")["ok"]


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_finds_and_shows_the_same():
    st = state()
    said = phone.run("""
import * as C from './lib/cited-by.ts';
const [citing, mine, me, st, author] = INPUT;
const a = C.parseCiting(citing, new Set(mine), me, '2026-09-01T00:00:00+00:00');
const b = C.parseCiting(citing, new Set(mine), me, '2026-10-19T00:00:00+00:00');
out({ parsed: b, merged: C.merge(a.slice(0, 2), b), author: C.parseAuthor(author),
  ask: [C.toAsk({ W1: 5, W2: 0, W3: 9 }, null), C.toAsk({ W1: 5, W2: 1, W3: 9 }, { W1: 5, W2: 0, W3: 8 }), C.toAsk({ W1: 5 }, { W1: 5 })],
  summary: C.summary(st, '2026-10-19'), empty: C.summary({}, '2026-10-19') });
""", [CITING, sorted(MINE), ME, st, AUTHOR])
    assert said["parsed"] == citedby.parse_citing(CITING, MINE, ME, "2026-10-19T00:00:00+00:00")
    assert said["merged"] == citedby.merge(citedby.parse_citing(CITING, MINE, ME, "2026-09-01T00:00:00+00:00")[:2],
                                           citedby.parse_citing(CITING, MINE, ME, "2026-10-19T00:00:00+00:00"))
    assert said["author"] == citedby.parse_author(AUTHOR)
    assert said["ask"] == [["W3", "W1"], ["W3", "W2"], []]
    assert said["summary"] == json.loads(json.dumps(citedby.summary(st, "2026-10-19")))
    assert said["empty"] == json.loads(json.dumps(citedby.summary({}, "2026-10-19")))
