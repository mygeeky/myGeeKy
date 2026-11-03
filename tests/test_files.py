"""Saving a data file from several threads at once: every save lands, and the file is always whole."""
from __future__ import annotations

import json
import threading

from mygeeky.files import read_json, write_json


def test_saves_of_one_file_from_many_threads_never_fail(tmp_path):
    path = tmp_path / "snapshot.json"
    errors: list[BaseException] = []

    def save(n: int) -> None:
        try:
            for k in range(30):
                write_json(path, {"by": n, "k": k})
        except BaseException as exc:          # noqa: BLE001 - any failure is the bug
            errors.append(exc)

    threads = [threading.Thread(target=save, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors[0]
    assert set(read_json(path, {})) == {"by", "k"}
    assert json.loads(path.read_text(encoding="utf-8"))["k"] == 29
    assert not list(tmp_path.glob(".*.tmp"))  # no temporary file left behind


def test_a_save_lands_even_when_windows_refuses_the_swap(tmp_path, monkeypatch):
    """Issues #8 and #9: another program held the file, os.replace kept saying 'Access is denied' and the panel
    stopped. Now the text is written into the file directly, and no temporary file is left behind."""
    import mygeeky.files as files

    path = tmp_path / "games_progress.json"
    write_json(path, {"old": 1})
    calls = []

    def refuse(src, dst):
        calls.append(dst)
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(files.os, "replace", refuse)
    monkeypatch.setattr(files.time, "sleep", lambda s: None)
    write_json(path, {"new": 2})
    assert read_json(path, {}) == {"new": 2}
    assert len(calls) == 6                    # it did retry first
    assert not list(tmp_path.glob(".*.tmp"))


def test_a_read_only_file_is_made_writable_before_retrying(tmp_path, monkeypatch):
    import os
    import stat

    import mygeeky.files as files

    path = tmp_path / "support.json"
    write_json(path, {"old": 1})
    os.chmod(path, stat.S_IREAD)
    real = os.replace

    def windows_like(src, dst):               # Windows won't replace a read-only file
        if not os.access(dst, os.W_OK):
            raise PermissionError(5, "Access is denied")
        real(src, dst)

    monkeypatch.setattr(files.os, "replace", windows_like)
    monkeypatch.setattr(files.time, "sleep", lambda s: None)
    write_json(path, {"new": 2})
    assert read_json(path, {}) == {"new": 2}
