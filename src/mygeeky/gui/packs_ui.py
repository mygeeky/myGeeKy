"""⚙ Settings → 📦 Packs: make a pack from your setup and show it as one to three QR codes, one at a time ("Code 2 of
3", Back / Next), for a phone to scan (packs.py). This computer has no camera, so packs are received on the phone
(You → Settings → 📦 Packs → Receive a pack); components/pack-settings.tsx is the phone's side.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QWidget)

from .. import packs, pairing
from .. import researchers as rs


class PackCodes(QDialog):
    """The codes, one at a time, with "Code 2 of 3" and Back / Next."""

    def __init__(self, parent: QWidget, codes: list[str], theme: dict[str, Any], qr_widget: Callable[..., QWidget]) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)       # in front of the always-on-top panel
        self.setWindowTitle("📦 Your pack")
        self.codes, self.at = codes, 0
        self.setStyleSheet(f"QDialog {{ background:#17171f; }} QLabel {{ color:{theme['text']}; font-size:11.5px; }}")
        lay = QVBoxLayout(self)
        self.count = QLabel("")
        self.count.setAlignment(Qt.AlignCenter)
        self.count.setStyleSheet("font-size:18px; font-weight:800;")
        self.qr = qr_widget([], 380)
        self.how = QLabel("On the phone: You → Settings → 📦 Packs → Receive a pack."
                          + (" It counts the codes and tells you when to show the next one." if len(codes) > 1 else ""))
        self.how.setWordWrap(True)
        self.how.setTextFormat(Qt.PlainText)
        row = QHBoxLayout()
        self.back = QPushButton("‹ Back")
        self.next = QPushButton("")
        self.back.clicked.connect(lambda: self.go(-1))
        self.next.clicked.connect(lambda: self.go(1) if self.at < len(self.codes) - 1 else self.accept())
        for b in (self.back, self.next):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"QPushButton {{ background:{theme['section_btn']}; color:{theme['text']}; border:none; "
                            "border-radius:8px; padding:6px 14px; font-size:12px; }")
            row.addWidget(b)
        self.back.setVisible(len(codes) > 1)
        lay.addWidget(self.count)
        lay.addWidget(self.qr, 0, Qt.AlignCenter)
        lay.addWidget(self.how)
        lay.addLayout(row)
        self.go(0)

    def go(self, step: int) -> None:
        self.at = max(0, min(len(self.codes) - 1, self.at + step))
        self.count.setText(f"Code {self.at + 1} of {len(self.codes)}" if len(self.codes) > 1 else "Your pack")
        self.qr.set_matrix(pairing.matrix(self.codes[self.at]))
        self.back.setEnabled(self.at > 0)
        self.next.setText("Next code ›" if self.at < len(self.codes) - 1 else "Done")


class PackSection(QWidget):
    def __init__(self, cfg: Any, theme: Callable[[], dict[str, Any]], qr_widget: Callable[..., QWidget]) -> None:
        super().__init__()
        self.cfg, self.theme, self.qr_widget = cfg, theme, qr_widget
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(4)
        self.head = QLabel("📦 PACKS")
        self.about = QLabel("Share your setup like a seed: a lab or a class starts from yours instead of from zero. It "
                            "goes only as QR codes a phone scans, with no internet. Only what you tick goes in; never "
                            "your account, tokens or Model.")
        self.boxes = {k: QCheckBox("") for k in ("words", "field", "people")}
        self.boxes["words"].setChecked(True)
        self.boxes["field"].setChecked(True)
        self.note = QLineEdit()
        self.note.setMaxLength(packs.MAX_NOTE)
        self.note.setPlaceholderText("A note, e.g. Plant genomics lab, 2026")
        self.fits = QLabel("")
        self.show_btn = QPushButton("📦 Show my pack")
        self.show_btn.setCursor(Qt.PointingHandCursor)
        self.show_btn.clicked.connect(self.show_codes)
        for lbl in (self.about, self.fits):
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.PlainText)
        lay.addWidget(self.head)
        lay.addWidget(self.about)
        for b in self.boxes.values():
            b.toggled.connect(self.refresh)
            lay.addWidget(b)
        self.note.textChanged.connect(self.refresh)
        lay.addWidget(self.note)
        lay.addWidget(self.fits)
        lay.addWidget(self.show_btn, 0, Qt.AlignLeft)
        self.refresh()

    def pack(self) -> dict[str, Any]:
        return packs.make(self.cfg, {k for k, b in self.boxes.items() if b.isChecked()}, self.note.text(),
                          rs.load()["following"])

    def refresh(self) -> None:
        following = rs.load()["following"]
        field = packs.make(self.cfg, {"field"})["f"]
        self.boxes["words"].setText(f"Keywords and topics ({len(self.cfg.keywords) + len(self.cfg.topics)})")
        # short, so ⚙ fits beside a pinned menu (a checkbox never wraps): the field's names are in its tooltip
        self.boxes["field"].setText("Research field" + (f" ({len(field)} area{'s' if len(field) != 1 else ''})" if field else " (none yet)"))
        self.boxes["field"].setToolTip(", ".join(field))
        self.boxes["people"].setText(f"Researchers you follow ({len(following)})")
        p = self.pack()
        codes = packs.codes(p)
        empty = packs.describe(p) == "nothing yet"
        self.fits.setText(f"Holds {packs.describe(p)}: {len(codes)} QR code{'s' if len(codes) > 1 else ''}." if codes
                          else "Too much for three QR codes: untick something.")
        self.show_btn.setEnabled(bool(codes) and not empty)
        self.apply_theme()

    def show_codes(self) -> None:
        codes = packs.codes(self.pack())
        if codes:
            PackCodes(self, codes, self.theme(), self.qr_widget).exec()

    def apply_theme(self) -> None:
        t = self.theme()
        self.head.setStyleSheet(f"color:{t['text']}; font-size:10.5px; font-weight:700; letter-spacing:0.5px; "
                                "background:transparent;")
        for lbl in (self.about, self.fits):
            lbl.setStyleSheet(f"color:{t['muted']}; font-size:10.5px; background:transparent;")
        for b in self.boxes.values():
            b.setStyleSheet(f"color:{t['text']}; font-size:11px; background:transparent;")
        self.note.setStyleSheet(f"color:{t['text']}; font-size:11px; padding:3px 6px; border-radius:6px; "
                                f"border:1px solid {t['muted']}; background:transparent;")
        self.show_btn.setStyleSheet(f"QPushButton {{ background:{t['section_btn']}; color:{t['text']}; border:none; "
                                    "border-radius:8px; padding:5px 10px; font-size:11px; }")
