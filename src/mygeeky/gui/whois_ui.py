"""⚙ → 📄 Your papers: "Is this you?" in the panel (whois.py does the finding). It shows who you are on OpenAlex if
you confirmed it; else the researchers a pending search found, to pick yourself; else a search. A search OpenAlex
was too busy for is tried again by the panel later (MyGeekyPanel._whois_tick), which then asks here.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from . import app as logic


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        elif item.layout():
            _clear(item.layout())


class WhoisSection(QWidget):
    def __init__(self, cfg, theme: Callable[[], dict[str, Any]], run_async: Callable[..., None],
                 toast: Callable[[str], None]) -> None:
        super().__init__()
        self.cfg, self.theme, self.run_async, self.toast = cfg, theme, run_async, toast
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 6, 0, 0)
        self.lay.setSpacing(4)
        self.render()

    def _label(self, text: str, css: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.PlainText)
        lbl.setStyleSheet(css)
        self.lay.addWidget(lbl)
        return lbl

    def _button(self, text: str, fn: Callable[[], Any], layout=None) -> QPushButton:
        t = self.theme()
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(f"QPushButton {{ background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:9px; "
                        f"padding:5px 10px; text-align:left; }} QPushButton:hover {{ background:{t['btn_hover']}; }}")
        b.clicked.connect(fn)
        (layout or self.lay).addWidget(b)
        return b

    def apply_theme(self) -> None:
        """Another theme in ⚙: drawn again in its colours (the panel calls this on every part that has it)."""
        self.render()

    def render(self) -> None:
        _clear(self.lay)
        t = self.theme()
        head = f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; background:transparent;"
        muted = f"color:{t['muted']}; font-size:11px; background:transparent;"
        self._label("📄 YOUR PAPERS (OPENALEX)", head)
        if self.cfg.orcid_id:
            self._label("Found through your ORCID iD.", muted)
            return
        state = logic.whois_state()
        if self.cfg.openalex_id:
            from .. import scholar
            oa = (scholar.load_scholar_profile() or {}).get("openalex") or {}
            who = oa.get("display_name") or self.cfg.openalex_id
            self._label(f"✓ You: {who}" + (f" · {oa.get('works_count')} works" if oa.get("works_count") else ""),
                        f"color:#7fe6c8; font-size:11px; background:transparent;")
            self._button("Not me: forget it", self._forget)
            return
        found = state.get("found")
        if isinstance(found, list) and found:
            self._label("Is this you? Pick yourself:", f"color:{t['text']}; font-size:11px; font-weight:700; "
                                                       "background:transparent;")
            for c in found:
                bits = [c.get("institution") or "", f"{c.get('works', 0)} works"]
                text = f"{c.get('name', '')} · " + " · ".join(b for b in bits if b)
                if c.get("titles"):
                    text += "\n• " + c["titles"][0]
                self._button(text, lambda _=False, c=c: self._confirm(c))
            self._button("None of these", self._reject)
            return
        if isinstance(state.get("pending"), dict):
            self._label(f"Looking for “{state['pending'].get('name', '')}”: OpenAlex was busy, myGeeKy tries again "
                        "by itself and asks here.", muted)
        else:
            self._label("No ORCID? Find your papers by your name and institution.", muted)
        row = QHBoxLayout()
        self.name, self.hint = QLineEdit(), QLineEdit()
        self.name.setPlaceholderText("Your name")
        self.hint.setPlaceholderText("Institution or email")
        for e in (self.name, self.hint):
            e.setStyleSheet(f"background:{t['btn_bg']}; color:{t['text']}; border:none; border-radius:7px; padding:4px 6px;")
            row.addWidget(e, 1)
        self.lay.addLayout(row)
        self.note = self._label("", muted)
        self._button("🔎  Search OpenAlex", self._search)

    def _search(self) -> None:
        name, hint = self.name.text().strip(), self.hint.text().strip()
        if len(name.split()) < 2:
            self.note.setText("Type your first and last name, as on your papers.")
            return
        self.note.setText("Looking on OpenAlex…")
        self.run_async(lambda: logic.whois_search(self.cfg, name, hint), self._searched)

    def _searched(self, out: Any) -> None:
        out = out if isinstance(out, dict) else {}
        if out.get("status") == "none":
            self.render()
            self.note.setText(out.get("why") or "No researcher by that name on OpenAlex. Check the spelling.")
            return
        self.render()

    def _confirm(self, c: dict[str, Any]) -> None:
        self.run_async(lambda: logic.whois_confirm(self.cfg, c.get("id", "")),
                       lambda ok: (self.toast("✓ Your papers will shape your profile.") if ok else None, self.render()))

    def _reject(self) -> None:
        logic.whois_reject()
        self.render()

    def _forget(self) -> None:
        logic.whois_forget(self.cfg)
        self.render()
