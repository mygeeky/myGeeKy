"""Train the protocol model and write data/protocol_model.json (maker side; needs scikit-learn).

    python tools/protocol_model/train.py

Labelled examples come from:
  - labels.jsonl       {"id", "role"} for candidates in candidates.jsonl (collect.py)
  - published.jsonl    protocols users published (python -m mygeeky.protocols harvest): every link
                       gets its stage's role, every link they removed becomes "none"
  - the curated learning resources and reviewed protocols in data/curated.json

It picks the regularisation by 5-fold cross-validation, reports held-out scores
(report.md), then fits on everything and keeps only the weights that matter,
so the JSON stays small. The phone and the computer read the same file.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import GroupKFold, StratifiedKFold, cross_val_predict

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mygeeky import curated, protocols, protomodel, skills  # noqa: E402

TODAY = date(2026, 10, 13)          # fixed, so retraining on the same data gives the same model
OUT = ROOT / "src/mygeeky/data/protocol_model.json"
PHONE = ROOT / "mobile/src/data/protocol_model.json"


def aliases(name: str) -> list[str]:
    s = skills.find(name)
    return sorted({name.lower(), *(s["aliases"] if s else [])})


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def link_row(item: dict, skill: str, role: str) -> dict:
    kind = item.get("kind", "website")
    return {"kind": "article" if kind == "article" else "repo" if kind == "repo" else "website",
            "title": item.get("title", ""), "text": item.get("note", ""), "topics": [], "skill": skill,
            "role": role, "url": item.get("url", "")}


def examples() -> list[dict]:
    rows = []
    cands = {c["id"]: c for c in read_jsonl(HERE / "candidates.jsonl")}
    for lab in read_jsonl(HERE / "labels.jsonl"):
        c = cands.get(lab.get("id"))
        if c and lab.get("role") in protomodel.ROLES:
            rows.append({**c, "role": lab["role"], "src": "labelled"})
    data = curated.clean(json.loads((ROOT / "src/mygeeky/data/curated.json").read_text(encoding="utf-8")))
    level_role = {"beginner": "basics", "": "basics", "intermediate": "deeper", "advanced": "deeper"}
    for r in data["resources"]:
        rows.append({**link_row({"title": r["title"], "note": r["summary"], "url": r["url"],
                                 "kind": "repo" if "github.com/" in r["url"] else "website"},
                                (r.get("skills") or [""])[0], level_role.get(r.get("level", ""), "basics")),
                     "src": "curated"})
    for p in data.get("protocols") or []:
        for st in p["stages"]:
            if st["role"] in protomodel.ROLES:
                rows.extend({**link_row(it, p["skill"], st["role"]), "src": "reviewed"} for it in st["items"])
    for pub in read_jsonl(HERE / "published.jsonl"):
        p = pub["protocol"]
        for st in p["stages"]:
            if st["role"] in protomodel.ROLES:
                rows.extend({**link_row(it, p["skill"], st["role"]), "src": "published"} for it in st["items"])
        rows.extend({**link_row({"title": u.rsplit("/", 2)[-2] + " " + u.rsplit("/", 1)[-1], "url": u,
                                 "kind": "repo" if "github.com/" in u else "website"}, p["skill"], "none"),
                     "src": "published"} for u in pub.get("removed") or [])
    return rows


def main() -> int:
    rows = examples()
    if len(rows) < 50:
        print(f"only {len(rows)} labelled examples: label more first (labels.jsonl)")
        return 1
    feats = [{t: 1 for t in protomodel.tokens(r, aliases(r.get("skill", "")), TODAY)} for r in rows]
    y = np.array([r["role"] for r in rows])
    df = Counter(t for f in feats for t in f)
    feats = [{t: 1 for t in f if df[t] >= 2} for f in feats]
    vec = DictVectorizer()
    X = vec.fit_transform(feats)
    print(f"{len(rows)} examples, {X.shape[1]} features; roles {dict(Counter(y))}")

    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=7)
    best = None
    for C in (0.3, 1.0, 3.0):
        model = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
        pred = cross_val_predict(model, X, y, cv=folds)
        f1 = f1_score(y, pred, average="macro")
        useful = accuracy_score(y == "none", pred == "none")
        print(f"  C={C}: accuracy {accuracy_score(y, pred):.3f}, macro-F1 {f1:.3f}, useful-or-not {useful:.3f}")
        if best is None or f1 > best[1]:
            best = (C, f1, pred)
    C, f1, pred = best
    # the app meets skills the model never saw: hold out whole skills too
    groups = np.array([r.get("skill", "") for r in rows])
    unseen = cross_val_predict(LogisticRegression(C=C, max_iter=3000, class_weight="balanced"), X, y,
                               cv=GroupKFold(n_splits=5), groups=groups)
    f1_unseen = f1_score(y, unseen, average="macro")
    useful_unseen = accuracy_score(y == "none", unseen == "none")
    print(f"  unseen skills: macro-F1 {f1_unseen:.3f}, useful-or-not {useful_unseen:.3f}")
    report = classification_report(y, pred, digits=3)
    labelled = np.array([r["src"] == "labelled" for r in rows])

    model = LogisticRegression(C=C, max_iter=3000, class_weight="balanced").fit(X, y)
    roles = list(model.classes_)
    order = [roles.index(r) for r in protomodel.ROLES]
    W = model.coef_[order].T                     # features x roles, in ROLES order
    names = vec.get_feature_names_out()
    full = model.predict(X)
    bias = model.intercept_[order]
    Wc = W - W.mean(axis=1, keepdims=True)       # softmax is unchanged by a shared shift; centring shrinks the file
    # the smallest set of weights that still decides like the full model (>= 97% of examples)
    for cut in (0.4, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03):
        rows_kept = np.abs(Wc).max(axis=1) >= cut
        logits = X[:, rows_kept] @ Wc[rows_kept] + (bias - bias.mean())
        agree = float(np.mean(np.array(protomodel.ROLES)[np.asarray(logits).argmax(axis=1)] == full))
        if agree >= 0.97:
            break
    keep = {str(names[i]): [round(float(x), 3) for x in Wc[i]] for i in np.flatnonzero(rows_kept)}
    out = {"version": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "roles": protomodel.ROLES,
           "trained_on": len(rows), "cv_macro_f1": round(f1, 3), "unseen_skill_macro_f1": round(f1_unseen, 3),
           "bias": [round(float(b - bias.mean()), 4) for b in bias], "weights": keep}
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    for path in (OUT, PHONE):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")

    # the shipped (pruned) weights, read back the way the app reads them, must decide like the full model
    m = protomodel.load(OUT)
    shipped = [max(protomodel.predict(r, aliases(r.get("skill", "")), m, TODAY).items(), key=lambda kv: kv[1])[0]
               for r in rows]
    agree = float(np.mean(np.array(shipped) == full))
    (HERE / "report.md").write_text(
        f"# Protocol model\n\nTrained {out['version']} on {len(rows)} examples "
        f"({int(labelled.sum())} labelled candidates, the rest curated, reviewed or published).\n\n"
        f"- Features kept: {len(keep)} of {X.shape[1]}; file size {len(text) / 1024:.0f} KB\n"
        f"- Regularisation C = {C} (chosen by 5-fold cross-validation)\n"
        f"- Held-out macro-F1: **{f1:.3f}**; accuracy {accuracy_score(y, pred):.3f}; "
        f"useful-or-not accuracy {accuracy_score(y == 'none', pred == 'none'):.3f}\n"
        f"- Held-out accuracy on labelled candidates only: {accuracy_score(y[labelled], pred[labelled]):.3f}\n"
        f"- **Skills it never saw** (5 folds, whole skills held out): macro-F1 {f1_unseen:.3f}; "
        f"useful-or-not accuracy {useful_unseen:.3f}\n"
        f"- Shipped weights agree with the full model on {agree:.1%} of examples\n\n"
        f"## Per role (held out)\n\n```\n{report}```\n", encoding="utf-8")
    print(report)
    print(f"kept {len(keep)} features, {len(text) / 1024:.0f} KB; shipped agrees {agree:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
