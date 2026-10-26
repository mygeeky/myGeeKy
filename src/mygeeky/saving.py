"""Where your data is saved, and switching it: Google Drive (recommended: one sign-in, nothing to renew; storesync.py)
or a private GitHub repo (the data folder as a git clone; sync.py) -- one or the other, never both. Both hold the same
plain files. Switching copies the latest over and leaves a "moved" mark (mygeeky.json) in the old place, so a device
still using it is told where the data went.
"""

from __future__ import annotations

from typing import Any

from . import storesync as ss
from .config import DATA_DIR, MyGeekyConfig, load_config, save_config


def where(cfg: MyGeekyConfig) -> str:
    """"drive", "github" or "" (only on this computer)."""
    if cfg.sync_store == "drive":
        return "drive"
    return "github" if cfg.sync_repo else ""


def label(cfg: MyGeekyConfig) -> str:
    return {"drive": "Google Drive", "github": f"GitHub · {cfg.sync_repo}"}.get(where(cfg), "")


def drive_store() -> ss.DriveStore:
    from . import google_login
    return ss.DriveStore(lambda fresh: google_login.access_token(fresh))


def ready(cfg: MyGeekyConfig) -> bool:
    """Set up on this computer: signed in to Google, or the data folder is a clone of the repo."""
    w = where(cfg)
    if w == "drive":
        from . import google_login
        return google_login.signed_in()
    if w == "github":
        from . import sync
        return sync.is_initialized()
    return False


def repo_moved() -> str | None:
    """The repo's "moved" mark, as the last pull brought it: where another device took the data."""
    try:
        return ss.moved_to((DATA_DIR / ss.FORMAT_FILE).read_bytes())
    except OSError:
        return None


def _settings(down: list[str]) -> None:
    """Between a sync's two halves: the settings another device saved are taken in, then this computer's go up."""
    from . import sync
    if "config.synced.json" in down:
        sync.import_config()
    sync.export_config()


def sync_now() -> dict[str, Any]:
    """One sync with Google Drive: {"down": [...], "up": [...]}."""
    from . import sync
    result = ss.sync(drive_store(), before_upload=_settings)
    sync._apply_admin_log()
    return result


def _set(store: str, repo: str) -> tuple[str, str]:
    cfg = load_config()
    old = (cfg.sync_store, cfg.sync_repo)
    cfg.sync_store, cfg.sync_repo = store, repo
    save_config(cfg)
    return old


def _mark_repo(to: str | None) -> None:
    """Write (or take away) the repo's "moved" mark and push it; the files here are what counts if that fails."""
    from . import sync
    path = DATA_DIR / ss.FORMAT_FILE
    if to:
        path.write_bytes(ss.format_doc(to))
    elif path.exists():
        path.unlink()
    else:
        return
    try:
        sync.push()
    except sync.SyncError:
        pass


def use_drive() -> dict[str, Any]:
    """After "Sign in with Google": keep the data in Drive from now on (moved from GitHub if it was there)."""
    from . import sync
    before = where(load_config())
    if before == "github" and sync.is_initialized():
        try:
            sync.pull()                       # the latest from the repo first
        except sync.SyncError:
            pass                              # the files here are what counts; they go to Drive next
    store = drive_store()
    ss.claim(store)
    old = _set("drive", "")
    try:
        result = ss.sync(store, before_upload=_settings)
        _set("drive", "")                     # settings that came down from another device don't undo this choice
    except Exception:
        _set(*old)
        raise
    sync._apply_admin_log()
    moved = ""
    if before == "github" and sync.is_initialized():
        _mark_repo("drive")
        moved = "Moved from GitHub. "
    return {"ok": True, "message": f"{moved}Your data is saved in Google Drive.", **result}


def use_github(repo: str) -> dict[str, Any]:
    """Keep the data in the private GitHub repo `repo` (moved from Google Drive if it was there)."""
    from . import google_login, sync
    repo = repo.strip()
    before = where(load_config())
    if before == "drive":
        try:
            sync_now()                        # the latest from Drive first
        except (ss.StoreError, google_login.GoogleLoginError):
            pass                              # moved away already, or signed out: the files here are what counts
    message = sync.init(repo)
    if repo_moved():
        _mark_repo(None)                      # chosen again after another device moved away: it's the place again
    _set("", repo)
    if before == "drive":
        try:
            ss.mark_moved(drive_store(), f"github:{repo}")
        except (ss.StoreError, google_login.GoogleLoginError):
            pass                              # Drive just keeps what it had
        message = "Moved from Google Drive.\n" + message
    return {"ok": True, "message": message}

