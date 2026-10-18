"""myGeeKy without a GitHub account: the setup skips the GitHub pages, and the parts that genuinely
read your account say what adding GitHub would unlock -- while the parts that only need a FIELD draw
normally. Repos and Market search public repos against your own keywords and never look your account up,
so an "Add GitHub" card there would be asking for something they do not use."""
import pytest

pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")

from test_window_place import _close, _panel, no_save, qapp  # noqa: F401


def test_the_github_parts_show_an_add_github_card(qapp, monkeypatch, no_save):
    from PySide6.QtWidgets import QPushButton

    def cards(area):                                             # cleared ones are hidden until Qt deletes them
        return [b for b in area.parentWidget().findChildren(QPushButton)
                if b.text() == "Add GitHub…" and not b.parentWidget().isHidden()]
    panel = _panel(monkeypatch, orcid_id="0000-0002-1825-0097")
    opened = []
    monkeypatch.setattr(panel, "_open_setup_window", lambda: opened.append(1))
    try:
        panel._render_suggestions({"followback": [], "domain_highlights": []})
        panel._render_contributions([])
        panel._on_activity_ready({"events": []})
        for area in (panel.followback_area, panel.activity_area):    # these are scored against YOUR account
            buttons = cards(area)
            assert len(buttons) == 1
        # Repos is picked by searching your field: an ORCID is a field, so it draws rather than asking.
        assert not cards(panel.repos_area)
        buttons[0].click()
        assert opened                                                # opens setup, to sign in with GitHub
        panel._load_status()
        assert "without GitHub" in panel.status_label.text() and "0000-0002-1825-0097" in panel.status_label.text()
        panel.cfg.github_username = "me"                             # with GitHub: the usual empty note
        panel._render_contributions([])
        assert not cards(panel.repos_area)
    finally:
        _close(panel)


def test_setup_without_github_skips_the_github_pages(qapp, monkeypatch):
    from mygeeky.gui import setup_wizard as sw
    w = sw.SetupWizard()
    profile, token = w.page(w.pageIds()[2]), w.page(w.pageIds()[3])
    w.state = {"github_username": "", "orcid_signin": True, "token_source": "none"}
    profile.initializePage()
    assert not profile.orcid_btn.isHidden() and not profile.isComplete()      # first choose a way in
    profile.guest_btn.click()                                                 # no account at all
    assert profile.isComplete() and profile.nextId() == w.finish_id          # straight to Finish
    assert "Give a few keywords" in profile.job()(None)["error"]              # a guest needs their field
    profile.topics.setText("gwas, single cell")
    monkeypatch.setattr(sw, "api", lambda python, action, payload=None, timeout=600: {"ok": True, "got": payload})
    assert profile.job()(None)["got"]["topics"] == "gwas, single cell"
    profile.github_btn.click()                                                # GitHub: its sign-in page next
    assert profile.nextId() == token.nextId() or profile.nextId() == w.pageIds()[3]
    token.initializePage()
    assert token.job() is None and "skip" in token.status.text()
    assert token.nextId() == w.finish_id                                      # past Sync and Signals
    w.state = {"github_username": "me", "orcid_signin": False, "token_source": "none"}
    profile.initializePage()
    assert profile.orcid_btn.isHidden()                                       # no ORCID client id in this build
    assert token.nextId() == w.pageIds()[4]
    monkeypatch.setattr(sw, "api", lambda python, action, payload=None, timeout=600:
                        {"ok": True, "orcid": "0000-0002-1825-0097", "name": "Josiah Carberry"})
    profile._orcid_done(sw.api(None, "orcid_login"))
    assert profile.orcid.text() == "0000-0002-1825-0097" and "Josiah Carberry" in profile.orcid_note.text()
    assert profile.mode == "orcid" and profile.nextId() == w.finish_id      # ORCID: field, then Finish


def test_the_field_half_of_people_draws_without_an_account(qapp, monkeypatch, no_save):
    """The domain-fit list is people found by searching your field. It used to vanish along with the
    follow-back list, hiding people from exactly the users who have no GitHub to find them any other way."""
    panel = _panel(monkeypatch, orcid_id="0000-0002-1825-0097")
    try:
        found = [{"username": "ada", "profile_url": "https://github.com/ada", "avatar_url": "",
                  "domain_fit": 0.8, "score": 0.1, "followers": 40, "following": 20, "public_repos": 9,
                  "bio": "metagenomics", "sources": ["domain_repo_owner:lab/tool"], "n_sources": 1}]
        panel._render_suggestions({"followback": [], "domain_highlights": found})
        said = _text_of(panel.domain_area)
        assert "ada" in said, "the field half of People was hidden with the follow-back half"
    finally:
        _close(panel)


def _text_of(area) -> str:
    from PySide6.QtWidgets import QLabel
    parent = area.parentWidget()
    return " ".join(lbl.text() for lbl in parent.findChildren(QLabel)
                    if not lbl.parentWidget().isHidden())
