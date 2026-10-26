# Where your data is saved

myGeeKy saves your settings and progress in **one** place you own: a hidden folder in your Google Drive (recommended)
or a private GitHub repo. Never both. Both hold the same plain files, under the same names, so switching copies them
as they are. There is no myGeeKy server.

| | Desktop (Python) | Phone (TypeScript) |
|---|---|---|
| Google Drive: the store and syncing | `src/mygeeky/storesync.py` | `mobile/src/lib/data-store.ts` (`driveStore`) |
| GitHub: the data folder as a git clone (desktop), the contents API (phone) | `src/mygeeky/sync.py` | `githubStore` in `data-store.ts`, `raw` / `appendPlain` in `model-repo.ts` |
| Choosing and switching | `src/mygeeky/saving.py` | `mobile/src/lib/saving.ts` |
| Google's sign-in (`drive.appdata` only) | `src/mygeeky/google_login.py` (browser, loopback + PKCE) | `mobile/src/lib/google-drive-auth.ts` + `mobile/modules/google-drive-auth` (Google Identity Services) |

Tests: `tests/test_storesync.py` (two devices, conflicts, Drive, the phone reading and adding to what the computer
saved), `tests/test_saving.py` (Drive first, a second computer, switching to GitHub and back).

## What's in the storage

    mygeeky.json                 {"format": 3} (+ "moved_to" after a switch: "drive" or "github:owner/name")
    config.synced.json           your settings
    interest_events.jsonl        a log: one line per thing you opened or liked
    ...

- What's synced on a computer: the data folder's top-level files, minus `sync.GITIGNORE` (caches, the pickled model,
  tokens), `config.json` (its copy, `config.synced.json`, travels) and `mygeeky.json`.
- **GitHub:** git does the work. Logs (`*.jsonl`) merge line by line (git's union driver); for any other file changed
  on two computers, the other computer's copy wins (`-X theirs`).
- **Google Drive:** the same rules, kept by `storesync.sync`. A file goes up when it changed here and comes down when it
  changed there; changed on both sides, a log keeps both sides' lines (in time order) and any other file takes Drive's.
  The computer remembers what it last synced (`LOCAL_DIR/drive_sync.json`: each file's Drive `md5Checksum` and the
  fingerprint of what it held), so only changed files move, four at a time.
- **The phone** reads the files and adds what you do on it to the logs (`interest_events.jsonl`, `usage.jsonl`): it
  reads the newest copy, adds its lines, writes it back. Your computers then merge them as above.

## The stores

- **Google Drive:** the `appDataFolder` space, `drive.appdata` scope only (non-sensitive: no user cap, no security
  review). Never ask for another scope. Desktop client: loopback + PKCE, refresh token in the keyring. Phone:
  Google Identity Services' AuthorizationClient (custom URI schemes are no longer allowed for Android clients), a
  1-hour token asked again quietly. Everything goes over HTTPS.
- **GitHub:** a private repo. The computer keeps the data folder as a clone and pushes with the user's own git login;
  the phone uses the contents API with its own single-repo token.

## Switching

"Switch to Google Drive" / "Switch to GitHub" brings in the latest, saves everything in the new place, then writes
`moved_to` in the old place's `mygeeky.json` (on GitHub it's committed and pushed); a device still using the old place
is told where the data went. Choosing a place again takes its mark away. The old place keeps its files until you delete
them. The **Connect your phone** QR code carries where the computer saves (`ds`).

0.37.0 encrypted the files (`*.mgk`); a Drive sync deletes those copies and puts the plain files in their place.
