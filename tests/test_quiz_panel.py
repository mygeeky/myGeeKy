"""Taking a quiz in the panel: the card, answering, the result, the flag, and the sharing choice."""

import pytest

pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")

from mygeeky import protocols, quiz
from mygeeky.config import MyGeekyConfig


def _q(qid, protocol, stage="basics", level="easy", answer=0, **kw):
    row = {"id": qid, "protocol": protocol, "stage": stage, "level": level, "kind": "choice",
           "q": "In tidy data, what does one row hold?",
           "options": ["One observation", "One variable", "One treatment group", "One whole table"],
           "answer": answer, "why": "Rows are observations: one measured thing per row.",
           "source": {"title": "R for Data Science", "url": "https://r4ds.hadley.nz/data-tidy", "kind": "book",
                      "quote": "Each observation is a row; each row is an observation."}}
    row.update(kw)
    return row


@pytest.fixture
def started(monkeypatch):
    """One protocol of mine, with four questions in the bank for it."""
    cfg = MyGeekyConfig(github_username="me")
    proto = protocols.fill(protocols.template("R", "data analysis"), [], {"resources": []})
    pid = protocols.start(cfg, proto)
    bank = quiz.clean_bank({"version": "2026-10-14T00:00:00Z",
                            "questions": [_q(f"{pid}.basics.{i:02d}", pid) for i in range(4)]})
    monkeypatch.setattr(quiz, "_bank", bank)
    return cfg, pid


def test_a_question_card_shows_the_level_the_step_and_four_answers(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel

    from mygeeky.gui.growth_ui import AnswerRow, QuestionCard
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    drawn = quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=1)
    q = drawn.questions[0]
    card = QuestionCard(q, THEMES["midnight"], lambda i: None, lambda url: True)
    texts = " ".join(lbl.text() for lbl in card.findChildren(QLabel))
    assert "BASICS" in texts.upper() and "1 of 1" in texts
    assert len(card.answers) == 4 and all(isinstance(a, AnswerRow) for a in card.answers)
    assert {"A", "B", "C", "D"} <= {lbl.text() for a in card.answers for lbl in a.findChildren(QLabel)}
    assert "why" not in texts.lower()                      # the reason only shows after you answer


def test_an_answer_can_be_as_narrow_as_the_panel(qapp_offscreen, started):
    """A QPushButton is never narrower than its own text: four long answers would force the whole panel
    wider and squeeze everything in it. Wrapping rows can be narrow and simply grow taller."""
    from mygeeky.gui.growth_ui import QuestionCard
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    for q in quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=4).questions:
        card = QuestionCard(q, THEMES["midnight"], lambda i: None, lambda url: True)
        assert card.minimumSizeHint().width() <= 320, q.id


def test_once_answered_the_card_shows_why_and_the_source(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel

    from mygeeky.gui.growth_ui import QuestionCard, ResourceCard
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    q = quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=1).questions[0]
    q.picked = q.answer
    card = QuestionCard(q, THEMES["midnight"], lambda i: None, lambda url: True)
    texts = " ".join(lbl.text() for lbl in card.findChildren(QLabel))
    assert "✓ Right" in texts
    assert "one measured thing per row" in texts
    assert "each row is an observation" in texts.lower()    # the sentence quoted from the source
    assert card.findChildren(ResourceCard), "the source is shown as a card you can open"


def test_a_wrong_answer_is_marked_and_the_right_one_is_still_shown(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel

    from mygeeky.gui.growth_ui import QuestionCard
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    q = quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=1).questions[0]
    q.picked = (q.answer + 1) % 4
    card = QuestionCard(q, THEMES["midnight"], lambda i: None, lambda url: True)
    texts = " ".join(lbl.text() for lbl in card.findChildren(QLabel))
    assert "Not this one" in texts
    # the right answer is still marked, and the one you picked is marked as wrong
    assert "✓" in " ".join(lbl.text() for lbl in card.answers[q.answer].findChildren(QLabel))
    assert "✗" in " ".join(lbl.text() for lbl in card.answers[q.picked].findChildren(QLabel))


def test_the_result_shows_the_score_the_best_and_where_you_went_wrong(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel

    from mygeeky.gui.growth_ui import ResultView, ScoreRing
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    drawn = quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=4)
    answers = [x.answer for x in drawn.questions]
    answers[0] = (answers[0] + 1) % 4
    attempt = quiz.mark(drawn, answers)
    view = ResultView(attempt, THEMES["midnight"], best_before=0.5)
    texts = " ".join(lbl.text() for lbl in view.findChildren(QLabel))
    assert "3 of 4 right" in texts and "Your best" in texts
    assert view.findChildren(ScoreRing)


def test_a_perfect_score_says_so(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel

    from mygeeky.gui.growth_ui import ResultView
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    drawn = quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=4)
    attempt = quiz.mark(drawn, [x.answer for x in drawn.questions])
    view = ResultView(attempt, THEMES["midnight"])      # kept alive while its labels are read
    texts = " ".join(lbl.text() for lbl in view.findChildren(QLabel))
    assert "100%" in texts and "clean sweep" in texts


def test_the_protocol_card_offers_the_quiz_and_then_your_best_score(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel, QPushButton

    from mygeeky.gui.growth_ui import ProtocolCard
    from mygeeky.gui.qt_panel import THEMES
    from mygeeky.gui import app as logic
    cfg, pid = started
    view = protocols.view(cfg, protocols.mine(cfg)[pid])
    noop = lambda *a, **k: None  # noqa: E731

    def card():
        return ProtocolCard(view, THEMES["midnight"], False, act=noop, on_check=noop, on_open=noop, on_edit=noop,
                            on_publish=noop, on_add_link=noop, on_rename=noop, on_add_stage=noop,
                            vote_item=lambda it: (lambda up: 0), vote_of=lambda it: 0,
                            quiz=logic.quiz_state(cfg, pid), on_quiz=noop, on_share=noop)

    texts = " ".join(lbl.text() for lbl in card().findChildren(QLabel))
    buttons = " ".join(b.text() for b in card().findChildren(QPushButton))
    assert "4 questions" in texts and "Take the quiz" in buttons
    assert "Show my result" not in buttons                 # nothing to share before you've scored

    drawn = quiz.Quiz.draw(view, n=4)
    quiz.record(quiz.mark(drawn, [x.answer for x in drawn.questions]))
    texts = " ".join(lbl.text() for lbl in card().findChildren(QLabel))
    buttons = " ".join(b.text() for b in card().findChildren(QPushButton))
    assert "Your best" in texts and "100%" in texts
    assert "Show my result" in buttons
    assert "today" in texts                                 # and not a second go today


def test_flagging_a_question_leaves_it_out_of_the_next_attempt(qapp_offscreen, started):
    cfg, pid = started
    from mygeeky.gui import app as logic
    first = quiz.Quiz.draw(protocols.mine(cfg)[pid]["protocol"], n=4)
    bad = first.questions[0].id
    assert logic.quiz_flag(bad) is True
    again = logic.quiz_draw(cfg, pid)
    assert bad not in {x.id for x in again.questions}
    assert logic.quiz_report(first.questions[0]).startswith("https://github.com/mygeeky/myGeeKy-ideas/")


def test_the_level_check_of_a_step_uses_the_bank_when_there_is_one(qapp_offscreen, started):
    cfg, pid = started
    from mygeeky.gui import app as logic
    drawn = logic.quiz_draw(cfg, pid, "basics")
    assert drawn is not None and {x.stage for x in drawn.questions} == {"basics"}
    assert logic.quiz_draw(cfg, pid, "project") is None      # no questions for that step: the old check is used


# --------------------------------------------------------------------------- the 🏆 Quiz tab
def test_the_quiz_tab_is_one_of_the_grow_tabs():
    from mygeeky.gui.qt_panel import MyGeekyPanel
    modes = dict(MyGeekyPanel.GROW_MODES)
    assert modes["quiz"] == "🏆 Quiz"
    assert list(modes) == ["skills", "paths", "quiz", "learn", "data", "wins", "highlights"]   # right after Protocols


def test_the_overview_lists_yours_first_then_reviewed_ones_you_could_start(qapp_offscreen, started):
    from mygeeky.gui import app as logic
    cfg, pid = started
    over = logic.quiz_overview(cfg)
    assert over["rows"] and over["rows"][0]["mine"] and over["rows"][0]["id"] == pid
    assert over["questions"] == 4 and over["per_attempt"] == 10
    assert over["mix"] == {"easy": 5, "medium": 4, "tricky": 1}
    assert over["taken"] == 0 and over["average"] == 0.0


def test_the_overview_counts_your_best_scores_and_what_is_still_waiting(qapp_offscreen, started):
    from mygeeky import protocols, quiz
    from mygeeky.gui import app as logic
    cfg, pid = started
    protocols.start(cfg, protocols.find_reviewed("GWAS"))          # no questions for it
    drawn = logic.quiz_draw(cfg, pid)
    logic.quiz_mark(cfg, drawn, [q.answer for q in drawn.questions])
    over = logic.quiz_overview(cfg)
    assert over["taken"] == 1 and over["perfect"] == 1 and over["average"] == 1.0
    assert over["rows"][0]["score"] == 1.0 and not over["rows"][0]["can_try"]    # one a day
    assert any("Genome-wide" in t for t in over["waiting"]), over["waiting"]
    _ = quiz


def test_a_quiz_card_shows_the_bank_the_score_and_the_right_button(qapp_offscreen, started):
    from PySide6.QtWidgets import QLabel, QPushButton

    from mygeeky.gui import app as logic
    from mygeeky.gui.growth_ui import QuizCard, ScoreRing
    from mygeeky.gui.qt_panel import THEMES
    cfg, pid = started
    noop = lambda: None  # noqa: E731
    row = logic.quiz_overview(cfg)["rows"][0]
    card = QuizCard({**row, "per_attempt": 10, "pass_mark": 0.75}, THEMES["midnight"], noop, noop, noop)
    texts = " ".join(lbl.text() for lbl in card.findChildren(QLabel))
    assert "4 questions" in texts
    assert "Take the quiz" in " ".join(b.text() for b in card.findChildren(QPushButton))
    assert not card.findChildren(ScoreRing)                      # no ring before you've scored

    drawn = logic.quiz_draw(cfg, pid)
    logic.quiz_mark(cfg, drawn, [q.answer for q in drawn.questions])
    row = logic.quiz_overview(cfg)["rows"][0]
    scored = QuizCard({**row, "per_attempt": 10, "pass_mark": 0.75}, THEMES["midnight"], noop, noop, noop)
    texts = " ".join(lbl.text() for lbl in scored.findChildren(QLabel))
    assert "best 100%" in texts and "🏴" in texts
    assert scored.findChildren(ScoreRing)
    assert "Show my result" in " ".join(b.text() for b in scored.findChildren(QPushButton))


def test_a_reviewed_quiz_you_have_not_started_offers_to_start_it(qapp_offscreen, started):
    from PySide6.QtWidgets import QPushButton

    from mygeeky.gui.growth_ui import QuizCard
    from mygeeky.gui.qt_panel import THEMES
    noop = lambda: None  # noqa: E731
    row = {"id": "excel-to-r", "title": "From Excel to R", "skill": "R", "mine": False,
           "counts": {"easy": 5, "medium": 4, "tricky": 2, "total": 11}, "best": {}, "score": 0.0,
           "can_try": False, "why_not": "", "flagged": 0, "per_attempt": 10, "pass_mark": 0.75}
    card = QuizCard(row, THEMES["midnight"], noop, noop, None)
    assert "🧭 Start this protocol" in " ".join(b.text() for b in card.findChildren(QPushButton))


def test_taking_back_every_flag_lets_those_questions_come_up_again(qapp_offscreen, started):
    from mygeeky.gui import app as logic
    cfg, pid = started
    first = logic.quiz_draw(cfg, pid)
    logic.quiz_flag(first.questions[0].id)
    assert logic.quiz_overview(cfg)["rows"][0]["flagged"] == 1
    assert logic.quiz_unflag_all() == 1
    assert logic.quiz_overview(cfg)["rows"][0]["flagged"] == 0


# --------------------------------------------------------------------------- nothing squeezes the panel
def test_a_long_protocol_title_cannot_make_the_panel_wider_than_it_is(qapp_offscreen, monkeypatch):
    """A button is never narrower than its own text. With 14 reviewed protocols, a row of buttons labelled
    with full titles made the whole Grow page wider than the panel and squeezed everything inside it."""
    import time

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget

    from mygeeky import protocols
    from mygeeky.config import MyGeekyConfig
    from tests.test_freshness import _close, _quiet_panel
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    monkeypatch.setattr("mygeeky.gui.app.save_config", lambda c: None)
    cfg = MyGeekyConfig(github_username="me", keywords=["gwas"])
    protocols.start(cfg, protocols.find_reviewed("R", "your first analysis of your own data"))
    app, panel = _quiet_panel(monkeypatch, cfg)
    panel.setAttribute(Qt.WA_DontShowOnScreen, True)
    panel.show()

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    try:
        pump(1.5)
        panel._switch_tab("grow")
        for w in list(panel._workers):
            w.wait(5000)
        pump(1.5)
        for mode in ("skills", "paths", "quiz", "learn", "wins", "collab"):
            panel._set_grow_mode(mode)
            for w in list(panel._workers):
                w.wait(5000)
            pump(0.8)
            viewport = panel._grow_scroll.viewport().width()
            page = panel._grow_scroll.widget()
            too_wide = [(type(x).__name__, (getattr(x, "text", lambda: "")() or "")[:40])
                        for x in page.findChildren(QWidget)
                        if x.isVisibleTo(page) and x.minimumSizeHint().width() > viewport]   # hidden ones take no room
            assert not too_wide, f"{mode}: these can't fit in {viewport}px: {too_wide[:3]}"
            assert page.width() <= viewport + 2, f"{mode}: the page is {page.width()}px in a {viewport}px panel"
    finally:
        _close(panel)


def test_a_long_label_is_shortened_on_a_word_boundary():
    from mygeeky.gui.qt_panel import _short
    assert _short("Statistics for experiments: which test, and why", 30) == "Statistics for experiments…"
    assert _short("R for data analysis", 30) == "R for data analysis"            # short enough already
    assert _short("", 30) == ""
    assert len(_short("Algorithms and data structures, for interviews and for real work", 30)) <= 31


# --------------------------------------------------------------------------- the quiz lives in the tab
def test_taking_a_quiz_opens_it_in_the_quiz_tab_and_never_a_dialog(qapp_offscreen, monkeypatch):
    """Pressing 🏁 anywhere moves to 🏆 Quiz and draws the attempt there, inside the tab."""
    import time

    from PySide6.QtCore import Qt

    from mygeeky import protocols as P
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui.growth_ui import QuestionDots, QuizRunView
    from tests.test_freshness import _close, _quiet_panel
    monkeypatch.setattr("mygeeky.gui.app.growth_due", lambda cfg: False)
    monkeypatch.setattr("mygeeky.gui.app.save_config", lambda c: None)
    cfg = MyGeekyConfig(github_username="me")
    pid = P.start(cfg, P.find_reviewed("R", "your first analysis of your own data"))
    app, panel = _quiet_panel(monkeypatch, cfg)
    panel.setAttribute(Qt.WA_DontShowOnScreen, True)
    panel.show()

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.02)

    try:
        pump(1.2)
        panel._switch_tab("grow")
        for w in list(panel._workers):
            w.wait(5000)
        panel._set_grow_mode("paths")
        pump(0.8)
        before = {w for w in app.topLevelWidgets() if w.isVisible()}
        panel._on_take_quiz(pid, "From Excel to R, with your own data")
        pump(0.8)
        assert panel._grow_mode == "quiz", "pressing the quiz button should move to the Quiz tab"
        page = panel._grow_scroll.widget()
        assert page.findChildren(QuizRunView), "the quiz should be drawn inside the tab"
        assert page.findChildren(QuestionDots), "a dot per question shows where you are"
        assert {w for w in app.topLevelWidgets() if w.isVisible()} == before, "no window should have opened"

        # answer every question, in the tab
        while not panel._quiz_run["attempt"]:
            run = panel._quiz_run
            panel._quiz_pick(run["quiz"].questions[run["at"]].answer)
            pump(0.15)
            panel._quiz_next()
            pump(0.15)
        assert panel._quiz_run["attempt"].percent == 100
        assert panel._grow_scroll.widget().findChildren(QuizRunView), "the result shows in the tab too"
        panel._quiz_close()
        for w in list(panel._workers):
            w.wait(5000)
        pump(0.8)
        assert panel._quiz_run is None and panel._grow_mode == "quiz"      # back to the list, same tab
    finally:
        _close(panel)
