# GEMS: how myGeeKy's games are fed, scored and learned from

**GEMS** (Games: Evidence, Mastery, Signals) is the protocol behind Play with GeeKOc. It decides what a game plays,
how a round is scored, and what myGeeKy may learn from it. The rules live in one file per app, kept line for line
alike: `src/mygeeky/gems.py` (computer) and `mobile/src/lib/gems.ts` (phone). `tests/test_gems.py` runs the phone's
real TypeScript against the Python on the same inputs.

## The games

Each game is one row in `GAMES`: an id, a name, an icon and the kinds of content it plays. Its screen is drawn per
app; its rules are shared.

| Game | Plays |
|---|---|
| Word Hunter | word sets (shoot the set's words, let decoys from other sets pass), quiz questions between waves |
| Rise | ladders: a pipeline's steps, one right and some wrong per row, each wrong one saying why |
| GeeKOc goes home | quiz questions (`data/questions.json`) on the maze's doors |
| GeeKOc run, Flappy GeeKOc | gates: a short question and two short answers |
| Whack-a-bug | critters: bugs to whack and good practices to spare |
| Real tool or made up? | real and invented tool names |
| Gene or Pokémon? | real gene names and Pokémon |
| Reviewer 2 attacks | reviewer comments, the right reply and wrong ones |
| Debug reef | short snippets (Python, R, Shell, SQL) and the line with the bug |
| Sort the catch | names to sort into 2-3 bins |
| Fix the figure | a flawed figure (drawn by the app) and its flaw among wrong ones |
| Which came first? | names with the year something happened |
| Terminal typing | a task, two right commands and one wrong one; the computer types the right one, the phone picks |

Adding a game: a row in `GAMES` on both apps, its icon (`tools/game_icons.py` cuts a 4 × 4 sheet), and a screen per
app. If it needs a new kind of content, add the kind to `KINDS` and its check to `validate` on both apps.

## The content (the evidence)

All content is one pack, `data/games.json`, shipped identical in both apps. Every item has:

- `id` (unique), `kind`, `level` 1-3 (easy, medium, hard);
- `terms`: lower-case field words, used to choose items from your field;
- `source`: a title and an https link that proves the item (a tool's page, a paper's DOI, a database, a lesson);
- the fields of its kind, checked by `validate`.

A pack that fails `validate` is never played: the app falls back to the one it shipped with. A newer pack is
fetched like the curated lists (`GAMES_PACK_FILE`) and wins only if it passes the checks and is at least as new.

**Renewal.** The core pack (283 items, October 2026) was written by hand. More is added in three ways, in this order
of preference:

1. **Maker packs:** the maker drafts new items with DeepSeek in Admin; each must carry its source and pass
   `validate`, and nothing is published without the maker's Accept (the same rule as TRACE).
2. **Built on the device** from what myGeeKy already holds (no network): your keywords and field, the curated tools,
   the AI race list, the quiz bank for your protocols.
3. **WISEP**, only when one fact is missing (a tool's first release, say), within WISEP's budgets.

## Choosing a round

`pick(items, n, progress, weights, today, seed, level)`:

- about **70%** from your field: items whose terms weigh most in your Model (your stated profile plus what you've
  been doing, `interests.profile_terms`);
- about **20%** new territory: items whose terms you've never shown interest in;
- about **10%** review: items you've seen and are **due** again (a Leitner box per item: a right answer moves it up
  and it comes back after 1, 2, 4, 8, 16 or 32 days; a wrong answer sends it back to the first box);
- never above what the game's level unlocks: easy items to start, medium from level 3, hard from level 6;
- if one group runs short, the others fill in; items resting (seen, not due) only when nothing else is left;
- shuffled by a seeded generator (mulberry32, seeded from the day, the game and its play count), the same on both
  apps.

## Scoring (the mastery)

- **Points:** 10 per right answer × the item's level, plus a bonus the game may add (speed, a correctly typed
  command).
- **Stars:** 3 at 95% right, 2 at 80%, 1 at 60%.
- **Game levels 1-10:** from the game's XP (its points): level 2 at 150, 3 at 450, 4 at 900, then +75·L each.
- **Player level:** from all games' XP together, with no cap.
- **Best score**, plays, time played, answered and right, per game.

Progress is `GAMES_PROGRESS_FILE` (`games_progress.json` on the computer, local storage on the phone). It stays on the
device and syncs only with the rest of your data to your own storage. No leaderboard unless you join one.

## What myGeeKy learns (the signals)

- **The Model** gets one `play` event per round (weight 0.8 per term, like a news click), built by `model_terms`:
  the topics played, a right answer counting fully and a wrong one 0.6, the whole scaled by playing time (0.3 for a
  short round up to 1.5 after ten minutes), the 12 biggest terms. It fades with your other interests.
- **Know and learning** (`mastery`): topics with at least 3 answers and 80% right are ones you **know**; topics with
  at least 2 wrong and under 60% right are ones you're **learning**. You, Grow, Learn and Job Quest can show and use
  them.
- **Badges:** 🎮 Player (rounds played: 3 / 25 / 100), 🎯 Sharp (right answers: 25 / 200 / 800), 🆙 Level Up (game
  levels gained: 3 / 15 / 40), counted from your progress on both apps.

## Promises

- Quiet: no sound and no streak pressure by default.
- Offline: a round needs no network; only a pack refresh or a WISEP fact does.
- Nothing about a round leaves the device except through your own sync, and never to a myGeeKy server.
- Internet text in a pack is shown as plain text, never as HTML, and no pack content is ever run.
- Every item can be traced to its source.
