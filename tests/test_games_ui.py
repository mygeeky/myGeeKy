"""🎮 Games on the computer (gui/games_ui.py): Games is in the main menu and opens the hub of every game with its
icon; a Terminal typing round (pick a right command, type it) ends in a result and reaches your progress, the
Model ("play") and the badges; Word Hunter starts its waves from the pack."""
from __future__ import annotations

from mygeeky import gems, gems_store, interests
from mygeeky.config import MyGeekyConfig


def _panel(qapp_offscreen):
    from mygeeky.gui.qt_panel import MyGeekyPanel
    p = MyGeekyPanel(MyGeekyConfig(github_username="me", keywords=["gwas", "python"]))
    p.resize(460, 760)
    p.show()
    return p


def test_games_is_in_the_main_menu_and_opens_every_game(qapp_offscreen):
    from mygeeky import navtree
    p = _panel(qapp_offscreen)
    try:
        top = [n["id"] for n in p.nav_tree["children"]]
        assert top[-2:] == ["games", "settings"]
        assert p._rail_icon(navtree.find(p.nav_tree, "games"))[0].startswith("M6 11h4")     # a line icon like the others
        p._nav_open(navtree.find(p.nav_tree, "games"))
        assert p.active_tab == "games" and p.nav_trail.text() == "Games"
        cards = p.games_page.cards
        assert sorted(c.game["id"] for c in cards) == sorted(gems.GAME_IDS)
    finally:
        p.close()


def test_a_terminal_round_reaches_progress_the_model_and_badges(qapp_offscreen):
    from PySide6.QtWidgets import QApplication
    p = _panel(qapp_offscreen)
    try:
        g = p.games_page
        g.open("terminal")
        w = g.game_widget
        assert len(w.items) == w.ROUND and all(it["kind"] == "command" for it in w.items)
        for i, it in enumerate(w.items):
            pick = it["right"][0] if i else it["wrong"]["cmd"]              # the first one wrong, the rest right
            next(b for b in w.buttons if b.text() == pick).click()
            if i:
                w.typing.setText(pick)
                w.typing.returnPressed.emit()
            w.next()
            QApplication.processEvents()
        prog = gems_store.load_progress()
        assert prog["games"]["terminal"]["plays"] == 1 and prog["games"]["terminal"]["right"] == len(w.items) - 1
        assert w.bonus > 0 and prog["games"]["terminal"]["xp"] > 10 * (len(w.items) - 1) - 1
        assert gems_store.badge_counts()["player"] == 1
        assert any(e["kind"] == "play" and e["source"] == "game:terminal" for e in interests.load_events())
    finally:
        p.close()


def test_word_hunter_starts_from_the_pack(qapp_offscreen):
    p = _panel(qapp_offscreen)
    try:
        p.games_page.open("hunter")
        hw = p.games_page.game_widget
        assert len(hw.waves) == 3 and all(ws["kind"] == "wordset" for ws in hw.waves)
        assert hw.queue and all(word for word, _ in hw.queue)
        assert any(s is hw.set for _, s in hw.queue) and any(s is not hw.set for _, s in hw.queue)   # set words and decoys
        hw.stop()
    finally:
        p.close()


def test_every_card_game_plays_a_round_into_progress(qapp_offscreen):
    """Real or made up, Gene or Pokémon, Which came first, Reviewer 2, Debug reef, Fix the figure: a whole round each,
    every question answered (some wrong), ending in a recorded round."""
    from PySide6.QtWidgets import QApplication
    from mygeeky.gui.games_cards import GAMES as CARDS
    p = _panel(qapp_offscreen)
    try:
        for gid in CARDS:
            p.games_page.open(gid)
            w = p.games_page.game_widget
            assert w.items, gid
            for i in range(len(w.items)):
                w.pick(w.right_index if i % 2 else (w.right_index + 1) % max(2, len(w.buttons)))
                assert w.note.text(), gid                          # an answer always says why
                w.next()
                QApplication.processEvents()
            stats = gems_store.load_progress()["games"][gid]
            assert stats["plays"] == 1 and stats["answered"] >= len(w.items), gid
        assert gems_store.badge_counts()["player"] == len(CARDS)
    finally:
        p.close()


def test_every_arcade_game_plays_to_the_end_into_progress(qapp_offscreen):
    """Whack-a-bug, Sort the catch, GeeKOc run, Flappy GeeKOc: driven frame by frame by a simple player until the
    round ends, which reaches your progress."""
    import time
    from PySide6.QtWidgets import QApplication
    from mygeeky.gui.games_arcade import GAMES as ARCADE

    def play(gid, w):
        if gid == "whack":
            for h in w.holes:
                if h["up"] and h["up"]["c"]["bug"]:
                    w.press(h["x"], h["y"] - 20)
        elif gid == "catch" and w.cur:
            w.cur["lane"], w.cur["vy"] = w.cur["bin"], 520
        elif gid == "run":
            nxt = next((o for o in w.obs if not o.get("done") and o["x"] > 60), None)
            if nxt and nxt["x"] < 190 and ("label" in nxt or nxt["top"]):
                w.jump()
        elif gid == "flappy":
            nxt = next((pp for pp in w.pipes if not pp.get("done")), None)
            (t0, t1), (b0, b1) = w._gaps()
            target = ((t0 + t1) / 2 if nxt["top"] else (b0 + b1) / 2) if nxt else w.H / 2
            if w.y > target + 10 and w.vy > -50:
                w.flap()

    p = _panel(qapp_offscreen)
    try:
        for gid in ARCADE:
            p.games_page.open(gid)
            w = p.games_page.game_widget
            w.timer.stop()                                   # driven by hand, 50 ms a frame
            w.go()
            for _ in range(4000):
                if w.ended:
                    break
                play(gid, w)
                w.step(0.05)
            assert w.ended and w.answers, gid
            end = time.time() + 3
            while time.time() < end and not gems_store.load_progress()["games"].get(gid):
                QApplication.processEvents()
            stats = gems_store.load_progress()["games"][gid]
            assert stats["plays"] == 1 and stats["answered"] == len(w.answers), gid
    finally:
        p.close()


def test_whack_a_bug_rewards_whacking_not_waiting(qapp_offscreen):
    """A round where you whack nothing: each critter counts once, a bug that got away is a miss, so it can't add up to
    a high score (it once counted every friend each time it popped up, and missed bugs not at all)."""
    p = _panel(qapp_offscreen)
    try:
        p.games_page.open("whack")
        w = p.games_page.game_widget
        w.timer.stop()
        w.go()
        for _ in range(700):
            if w.ended:
                break
            w.step(0.05)
        ids = [a["id"] for a in w.answers]
        assert len(ids) == len(set(ids))                                   # once each
        assert all(a["right"] is False for a in w.answers if a["id"].startswith("cr-b"))   # every bug got away
    finally:
        p.close()


def test_rise_and_the_maze_play_to_the_end(qapp_offscreen):
    """Rise: one wrong platform (it sinks, says why, and counts as that row's answer), then the right steps to the top.
    GeeKOc goes home: walk the way home, answering every door right."""
    import time
    from PySide6.QtWidgets import QApplication, QPushButton
    from mygeeky.gui.games_cards import WrapButton

    def frames(w, n=40):
        for _ in range(n):
            w.step(0.05)

    p = _panel(qapp_offscreen)
    try:
        p.games_page.open("rise")
        w = p.games_page.game_widget
        w.timer.stop()
        w.go()
        w.choose(next(i for i, o in enumerate(w.opts) if not o["ok"]))
        frames(w)
        assert w.message and w.answers[0]["right"] is False
        while not w.paused:
            w.choose(next(i for i, o in enumerate(w.opts) if o["ok"]))
            frames(w)
        assert w.row == len(w.ladder["rows"]) and len(w.answers) == len(w.ladder["rows"])

        p.games_page.open("maze")
        m = p.games_page.game_widget
        m.timer.stop()
        m.go()
        for _ in range(300):
            if m.home:
                break
            if m.overlay is not None:
                done = [b for b in m.overlay.findChildren(QPushButton) if b.text().startswith("Through")]
                if done:
                    done[0].click()
                    continue
                texts = [b.text() for b in m.overlay.findChildren(WrapButton)]
                q = next(q for q in sum(m.questions.values(), []) if sorted(q["options"]) == sorted(texts))
                next(b for b in m.overlay.findChildren(WrapButton) if b.text() == q["options"][0]).click()
                continue
            path = m._path(m.at[0], m.at[1], lambda k: False)
            m.move(path[1][0] - m.at[0], path[1][1] - m.at[1])
            frames(m, 4)
        assert m.home and m.asked >= 1 and m.right_first == m.asked
        end = time.time() + 2
        while time.time() < end:
            QApplication.processEvents()
    finally:
        p.close()
