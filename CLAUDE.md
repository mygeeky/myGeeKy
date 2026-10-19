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
- `mygeeky-ideas`: the maintainer's private `ideas.md` (git-ignored; never commit it).
- `mygeeky-article`: Highlights and the article skill DeepSeek follows (`src/mygeeky/data/article_skill.md`).

## Promises the code must keep

- myGeeKy only suggests: it never follows, stars, posts or writes for the user. GitHub access is read-only,
  except the data repo and the Signals beacon, each through its own single-repo token.
- No telemetry, no myGeeKy server: data stays on the device or in the user's own GitHub repos.
- Works without a GitHub account (ORCID or keywords are a full profile); only what reads the user's own account
  needs GitHub.
- Text from the internet is untrusted: never render it as HTML (Qt labels use plain text), never run code from
  it.

## Checks

- Desktop: `.venv/bin/python -m pytest -q`
- Phone: `cd mobile && npx tsc --noEmit && npx expo lint`
- Website: `.venv/bin/python website/build.py`
- Code map: `graphify query "<question>"` when `graphify-out/graph.json` exists (local only; rebuild with
  `graphify update .`).
