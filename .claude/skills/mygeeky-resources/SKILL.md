---
name: mygeeky-resources
description: Use when measuring or changing what myGeeKy takes from a computer or phone -- RAM, CPU, battery, storage, the synced data repo, the beacon, timers, threads, animations, caches, history files -- or when a change adds a timer, a background job, a cache, a file that is written often, a synced file, or a big bundled data file. Holds the resource audit (tools/resource_audit.py), the budgets, the phone's adb steps, and how to read and fix what they find.
---

# myGeeKy's resources: measure, budget, fix

myGeeKy is a quiet helper: it must never be the reason a laptop fan spins, a phone battery drains or a disk fills.
Every claim about efficiency is measured, against a budget, on every platform it concerns. The current numbers,
findings and plan are in `docs/RESOURCES.md`; read it before changing anything below.

## The rules (evidence first)

1. **Measure before and after.** A finding names the workload, the number, the cause (file:line) and one fix.
2. **Counts beat timings.** Widgets, Qt objects, timers, threads, commits per day and bytes are steady on any
   machine; seconds and CPU % vary. Budget timings loosely; budget counts tightly.
3. **What grows with each identical round is a leak** (Valgrind's "definitely lost"): run the same thing N times
   and look at the slope after the first two rounds, never at one reading.
4. **Hidden means quiet.** Nothing repaints, polls or rebuilds a page while the window is hidden, folded or the
   phone page isn't showing. Background work is due-checked (it asks "is it due?" and returns), and network work
   goes through WISEP (`mygeeky-wisep`).
5. **Everything kept has a limit.** Every cache, list, log, history file and AsyncStorage key has a cap (entries
   and bytes) or a trim (days). Append-only files rotate.
6. **The synced folder carries only your data.** No databases, no caches, no files rewritten every few seconds.
   Anything new in `DATA_DIR` is either in `sync.GITIGNORE` or deliberately synced (and small). Live databases go in
   `config.LOCAL_DIR` (`config.local_db`).
7. **Never on the user's real data.** The live checks run in a throwaway profile with the network blocked
   (`resource_audit.py` does this; tests get it from `tests/conftest.py`). `storage` only reads.

## Desktop (Windows, macOS, Linux)

```bash
PYTHONPATH=src .venv/bin/python tools/resource_audit.py storage     # real folders, read-only
.venv/bin/python tools/resource_audit.py leak 8                     # every page x8: widgets, Qt objects, Python memory
.venv/bin/python tools/resource_audit.py idle 20                    # CPU shown/hidden after startup settles, live timers
.venv/bin/python tools/resource_audit.py startup
.venv/bin/python tools/resource_audit.py all --json                 # what CI runs on all three systems
```

- `.github/workflows/resources.yml` runs `all --json` on Windows, macOS and Linux and keeps the report.
- `tests/test_resources.py` is the quick version on every test run (no widget leak, storage audit, ignore list).
- Deeper tools when a number is off: `python -X tracemalloc` / `tracemalloc` snapshots (built in), `memray run`
  + `memray flamegraph --temporal` (Linux/macOS: native and Qt memory too), `py-spy dump --pid` / `py-spy record`
  (what a busy thread is doing, from outside), `objgraph.show_growth()` between rounds (which object type grows).
- A running panel: `psutil.Process(pid)` RSS/USS, CPU %, threads, open files, sampled every 2 s for minutes.
- Qt specifics: `QApplication.allWidgets()` counts; `deleteLater()` only runs from the main loop, so a test that
  pumps events must also call `QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)` or it reports a
  false leak.

## The synced data repo and the beacon

```bash
git -C <DATA_DIR> count-objects -vH            # size-pack = history; size = loose copies not packed yet
git -C <DATA_DIR> log --since="1 day ago" --oneline | wc -l    # syncs a day
git -C <DATA_DIR> ls-files -ci --exclude-standard              # tracked but ignored: must be empty
git-sizer --json --json-version=2              # optional (github/git-sizer): biggest blobs and history depth
```
History by file: `git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize:disk) %(rest)'`
summed per path. The beacon: `beacon.json` size (budget in the audit), and how many repos and boxes a refresh reads.

## Phone (Android; the same ideas hold for iOS)

```bash
adb shell dumpsys meminfo org.mygeeky.app        # TOTAL PSS, Java heap, Native heap (Hermes), Graphics
adb shell top -b -n 1 -p $(adb shell pidof org.mygeeky.app)     # CPU now; repeat for a minute
adb shell run-as org.mygeeky.app du -sh databases files cache   # storage (AsyncStorage is databases/RKStorage)
adb shell dumpsys gfxinfo org.mygeeky.app        # frames drawn: a static page should draw ~0
adb shell dumpsys batterystats org.mygeeky.app   # wakeups and jobs (meaningful on a real phone, not the emulator)
```
- Measure a **release** build for numbers people see; a development build (Metro) is several times heavier.
- Idle test: open a page, leave it 60 s, read CPU and `gfxinfo` frames. A page that draws frames while nothing
  moves (an interval-driven animation) fails rule 4.
- Deeper: React Native DevTools Memory (Hermes heap snapshots, compare two), Perfetto traces, Flashlight
  (bamlab/flashlight) for a CPU/RAM/FPS score, Reassure (callstack) for render counts in CI.
- Ideas borrowed from callstackincubator/agent-skills (react-native-best-practices: measure → optimise → re-measure,
  JS and native memory leaks) and GetStream's perf-benchmarking rules (real device, counts over timings, median of
  5+ runs, same content before and after).

## When you change code

- Adding a `QTimer` / `setInterval` / background task: say its interval, make it stop or no-op when hidden, and
  check `idle` (timers list) before and after.
- Adding a cache or history file: give it a cap and say where it lives (`LOCAL_DIR` if it's a database or a cache
  the user doesn't need on another computer; add it to `sync.GITIGNORE`).
- Adding bundled data: say its size; the phone imports data files statically (parsed at startup), so prefer lazy
  loading for anything over ~100 KB.
- After the change: `tools/resource_audit.py all` (or the part you touched), update the numbers in
  `docs/RESOURCES.md` if they moved, and keep `BUDGETS` honest (tighten when a fix lands).
