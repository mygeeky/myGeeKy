"""Sync your data folder with your storage, locked (datalock.py): Google Drive's hidden app folder, or a private
GitHub repo. One way of syncing for both, and the same files the phone reads and writes (mobile/src/lib/data-store.ts):

* a state file (config.synced.json, scholar_profile.json...) goes up when it changed here, comes down when it changed
  there, and when both changed, theirs wins (as the git sync's `-X theirs` did);
* a log (*.jsonl) is kept in the storage as one file per month per device; this device writes only its own, with the
  lines no other device's file for that month has, and adds every line it hasn't got from the others.

What was synced last is remembered here (LOCAL_DIR/storage_sync.json: each stored file's revision, the fingerprint
of what it held, and for the other devices' logs the short hashes of their lines), so only files that changed move.

Older myGeeKy kept the data folder itself as a plain git clone (sync.py); that stays for repos not locked yet, and
`lock_github` moves one over.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from . import datalock as dl
from .config import DATA_DIR, LOCAL_DIR, ensure_dirs
from .files import write_text_atomic

STATE_FILE = LOCAL_DIR / "storage_sync.json"
DEVICE_FILE = LOCAL_DIR / "device_id"
LOCKED_CLONE = LOCAL_DIR / "locked-repo"        # this computer only (tests keep LOCAL_DIR apart, conftest.py)
KEY_SERVICE = "mygeeky-data-key"
KEY_USER = "default"
MAX_FILE_MB = 50
# never synced besides sync.GITIGNORE's list: this computer's own config (config.synced.json carries it) and git's files
NOT_SYNCED = ("config.json", "README.md", "*.backup*", "storage_sync.json")


class StoreError(RuntimeError):
    pass


class NeedsKey(StoreError):
    """The storage is locked with a key this device doesn't have: type the recovery code (or scan the QR code)."""

    def __init__(self, kid: str):
        super().__init__("Your saved data is encrypted with a key this computer doesn't have yet. Type your recovery "
                         "code (Settings → Accounts → Saving your data).")
        self.kid = kid


class Moved(StoreError):
    """Another device moved your data to another storage (Switch to ...): this one is left as it was."""

    def __init__(self, to: str):
        place = "Google Drive" if to == "drive" else to.split(":", 1)[-1]
        super().__init__(f"Your data moved to {place} on another device. Switch this computer too: Settings → Accounts.")
        self.to = to


class Retry(StoreError):
    """Another device wrote at the same moment: sync again."""


class Store(Protocol):
    ident: str

    def start(self) -> None: ...
    def list(self) -> dict[str, str]: ...
    def read(self, name: str) -> bytes | None: ...
    def write(self, name: str, data: bytes) -> str: ...
    def finish(self) -> None: ...


# ---- the key (OS keyring) and this device's id
def get_key() -> bytes | None:
    import base64
    try:
        import keyring
        text = keyring.get_password(KEY_SERVICE, KEY_USER)
    except Exception:  # noqa: BLE001 - no keyring backend: no key
        return None
    try:
        key = base64.b64decode(text or "", validate=True)
    except ValueError:
        return None
    return key if len(key) == 32 else None


def set_key(key: bytes | None) -> None:
    import base64

    import keyring
    if key is None:
        try:
            keyring.delete_password(KEY_SERVICE, KEY_USER)
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        keyring.set_password(KEY_SERVICE, KEY_USER, base64.b64encode(key).decode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise StoreError("This computer has no keyring to keep the encryption key in, so your data can't be saved "
                         "encrypted here.") from exc


def ensure_key() -> bytes:
    key = get_key()
    if key is None:
        key = dl.new_key()
        set_key(key)
    return key


def device_id() -> str:
    ensure_dirs()
    try:
        text = DEVICE_FILE.read_text(encoding="ascii").strip()
        if len(text) == 8 and all(c in "0123456789abcdef" for c in text):
            return text
    except OSError:
        pass
    text = dl.new_device_id()
    write_text_atomic(DEVICE_FILE, text)
    return text


# ---- what's synced
def synced_names(folder: Path | None = None) -> list[str]:
    folder = folder or DATA_DIR
    from .sync import GITIGNORE
    patterns = [p.strip().rstrip("/") for p in GITIGNORE.splitlines() if p.strip() and not p.startswith("#")]
    out = []
    for p in sorted(folder.iterdir()) if folder.exists() else []:
        name = p.name
        if (name.startswith(".") or not p.is_file() or not dl.valid_name(name)
                or any(fnmatch.fnmatch(name, pat) for pat in [*patterns, *NOT_SYNCED])
                or p.stat().st_size > MAX_FILE_MB * 1024 * 1024):
            continue
        out.append(name)
    return out


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()[:16]


def _time_of(line: str) -> str:
    try:
        rec = json.loads(line)
    except ValueError:
        return ""
    if isinstance(rec, dict):
        for k in ("at", "timestamp", "time", "date", "ts"):
            if isinstance(rec.get(k), str):
                return rec[k]
    return ""


def _load_state(ident: str) -> dict[str, Any]:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    s = state.get(ident) if isinstance(state, dict) else None
    return s if isinstance(s, dict) and isinstance(s.get("files"), dict) else {"files": {}}


def _save_state(ident: str, s: dict[str, Any]) -> None:
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}
    state[ident] = s
    ensure_dirs()
    write_text_atomic(STATE_FILE, json.dumps(state, separators=(",", ":")))


def forget_state(ident: str | None = None) -> None:
    if ident is None:
        STATE_FILE.unlink(missing_ok=True)
        return
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(state, dict) and state.pop(ident, None) is not None:
        write_text_atomic(STATE_FILE, json.dumps(state, separators=(",", ":")))


# ---- the sync
def sync_once(store: Store, key: bytes, device: str, folder: Path | None = None,
              before_upload: Callable[[], None] | None = None) -> dict[str, Any]:
    """One two-way sync. Returns {"down": [names changed here], "up": [stored names written], "unreadable": n}."""
    folder = folder or DATA_DIR
    store.start()
    remote = store.list()
    fmt = store.read(dl.FORMAT_FILE) if dl.FORMAT_FILE in remote else None
    kid = dl.format_key_id(fmt)
    if kid is not None and kid != dl.key_id(key):
        raise NeedsKey(kid)
    moved = dl.moved_to(fmt)
    if moved:
        raise Moved(moved)
    first_time = kid is None
    s = _load_state(store.ident)
    files: dict[str, dict] = dict(s["files"])
    down: list[str] = []
    up: list[str] = []
    unreadable = 0

    def local_bytes(name: str) -> bytes | None:
        try:
            return (folder / name).read_bytes()
        except OSError:
            return None

    # 1. what changed there comes down
    logs_in: dict[str, list[str]] = {}
    for stored, rev in sorted(remote.items()):
        p = dl.parse_stored(stored)
        if p is None:
            continue
        known = files.get(stored)
        if known and known.get("rev") == rev:
            continue
        data = dl.open_sealed(key, p["name"], store.read(stored) or b"")
        if data is None:
            unreadable += 1
            continue
        entry: dict[str, Any] = {"rev": rev, "fp": dl.fingerprint(data)}
        if p["kind"] == "state":
            here = local_bytes(p["name"])
            if here != data:                  # unchanged here, or changed on both sides: theirs wins
                write_bytes(folder / p["name"], data)
                down.append(p["name"])
        else:
            lines = dl.lines_of(data.decode("utf-8", "replace"))
            logs_in.setdefault(f"{p['stem']}.jsonl", []).extend(lines)
            if p["device"] != device:
                entry["lines"] = [_line_hash(x) for x in lines]
        files[stored] = entry
    for name, lines in logs_in.items():
        if _merge_lines(folder / name, lines):
            down.append(name)

    if before_upload:
        before_upload()                       # e.g. the config, exported after what came down was taken in

    # 2. what changed here goes up
    if first_time:
        store.write(dl.FORMAT_FILE, dl.format_doc(key))
        up.append(dl.FORMAT_FILE)
    others: dict[tuple[str, str], set[str]] = {}
    for stored, entry in files.items():
        p = dl.parse_stored(stored)
        if p and p["kind"] == "log" and p["device"] != device and stored in remote:
            others.setdefault((p["stem"], p["month"]), set()).update(entry.get("lines") or [])
    for name in synced_names(folder):
        data = local_bytes(name)
        if data is None:
            continue
        if not dl.is_log(name):
            stored = name + dl.SUFFIX
            fp = dl.fingerprint(data)
            if files.get(stored, {}).get("fp") == fp and stored in remote:
                continue
            rev = store.write(stored, dl.seal(key, name, data))
            files[stored] = {"rev": rev, "fp": fp}
            up.append(stored)
            continue
        stem = name[:-len(".jsonl")]
        if not dl.valid_name(stem) or "." in stem:
            continue
        for month, lines in dl.by_month(dl.lines_of(data.decode("utf-8", "replace"))).items():
            seen = others.get((stem, month), set())
            mine = [x for x in lines if _line_hash(x) not in seen]
            chunk = dl.log_chunk(stem, month, device)
            stored = chunk + dl.SUFFIX
            if not mine and stored not in remote:
                continue
            body = ("\n".join(mine) + "\n" if mine else "").encode("utf-8")
            fp = dl.fingerprint(body)
            if files.get(stored, {}).get("fp") == fp and stored in remote:
                continue
            rev = store.write(stored, dl.seal(key, chunk, body))
            files[stored] = {"rev": rev, "fp": fp}
            up.append(stored)
    store.finish()
    # forget files the storage no longer has (and wasn't just given)
    files = {k: v for k, v in files.items() if k in remote or k in up}
    _save_state(store.ident, {"files": files, "synced": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    return {"down": down, "up": up, "unreadable": unreadable}


def sync(store: Store, key: bytes, device: str, folder: Path | None = None, attempts: int = 3,
         before_upload: Callable[[], None] | None = None) -> dict[str, Any]:
    for attempt in range(attempts):
        try:
            return sync_once(store, key, device, folder, before_upload)
        except Retry:
            if attempt == attempts - 1:
                raise StoreError("Another device kept saving at the same moment. Sync will try again later.") from None
    raise AssertionError("unreachable")


def write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.sync.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _merge_lines(path: Path, incoming: list[str]) -> bool:
    """Add the lines this log doesn't have yet, then keep it in time order. True if anything was added."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    have = dl.lines_of(text)
    seen = set(have)
    new = []
    for line in incoming:
        if line not in seen:
            seen.add(line)
            new.append(line)
    if not new:
        return False
    merged = sorted(have + new, key=_time_of)             # stable: lines of the same moment keep their order
    write_bytes(path, ("\n".join(merged) + "\n").encode("utf-8"))
    return True


# ---- Google Drive's hidden app folder
class DriveStore:
    API = "https://www.googleapis.com/drive/v3/files"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
    ident = "drive"

    def __init__(self, token: Callable[[bool], str], session: Any = None):
        import requests
        self._token = token
        self.http = session or requests.Session()
        self.ids: dict[str, str] = {}
        self.revs: dict[str, str] = {}

    def _call(self, method: str, url: str, **kw: Any) -> Any:
        for fresh in (False, True):
            headers = {**kw.pop("headers", {}), "Authorization": f"Bearer {self._token(fresh)}"}
            try:
                r = self.http.request(method, url, headers=headers, timeout=60, **kw)
            except Exception as exc:  # noqa: BLE001
                raise StoreError(f"Couldn't reach Google Drive ({type(exc).__name__}). Sync will try again later.") from None
            if r.status_code != 401:
                break
        if r.status_code == 401:
            raise StoreError("Google Drive no longer accepts this computer's sign-in. Sign in with Google again.")
        if r.status_code == 403 and "storageQuota" in r.text:
            raise StoreError("Your Google Drive is full, so your data can't be saved there.")
        if r.status_code >= 400:
            raise StoreError(f"Google Drive answered {r.status_code}. Sync will try again later.")
        return r

    def start(self) -> None:
        self.ids, self.revs = {}, {}

    def list(self) -> dict[str, str]:
        out: dict[str, str] = {}
        page = None
        while True:
            params = {"spaces": "appDataFolder", "pageSize": 1000,
                      "fields": "nextPageToken,files(id,name,md5Checksum,modifiedTime)"}
            if page:
                params["pageToken"] = page
            j = self._call("GET", self.API, params=params).json()
            for f in j.get("files", []):
                name, fid = str(f.get("name", "")), str(f.get("id", ""))
                when = str(f.get("modifiedTime", ""))
                if name and fid and (name not in out or when > out[name]):    # two copies: the newest
                    out[name] = when
                    self.ids[name] = fid
                    self.revs[name] = str(f.get("md5Checksum", "")) or when
            page = j.get("nextPageToken")
            if not page:
                break
        return dict(self.revs)

    def read(self, name: str) -> bytes | None:
        fid = self.ids.get(name)
        if not fid:
            return None
        return self._call("GET", f"{self.API}/{fid}", params={"alt": "media"}).content

    def write(self, name: str, data: bytes) -> str:
        fid = self.ids.get(name)
        if fid:
            r = self._call("PATCH", f"{self.UPLOAD}/{fid}", params={"uploadType": "media", "fields": "id,md5Checksum"},
                           data=data, headers={"Content-Type": "application/octet-stream"})
        else:
            boundary = "mygeeky" + hashlib.sha256(data).hexdigest()[:24]
            meta = json.dumps({"name": name, "parents": ["appDataFolder"]})
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                    f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + data + \
                f"\r\n--{boundary}--".encode()
            r = self._call("POST", self.UPLOAD, params={"uploadType": "multipart", "fields": "id,md5Checksum"},
                           data=body, headers={"Content-Type": f"multipart/related; boundary={boundary}"})
        j = r.json()
        self.ids[name] = str(j.get("id", fid or ""))
        return str(j.get("md5Checksum", "")) or hashlib.md5(data).hexdigest()  # noqa: S324 - Drive's own checksum

    def finish(self) -> None:
        pass

    def delete_all(self) -> int:
        """Remove everything myGeeKy keeps in this Drive (Switch away, Start over). How many files went."""
        self.start()
        names = list(self.list())
        for name in names:
            self._call("DELETE", f"{self.API}/{self.ids[name]}")
        return len(names)


# ---- a private GitHub repo, locked: a clone beside the data folder holds only locked files
def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()  # noqa: S324 - git's own object id


class GitStore:
    def __init__(self, repo: str, clone: Path | None = None, fresh: bool = False, url: str | None = None):
        from . import sync
        self.repo, self.clone, self.fresh = repo, clone or LOCKED_CLONE, fresh
        self.url = url or sync.remote_url(repo)
        self.ident = f"github:{repo.lower()}"
        self.changed = False
        self.old_head = ""

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        from . import sync
        try:
            return sync._git(*args, cwd=self.clone, check=check)
        except sync.SyncError as exc:
            raise StoreError(str(exc)) from None

    def start(self) -> None:
        from . import sync
        try:
            sync._require_git()
        except sync.SyncError as exc:
            raise StoreError(str(exc)) from None
        self.clone.mkdir(parents=True, exist_ok=True)
        if not (self.clone / ".git").exists():
            self.git("init", "-q", "-b", "main")
            self.git("remote", "add", "origin", self.url)
        else:
            self.git("remote", "set-url", "origin", self.url)
        self.git("fetch", "-q", "origin")
        has_main = bool(self.git("rev-parse", "-q", "--verify", "origin/main", check=False).stdout.strip())
        self.old_head = self.git("rev-parse", "origin/main").stdout.strip() if has_main else ""
        if self.fresh:                         # a new history with nothing in it (lock_github)
            self.git("checkout", "-q", "--orphan", "locked-new")
            self.git("rm", "-rqf", "--ignore-unmatch", ".")
            for p in self.clone.iterdir():
                if p.name != ".git":
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
        elif has_main:
            self.git("checkout", "-q", "-B", "main", "origin/main")
            self.git("reset", "-q", "--hard", "origin/main")
            self.git("clean", "-qfd")
        self.changed = False

    def list(self) -> dict[str, str]:
        if self.fresh or not self.git("rev-parse", "-q", "--verify", "HEAD", check=False).stdout.strip():
            return {}
        out = {}
        for line in self.git("ls-tree", "HEAD").stdout.splitlines():
            meta, _, name = line.partition("\t")
            parts = meta.split()
            if len(parts) == 3 and parts[1] == "blob":
                out[name] = parts[2]
        return out

    def read(self, name: str) -> bytes | None:
        try:
            return (self.clone / name).read_bytes()
        except OSError:
            return None

    def write(self, name: str, data: bytes) -> str:
        write_bytes(self.clone / name, data)
        self.changed = True
        return _blob_sha(data)

    def finish(self) -> None:
        if not self.changed:
            return
        attrs = self.clone / ".gitattributes"
        if not attrs.exists():                 # locked files never diff or merge as text
            attrs.write_text("*.mgk binary\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"myGeeKy sync {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        if self.fresh:
            lease = f"--force-with-lease=main:{self.old_head}" if self.old_head else "--force"
            r = self.git("push", "-q", lease, "origin", "HEAD:main", check=False)
        else:
            r = self.git("push", "-q", "origin", "HEAD:main", check=False)
        if r.returncode != 0:
            if "rejected" in r.stderr or "fetch first" in r.stderr or "stale info" in r.stderr:
                raise Retry()
            raise StoreError(f"Couldn't save to GitHub: {(r.stderr or r.stdout).strip()[:300]}")
        if self.fresh:
            self.git("checkout", "-q", "-B", "main")
            self.git("branch", "-q", "-D", "locked-new", check=False)
            self.fresh = False


def remote_kind(repo: str, clone: Path | None = None, url: str | None = None) -> str:
    """"empty", "plain" (an older myGeeKy's repo) or "locked"."""
    store = GitStore(repo, clone, url=url)
    store.start()
    names = store.list()
    if not names:
        return "empty"
    return "locked" if dl.FORMAT_FILE in names else "plain"


def mark_moved(store: Store, key: bytes, to: str) -> None:
    """Tell devices still using `store` that the data now lives elsewhere ("drive" or "github:owner/name")."""
    store.start()
    store.list()
    doc = json.loads(dl.format_doc(key))
    doc["moved_to"] = to
    store.write(dl.FORMAT_FILE, json.dumps(doc, indent=1).encode("utf-8"))
    store.finish()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def retire_plain_clone(folder: Path | None = None) -> Path | None:
    """The data folder stops being a git clone (its history moves beside it, nothing is deleted). Where it went."""
    folder = folder or DATA_DIR
    git_dir = folder / ".git"
    if not git_dir.exists():
        return None
    dest = folder.parent / f"{folder.name}-git-backup-{stamp()}"
    shutil.move(str(git_dir), str(dest))
    return dest
