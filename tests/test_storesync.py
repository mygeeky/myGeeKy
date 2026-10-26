"""Saving your data in Google Drive (storesync.py): two devices keep the same plain files, only changed files move,
logs changed on both sides keep both sides' lines, a "moved" mark is obeyed, and the phone reads and adds to what the
computer saved."""
from __future__ import annotations

import hashlib
import json

import pytest

from mygeeky import storesync as ss


class MemStore:
    ident = "mem"

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.reads = 0
        self.writes: list[str] = []

    def list(self):
        return {n: hashlib.sha256(b).hexdigest() for n, b in self.files.items()}

    def read(self, name):
        self.reads += 1
        return self.files.get(name)

    def write(self, name, data):
        self.files[name] = data
        self.writes.append(name)
        return hashlib.sha256(data).hexdigest()

    def delete(self, name):
        self.files.pop(name, None)


def line(at, what="open"):
    return json.dumps({"at": at, "what": what})


@pytest.fixture
def two(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "config.synced.json").write_text('{"keywords": ["genomics"]}')
    (a / "cv_text.txt").write_text("my cv")
    (a / "usage.jsonl").write_text("\n".join([line("2026-09-30T10:00:00"), line("2026-10-01T10:00:00")]) + "\n")
    (a / "model.pkl").write_bytes(b"never synced")
    (a / "github_cache.sqlite").write_bytes(b"never synced")

    def use(device):                         # each device remembers its own last sync
        monkeypatch.setattr(ss, "STATE_FILE", tmp_path / f"state-{device}.json")
    return a, b, use


def test_two_devices_end_up_with_the_same_data_and_only_changes_move(two):
    a, b, use = two
    store = MemStore()
    use("a")
    r = ss.sync(store, a)
    assert set(store.files) == {"mygeeky.json", "config.synced.json", "cv_text.txt", "usage.jsonl"}
    assert store.files["cv_text.txt"] == b"my cv" and sorted(r["up"]) == ["config.synced.json", "cv_text.txt",
                                                                          "usage.jsonl"]
    use("b")
    r = ss.sync(store, b)
    assert (b / "cv_text.txt").read_text() == "my cv" and (b / "config.synced.json").read_text() == '{"keywords": ["genomics"]}'
    assert (b / "usage.jsonl").read_text() == (a / "usage.jsonl").read_text()
    assert r["up"] == []                     # B had nothing of its own: it writes nothing

    with (b / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-26T09:00:00", "click") + "\n")
    (b / "cv_text.txt").write_text("my cv, longer")
    store.writes.clear()
    ss.sync(store, b)
    assert sorted(store.writes) == ["cv_text.txt", "usage.jsonl"]

    use("a")
    store.reads = 0
    r = ss.sync(store, a)
    assert sorted(r["down"]) == ["cv_text.txt", "usage.jsonl"] and store.reads == 3   # mygeeky.json + the two
    assert (a / "cv_text.txt").read_text() == "my cv, longer"
    assert (a / "usage.jsonl").read_text().splitlines()[-1] == line("2026-10-26T09:00:00", "click")
    store.writes.clear()
    store.reads = 0
    assert ss.sync(store, a) == {"down": [], "up": []}
    assert store.reads == 1 and store.writes == []           # nothing changed: only mygeeky.json is looked at


def test_when_both_changed_theirs_wins_and_logs_keep_both_sides(two):
    a, b, use = two
    store = MemStore()
    use("a")
    ss.sync(store, a)
    use("b")
    ss.sync(store, b)
    (b / "cv_text.txt").write_text("from b")
    with (b / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-02T00:00:00", "b") + "\n")
    ss.sync(store, b)
    use("a")
    (a / "cv_text.txt").write_text("from a")
    with (a / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-03T00:00:00", "a") + "\n")
    ss.sync(store, a)
    assert (a / "cv_text.txt").read_text() == "from b"
    whats = [json.loads(x)["what"] for x in (a / "usage.jsonl").read_text().splitlines()]
    assert whats == ["open", "open", "b", "a"]                # in time order, nothing lost
    assert store.files["usage.jsonl"] == (a / "usage.jsonl").read_bytes()   # and the merged log went back up


def test_a_log_trimmed_on_one_device_stays_trimmed(two):
    a, b, use = two
    store = MemStore()
    use("a")
    ss.sync(store, a)
    use("b")
    ss.sync(store, b)
    (b / "usage.jsonl").write_text(line("2026-10-01T10:00:00") + "\n")      # B keeps only the newest line
    ss.sync(store, b)
    use("a")
    ss.sync(store, a)
    assert (a / "usage.jsonl").read_text() == line("2026-10-01T10:00:00") + "\n"


def test_what_is_synced_leaves_out_caches_tokens_and_this_computers_config(tmp_path):
    for name in ("config.json", "config.synced.json", "model.pkl", "github_cache.sqlite", "x.token", ".hidden",
                 "news.json", "usage.jsonl", "scholar_profile.json", "README.md", "mygeeky.json"):
        (tmp_path / name).write_text("x")
    assert ss.synced_names(tmp_path) == ["config.synced.json", "scholar_profile.json", "usage.jsonl"]


def test_a_store_another_device_moved_away_from_says_where_the_data_went(two):
    a, b, use = two
    store = MemStore()
    use("a")
    ss.sync(store, a)
    ss.mark_moved(store, "github:ada/mygeeky-data")
    use("b")
    with pytest.raises(ss.Moved) as e:
        ss.sync(store, b)
    assert "ada/mygeeky-data" in str(e.value) and e.value.to == "github:ada/mygeeky-data"
    assert not list(b.iterdir())                              # nothing taken from a place that's no longer used
    ss.claim(store)                                           # chosen again: it's the place again
    assert ss.moved_to(store.files["mygeeky.json"]) is None and ss.sync(store, b)["down"]


def test_the_encrypted_copies_037_left_are_replaced_by_plain_files(two):
    a, _, use = two
    store = MemStore()
    store.files = {"cv_text.txt.mgk": b"MGK1...", "usage.2026-10.aaaaaaaa.jsonl.mgk": b"MGK1...",
                   "mygeeky.json": b'{"format": 2, "key": "0123456789abcdef"}'}
    use("a")
    ss.sync(store, a)
    assert not any(n.endswith(".mgk") for n in store.files) and store.files["cv_text.txt"] == b"my cv"


# ---- Google Drive, faked at the HTTP level
class FakeDrive:
    def __init__(self):
        self.files: dict[str, dict] = {}
        self.calls: list[tuple[str, str]] = []
        self.n = 0

    def request(self, method, url, headers=None, params=None, data=None, timeout=None):
        assert headers["Authorization"] == "Bearer tok" and timeout
        self.calls.append((method, url.split("/drive/v3/")[-1]))
        params = params or {}

        class R:
            def __init__(self, code, body=b"", js=None):
                self.status_code, self.content, self._js, self.text = code, body, js, ""

            def json(self):
                return self._js

        if method == "GET" and url.endswith("/files"):
            assert params["spaces"] == "appDataFolder"
            return R(200, js={"files": [{"id": i, "name": f["name"], "md5Checksum": hashlib.md5(f["data"]).hexdigest(),
                                         "modifiedTime": "2026"} for i, f in list(self.files.items())]})
        if method == "GET":
            return R(200, self.files[url.rsplit("/", 1)[1]]["data"])
        if method == "POST":
            boundary = headers["Content-Type"].split("boundary=")[1].encode()
            parts = data.split(b"--" + boundary)
            meta = json.loads(parts[1].split(b"\r\n\r\n", 1)[1].strip())
            assert meta["parents"] == ["appDataFolder"]
            body = parts[2].split(b"\r\n\r\n", 1)[1][:-2]
            self.n += 1
            fid = f"id{self.n}"
            self.files[fid] = {"name": meta["name"], "data": body}
            return R(200, js={"id": fid, "md5Checksum": hashlib.md5(body).hexdigest()})
        if method == "PATCH":
            fid = url.rsplit("/", 1)[1]
            self.files[fid]["data"] = data
            return R(200, js={"id": fid, "md5Checksum": hashlib.md5(data).hexdigest()})
        if method == "DELETE":
            del self.files[url.rsplit("/", 1)[1]]
            return R(204)
        raise AssertionError(method)


def test_drive_store_keeps_everything_in_the_hidden_app_folder(two):
    a, b, use = two
    drive = FakeDrive()
    use("a")
    ss.sync(ss.DriveStore(lambda fresh: "tok", drive), a)
    assert sorted(f["name"] for f in drive.files.values()) == ["config.synced.json", "cv_text.txt", "mygeeky.json",
                                                              "usage.jsonl"]
    use("b")
    ss.sync(ss.DriveStore(lambda fresh: "tok", drive), b)
    assert (b / "cv_text.txt").read_text() == "my cv"
    use("a")
    (a / "cv_text.txt").write_text("edited")
    drive.calls.clear()
    ss.sync(ss.DriveStore(lambda fresh: "tok", drive), a)
    assert [c[0] for c in drive.calls] == ["GET", "GET", "PATCH"]     # list, mygeeky.json, the one changed file


def test_what_never_syncs_never_comes_down_either(two):
    a, b, use = two
    store = MemStore()
    store.files = {"model.pkl": b"pickled code", "github_cache.sqlite": b"x", "x.token": b"x", "cv_text.txt": b"cv"}
    use("b")
    assert ss.sync(store, b)["down"] == ["cv_text.txt"] and sorted(p.name for p in b.iterdir()) == ["cv_text.txt"]


def test_a_retry_after_google_refused_the_token_keeps_the_upload_intact(two):
    a, _, use = two
    drive = FakeDrive()
    tokens = iter(["old", "tok", "tok", "tok", "tok", "tok", "tok", "tok"])
    real = drive.request

    def request(method, url, headers=None, **kw):
        if headers["Authorization"] == "Bearer old":
            class R:
                status_code, text = 401, ""
            return R()
        return real(method, url, headers=headers, **kw)
    drive.request = request
    use("a")
    ss.sync(ss.DriveStore(lambda fresh: next(tokens), drive), a)
    assert sorted(f["name"] for f in drive.files.values())[0] == "config.synced.json"


@pytest.mark.skipif(not __import__("phone").node_ok(), reason="needs Node 22.6+")
def test_the_phone_reads_what_the_computer_saved_and_the_computer_takes_what_the_phone_adds(two):
    import phone
    a, _, use = two
    store = MemStore()
    use("a")
    ss.sync(store, a)
    files = {n: v.decode() for n, v in store.files.items()}
    said = phone.run("""
import { openStore } from './lib/data-store.ts';
const files: Record<string, string> = { ...INPUT.files };
const store = { label: 'mem', list: async () => Object.fromEntries(Object.keys(files).map((n) => [n, String(files[n].length)])),
  read: async (n: string) => files[n] ?? null, write: async (n: string, d: string) => { files[n] = d; } };
const opened = await openStore(store);
const cfg = await opened.read('config.synced.json');
const usage = await opened.read('usage.jsonl');
await opened.append('usage.jsonl', [INPUT.line]);
files['mygeeky.json'] = JSON.stringify({ format: 3, moved_to: 'github:ada/data' });
let moved = '';
try { await openStore(store); } catch (e) { moved = (e as Error).message; }
out({ cfg, usage, moved, files });
""", {"files": files, "line": line("2026-10-27T08:00:00", "phone")}, name="store")
    assert said["cfg"] == '{"keywords": ["genomics"]}' and "ada/data" in said["moved"]
    assert said["usage"] == (a / "usage.jsonl").read_text()
    store.files = {n: v.encode() for n, v in said["files"].items()}
    store.files["mygeeky.json"] = ss.format_doc()
    r = ss.sync(store, a)
    assert "usage.jsonl" in r["down"] and (a / "usage.jsonl").read_text().splitlines()[-1] == line("2026-10-27T08:00:00", "phone")
