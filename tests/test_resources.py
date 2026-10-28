"""The resource audit's quick version, on every test run: pages must not leak widgets, the synced folder must not carry
databases, and the audit itself reads the folders right (tools/resource_audit.py; the protocol: docs/RESOURCES.md)."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resource_audit", ROOT / "tools" / "resource_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_visiting_every_page_again_and_again_leaks_no_widgets(qapp_offscreen):
    out = audit.leak(rounds=4)
    assert len(out["tabs"]) >= 10
    widgets = [r["widgets"] for r in out["rounds"]]
    assert widgets[-1] - widgets[1] <= audit.BUDGETS["leak_widgets_per_round"] * 2, widgets
    assert out["checks"]["leak_widgets_per_round"] != "FAIL"


def test_the_storage_audit_finds_databases_and_tracked_ignored_files(tmp_path, monkeypatch):
    from mygeeky import config, sync
    data, local = tmp_path / "mygeeky", tmp_path / "mygeeky-local"
    data.mkdir()
    local.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "LOCAL_DIR", local)
    monkeypatch.setattr(config, "AVATAR_CACHE_DIR", data / "avatar_cache")
    monkeypatch.setattr(config, "LOG_DIR", data / "logs")
    subprocess.run(["git", "init", "-q", "-b", "main", str(data)], check=True, timeout=120)
    (data / ".gitignore").write_text(sync.GITIGNORE)
    (data / "taste.json").write_text("{}")
    (data / "headlines.json").write_text("[]")
    subprocess.run(["git", "-C", str(data), "add", "-f", "headlines.json", "taste.json"], check=True, timeout=120)
    subprocess.run(["git", "-C", str(data), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                   check=True, timeout=120)
    (data / "wisep.sqlite").write_bytes(b"x" * 1000)
    (local / "github_cache.sqlite").write_bytes(b"x" * 2_000_000)
    out = audit.storage()
    assert out["stray_in_data"] == ["wisep.sqlite"] and out["checks"]["stray_in_data"] == "WARN"
    assert out["tracked_but_ignored"] == ["headlines.json"] and out["checks"]["tracked_but_ignored"] == "FAIL"
    assert out["local_mb"] == pytest.approx(2.0, abs=0.01) and out["syncs_per_day"] == 1
    assert set(out["checks"]) >= {"data_working_mb", "local_mb", "data_git_mb", "syncs_per_day", "beacon_kb"}


def test_the_ignore_list_covers_every_file_the_program_says_is_never_synced():
    """config.py names files that stay on one computer; sync must not carry them (four slipped through)."""
    from mygeeky import sync
    ignored = sync.GITIGNORE.splitlines()
    for name in ("notify_state.json", "rank_seen.json", "my_github_events.json", "whois.json", "wisep.sqlite",
                 "github_cache.sqlite", "headlines.json", "keywords.json", "github_achievements.json"):
        assert any(name == p or (p.startswith("*") and name.endswith(p.lstrip("*"))) or
                   (p.endswith("*") and name.startswith(p.rstrip("*"))) for p in ignored), name


def test_the_interest_map_moves_a_while_then_rests(qapp_offscreen):
    from mygeeky.gui import qt_panel
    m = qt_panel.InterestMap()
    m.set_data("me", ["Genomics"], [("gwas", 1.0)], ["ecology"])
    m.show()
    assert m._timer.isActive()                                  # it comes alive when it appears
    m._awake_until = 0.0
    m._tick()
    assert not m._timer.isActive()                              # ...then rests: no more repaints
    m.wake(qt_panel.MAP_WAKE_MS)
    assert m._timer.isActive()                                  # the mouse coming over it wakes it again
    m.hide()
    assert not m._timer.isActive()


def test_games_opened_again_and_again_leak_nothing_and_rest_when_still(qapp_offscreen):
    """Every game opened and left four times: no widgets pile up and no game timer keeps running after you leave;
    a game resting on its start card stops repainting; a finished round's delayed result dies with the game."""
    import time
    from PySide6.QtCore import QEvent, QTimer
    from PySide6.QtWidgets import QApplication
    from mygeeky import gems
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui.qt_panel import MyGeekyPanel

    def settle(seconds=0.0):
        end = time.time() + seconds
        while True:
            QApplication.processEvents()
            QApplication.sendPostedEvents(None, QEvent.DeferredDelete.value)    # run deleteLater
            if time.time() >= end:
                break
            time.sleep(0.01)

    p = MyGeekyPanel(MyGeekyConfig(github_username="me", keywords=["gwas", "python"]))
    p.resize(460, 760)
    p.show()
    try:
        p._switch_tab("games")
        g = p.games_page
        counts = []
        for _ in range(4):
            for gid in gems.GAME_IDS:
                g.open(gid)
                settle(0.05)
                g.show_hub()
            settle()
            counts.append(len(QApplication.allWidgets()))
        assert counts[-1] - counts[0] <= 5, counts
        assert not [t for t in g.findChildren(QTimer) if t.isActive()]       # nothing left running on the hub

        g.open("run")                                                          # resting on its start card
        w = g.game_widget
        settle(0.3)
        assert w.paused and w._still                                           # drawn once, then no more repaints
        import sys
        errors, hook = [], sys.excepthook
        sys.excepthook = lambda *e: errors.append(e[1])
        try:
            w.end()                                                            # a round ends...
            g.show_hub()                                                       # ...and you leave at once
            settle(0.7)
        finally:
            sys.excepthook = hook
        assert not errors, errors                                              # its result never reached a deleted game
    finally:
        p.close()


def test_the_live_ticker_stops_while_hidden(qapp_offscreen):
    from PySide6.QtWidgets import QWidget
    from mygeeky.gui import qt_panel
    host = QWidget()
    t = qt_panel.SpotlightTicker(lambda url: True, None)
    t.setParent(host)
    t.resize(300, 200)
    t._items = [{"title": str(i)} for i in range(10)]          # more than fit: it would turn
    t.start(4500)
    assert not t.is_running()                                   # not shown yet: nothing turns
    host.show()
    t.show()
    if len(t._items) > len(t._cards):
        assert t.is_running()
    host.hide()
    assert not t.is_running()                                   # folded or hidden: it rests


def test_a_sealed_box_is_opened_once():
    from mygeeky import signal_crypto as sc
    key, pub = sc.new_keypair()
    box = sc.seal(pub, b"thanks")
    sc._open_box.cache_clear()
    assert sc.open_box(key, box) == b"thanks" and sc.open_box(key, box) == b"thanks"
    info = sc._open_box.cache_info()
    assert info.hits == 1 and info.misses == 1                   # the second read cost nothing
    assert sc.open_box(key, 123) is None and sc.open_box(None, box) is None


def test_history_files_keep_four_months_live_and_archive_the_rest(tmp_path):
    import gzip
    import json
    from datetime import datetime, timezone
    from mygeeky import storage
    log = tmp_path / "suggestions_history.jsonl"
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    rows = [{"username": f"u{i}", "timestamp": f"2026-{m:02d}-15T00:00:00+00:00"} for i, m in enumerate([4, 5, 5, 9, 10])]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows) + "not json\n")
    assert storage.rotate_jsonl(log, now=now) == 3                       # April and May: past 120 days
    kept = log.read_text().splitlines()
    assert [json.loads(x)["username"] for x in kept[:2]] == ["u3", "u4"] and kept[2] == "not json"
    may = gzip.decompress((tmp_path / "archive" / "suggestions_history-2026-05.jsonl.gz").read_bytes()).decode()
    assert [json.loads(x)["username"] for x in may.splitlines()] == ["u1", "u2"]   # kept, compressed, on this computer
    assert storage.rotate_jsonl(log, now=now) == 0                       # nothing old left: no rewrite
    log.write_text(json.dumps({"username": "x", "timestamp": "2026-06-10T00:00:00+00:00"}) + "\n")
    assert storage.rotate_jsonl(log, now=now) == 0                       # 133 days: within the monthly slack, wait
    from mygeeky import sync
    assert "archive/" in sync.GITIGNORE.splitlines()                     # the archive never travels


def test_the_avatar_cache_keeps_the_newest_photos(tmp_path):
    import os
    from mygeeky.gui.qt_panel import AvatarLoader
    for i in range(AvatarLoader.MAX_FILES + 25):
        p = tmp_path / f"{i:04d}.png"
        p.write_bytes(b"x")
        os.utime(p, (1000 + i, 1000 + i))
    assert AvatarLoader.prune(tmp_path) == 25
    left = sorted(p.name for p in tmp_path.glob("*.png"))
    assert len(left) == AvatarLoader.MAX_FILES and left[0] == "0025.png"          # the oldest went


def test_wisep_keeps_three_months_of_its_tally():
    from datetime import date, timedelta
    from mygeeky import wisep
    st = wisep.store()
    old, today = (date.today() - timedelta(days=200)).isoformat(), date.today().isoformat()
    st.count("openalex", "asked", old)
    st.count("openalex", "asked", today)
    st._trim()
    days = [r[0] for r in st.db.execute("SELECT day FROM calls").fetchall()]
    assert today in days and old not in days


def test_the_panel_starts_without_loading_scikit_learn():
    """scikit-learn, SciPy and NumPy cost about a second and 100+ MB: only what needs them loads them."""
    import subprocess
    import sys
    code = ("import sys; import mygeeky.gui.qt_panel, mygeeky.interests, mygeeky.cli; "
            "print(sorted(m for m in ('sklearn', 'scipy', 'numpy') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                         env={**__import__('os').environ, "QT_QPA_PLATFORM": "offscreen"})
    assert out.stdout.strip() == "[]", out.stdout + out.stderr


def test_the_vocabulary_matches_scikit_learn_without_loading_it():
    from sklearn.feature_extraction.text import CountVectorizer
    from mygeeky.matcher import build_domain_vocabulary
    text = ("Genome-wide association studies (GWAS) of wheat and chickpea; GWAS pipelines in Snakemake; "
            "machine learning for plant breeding, plant genomics and genomic selection. " * 3)
    v = CountVectorizer(stop_words="english", ngram_range=(1, 2), max_features=200, min_df=1)
    m = v.fit_transform([text]).toarray()[0]
    ref = {t: c / m.max() for t, c in zip(v.get_feature_names_out(), m) if c > 0}
    assert build_domain_vocabulary(text, 200) == ref                     # every term, every weight (no ties cut)


def test_the_model_page_reads_saved_weights(tmp_path, monkeypatch):
    from mygeeky import matcher
    from mygeeky.gui import app as logic
    monkeypatch.setattr(matcher, "MODEL_FILE", tmp_path / "model.pkl")
    model = matcher.LearnedModel()
    assert model.train([[0.1] * len(matcher.FEATURE_NAMES), [0.9] * len(matcher.FEATURE_NAMES)] * 3, [0, 1] * 3)
    model.save()
    assert (tmp_path / "model_weights.json").exists() and matcher.saved_weights() is not None
    shown = logic.get_model_weights()
    assert len(shown) == len(matcher.FEATURE_NAMES) and all("weight" in w for w in shown)


def test_matched_people_are_asked_every_half_hour_not_every_five_minutes(monkeypatch):
    from datetime import datetime, timezone
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui import app as logic
    asked = []

    class Client:
        def list_following(self, me):
            return ["friend"]

        def list_user_events(self, login, per_page=30):
            asked.append(login)
            return [{"type": "WatchEvent", "actor": {"login": login, "avatar_url": ""},
                     "repo": {"name": f"{login}/x"}, "payload": {"action": "started"},
                     "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}]
    monkeypatch.setattr(logic, "_build_client", lambda cfg: Client())
    monkeypatch.setattr(logic, "get_recent_activity", lambda *a, **k: [])
    monkeypatch.setattr(logic, "_profile_matches", lambda cfg, following: ["ada", "grace"])
    cfg = MyGeekyConfig(github_username="me")
    first = logic.get_activity(cfg, force=True)
    assert asked == ["ada", "grace"] and {e["actor"] for e in first["events"]} == {"ada", "grace"}
    second = logic.get_activity(cfg, force=True)                       # 5 minutes later, say
    assert [x for x in asked if x != "me"] == ["ada", "grace"]         # no new calls for them (your own: learning)
    assert {e["actor"] for e in second["events"]} == {"ada", "grace"}  # ...their events kept


def test_chances_draws_its_cards_when_first_opened(qapp_offscreen):
    from mygeeky.config import MyGeekyConfig
    from mygeeky.gui.qt_panel import MyGeekyPanel
    panel = MyGeekyPanel(MyGeekyConfig(github_username="me", keywords=["gwas"]))
    try:
        panel._on_chances_ready({"jobs": [], "funding": [], "conferences": []})
        assert panel.chances_area.count() == 0 and panel._chances_pending       # not built while unseen
        panel._switch_tab("chances")
        assert panel._chances_drawn and not panel._chances_pending              # built on first open
    finally:
        panel.close()


def test_a_refused_token_is_dropped_and_public_data_still_reads():
    """GitHub's 401 (an expired or revoked token): the computer reads on without it, as the phone does."""
    import requests
    from mygeeky.github_client import GitHubClient
    c = GitHubClient(token="ghp_expired0000000000000000000000000000", use_cache=False, rate_limit_sleep=0)
    seen = []

    def get(url, params=None, headers=None, timeout=None):
        seen.append("Authorization" in c.session.headers)
        r = requests.Response()
        r.status_code = 401 if "Authorization" in c.session.headers else 200
        r._content = b'{"login": "octocat"}'
        r.headers["Content-Type"] = "application/json"
        return r
    c.session.get = get
    assert c._get("/users/octocat").json() == {"login": "octocat"}
    assert seen == [True, False] and c.token_refused                       # tried with it, then without
    c._get("/users/torvalds")
    assert seen[-1] is False                                               # and without it from then on


@pytest.mark.skipif(not __import__("tests.phone", fromlist=["x"]).node_ok(), reason="needs Node 22.6+")
def test_the_phone_forgets_a_refused_token_and_reads_on_without_it():
    from tests import phone
    said = phone.run("""
import { gh } from './lib/github.ts';
import { getToken, isRejected, onTokenRejected, setToken } from './lib/storage.ts';
const sent: (string | null)[] = [];
let told = 0;
onTokenRejected(() => { told += 1; });
globalThis.fetch = (async (_url: string, init: any) => {
  const auth = init?.headers?.Authorization ?? null;
  sent.push(auth);
  return new Response(JSON.stringify({ login: 'octocat' }), { status: auth ? 401 : 200, headers: { 'Content-Type': 'application/json' } });
}) as any;
await setToken('ghp_expired');
const first = await gh('/users/octocat', 'ghp_expired');
const second = await gh('/users/torvalds', 'ghp_expired');     // a screen still holding the old token
out({ first, sent, told, stored: await getToken(), rejected: isRejected('ghp_expired') });
""", {})
    assert said["first"] == {"login": "octocat"}
    assert said["sent"] == ["Bearer ghp_expired", None, None]               # once with it, then never again
    assert said["told"] == 1 and said["stored"] is None and said["rejected"] is True
