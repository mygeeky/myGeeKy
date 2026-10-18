# Platform parity

Shared changes that one platform still has to catch up on. Add a line when a shared change is done on only some
platforms; remove it when the last one is done. See `.claude/skills/mygeeky-platforms/SKILL.md`.

## Pending

- 2026-10-18 · **Keyword suggestions in the phone's Settings keyword box**: setup has them on both apps, and so does
  the desktop's Model tab box; the phone's Settings box doesn't yet (`lib/word-suggest.ts` is ready to use there).
- 2026-10-18 · **Connecting the phone without a GitHub username**: the desktop refuses to make the pairing code
  (`gui/app.py` `phone_pairing`) and the phone refuses a code without one (`lib/pairing.ts`). Both sides must
  change together.

## Checked, nothing to do

- 2026-10-18 · Done on both now: "Continue as guest" (desktop setup + website), keyword suggestions (desktop setup and the panel's
  Model tab box; phone setup; same words, `test_phone_words_match_desktop.py`), and the data-repo warning on the desktop's
  Sync page.

- 2026-10-18 · HTML injection fix in the Qt panel (`qt_panel.py`, `growth_ui.py`): the phone renders text with
  React Native `<Text>`, which never interprets HTML, so it has no equivalent bug.
- 2026-10-18 · The quiz writer no longer runs AI-written code (`quizwriter.py`): desktop-only feature.
- 2026-10-18 · Menu-entry removal guarded to Linux (`gui/desktop.py`): desktop-only (the phone has no menu entry).
