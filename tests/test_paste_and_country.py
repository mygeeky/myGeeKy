"""A page pasted by hand, and the country a listing is in."""

from datetime import date

import pytest

from mygeeky import curated, scout


# --------------------------------------------------------------------------- the country
def test_the_country_is_read_from_the_end_where_people_put_it():
    assert curated.country_of("Lyon, France") == "France"
    assert curated.country_of("Cambridge, Cambridgeshire, UK") == "United Kingdom"
    assert curated.country_of("Doha, Qatar") == "Qatar"
    assert curated.country_of("Abu Dhabi, United Arab Emirates") == "United Arab Emirates"


def test_a_country_written_as_a_code_in_brackets_is_still_read():
    """Boards write it this way: "Dortmund, Nordrhein-Westfalen (DE)"."""
    assert curated.country_of("Dortmund, Nordrhein-Westfalen (DE)") == "Germany"
    assert curated.country_of("Houston, Texas (US)") == "United States"


def test_an_american_board_naming_only_the_state_is_still_read():
    assert curated.country_of("Los Angeles, California") == "United States"
    assert curated.country_of("Boston, Massachusetts") == "United States"


def test_a_place_that_names_no_country_gets_none_rather_than_a_guess():
    """"Lyon" alone must not invent a country called Lyon: a wrong country is worse than no country."""
    assert curated.country_of("Lyon") == ""
    assert curated.country_of("Devon, Exeter") == ""
    assert curated.country_of("") == "" and curated.country_of(None) == ""


def test_somewhere_that_is_nowhere_has_no_country():
    for nowhere in ("online", "Online", "remote", "worldwide", "hybrid"):
        assert curated.country_of(nowhere) == "", nowhere


def test_the_short_forms_people_actually_write():
    for written, meant in (("London, UK", "United Kingdom"), ("Edinburgh, Scotland", "United Kingdom"),
                           ("Boston, USA", "United States"), ("Seoul, Korea", "South Korea"),
                           ("Istanbul, Turkey", "Türkiye"), ("Amsterdam, Holland", "Netherlands")):
        assert curated.country_of(written) == meant, written


def _job(place, **more):
    return {"id": "a-lab-post-2026", "title": "Postdoc in statistical genetics",
            "url": "https://example.org/1", "deadline": "2026-12-01", "org": "A Lab", "place": place, **more}


def test_a_listing_carries_its_country():
    assert curated.clean_item("jobs", _job("Lyon, France"))["country"] == "France"
    conf = curated.clean_item("conferences", _job("Heidelberg, Germany"))
    assert conf["country"] == "Germany"


def test_the_filter_only_offers_countries_that_have_something_behind_them():
    items = [curated.clean_item("jobs", _job("Lyon, France")),
             curated.clean_item("jobs", dict(_job("Cambridge, UK"), id="b-lab-post-2026")),
             curated.clean_item("jobs", dict(_job("online"), id="c-lab-post-2026"))]
    assert curated.countries_in(items) == ["France", "United Kingdom"]


def test_the_countries_offered_are_in_a_settled_order():
    items = [curated.clean_item("jobs", dict(_job(p), id=f"lab-{i}-post-2026"))
             for i, p in enumerate(("Oslo, Norway", "Lyon, France", "Cairo, Egypt"))]
    assert curated.countries_in(items) == ["Egypt", "France", "Norway"]


# --------------------------------------------------------------------------- a page pasted by hand
PAGE = """Bioinformatics Research Associate
Imperial College London - National Heart & Lung Institute
London, United Kingdom
Salary: £46,000 to £54,000 per annum
We are seeking a Bioinformatics Research Associate to analyse single-cell RNA-seq data from
cardiac tissue. You will work within a team of computational biologists.
Closing date: 10 November 2026.
Apply online through the Imperial College London recruitment site."""

LINK = "https://www.jobs.ac.uk/job/ABC123/bioinformatics-research-associate"


@pytest.fixture(autouse=True)
def _own_queue(tmp_path, monkeypatch):
    """Never touch the maker's real queue: an ad-hoc run must not write their data."""
    monkeypatch.setattr(scout, "SCOUT_FILE", tmp_path / "scout.json")


def _deepseek(answer):
    """A stand-in for DeepSeek that replies with whatever this test wants."""
    import json

    class Reply:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": json.dumps(answer)}}]}

    return lambda url, json=None, timeout=None, headers=None: Reply()


FOUND = {"listings": [{
    "title": "Bioinformatics Research Associate", "language": "English",
    "title_en": "Bioinformatics Research Associate",
    "summary_en": "Analysing single-cell RNA-seq data from cardiac tissue at Imperial College London.",
    "org": "Imperial College London", "place": "London, United Kingdom", "type": "postdoc",
    "deadline": "2026-11-10", "deadline_quote": "Closing date: 10 November 2026",
    "keywords": ["single-cell", "rna-seq"], "relevance": 0.95, "confidence": 0.95}]}


def test_a_pasted_listing_goes_through_the_same_checks_and_into_the_same_queue():
    out = scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15),
                           post=_deepseek(FOUND))
    assert out == {"added": 1, "dropped": 0, "why": [], "found": 1}
    queued = list(scout.load()["candidates"].values())
    assert len(queued) == 1
    c = queued[0]
    assert c["status"] == "new", "it waits for the maker, it does not go straight onto the lists"
    assert c["from"] == "pasted" and c["source"] == LINK
    assert c["item"]["country"] == "United Kingdom"
    assert all(ok for ok, _ in c["checks"]), c["checks"]


def test_the_pasted_text_is_what_the_quote_is_checked_against():
    """The whole point of the paste standing in for the page.

    A quote that is not in the pasted text fails its check and drags the score down, exactly as it would
    on a page myGeeKy fetched itself. It is not thrown away outright -- nothing the scout finds is -- it
    goes to the maker carrying a ✗, which is what the review queue is for."""
    invented = {"listings": [dict(FOUND["listings"][0],
                                  deadline_quote="Applications close on 10 November 2026")]}
    scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15), post=_deepseek(invented))
    bad = list(scout.load()["candidates"].values())[0]
    checks = dict((text, ok) for ok, text in bad["checks"])
    assert checks["deadline sentence is on the page"] is False
    # the invented sentence does hold the date it claims -- that is exactly why it is not the check that
    # catches it. Being findable in the text is what an invention cannot fake.
    assert checks["that sentence holds the date"] is True

    # a second run, this time with the sentence that really is in the text
    scout.save({"candidates": {}, "rejected": [], "sources": scout.SOURCES, "focus": scout.DEFAULT_FOCUS})
    scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15), post=_deepseek(FOUND))
    good = list(scout.load()["candidates"].values())[0]
    assert good["score"] > bad["score"], "a sentence really in the text scores higher than an invented one"


def test_a_listing_with_no_deadline_in_the_text_is_refused():
    """Most American job ads carry no closing date, and myGeeKy cannot publish what it cannot date."""
    undated = {"listings": [dict(FOUND["listings"][0], deadline="", deadline_quote="")]}
    out = scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15),
                           post=_deepseek(undated))
    assert out["added"] == 0
    assert any("deadline" in w for w in out["why"]), out["why"]


def test_a_listing_keeps_its_own_link_when_the_text_carried_one():
    own = "https://www.imperial.ac.uk/jobs/description/XYZ/"
    with_link = {"listings": [dict(FOUND["listings"][0], link=own)]}
    scout.from_paste("jobs", f"{PAGE}\nApply at {own}", LINK, key="sk-test", today=date(2026, 10, 15),
                     post=_deepseek(with_link))
    assert list(scout.load()["candidates"].values())[0]["item"]["url"] == own


def test_a_link_the_text_never_said_is_replaced_by_the_page():
    made_up = {"listings": [dict(FOUND["listings"][0], link="https://apply-imperial.example/now")]}
    scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15), post=_deepseek(made_up))
    assert list(scout.load()["candidates"].values())[0]["item"]["url"] == LINK


def test_nothing_in_the_text_is_not_an_error():
    out = scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15),
                           post=_deepseek({"listings": []}))
    assert out == {"added": 0, "dropped": 0, "why": [], "found": 0}


def test_the_same_listing_pasted_twice_is_only_queued_once():
    for _ in range(2):
        scout.from_paste("jobs", PAGE, LINK, key="sk-test", today=date(2026, 10, 15), post=_deepseek(FOUND))
    assert len(scout.load()["candidates"]) == 1


def test_it_refuses_to_guess_what_was_pasted():
    for text, url, why in ((PAGE, "", "link"), ("too short", LINK, "short"), (PAGE, "ftp://x/y", "link")):
        with pytest.raises(ValueError, match=why):
            scout.from_paste("jobs", text, url, key="sk-test", today=date(2026, 10, 15),
                             post=_deepseek(FOUND))


def test_a_kind_myGeeKy_does_not_keep_is_refused():
    with pytest.raises(ValueError, match="kind must be"):
        scout.from_paste("resources", PAGE, LINK, key="sk-test", post=_deepseek(FOUND))


def test_the_sources_that_were_tested_are_the_ones_that_were_added():
    """Only boards that answer a plain fetch with real HTML belong in SOURCES; the rest go through paste."""
    urls = " ".join(s["url"] for s in scout.SOURCES)
    for blocked in ("indeed.com", "linkedin.com", "glassdoor.com", "monster.com", "ziprecruiter.com",
                    "simplyhired.com", "careerbuilder.com", "successfactors"):
        assert blocked not in urls, f"{blocked} cannot be read by a robot, or forbids one"
    assert "jobs.sciencecareers.org" in urls and "bioinformatics.org" in urls


# --------------------------------------------------------------------------- one filter, over everything
def _panel(monkeypatch):
    from tests.test_freshness import _quiet_panel
    from mygeeky.config import MyGeekyConfig
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    qapp, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="me"))
    panel._switch_tab("chances")
    for w in list(panel._workers):
        w.wait(5000)
    for _ in range(5):
        qapp.processEvents()
    return qapp, panel


def test_the_country_filter_sits_above_the_four_kinds(qapp_offscreen, monkeypatch):
    """It applies to all of them, so it belongs above them, not inside whichever one is open."""
    pytest.importorskip("PySide6")
    _, panel = _panel(monkeypatch)
    try:
        row = next(iter(panel.chance_mode_buttons.values())).parentWidget()
        layout = panel.country_picker.parentWidget().layout()
        assert layout.indexOf(panel.country_picker) < layout.indexOf(row), \
            "the location filter must come before the kinds it applies to"
        assert layout.indexOf(panel.country_picker) < layout.indexOf(panel.season_picker), \
            "and before the period picker, which applies only to seasons"
    finally:
        panel.close()


def test_the_chosen_country_is_kept_when_the_kind_is_switched(qapp_offscreen, monkeypatch):
    """Choosing Germany and pressing 🎤 Conferences must not quietly reset to anywhere."""
    pytest.importorskip("PySide6")
    qapp, panel = _panel(monkeypatch)
    try:
        offered = [panel.country_picker.itemData(i) or ""
                   for i in range(panel.country_picker.count())]
        if len(offered) < 2:
            pytest.skip("the shipped lists offer no country to choose")
        panel.country_picker.setCurrentIndex(1)
        chosen = offered[1]
        assert panel._country == chosen
        for mode in ("conferences", "funding", "seasons", "jobs"):
            panel._set_chance_mode(mode)
            qapp.processEvents()
            assert panel._country == chosen, f"the country was lost on {mode}"
    finally:
        panel.close()


def test_the_countries_offered_do_not_change_with_the_kind(qapp_offscreen, monkeypatch):
    """A filter above the kinds must offer the same choices whichever kind is open."""
    pytest.importorskip("PySide6")
    qapp, panel = _panel(monkeypatch)
    try:
        seen = []
        for mode in ("jobs", "funding", "conferences", "seasons"):
            panel._set_chance_mode(mode)
            qapp.processEvents()
            seen.append([panel.country_picker.itemData(i) or ""
                         for i in range(panel.country_picker.count())])
        assert all(s == seen[0] for s in seen), "the options shifted between kinds"
    finally:
        panel.close()


def test_a_season_that_leads_nowhere_in_particular_is_never_filtered_out(qapp_offscreen, monkeypatch):
    """MSCA goes to "Europe (or a third country, then Europe)", which is not a country."""
    pytest.importorskip("PySide6")
    _, panel = _panel(monkeypatch)
    try:
        panel._country = "Japan"
        assert panel._in_country({"goes_to": "Europe (or a third country, then Europe)"})
        assert panel._in_country({"goes_to": ""})
        assert panel._in_country({"goes_to": "Japan"})
        assert not panel._in_country({"goes_to": "Germany"})
        panel._country = ""
        assert panel._in_country({"goes_to": "Germany"}), "anywhere means everything"
    finally:
        panel.close()
