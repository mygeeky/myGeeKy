"""The 💡 opens the same GitHub issue -- or, with no GitHub account, the same ready-made email -- on both apps.

mobile/src/lib/ideas.ts is a port of ideas.py; this runs the phone's real TypeScript in Node on the same inputs.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from mygeeky import ideas

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
WORK = MOBILE / ".crosscheck"
CASES = [
    ["idea", "Seasons from Greece", "CIHEAM Chania has MSc scholarships (it's in Crete!)"],
    ["problem", "  Seasons   empty on Linux ", ""],
    ["question", "", "Why does it need ~ 60 requests/hour * 2?"],
    ["keyword", "Keyword: phylogenetics", "árbol, 系统发育, ok"],
    ["idea", "A long one", "word " * 900],
]
SCRIPT = """
import { emailUrl, issueUrl } from './ideas.ts';
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map(([k, t, d]) => [issueUrl(k, t, d, null), emailUrl(k, t, d, null)])));
"""


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


def test_the_email_carries_what_was_typed_to_support():
    url = ideas.email_url("problem", "Seasons empty", "It showed nothing.", include_version=True)
    parts = urlsplit(url)
    assert parts.scheme == "mailto" and parts.path == ideas.SUPPORT_EMAIL
    q = parse_qs(parts.query)
    assert q["subject"] == ["🐞 Seasons empty"]
    assert q["body"][0].startswith("It showed nothing.\n\n---\nSent from the 💡 in myGeeKy · myGeeKy ")
    assert "+" not in url and "%20" in url                      # spaces as %20: a mail app shows a + literally
    assert "<sub>" not in unquote(url)                          # plain text, no GitHub markup


def test_a_long_email_is_trimmed_but_keeps_its_title():
    url = ideas.email_url("idea", "Long", "word " * 2000, include_version=False)
    assert len(url) <= ideas.MAX_MAILTO and "subject=%F0%9F%92%A1%20Long" in url
    assert "trimmed" in unquote(url)


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_opens_the_same_issue_and_the_same_email():
    WORK.mkdir(exist_ok=True)
    shutil.copy(MOBILE / "src" / "lib" / "ideas.ts", WORK / "ideas.ts")
    (WORK / "ideas-side.ts").write_text(SCRIPT, encoding="utf-8")
    out = subprocess.run(["node", "--experimental-strip-types", str(WORK / "ideas-side.ts"), json.dumps(CASES)],
                         capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert out.returncode == 0, out.stderr
    phone = json.loads(out.stdout)
    for (kind, title, details), (issue, email) in zip(CASES, phone):
        desktop = ideas.issue_url(kind, title, details, include_version=False)
        # the issue link: URLSearchParams and urlencode escape ~ and * differently; GitHub receives the same
        assert urlsplit(issue)[:3] == urlsplit(desktop)[:3], kind
        assert parse_qs(urlsplit(issue).query) == parse_qs(urlsplit(desktop).query), kind
        assert email == ideas.email_url(kind, title, details, include_version=False), kind   # the email: exactly


def test_the_desktop_idea_window_offers_the_email(monkeypatch):
    pytest.importorskip("PySide6")
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication.instance() or QApplication([])
    from mygeeky.gui import qt_panel
    from mygeeky.gui.app import THEMES
    opened = []
    monkeypatch.setattr(qt_panel.QDesktopServices, "openUrl", lambda u: opened.append(u.toString()))
    host = QWidget()
    dlg = qt_panel.IdeaDialog(host, THEMES["midnight"])
    dlg.send_email.click()
    assert not opened and "title" in dlg.status.text()        # no title yet: asks for one, opens nothing
    dlg.title_edit.setText("Seasons from Greece")
    dlg.details.setPlainText("CIHEAM Chania")
    dlg.send_email.click()
    assert opened and opened[0].startswith("mailto:support@mygeeky.org?subject=")
    assert "Send" in dlg.status.text()
    dlg.close()
    host.deleteLater()
    app.processEvents()
