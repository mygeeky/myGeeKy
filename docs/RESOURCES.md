# myGeeKy's resources: what it takes, and how to make it take less

myGeeKy is a quiet helper; it must never be why a laptop fan spins, a phone battery drains or a disk fills. This is
the measured state, the budgets, and the plan in order of impact. The protocol (how to measure, the tools, the rules)
is in the `mygeeky-resources` skill; the audit is `tools/resource_audit.py`; CI runs it on Windows, macOS and Linux
(`.github/workflows/resources.yml`); `tests/test_resources.py` is its quick version on every test run.

First audit: 2026-10-21, on the maintainer's Linux computer (two computers syncing), the installed desktop 0.30.0,
the code at 0.30.1, and the phone app's current code on the Android emulator (a development build, so its RAM is
several times what a release build uses).

## The numbers

| What | Measured | Budget | Verdict |
|---|---|---|---|
| **Desktop, idle (shown, after startup settles)** | 0.05% CPU | 2% | ✅ |
| Desktop, idle (hidden) | 0.02% CPU | 0.5% | ✅ |
| Desktop, a running panel over 3 min (real use) | 0.39% average CPU, 9% peak, 91% of samples under 1% | | ✅ |
| Desktop RAM (running panel) | 388 MB RSS, 343 MB its own (USS), 21–25 threads | 450 MB | ⚠️ heavy |
| Desktop RAM (throwaway profile, every page visited) | 328 MB → **175 MB** after plan 6 (173 MB with a CV) | 250 MB | ✅ |
| Widgets the panel builds | 1,467 (every page at once, at startup) | | ⚠️ |
| **Leak test: every page × 8 rounds** | widgets +0, Qt objects +0 per round; Python +25 KB/round (mostly the audit itself) | +2 widgets, +512 KB | ✅ no leak |
| Startup (throwaway profile) | a few seconds | 8 s | ✅ |
| **Phone, Live page idle 60 s** | 0 frames drawn, 2.4% CPU (development build) | | ✅ |
| **Phone, Model page idle 30 s** | before: 902 frames (30 fps), 52% janky, 108% CPU · **after plan 1: 0 frames, 2.5% CPU** | ~0 frames | ✅ fixed |
| Phone, app in the background | 0.1% CPU (Android pauses it) | | ✅ |
| Phone RAM (development build) | 503–604 MB PSS, Hermes native heap 260 MB | | ⚠️ measure a release build |
| Phone storage | AsyncStorage 4.1 MB, files 10.6 MB, cache 16.5 MB | | ✅ |
| **Data folder (synced)** | 284 MB: history 171 MB packed + 36 MB loose; working files 83 MB (82 of it stray caches from 0.30.0) | 40 MB working, 300 MB history | ❌ until both computers run 0.30.1 |
| Your real data in that history | under 5 MB in all; grows ~0.5 MB a day | | ✅ |
| Old cache copies in that history | 193 MB (`github_cache.json`, 697 versions) + 14 MB (`github_cache.sqlite`) | | stays (compressed); not worth rewriting history |
| Syncs a day (two computers) | 138 at every 15 min · hourly now (≤ 48 for two computers) | 60 | ✅ fixed in code |
| Tracked but ignored files | `headlines.json` (155 versions), `keywords.json`, `github_achievements.json`, plus four "never synced" files | none | ❌ fixed in code (untracked at the next sync) |
| Live databases (beside the data folder) | 25 MB (`github_cache.sqlite`, capped at 60 MB / 4,000 entries) | 120 MB | ✅ |
| Avatar cache | 1.1–2.2 MB, 513 files, **no limit** | 30 MB | ⚠️ |
| Logs | 20 KB; `logs/weekly.log` never rotated | 20 MB | ⚠️ |
| Beacon | `beacon.json` 165 B; the public repo 13 KB, 88 commits | 64 KB | ✅ |
| Desktop app install (venv) | 562 MB (Qt is most of it) | | — |

## Release 0.31.0 on every system (2026-10-21)

The audit on GitHub's runners (throwaway profile, offline; `.github/workflows/resources.yml`) and the phone's release APK
on the emulator:

| System | Startup | RAM, every page visited | Leak (widgets per round) | Idle CPU shown / hidden |
|---|---|---|---|---|
| Windows | 0.88 s | 176 MB | 0 | 0.31% / 0.39% |
| macOS | 0.65 s | 267 MB (2026-10-21; its own budget, 270 MB: see Budgets) | 0 | 0.39% / 0.27% |
| Linux | 0.46 s | 205 MB | 0 | 0.09% / 0.06% |
| Phone (release APK 1.13.0) | | 161 MB at start (PSS) | | Model page idle: 0 frames, 1.9% |

The only WARN everywhere is the half-second "seen" tick (plan 10: measured, not worth changing). The pack QR code drawn by
the phone decodes into a whole pack with an independent reader.

## Why the data folder is ~280 MB, and how it grows

- 193 MB is 697 old copies of `github_cache.json`, a cache an older myGeeKy (still on the second computer) commits
  every 15 minutes; 14 MB is copies of the newer `github_cache.sqlite`. Your own history (suggestions, settings,
  what you liked, your Model's learning) is under 5 MB in all.
- With 0.30.1 on **both** computers, caches are never committed again; the folder then grows only with your data:
  about **0.5 MB a day (~15 MB a month, ~180 MB a year)**, mostly `suggestions_history.jsonl` rewritten on each
  sync. Plan item 5 below brings that down to a few MB a year.
- The old copies stay in the history, compressed (~170 MB). Removing them means rewriting the history on GitHub and
  re-cloning on every computer; not worth it at this size.

## The plan, in order of impact

1. ✅ **Done 2026-10-21.** **Phone: stop the interest map's endless animation** (`mobile/src/components/interest-map.tsx:62`). A 50 ms
   `setInterval` sets state twice per tick, so the whole SVG re-renders 20–30 times a second for as long as the
   Model page is open: a full CPU core and a warm battery while someone reads. Fix: animate with the native driver
   (`Animated` / Reanimated, no React re-render), or run the motion for a few seconds after the page appears and
   then rest; pause when the screen isn't focused (`useIsFocused` / AppState). Budget: ~0 frames when nothing moves.
2. ✅ **Done 2026-10-21.** **Desktop: the live ticker never stops** (`qt_panel.py:3455`, `SpotlightTicker`): every 4.5 s it builds a new
   card and animates it, even folded, hidden or minimised. Stop it on hide/fold, start it on show.
3. ✅ **Done 2026-10-21** (rebuild only when the data changed; each sealed box decrypted once per run). **Desktop: pages rebuild on timers while nobody looks.** Activity rebuilds its whole tab every 60 s from the
   cache (`:3457`) even when nothing changed and the tab isn't open; Signals reads the keyring and decrypts every
   sealed box from every beacon every 5 min (`:3482`, beacon `inbox()`), even when nothing new was fetched. Rebuild
   only when the data changed and the tab is showing (mark it dirty otherwise); decrypt only new boxes (remember
   what was opened).
4. ✅ **Done 2026-10-21** (hourly and at quit; a sync with nothing new on either side is one `ls-remote`, no fetch, merge or push). **Sync less, and only when something changed.** 138 syncs a day between two computers, each ~8 git commands and
   several network round-trips even with nothing new (`SYNC_EVERY_MS` 15 min). Commit/push only when a synced file
   changed (and at quit), fetch less often (30–60 min), and skip a sync when the only change is a file rewritten
   by reading (`seen.json` every 5 s).
5. ✅ **Done 2026-10-21** (the suggestion and repo histories keep 120 days live and move older lines, in monthly batches, to compressed archives on this computer; the small logs and the Model's training data stay whole). **Append-only history files rotate.** `suggestions_history.jsonl` (1.26 MB, read in full twice every 5 min),
   `contribute_history.jsonl`, `training_data.jsonl`, `interest_events.jsonl`, `usage.jsonl` and the admin logs
   grow forever and are rewritten into the git history on each change. Keep the last N months (or N lines) live and
   fold older lines into a small summary; read the tail, not the whole file.
6. ✅ **Done differently 2026-10-21, after measuring.** Pages turned out to cost only 65–90 MB; **importing
   scikit-learn, SciPy and NumPy at startup cost ~140 MB and a second** (matcher.py, contribute.py imported them at
   the top). They now load only when needed; the CV vocabulary is counted in plain Python (the same terms and weights
   as scikit-learn's CountVectorizer, ties at the cutoff aside), and the Model page reads `model_weights.json` saved
   with the model instead of unpickling it. **Panel RAM 313 → 175 MB (−44%), startup imports 1.2 s → 0.23 s**, with or
   without a CV; budget tightened to 250 MB. Building pages on first open (the original idea) would save the remaining
   65–90 MB but touches most of qt_panel.py. Measured instead which page holds the widgets: **Chances, 575 of 1,019** (32 cards); it now draws on first open (no "new" count depends on it): **1,019 → 479 widgets at startup**, 150 → 137 MB before any page is opened. **Desktop RAM: build pages when first opened.** All 14 tabs are filled at startup (1,467 widgets, ~330 MB).
   Build each page the first time it's shown (keep the data loading as it is). Also cap the in-session caches that
   only grow: `ghcache.Store._rows` (decoded bodies kept for the whole session), `AvatarLoader._memory` (pixmaps),
   `profile_card._cache`.
7. ✅ **Done 2026-10-21** (avatar photos: newest 600 on disk, 400 in memory; weekly.log rotated at 1 MB; WISEP's tally trimmed to 3 months; the phone's WISEP row kept under 1.2 MB). **Caps where there are none:** the avatar cache folder (keep ~500 files / 30 MB, oldest first), `logs/weekly.log`
   (rotate at 1 MB, like `fatal.log`), the phone's single `wisep` AsyncStorage key (up to 300 full bodies in one row,
   near Android's ~2 MB row limit: cap by bytes, or one key per answer), WISEP's `calls` table (`KEEP_DAYS` is
   declared but never applied).
8. ✅ **Done 2026-10-21, with a measured trade-off.** Workers share a pool (8 for work, 8 for avatar photos; idle threads end after 30 s). A page of 40 uncached photos: 40 threads in 0.2 s before, 8 threads in 1.0 s now (3 threads took 2.8 s: too slow); photos from the disk cache stay instant. Matched people's Activity is asked every 30 min (was every 5), their events kept from the cache in between. **Threads:** every async job and avatar starts a fresh `QThread`; a small pool (`QThreadPool`, 4 workers) would
   cut thread churn. The N+1 Activity fetch (one `/users/<x>/events` per matched person, up to 24 every 5 min)
   should go through the GitHub cache with a longer refresh, or batch.
9. ✅ **Done 2026-10-21** for the four biggest (protocol model, curated lists, quiz, datasets: 1.2 MB, now read on first use; development build startup 503 → 480 MB PSS, Hermes native heap 260 → 233 MB; Chances checked on the emulator). `field-words` and `geekoc` stay: the first pages use them. **Phone bundle:** 1.7 MB of data files are imported statically, so they're parsed into the JS heap at startup
   (`field-words.json` twice). Load the big ones (`protocol_model`, `keywords`/`field-words`, `questions`,
   `datasets`) lazily when their page opens.
10. ⏸ **Not worth it, measured:** hidden idle is already 0.02% CPU; the tick returns at once. **The half-second "seen" tick** (`SEEN_TICK_MS`) walks every card on the page; it returns at once when hidden,
    but could stop its timer on hide and restart on show (the audit flags any sub-second timer left running hidden).

## Budgets

The numbers the audit checks are in `tools/resource_audit.py` (`BUDGETS`). Tighten a budget when a fix lands (for
example `rss_mb` after plan item 6), never loosen one to make a check pass without writing down why here.

- `rss_mb_macos` 270 (2026-10-21, the maintainer's decision): on the same code GitHub's runners measured the panel at
  266.7 MB on macOS, 211.8 on Linux and 184.0 on Windows (psutil RSS, after every page × 8). macOS counts the larger
  Qt frameworks and its allocator's reserve in RSS, so it reads ~50 MB higher; nothing in the app differs. Linux and
  Windows keep `rss_mb` 250. Trimming (cap `ghcache.Store._rows` and `AvatarLoader._memory`, then building pages on
  first open) would lower all three; if it lands, tighten both.

## History of this page

- 2026-10-21: plans 1–3 done and 4 partly (the interest map rests after 8 s on both apps; the phone's Model page went from 902 frames and 108% CPU in 30 s to 0 frames and 2.5%; the ticker stops while hidden; Activity and Signals rebuild only on new data; sealed boxes decrypted once; sync hourly).
- 2026-10-21: first audit. Fixed the same day: live databases moved out of the synced folder, ignored files untracked,
  conflicts from older computers settled, git's loose copies packed (data folder 4.9 GB → 279 MB), the four
  "never synced" files added to the ignore list, tests isolated from the real data and the network.
