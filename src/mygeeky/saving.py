"""Where your data is saved, and switching it: Google Drive (recommended: one sign-in, nothing to renew) or a private
GitHub repo -- one or the other, never both. Either way it's encrypted on your devices first (datalock.py) and synced
by storesync.py. Older myGeeKy kept a plain git clone of the repo (sync.py); that keeps working until `lock_github`
moves it over, and a computer that finds its repo already locked by another one follows by itself.
"""

from __future__ import annotations

from typing import Any

from . import datalock as dl
from . import storesync as ss
from .config import MyGeekyConfig, load_config, save_config


def where(cfg: MyGeekyConfig) -> str:
    """"drive", "github" (locked), "github-plain" (an older plain repo) or "" (only on this computer)."""
    if cfg.sync_store == "drive":
        return "drive"
    if cfg.sync_repo:
        return "github" if cfg.sync_locked else "github-plain"
    return ""


def label(cfg: MyGeekyConfig) -> str:
    w = where(cfg)
    return {"drive": "Google Drive", "github": f"GitHub · {cfg.sync_repo}",
            "github-plain": f"GitHub · {cfg.sync_repo} (not encrypted yet)"}.get(w, "")


def store_for(cfg: MyGeekyConfig) -> ss.Store:
    if where(cfg) == "drive":
        from . import google_login
        return ss.DriveStore(lambda fresh: google_login.access_token(fresh))
    return ss.GitStore(cfg.sync_repo)


def ready(cfg: MyGeekyConfig) -> bool:
    """Set up here: signed in to Google, or git present for a locked repo (a plain one: sync.py decides)."""
    w = where(cfg)
    if w == "drive":
        from . import google_login
        return google_login.signed_in()
    if w == "github":
        from . import sync
        return sync.git_exe() is not None
    return False


def _key_for(store: ss.Store) -> bytes:
    """This device's key, made now if the storage is new; NeedsKey if the storage was locked with one we lack."""
    store.start()
    names = store.list()
    kid = dl.format_key_id(store.read(dl.FORMAT_FILE)) if dl.FORMAT_FILE in names else None
    key = ss.get_key()
    if kid is None:
        return key or ss.ensure_key()
    if key is None or dl.key_id(key) != kid:
        raise ss.NeedsKey(kid)
    return key


def _claim(store: ss.Store, key: bytes) -> None:
    """Choosing a storage another device once moved away from: it's the place again (its "moved" mark goes)."""
    store.start()
    names = store.list()
    if dl.FORMAT_FILE in names and dl.moved_to(store.read(dl.FORMAT_FILE)):
        store.write(dl.FORMAT_FILE, dl.format_doc(key))
        store.finish()


def sync_now(cfg: MyGeekyConfig | None = None) -> dict[str, Any]:
    """One sync with the locked storage: {"down": [...], "up": [...], "unreadable": n}."""
    from . import sync
    cfg = cfg or load_config()
    key = ss.get_key()
    if key is None:
        raise ss.NeedsKey("")
    result = ss.sync(store_for(cfg), key, ss.device_id(), before_upload=sync.export_config)
    if "config.synced.json" in result["down"]:
        sync.import_config()
    sync._apply_admin_log()
    return result


def _push_plain() -> None:
    """Bring an older plain clone up to date one last time before the data moves (it's retired once the new place
    works; its history is kept beside the data folder)."""
    from . import sync
    if sync.is_initialized():
        try:
            sync.push()
        except sync.SyncError:
            pass                              # the files here are what counts; they go to the new place next


def use_drive() -> dict[str, Any]:
    """After "Sign in with Google": keep the data in Drive from now on (moved from GitHub if it was there)."""
    from . import google_login
    cfg = load_config()
    before = where(cfg)
    if before == "github":
        sync_now(cfg)                        # the latest from the repo first
    elif before == "github-plain":
        _push_plain()
    store = ss.DriveStore(lambda fresh: google_login.access_token(fresh))
    key = _key_for(store)                    # NeedsKey here leaves everything as it was
    _claim(store, key)
    if before == "github-plain":
        ss.retire_plain_clone()
    cfg = load_config()
    old_repo = cfg.sync_repo
    old = (cfg.sync_store, cfg.sync_repo, cfg.sync_locked)
    cfg.sync_store, cfg.sync_repo, cfg.sync_locked = "drive", "", False
    save_config(cfg)
    try:
        from . import sync
        result = ss.sync(store, key, ss.device_id(), before_upload=sync.export_config)
        if "config.synced.json" in result["down"]:
            sync.import_config()
            cfg = load_config()
            if cfg.sync_store != "drive":      # what came down was another device's older settings: this choice wins
                cfg.sync_store, cfg.sync_repo, cfg.sync_locked = "drive", "", False
                save_config(cfg)
    except Exception:
        cfg = load_config()
        cfg.sync_store, cfg.sync_repo, cfg.sync_locked = old
        save_config(cfg)
        raise
    if before == "github":
        try:
            ss.mark_moved(ss.GitStore(old_repo), key, "drive")
        except ss.StoreError:
            pass                              # the repo just keeps what it had
    moved = {"github": "Moved from GitHub. ", "github-plain": "Moved from GitHub. "}.get(before, "")
    return {"ok": True, "message": f"{moved}Your data is saved in Google Drive, encrypted.", **result}


def use_github(repo: str) -> dict[str, Any]:
    """Keep the data in the private GitHub repo `repo`, encrypted (an older plain repo with data stays plain until
    "Encrypt it"). Moves it from Google Drive if it was there."""
    from . import sync
    repo = repo.strip()
    if "/" not in repo:
        raise ss.StoreError("Give the repo as owner/name, e.g. octocat/mygeeky-data.")
    if sync.public_on_github(repo):
        raise ss.StoreError(f"https://github.com/{repo} is PUBLIC. myGeeKy only saves to a private repo: make it "
                            "private (its Settings → Danger Zone → Change visibility) or pick another name.")
    sync._require_git()
    cfg = load_config()
    before = where(cfg)
    if before == "drive":
        sync_now(cfg)
    elif before == "github-plain":
        _push_plain()
    sync._interactive = True                  # the user is here: Git may ask them to sign in to GitHub
    try:
        if not sync._repo_exists(repo):
            sync._create_private_repo(repo)
        elif sync._repo_is_private(repo) is False:
            raise ss.StoreError(f"https://github.com/{repo} is PUBLIC. myGeeKy only saves to a private repo.")
        kind = ss.remote_kind(repo)
        if kind == "plain":                   # an older myGeeKy's repo, with your data in it: join it as it is
            message = sync.init(repo)
            cfg = load_config()
            cfg.sync_repo, cfg.sync_store, cfg.sync_locked = repo, "", False
            save_config(cfg)
            return {"ok": True, "message": message + "\nIt isn't encrypted yet: Settings → Accounts → Encrypt it."}
        store = ss.GitStore(repo)
        key = _key_for(store)
        _claim(store, key)
        if before == "github-plain":
            ss.retire_plain_clone()           # only now: the new place works
        cfg = load_config()
        cfg.sync_repo, cfg.sync_store, cfg.sync_locked = repo, "", True
        save_config(cfg)
        result = ss.sync(store, key, ss.device_id(), before_upload=sync.export_config)
        if "config.synced.json" in result["down"]:
            sync.import_config()
            cfg = load_config()
            cfg.sync_repo, cfg.sync_store, cfg.sync_locked = repo, "", True
            save_config(cfg)
    finally:
        sync._interactive = False
    if before == "drive":
        from . import google_login
        try:
            ss.mark_moved(ss.DriveStore(lambda fresh: google_login.access_token(fresh)), key, f"github:{repo}")
        except (ss.StoreError, google_login.GoogleLoginError):
            pass
    moved = "Moved from Google Drive. " if before == "drive" else ""
    return {"ok": True, "message": f"{moved}Your data is saved in {repo}, encrypted.", **result}


def lock_github() -> dict[str, Any]:
    """Encrypt an older plain repo: one last plain sync, then the repo starts over with only encrypted files (its old,
    readable history is dropped from GitHub), and this data folder stops being a git clone."""
    from . import sync
    cfg = load_config()
    if where(cfg) != "github-plain":
        raise ss.StoreError("There's no unencrypted GitHub repo to encrypt.")
    sync._require_git()
    try:
        sync.push()
    except sync.SyncError as exc:
        raise ss.StoreError(f"Couldn't bring the repo up to date first: {exc}") from None
    key = ss.ensure_key()
    cfg.sync_locked = True
    save_config(cfg)
    try:
        result = ss.sync(ss.GitStore(cfg.sync_repo, fresh=True), key, ss.device_id(), before_upload=sync.export_config)
    except Exception:
        cfg = load_config()
        cfg.sync_locked = False
        save_config(cfg)
        raise
    ss.retire_plain_clone()
    return {"ok": True, "message": f"{cfg.sync_repo} now holds only encrypted files.", **result}


def follow_if_locked(cfg: MyGeekyConfig) -> bool:
    """A plain clone whose repo another computer has since encrypted: stop using the clone and sync locked. True if
    this computer switched (it needs the key: NeedsKey says so)."""
    from . import sync
    if where(cfg) != "github-plain" or not sync.is_initialized():
        return False
    sync._git("fetch", "-q", "origin", check=False)
    if sync._git("cat-file", "-e", f"origin/main:{dl.FORMAT_FILE}", check=False).returncode != 0:
        return False
    ss.retire_plain_clone()
    cfg.sync_locked = True
    save_config(cfg)
    return True


def stop() -> None:
    """Keep the data on this computer only (nothing is deleted anywhere)."""
    from . import google_login
    cfg = load_config()
    if where(cfg) == "github-plain":
        ss.retire_plain_clone()
    if cfg.sync_store == "drive":
        google_login.sign_out()
    cfg.sync_store, cfg.sync_repo, cfg.sync_locked = "", "", False
    save_config(cfg)
    ss.forget_state()


def recovery_code() -> str | None:
    key = ss.get_key()
    return dl.recovery_code(key) if key else None


def enter_code(code: str) -> dict[str, Any]:
    """The recovery code typed on this computer: keep its key, then sync."""
    key = dl.key_from_code(code)
    if key is None:
        raise ss.StoreError("That code isn't right: check each group of four (the last letters catch typos).")
    previous = ss.get_key()
    ss.set_key(key)
    cfg = load_config()
    if where(cfg) in ("drive", "github"):
        try:
            return {"ok": True, **sync_now(cfg)}
        except ss.NeedsKey:
            ss.set_key(previous)
            raise ss.StoreError("That's a real recovery code, but not the one your saved data is encrypted with.") \
                from None
    return {"ok": True}
