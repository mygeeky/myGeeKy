# myGeeKy

Your geeky friend who helps you grow, quietly: a desktop panel (Python/Qt, Windows/macOS/Linux), a phone app
(Expo, `mobile/`) and a website (`website/`), all one product.

## The rule that matters most

myGeeKy runs on several platforms and **none may fall behind**. Before finishing any change, decide whether it
is shared or platform-specific, do every side of a shared change, and run the parity tests. The
**`mygeeky-platforms`** skill has the desktop↔phone file map, the shared data files and the checklist. Anything
shared that is left for later goes in `PARITY.md`; read it before working on the side that is behind.

## Project skills (`.claude/skills/`)

- `mygeeky-platforms`: every code, data or text change (always).
- `mygeeky-phone`: running and debugging the phone app on the emulator.
- `mygeeky-release`: versions, changelog, tags, PyPI, the Windows installer, APKs and Google Play.
- `mygeeky-ideas`: the maintainer's private `ideas.md` (git-ignored; never commit it).

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
