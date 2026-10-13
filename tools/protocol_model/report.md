# Protocol model

Trained 2026-10-13T20:28:26Z on 7440 examples (7365 labelled candidates, the rest curated, reviewed or published).

- Features kept: 8746 of 27657; file size 413 KB
- Regularisation C = 0.3 (chosen by 5-fold cross-validation)
- Held-out macro-F1: **0.620**; accuracy 0.693; useful-or-not accuracy 0.825
- Held-out accuracy on labelled candidates only: 0.694
- **Skills it never saw** (5 folds, whole skills held out): macro-F1 0.553; useful-or-not accuracy 0.797
- Shipped weights agree with the full model on 97.3% of examples

## Per role (held out)

```
              precision    recall  f1-score   support

     applied      0.471     0.509     0.489       981
      basics      0.651     0.717     0.682      1640
      deeper      0.592     0.596     0.594      1153
        none      0.840     0.773     0.805      3479
     project      0.498     0.567     0.530       187

    accuracy                          0.693      7440
   macro avg      0.610     0.632     0.620      7440
weighted avg      0.703     0.693     0.697      7440
```
