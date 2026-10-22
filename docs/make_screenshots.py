"""Re-render every screenshot in docs/screenshots from the real panel.

    python docs/make_screenshots.py

Uses your own config and cached data (People, Repos, Market, Research, News,
Activity, Model). Signals uses made-up example people, since it shows other
users. Banners (update, token expiry) are switched off so the shots are clean.
Also writes docs/screenshots/hero.png (three tabs side by side) and
docs/tour.gif (every tab, crossfading) for the README.

    python docs/make_screenshots.py --tall

retakes the tabs as tall as the panel goes, into launch/video/intro/shots/ (git-ignored), for the video
(launch/video/make_falling.py), so each one shows its content, not just the panel's header.
"""

from __future__ import annotations

import dataclasses
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("QT_SCALE_FACTOR", "2")
os.environ.setdefault("MYGEEKY_NO_TOUR", "1")      # GeeKOc's tour stays out of the pictures
ROOT = Path(__file__).resolve().parent.parent
TALL = "--tall" in sys.argv
SHOTS = ROOT / "launch" / "video" / "intro" / "shots" if TALL else ROOT / "docs" / "screenshots"

TABS = [  # (file, tab, market mode)
    ("live", "live", None), ("suggestions", "suggestions", None), ("repos", "repos", None),
    ("market", "market", "repos"), ("research", "market", "research"), ("models", "market", "models"),
    ("news", "news", "headlines"),
    ("activity", "activity", None), ("signals", "signals", None), ("model", "model", "model"),
    ("grow-skills", "grow", "skills"), ("grow-protocols", "grow", "paths"), ("grow-quiz", "grow", "quiz"),
    ("grow-quiz-question", "grow", "quiz-run"),
    ("grow-learn", "grow", "learn"),
    ("chances-seasons", "chances", "seasons"),
    ("chances-jobs", "chances", "jobs"), ("chances-funding", "chances", "funding"),
    ("chances-conferences", "chances", "conferences"),
]


SHOW_EXAMPLES = {"on": False}   # only the Signals tab shows example people, never Live


def example_signals(cfg, force=False):
    if not SHOW_EXAMPLES["on"]:
        return {"enabled": True, "can_send": True, "incoming": [], "people": [], "fetched_at": None, "error": None}
    now = datetime.now(timezone.utc)
    ago = lambda h: (now - timedelta(hours=h)).isoformat()  # noqa: E731
    people = [("ada-genomics", "🔬 deep in analysis", ["gwas", "fine mapping", "python"]),
              ("lin-spatial", "☕ open to chat", ["single cell", "spatial transcriptomics"]),
              ("omar-plants", "🌱 learning", ["plant genomics", "population genetics", "r"])]
    return {
        "enabled": True, "can_send": True, "fetched_at": ago(0.1), "error": None,
        "incoming": [
            {"from": "ada-genomics", "avatar_url": "", "profile_url": "", "type": "thanks", "emoji": "🙏",
             "text": "🙏 thanked you for your work", "repo": "", "at": ago(1), "mutual": False},
            {"from": "lin-spatial", "avatar_url": "", "profile_url": "", "type": "collab", "emoji": "🤝",
             "text": "🤝 you both want to collaborate", "repo": "", "at": ago(5), "mutual": True},
            {"from": "omar-plants", "avatar_url": "", "profile_url": "", "type": "used", "emoji": "⭐",
             "text": "⭐ used your-name/finemap-kit in their work", "repo": "", "at": ago(26), "mutual": False},
        ],
        "people": [{"login": p, "avatar_url": "", "profile_url": "", "status": s, "interests": i, "shared": i[:2],
                    "signalled_you": True, "you_signalled": p == "ada-genomics", "can_receive": True, "fit": f}
                   for (p, s, i), f in zip(people, (0.84, 0.58, 0.41))],
        "calls": [{"id": "a1b2c3d4", "owner": "ada-genomics", "avatar_url": "", "repo": "finemap-lite",
                   "full_name": "ada-genomics/finemap-lite", "repo_url": "https://github.com/ada-genomics/finemap-lite",
                   "note": "Port our SuSiE fine-mapping step to Snakemake so it runs on any cluster.",
                   "skills": ["snakemake", "fine mapping", "python"], "matched": ["snakemake", "python"],
                   "fit": 0.82, "explore": False, "level_label": "experienced", "time_label": "a few weeks",
                   "days_left": 41, "joined": False}],
        "my_calls": [{"id": "0f0f0f0f", "repo": "gwas-qc", "full_name": "your-name/gwas-qc",
                      "note": "A second pair of eyes on the LD-pruning step before we publish.",
                      "skills": ["plink", "gwas"], "level_label": "any level", "time_label": "a few hours",
                      "days_left": 23, "filled": False,
                      "responders": [{"login": "omar-plants", "avatar_url": "", "skills": ["plink"], "at": ago(3),
                                      "profile_url": ""}]}],
    }


def render() -> dict[str, Path]:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QScrollArea
    app = QApplication.instance() or QApplication(sys.argv)
    from mygeeky.config import load_config
    from mygeeky.gui import app as logic
    logic.get_update_info = lambda cfg: {"show": False}
    logic.get_token_warnings = lambda cfg: []
    logic.save_config = lambda c: None
    import mygeeky.config as config_mod
    config_mod.save_config = lambda c: None          # the pictures must never change your settings...
    from mygeeky import freshness
    freshness.save = lambda data: None               # ...or mark your cards as seen
    logic.mark_seen = lambda keys, clicked=False: None
    logic.get_signals = example_signals
    logic.is_admin = lambda cfg: False      # the maker's private tab stays out of public pictures
    logic.sync_enabled = lambda cfg: False
    for name in ("news_refresh_due", "trends_due", "market_refresh_due", "hf_models_due", "growth_due"):
        setattr(logic, name, lambda cfg: False)
    # Chances: the listings the maker accepted show as they will once published (no "not published" note)
    shown_opportunities = logic.get_opportunities

    def opportunities(cfg):
        out = shown_opportunities(cfg)
        try:
            from mygeeky import curated, scout
            accepted = [c for c in scout.candidates("accepted")]
            if accepted:
                data = curated.load()
                data = {**data, **{k: list(data.get(k, [])) + [c["item"] for c in accepted if c["kind"] == k]
                                   for k in curated.DATED}}
                from mygeeky import interests
                w = interests.profile_terms(cfg)
                out.update({k: curated.ranked(cfg, k, weights=w, data=data) for k in curated.DATED})
        except Exception:
            pass
        return out
    logic.get_opportunities = opportunities
    # Protocols: two started ones, in a throwaway file (never your own learning_paths.json)
    import tempfile
    from mygeeky import protocols
    protocols.PATHS_FILE = Path(tempfile.mkdtemp()) / "learning_paths.json"
    pid = protocols.start(cfg_for_protocols := load_config(), protocols.find_reviewed("R", "data analysis"))
    protocols.tick(cfg_for_protocols, pid, "deeper")
    protocols.start(cfg_for_protocols, protocols.find_reviewed("GWAS"))
    # Quiz scores, in a throwaway file too (never your own quiz.json)
    from mygeeky import quiz
    quiz.QUIZ_FILE = Path(tempfile.mkdtemp()) / "quiz.json"
    banked = {q["protocol"] for q in quiz.bank()["questions"]}
    for p in protocols.reviewed():                     # start the ones with a quiz, and score one
        if p["id"] in banked:
            protocols.start(cfg_for_protocols, p)
    shown = next((pid for pid in protocols.mine(cfg_for_protocols) if pid in banked), "")
    if shown:
        drawn = quiz.Quiz.draw(protocols.mine(cfg_for_protocols)[shown]["protocol"])
        answers = [q.answer for q in drawn.questions]
        if len(answers) > 2:
            answers[1] = (answers[1] + 1) % 4          # one wrong: a real-looking score
        quiz.record(quiz.mark(drawn, answers))
    from mygeeky.gui.qt_panel import MyGeekyPanel
    from PySide6.QtCore import QRect
    # one size for every picture, whatever this computer's screen: a share of a small laptop screen at 2x
    # is too short to show anything, and your own width setting shouldn't change the README
    size = (500, 700 if TALL else 520)
    docked = MyGeekyPanel._docked_geometry
    MyGeekyPanel._docked_geometry = lambda self, folded, screen: (docked(self, folded, screen) if folded
                                                                  else QRect(0, 0, *size))

    def pump(seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            app.processEvents()
            time.sleep(0.03)

    cfg = dataclasses.replace(load_config(), gui_hearts_enabled=False, gui_panel_height_fraction=1.0 if TALL else 0.62,   # 1.0: clamped to the tallest
                              gui_theme="midnight")              # the pictures always show the dark theme
    panel = MyGeekyPanel(cfg)
    panel.setAttribute(Qt.WA_DontShowOnScreen, True)
    panel.show()
    pump(3)
    out = {}
    for fname, tab, mode in TABS:
        if tab == "signals":
            SHOW_EXAMPLES["on"] = True
            panel._refresh_signals(force=True)
        panel._switch_tab(tab)
        if tab == "grow" and mode == "quiz-run":        # a quiz being taken, inside the tab
            panel._set_grow_mode("quiz")
            pump(1.0)
            pid = next((p for p in protocols.mine(cfg_for_protocols)
                        if quiz.counts(p)["total"]), "")
            if pid:
                drawn = quiz.Quiz.draw(protocols.mine(cfg_for_protocols)[pid]["protocol"])
                panel._start_quiz(pid, drawn, stage="", stage_title="")
                pump(1.0)
                panel._quiz_pick(drawn.questions[0].answer)      # answered, so the reason and source show
                pump(0.6)
                panel._grow_scroll.verticalScrollBar().setValue(0)   # start the picture at the question
        elif tab == "grow":
            panel._set_grow_mode(mode)
        elif tab == "chances":
            panel._set_chance_mode(mode)
        elif tab == "news":
            panel._set_news_mode(mode)
        elif tab == "model":
            panel._show_you_part(mode)
        elif mode:
            panel._set_market_mode(mode)
        pump(4.5 if tab in ("grow", "chances") else 2.5)
        if tab in ("grow", "chances") and mode != "quiz-run":   # each picture starts at the top of its page,
            area = panel._grow_scroll if tab == "grow" else panel.chances_area.parentWidget()   # not where the last left it
            while area is not None and not isinstance(area, QScrollArea):
                area = area.parentWidget()
            if area is not None:
                area.verticalScrollBar().setValue(0)
                pump(0.3)
        if fname == "grow-protocols":  # start the picture at your protocols: the road map and a step
            from mygeeky.gui.growth_ui import ProtocolCard
            cards = [c for c in panel.grow_area.parentWidget().findChildren(ProtocolCard) if c.isVisible()]
            box = panel._grow_scroll
            if cards:
                box.verticalScrollBar().setValue(cards[0].mapTo(box.widget(), cards[0].rect().topLeft()).y() - 4)
            pump(0.5)
        if fname == "chances-seasons":
            # Seasons opens on a month picker and a paragraph explaining itself, which is the right
            # thing in the app and a picture of nothing in a README. Start at the first card instead:
            # a season IS its card -- the window, the years of evidence, the sentence that was found.
            from mygeeky.gui.growth_ui import SeasonCard
            cards = [c for c in panel.chances_area.parentWidget().findChildren(SeasonCard) if c.isVisible()]
            box = panel.chances_area.parentWidget()
            while box is not None and not isinstance(box, QScrollArea):
                box = box.parentWidget()
            if cards and box is not None:
                top = cards[0].mapTo(box.widget(), cards[0].rect().topLeft()).y()
                box.verticalScrollBar().setValue(max(0, top - 4))
            pump(0.5)
        if tab == "signals":          # start the picture at "Your field" (the panel is short)
            from mygeeky.gui.signals_ui import FieldCard
            field = panel.signals_area.parentWidget().findChildren(FieldCard)[0]
            box = panel.signals_area.parentWidget()
            while box is not None and not isinstance(box, QScrollArea):
                box = box.parentWidget()
            if box is not None:
                box.verticalScrollBar().setValue(field.mapTo(box.widget(), field.rect().topLeft()).y() - 4)
            pump(0.5)
        path = SHOTS / f"{fname}.png"
        panel.panel_frame.grab().save(str(path))
        out[fname] = path
        print("  ", path.name)
    out.update(quiz_shots(app, cfg))
    return out


def _trim_bottom(path: Path, keep: int = 14) -> None:
    """Cut the plain background off the bottom of a picture (Qt's wrapped labels ask for too much room)."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    bg = im.getpixel((w - 2, h - 2))
    bottom = h
    while bottom > 1:
        row = im.crop((0, bottom - 1, w, bottom)).getcolors(w) or []
        if len(row) > 1 or row[0][1] != bg:
            break
        bottom -= 1
    if bottom < h:
        im.crop((0, 0, w, min(h, bottom + keep))).save(path)


def quiz_shots(app, cfg) -> dict:
    """The quiz: one question answered (why, and the source it came from), and the score at the end."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from mygeeky import protocols, quiz
    from mygeeky.gui.growth_ui import QuestionCard, ResultView
    from mygeeky.gui.qt_panel import THEMES
    theme = THEMES["midnight"]
    out = {}
    # the protocol with the most questions in the shipped bank
    banked = {}
    for q in quiz.bank()["questions"]:
        banked[q["protocol"]] = banked.get(q["protocol"], 0) + 1
    if not banked:
        print("   (no questions in the bank yet: skipping the quiz pictures)")
        return out
    pid = max(banked, key=lambda k: banked[k])
    proto = next(p for p in protocols.reviewed() if p["id"] == pid)
    drawn = quiz.Quiz.draw(proto, n=min(10, banked[pid]))

    def shot(widget, name):
        holder = QWidget()
        holder.setStyleSheet("background:#17171f;")
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.addWidget(widget)
        holder.setFixedWidth(430)
        holder.show()
        end = time.time() + 1.2
        while time.time() < end:
            app.processEvents()
            time.sleep(0.03)
        holder.resize(430, holder.layout().sizeHint().height())   # only as tall as what it says
        app.processEvents()
        path = SHOTS / f"{name}.png"
        holder.grab().save(str(path))
        _trim_bottom(path)          # wrapped labels over-report their height: cut the empty tail
        out[name] = path
        print("  ", path.name)
        holder.hide()

    q = drawn.questions[0]
    q.picked = q.answer                       # answered, so the reason and the source show
    shot(QuestionCard(q, theme, lambda i: None, lambda url: True), "quiz-question")
    answers = [x.answer for x in drawn.questions]
    if len(answers) > 2:
        answers[1] = (answers[1] + 1) % 4     # one wrong, so the breakdown is worth looking at
    shot(ResultView(quiz.mark(drawn, answers), theme, best_before=0.6), "quiz-score")
    return out


def setup_pages() -> None:
    """The installer's pages (welcome, token 1, Signals, finish), with your real state."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    from mygeeky import __version__, setup_api
    from mygeeky.gui import setup_wizard as sw
    # same answers the installer would get, computed in this process (no helper processes, no installs)
    sw.api = lambda python, action, payload=None, timeout=None, **kw: setup_api.ACTIONS[action](payload or {})
    sw.SetupWizard.detect = lambda self: self.info.update(version=__version__, editable=False) or self.info
    wiz = sw.SetupWizard()
    wiz.python = sys.executable
    wiz.refresh_state()
    welcome = wiz.page(0)                 # its background check dies when rendered off-screen; say it directly
    welcome._checked = True
    welcome.found.setText(f"Found myGeeKy {__version__}. Setup will update it and keep all your settings.")
    wiz.setAttribute(Qt.WA_DontShowOnScreen, True)
    wiz.show()
    for name, page_id, wait in (("setup-welcome", 0, 2), ("setup-github", 3, 2), ("setup-signals", 5, 8),
                                ("setup-finish", 6, 2)):
        wiz.setStartId(page_id)
        wiz.restart()
        end = time.time() + wait
        while time.time() < end:
            app.processEvents()
            time.sleep(0.03)
        wiz.grab().save(str(SHOTS / f"{name}.png"))
        print("  ", f"{name}.png")


def hero(shots: dict[str, Path]) -> None:
    from PIL import Image, ImageDraw, ImageFilter
    picks = [Image.open(shots[k]).convert("RGBA") for k in ("suggestions", "model", "research")]
    h = 1100
    picks = [p.resize((round(p.width * h / p.height), h), Image.LANCZOS) for p in picks]
    gap, pad = 60, 90
    W = sum(p.width for p in picks) + gap * (len(picks) - 1) + pad * 2
    H = h + pad * 2
    bg = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(bg)
    for y in range(H):   # the website's charcoal (#141416), a touch lighter at the top
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(30 - 10 * k), int(30 - 10 * k), int(33 - 11 * k), 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for cx, color in ((0.2, (255, 111, 216, 40)), (0.8, (127, 216, 255, 34))):
        gd.ellipse([W * cx - 500, H * 0.5 - 420, W * cx + 500, H * 0.5 + 420], fill=color)
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    x = pad
    for i, p in enumerate(picks):
        y = pad + (0 if i == 1 else 40)
        shadow = Image.new("RGBA", (p.width + 80, p.height + 80), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle([40, 40, p.width + 40, p.height + 40], 40, fill=(0, 0, 0, 150))
        bg.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(26)), (x - 40, y - 20))
        bg.alpha_composite(p, (x, y))
        x += p.width + gap
    bg.convert("RGB").save(SHOTS / "hero.png", optimize=True)
    print("   hero.png")


def tour(shots: dict[str, Path]) -> None:
    """Every tab, crossfading -- small enough for GitHub and PyPI."""
    from PIL import Image
    order = ["live", "suggestions", "repos", "market", "research", "news", "activity", "signals", "grow-skills",
             "grow-protocols", "chances-jobs", "model"]
    w = 400
    frames_src = []
    for k in order:
        im = Image.open(shots[k]).convert("RGB")
        frames_src.append(im.resize((w, round(im.height * w / im.width)), Image.LANCZOS))
    h = max(f.height for f in frames_src)
    canvas = lambda f: (lambda c: (c.paste(f, (0, 0)), c)[1])(Image.new("RGB", (w, h), (18, 18, 28)))  # noqa: E731
    frames_src = [canvas(f) for f in frames_src]
    frames, durations = [], []
    for i, f in enumerate(frames_src):
        nxt = frames_src[(i + 1) % len(frames_src)]
        frames.append(f)
        durations.append(2200)
        for s in (0.25, 0.5, 0.75):
            frames.append(Image.blend(f, nxt, s))
            durations.append(70)
    pal = [f.quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for f in frames]
    pal[0].save(ROOT / "docs" / "tour.gif", save_all=True, append_images=pal[1:], duration=durations, loop=0,
                optimize=True, disposal=1)
    print("   tour.gif", round((ROOT / "docs" / "tour.gif").stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    shots = render()
    if TALL:
        sys.stdout.flush()
        os._exit(0)
    setup_pages()
    hero(shots)
    tour(shots)
    sys.stdout.flush()
    os._exit(0)   # skip Qt's slow teardown of background workers
