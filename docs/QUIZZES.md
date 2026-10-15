# Quizzes: how the questions are written, checked, and shown

Every reviewed protocol can have a **question bank**. An attempt draws ten questions from it and marks them on the
person's own device. This page is for the maker: how a question gets into the bank, and what stops a wrong one.

Nothing here is a judgement of anyone. Scores stay on the device unless the person asks for one to be shown
([LEADERBOARD.md](LEADERBOARD.md)).

## What a question looks like

`src/mygeeky/data/questions.json`, shipped with the app and refreshed from `main` like the curated lists:

```json
{"version": "2026-10-14T00:00:00Z",
 "questions": [
  {"id": "excel-to-r.deeper.02", "protocol": "excel-to-r", "stage": "deeper",
   "level": "easy", "kind": "choice",
   "q": "In tidy data, what does one row hold?",
   "options": ["One observation", "One variable", "One treatment group", "One plate"],
   "answer_hash": "4b8f…",
   "why": "Rows are observations: one measured thing per row, however many columns it needs.",
   "source": {"title": "R for Data Science (2e)", "url": "https://r4ds.hadley.nz/data-tidy", "kind": "book",
              "quote": "Each observation is a row; each row is an observation."},
   "checks": ["the sentence it quotes is on the source page"]}]}
```

- **`protocol` and `stage`** must exist in a reviewed protocol (`curated.json`). The test suite checks this.
- **`level`** is `easy` (50% of an attempt), `medium` (35%) or `tricky` (15%). *Tricky* means a mistake people
  really make at that step — a silent row drop in R, a leak between train and test — never confusing wording.
- **`kind`** is `choice`, or `code` when the answer is what the snippet prints.
- **`source`** is one of that step's own links — or a page of the same site, since a protocol links a book's
  front page while a question quotes one of its chapters — and **`quote`** is the sentence that proves the answer.
  A `code` question needs the source but no quote: it proves itself when it's run.
- **`answer_hash`** is a short SHA-256 of the right option, tied to the question's id
  (`quiz.answer_token`), so opening the file doesn't show which one is right. The app hashes each option
  and finds the match; the phone does the same (`mobile/src/lib/quiz.ts`), and a test keeps the two in step.
  While a batch is being written the plain `answer` is still used; `quiz.hide_answer` swaps it for the hash
  as the batch is accepted into the bank.
- Exactly **four** options, all different.

## Writing them by hand (how the shipped bank was made)

All 258 shipped questions were written by hand, not by DeepSeek. The rule is the same either way: each one
quotes a sentence that is really on one of that protocol's own sources.

```
python tools/quiz/sources.py --list                 # which protocols have how many questions
python tools/quiz/sources.py git-github-teamwork    # that protocol's sources, as quotable sentences
#   write the batch as a JSON list (plain `answer` position), then:
python tools/quiz/add.py batch.json                 # check it: shape, quote, code, no bench work
python tools/quiz/add.py batch.json --write         # add it, hashing the answers, and update the phone copy
```

`add.py` puts a hand-written batch through exactly the checks the DeepSeek writer uses, plus two of its
own: the question's step must exist in that protocol, and its source must be one of that protocol's links
(or a page of the same site, since a protocol links a book's front page while a question quotes a chapter).
Pages are cached under `tools/quiz/.cache`, so rewriting a batch costs no requests.

It caught real mistakes while this bank was written: duplicate questions between two protocols that share a
source, a quote taken from a book's front page rather than the chapter it was on, options that gave the
answer away by being much longer than the rest, and one question of mine that broke my own no-NOT rule.

## Writing a batch with DeepSeek

Admin tab → **📝 QUIZZES TO WRITE** → **📝 Write questions** on a protocol. It uses the same key as the listing
scout (kept in the system credential store, never in a file, never shipped).

For each of that protocol's links, in turn:

1. The page is fetched (a GitHub repo reads as its README) and sent with the step it belongs to.
2. DeepSeek writes a handful of questions **from that text alone**, each with the sentence it quotes.
3. myGeeKy checks each one, in order of cost (`quizwriter.check_question`):

   | check | what it catches |
   |---|---|
   | the rules, in code | not four different options, "all of the above", a NOT/EXCEPT question, an answer that stands out by length, no reason given, a near-duplicate of a question already in the bank |
   | the quote | the sentence isn't on the page (so the question was written from memory, not the source) |
   | running the code | `print(…)` doesn't produce the answer. Python runs here; R only if R is installed |
   | a blind second read | a second call gets the question **without** the answer, options shuffled differently each time. It must pick the right one **both** times, and agree the question is clear with exactly one right answer. One disagreement is enough to drop it |
   | safety | anything outside what myGeeKy covers (`safety.py`): it teaches analysis, so a source that describes laboratory work gives no questions at all, and such a source is dropped before it is even read |

4. What survives is kept with the checks it passed.

The report says how many were kept and the most common reasons the rest were dropped.

## Your review: five questions

**👀 Spot-check** shows the ones where the checks disagreed, plus a few at random — five in all. Mark each
**👍 fine** or **👎 wrong**.

- All 👍 → the batch is trimmed towards the level mix and written into `src/mygeeky/data/questions.json`.
- Any 👎 → the whole batch is thrown away. A bad question means the prompt or the source was wrong, so rewriting is
  cheaper than fixing one question.

Then check and commit it:

```
python tools/quiz/verify.py          # every quote still on its page, code run, sums redone
python -m mygeeky.quiz check         # the shape of the file, and the mix per protocol
cp src/mygeeky/data/questions.json mobile/src/data/questions.json
```

`verify.py` is the one to run before a release: it catches a source page that has changed since a question was
written.

## When a question is wrong anyway

Everyone taking a quiz has a **🚩** on every question:

- it's left out of that person's next attempts straight away;
- it can be sent to the maker as a public issue (the question, never their answers).

To drop one from the bank:

```python
from mygeeky import quizwriter
quizwriter.retire(["excel-to-r.basics.04"])     # then commit, and write a replacement
```

## How it is shown

Four small classes draw the whole thing, and none of them decides anything (`src/mygeeky/gui/growth_ui.py`;
the phone mirrors them in `mobile/src/components/`):

| class | what it draws |
|---|---|
| `AnswerRow` | one answer: a letter badge and text that **wraps**. Not a button: a button is never narrower than its own text, which would force the panel wider and squeeze everything in it |
| `QuestionCard` | the question unit — step, level, the question, its code block, the four answers, and after answering: right or wrong, why, the quoted sentence and the source as a card |
| `QuestionDots` | a dot per question in the attempt: answered, where you are, still to come; green and red once marked |
| `QuizRunView` | a whole attempt inside the 🏆 Quiz tab: the header, the dots, the question, one button onward — then the result (`ResultView`, `ScoreRing`) and what to do next |

The panel owns the answers and hands them to `QuizRunView`; the view draws and calls back. That is why the
same views serve all three ways in (🏁 in the Quiz tab, 🏁 on a protocol, 🎓 on a step) with no second code path.

## What the app does with a bank

- **An attempt** is 10 questions, drawn in the mix, options shuffled, from that protocol's bank only. A protocol
  somebody edited keeps the questions of the one it came from (`based_on`).
- **The level check** on one step uses that step's questions when there are any; otherwise it falls back to the
  quiz written into the protocol itself, or to "I can do these".
- **Only the best score counts**, and there's one attempt per protocol per day — so a score means something, and
  so nobody can grind the same questions.
- **Difficulty** (`quiz.weight_of`): until enough people have shared scores, the share of tricky questions stands
  in for how hard a protocol is. After that, the average score people actually get decides.

## Honest limits

- **The hash is obfuscation, not security.** It keeps the answers out of plain sight, and that is all it
  does. There are only four options, so anyone willing to write five lines can hash all four and compare —
  and a question's own `why` and quoted sentence usually give the answer away anyway, because that is what
  makes it teach something. A score nobody can fake needs marking somewhere the person can't reach, and
  myGeeKy has no server on purpose. What actually keeps the board fair: the random draw from a growing bank,
  one attempt a day, and the maker approving anything that reaches the website — on a board that says it is
  for fun.
- **R code can't be checked where R isn't installed.** Those questions fall to the blind read and the spot check.
- **A source page can change.** That's what `tools/quiz/verify.py` is for.
