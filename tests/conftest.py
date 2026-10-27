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
import mygeeky.trace  # noqa: F401
import mygeeky.adminaudit  # noqa: F401
import mygeeky.support  # noqa: F401

@pytest.fixture(autouse=True, scope="session")
def _isolate_child_processes(tmp_path_factory):
    """Tests that start myGeeKy as a separate program (the CLI, the setup helper, the phone checks) can't see the
    patching below: point every OS's data and settings folders somewhere temporary for them, so they never open the
    user's real databases (one moved the real GitHub cache)."""
    import os
    root = tmp_path_factory.mktemp("child-home")
    saved = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "APPDATA", "LOCALAPPDATA")}
    for k in saved:
        os.environ[k] = str(root / k.lower())
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


REAL_ROOTS = (Path(config_module.CONFIG_DIR), Path(config_module.DATA_DIR), Path(config_module.LOCAL_DIR))


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
    fake_roots = {REAL_ROOTS[0]: tmp_path / "config", REAL_ROOTS[1]: tmp_path / "data", REAL_ROOTS[2]: tmp_path / "data-local"}
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
def _background_work_ends_inside_its_test(_isolate_real_data):
    """A panel starts quiet background refreshes (repos you could improve, new faces...). One that outlives its test
    runs after the isolation above is undone: with the user's real settings, real cache and real network (it searched
    GitHub with a real profile). Each test waits here for its workers, while still isolated."""
    yield
    qt_panel = sys.modules.get("mygeeky.gui.qt_panel")
    if qt_panel is not None:
        for worker in list(getattr(qt_panel._Worker, "_alive", ())):
            try:
                worker.wait(20_000)
            except RuntimeError:
                pass                       # its Qt object is already gone: nothing left running


@pytest.fixture(autouse=True, scope="session")
def _no_real_network():
    """Tests never reach the internet: anything that tries (a leftover background job, a forgotten fake) fails fast
    instead of using the network with whatever settings it finds. Loopback stays open (local servers, Node)."""
    import socket
    real_connect = socket.socket.connect

    def connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and (host in ("localhost", "::1") or host.startswith("127.") or self.family == socket.AF_UNIX):
            return real_connect(self, address)
        raise OSError(f"tests are offline (tried to reach {host})")
    socket.socket.connect = connect
    yield
    socket.socket.connect = real_connect


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


@pytest.fixture(autouse=True)
def _app_palette_back_after_each_test():
    """A panel sets the whole app's palette and font from its theme (qt_panel._apply_theme): each test starts with
    the app as it was, whatever theme the test before it used."""
    app = None
    if "PySide6.QtWidgets" in sys.modules:
        app = sys.modules["PySide6.QtWidgets"].QApplication.instance()
    saved = (app.palette(), app.font()) if app is not None else None
    yield
    if saved is not None:
        app.setPalette(saved[0])
        app.setFont(saved[1])


@pytest.fixture(autouse=True)
def _no_real_mailbox_passwords(monkeypatch):
    """The mailbox app passwords (job alerts, TRACE's trigger inbox, support@) live in the system keyring: a test gets
    an empty in-memory keyring for them instead, and can never read or write the real ones."""
    import mygeeky.mailbox as mailbox
    kept: dict[str, str] = {}
    monkeypatch.setattr(mailbox, "get_password", lambda service=mailbox.KEY_SERVICE: kept.get(service))

    def set_password(password, service=mailbox.KEY_SERVICE):
        password = (password or "").strip().replace(" ", "")
        if len(password) < 8:
            return False
        kept[service] = password
        return True
    monkeypatch.setattr(mailbox, "set_password", set_password)
    monkeypatch.setattr(mailbox, "forget_password", lambda service=mailbox.KEY_SERVICE: kept.pop(service, None))


@pytest.fixture(autouse=True)
def _no_real_google_sign_in(monkeypatch):
    """The maker's Google sign-in (in the system keyring) is never seen or changed by a test: each test gets an empty
    in-memory keyring for it."""
    import mygeeky.google_login as google_login
    kept: dict[str, str | None] = {}
    monkeypatch.setattr(google_login, "_get_refresh", lambda: kept.get("refresh"))
    monkeypatch.setattr(google_login, "_set_refresh", lambda value: kept.__setitem__("refresh", value))
    monkeypatch.setattr(google_login, "_access", {})


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
def _wisep_in_memory():
    """WISEP's store in memory for every test: no answers kept between tests, nothing written to the data folder."""
    import mygeeky.wisep as wisep
    wisep.reset(":memory:")
    yield


@pytest.fixture(autouse=True)
def _no_skill_trends(monkeypatch):
    """Rising skills reads the shared world file (it changes daily): an empty one in tests, never over the network."""
    import mygeeky.skilltrends as skilltrends
    monkeypatch.setattr(skilltrends, "refresh_if_due", lambda *a, **kw: False)
    monkeypatch.setattr(skilltrends, "load", lambda *a, **kw: skilltrends.clean({}))
    import mygeeky.datasets as datasets
    monkeypatch.setattr(datasets, "refresh_if_due", lambda *a, **kw: False)    # Grow → Data's list: never fetched


@pytest.fixture(autouse=True)
def _no_quiz_fetch(monkeypatch, request):
    """New quiz questions are never fetched by a test (test_quiz.py checks the fetch itself, with a fake network)."""
    if request.path.name != "test_quiz.py":
        import mygeeky.quiz as quiz
        monkeypatch.setattr(quiz, "refresh_if_due", lambda *a, **kw: False)


@pytest.fixture(autouse=True)
def _no_cited_by_fetch(monkeypatch, request):
    """You → Cited by asks OpenAlex in the background: never over the network in tests (test_citedby tests it)."""
    if request.module.__name__.endswith("test_citedby"):
        return
    import mygeeky.citedby as citedby
    monkeypatch.setattr(citedby, "refresh", lambda *a, **kw: {"ok": False, "state": {}})
