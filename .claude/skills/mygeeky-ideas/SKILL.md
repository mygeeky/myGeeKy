---
name: mygeeky-ideas
description: Use when the user adds, orders, reviews or works through myGeeKy ideas ("add this to the ideas", "what's next", "let's do the ideas one by one"), leaves something "for the future", or when finishing work that matches an idea.
---

# The myGeeKy ideas list (and the future plans)

Two private files, kept in the maintainer's **private repo `AlsammanAlsamman/mygeeky_ideas`**, cloned next to
this repo at `../mygeeky_ideas/`:

- `ideas.md`: the ideas, in order, marked (done) when built;
- `future.md`: plans deliberately left for later ("leave this for the future"), each with what was found (numbers,
  evidence), why it waits, and the plan -- so it can be picked up months later without rediscovering anything.

In this repo, `ideas.md` and `future.md` are symlinks to those files and are in `.gitignore`: never commit them
here. If `../mygeeky_ideas` is missing (another computer), clone it
(`gh repo clone AlsammanAlsamman/mygeeky_ideas ../mygeeky_ideas`) or say so; don't invent its contents.

**Keep the private repo up to date, automatically.** After ANY change to `ideas.md` or `future.md` (adding,
reordering, marking done, editing), commit and push it in `../mygeeky_ideas` in the same turn, without asking --
the maintainer authorised this for that private repo only:

```bash
git -C ../mygeeky_ideas add -A && git -C ../mygeeky_ideas commit -q -m "<what changed, one line>" \
  && git -C ../mygeeky_ideas push -q
```

This standing permission covers only `mygeeky_ideas`. Pushing the myGeeKy repo itself, tags, PyPI and Play still
need the maintainer's go-ahead each time (`CLAUDE.md`).

## Its shape

- Numbered ideas grouped **Small** (an hour or two), **Medium** (a day or two), **Larger** (about a week) and
  **Big** (several weeks), ordered from least work to most. Numbering runs through the whole file.
- Each idea: a bold title and a few plain lines: what, why, where in the code if known.
- Similar ideas are merged into one. When adding, put the idea in the right group and renumber everything.
- Built ideas are marked **(done)**; part-built ones say where (e.g. **(done on the phone)**) and what's left.
  Mark them in the same turn the work is finished.

## Working through the list

1. **Explain before coding, then wait.** When moving to a new idea (smallest first unless the user picks one),
   tell the user briefly, in plain words:
   - what the idea is (one or two sentences);
   - what will change in the program: which screens or behaviour, on which platforms (desktop, phone, website);
   - anything they should decide first (a wording, a choice between two approaches).
   Look at the code enough to describe this accurately, but **do not edit any file until the user says
   "start code"** (or clearly says to go ahead). If they change the plan, explain again and wait again.
2. Apply the `mygeeky-platforms` skill: an idea is only **(done)** when every platform it concerns has it, or
   the missing side is written as "still to do" on the idea (and in `PARITY.md` if it's a shared rule).
3. Verify (tests, type check, a look at the screen), then mark it and tell the user what changed and what's left.
4. Commit the code locally (never `ideas.md` or `future.md` here; they go to `mygeeky_ideas` as above), then ask
   whether to push the code to GitHub. Never push, tag or upload
   without the maintainer's go-ahead for that work (see `CLAUDE.md`).
