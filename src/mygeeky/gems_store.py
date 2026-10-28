"""Your games on this computer: the pack they play and your progress, on top of the rules in gems.py.

The pack is the one shipped with myGeeKy (data/games.json) unless a newer valid one has been fetched
(GAMES_PACK_FILE); a pack that fails gems.validate is never played. Progress lives in GAMES_PROGRESS_FILE, which
syncs with the rest of your data to your own storage. `finish` is the one door a game goes through when a round
ends: it records the round, saves it, and tells the Model what was played (interests.record_terms, kind "play").
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from . import gems
from .config import GAMES_PACK_FILE, GAMES_PROGRESS_FILE, MyGeekyConfig, ensure_dirs
from .files import read_json, write_json

BUNDLED = Path(__file__).parent / "data" / "games.json"
_pack: dict[str, Any] | None = None


def load_pack(force: bool = False) -> dict[str, Any]:
    """The newest valid pack: the fetched one if it passes the checks and is at least as new, else the shipped one."""
    global _pack
    if _pack is not None and not force:
        return _pack
    shipped = read_json(BUNDLED, None) or {"items": []}
    fetched = read_json(GAMES_PACK_FILE, None)
    if isinstance(fetched, dict) and not gems.validate(fetched) and str(fetched.get("updated", "")) >= str(shipped.get("updated", "")):
        _pack = fetched
    else:
        _pack = shipped
    return _pack


def load_progress() -> dict[str, Any]:
    data = read_json(GAMES_PROGRESS_FILE, None)
    return data if isinstance(data, dict) and data.get("version") == 1 else gems.empty_progress()


def save_progress(progress: dict[str, Any]) -> None:
    ensure_dirs()
    write_json(GAMES_PROGRESS_FILE, progress)


def weights(cfg: MyGeekyConfig) -> dict[str, float]:
    """Your Model's terms (what you stated plus what you've been doing), lower-cased like the pack's terms."""
    try:
        from . import interests
        return {str(t).lower(): float(w) for t, w in interests.profile_terms(cfg).items()}
    except Exception:
        return {}


def round_items(cfg: MyGeekyConfig, game: str, kind: str, n: int, today: str | None = None) -> list[dict[str, Any]]:
    """The items one round of `game` plays from `kind`: gems.pick with your Model, your progress and your level."""
    today = today or date.today().isoformat()
    prog = load_progress()
    level = gems.level_of(int((prog.get("games", {}).get(game) or {}).get("xp", 0)))
    items = gems.items_of(load_pack(), kind)
    return gems.pick(items, n, prog, weights(cfg), today, gems.seed_of(f"{today}:{game}:{prog['games'].get(game, {}).get('plays', 0)}"), level)


def finish(cfg: MyGeekyConfig, game: str, answers: list[dict[str, Any]], seconds: float, bonus: int = 0,
           today: str | None = None) -> dict[str, Any]:
    """A round ended: record it, save it, teach the Model. Returns gems.record's summary plus what you know and
    what you're learning now."""
    today = today or date.today().isoformat()
    prog, summary = gems.record(load_progress(), game, answers, seconds, today, bonus)
    save_progress(prog)
    try:
        from . import interests
        interests.record_terms("play", gems.model_terms(answers, seconds), source=f"game:{game}", cfg=cfg)
    except Exception:
        pass                                               # learning never gets in the way of a game
    return {**summary, **gems.mastery(prog)}


def badge_counts() -> dict[str, int]:
    return gems.badge_counts(load_progress())


def summary() -> dict[str, Any]:
    return gems.summary_of(load_progress())
