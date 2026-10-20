"""Keep every test away from the user's real myGeeKy data.

The real data dir is synced to the user's private GitHub repo, so a test
that logs suggestions/training rows/model history there doesn't just
pollute this machine -- it gets pushed and shows up as fake suggestions on
every machine. This autouse fixture repoints every path constant under the
real CONFIG_DIR/DATA_DIR, in every already-imported mygeeky module (each
`from .config import X` makes its own binding), to a per-test temp dir.
Tests that set their own paths (e.g. the sync tests) still win, since their
monkeypatching runs after this.
"""

import sys
from pathlib import Path

import pytest

import mygeeky.beacon  # noqa: F401 -- import everything that binds paths before patching
import mygeeky.cli  # noqa: F401
import mygeeky.setup_api  # noqa: F401
import mygeeky.producthunt  # noqa: F401
import mygeeky.updates  # noqa: F401
import mygeeky.tokens  # noqa: F401
import mygeeky.interests  # noqa: F401
import mygeeky.news  # noqa: F401
import mygeeky.papers  # noqa: F401
import mygeeky.admin  # noqa: F401
import mygeeky.keywords  # noqa: F401
import mygeeky.headlines  # noqa: F401
import mygeeky.achievements  # noqa: F401
import mygeeky.hfmodels  # noqa: F401
import mygeeky.producthunt  # noqa: F401
import mygeeky.config as config_module
import mygeeky.gui.app  # noqa: F401
import mygeeky.storage  # noqa: F401
import mygeeky.sync  # noqa: F401
import mygeeky.taste  # noqa: F401
import mygeeky.curated  # noqa: F401
import mygeeky.skills  # noqa: F401
import mygeeky.wins  # noqa: F401
import mygeeky.collab  # noqa: F401
import mygeeky.protocols  # noqa: F401
import mygeeky.protomodel  # noqa: F401
import mygeeky.scout  # noqa: F401
import mygeeky.ghcache  # noqa: F401
import mygeeky.quiz  # noqa: F401
import mygeeky.quizwriter  # noqa: F401
import mygeeky.leaderboard  # noqa: F401

REAL_ROOTS = (Path(config_module.CONFIG_DIR), Path(config_module.DATA_DIR))


def _under_real_root(value: Path) -> tuple[Path, Path] | None:
    for root in REAL_ROOTS:
        try:
            return root, value.relative_to(root)
        except ValueError:
            continue
    return None


@pytest.fixture(autouse=True)
def _own_github_cache(tmp_path, monkeypatch):
    """Each test gets its own GitHub cache: one test's remembered answers must never serve another's."""
    import mygeeky.ghcache as ghcache
    monkeypatch.setattr(ghcache, "CACHE_FILE", tmp_path / "github_cache.sqlite")
    ghcache.reset(tmp_path / "github_cache.sqlite")
    yield
    ghcache.reset(tmp_path / "github_cache.sqlite")


@pytest.fixture(autouse=True)
def _isolate_real_data(tmp_path, monkeypatch):
    fake_roots = {REAL_ROOTS[0]: tmp_path / "config", REAL_ROOTS[1]: tmp_path / "data"}
    for name, module in list(sys.modules.items()):
        if not (name == "mygeeky" or name.startswith("mygeeky.")) or module is None:
            continue
        for attr, value in list(vars(module).items()):
            if attr.isupper() and isinstance(value, Path):
                hit = _under_real_root(value)
                if hit:
                    root, rel = hit
                    monkeypatch.setattr(module, attr, fake_roots[root] / rel)


@pytest.fixture(autouse=True)
def _fresh_curated_lists(monkeypatch):
    """The curated lists are cached in memory once read: every test starts from the files."""
    import mygeeky.curated as curated
    monkeypatch.setattr(curated, "_loaded", None)


@pytest.fixture(autouse=True)
def _no_github_achievements_fetch(monkeypatch):
    """Panels read your GitHub achievements in the background: never over the network in tests."""
    import mygeeky.achievements as ach

    def offline(*a, **kw):
        raise ach.requests.ConnectionError("tests are offline")
    monkeypatch.setattr(ach.requests, "get", offline)



_EXIT_STATUS = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _EXIT_STATUS["code"] = int(exitstatus)


def pytest_unconfigure(config):
    """Panels made by tests start background work (fetches) that can outlive the tests.
    Qt aborts a process that exits with a QThread still running ("QThread: Destroyed
    while thread is still running"), turning a green run red. Do what the app does
    when it quits (gui/app.py): give the work a moment, then leave without destroying
    it. This is pytest's last hook, so the summary (and any failures) is already printed."""
    worker_module = sys.modules.get("mygeeky.gui.qt_panel")
    if worker_module is None:
        return
    if worker_module._Worker.drain(15000):
        import os
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_EXIT_STATUS["code"])


@pytest.fixture(autouse=True)
def _no_real_deepseek_key(monkeypatch):
    """The maker's real DeepSeek key (system keyring) is never seen by a test: a test that needs a key
    passes a fake one itself, and DeepSeek is always faked."""
    import mygeeky.scout as scout
    monkeypatch.setattr(scout, "get_key", lambda: None)


@pytest.fixture(scope="session")
def qapp_offscreen():
    """A Qt application with no screen, for widget tests (skipped when PySide6 isn't installed)."""
    import os
    pytest.importorskip("PySide6", reason="PySide6 (the 'gui' extra) is not installed")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def _no_ai_race_fetch(monkeypatch):
    """The News tab's AI race asks GitHub for the newest data in the background: never over the network in tests."""
    import mygeeky.airace as airace
    monkeypatch.setattr(airace, "refresh_if_due", lambda *a, **kw: False)
    monkeypatch.setattr(airace, "_loaded", None)


@pytest.fixture(autouse=True)
def _no_skill_trends(monkeypatch):
    """Rising skills reads the shared world file (it changes daily): an empty one in tests, never over the network."""
    import mygeeky.skilltrends as skilltrends
    monkeypatch.setattr(skilltrends, "refresh_if_due", lambda *a, **kw: False)
    monkeypatch.setattr(skilltrends, "load", lambda *a, **kw: skilltrends.clean({}))
    import mygeeky.datasets as datasets
    monkeypatch.setattr(datasets, "refresh_if_due", lambda *a, **kw: False)    # Grow → Data's list: never fetched


@pytest.fixture(autouse=True)
def _no_cited_by_fetch(monkeypatch, request):
    """You → Cited by asks OpenAlex in the background: never over the network in tests (test_citedby tests it)."""
    if request.module.__name__.endswith("test_citedby"):
        return
    import mygeeky.citedby as citedby
    monkeypatch.setattr(citedby, "refresh", lambda *a, **kw: {"ok": False, "state": {}})
