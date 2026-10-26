"""Learning before an account: the phone keeps and uses what you open, and nothing is lost when you connect later."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mygeeky import interests
from mygeeky.config import MyGeekyConfig

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
NOW = "2026-10-18T12:00:00+00:00"
EVENTS = [
    {"at": "2026-10-17T09:00:00+00:00", "kind": "star", "terms": {"single cell": 0.5, "scanpy": 0.3, "umap": 0.2}},
    {"at": "2026-10-10T09:00:00+00:00", "kind": "repo", "terms": {"single cell": 0.6, "seurat": 0.4}},
    {"at": "2026-09-01T09:00:00+00:00", "kind": "fork", "terms": {"gwas": 0.7, "plink": 0.3}},
    {"at": "2026-10-18T08:00:00+00:00", "kind": "news", "terms": {"protein folding": 1.0}},
    {"at": "2026-10-16T08:00:00+00:00", "kind": "follow", "terms": {"scanpy": 0.5, "spatial": 0.5}},
    # the same follow seen "new" again and again, with the person's name in it: counted once, the name left out
    *[{"at": f"2026-10-1{d}T08:00:00+00:00", "kind": "follow", "source": "followed JakeWharton",
       "terms": {"jake": 0.3, "wharton": 0.3, "kotlin": 0.4}} for d in range(8)],
]
TEXTS = [["Scanpy: single-cell analysis in Python, with UMAP and Leiden clustering", ["single-cell", "scanpy"]],
         ["PLINK 2.0 for GWAS and population genetics", ["gwas"]],
         ["A fast tool for the 3 people who use it", []]]


def _node() -> bool:
    if not shutil.which("node"):
        return False
    v = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=120).stdout.strip().lstrip("v").split(".")
    return len(v) > 1 and v[0].isdigit() and v[1].isdigit() and (int(v[0]), int(v[1])) >= (22, 6)


@pytest.mark.skipif(not _node(), reason="needs Node 22.6+")
def test_the_phone_learns_exactly_as_the_desktop():
    work = MOBILE / ".crosscheck"
    work.mkdir(exist_ok=True)
    shutil.copy(MOBILE / "src" / "lib" / "learn.ts", work / "learn.ts")
    (work / "learn-side.ts").write_text(
        "import { blendLearned, extractTerms, learnedTerms } from './learn.ts';\n"
        "const [events, now, texts] = JSON.parse(process.argv[2]);\n"
        "const cfg = { interest_learning: true, interest_half_life_days: 30 };\n"
        "const learned = learnedTerms(events, cfg, 15, Date.parse(now));\n"
        "console.log(JSON.stringify({ learned, blend: blendLearned({ gwas: 1, ai: 0.4 }, learned),\n"
        "  terms: texts.map(([t, topics]) => extractTerms(t, topics)) }));\n", encoding="utf-8")
    out = subprocess.run(["node", "--experimental-strip-types", str(work / "learn-side.ts"),
                          json.dumps([EVENTS, NOW, TEXTS])], capture_output=True, text=True, cwd=MOBILE, timeout=60)
    assert out.returncode == 0, out.stderr[-600:]
    phone = json.loads(out.stdout)
    interests.INTEREST_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    interests.INTEREST_EVENTS_FILE.write_text("".join(json.dumps(e) + "\n" for e in EVENTS), encoding="utf-8")
    cfg = MyGeekyConfig(interest_learning=True, interest_half_life_days=30)
    desktop = interests.learned_terms(cfg, 15, datetime.fromisoformat(NOW))
    assert desktop and [[t, w] for t, w in desktop] == phone["learned"]
    assert not {"jake", "wharton", "kotlin"} & {t for t, _ in desktop}       # 2.0 x 0.4 once is below the bar
    assert interests.blend_learned({"gwas": 1, "ai": 0.4}, desktop) == phone["blend"]
    for (text, topics), said in zip(TEXTS, phone["terms"]):
        assert interests.extract_terms(text, topics) == said, text


def test_the_phone_keeps_what_you_open_with_no_repo_and_sends_it_on_connecting():
    repo = (MOBILE / "src" / "lib" / "model-repo.ts").read_text(encoding="utf-8")
    record = re.search(r"export async function recordInterest\(.*?\n}\n", repo, re.S).group(0)
    assert "nothing is kept" not in record and "!(await modelLink())) return" not in record
    usage = re.search(r"export async function queueUsage\(.*?\n}\n", repo, re.S).group(0)
    assert "if (!(await modelLink())) return" not in usage
    connect = re.search(r"export async function connectModel\(.*?\n}\n", repo, re.S).group(0)
    assert "flushInterests(repo, token)" in connect                       # what it learned goes to the repo now
    state = (MOBILE / "src" / "lib" / "app-state.tsx").read_text(encoding="utf-8")
    assert state.count("withLocalLearning(") >= 4                           # every way the profile is built


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True, timeout=120).stdout


@pytest.mark.skipif(not shutil.which("git"), reason="needs git")
def test_a_computer_joining_a_repo_with_data_merges_what_it_learned(tmp_path, monkeypatch):
    from mygeeky import sync
    # GitHub, played by a bare repo that another computer already filled
    bare = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    other = tmp_path / "other"
    _git(tmp_path, "clone", "-q", str(bare), str(other))
    (other / "interest_events.jsonl").write_text('{"from": "the other computer"}\n', encoding="utf-8")
    _git(other, "add", "-A")
    _git(other, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "first")
    _git(other, "push", "-q", "origin", "main")
    # this computer, used as a guest: it learned on its own
    data = sync.DATA_DIR
    data.mkdir(parents=True, exist_ok=True)
    (data / "interest_events.jsonl").write_text('{"from": "this computer"}\n{"from": "the other computer"}\n',
                                                encoding="utf-8")
    monkeypatch.setattr(sync, "public_on_github", lambda repo: False)
    monkeypatch.setattr(sync, "_repo_exists", lambda repo: True)
    monkeypatch.setattr(sync, "_repo_is_private", lambda repo: True)
    monkeypatch.setattr(sync, "remote_url", lambda repo: str(bare))
    monkeypatch.setattr(sync, "import_config", lambda: None)
    said = sync.init("me/mygeeky-data")
    assert "Backed up" in said and "Merged 1 records" in said
    lines = (data / "interest_events.jsonl").read_text(encoding="utf-8").splitlines()
    assert lines == ['{"from": "the other computer"}', '{"from": "this computer"}']   # both, once each
    _git(other, "pull", "-q", "origin", "main")                         # and the repo has it for the others
    assert '{"from": "this computer"}' in (other / "interest_events.jsonl").read_text(encoding="utf-8")


def test_merge_logs_adds_only_what_is_missing(tmp_path):
    from mygeeky.sync import merge_logs
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.jsonl").write_text("1\n2\n3\n", encoding="utf-8")
    (b / "x.jsonl").write_text("2\n4", encoding="utf-8")              # no newline at the end
    (a / "y.jsonl").write_text("only here\n", encoding="utf-8")
    (a / "config.json").write_text("{}", encoding="utf-8")            # not a log: left alone
    assert merge_logs(a, b) == 3
    assert (b / "x.jsonl").read_text(encoding="utf-8") == "2\n4\n1\n3\n"
    assert (b / "y.jsonl").read_text(encoding="utf-8") == "only here\n" and not (b / "config.json").exists()


def test_the_model_tab_says_learning_stays_here_without_a_data_repo(monkeypatch):
    pytest.importorskip("PySide6")
    from tests.test_freshness import _close, _quiet_panel
    app, panel = _quiet_panel(monkeypatch, MyGeekyConfig(github_username="", keywords=["gwas"]))
    try:
        panel._render_brain()
        assert not panel.local_only.isHidden() and "this computer only" in panel.local_only.text()
        monkeypatch.setattr("mygeeky.gui.app.sync_enabled", lambda cfg: True)
        panel._render_brain()
        assert panel.local_only.isHidden()
    finally:
        _close(panel)
