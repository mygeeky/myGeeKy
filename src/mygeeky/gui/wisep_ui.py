"""⚙ Settings → 🧠 How myGeeKy asks the internet: every user's own WISEP, in plain words. What it asked today and what
its cache answered instead, GitHub beside it, the pages it learned you open, how far it is from deciding alone, the
Auto / Always / Never switch, and Forget what it learned. Everything shown is kept on this computer only. The phone has
the same section (components/wisep-settings.tsx).
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import wisep

MODE_WORDS = {"auto": "Auto", "on": "Always", "off": "Never"}


def summary() -> str:
    """WISEP on this computer today, in a few plain sentences."""
    s = wisep.stats()
    parts = [f"{src}: {t['asked']} asked, {t['saved']} from what it kept"
             + (f", {t['topup']} in the evening top-up" if t["topup"] else "") for src, t in sorted(s["today"].items())]
    g, pr = s["github"], s["proven"]
    pages = ", ".join(p["page"] for p in s["pages"][:4])
    alone = ("It decides alone" + (" (you said Always)." if pr["mode"] == "on" else ": it has proven itself.") if pr["alone"]
             else "The old once-a-day timers lead (you said Never)." if pr["mode"] == "off"
             else f"It takes over from the old once-a-day timers once it has proven itself: {pr['days']} of "
                  f"{wisep.PROVEN_DAYS} days, {pr['looks']} of {wisep.PROVEN_LOOKS} answers, "
                  f"{round(100 * pr['saved'])}% from what it kept (it needs {round(100 * wisep.PROVEN_SAVED)}%).")
    tuned = ", ".join(f"{k} about every {v:g} hours" for k, v in sorted(s["priors"].items()))
    oa = s["server"].get("openalex")
    whose = "your own key's" if s["key"] else "the free budget your whole network shares"
    budget = (f" OpenAlex: {oa['remaining']} of {oa['limit']} credits left ({whose}; a text search costs 10, a list 1, one record "
              f"nothing), back in {oa['reset_in'] // 3600} h {oa['reset_in'] % 3600 // 60} min." if oa else
              (" OpenAlex: with your own key." if s["key"] else
               " OpenAlex: no key, so the free budget your whole network shares (1,000 credits a day)."))
    return ("Today: " + ("; ".join(parts) + "." if parts else "nothing asked yet.")
            + f" GitHub (with its own cache): {g['asked']} asked, {g['saved']} free."
            + (f" You open most: {pages}." if pages else "") + f" {alone}"
            + (f" It learned how often answers change here: {tuned}." if tuned else "") + budget)


class WisepSection(QWidget):
    def __init__(self, theme: Callable[[], dict[str, Any]], toast: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self.theme, self.toast = theme, toast
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(4)
        self.head = QLabel("🧠 HOW MYGEEKY ASKS THE INTERNET")
        self.about = QLabel("Papers, citations and datasets come from open databases (OpenAlex, Zenodo, NCBI…). myGeeKy "
                            "keeps their answers and asks again only when a fresh one is worth it: when it has probably "
                            "changed and you're likely to look, within a daily budget, and kindly to the databases. It "
                            "learns which pages you open and when, on this computer only, and spends what's left of the "
                            "day's budget in the evening on what you'll want tomorrow.")
        self.numbers = QLabel("")
        for lbl in (self.about, self.numbers):
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.PlainText)
        lay.addWidget(self.head)
        lay.addWidget(self.about)
        lay.addWidget(self.numbers)
        row = QHBoxLayout()
        self.mode_btn = QPushButton("")
        self.mode_btn.setToolTip("Auto: it decides alone once it has proven itself (14 days, 40% answered from what it "
                                 "kept). Always / Never: your choice. Click to change.")
        self.mode_btn.clicked.connect(self.next_mode)
        self.forget_btn = QPushButton("Forget what it learned")
        self.forget_btn.setToolTip("The pages you open and how often answers change here. What it kept from the "
                                   "databases stays: it's public, and only makes the screen faster.")
        self.forget_btn.clicked.connect(self.forget)
        self.key_btn = QPushButton("")
        self.key_btn.setToolTip("A free OpenAlex key gives you your own daily budget instead of the one everyone on "
                                "your network shares. Kept in this computer's credential store.")
        self.key_btn.clicked.connect(self.key_menu)
        for b in (self.mode_btn, self.key_btn):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.forget_btn.setCursor(Qt.PointingHandCursor)            # on its own line: three fit no panel's width
        lay.addWidget(self.forget_btn, 0, Qt.AlignLeft)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.numbers.setText(summary())
        except Exception:
            self.numbers.setText("")
        self.mode_btn.setText("🧠 Decides alone: " + MODE_WORDS[wisep.mode()])
        self.key_btn.setText("🔑 OpenAlex key ✓" if wisep.get_key() else "🔑 Get a free OpenAlex key")
        self.apply_theme()

    def key_menu(self) -> None:
        from PySide6.QtWidgets import QInputDialog, QMessageBox
        if wisep.get_key():
            if QMessageBox.question(self, "OpenAlex key", "Forget your OpenAlex key? myGeeKy goes back to the free "
                                    "budget your network shares.") == QMessageBox.Yes:
                wisep.forget_key()
                self.refresh()
            return
        choice, ok = QInputDialog.getItem(self, "A free OpenAlex key", "OpenAlex gives everyone a free key with its own "
                                          "daily budget.", ["Send me one by email", "I have one: paste it"], 0, False)
        if not ok:
            return
        if choice.startswith("Send"):
            email, ok = QInputDialog.getText(self, "A free OpenAlex key", "Your email (it goes to OpenAlex only; they "
                                             "email you a link, and the key works once you click it):")
            if ok and email.strip():
                out = wisep.request_key(email)
                QMessageBox.information(self, "OpenAlex key", out["message"])
        else:
            key, ok = QInputDialog.getText(self, "OpenAlex key", "Paste your OpenAlex key:")
            if ok and key.strip() and not wisep.set_key(key):
                QMessageBox.information(self, "OpenAlex key", "That doesn't look like a key.")
        self.refresh()

    def next_mode(self) -> None:
        wisep.set_mode({"auto": "on", "on": "off", "off": "auto"}[wisep.mode()])
        self.refresh()

    def forget(self) -> None:
        wisep.forget_learned()
        self.refresh()
        if self.toast:
            self.toast("Forgotten: it starts learning your day again.")

    def apply_theme(self) -> None:
        t = self.theme()
        self.head.setStyleSheet(f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                                "background:transparent;")
        for lbl in (self.about, self.numbers):
            lbl.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        for b in (self.mode_btn, self.forget_btn, self.key_btn):
            b.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                            "border-radius:8px; padding:5px 10px; font-size:11px; }")
