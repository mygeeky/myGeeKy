"""Seasons: scholarships that come back every year, and the care taken not to invent next year's date."""

from datetime import date

import pytest

from mygeeky import curated, scout, seasons


def _season(**more):
    base = {"id": "mext-research-egypt", "title": "MEXT Scholarship for Research Students",
            "url": "https://www.eg.emb-japan.go.jp/x", "org": "MEXT", "levels": ["master", "phd"],
            "for": ["Egypt"], "opens_about": "04-22", "closes_about": "05-14", "prepare_weeks": 10}
    base.update(more)
    return base


def _seen(opens="2026-04-22", closes="2026-05-14", checked=True, **more):
    return {"cycle": 2027, "opens": opens, "closes": closes, "checked": checked,
            "url": "https://www.eg.emb-japan.go.jp/x",
            "quote": "documents must be sent from April 22, 2026 until May 14, 2026", **more}


# --------------------------------------------------------------------------- what counts as evidence
def test_an_occurrence_without_a_page_or_a_sentence_is_not_evidence():
    """A date somebody wrote down is a claim. A date with a page and a quoted sentence is evidence."""
    assert seasons.clean_seen([_seen(url="")]) == []
    assert seasons.clean_seen([dict(_seen(), quote="")]) == []
    assert seasons.clean_seen([dict(_seen(), closes="")]) == []
    assert len(seasons.clean_seen([_seen()])) == 1


def test_an_occurrence_is_unchecked_until_something_checks_it():
    """Nothing may mark itself as confirmed just by being written down."""
    assert seasons.clean_seen([dict(_seen(), checked=True)])[0]["checked"] is True
    for sneaky in (None, "", "yes", 1, "true"):
        assert seasons.clean_seen([dict(_seen(), checked=sneaky)])[0]["checked"] is False


def test_a_window_that_closed_before_it_opened_is_thrown_out():
    assert seasons.clean_seen([_seen(opens="2026-05-14", closes="2026-04-22")]) == []


def test_occurrences_come_back_newest_first():
    out = seasons.clean_seen([_seen(opens="2024-04-06", closes="2024-04-30"),
                              _seen(opens="2026-04-22", closes="2026-05-14"),
                              _seen(opens="2025-04-11", closes="2025-05-02")])
    assert [s["closes"][:4] for s in out] == ["2026", "2025", "2024"]


def test_a_season_is_only_shown_once_a_page_has_been_found():
    assert not seasons.evidenced(seasons.clean_season(_season(seen=[_seen(checked=False)])))
    assert seasons.evidenced(seasons.clean_season(_season(seen=[_seen(checked=True)])))


# --------------------------------------------------------------------------- the season itself
def test_a_season_that_cannot_say_when_anything_happens_is_refused():
    """With no history and no stated window there is nothing to be prepared for."""
    assert seasons.clean_season(_season(opens_about="", closes_about="", seen=[])) is None


def test_a_season_with_only_a_stated_window_is_kept_but_has_no_evidence():
    """How a newly discovered programme arrives: a window, no history, maker-only until checked."""
    s = seasons.clean_season(_season(seen=[]))
    assert s is not None and not seasons.evidenced(s)
    assert seasons.pattern(s) == ("04-22", "05-14", 0)


def test_rubbish_is_refused():
    for bad in (None, "", [], {"id": "x"}, _season(id="Not An Id"), _season(title=""), _season(url="")):
        assert seasons.clean_season(bad) is None


def test_the_history_is_what_sets_the_expectation_not_the_stated_window():
    """The stated window is a fallback. Once there are real years, those are what the next one comes from."""
    s = seasons.clean_season(_season(opens_about="01-01", closes_about="12-31",
                                     seen=[_seen(opens="2024-04-06", closes="2024-04-30"),
                                           _seen(opens="2025-04-11", closes="2025-05-02"),
                                           _seen(opens="2026-04-22", closes="2026-05-14")]))
    opens, closes, years = seasons.pattern(s)
    assert (opens, closes) == ("04-11", "05-02"), "the middle year, so one odd year cannot drag it"
    assert years == 3


# --------------------------------------------------------------------------- where it stands today
def test_a_window_myGeeKy_actually_read_is_the_only_confirmed_one():
    s = seasons.clean_season(_season(seen=[_seen(opens="2026-10-01", closes="2026-11-15")]))
    now = seasons.when(s, date(2026, 10, 15))
    assert now["state"] == "open" and now["confirmed"] is True
    assert now["days_to_close"] == 31
    assert seasons.notice_text(now) == "open now · closes in 31 days"


def test_an_expected_window_never_calls_itself_confirmed():
    """Same month, but the year myGeeKy read was last year's. It may say 'expected', not 'open'."""
    s = seasons.clean_season(_season(seen=[_seen(opens="2025-10-01", closes="2025-11-15")]))
    now = seasons.when(s, date(2026, 10, 15))
    assert now["state"] == "open" and now["confirmed"] is False
    assert seasons.notice_text(now) == "expected to be open now"


def test_the_next_one_is_worked_out_and_said_as_an_expectation():
    s = seasons.clean_season(_season(seen=[_seen()]))
    now = seasons.when(s, date(2026, 10, 15))
    assert now["opens"] == "2027-04-22" and now["confirmed"] is False
    assert "expected" in seasons.notice_text(now)
    assert now["days_to_open"] == 189


def test_nothing_ever_states_a_future_date_as_a_fact():
    """Every phrase for a date still to come is hedged; only a window read off a page is not."""
    s = seasons.clean_season(_season(seen=[_seen()]))
    for day in (date(2026, 10, 15), date(2027, 1, 1), date(2027, 4, 1), date(2027, 6, 1)):
        state = seasons.when(s, day)
        said = seasons.notice_text(state)
        if not state["confirmed"]:
            assert "expected" in said or said == "no dates yet", said


def test_a_season_whose_window_straddles_the_new_year():
    """November to February: the close is in the year after the open, and that must not confuse it."""
    s = seasons.clean_season(_season(id="csc-type-a", opens_about="11-01", closes_about="02-14", seen=[]))
    now = seasons.when(s, date(2026, 10, 15))
    assert now["state"] in ("soon", "later") and now["opens"] == "2026-11-01"
    assert now["closes"] > now["opens"], "it closes after it opens, in the following year"
    mid = seasons.when(s, date(2026, 12, 20))
    assert mid["state"] == "open", "December is inside a November-to-February window"


def test_the_twenty_ninth_of_february_does_not_crash_a_normal_year():
    s = seasons.clean_season(_season(opens_about="02-29", closes_about="03-15", seen=[]))
    assert seasons.when(s, date(2026, 1, 1))["opens"] == "2026-02-28"


# --------------------------------------------------------------------------- how much warning
def test_the_warning_is_at_least_a_fortnight_but_longer_when_more_is_needed():
    """The floor is 15 days. A programme wanting a proposal and two referees gets its 10 weeks."""
    quick = seasons.clean_season(_season(id="quick-grant", prepare_weeks=1, seen=[_seen()]))
    slow = seasons.clean_season(_season(id="slow-grant", prepare_weeks=20, seen=[_seen()]))
    assert seasons.when(quick, date(2026, 10, 15))["notice"] == seasons.LEAST_NOTICE
    assert seasons.when(slow, date(2026, 10, 15))["notice"] == 140


def test_it_says_prepare_now_only_inside_the_preparing_window():
    s = seasons.clean_season(_season(prepare_weeks=10, seen=[_seen()]))       # opens about 22 April
    assert not seasons.prepare_now(s, date(2026, 11, 1)), "six months out is not yet"
    assert seasons.prepare_now(s, date(2027, 3, 1)), "ten weeks out, it is time"
    assert not seasons.prepare_now(s, date(2027, 4, 30)), "it is open: applying, not preparing"


# --------------------------------------------------------------------------- who it is for
def test_a_season_for_one_country_is_not_shown_to_everybody():
    """It matters more here than anywhere: a postdoc in Lyon is open to all, MEXT-through-Cairo is not."""
    egypt_only = seasons.clean_season(_season(**{"for": ["Egypt"]}))
    assert seasons.fits(egypt_only, "Egypt")
    assert seasons.fits(egypt_only, "egypt"), "case does not matter"
    assert not seasons.fits(egypt_only, "Tunisia")


def test_a_season_naming_no_country_is_for_anyone():
    anyone = seasons.clean_season(_season(**{"for": []}))
    assert seasons.fits(anyone, "Tunisia") and seasons.fits(anyone, "")


def test_someone_who_has_not_said_where_they_are_from_is_shown_everything():
    """myGeeKy does not demand a nationality before it will show anything."""
    assert seasons.fits(seasons.clean_season(_season(**{"for": ["Egypt"]})), "")


# --------------------------------------------------------------------------- the order they come in
def test_open_first_then_what_to_prepare_for_then_the_rest():
    now = date(2026, 10, 15)
    open_now = seasons.clean_season(_season(id="open-now", title="Open now",
                                            seen=[_seen(opens="2026-10-01", closes="2026-11-15")]))
    soon = seasons.clean_season(_season(id="soon-one", title="Soon", prepare_weeks=8,
                                        opens_about="11-20", closes_about="12-20", seen=[]))
    later = seasons.clean_season(_season(id="later-one", title="Later", prepare_weeks=4,
                                         opens_about="08-01", closes_about="09-01", seen=[]))
    out = seasons.ranked([later, soon, open_now], now)
    assert [s["id"] for s in out] == ["open-now", "soon-one", "later-one"]
    assert [s["when"]["state"] for s in out] == ["open", "soon", "later"]


def test_the_list_can_be_narrowed_by_nationality_and_by_level():
    now = date(2026, 10, 15)
    egypt = seasons.clean_season(_season(id="egypt-only", **{"for": ["Egypt"]}))
    phd = seasons.clean_season(_season(id="phd-only", levels=["phd"], **{"for": []}))
    assert [s["id"] for s in seasons.ranked([egypt, phd], now, nationality="Tunisia")] == ["phd-only"]
    assert [s["id"] for s in seasons.ranked([egypt, phd], now, levels=["master"])] == ["egypt-only"]


# --------------------------------------------------------------------------- it reaches the lists
def test_seasons_survive_the_lists_being_cleaned():
    out = curated.clean({"version": "x", "seasons": [_season(seen=[_seen()])]})
    assert len(out["seasons"]) == 1 and out["seasons"][0]["id"] == "mext-research-egypt"


def test_two_seasons_with_the_same_id_become_one():
    out = curated.clean({"version": "x", "seasons": [_season(seen=[_seen()]), _season(title="Again")]})
    assert len(out["seasons"]) == 1


def test_the_seasons_that_ship_with_myGeeKy_are_all_usable():
    """Whatever is in the shipped lists must survive its own cleaning, or people would see nothing."""
    shipped = curated.load().get("seasons") or []
    assert shipped, "myGeeKy ships with some seasons"
    for s in shipped:
        assert seasons.clean_season(s) is not None, s.get("id")
        assert seasons.when(s, date(2026, 10, 15))["state"] != "unknown", s.get("id")


# --------------------------------------------------------------------------- what DeepSeek is allowed to do
PAGE = {"url": "https://www.turkiyeburslari.gov.tr/announcements/x",
        "text": "Türkiye Scholarships 2026 applications will be received between 10 January - "
                "20 February 2026. Applications are open to those wishing to pursue a master's degree."}
TURKIYE = {"id": "turkiye-burslari", "title": "Türkiye Bursları",
           "url": "https://www.turkiyeburslari.gov.tr/", "closes_about": "02-20"}


def _answer(**more):
    return {"found": True, "recurring": True, "opens": "2026-01-10", "closes": "2026-02-20", "cycle": "2026",
            "quote": "applications will be received between 10 January - 20 February 2026", **more}


def test_a_sentence_that_is_really_on_the_page_becomes_evidence():
    out = scout.check_season(TURKIYE, _answer(), PAGE)
    assert out["ok"] and out["seen"]["checked"] is True
    assert out["seen"]["opens"] == "2026-01-10" and out["seen"]["closes"] == "2026-02-20"


def test_a_sentence_that_is_not_on_the_page_is_refused():
    """The same rule as a listing's deadline: an invented quote fails, however plausible it reads."""
    out = scout.check_season(TURKIYE, _answer(quote="Applications close on 20 February 2026"), PAGE)
    assert not out["ok"] and out["why"] == "the sentence it quoted is not on the page"
    assert out["seen"] is None


def test_a_page_with_no_closing_date_gives_nothing():
    assert scout.check_season(TURKIYE, _answer(closes=""), PAGE)["why"] == "no closing date on the page"


def test_a_page_that_is_not_about_this_programme_gives_nothing():
    assert not scout.check_season(TURKIYE, _answer(found=False), PAGE)["ok"]


def test_a_quote_that_does_not_hold_the_date_it_claims_is_marked_wrong():
    """The sentence is on the page, but the date claimed is not in it -- the same check a listing gets."""
    out = scout.check_season(TURKIYE, _answer(closes="2026-03-31"), PAGE)
    assert dict((text, ok) for ok, text in out["checks"])["that sentence holds the closing date"] is False


def test_evidence_from_a_different_site_is_kept_but_is_marked_as_such():
    """A national contact point's announcement is still a page; the maker should see that it is not the
    programme's own site, rather than have it quietly pass or quietly fail."""
    out = scout.check_season(TURKIYE, _answer(), dict(PAGE, url="https://www.nks-msc.de/en/x"))
    assert out["ok"], "a real sentence on a real page is still evidence"
    assert dict((text, ok) for ok, text in out["checks"])["on the programme's own site"] is False


def test_the_page_wins_when_it_disagrees_with_what_was_written_down():
    """The maker's guess at a date is not evidence; the sentence on the page is. So the page overwrites."""
    claimed = seasons.clean_season({**TURKIYE, "seen": [{"cycle": 2026, "opens": "2026-01-01",
                                                         "closes": "2026-02-28", "checked": False,
                                                         "url": PAGE["url"], "quote": "a guess"}]})
    out = scout.check_season(claimed, _answer(), PAGE)
    assert out["seen"]["closes"] == "2026-02-20", "the date from the page, not the one written down"


@pytest.mark.parametrize("field", ["opens", "closes"])
def test_a_date_that_is_not_a_date_is_refused(field):
    out = scout.check_season(TURKIYE, _answer(**{field: "sometime in spring"}), PAGE)
    assert out["seen"] is None or not out["seen"][field]
