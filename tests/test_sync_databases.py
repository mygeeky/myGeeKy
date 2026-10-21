"""Live databases never travel through sync: they live beside the data folder, files the ignore list names stop being
carried even if an older version committed them, and another computer still committing one can't break a sync or
overwrite anything. (A synced GitHub cache grew a data repo to gigabytes and damaged the cache on every pull.)"""

import os
import shutil
import subprocess

import pytest

from mygeeky import config, sync

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _computer(path, remote):
    """An older myGeeKy's data folder: it commits whatever is there (as before the fix)."""
    _git(remote.parent, "clone", "-q", str(remote), str(path))
    _git(path, "config", "user.email", "t@t")
    _git(path, "config", "user.name", "t")
    _git(path, "checkout", "-q", "-B", "main")
    return path


def _old_sync(path, files, message):
    for name, body in files.items():
        (path / name).write_bytes(body)
    _git(path, "add", "-A", "-f")                     # -f: the old version carried the database regardless
    _git(path, "commit", "-q", "-m", message)
    if _git(path, "ls-remote", "--heads", "origin", "main").strip():
        _git(path, "pull", "-q", "--no-rebase", "-X", "theirs", "origin", "main")
    _git(path, "push", "-q", "origin", "main")


@pytest.fixture
def two_computers(tmp_path, monkeypatch):
    remote = tmp_path / "github.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    old = _computer(tmp_path / "old", remote)
    _old_sync(old, {"github_cache.sqlite": b"v1" * 1000, "taste.json": b'{"a": 1}'}, "old computer's first sync")
    new = tmp_path / "new"
    _git(tmp_path, "clone", "-q", str(remote), str(new))
    monkeypatch.setattr(sync, "DATA_DIR", new)
    monkeypatch.setattr(sync, "_has_gh", lambda: False)
    monkeypatch.setattr(sync, "export_config", lambda: None)
    monkeypatch.setattr(sync, "import_config", lambda: False)
    monkeypatch.setattr(sync, "_apply_admin_log", lambda: 0)
    return remote, old, new


def test_a_database_an_older_version_committed_stops_being_carried(two_computers):
    remote, old, new = two_computers
    assert "github_cache.sqlite" in _git(new, "ls-files")
    (new / "taste.json").write_text('{"a": 2}')
    sync.push()
    assert "github_cache.sqlite" not in _git(new, "ls-files")                        # no longer carried
    assert (new / "github_cache.sqlite").exists()                                    # but nothing deleted here
    assert "*.sqlite" in (new / ".gitignore").read_text()
    assert "wisep.sqlite" not in _git(new, "ls-files")


def test_another_computer_still_committing_it_cannot_break_a_sync_or_overwrite_anything(two_computers):
    remote, old, new = two_computers
    (new / "github_cache.sqlite").unlink()                                            # its database lives elsewhere now
    sync._commit_local("the fixed computer lets go of it")                           # not pushed yet...
    _old_sync(old, {"github_cache.sqlite": b"v2" * 1000, "taste.json": b'{"a": 3}'}, "old computer, again")  # ...meanwhile
    (new / "seen.json").write_text("[]")
    assert sync.push() == "Pushed to GitHub."                                         # the conflict is settled, not raised
    assert (new / "taste.json").read_text() == '{"a": 3}'                             # the rest still merges
    assert not (new / "github_cache.sqlite").exists()                                 # their copy wasn't left here
    assert "github_cache.sqlite" not in _git(new, "ls-files")
    assert _git(new, "status", "--porcelain").strip() == ""
    tree = _git(remote, "ls-tree", "--name-only", "main")
    assert "seen.json" in tree and "github_cache.sqlite" not in tree


def test_a_real_conflict_is_not_hidden(two_computers):
    remote, old, new = two_computers
    (new / "taste.json").unlink()                                                     # one side deletes your data...
    sync._commit_local("deleted here")
    _old_sync(old, {"taste.json": b'{"a": 9}'}, "changed there")                      # ...the other changes it
    with pytest.raises(sync.SyncError, match="Couldn't merge"):
        sync.push()
    assert "MERGE_HEAD" not in [p.name for p in (new / ".git").iterdir()]             # left as it was, not half-merged


def test_the_databases_live_beside_the_data_folder_and_move_there_once(tmp_path, monkeypatch):
    data, local = tmp_path / "mygeeky", tmp_path / "mygeeky-local"
    data.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "LOCAL_DIR", local)
    for suffix, body in (("", b"db"), ("-wal", b"wal"), ("-shm", b"shm")):
        (data / f"wisep.sqlite{suffix}").write_bytes(body)
    for i in range(5):
        p = data / f"wisep.sqlite.broken-{i}"
        p.write_bytes(b"x")
        os.utime(p, (1000 + i, 1000 + i))
    new = config.local_db("wisep.sqlite")
    assert new == local / "wisep.sqlite" and new.read_bytes() == b"db"
    assert (local / "wisep.sqlite-wal").read_bytes() == b"wal" and not (data / "wisep.sqlite").exists()
    assert sorted(p.name for p in data.glob("wisep.sqlite.broken-*")) == ["wisep.sqlite.broken-3", "wisep.sqlite.broken-4"]
    (data / "wisep.sqlite").write_bytes(b"a stray copy from another computer")
    assert config.local_db("wisep.sqlite").read_bytes() == b"db"                      # never replaced by a stray
    from mygeeky import ghcache, wisep
    assert ghcache.CACHE_FILE.name == "github_cache.sqlite" and wisep.DB_FILE.name == "wisep.sqlite"
    real = config.DATA_DIR.parent / f"{config.DATA_DIR.name}-local"
    assert ghcache.CACHE_FILE.parent != config.DATA_DIR and wisep.DB_FILE.parent != config.DATA_DIR
    assert real.name.endswith("-local")


def test_a_sync_with_nothing_new_on_either_side_only_checks(two_computers, monkeypatch):
    remote, old, new = two_computers
    sync.push()                                                              # in step now
    calls = []
    real = sync._git
    monkeypatch.setattr(sync, "_git", lambda *a, **k: calls.append(a[0]) or real(*a, **k))
    assert sync.push() == "Nothing new to push (remote is up to date)."
    assert "fetch" not in calls and "push" not in calls and "merge" not in calls
    _old_sync(old, {"notes.md": b"new there\n"}, "the other computer")       # something new there...
    calls.clear()
    sync.push()
    assert "fetch" in calls and (new / "notes.md").read_text() == "new there\n"   # ...is fetched and merged
