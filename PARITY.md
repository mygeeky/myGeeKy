# Platform parity

Shared changes that one platform still has to catch up on. Add a line when a shared change is done on only some
platforms; remove it when the last one is done. See `.claude/skills/mygeeky-platforms/SKILL.md`.

## Pending

- 2026-10-26 · **The new start, one question a screen** (Welcome with GeeKOc → GitHub, skip → ORCID, skip → "Can you
  give me one of these?" three keywords / a CV / an ORCID iD, each unfolding, or *Continue without*): done on the phone
  (`app/setup.tsx`); the computer's setup wizard (`gui/setup_wizard.py`) still has its own pages and *Continue as
  guest*, and asks for at least one thing. Behind: the computer.
- 2026-10-18 · **People without a GitHub account**: on the desktop, People still finds people from your field (the
  "field half", by searching repos in your field); on the phone, People needs GitHub. So the tab order differs too:
  the desktop moves Activity and Signals last, the phone also Live and People (`tab-order.ts`). Behind: the phone.
- 2026-10-18 · **Keyword suggestions in the phone's Settings keyword box**: setup has them on both apps, and so does
  the desktop's Model tab box; the phone's Settings box doesn't yet (`lib/word-suggest.ts` is ready to use there).
- 2026-10-18 · **Connecting the phone without a GitHub username**: the desktop refuses to make the pairing code
  (`gui/app.py` `phone_pairing`) and the phone refuses a code without one (`lib/pairing.ts`). Both sides must
  change together.
- 2026-10-21 · **A dotted ring on planets that open into more**: the phone's orbit and folded dock draw a still
  dashed ring around a planet with parts (`components/dashed-orbit.tsx`; none in the centre). The desktop's
  planet row still shows the old small mark. Behind: the desktop.

## Checked, nothing to do

- 2026-10-18 · Done on both now: "Continue as guest" (desktop setup + website), keyword suggestions (desktop setup and the panel's
  Model tab box; phone setup; same words, `test_phone_words_match_desktop.py`), and the data-repo warning on the desktop's
  Sync page.

- 2026-10-18 · HTML injection fix in the Qt panel (`qt_panel.py`, `growth_ui.py`): the phone renders text with
  React Native `<Text>`, which never interprets HTML, so it has no equivalent bug.
- 2026-10-18 · The quiz writer no longer runs AI-written code (`quizwriter.py`): desktop-only feature.
- 2026-10-18 · Menu-entry removal guarded to Linux (`gui/desktop.py`): desktop-only (the phone has no menu entry).
