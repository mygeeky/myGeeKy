"""Theme audit: is every text on the panel readable in every theme?

Opens the panel (offscreen, on throwaway data), visits every page and part of the side rail's tree, and checks each
visible label, button and check box: its text colour (what Qt will paint, stylesheet included) against the colour
behind it (its own background if it has one, else the nearest ancestor's, else the theme's). Text under a contrast
of MIN_CONTRAST is reported with where it lives, so a hard-coded white, or a page that kept the old theme's colours
after you switched, shows up by name.

    python tools/theme_audit.py                 # every theme, started in it and switched to from Midnight
    python tools/theme_audit.py frosted         # one theme
    python tools/theme_audit.py --json          # machine-readable (tests/test_theme_audit.py)
"""

from __future__ import annotations

import json
import os
import re
import sys

os.environ.setdefault("MYGEEKY_NO_TOUR", "1")      # GeeKOc's tour would sit over every page it reads
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_CONTRAST = 2.6          # WCAG asks 4.5 for body text; this catches only what is close to invisible


def _lum(c) -> float:
    def ch(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _behind(img, rect, fg=None):
    """The colour behind a text: the commonest colour in its box on the rendered page, leaving out the letters' own
    colour (on a gradient no colour is common, and the letters would win)."""
    from collections import Counter
    from PySide6.QtGui import QColor
    counts: Counter = Counter()
    dpr = img.devicePixelRatio()                          # a Retina grab has 2 pixels per point
    x0, y0 = max(round(rect.left() * dpr), 0), max(round(rect.top() * dpr), 0)
    x1, y1 = min(round(rect.right() * dpr), img.width() - 1), min(round(rect.bottom() * dpr), img.height() - 1)
    step = max(1, min(x1 - x0, y1 - y0) // 12)
    for y in range(y0, y1 + 1, step):
        for x in range(x0, x1 + 1, step):
            c = img.pixelColor(x, y)
            if fg is not None and abs(c.red() - fg.red()) + abs(c.green() - fg.green()) + abs(c.blue() - fg.blue()) < 48:
                continue
            counts[(c.red() // 8, c.green() // 8, c.blue() // 8)] += 1
    if not counts:
        return None
    r, g, b = counts.most_common(1)[0][0]
    return QColor(r * 8 + 4, g * 8 + 4, b * 8 + 4)


def scan(panel, theme_name: str) -> list[dict]:
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QAbstractButton, QCheckBox, QLabel, QWidget
    img = panel.grab().toImage()
    out = []
    for w in panel.findChildren(QWidget):
        if not isinstance(w, (QLabel, QAbstractButton)) or not w.isVisible() or w.width() < 4 or w.height() < 4:
            continue
        text = w.text() if hasattr(w, "text") else ""
        if not text or not re.search(r"[A-Za-z0-9]", text) or (isinstance(w, QLabel) and w.pixmap() is not None and not w.pixmap().isNull()):
            continue
        if isinstance(w, QLabel) and w.textFormat() != 0 and "<" in text:      # rich text sets its own colours
            continue
        seen = w.visibleRegion().boundingRect()           # what isn't scrolled out of view
        if seen.width() * seen.height() < 0.5 * w.width() * w.height():
            continue
        if isinstance(w, QAbstractButton) and w.isChecked():
            continue                                       # a :checked colour isn't in the palette Qt reports
        w.ensurePolished()
        fg = w.palette().color(w.foregroundRole())
        if isinstance(w, (QAbstractButton,)) and not isinstance(w, QCheckBox):
            fg = w.palette().color(w.palette().ColorRole.ButtonText) if fg.alpha() == 0 else fg
        bg = _behind(img, QRect(w.mapTo(panel, seen.topLeft()), seen.size()), fg)
        if bg is None:
            continue
        ratio = contrast(fg, bg)
        if fg.alpha() < 60 or ratio < MIN_CONTRAST:
            page = w
            while page.parentWidget() is not None and page.parentWidget() is not panel.content_stack:
                page = page.parentWidget()
            out.append({"theme": theme_name, "text": " ".join(text.split())[:60], "fg": fg.name(), "bg": bg.name(),
                        "contrast": round(ratio, 2), "widget": type(w).__name__, "name": w.objectName(),
                        "page": page.objectName() or type(page).__name__, "tab": panel.active_tab})
    return out


def run(theme_name: str, switched: bool) -> list[dict]:
    import importlib.util
    spec = importlib.util.spec_from_file_location("ra", ROOT / "tools" / "resource_audit.py")
    ra = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ra)
    from PySide6.QtWidgets import QApplication
    from mygeeky import navtree
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui import app as logic
    from mygeeky.gui.qt_panel import MyGeekyPanel
    logic.save_config = lambda cfg: None                  # switching theme here must not write settings
    app = QApplication.instance() or QApplication(sys.argv[:1])
    cfg = MyGeekyConfig(github_username="audit", keywords=["gwas", "genomics", "machine learning", "snakemake"],
                        topics=["bioinformatics"], gui_theme="midnight" if switched else theme_name)
    panel = MyGeekyPanel(cfg)
    panel.show()
    try:
        panel.resize(460, 900)
        ra._spin(app, 1)
        if switched:                                       # the way ⚙'s theme swatches switch it
            panel._on_theme_clicked(theme_name)
            ra._spin(app, 0.3)
        found: dict[tuple, dict] = {}
        for nd in navtree.walk(panel.nav_tree)[1:]:
            if not nd.get("tab") or nd["children"] and nd["part"] == "":
                continue
            try:
                panel._nav_open(nd)
            except Exception:
                continue
            ra._spin(app, 0.15)
            for f in scan(panel, theme_name):
                found.setdefault((f["text"], f["fg"], f["bg"], f["tab"]), f)
        if hasattr(panel, "_toggle_settings"):
            try:
                panel._toggle_settings()
                ra._spin(app, 0.6)
                bar = panel.settings_scroll.verticalScrollBar()
                for y in range(0, bar.maximum() + bar.pageStep(), max(1, bar.pageStep() // 2)):
                    bar.setValue(y)                       # ⚙ scrolls: every part of it comes into view
                    ra._spin(app, 0.1)
                    for f in scan(panel, theme_name):
                        found.setdefault((f["text"], f["fg"], f["bg"], "settings"), dict(f, tab="settings"))
            except Exception:
                pass
        return list(found.values())
    finally:
        panel.close()


def main(argv: list[str]) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("ra", ROOT / "tools" / "resource_audit.py")
    ra = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ra)
    ra._isolate()
    from mygeeky.gui.app import THEMES
    names = [a for a in argv[1:] if a in THEMES] or [n for n in THEMES]
    report = []
    for name in names:
        for switched in ((False, True) if name != "midnight" else (False,)):
            for f in run(name, switched):
                report.append(dict(f, how="switched to" if switched else "started in"))
    if "--json" in argv:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for f in sorted(report, key=lambda f: (f["theme"], f["how"], f["tab"], f["contrast"])):
            print(f"{f['theme']:8s} {f['how']:11s} {f['tab']:12s} {f['contrast']:5.2f}  {f['fg']} on {f['bg']}  "
                  f"{f['widget']}#{f['name']}  “{f['text']}”")
        print(f"\n{len(report)} hard-to-read texts")
    return 1 if report and "--strict" in argv else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
