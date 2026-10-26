# Where your data is saved, and how it's locked

myGeeKy saves your settings and progress in **one** place you own: a hidden folder in your Google Drive (recommended)
or a private GitHub repo. Never both. Either way, every file is encrypted on your device before it leaves, so the
storage holds only unreadable bytes. There is no myGeeKy server.

| | Desktop (Python) | Phone (TypeScript) |
|---|---|---|
| The format: key, sealing, recovery code, names | `src/mygeeky/datalock.py` | `mobile/src/lib/data-lock.ts` |
| The stores (Drive, GitHub) and syncing | `src/mygeeky/storesync.py` | `mobile/src/lib/data-store.ts` |
| Choosing and switching | `src/mygeeky/saving.py` | `mobile/src/lib/saving.ts` |
| Google's sign-in (`drive.appdata` only) | `src/mygeeky/google_login.py` (browser, loopback + PKCE) | `mobile/src/lib/google-drive-auth.ts` + `mobile/modules/google-drive-auth` (Google Identity Services) |
| Older plain repos | `src/mygeeky/sync.py` (the data folder as a git clone) | `appendPlain` / `raw` in `model-repo.ts` |

Tests: `tests/test_datalock.py` (format, phone ↔ desktop), `tests/test_storesync.py` (two devices, conflicts, git,
Drive, the phone reading and adding to what the computer saved).

## The key

32 random bytes, made on the first device; kept in the OS keyring (desktop, service `mygeeky-data-key`) or the
phone's secure store (`mygeeky.data.key`). Other devices get it from:

- the **Connect your phone** QR code (`ds`: where, `dk`: the key, base64url), shown for two minutes when asked;
- the **recovery code**: the key in Crockford base32 plus three check bytes, 56 characters in groups of four. Shown
  once after setup and any time in Settings → Accounts.

Lose every device and the code, and the data can't be read. The key id (`sha256("mygeeky-key-id:" + key)[:16]`)
tells devices whether they hold the right key without revealing it.

## A locked file

    "MGK1" | nonce (12 random bytes) | ChaCha20-Poly1305(key, nonce, raw deflate(plaintext), AAD = "mygeeky-data-v1:" + name)

Compressed first (text shrinks several times), the name in the AAD so a file can't be passed off as another.

## What's in the storage

    mygeeky.json                                   plain: {"format": 2, "key": "<key id>"} (+ "moved_to" after a switch)
    config.synced.json.mgk                         a state file: the latest copy wins
    interest_events.2026-10.d3f1a2b4.jsonl.mgk     a log: one file per month per device

- **State files** (`*.json`, `cv_text.txt`): up when changed here, down when changed there; both changed: theirs wins.
- **Logs** (`*.jsonl`): each device writes only its own month files (`<stem>.<YYYY-MM>.<device>.jsonl`), holding the
  lines no other device's file for that month has. Reading a log is the union of every device's files, in time
  order. So two devices never write the same file at once, and a sync sends only this month's small file.
- The desktop remembers what it last synced (`LOCAL_DIR/storage_sync.json`: each file's revision, fingerprint, and
  the short hashes of other devices' log lines), so only changed files move. Drive gives `md5Checksum`; git gives
  the blob id.
- What's synced on a computer: the data folder's top-level files, minus `sync.GITIGNORE` (caches, the pickled model,
  tokens) and `config.json` (its copy, `config.synced.json`, travels).

## The stores

- **Google Drive:** the `appDataFolder` space, `drive.appdata` scope only (non-sensitive: no user cap, no security
  review). Never ask for another scope. Desktop client: loopback + PKCE, refresh token in the keyring. Phone:
  Google Identity Services' AuthorizationClient (custom URI schemes are no longer allowed for Android clients), a
  1-hour token asked again quietly.
- **GitHub, locked:** the desktop keeps a clone in its local folder (`<data>-local/locked-repo`) holding only locked files and
  pushes with the user's own git login; a refused push means another device saved first: sync again. `.gitattributes`
  marks `*.mgk` binary. The phone uses the contents API with its own single-repo token.
- **GitHub, older plain repo:** `sync.py` as before. **Encrypt it** (desktop, Settings → Accounts) syncs once more,
  then force-pushes a new history holding only locked files (the old readable history is dropped from GitHub), and
  the data folder stops being a clone (its `.git` moves beside it). Other computers notice `mygeeky.json` on their next
  sync and follow (they need the key).

## Switching

"Switch to Google Drive" / "Switch to GitHub" syncs the latest, saves everything in the new place, then writes
`moved_to` in the old place's `mygeeky.json`; a device still using the old place is told where the data went. The
phone copies the locked files over without opening them. The old place keeps its files until you delete them.
