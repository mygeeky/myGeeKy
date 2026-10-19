---
name: mygeeky-article
description: Use when writing, reviewing or changing myGeeKy Highlights (research articles retold as short news articles in Grow -> Highlights), or the article skill DeepSeek follows (src/mygeeky/data/article_skill.md). Covers the story's sections, the no-guessing rules, how facts come from OpenAlex, the translation step, and how to change the skill safely.
---

# The article skill (Highlights)

A Highlight retells one research article as a short science news article that an early-career researcher anywhere
can read in three minutes, in English and in each language myGeeKy offers (ar, fr, de, es, zh).

**The skill itself is `src/mygeeky/data/article_skill.md`**: one versioned prompt, in two steps (write the
English story; translate it). DeepSeek follows it in the admin tab (`src/mygeeky/highlights.py`). When you
write a Highlight yourself, follow the same file. Never keep a second copy of the rules anywhere else.

## The story: a short news article

A headline (what was found, plain words), a standfirst (one sentence), then 5 to 8 paragraphs, each carrying
ONE idea, no headings: the lead (the finding and why it matters) · who and where (team leader = last
author, institution, journal, date, the collaboration: how many institutions and countries) · the problem
and what came before · what they did and with which tools · what they found (numbers exactly as written;
two paragraphs for two findings) · the limits · the close (the take-home, what comes next if the text says).
A paragraph with nothing behind it is left out, never padded. Underneath: "learn these tools" (skills,
linked to Grow) and "read the article" (the DOI link).

## What keeps it honest

- **Facts are looked up, not written**: authors, team leader, institutions, countries, journal, date and
  open access come from OpenAlex by DOI (`highlights.look_up` / `facts`). The model only words them.
- **Only the given text**: what the text doesn't say is left out -- never guessed.
- **Checked afterwards** (`highlights.checks`): every number in the article and every tool name must be in
  the text (or the looked-up facts); the team leader must be named. Failures show beside the draft; the maker decides.
- **Coverage is said out loud**: "From the full article" or "From the abstract only" on every story.
- **Translations** keep numbers, names, tools, genes, species and abbreviations exactly.

## Changing the skill

1. Edit `article_skill.md` (bump its version line). Keep the JSON keys (title, hook, body, tool_names,
   skills, keywords, coverage): both apps read them, and `tests/test_highlights.py` checks the rules that
   must stay.
2. New words around a story mean `LABELS` in `highlight_shape.py` and `mobile/src/lib/highlight-shape.ts`
   (all six languages); `tests/test_highlights.py` checks the phone has every one.
3. News and AI models will get their own skill files next to this one, sharing the same shape.
