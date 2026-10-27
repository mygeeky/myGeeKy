"""The admin console's Support page (support.py): emails to support@mygeeky.org, read-only, with a reply box where
DeepSeek can draft, improve, shorten or warm a reply (from the email with personal details removed), and Send -- as
support@mygeeky.org, after the maker confirms. Plus the support mailbox's settings form for Settings.

Users' words are shown as plain text, never as HTML."""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

from . import app as logic


def _label(text: str, css: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setTextFormat(Qt.PlainText)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(css + " background:transparent;")
    return lbl



def _button(text: str, t: dict[str, Any], primary: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(f"QPushButton {{ background:{t['accent'] if primary else t['section_btn']}; "
                    f"color:{t['on_accent'] if primary else t['text']}; "
                    f"border:none; border-radius:8px; padding:5px 11px; font-size:11.5px; "
                    f"font-weight:{'700' if primary else '500'}; }} QPushButton:disabled {{ color:{t['muted']}; }}")
    return b


class SupportPage(QWidget):
    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None], toast: Callable[[str], None],
                 on_changed: Callable[[], None]) -> None:
        super().__init__()
        self.theme, self.run_async, self.toast, self.on_changed = theme, run_async, toast, on_changed
        self.threads: list[dict[str, Any]] = []
        self.current = ""
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(4)
        left = QWidget()
        left.setLayout(self.list_box)
        left.setMinimumWidth(240)
        left.setMaximumWidth(360)
        outer.addWidget(left, 2)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        self.head = _label("", "")
        self.body = _label("", "")
        self.body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rl.addWidget(self.head)
        rl.addWidget(self.body)
        tools = QHBoxLayout()
        self.ai_btns = {}
        for kind, text in (("draft", "Draft with DeepSeek"), ("improve", "Improve"), ("shorter", "Shorter"), ("warmer", "Warmer")):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False, k=kind: self._ai(k))
            self.ai_btns[kind] = b
            tools.addWidget(b)
        tools.addStretch(1)
        rl.addLayout(tools)
        self.reply = QPlainTextEdit()
        self.reply.setPlaceholderText("Your reply")
        self.reply.setMinimumHeight(160)
        rl.addWidget(self.reply)
        self.note = _label("", "")
        rl.addWidget(self.note)
        acts = QHBoxLayout()
        self.send_btn, self.save_btn, self.done_btn, self.fetch_btn = (QPushButton("Send as support@mygeeky.org"), QPushButton("Save draft"),
                                                                       QPushButton("Mark done, no reply"), QPushButton("Check for new mail"))
        for b, fn in ((self.send_btn, self._send), (self.save_btn, self._save), (self.done_btn, self._done_thread),
                      (self.fetch_btn, self._fetch)):
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(fn)
            acts.addWidget(b)
        acts.addStretch(1)
        rl.addLayout(acts)
        rl.addStretch(1)
        outer.addWidget(right, 3)
        self.setStyleSheet("background:transparent;")

    # ---- drawing
    def set_threads(self, threads: list[dict[str, Any]], note: str = "") -> None:
        self.threads = threads
        if self.current not in {t["id"] for t in threads}:
            self.current = threads[0]["id"] if threads else ""
        self.render(note)

    def render(self, note: str = "") -> None:
        t = self.theme()
        while self.list_box.count():
            w = self.list_box.takeAt(0).widget()
            if w is not None:
                w.hide()                 # out of sight now: deleteLater waits for the event loop
                w.deleteLater()
        if not self.threads:
            self.list_box.addWidget(_label(note or "No support emails yet. Check for new mail, or set up the support "
                                                   "mailbox in Settings.", f"color:{t['muted']}; font-size:10.5px;"))
        for th in self.threads[:60]:
            b = QPushButton(f"{'● ' if th.get('status') == 'new' else ''}{th.get('who', '')} · {th.get('tag', '')}\n"
                            f"{th.get('subject', '')[:60]}")
            b.setCursor(Qt.PointingHandCursor)
            on = th["id"] == self.current
            b.setStyleSheet(f"QPushButton {{ background:{t['section_btn'] if on else t['card_bg']}; color:{t['text']}; border:none; "
                            "border-radius:8px; padding:6px 9px; font-size:11px; text-align:left; }")
            b.clicked.connect(lambda checked=False, i=th["id"]: self._pick(i))
            self.list_box.addWidget(b)
        self.list_box.addStretch(1)
        th = self._thread()
        self.head.setText(f"{th.get('subject', '')}\nFrom {th.get('who', '')} · {th.get('date', '')} · {th.get('tag', '')} · "
                          f"{th.get('status', '')}" if th else "")
        self.head.setStyleSheet(f"color:{t['text']}; font-size:12.5px; font-weight:700; background:transparent;")
        self.body.setText(th.get("body", "")[:6000] if th else "")
        self.body.setStyleSheet(f"color:{t['text']}; font-size:11.5px; background:{t['card_bg']}; border-radius:8px; padding:8px;")
        if th and not self.reply.toPlainText().strip():
            self.reply.setPlainText(th.get("draft", ""))
        self.reply.setStyleSheet(f"QPlainTextEdit {{ background:{t['btn_bg']}; color:{t['text']}; border:none; "
                                 "border-radius:8px; padding:6px; font-size:11.5px; }")
        self.note.setText(self.note.text() or "Before anything goes to DeepSeek, email addresses, phone numbers, file "
                                              "paths and anything like a token are removed, and a crash report is "
                                              "cut off. Nothing is sent until you press Send and confirm.")
        self.note.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        for b in list(self.ai_btns.values()) + [self.save_btn, self.done_btn, self.fetch_btn]:
            b.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                            "border-radius:8px; padding:5px 10px; font-size:11px; }")
            b.setEnabled(bool(th) or b is self.fetch_btn)
        self.send_btn.setStyleSheet(f"QPushButton {{ background:{t['accent']}; color:{t['on_accent']}; border:none; "
                                    "border-radius:8px; padding:5px 12px; font-size:11.5px; font-weight:700; }")
        self.send_btn.setEnabled(bool(th))

    def apply_theme(self) -> None:
        self.render()

    def _thread(self) -> dict[str, Any]:
        return next((th for th in self.threads if th["id"] == self.current), {})

    # ---- actions
    def _pick(self, tid: str) -> None:
        self.current = tid
        self.reply.clear()
        self.note.setText("")
        self.render()

    def _ai(self, kind: str) -> None:
        tid, draft = self.current, self.reply.toPlainText()
        if not tid:
            return
        self.note.setText("Asking DeepSeek…")

        def done(out: Any) -> None:
            out = out if isinstance(out, dict) else {"error": str(out)}
            if out.get("error"):
                self.note.setText(out["error"])
                return
            self.reply.setPlainText(out["reply"])
            self.note.setText({"draft": "Drafted by DeepSeek from the cleaned email. Read it before sending.",
                               "improve": "Improved by DeepSeek: clearer, same meaning.", "shorter": "Made shorter by DeepSeek.",
                               "warmer": "Made warmer by DeepSeek."}[kind])
        self.run_async(lambda: logic.support_ai(tid, kind, draft), done)

    def _send(self) -> None:
        th, body = self._thread(), self.reply.toPlainText().strip()
        if not th or not body:
            self.note.setText("Write the reply first.")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Send this reply?")
        box.setTextFormat(Qt.PlainText)
        box.setText(f"Send this reply to {th.get('who', '')} from support@mygeeky.org? It can't be unsent.")
        yes = box.addButton("Yes, send", QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec()
        if box.clickedButton() is not yes:
            return

        def done(out: Any) -> None:
            out = out if isinstance(out, dict) else {"error": str(out)}
            if out.get("error"):
                self.note.setText(out["error"])
                return
            self.reply.clear()
            self.toast("Sent from support@mygeeky.org.")
            self.on_changed()
        self.run_async(lambda: logic.support_send(th["id"], body), done)

    def _save(self) -> None:
        tid, text = self.current, self.reply.toPlainText()
        self.run_async(lambda: logic.support_save_draft(tid, text), lambda _r: self.toast("Draft saved."))

    def _done_thread(self) -> None:
        tid = self.current
        self.run_async(lambda: logic.support_mark_done(tid), lambda _r: self.on_changed())

    def _fetch(self) -> None:
        self.toast("Checking support@mygeeky.org…")

        def done(out: Any) -> None:
            out = out if isinstance(out, dict) else {"error": str(out)}
            self.toast(out.get("error") or f"{out.get('new', 0)} new support email(s).")
            self.on_changed()
        self.run_async(logic.support_fetch, done)


class SupportMailboxForm(QWidget):
    """Settings → Support mailbox: the Gmail account support@ forwards to, its app password, the send-as address and
    the three switches (read, send, DeepSeek)."""

    def __init__(self, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None], toast: Callable[[str], None]) -> None:
        super().__init__()
        self.theme, self.run_async, self.toast = theme, run_async, toast
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.info = _label("", "")
        lay.addWidget(self.info)
        row = QHBoxLayout()
        self.addr, self.pw, self.send_as = QLineEdit(), QLineEdit(), QLineEdit()
        self.addr.setPlaceholderText("Gmail account, e.g. aalsamman100@gmail.com")
        self.pw.setPlaceholderText("app password (kept in the keyring)")
        self.pw.setEchoMode(QLineEdit.Password)
        self.send_as.setPlaceholderText("send replies as, e.g. support@mygeeky.org")
        for w in (self.addr, self.pw, self.send_as):
            row.addWidget(w, 1)
        lay.addLayout(row)
        row = QHBoxLayout()
        self.read, self.send, self.ai = (QCheckBox("Read (read-only)"), QCheckBox("Send (only when you press Send)"),
                                         QCheckBox("Let DeepSeek draft and improve replies (details removed first)"))
        for w in (self.read, self.send, self.ai):
            row.addWidget(w)
        row.addStretch(1)
        lay.addLayout(row)
        self.save_btn = QPushButton("Save the support mailbox")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self._save)
        lay.addWidget(self.save_btn, 0, Qt.AlignLeft)
        self.setStyleSheet("background:transparent;")
        self.load()

    def load(self) -> None:
        s = logic.support_settings()
        self.addr.setText(s.get("address", ""))
        self.send_as.setText(s.get("send_as", ""))
        for box, key in ((self.read, "read"), (self.send, "send"), (self.ai, "ai")):
            box.setChecked(bool(s.get(key)))
        self.apply_theme(s)

    def apply_theme(self, s: dict[str, Any] | None = None) -> None:
        t = self.theme()
        s = s or logic.support_settings()
        self.info.setText(f"support@mygeeky.org forwards to {s.get('address', '')}; myGeeKy reads only its "
                          f"'{s.get('label', 'support')}' label and sends replies as {s.get('send_as', '')} (Gmail → "
                          f"Settings → Accounts → Send mail as must list it). App password: "
                          + ("saved in the keyring." if s.get("has_password") else "not added yet."))
        self.info.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        for w in (self.addr, self.pw, self.send_as):
            w.setStyleSheet(f"QLineEdit {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:7px; "
                            "padding:5px 8px; font-size:11.5px; }")
        for w in (self.read, self.send, self.ai):
            w.setStyleSheet(f"color:{t['text']}; font-size:11px; background:transparent;")
        self.save_btn.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                                    "border-radius:8px; padding:5px 11px; font-size:11.5px; }")

    def _save(self) -> None:
        addr, pw, send_as = self.addr.text(), self.pw.text(), self.send_as.text()
        flags = {"read": self.read.isChecked(), "send": self.send.isChecked(), "ai": self.ai.isChecked()}
        self.pw.clear()

        def done(out: Any) -> None:
            out = out if isinstance(out, dict) else {"error": str(out)}
            self.toast(out.get("error") or "Support mailbox saved.")
            self.load()
        self.run_async(lambda: logic.support_save_settings(addr, send_as, pw, flags), done)
