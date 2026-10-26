"""Saving your data locked (storesync.py): two devices keep the same data through any storage, only changed files
move, each device writes only its own logs, a wrong key is caught, and the GitHub and Google Drive stores work."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

import pytest

from mygeeky import datalock as dl
from mygeeky import storesync as ss

KEY = bytes(range(32))


class MemStore:
    ident = "mem"

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.reads = 0
        self.writes: list[str] = []

    def start(self):
        pass

    def list(self):
        return {n: hashlib.sha256(b).hexdigest() for n, b in self.files.items()}

    def read(self, name):
        self.reads += 1
        return self.files.get(name)

    def write(self, name, data):
        self.files[name] = data
        self.writes.append(name)
        return hashlib.sha256(data).hexdigest()

    def finish(self):
        pass


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
    states = {}

    def use(device):                         # each device remembers its own last sync
        monkeypatch.setattr(ss, "STATE_FILE", tmp_path / f"state-{device}.json")
    return a, b, use, states


def test_two_devices_end_up_with_the_same_data_and_only_changes_move(two):
    a, b, use, _ = two
    store = MemStore()
    use("a")
    r = ss.sync(store, KEY, "aaaaaaaa", a)
    assert set(store.files) == {"mygeeky.json", "config.synced.json.mgk", "cv_text.txt.mgk",
                                "usage.2026-09.aaaaaaaa.jsonl.mgk", "usage.2026-10.aaaaaaaa.jsonl.mgk"}
    assert not any(b"genomics" in v or b"my cv" in v for v in store.files.values())      # nothing readable up there
    assert len(r["up"]) == 5
    use("b")
    r = ss.sync(store, KEY, "bbbbbbbb", b)
    assert (b / "cv_text.txt").read_text() == "my cv" and (b / "config.synced.json").read_text() == '{"keywords": ["genomics"]}'
    assert (b / "usage.jsonl").read_text() == (a / "usage.jsonl").read_text()
    assert r["up"] == []                     # B had nothing of its own: it writes nothing

    # B opens something new and edits the CV; only those go up, only B's own month file
    with (b / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-26T09:00:00", "click") + "\n")
    (b / "cv_text.txt").write_text("my cv, longer")
    store.writes.clear()
    ss.sync(store, KEY, "bbbbbbbb", b)
    assert sorted(store.writes) == ["cv_text.txt.mgk", "usage.2026-10.bbbbbbbb.jsonl.mgk"]
    mine = dl.open_sealed(KEY, "usage.2026-10.bbbbbbbb.jsonl", store.files["usage.2026-10.bbbbbbbb.jsonl.mgk"])
    assert mine.decode().splitlines() == [line("2026-10-26T09:00:00", "click")]   # only what A's file hasn't got

    use("a")
    store.reads = 0
    r = ss.sync(store, KEY, "aaaaaaaa", a)
    assert sorted(r["down"]) == ["cv_text.txt", "usage.jsonl"] and store.reads == 3   # mygeeky.json + the two
    assert (a / "cv_text.txt").read_text() == "my cv, longer"
    assert (a / "usage.jsonl").read_text().splitlines()[-1] == line("2026-10-26T09:00:00", "click")
    store.writes.clear()
    store.reads = 0
    assert ss.sync(store, KEY, "aaaaaaaa", a) == {"down": [], "up": [], "unreadable": 0}
    assert store.reads == 1 and store.writes == []           # nothing changed: only mygeeky.json is looked at


def test_when_both_changed_theirs_wins_and_logs_keep_both_sides(two):
    a, b, use, _ = two
    store = MemStore()
    use("a")
    ss.sync(store, KEY, "aaaaaaaa", a)
    use("b")
    ss.sync(store, KEY, "bbbbbbbb", b)
    (b / "cv_text.txt").write_text("from b")
    with (b / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-02T00:00:00", "b") + "\n")
    ss.sync(store, KEY, "bbbbbbbb", b)
    use("a")
    (a / "cv_text.txt").write_text("from a")
    with (a / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-03T00:00:00", "a") + "\n")
    ss.sync(store, KEY, "aaaaaaaa", a)
    assert (a / "cv_text.txt").read_text() == "from b"
    whats = [json.loads(x)["what"] for x in (a / "usage.jsonl").read_text().splitlines()]
    assert whats == ["open", "open", "b", "a"]                # in time order, nothing lost


def test_a_storage_locked_with_another_key_is_never_overwritten(two):
    a, b, use, _ = two
    store = MemStore()
    use("a")
    ss.sync(store, KEY, "aaaaaaaa", a)
    before = dict(store.files)
    use("b")
    with pytest.raises(ss.NeedsKey) as e:
        ss.sync(store, bytes(32), "bbbbbbbb", b)
    assert e.value.kid == dl.key_id(KEY) and store.files == before and not list(b.iterdir())


def test_what_is_synced_leaves_out_caches_tokens_and_this_computers_config(tmp_path):
    for name in ("config.json", "config.synced.json", "model.pkl", "github_cache.sqlite", "x.token", ".hidden",
                 "news.json", "usage.jsonl", "scholar_profile.json", "README.md"):
        (tmp_path / name).write_text("x")
    assert ss.synced_names(tmp_path) == ["config.synced.json", "scholar_profile.json", "usage.jsonl"]


# ---- a private GitHub repo, here a bare repo on disk
needs_git = pytest.mark.skipif(not shutil.which("git"), reason="needs git")


def _bare(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True, timeout=120)
    return bare


@needs_git
def test_git_store_two_computers_saving_at_once_both_get_through(two, tmp_path):
    a, b, use, _ = two
    url = str(_bare(tmp_path))
    sa = ss.GitStore("me/data", tmp_path / "clone-a", url=url)
    sb = ss.GitStore("me/data", tmp_path / "clone-b", url=url)
    use("a")
    ss.sync(sa, KEY, "aaaaaaaa", a)
    use("b")
    ss.sync(sb, KEY, "bbbbbbbb", b)
    assert (b / "cv_text.txt").read_text() == "my cv"
    # both change something; A saves first, so B's push is refused once and it syncs again
    (a / "cv_text.txt").write_text("a2")
    use("a")
    ss.sync(sa, KEY, "aaaaaaaa", a)
    with (b / "usage.jsonl").open("a") as f:
        f.write(line("2026-10-20T00:00:00", "b") + "\n")
    use("b")
    calls = []
    real = ss.sync_once
    ss_sync_once = lambda *x, **k: (calls.append(1), real(*x, **k))[1]   # noqa: E731
    import mygeeky.storesync as mod
    mod.sync_once = ss_sync_once
    try:
        ss.sync(sb, KEY, "bbbbbbbb", b)
    finally:
        mod.sync_once = real
    assert (b / "cv_text.txt").read_text() == "a2" and len(calls) == 1      # fetched first: no refusal needed
    use("a")
    ss.sync(sa, KEY, "aaaaaaaa", a)
    assert (a / "usage.jsonl").read_text().splitlines()[-1] == line("2026-10-20T00:00:00", "b")
    names = subprocess.run(["git", "ls-tree", "--name-only", "main"], cwd=url, capture_output=True, text=True,
                           timeout=120).stdout.split()
    assert "mygeeky.json" in names and all(n in ("mygeeky.json", ".gitattributes") or n.endswith(".mgk") for n in names)
    assert ss.remote_kind("me/data", tmp_path / "probe", url=url) == "locked"


@needs_git
def test_git_store_a_push_refused_mid_sync_is_retried(two, tmp_path):
    a, b, use, _ = two
    url = str(_bare(tmp_path))
    sa = ss.GitStore("me/data", tmp_path / "clone-a", url=url)
    use("a")
    ss.sync(sa, KEY, "aaaaaaaa", a)
    sb = ss.GitStore("me/data", tmp_path / "clone-b", url=url)
    use("b")
    ss.sync(sb, KEY, "bbbbbbbb", b)
    (b / "cv_text.txt").write_text("b2")
    real_finish = sb.finish
    sneaked = []

    def finish():                           # A pushes between B's fetch and B's push
        if not sneaked:
            sneaked.append(1)
            (a / "cv_text.txt").write_text("a-sneaks-in")
            use("a")
            ss.sync(sa, KEY, "aaaaaaaa", a)
            use("b")
        real_finish()
    sb.finish = finish
    ss.sync(sb, KEY, "bbbbbbbb", b)
    assert (b / "cv_text.txt").read_text() == "a-sneaks-in"   # the retry took A's newer copy (theirs wins)


@needs_git
def test_locking_an_old_plain_repo_leaves_no_plain_history(two, tmp_path):
    a, _, use, _ = two
    url = str(_bare(tmp_path))
    plain = tmp_path / "plain"
    subprocess.run(["git", "clone", "-q", url, str(plain)], check=True, timeout=120, capture_output=True)
    (plain / "cv_text.txt").write_text("my secret cv")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    import os
    for cmd in (["add", "-A"], ["commit", "-qm", "plain"], ["push", "-q", "origin", "HEAD:main"]):
        subprocess.run(["git", *cmd], cwd=plain, check=True, timeout=120, env={**os.environ, **env})
    assert ss.remote_kind("me/data", tmp_path / "probe", url=url) == "plain"
    use("a")
    ss.sync(ss.GitStore("me/data", tmp_path / "clone-a", fresh=True, url=url), KEY, "aaaaaaaa", a)
    log = subprocess.run(["git", "log", "--oneline", "main"], cwd=url, capture_output=True, text=True, timeout=120).stdout
    assert len(log.splitlines()) == 1
    everything = subprocess.run(["git", "log", "-p", "--text", "main"], cwd=url, capture_output=True, timeout=120).stdout
    assert b"my secret cv" not in everything and b"my cv" not in everything
    assert ss.remote_kind("me/data", tmp_path / "probe2", url=url) == "locked"


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
                                         "modifiedTime": "2026"} for i, f in self.files.items()]})
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
    a, b, use, _ = two
    drive = FakeDrive()
    use("a")
    ss.sync(ss.DriveStore(lambda fresh: "tok", drive), KEY, "aaaaaaaa", a)
    assert sorted(f["name"] for f in drive.files.values())[0] == "config.synced.json.mgk"
    use("b")
    ss.sync(ss.DriveStore(lambda fresh: "tok", drive), KEY, "bbbbbbbb", b)
    assert (b / "cv_text.txt").read_text() == "my cv"
    use("a")
    (a / "cv_text.txt").write_text("edited")
    drive.calls.clear()
    ss.sync(ss.DriveStore(lambda fresh: "tok", drive), KEY, "aaaaaaaa", a)
    assert [c[0] for c in drive.calls] == ["GET", "GET", "PATCH"]     # list, mygeeky.json, the one changed file
    n = len(drive.files)
    assert ss.DriveStore(lambda fresh: "tok", drive).delete_all() == n and drive.files == {}


def test_a_store_another_device_moved_away_from_says_where_the_data_went(two):
    a, b, use, _ = two
    store = MemStore()
    use("a")
    ss.sync(store, KEY, "aaaaaaaa", a)
    ss.mark_moved(store, KEY, "github:ada/mygeeky-data")
    use("b")
    with pytest.raises(ss.Moved) as e:
        ss.sync(store, KEY, "bbbbbbbb", b)
    assert "ada/mygeeky-data" in str(e.value) and e.value.to == "github:ada/mygeeky-data"


@pytest.mark.skipif(not __import__("phone").node_ok(), reason="needs Node 22.6+")
def test_the_phone_reads_what_the_computer_saved_and_the_computer_takes_what_the_phone_adds(two):
    import base64

    import phone
    a, b, use, _ = two
    store = MemStore()
    use("a")
    ss.sync(store, KEY, "aaaaaaaa", a)
    files = {n: base64.b64encode(v).decode() for n, v in store.files.items()}
    said = phone.run("""
import { openLocked } from './lib/data-store.ts';
import { b64, unb64 } from './lib/signal-crypto.ts';
const files: Record<string, Uint8Array> = Object.fromEntries(Object.entries(INPUT.files).map(([n, v]) => [n, unb64(v as string)!]));
const store = { label: 'mem', list: async () => Object.fromEntries(Object.keys(files).map((n) => [n, 'r'])),
  read: async (n: string) => files[n] ?? null, write: async (n: string, d: Uint8Array) => { files[n] = d; } };
const key = Uint8Array.from(INPUT.key);
const locked = await openLocked(store, key);
const cfg = await locked.read('config.synced.json');
const usage = await locked.read('usage.jsonl');
await locked.append('usage.jsonl', [INPUT.line]);
let wrong = '';
try { await openLocked(store, new Uint8Array(32)); } catch (e) { wrong = (e as Error).constructor.name; }
out({ cfg, usage, wrong, files: Object.fromEntries(Object.entries(files).map(([n, v]) => [n, b64(v)])) });
""", {"files": files, "key": list(KEY), "line": line("2026-10-27T08:00:00", "phone")}, name="store")
    assert said["cfg"] == '{"keywords": ["genomics"]}' and said["wrong"] == "NeedsKey"
    assert said["usage"] == (a / "usage.jsonl").read_text()
    store.files = {n: base64.b64decode(v) for n, v in said["files"].items()}
    phone_files = [n for n in store.files if n.startswith("usage.2026-10.") and "aaaaaaaa" not in n]
    assert len(phone_files) == 1                                   # the phone wrote only its own month file
    r = ss.sync(store, KEY, "aaaaaaaa", a)
    assert "usage.jsonl" in r["down"] and (a / "usage.jsonl").read_text().splitlines()[-1] == line("2026-10-27T08:00:00", "phone")
