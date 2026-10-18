---
name: mygeeky-platforms
description: Use for ANY change to myGeeKy code, data or text (a bug fix, a feature, a rule, a wording, a data file). myGeeKy is one product on several platforms (desktop Python/Qt app on Windows, macOS and Linux; the Expo phone app; the website and docs), so every change must be checked against the other platforms so none falls behind. Covers the desktop↔phone file map, shared data files, the parity tests, and the end-of-change checklist.
---

# myGeeKy is one product on several platforms: none may fall behind

Every change gets classified before it's done: **shared** (all platforms must get it), **platform-specific**
(only one platform has that code or feature), or **pending** (shared, but the other side is done later, and that
is written down). Never finish a change as "shared" with only one side done and nothing recorded.

## The platforms

| Platform | Where | Language | Ships as |
|---|---|---|---|
| Desktop app (panel, CLI, setup wizard) | `src/mygeeky/`, `src/mygeeky/gui/` | Python 3, PySide6/Qt | PyPI `mygeeky`; Windows installer (`installer/`, `.github/workflows/release.yml`); macOS app bundle and Linux menu entry (`gui/desktop.py`, `gui/macos.py`) |
| Phone app | `mobile/src/` (screens in `mobile/src/app/`, logic in `mobile/src/lib/`) | TypeScript, Expo / React Native | Android APK / Play Store (`mobile/eas.json`); see `mobile/AGENTS.md` |
| Website | `website/` (`index.html`, `privacy.html`, `build.py`) | HTML/JS | mygeeky.org via `.github/workflows/pages.yml` |
| Docs | `README.md`, `docs/GUIDE.md`, `CHANGELOG.md`, `docs/*.md` | Markdown | GitHub and PyPI pages |

Windows, macOS and Linux share the desktop code but differ in installers, menus, paths, start-at-login and
process handling (`winproc.py`, `topmost.py`, `macos.py`, `desktop.py`, `scheduler.py`). A desktop change that
touches files, processes, windows or startup must be thought through on all three.

## Desktop ↔ phone: files that must change together

Each phone file says in its opening comment which desktop file it ports. Keep that comment true.

| Phone (`mobile/src/lib/…`) | Desktop (`src/mygeeky/…`) |
|---|---|
| `admin.ts` | `admin.py` |
| `badges.ts` | `badges.py` |
| `collab.ts` | `collab.py` |
| `contribute.ts` | `contribute.py` |
| `curated.ts`, `countries.ts` | `curated.py` |
| `github-login.ts` | `github_login.py` |
| `headlines.ts` | `headlines.py` |
| `interests.ts` | `interests.py` |
| `live.ts` | `activity.py` |
| `market.ts`, `board.ts` | `market.py` |
| `model-repo.ts` | `sync.py`, `gui/app.py` (the data repo, the model) |
| `models.ts` | `hfmodels.py` |
| `news.ts` | `news.py` |
| `orcid-login.ts` | `orcid_login.py` |
| `pairing.ts` | `pairing.py` (the QR code: both sides read the same format) |
| `profile-card.ts` | `profile_card.py` |
| `protocols.ts`, `protocol-shape.ts`, `reviewed-fit.ts` | `protocols.py` |
| `protomodel.ts` | `protomodel.py` |
| `quiz.ts` | `quiz.py` |
| `research.ts` | `papers.py`, `scholar.py` |
| `safety.ts` | `safety.py` |
| `seasons.ts` | `seasons.py` |
| `seen.ts` | `freshness.py` |
| `signal-crypto.ts` | `signal_crypto.py` |
| `signals.ts`, `signals-core.ts` | `beacon.py` |
| `skills.ts` | `skills.py` |
| `taste.ts` | `taste.py` |
| `theme.ts` | `gui/app.py` (THEMES) |
| `tokens.ts` | `tokens.py`, `token_check.py` |
| `wins.ts` | `wins.py` |
| `word-suggest.ts` | `keywords.py` (`suggest`, `pick`) + `gui/word_suggest.py` |
| `components/field-map.tsx`, `interest-map.tsx`, `model-plots.tsx` | `gui/signals_ui.py`, `gui/qt_panel.py` |
| `ideas.ts` (+ `components/idea-sheet.tsx`) | `ideas.py` (+ `IdeaDialog` in `gui/qt_panel.py`) |
| `app/setup.tsx`, `components/setup-steps.tsx`, `signin.tsx` | `gui/setup_wizard.py`, `setup_api.py` |

Desktop-only today (no phone side, so a fix there is platform-specific unless the phone gains the feature):
`scout.py`, `quizwriter.py`, `leaderboard.py`, `mailbox.py`, `updates.py`, `uninstall.py`, `crashreport.py`,
`scheduler.py`, `winproc.py`, `topmost.py`, `sync.py` git handling, the CLI.

## Shared data: one source, copies kept equal

The desktop file is the source; the phone copy must be identical or generated from it.

| Desktop | Phone | Kept equal by |
|---|---|---|
| `src/mygeeky/data/curated.json` | `mobile/src/data/curated.json` | `.github/workflows/curated-lists.yml` writes both; tests (`test_growth.py`) |
| `src/mygeeky/data/questions.json` | `mobile/src/data/questions.json` | tests (`test_quiz.py`) |
| `src/mygeeky/data/protocol_model.json` | `mobile/src/data/protocol_model.json` | tests (`test_protocols.py`) |
| `src/mygeeky/data/skills.json` | `mobile/src/data/skills.json` | tests (`test_growth.py`) |
| `src/mygeeky/data/keywords.json` | `mobile/src/data/field-words.json` (generated) | `keywords.save()` writes it; `test_phone_words_match_desktop.py` |

After editing a desktop data file, update the phone copy in the same change (`cmp` them).

## The parity tests (run them for any shared change)

```bash
.venv/bin/python -m pytest -q -rs tests/test_phone_*_match_desktop.py tests/test_quiz.py tests/test_protocols.py tests/test_growth.py   # -rs shows any skip
```

`test_phone_seasons_match_desktop.py`, `test_phone_signals_match_desktop.py` and
`test_phone_reviewed_match_desktop.py`, `test_phone_ideas_match_desktop.py` run the phone's real TypeScript in Node (copied into `mobile/.crosscheck/`,
imports given their `.ts` ending) on the same inputs as the Python and compare the answers. They need **Node 22.6+**
(`node --experimental-strip-types`) and skip without it: if pytest reports them as *skipped*, the phone was not
checked, so say so instead of calling the change verified. When you change a shared
rule that has no such test yet, add a case: same input through both, same answer expected.

## How to work a change

1. **Before editing:** find the change's counterparts. Use the table above, the opening comment of the file,
   and `graphify query "<the rule or function>"` (the project graph is in `graphify-out/`).
2. **Classify it:** shared / platform-specific / pending. A bug in a rule (validation, a regex, a deadline,
   a limit, a score, wording the user sees) is almost always shared. Layout, widgets, installers and OS calls
   are usually platform-specific, but check whether the other side has the *same bug in its own way*.
3. **Do both sides in the same change** when it's shared. Same behaviour, same limits, same words.
4. **Check the user-facing text everywhere:** a changed feature or promise may also need `README.md`,
   `docs/GUIDE.md`, `website/index.html`, `website/privacy.html` (anything about data or accounts), the Play
   listing (`docs/play/LISTING.md`) and `CHANGELOG.md`.
5. **Verify each side:** desktop `.venv/bin/python -m pytest -q`; phone `cd mobile && npx tsc --noEmit && npx expo lint`;
   website `python website/build.py`. Run the parity tests above.
6. **Report the parity line** at the end of the work and in the commit message body:
   `Platforms: desktop ✓ phone ✓ website n/a` — or `phone: pending (reason)`.

## Pending work is never silent

If a shared change can't be finished on every platform now, add it to `PARITY.md` at the repo root (create it if
missing) under "Pending", one line each: date, what, which side is behind, why. Remove the line when done.
Check `PARITY.md` at the start of any work on the side that is behind.
