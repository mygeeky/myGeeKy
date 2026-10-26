"""Sync your data folder with Google Drive's hidden app folder (`drive.appdata`): the same files, under the same names,
that a GitHub data repo holds (sync.py), so switching between the two copies the files as they are, and the phone reads
both alike (mobile/src/lib/data-store.ts).

* a file goes up when it changed here, and comes down when it changed there;
* changed on both sides: a log (*.jsonl) keeps both sides' lines (as git's union merge does), any other file takes
  theirs (as the git sync's `-X theirs` does).

What was synced last is remembered here (LOCAL_DIR/drive_sync.json: each file's Drive checksum and the fingerprint of
what it held), so only files that changed move, a few at a time.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from .config import DATA_DIR, LOCAL_DIR, ensure_dirs
from .files import write_text_atomic

STATE_FILE = LOCAL_DIR / "drive_sync.json"
FORMAT_FILE = "mygeeky.json"            # {"format": 3}, plus "moved_to" once another device switched away
MAX_FILE_MB = 50
WORKERS = 4                             # files moved at the same time
# never synced besides sync.GITIGNORE's list: this computer's own config (config.synced.json carries it) and git's files
NOT_SYNCED = ("config.json", "README.md", "*.backup*", FORMAT_FILE)
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
_MOVED = re.compile(r"^(drive|github:[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100})$")


class StoreError(RuntimeError):
    pass


class Moved(StoreError):
    """Another device moved your data to another storage (Switch to ...): this one is left as it was."""

    def __init__(self, to: str):
        place = "Google Drive" if to == "drive" else to.split(":", 1)[-1]
        super().__init__(f"Your data moved to {place} on another device. Switch this computer too: Settings → Accounts.")
        self.to = to


class Store(Protocol):
    ident: str

    def list(self) -> dict[str, str]: ...
    def read(self, name: str) -> bytes | None: ...
    def write(self, name: str, data: bytes) -> str: ...
    def delete(self, name: str) -> None: ...


# ---- the mark a storage carries
def format_doc(moved: str | None = None) -> bytes:
    doc: dict[str, Any] = {"format": 3}
    if moved:
        doc["moved_to"] = moved
    return json.dumps(doc, indent=1).encode("utf-8")


def moved_to(data: bytes | str | None) -> str | None:
    """Where another device moved the data ("drive" or "github:owner/name"), from a mygeeky.json; None if it didn't."""
    try:
        m = json.loads(data or "null").get("moved_to")
    except (ValueError, AttributeError):
        return None
    return m if isinstance(m, str) and _MOVED.match(m) else None


# ---- what's synced
def synced(name: str) -> bool:
    """A file that travels: a plain name, not a cache, the pickled model, a token or this computer's own config
    (sync.GITIGNORE, NOT_SYNCED) -- the same rule for what goes up and what may come down."""
    from .sync import GITIGNORE
    patterns = [p.strip().rstrip("/") for p in GITIGNORE.splitlines() if p.strip() and not p.startswith("#")]
    return bool(_NAME.match(name)) and not any(fnmatch.fnmatch(name, pat) for pat in [*patterns, *NOT_SYNCED])


def synced_names(folder: Path | None = None) -> list[str]:
    folder = folder or DATA_DIR
    found = sorted(folder.iterdir()) if folder.exists() else []
    return [p.name for p in found if p.is_file() and synced(p.name) and p.stat().st_size <= MAX_FILE_MB * 1024 * 1024]


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:32]


def _load_state() -> dict[str, dict]:
    try:
        files = json.loads(STATE_FILE.read_text(encoding="utf-8")).get("files")
    except (OSError, ValueError, AttributeError):
        return {}
    return files if isinstance(files, dict) else {}


def _save_state(files: dict[str, dict]) -> None:
    ensure_dirs()
    write_text_atomic(STATE_FILE, json.dumps(
        {"files": files, "synced": datetime.now(timezone.utc).isoformat(timespec="seconds")}, separators=(",", ":")))


# ---- the sync
def sync(store: Store, folder: Path | None = None,
         before_upload: Callable[[list[str]], None] | None = None) -> dict[str, Any]:
    """One two-way sync. Returns {"down": [names changed here], "up": [names written there]}. `before_upload` gets
    what came down, between the two halves (to take in a config that came down, then export this one)."""
    folder = folder or DATA_DIR
    remote = store.list()
    if FORMAT_FILE in remote:
        moved = moved_to(store.read(FORMAT_FILE))
        if moved:
            raise Moved(moved)
    files = _load_state()
    down: list[str] = []

    def local(name: str) -> bytes | None:
        try:
            return (folder / name).read_bytes()
        except OSError:
            return None

    # 1. what changed there comes down
    changed = [n for n, rev in sorted(remote.items()) if synced(n) and files.get(n, {}).get("rev") != rev]
    with ThreadPoolExecutor(WORKERS) as pool:
        got = dict(zip(changed, pool.map(store.read, changed)))
    for name in changed:
        data = got[name]
        if data is None:
            continue
        here = local(name)
        known = files.get(name, {}).get("fp")
        if here != data:
            changed_here = here is not None and fingerprint(here) != known
            if name.endswith(".jsonl") and changed_here:         # both sides added lines: keep them all
                _write(folder / name, _union(data, here))
            else:
                _write(folder / name, data)
            down.append(name)
        files[name] = {"rev": remote[name], "fp": fingerprint(data)}

    if before_upload:
        before_upload(down)

    # 2. what changed here goes up
    todo = []
    for name in synced_names(folder):
        data = local(name)
        if data is not None and not (name in remote and files.get(name, {}).get("fp") == fingerprint(data)):
            todo.append((name, data))
    with ThreadPoolExecutor(WORKERS) as pool:
        revs = list(pool.map(lambda item: store.write(*item), todo))
    up = []
    for (name, data), rev in zip(todo, revs):
        files[name] = {"rev": rev, "fp": fingerprint(data)}
        up.append(name)
    if FORMAT_FILE not in remote:
        store.write(FORMAT_FILE, format_doc())
    for name in remote:
        if name.endswith(".mgk"):             # 0.37.0's encrypted copies: the plain files above replace them
            store.delete(name)
    _save_state({k: v for k, v in files.items() if k in remote or k in up})
    return {"down": down, "up": up}


def _write(path: Path, data: bytes) -> None:
    import os
    import threading
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.sync.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


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


def _union(theirs: bytes, mine: bytes) -> bytes:
    """Both sides' lines, each once, in time order (lines of the same moment keep their order)."""
    lines: list[str] = []
    seen: set[str] = set()
    for text in (theirs, mine):
        for line in text.decode("utf-8", "replace").splitlines():
            if line.strip() and line not in seen:
                seen.add(line)
                lines.append(line)
    return ("\n".join(sorted(lines, key=_time_of)) + "\n").encode("utf-8")


def claim(store: Store) -> None:
    """Choosing a storage another device once moved away from: it's the place again (its "moved" mark goes)."""
    if FORMAT_FILE in store.list() and moved_to(store.read(FORMAT_FILE)):
        store.write(FORMAT_FILE, format_doc())


def mark_moved(store: Store, to: str) -> None:
    """Tell devices still using `store` that the data now lives elsewhere ("drive" or "github:owner/name")."""
    store.list()
    store.write(FORMAT_FILE, format_doc(to))


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

    def _call(self, method: str, url: str, **kw: Any) -> Any:
        extra = kw.pop("headers", {})
        for fresh in (False, True):
            headers = {**extra, "Authorization": f"Bearer {self._token(fresh)}"}
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
        if r.status_code >= 400 and not (method == "DELETE" and r.status_code == 404):
            raise StoreError(f"Google Drive answered {r.status_code}. Sync will try again later.")
        return r

    def list(self) -> dict[str, str]:
        out: dict[str, str] = {}
        when: dict[str, str] = {}
        self.ids = {}
        page = None
        while True:
            params = {"spaces": "appDataFolder", "pageSize": 1000,
                      "fields": "nextPageToken,files(id,name,md5Checksum,modifiedTime)"}
            if page:
                params["pageToken"] = page
            j = self._call("GET", self.API, params=params).json()
            for f in j.get("files", []):
                name, fid, t = str(f.get("name", "")), str(f.get("id", "")), str(f.get("modifiedTime", ""))
                if name and fid and (name not in when or t > when[name]):    # two copies: the newest
                    when[name] = t
                    self.ids[name] = fid
                    out[name] = str(f.get("md5Checksum", "")) or t
            page = j.get("nextPageToken")
            if not page:
                break
        return out

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

    def delete(self, name: str) -> None:
        fid = self.ids.pop(name, None)
        if fid:
            self._call("DELETE", f"{self.API}/{fid}")
