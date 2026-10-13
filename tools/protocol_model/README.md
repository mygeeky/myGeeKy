# The protocol model

This is the small model the app uses to build a protocol for any skill. It looks at a GitHub repo or an article, as a
search returns it, and says whether it's learning material, and for which stage:

| role | what it means |
|---|---|
| `none` | not learning material: a library, an app, homework, an unrelated hit |
| `basics` | an introduction: beginner courses, tutorials, intro books |
| `deeper` | in depth: methods, advanced books, reviews, best practice, awesome-lists |
| `applied` | the skill used on a real task, as teaching material (e.g. "RNA-seq analysis in R") |
| `project` | a real analysis or pipeline worth reading and rerunning |

**How it works:**
- It's a multinomial logistic regression over the words, word pairs and a few binned facts (stars, age, article
  type) of the name, description, topics, title and abstract.
- The skill's own name is masked, so what it learns carries over to skills it never saw.
- It ships as plain JSON (`src/mygeeky/data/protocol_model.json`, copied to `mobile/src/data/`).
- The computer (`protomodel.py`) and the phone (`protomodel.ts`) compute the same numbers.

## Retraining

```
python tools/protocol_model/collect.py      # candidates.jsonl: the same searches the app runs, for ~55 skills
                                            #   (needs myGeeKy's saved GitHub token; about 3 minutes per skill,
                                            #   because GitHub allows 30 searches a minute)
# label them: labels.jsonl, one {"id", "role"} per candidate
python -m mygeeky.protocols harvest         # published.jsonl: protocols users published
python tools/protocol_model/train.py        # writes the model (computer + phone) and report.md
```

**`train.py` learns from:**
- the labelled candidates;
- the curated learning resources and reviewed protocols;
- every published protocol: each link gets its stage's role, and each link the user removed counts as `none`.

**How it's tuned and checked:**
- The regularisation is chosen by 5-fold cross-validation.
- The weights are pruned to the smallest set that still decides like the full model on at least 98% of examples.
- `report.md` holds the held-out scores.
- The test suite checks that the file stays under 1 MB and that the phone copy is identical.

**About the labels:** they were written by AI labellers reading each candidate's name, description and topics,
following the role table above. Correct any of them in `labels.jsonl` and retrain: your corrections and the
protocols users publish are what make the next model better.
