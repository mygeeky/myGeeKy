# Platform parity

Shared changes that one platform still has to catch up on. Add a line when a shared change is done on only some
platforms; remove it when the last one is done. See `.claude/skills/mygeeky-platforms/SKILL.md`.

## Pending

- 2026-10-18 · **"Continue as guest"** (no account, then keywords) is on the phone's first screen.
  Behind: desktop setup wizard (`gui/setup_wizard.py`, ProfilePage) and the website.
- 2026-10-18 · **Keyword suggestions while typing** (`mobile/src/lib/word-suggest.ts`, from the keyword
  dictionary) are on the phone's setup. Behind: desktop setup wizard and the panel's keyword boxes, and the
  phone's Settings keyword box.
- 2026-10-18 · **Walk-through after GitHub sign-in: data repo, then Signals** is on the phone
  (`components/setup-steps.tsx`). The desktop wizard already has both pages (Sync, Signals), but it doesn't
  yet warn that skipping the data repo keeps everything on this computer only, with no sharing with the phone.
- 2026-10-18 · **Connecting the phone without a GitHub username**: the desktop refuses to make the pairing code
  (`gui/app.py` `phone_pairing`) and the phone refuses a code without one (`lib/pairing.ts`). Both sides must
  change together.

## Checked, nothing to do

- 2026-10-18 · HTML injection fix in the Qt panel (`qt_panel.py`, `growth_ui.py`): the phone renders text with
  React Native `<Text>`, which never interprets HTML, so it has no equivalent bug.
- 2026-10-18 · The quiz writer no longer runs AI-written code (`quizwriter.py`): desktop-only feature.
- 2026-10-18 · Menu-entry removal guarded to Linux (`gui/desktop.py`): desktop-only (the phone has no menu entry).
