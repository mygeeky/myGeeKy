"""🌟 Leading lights: the list is cleaned like any internet text, the set on show follows your Model and changes every
three days without repeats, the latest papers and the report are read right from OpenAlex's answers, and the phone
(lib/lights.ts) answers exactly as the computer does."""
from __future__ import annotations

import filecmp
from pathlib import Path

import pytest

import phone
from mygeeky import lights

ROOT = Path(__file__).resolve().parents[1]


def person(aid, name, badge="cited", topics=(), field="Genetics & genomics", cited=0, **more):
    return {"id": aid, "name": name, "badge": badge, "why": "Among the most cited", "source": "https://openalex.org/T1",
            "field": field, "topics": list(topics), "institution": "Broad Institute", "cited": cited, **more}


PEOPLE = [person("A1001", "Ann", topics=["Genetic Associations and Epidemiology"], cited=900),
          person("A1002", "Bo", topics=["Systemic Lupus Erythematosus Research"], cited=500, field="Biology & medicine"),
          person("A1003", "Cy", badge="nobel", topics=["RNA interference"], cited=300, field="Biology & medicine"),
          person("A1004", "Di", badge="tool", topics=["Single-cell RNA sequencing", "Genetic Associations"], cited=200),
          person("A1005", "Ed", badge="prize", topics=["Deep learning"], cited=800, field="Computer science & AI"),
          person("A1006", "Fa", topics=["Genetic diversity"], cited=100)]
W = {"genetic": 1.0, "lupus": 0.6, "single-cell": 0.5}


def test_the_shipped_list_is_clean_and_the_same_on_both_apps():
    data = lights.load()
    assert data["version"] and len(data["people"]) >= 50
    assert filecmp.cmp(lights.DATA_FILE, ROOT / "mobile" / "src" / "data" / "lights.json", shallow=False)
    assert all(p["badge"] in lights.BADGES and p["name"] and p["why"] for p in data["people"])
    assert len({p["id"] for p in data["people"]}) == len(data["people"])


def test_only_what_each_field_may_hold():
    bad = person("A2001", "<b>X</b>  \n Y", topics=["t"] * 9, orcid="nope", scholar="https://evil.example/?user=abcdefg",
                 github="bad user", source="javascript:alert(1)")
    p = lights.clean_person(bad)
    assert p["name"] == "<b>X</b> Y" and len(p["topics"]) == 6, "plain text (shown as plain text), capped"
    assert p["orcid"] == p["scholar"] == p["github"] == p["source"] == ""
    good = lights.clean_person(person("A2002", "Z", orcid="0000-0002-1825-009X",
                                      scholar="https://scholar.google.com/citations?user=AbC-12_xyz", github="zz-top"))
    assert [x[0] for x in lights.links(good)] == ["Google Scholar", "ORCID", "OpenAlex", "GitHub"]
    assert lights.clean_person(person("W1", "not an author")) is None and lights.clean_person(person("A3", "x", badge="?")) is None
    assert len(lights.clean({"people": [person("A4444", "a"), person("A4444", "a")]})["people"]) == 1


def test_the_set_follows_your_model_and_goes_round_without_repeats():
    people = [lights.clean_person(p) for p in PEOPLE]
    first = [p["id"] for p in lights.pick(people, W, "2026-10-25", n=2)]
    assert len(first) == 2 and lights.pick(people, W, "2026-10-25", n=2) == lights.pick(people, W, "2026-10-25", n=2)
    fitting = {"A1001", "A1002", "A1004", "A1006"}                  # genetic / lupus / single-cell; not Cy or Ed
    seen = []
    day = "2026-10-25"
    for _ in range(2):                                              # two sets of two: everyone who fits, once
        seen += [p["id"] for p in lights.pick(people, W, day, n=2)]
        day = lights.next_change(day)
    assert set(seen) == fitting and len(seen) == 4
    assert lights.next_change("2026-10-25") > "2026-10-25"
    assert lights.period("2026-10-25") == lights.period(lights.next_change("2026-10-25")) - 1
    nobody = [p["id"] for p in lights.pick(people, {}, "2026-10-25", n=6)]
    assert set(nobody) == {p["id"] for p in people} and nobody[:2] == ["A1005", "A1003"], "no Model: laureates first"


AUTHOR = {"works_count": 812, "cited_by_count": 150000, "summary_stats": {"h_index": 140, "i10_index": 600},
          "counts_by_year": [{"year": 2026, "works_count": 20, "cited_by_count": 9000},
                             {"year": 2024, "works_count": 31, "cited_by_count": 12000}],
          "topics": [{"display_name": "Genetic Associations and Epidemiology"}, {"display_name": "Cancer genomics"}],
          "last_known_institutions": [{"display_name": "Broad Institute"}]}
TOP = {"results": [{"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/x", "title": "Big paper",
                    "publication_year": 2009, "cited_by_count": 40000, "primary_location": {"source": {"display_name": "Nature"}}}]}
RECENT = {"results": [
    {"id": "https://openalex.org/W9", "doi": None, "title": "Newest", "publication_date": "2026-10-01",
     "primary_location": {"source": {"display_name": "bioRxiv"}},
     "authorships": [{"author": {"id": "https://openalex.org/A1001"}}, {"author": {"id": "https://openalex.org/A1002"}}]},
    {"id": "https://openalex.org/W8", "doi": "https://doi.org/10.2/y", "title": "Older", "publication_date": "2026-05-01",
     "authorships": [{"author": {"id": "https://openalex.org/A1001"}}]},
    {"id": "https://openalex.org/W7", "title": "Third", "publication_date": "2026-01-01",
     "authorships": [{"author": {"id": "https://openalex.org/A1001"}}]}]}


def test_latest_papers_and_the_report_from_openalex():
    got = lights.parse_recent(RECENT, ["A1001", "A1002", "A1003"])
    assert [w["title"] for w in got["A1001"]] == ["Newest", "Older"] and got["A1003"] == []
    assert got["A1002"][0]["url"] == "https://openalex.org/W9" and got["A1001"][1]["url"] == "https://doi.org/10.2/y"
    assert "author.id:A1001|A1002" in lights.recent_url(["A1002", "A1001"], "2026-10-25")
    assert "from_publication_date:2025-10-01" in lights.recent_url(["A1"], "2026-10-25")
    r = lights.report(AUTHOR, TOP, W, "2026-10-25")
    assert (r["works"], r["cited"], r["h"], r["i10"], r["institution"]) == (812, 150000, 140, 600, "Broad Institute")
    assert len(r["years"]) == 10 and r["years"][-1] == [2026, 20, 9000] and r["years"][-2] == [2025, 0, 0]
    assert r["topics"] == [["Genetic Associations and Epidemiology", True], ["Cancer genomics", False]]
    assert r["top"][0] == {"title": "Big paper", "url": "https://doi.org/10.1/x", "date": "", "venue": "Nature",
                           "year": 2009, "cited": 40000}
    assert lights.report(None, None, {}, "2026-10-25")["works"] == 0, "a broken answer is an empty report"


@pytest.mark.skipif(not phone.node_ok(), reason="needs Node 22.6+ and the phone's packages")
def test_the_phone_answers_the_same():
    said = phone.run("""
import * as L from './lib/lights.ts';
const [people, w, recent, author, top, bad] = INPUT;
const clean = people.map(L.cleanPerson);
const days = ['2026-10-25', '2026-10-28', '2026-12-31', '2027-03-01'];
out({ clean, bad: L.cleanPerson(bad), picks: days.map((d) => L.pick(clean, w, d, 2).map((p) => [p.id, p.fit])),
  none: L.pick(clean, {}, '2026-10-25', 6).map((p) => p.id), next: days.map((d) => L.nextChange(d)),
  period: days.map((d) => L.period(d)), recent: L.parseRecent(recent, ['A1001', 'A1002', 'A1003']),
  url: L.recentUrl(['A1002', 'A1001'], '2026-10-25'), report: L.report(author, top, w, '2026-10-25'),
  links: L.links(clean[0]), shipped: L.load().people.length });
""", [PEOPLE, W, RECENT, AUTHOR, TOP, person("A2001", "<b>X</b>  \n Y", orcid="nope", github="bad user")])
    clean = [lights.clean_person(p) for p in PEOPLE]
    days = ["2026-10-25", "2026-10-28", "2026-12-31", "2027-03-01"]
    assert said["clean"] == clean
    assert said["bad"] == lights.clean_person(person("A2001", "<b>X</b>  \n Y", orcid="nope", github="bad user"))
    assert said["picks"] == [[[p["id"], p["fit"]] for p in lights.pick(clean, W, d, 2)] for d in days]
    assert said["none"] == [p["id"] for p in lights.pick(clean, {}, "2026-10-25", 6)]
    assert said["next"] == [lights.next_change(d) for d in days] and said["period"] == [lights.period(d) for d in days]
    assert said["recent"] == lights.parse_recent(RECENT, ["A1001", "A1002", "A1003"])
    assert said["url"] == lights.recent_url(["A1002", "A1001"], "2026-10-25")
    assert said["report"] == lights.report(AUTHOR, TOP, W, "2026-10-25")
    assert said["links"] == [list(x) for x in lights.links(clean[0])]
    assert said["shipped"] == len(lights.load()["people"])


def test_the_panel_shows_leading_lights_and_a_report(qapp_offscreen, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from mygeeky import researchers as rs
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui import app as logic
    from mygeeky.gui import lights_ui
    from tests.test_freshness import _close, _quiet_panel
    asked, shown, opened = [], [], []
    monkeypatch.setattr(lights, "fetch_recent", lambda people, today=None, session=None: asked.append(len(people)) or {
        "ok": True, "recent": {p["id"]: [{"title": f"New paper by {p['name']}", "url": "https://doi.org/10.1/z",
                                          "date": "2026-10-01", "venue": "Nature"}] for p in people}})
    monkeypatch.setattr(lights, "fetch_report", lambda aid, weights, today=None, session=None: {
        "ok": True, "report": lights.report(AUTHOR, TOP, weights, "2026-10-25")})
    monkeypatch.setattr(lights_ui.ReportDialog, "exec", lambda self: shown.append(self.windowTitle()) or 0)
    monkeypatch.setattr(logic, "open_link", lambda url: opened.append(url) or True)
    app, p = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me", keywords=["gwas", "genetic"]))
    try:
        p.resize(460, 900)
        p.show()
        p.nav_buttons["circle"].click() if "circle" in p.nav_buttons else None
        p._switch_tab("researchers")
        page = p.researchers_page
        page.set_part("lights")
        for _ in range(10):
            for w in list(p._workers):
                w.wait(3000)
            QApplication.processEvents()
        texts = [x.text() for x in page.body.findChildren(QLabel)]
        assert asked == [lights.PER_SET], "one search for everyone on show"
        assert sum(t.startswith("📄 New paper by") for t in texts) == lights.PER_SET
        assert any("new set every 3 days" in t for t in texts) and any("Report a mistake" in t for t in texts)
        report = next(b for b in page.body.findChildren(QPushButton) if b.text() == "Report")
        report.click()
        for _ in range(10):
            for w in list(p._workers):
                w.wait(3000)
            QApplication.processEvents()
        assert len(shown) == 1
        follow = next(b for b in page.body.findChildren(QPushButton) if b.text() == "Follow")
        follow.click()
        assert len(rs.load()["following"]) == 1
        assert logic.lights_weights(p.cfg).get("gwas") is not None
        page.grab().save(str(ROOT / "tests" / ".lights-shot.png")) if False else None
    finally:
        _close(p)
