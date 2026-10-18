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

1. Take the next idea (smallest first unless the user picks), say in one line what it will change and on which
   platforms.
2. Apply the `mygeeky-platforms` skill: an idea is only **(done)** when every platform it concerns has it, or
   the missing side is written as "still to do" on the idea (and in `PARITY.md` if it's a shared rule).
3. Verify (tests, type check, a look at the screen), then mark it and tell the user what changed and what's left.
4. Commit the code (not `ideas.md`) when the user wants it pushed.
