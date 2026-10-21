"""The resource audit's quick version, on every test run: pages must not leak widgets, the synced folder must not carry
databases, and the audit itself reads the folders right (tools/resource_audit.py; the protocol: docs/RESOURCES.md)."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resource_audit", ROOT / "tools" / "resource_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_visiting_every_page_again_and_again_leaks_no_widgets(qapp_offscreen):
    out = audit.leak(rounds=4)
    assert len(out["tabs"]) >= 10
    widgets = [r["widgets"] for r in out["rounds"]]
    assert widgets[-1] - widgets[1] <= audit.BUDGETS["leak_widgets_per_round"] * 2, widgets
    assert out["checks"]["leak_widgets_per_round"] != "FAIL"


def test_the_storage_audit_finds_databases_and_tracked_ignored_files(tmp_path, monkeypatch):
    from mygeeky import config, sync
    data, local = tmp_path / "mygeeky", tmp_path / "mygeeky-local"
    data.mkdir()
    local.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "LOCAL_DIR", local)
    monkeypatch.setattr(config, "AVATAR_CACHE_DIR", data / "avatar_cache")
    monkeypatch.setattr(config, "LOG_DIR", data / "logs")
    subprocess.run(["git", "init", "-q", "-b", "main", str(data)], check=True)
    (data / ".gitignore").write_text(sync.GITIGNORE)
    (data / "taste.json").write_text("{}")
    (data / "headlines.json").write_text("[]")
    subprocess.run(["git", "-C", str(data), "add", "-f", "headlines.json", "taste.json"], check=True)
    subprocess.run(["git", "-C", str(data), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                   check=True)
    (data / "wisep.sqlite").write_bytes(b"x" * 1000)
    (local / "github_cache.sqlite").write_bytes(b"x" * 2_000_000)
    out = audit.storage()
    assert out["stray_in_data"] == ["wisep.sqlite"] and out["checks"]["stray_in_data"] == "WARN"
    assert out["tracked_but_ignored"] == ["headlines.json"] and out["checks"]["tracked_but_ignored"] == "FAIL"
    assert out["local_mb"] == pytest.approx(2.0, abs=0.01) and out["syncs_per_day"] == 1
    assert set(out["checks"]) >= {"data_working_mb", "local_mb", "data_git_mb", "syncs_per_day", "beacon_kb"}


def test_the_ignore_list_covers_every_file_the_program_says_is_never_synced():
    """config.py names files that stay on one computer; sync must not carry them (four slipped through)."""
    from mygeeky import sync
    ignored = sync.GITIGNORE.splitlines()
    for name in ("notify_state.json", "rank_seen.json", "my_github_events.json", "whois.json", "wisep.sqlite",
                 "github_cache.sqlite", "headlines.json", "keywords.json", "github_achievements.json"):
        assert any(name == p or (p.startswith("*") and name.endswith(p.lstrip("*"))) or
                   (p.endswith("*") and name.startswith(p.rstrip("*"))) for p in ignored), name
