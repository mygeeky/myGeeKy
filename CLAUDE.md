# myGeeKy

Your geeky friend who helps you grow, quietly: a desktop panel (Python/Qt, Windows/macOS/Linux), a phone app
(Expo, `mobile/`) and a website (`website/`), all one product.

## The rule that matters most

myGeeKy runs on several platforms and **none may fall behind**. Before finishing any change, decide whether it
is shared or platform-specific, do every side of a shared change, and run the parity tests. The
**`mygeeky-platforms`** skill has the desktop↔phone file map, the shared data files and the checklist. Anything
shared that is left for later goes in `PARITY.md`; read it before working on the side that is behind.

## Never publish without the maintainer's go-ahead

Do **not** push to GitHub (no `git push`, no tags, no releases, no `gh release upload`), upload to PyPI, submit to
Google Play, or deploy the website until the maintainer says so in this conversation. Work and commit locally.
After each major improvement (a finished idea, a fix that's tested, a feature that works), stop and ask whether
to push or publish it, saying what would go out. A "yes" covers only what was asked about, not later work.

## Project skills (`.claude/skills/`)

- `mygeeky-platforms`: every code, data or text change (always).
- `mygeeky-phone`: running and debugging the phone app on the emulator.
- `mygeeky-release`: versions, changelog, tags, PyPI, the Windows installer, APKs and Google Play.
- `mygeeky-play`: getting the phone app through Google Play: its current rules (target API, 16 KB pages, Data safety,
  privacy policy, permissions, user content, signing) with sources, where myGeeKy stands, the open gaps, and
  `tools/play_check.py`, which checks a built APK.
- `mygeeky-ideas`: the maintainer's private `ideas.md` and `future.md`, kept in the private repo
  `AlsammanAlsamman/mygeeky_ideas` (symlinked here, git-ignored); changes to them are pushed there automatically.
- `mygeeky-article`: Highlights and the article skill DeepSeek follows (`src/mygeeky/data/article_skill.md`).
- `mygeeky-wisep`: every call to an open database (OpenAlex, arXiv, Zenodo, NCBI...) goes through WISEP; its rules
  and how it's evaluated (`docs/WISEP.md`).
- `mygeeky-resources`: what myGeeKy takes from a computer or phone (RAM, CPU, battery, storage, the synced repo, the
  beacon): the audit (`tools/resource_audit.py`), the budgets, and the plan (`docs/RESOURCES.md`).
- `mygeeky-datasets`: Grow → Data: the rules a dataset must pass to be shown, the sources harvested and how the list
  is updated.

## Promises the code must keep

- myGeeKy only suggests: it never follows, stars, posts or writes for the user. GitHub access is read-only,
  except the data repo and the Signals beacon, each through its own single-repo token.
- No telemetry, no myGeeKy server: data stays on the device or in the user's own storage (a hidden folder in their
  Google Drive, `drive.appdata` only, or their own GitHub repos), encrypted on the device before it leaves
  (`docs/STORAGE.md`). Never ask Google for another scope.
- Works without a GitHub account (ORCID or keywords are a full profile); only what reads the user's own account
  needs GitHub.
- Text from the internet is untrusted: never render it as HTML (Qt labels use plain text), never run code from
  it.

## Themes (desktop)

Every colour on the panel comes from the theme (`gui/app.py` `THEMES`), never a literal that suits one theme only.
A colour used for text (a group's, a kind's, a warning's) goes through `logic.readable(color, theme)`, which darkens
it on a light theme or lightens it on a dark one until it reads. A part that styles its own widgets defines
`apply_theme()` (no arguments): when the theme changes, the panel calls it on every part that has one. A wide row in ⚙
wraps to a second line rather than widening ⚙ (it must fit a 360px panel). `python tools/theme_audit.py` opens every
page and part in every theme, started in it and switched to it, and lists any text that's hard to read
(`tests/test_theme_audit.py` runs it for Frosted).

## Checks

- Desktop: `.venv/bin/python -m pytest -q`
- Phone: `cd mobile && npx tsc --noEmit && npx expo lint`
- Website: `.venv/bin/python website/build.py`
- Themes (desktop): `.venv/bin/python tools/theme_audit.py` (every page in every theme; 0 hard-to-read texts)
- Code map: `graphify query "<question>"` when `graphify-out/graph.json` exists (local only; rebuild with
  `graphify update .`).
