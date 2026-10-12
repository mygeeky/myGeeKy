"""myGeeKy without a GitHub account: the setup skips the GitHub pages, and the
GitHub-only parts of the panel say what adding GitHub would unlock."""
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
        for area in (panel.followback_area, panel.repos_area, panel.activity_area):
            buttons = cards(area)
            assert len(buttons) == 1
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
    assert not profile.orcid_btn.isHidden() and profile.isComplete()          # the username isn't required
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
