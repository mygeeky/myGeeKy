"""Scores on mygeeky.org: nothing without consent, consent only from the person's own account, and withdrawal."""

import json
from datetime import date

import pytest

from mygeeky import leaderboard as lb
from mygeeky import quiz
from mygeeky.config import MyGeekyConfig

TODAY = date(2026, 10, 14)


def _share(login="someresearcher", name=True, scores=True, rows=None):
    return lb.Share(login=login, name="Some Researcher", profile_url=f"https://github.com/{login}",
                    avatar_url=f"https://github.com/{login}.png", share_name=name, share_scores=scores,
                    scores=rows if rows is not None else {"qpcr-ddct": 1.0, "excel-to-r": 0.9},
                    titles={"qpcr-ddct": "qPCR, from the plate to ddCt"})


def _issue(share, login=None, body=None):
    return {"title": "\U0001f3c6 Quiz score: Some Researcher", "body": body if body is not None else lb.accept_body(share),
            "user": {"login": login or share.login}, "created_at": "2026-10-14T10:00:00Z", "number": 7,
            "html_url": "https://github.com/mygeeky/myGeeKy-ideas/issues/7"}


# --------------------------------------------------------------------------- nothing is shared by default
def test_nothing_is_shared_until_both_switches_are_on():
    assert lb.can_share(_share(name=False))[0] is False
    assert "nothing would be shown" in lb.can_share(_share(name=False))[1].lower()
    assert _share(scores=False).shown_scores == {}
    assert lb.can_share(_share(scores=False))[0] is False
    assert lb.can_share(_share())[0] is True


def test_a_low_score_is_never_shown_even_with_consent():
    share = _share(rows={"excel-to-r": 0.6, "qpcr-ddct": 0.85})
    assert share.shown_scores == {"qpcr-ddct": 0.85}
    only_low = _share(rows={"excel-to-r": 0.5})
    assert only_low.shown_scores == {}
    ok, why = lb.can_share(only_low)
    assert not ok and "80%" in why


def test_the_maker_is_left_off_the_board():
    ok, why = lb.can_share(_share(login="alsammanalsamman"))
    assert not ok and "maker" in why


def test_without_a_github_account_there_is_nothing_to_prove_it_with():
    ok, why = lb.can_share(_share(login=""))
    assert not ok and "GitHub" in why


def test_what_would_appear_is_said_in_plain_words_and_nothing_else_travels():
    lines = " ".join(_share().lines())
    assert "Some Researcher" in lines and "github.com/someresearcher" in lines
    assert "never your affiliation" in lines
    payload = _share().payload()
    assert set(payload) == {"login", "name", "profile", "avatar", "share_name", "share_scores", "scores"}
    assert payload["scores"] == {"excel-to-r": 0.9, "qpcr-ddct": 1.0}
    assert "email" not in json.dumps(payload) and "affiliation" not in json.dumps(payload)


def test_turning_the_name_off_empties_the_name_fields():
    payload = _share(name=False).payload()
    assert payload["name"] == "" and payload["profile"] == "" and payload["avatar"] == ""


# --------------------------------------------------------------------------- consent, provably
def test_the_issue_holds_what_would_appear_and_the_word_accept():
    body = lb.accept_body(_share())
    assert "\naccept\n" in body and "withdraw" in body
    assert "Some Researcher" in body and "```json" in body
    url = lb.accept_url(_share())
    assert url.startswith("https://github.com/mygeeky/myGeeKy-ideas/issues/new?")
    assert "leaderboard" in url


def test_consent_counts_only_from_the_account_it_is_about():
    share = _share()
    said = lb.consent(_issue(share))
    assert said["action"] == "accept" and said["login"] == "someresearcher"
    assert said["entry"]["scores"] == {"excel-to-r": 0.9, "qpcr-ddct": 1.0}
    assert lb.consent(_issue(share, login="someoneelse")) is None       # nobody accepts for anyone else
    assert lb.consent(_issue(share, login="alsammanalsamman")) is None  # not the maker either


def test_without_the_word_accept_nothing_counts():
    body = lb.accept_body(_share()).replace("\naccept\n", "\n")
    assert lb.consent(_issue(_share(), body=body)) is None


def test_an_issue_that_is_not_one_of_these_is_ignored():
    share = _share()
    assert lb.consent({**_issue(share), "title": "A protocol for R"}) is None
    assert lb.consent({**_issue(share), "body": "accept"}) is None       # no machine-readable part


def test_a_withdraw_from_the_same_account_wins_and_from_anyone_else_is_ignored():
    share = _share()
    mine = [{"user": {"login": "someresearcher"}, "body": "withdraw", "created_at": "2026-10-15T09:00:00Z"}]
    theirs = [{"user": {"login": "stranger"}, "body": "withdraw", "created_at": "2026-10-20T09:00:00Z"}]
    assert lb.consent(_issue(share), mine)["action"] == "withdraw"
    assert lb.consent(_issue(share), theirs)["action"] == "accept"


def test_the_last_word_from_that_account_is_the_one_that_counts():
    share = _share()
    said = lb.consent(_issue(share), [
        {"user": {"login": "someresearcher"}, "body": "withdraw", "created_at": "2026-10-15T09:00:00Z"},
        {"user": {"login": "someresearcher"}, "body": "accept", "created_at": "2026-10-16T09:00:00Z"}])
    assert said["action"] == "accept" and said["at"].startswith("2026-10-16")


def test_a_score_someone_edited_into_the_issue_is_still_checked():
    """The body is someone's text by the time it arrives: a score above 1, or below the floor, is dropped."""
    body = lb.accept_body(_share()).replace('"qpcr-ddct":1.0', '"qpcr-ddct":4.0').replace('"excel-to-r":0.9',
                                                                                          '"excel-to-r":0.1')
    assert lb.consent(_issue(_share(), body=body)) is None          # nothing left that may be shown


def test_an_entry_about_someone_else_is_refused():
    body = lb.accept_body(_share()).replace('"login":"someresearcher"', '"login":"somebodyelse"')
    assert lb.consent(_issue(_share(), body=body)) is None


# --------------------------------------------------------------------------- the board
def _accepted(login, scores, at, name=None):
    return {"login": login, "action": "accept", "at": at,
            "entry": {"login": login, "name": name or login, "profile": f"https://github.com/{login}",
                      "avatar": f"https://github.com/{login}.png", "scores": scores}}


def test_the_month_board_is_the_top_three_by_weighted_score():
    rows = [_accepted("a", {"qpcr-ddct": 1.0}, "2026-10-02T10:00:00"),
            _accepted("b", {"qpcr-ddct": 0.9}, "2026-10-03T10:00:00"),
            _accepted("c", {"qpcr-ddct": 0.95}, "2026-10-04T10:00:00"),
            _accepted("d", {"qpcr-ddct": 0.85}, "2026-10-05T10:00:00"),
            _accepted("old", {"qpcr-ddct": 1.0}, "2026-09-05T10:00:00")]
    board = lb.board(rows, month="2026-10")
    assert [w["login"] for w in board["top"]] == ["a", "c", "b"]
    assert len(board["top"]) == lb.TOP
    assert "old" in {w["login"] for w in board["hall"]}      # all-time keeps them


def test_the_first_five_to_one_hundred_percent_are_the_protocol_s_people_and_the_first_is_the_pathfinder():
    rows = [_accepted(f"p{i}", {"qpcr-ddct": 1.0}, f"2026-10-0{i}T10:00:00") for i in range(1, 8)]
    board = lb.board(rows, month="2026-10")
    people = board["protocols"]["qpcr-ddct"]
    assert [w["login"] for w in people] == ["p1", "p2", "p3", "p4", "p5"]
    assert people[0]["pathfinder"] and not people[1]["pathfinder"]


def test_only_a_full_score_claims_a_protocol():
    board = lb.board([_accepted("a", {"qpcr-ddct": 0.9}, "2026-10-02T10:00:00")], month="2026-10")
    assert board["protocols"] == {}


def test_a_withdrawal_keeps_them_off_the_board_and_is_listed_for_the_rewrite():
    rows = [_accepted("a", {"qpcr-ddct": 1.0}, "2026-10-02T10:00:00"),
            {"login": "b", "action": "withdraw", "at": "2026-10-03T10:00:00",
             "entry": {"login": "b", "name": "b", "profile": "https://github.com/b",
                       "avatar": "https://github.com/b.png", "scores": {"qpcr-ddct": 1.0}}}]
    board = lb.board(rows, month="2026-10")
    assert [w["login"] for w in board["top"]] == ["a"]
    assert lb.withdraw_names(rows) == ["b"]


def test_the_maker_never_reaches_the_board_even_if_an_entry_says_so():
    board = lb.board([_accepted("alsammanalsamman", {"qpcr-ddct": 1.0}, "2026-10-02T10:00:00")], month="2026-10")
    assert board["top"] == [] and board["hall"] == []


def test_the_board_file_is_checked_before_it_could_be_published():
    good = lb.board([_accepted("a", {"qpcr-ddct": 1.0}, "2026-10-02T10:00:00")], month="2026-10")
    assert lb.problems(good) == []
    bad = json.loads(json.dumps(good))
    bad["top"][0]["scores"]["qpcr-ddct"] = 0.4
    bad["top"][0]["affiliation"] = "Some University"
    found = " ".join(lb.problems(bad))
    assert "80%" in found and "affiliation" in found
    assert lb.problems({"top": [{"login": "not a login!"}]})


def test_how_hard_each_protocol_turned_out_needs_a_few_people():
    rows = [_accepted(f"p{i}", {"qpcr-ddct": 0.9, "excel-to-r": 1.0}, f"2026-10-0{i}T10:00:00") for i in range(1, 5)]
    out = lb.difficulty_of(rows)
    assert out["qpcr-ddct"] == pytest.approx(0.9)
    assert lb.difficulty_of(rows[:2]) == {}            # two people say nothing about difficulty


# --------------------------------------------------------------------------- "is this a real account?"
class _Client:
    def __init__(self, user):
        self.user = user

    def _get(self, path, params=None):
        class Resp:
            status_code = 200

            @staticmethod
            def json():
                return self.user
        return Resp()


def test_a_fresh_empty_account_is_flagged_and_a_working_one_is_not():
    old = _Client({"login": "a", "created_at": "2023-01-01T00:00:00Z", "public_repos": 9, "followers": 3,
                   "bio": "PhD student", "name": "A"})
    new = _Client({"login": "b", "created_at": "2026-10-10T00:00:00Z", "public_repos": 0, "followers": 0})
    assert lb.looks_real(old, "a", today=TODAY)["looks_real"] is True
    assert lb.looks_real(new, "b", today=TODAY)["looks_real"] is False


def test_the_check_only_ever_uses_public_facts_and_never_the_app_s_data():
    client = _Client({"login": "a", "created_at": "2023-01-01T00:00:00Z", "public_repos": 9, "followers": 3,
                      "bio": "PhD student", "name": "A", "email": "someone@example.org"})
    facts = lb.facts_of(client, "a")
    assert "email" not in facts and facts["public_repos"] == 9


def test_few_followers_is_not_held_against_anyone():
    quiet = _Client({"login": "a", "created_at": "2022-01-01T00:00:00Z", "public_repos": 2, "followers": 0})
    assert lb.looks_real(quiet, "a", today=TODAY)["looks_real"] is True
    assert "followers" in lb.PROFILE_SYSTEM            # and DeepSeek is told the same


# --------------------------------------------------------------------------- the panel's own numbers
def test_share_state_reads_your_own_best_scores(monkeypatch):
    from mygeeky.gui import app as logic
    cfg = MyGeekyConfig(github_username="someresearcher")
    quiz._save({"best": {"qpcr-ddct": {"score": 1.0, "at": "2026-10-14", "title": "qPCR", "right": 10,
                                       "questions": 10}}, "attempts": [], "flags": [], "seen": {}})
    st = logic.share_state(cfg, share_name=True, share_scores=True)
    assert st["ok"] and st["scores"] == {"qpcr-ddct": 1.0}
    assert logic.share_url(cfg, True, True).startswith("https://github.com/")
    assert logic.share_url(cfg, False, False) == ""           # nothing agreed: no link at all


def test_withdrawing_points_at_your_own_issues():
    cfg = MyGeekyConfig(github_username="someresearcher")
    from mygeeky.gui import app as logic
    url = logic.withdraw_url(cfg)
    assert "author%3Asomeresearcher" in url and "leaderboard" in url
