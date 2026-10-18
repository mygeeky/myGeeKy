---
name: mygeeky-ideas
description: Use when the user adds, orders, reviews or works through myGeeKy ideas ("add this to the ideas", "what's next", "let's do the ideas one by one"), or when finishing work that matches an idea.
---

# The myGeeKy ideas list

The list lives in `ideas.md` at the repo root. It is the maintainer's private file: it is in `.gitignore`, so it
exists only on their computer and must never be committed. If it's missing (another computer), say so and offer
to start one; don't invent its contents.

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
4. Commit the code locally (never `ideas.md`), then ask whether to push it to GitHub. Never push, tag or upload
   without the maintainer's go-ahead for that work (see `CLAUDE.md`).
