"""Choosing where your data is saved (saving.py): Google Drive first, a second computer that needs the recovery code,
and switching to GitHub, which leaves a "moved" mark behind."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from mygeeky import config, datalock as dl, google_login, saving, storesync as ss, sync
from mygeeky.config import load_config, save_config

from test_storesync import FakeDrive


@pytest.fixture
def drive(monkeypatch):
    fake = FakeDrive()
    real = ss.DriveStore
    monkeypatch.setattr(ss, "DriveStore", lambda token, session=None: real(lambda fresh: "tok", fake))
    monkeypatch.setattr(google_login, "signed_in", lambda: True)
    return fake


def _data():
    config.ensure_dirs()
    sync.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sync.DATA_DIR


def test_drive_first_then_a_second_computer_with_the_recovery_code(drive, monkeypatch, tmp_path):
    data = _data()
    (data / "cv_text.txt").write_text("my cv")
    cfg = load_config()
    cfg.keywords = ["genomics"]
    save_config(cfg)
    out = saving.use_drive()
    assert out["ok"] and saving.where(load_config()) == "drive"
    names = {f["name"] for f in drive.files.values()}
    assert {"mygeeky.json", "cv_text.txt.mgk", "config.synced.json.mgk"} <= names
    code = saving.recovery_code()
    assert dl.key_from_code(code) == ss.get_key()

    # another computer: an empty data folder, no key yet
    shutil.rmtree(data)
    data.mkdir()
    monkeypatch.setattr(ss, "STATE_FILE", tmp_path / "other-state.json")
    monkeypatch.setattr(ss, "DEVICE_FILE", tmp_path / "other-device")
    ss.set_key(None)
    with pytest.raises(ss.NeedsKey):
        saving.use_drive()
    cfg = load_config()
    cfg.sync_store = "drive"
    save_config(cfg)
    with pytest.raises(ss.StoreError, match="isn't right"):
        saving.enter_code("AAAA-" + code[5:])
    assert saving.enter_code(code)["ok"]
    assert (data / "cv_text.txt").read_text() == "my cv" and load_config().keywords == ["genomics"]


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_switching_to_github_moves_the_data_and_marks_drive_moved(drive, monkeypatch, tmp_path):
    data = _data()
    (data / "cv_text.txt").write_text("my cv")
    saving.use_drive()
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True, timeout=120)
    real_git = ss.GitStore
    monkeypatch.setattr(ss, "GitStore", lambda repo, clone=None, fresh=False, url=None:
                        real_git(repo, clone, fresh, url=str(bare)))
    monkeypatch.setattr(sync, "public_on_github", lambda repo: False)
    monkeypatch.setattr(sync, "_repo_exists", lambda repo: True)
    monkeypatch.setattr(sync, "_repo_is_private", lambda repo: True)
    out = saving.use_github("ada/mygeeky-data")
    assert out["ok"] and "Moved from Google Drive" in out["message"]
    cfg = load_config()
    assert saving.where(cfg) == "github" and cfg.sync_repo == "ada/mygeeky-data" and cfg.sync_store == ""
    tree = subprocess.run(["git", "ls-tree", "--name-only", "main"], cwd=bare, capture_output=True, text=True,
                          timeout=120).stdout.split()
    assert "cv_text.txt.mgk" in tree
    fmt = next(f["data"] for f in drive.files.values() if f["name"] == "mygeeky.json")
    assert dl.moved_to(fmt) == "github:ada/mygeeky-data"
    # a device still on Drive is told where the data went
    with pytest.raises(ss.Moved):
        ss.sync(ss.DriveStore(None), ss.get_key(), "bbbbbbbb", tmp_path / "elsewhere")
