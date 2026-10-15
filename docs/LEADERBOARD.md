# Quiz scores on mygeeky.org: only if someone asks, and provably

A quiz score could follow somebody into a job application. So **nothing about anyone appears on mygeeky.org unless
they ask for it**, and the asking has to be provable — which is why it happens on GitHub, from their own account,
and never by email.

This page is the whole promise, in one place: what the app does, what the maker does, and what can never happen.

## What the person does (in myGeeKy)

🌱 Grow → 🧭 Protocols → **🌍 Show my result** on a protocol they've scored.

1. **Two separate switches**, both off:
   - *Show my name, my profile link and my GitHub photo*
   - *Show my scores next to it*
2. The dialog shows **exactly what would appear**, in plain words, before anything is sent.
3. **Accept on GitHub** opens a prefilled public issue in
   [mygeeky/myGeeKy-ideas](https://github.com/mygeeky/myGeeKy-ideas/issues) — title starting **🏆**, label
   `leaderboard` — holding that same text, a small JSON block, and the word `accept`. They press Submit.

That Submit is the consent: GitHub records **who** wrote it and **when**, and the issue says what they agreed to.

**Taking it back:** `withdraw` on the same issue, or the button in the app. Nothing else is needed, ever.

**Each new score needs its own `accept`.** Agreeing to show 90% is not agreeing to show 100%.

## What can never happen

- **Nobody can accept for anyone else.** `leaderboard.consent` ignores an `accept` whose author isn't the account
  the entry is about, however it's worded. Same for `withdraw`.
- **A score below 80% is never shown**, agreed or not. The page lists only the month's top three and the first
  people to finish a protocol.
- **No affiliation, no email address, nothing else.** The payload has exactly: login, name, profile, avatar, the two
  switches, and the scores at or above the floor. `leaderboard.problems` fails the build if anything else turns up.
- **The maker never ranks.** `alsammanalsamman` is excluded in code — that's where the testing happens.
- **Nobody is invited.** The request always starts with the person. The maker never opens one of these issues for
  someone, because the issue is public from the moment it exists.

## What the maker does

A daily GitHub Action (`.github/workflows/leaderboard.yml`) reads the 🏆 issues and writes
`website/data/leaderboard.json`:

```
python -m mygeeky.leaderboard harvest website/data/leaderboard.json
```

- the newest word from each account wins (`accept`, then a later `withdraw`);
- `leaderboard.problems` must come back empty or the job fails;
- with `DEEPSEEK_API_KEY` set as a repository secret, the job adds a note per account — *does this look like a real
  researcher's account?* — from **public facts only** (how old it is, public repositories, bio). Few followers is
  never held against anyone. It is a note for the maker, never a gate on anyone;
- the job **opens a pull request**. Nothing reaches the website until the maker merges it.

**After a withdrawal,** run the workflow with *Rewrite the board branch* so the file is rewritten rather than added
to. The board lives on its own branch for exactly this reason: a rewrite leaves no old copy of someone's score in
the history.

## What the page shows

- **🏆 Top three this month**, by score weighted for how hard each protocol turned out to be (`quiz.weight_of`).
  Monthly, so somebody new can always get there; the all-time list is a separate *Hall of fame*.
- **Protocol's people**: the first five to reach 100% on a protocol, in order. The first one is the
  **🏴 Pathfinder** of that protocol.
- Each person: their name, a link to their profile, their GitHub photo, and — if they shared scores — the score.

## Why "for fun" is honest, not a disclaimer

The question bank ships inside the app, so a determined person can look the answers up. The random draw, the one
attempt a day, the growing bank and the maker's approval keep it fair enough for a bit of fun between researchers.
It is not an exam, it does not certify anyone, and the page says so.
