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
