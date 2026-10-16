"""The live glass panel: a small, docked, always-on-top Qt window.

Built on PySide6/Qt, not a webview. pywebview's WebView2-on-Windows
transparency turned out to be a confirmed, currently-unreliable upstream bug
(see https://github.com/r0x0r/pywebview/issues/1611 -- even the maintainer
can't get it consistent across versions/machines, and CSS `backdrop-filter`
never worked through it at all). Qt's `WA_TranslucentBackground` on a
frameless window is the mature, well-supported way apps actually get real
per-pixel window transparency on Windows, confirmed working here. A native
DWM Acrylic backdrop (real blur-behind) was also tried and removed again --
it reliably turned the otherwise-working Qt transparency fully opaque on
this setup (see the comment above `main()`). So this panel is genuinely
see-through (real per-pixel alpha), just without a blurred backdrop.

Design constraints, deliberately unchanged from the previous version:

- Read-only over local state by default. Opening the panel never hits the
  network; `get_suggestions()`/`get_model_history()` replay what `mygeeky
  run`/`learn` already produced and logged to disk.
- The only automatic network call is a cheap, cached activity-feed refresh
  (one GitHub Events API call), rate-limited by `gui_activity_refresh_minutes`
  so the panel can't hammer the API just by being left open.
- A full candidate search (`refresh_suggestions`) runs when the user clicks
  "Refresh", or by itself only once the follow-back list has run empty AND
  the last search is older than `gui_suggestions_auto_refresh_hours`
  (default 6; 0 disables). A repo search (`refresh_contributions`) only ever
  runs on a click.
- Opening a profile is the ONLY thing a click ever reaches out to do, and
  all it does is open the URL in the system browser. There is no
  follow/unfollow call anywhere in this file, same as the rest of myGeeKy.
  Likewise the Repos tab only opens repo/issue/fork pages -- nothing here
  forks a repo or opens a PR.
- The one exception, opt-in via `mygeeky beacon init`: clicking a gesture
  button on the Signals tab publishes that emoji signal to your own public
  beacon repo (see beacon.py). Nothing else in the panel writes anything.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from .. import auth
from ..activity import get_matched_activity, get_recent_activity
from ..cli import _run_contribute, _run_suggestions
from ..config import MyGeekyConfig, load_config, profile_ready, save_config
from ..github_client import GitHubClient
from ..storage import (
    add_excluded,
    load_activity_cache,
    load_excluded,
    load_following_snapshot,
    load_model_history,
    load_training_examples,
    last_contributions,
    last_suggestion_time,
    last_suggestions,
    save_activity_cache,
)

THEME_NAMES = ("midnight", "frosted", "aurora")

THEMES: dict[str, dict[str, Any]] = {
    "midnight": {
        # A drop box's list is drawn in its own window, where a translucent colour goes black.
        # These two are the only opaque surface in the theme, and exist for exactly that.
        "solid_bg": "#1c1c2a",
        "solid_text": "#f0f0f5",
        "bg": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(28,28,42,158), stop:1 rgba(12,12,20,107))",
        "border": "rgba(255,255,255,31)",
        "text": "#f0f0f5",
        "muted": "rgba(240,240,245,150)",
        "card_bg": "rgba(255,255,255,15)",
        "btn_bg": "rgba(255,255,255,26)",
        "btn_hover": "rgba(255,255,255,51)",
        "tab_active": "rgba(120,180,255,71)",
        "section_btn": "rgba(120,180,255,56)",
        "accent": "#7fd8ff",
        "swatch_border": "rgba(255,255,255,80)",
        # text roles: every label asks the theme for its kind of text, never a fixed colour
        "title": "#ffffff", "link": "#7fd8ff", "good": "#34d399", "bad": "#f87171", "warn": "#fbbf24",
        "cat_ai": "#ff6fd8", "cat_science": "#34d399", "cat_tech": "#7fd8ff",
        "on_accent": "#15151f", "explore": "#9b87ff", "dark": True,
    },
    "frosted": {
        # A drop box's list is drawn in its own window, where a translucent colour goes black.
        # These two are the only opaque surface in the theme, and exist for exactly that.
        "solid_bg": "#f6f1ea",
        "solid_text": "#241f1a",
        "bg": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,255,255,140), stop:1 rgba(255,255,255,71))",
        "border": "rgba(255,255,255,153)",
        "text": "#241f1a",
        "muted": "rgba(36,31,26,175)",
        "card_bg": "rgba(255,255,255,89)",
        "btn_bg": "rgba(0,0,0,31)",
        "btn_hover": "rgba(0,0,0,51)",
        "tab_active": "rgba(0,0,0,31)",
        "section_btn": "rgba(224,138,79,71)",
        "accent": "#b5591f",
        "swatch_border": "rgba(0,0,0,60)",
        # darker shades: they have to stay readable on white
        "title": "#14110e", "link": "#0b5f8f", "good": "#047857", "bad": "#b91c1c", "warn": "#a16207",
        "cat_ai": "#a21caf", "cat_science": "#047857", "cat_tech": "#0369a1",
        "on_accent": "#ffffff", "explore": "#6d28d9", "dark": False,
    },
    "aurora": {
        # A drop box's list is drawn in its own window, where a translucent colour goes black.
        # These two are the only opaque surface in the theme, and exist for exactly that.
        "solid_bg": "#241a33",
        "solid_text": "#ffffff",
        # an opaque aurora: the panel paints its background solid (the Transparency slider sees to the
        # glass), and the old near-transparent white turned into a white panel under white text
        "bg": "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3a1d5e, stop:0.55 #272463, stop:1 #10385f)",
        "border": "rgba(255,255,255,89)",
        "text": "#ffffff",
        "muted": "rgba(255,255,255,195)",
        "card_bg": "rgba(255,255,255,26)",
        "btn_bg": "rgba(255,255,255,46)",
        "btn_hover": "rgba(255,255,255,71)",
        "tab_active": "qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff6fd8, stop:1 #7a5cff)",
        "section_btn": "rgba(255,111,216,77)",
        "accent": "#ff6fd8",
        "title": "#ffffff", "link": "#a5f3fc", "good": "#6ee7b7", "bad": "#fca5a5", "warn": "#fde68a",
        "cat_ai": "#ff9ce6", "cat_science": "#6ee7b7", "cat_tech": "#a5f3fc",
        "on_accent": "#1a1030", "explore": "#c4b5fd", "dark": True,
        "swatch_border": "rgba(255,255,255,120)",
    },
}


# --------------------------------------------------------------------------- business logic (no Qt dependency -- testable without a live app)

def _build_client(cfg: MyGeekyConfig) -> GitHubClient:
    token = auth.get_token(cfg.github_username)
    return GitHubClient(token, rate_limit_sleep=cfg.rate_limit_sleep_seconds, search_pause=cfg.search_pause_seconds)


def get_status(cfg: MyGeekyConfig) -> dict[str, Any]:
    return {
        "github_username": cfg.github_username,
        "token_present": auth.get_token(cfg.github_username) is not None,
        "dock_side": dock_side(cfg),
        "theme": cfg.gui_theme if cfg.gui_theme in THEME_NAMES else "midnight",
        "configured": bool(cfg.github_username),
        "profile_ready": profile_ready(cfg),
        "orcid_id": cfg.orcid_id,
        "from_keywords": bool(not cfg.github_username and not cfg.orcid_id and (cfg.keywords or cfg.topics)),
    }


# --------------------------------------------------------------------------- starting from keywords alone
def field_opening() -> list[dict[str, Any]]:
    """The first five keywords to offer somebody with no account of any kind."""
    from .. import fieldstart
    return fieldstart.opening()


def field_suggest(picked: list[str], dismissed: list[str] | None = None,
                  shown: list[str] | None = None) -> list[dict[str, Any]]:
    """The next five: three near what they picked, two deliberately elsewhere."""
    from .. import fieldstart
    return fieldstart.suggest(picked or [], dismissed or [], shown or [])


def field_ready(picked: list[str]) -> dict[str, Any]:
    """Whether the picks describe a field well enough to start, and how full the bar is."""
    from .. import fieldstart
    return fieldstart.ready(picked or [])


def field_offer(typed: str, online: bool = False) -> dict[str, Any]:
    """What myGeeKy can say about a word somebody typed, known to it or not."""
    from .. import fieldstart
    return fieldstart.offer_for(typed, online=online)


def field_keep(cfg: MyGeekyConfig, picked: list[str]) -> dict[str, Any]:
    """Save the picked keywords onto the profile, merged with whatever is already there."""
    from .. import fieldstart
    fieldstart.keep(cfg, picked or [])
    save_config(cfg)
    return fieldstart.summary(cfg)


def account_nudge(cfg: MyGeekyConfig, wall: str = "") -> dict[str, Any]:
    """Whether to bring up making an ORCID or GitHub account, and what to say about it."""
    from .. import fieldstart
    return fieldstart.nudge(cfg, wall=wall)


def account_asked(cfg: MyGeekyConfig, wall: str = "") -> None:
    """Remember the ask happened, so the same thing is never said twice."""
    from .. import fieldstart
    fieldstart.asked(cfg, wall=wall)
    save_config(cfg)


def field_summary(cfg: MyGeekyConfig) -> dict[str, Any]:
    from .. import fieldstart
    return fieldstart.summary(cfg)


def set_theme(cfg: MyGeekyConfig, theme: str) -> bool:
    if theme not in THEME_NAMES:
        return False
    cfg.gui_theme = theme
    save_config(cfg)
    return True


DOCK_SIDES = ("right", "left", "bottom-right", "bottom-left")
LAYERS = ("front", "normal", "behind")


def dock_side(cfg: MyGeekyConfig) -> str:
    return cfg.gui_dock_side if cfg.gui_dock_side in DOCK_SIDES else "right"


def layer(cfg: MyGeekyConfig) -> str:
    return cfg.gui_layer if cfg.gui_layer in LAYERS else "front"


def set_dock_side(cfg: MyGeekyConfig, side: str) -> bool:
    if side not in DOCK_SIDES:
        return False
    cfg.gui_dock_side = side
    save_config(cfg)
    return True


def set_layer(cfg: MyGeekyConfig, value: str) -> bool:
    if value not in LAYERS:
        return False
    cfg.gui_layer = value
    save_config(cfg)
    return True


MIN_OPACITY = 0.6           # the Transparency slider's 100% is 40% see-through: the panel never fades away
MAX_OPACITY = 1.0


def set_opacity(cfg: MyGeekyConfig, opacity: float) -> bool:
    if not (MIN_OPACITY <= opacity <= MAX_OPACITY):
        return False
    cfg.gui_opacity = opacity
    save_config(cfg)
    return True


MIN_PANEL_HEIGHT = 0.35     # share of the screen: never so short it's useless...
MAX_PANEL_HEIGHT = 0.90     # ...nor so tall it covers the whole screen


def clamp_panel_height(fraction: float) -> float:
    return round(min(max(float(fraction), MIN_PANEL_HEIGHT), MAX_PANEL_HEIGHT), 3)


def set_panel_height(cfg: MyGeekyConfig, fraction: float) -> float:
    cfg.gui_panel_height_fraction = clamp_panel_height(fraction)
    save_config(cfg)
    return cfg.gui_panel_height_fraction


def setup_overview(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Everything that decides how myGeeKy works for you, for ⚙ (may check the
    tokens' expiry with GitHub, at most once a day)."""
    from .. import __version__, tokens
    try:
        toks = tokens.status(cfg)
    except Exception:
        toks = []
    return {
        "user": cfg.github_username, "version": __version__,
        "tokens": [{"name": t.get("name", ""), "message": t.get("message", ""), "state": t.get("state", "")} for t in toks],
        "signals": cfg.beacon_enabled,
        "beacon_token": bool(cfg.github_username and auth.get_beacon_token(cfg.github_username)),
        "sync": cfg.sync_repo, "orcid": cfg.orcid_id, "scholar": cfg.scholar_id,
        "cv": Path(cfg.cv_path).name if cfg.cv_path else "", "keywords": list(cfg.keywords),
    }


def set_signals_enabled(cfg: MyGeekyConfig, on: bool) -> dict[str, Any]:
    """Turn Signals on (publishes your beacon with your Signals token) or off
    (your beacon repo stays as it is; you just stop sending and receiving)."""
    from .. import beacon as bc
    if on:
        try:
            bc.go_live(cfg)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True}
    cfg.beacon_enabled = False
    save_config(cfg)
    return {"ok": True}


def get_update_info(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Whether to show the update banner: a newer release on PyPI that the
    user hasn't said "Later" to. Checks PyPI at most once a day."""
    from .. import updates
    if not cfg.check_for_updates:
        return {"show": False}
    info = updates.check()
    show = info["newer"] and info["latest"] != cfg.update_dismissed
    return {**info, "show": show, "editable": updates.is_editable(), "releases_url": updates.RELEASES_URL}


def dismiss_update(cfg: MyGeekyConfig, version: str) -> None:
    cfg.update_dismissed = version
    save_config(cfg)


def install_update() -> dict[str, Any]:
    """Only ever called from a click on the banner's Update button."""
    from .. import updates
    ok, message = updates.run_upgrade()
    return {"ok": ok, "message": message}


def get_token_warnings(cfg: MyGeekyConfig) -> list[dict[str, Any]]:
    """Tokens that expire within a week (or already have); checked at most daily."""
    from .. import tokens
    if not cfg.github_username:
        return []
    return tokens.warnings(cfg)


def replace_token(cfg: MyGeekyConfig, name: str, value: str) -> dict[str, Any]:
    """Store a renewed token, but only after it has proven it works: the read
    token must belong to you, and the Signals token must be able to publish."""
    import keyring
    from .. import beacon, tokens
    value = (value or "").strip()
    user = cfg.github_username
    if not value:
        return {"ok": False, "message": "No token pasted."}
    try:
        if name == "read":
            login = GitHubClient(value, rate_limit_sleep=0).get_authenticated_user().get("login", "")
            if login.lower() != user.lower():
                return {"ok": False, "message": f"That token belongs to {login}, not {user}."}
            keyring.set_password(auth.SERVICE_NAME, user, value)
        else:
            beacon.go_live(cfg, beacon.BeaconWriter(value, user))
            keyring.set_password(auth.BEACON_SERVICE_NAME, user, value)
    except Exception as exc:
        from ..errors import describe
        return {"ok": False, "message": f"That token didn't work: {describe(exc)}"}
    tokens.forget()
    renewed = next((t for t in tokens.status(cfg, force=True) if t["name"] == name), None)
    return {"ok": True, "message": "Saved. " + (renewed["message"] if renewed else "")}


WORK_STYLES = (("", "I'd rather not say"), ("code", "I mostly build software"),
               ("analysis", "I mostly analyse data"), ("both", "Both"))


def set_work_style(cfg: MyGeekyConfig, style: str) -> str:
    """What kind of work you mostly do: it only tilts which kinds of skill come up first (skills.py)."""
    from ..config import save_config
    cfg.work_style = style if style in {s for s, _ in WORK_STYLES} else ""
    save_config(cfg)
    return cfg.work_style


def set_hearts(cfg: MyGeekyConfig, enabled: bool) -> None:
    cfg.gui_hearts_enabled = bool(enabled)
    save_config(cfg)


def _hidden_usernames() -> set[str]:
    """People not to show any more: anyone you clicked (added to the
    excluded list, which future runs skip too) plus anyone you now follow,
    per the following list cached by the last activity refresh. That list is
    deliberately NOT the `learn` snapshot -- `learn` detects new follows by
    diffing against that snapshot, so the panel must never update it."""
    hidden = {u.lower() for u in load_excluded()}
    hidden |= {u.lower() for u in (load_activity_cache() or {}).get("following") or []}
    return hidden


def get_suggestions(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Who to show: people you haven't seen first, from everyone suggested lately
    (see freshness.py: someone you've seen rests a while, then may come back)."""
    from .. import freshness
    from ..storage import suggestion_pool
    hidden = _hidden_usernames()
    try:
        seen = freshness.load()
        followback = freshness.arrange(cfg, "person", suggestion_pool("followback", hidden),
                                       cfg.max_suggestions_returned, data=seen)
        domain = freshness.arrange(cfg, "person", suggestion_pool("domain", hidden),
                                   cfg.domain_highlight_count, data=seen)
    except Exception as exc:     # never let "what's new" stop the panel: plain lists, and a report
        _report_freshness_error(exc)
        followback = last_suggestions(cfg.max_suggestions_returned, list_type="followback", exclude=hidden)
        domain = last_suggestions(cfg.domain_highlight_count, list_type="domain", exclude=hidden)
    return {"followback": followback, "domain_highlights": domain,
            "new": freshness.count_new(followback) + freshness.count_new(domain)}


def _report_freshness_error(exc: Exception) -> None:
    try:
        from .. import crashreport
        from ..config import LOG_DIR
        crashreport.write(LOG_DIR, "what's new (freshness)", exc)
    except Exception:
        pass


def suggestions_auto_refresh_due(cfg: MyGeekyConfig, now: datetime | None = None) -> bool:
    """True when the panel should start a suggestion search by itself: the
    follow-back list is empty and the last search is older than
    `gui_suggestions_auto_refresh_hours` (0 turns this off)."""
    from .. import freshness
    hours = cfg.gui_suggestions_auto_refresh_hours
    if not profile_ready(cfg) or hours <= 0:
        return False
    # Without an account there is no follow-back list at all, so the domain-fit list is what "empty" means.
    shown = get_suggestions(cfg)["followback" if cfg.github_username else "domain_highlights"]
    if shown and not freshness.running_low(shown, cfg.max_suggestions_returned):
        return False
    if shown:                                   # running low on new faces: top up, but gently
        hours = max(hours, cfg.fresh_people_topup_hours)
    last = last_suggestion_time()
    if last is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - last).total_seconds() >= hours * 3600


def record_click(cfg: MyGeekyConfig, kind: str, item: dict[str, Any]) -> None:
    """A click on a person, repo, Market row or news item is an interest
    signal (terms only; see interests.py), and counts toward your badges
    (the kind of thing only). Never raises."""
    _log_click_for_badges(kind, item)
    try:
        from .. import interests
        if kind == "person":
            sources = " ".join(s.split(":", 1)[-1].replace("/", " ") for s in item.get("sources") or [])
            interests.record("person", f"{item.get('bio') or ''} {sources}", source=item.get("username", ""), cfg=cfg)
        elif kind == "repo":
            name = item.get("full_name") or item.get("repo") or ""
            interests.record("repo", f"{name.replace('/', ' ')} {item.get('description') or ''} "
                                     f"{item.get('language') or ''}", topics=item.get("topics") or [],
                             source=name, cfg=cfg)
        elif kind == "model":
            interests.record("repo", f"{item.get('id', '').replace('/', ' ')} {item.get('pipeline', '')}",
                             topics=item.get("tags") or [], source=item.get("id", ""), cfg=cfg)
        elif kind in ("news", "paper", "headline"):
            interests.record("news", item.get("title", ""), topics=item.get("match") or [],
                             source=item.get("id", ""), cfg=cfg)
    except Exception:
        pass


def _log_click_for_badges(kind: str, item: dict[str, Any]) -> None:
    from .. import achievements, badges
    if kind == "news":
        source = item.get("source", "")
        kind = "paper" if source in ("arxiv", "biorxiv") or "velocity" in item or "cited" in item else "news"
    elif kind == "headline" and badges.item_kind(item) == "P":
        kind = "paper"
    achievements.log("click", kind, str(item.get("category", "")), bool(item.get("explore")))


def phone_pairing(cfg: MyGeekyConfig, include_token: bool = True) -> dict[str, Any]:
    """The "Connect your phone" QR code: your profile, plus your token only if
    it's strictly read-only. Checks the token with GitHub (a few seconds)."""
    from .. import pairing
    if not cfg.github_username:
        return {"ok": False, "error": "Set up myGeeKy here first (your GitHub username)."}
    token, why = pairing.shareable_token(cfg) if include_token else (None, "Without your token.")
    text = pairing.payload(cfg, token)
    return {"ok": True, "text": text, "matrix": pairing.matrix(text), "with_token": bool(token), "why": why,
            "seconds": pairing.SHOW_SECONDS}


def get_badges(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Your badges (local files only) and your cached GitHub achievements."""
    from .. import achievements
    try:
        cache = __import__("json").loads(__import__("pathlib").Path(achievements.GH_ACHIEVEMENTS_FILE)
                                         .read_text(encoding="utf-8"))
        github = cache.get("items", []) if cache.get("user") == cfg.github_username else []
    except (OSError, ValueError):
        github = []
    every = achievements.earned(cfg)
    return {"all": every, "earned": [b for b in achievements.earned_only(cfg)], "github": github}


def refresh_github_achievements(cfg: MyGeekyConfig) -> list[dict[str, str]]:
    from .. import achievements
    return achievements.github_achievements(cfg.github_username) if cfg.github_username else []


def mark_badges_seen(cfg: MyGeekyConfig, keys: list[str]) -> None:
    cfg.badges_seen = sorted(set(cfg.badges_seen) | set(keys))
    save_config(cfg)


def mark_suggestion_seen(username: str) -> None:
    """Clicking a suggestion means you've looked at them: never suggest them again."""
    if username:
        add_excluded([username.lower()])


def refresh_suggestions(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Runs a real `mygeeky run` -- only ever called from an explicit button click.

    Without a GitHub account only the domain-fit list comes back: people found by searching your field. The
    follow-back list is scored against your own account, so there is nothing to score."""
    if not profile_ready(cfg):
        return {"error": "Run `mygeeky init` in a terminal first."}
    try:
        return _run_suggestions(cfg)
    except Exception as exc:  # surfaced to the panel, not a crash
        return {"error": str(exc)}


def get_contributions(cfg: MyGeekyConfig) -> list[dict[str, Any]]:
    """Repos to show: ones you haven't seen first, from every repo suggested lately."""
    from .. import freshness, papers
    from ..storage import contribution_pool
    try:
        rows = freshness.arrange(cfg, "repo", contribution_pool(), cfg.contribute_max_returned)
    except Exception as exc:     # never let "what's new" stop the panel
        _report_freshness_error(exc)
        rows = last_contributions(cfg.contribute_max_returned)
    return [{**r, "paper": r.get("paper") or papers.cached_paper(r.get("full_name", ""))} for r in rows]


def contributions_top_up_due(cfg: MyGeekyConfig, now: datetime | None = None) -> bool:
    """The Repos tab is running low on repos you haven't seen and the last search is
    old enough: look for more in the background."""
    from .. import freshness
    from ..storage import read_jsonl
    from ..config import CONTRIBUTE_LOG
    if not profile_ready(cfg) or cfg.fresh_repos_topup_hours <= 0:
        return False
    shown = get_contributions(cfg)
    if shown and not freshness.running_low(shown, cfg.contribute_max_returned):
        return False
    records = read_jsonl(CONTRIBUTE_LOG)
    last = records[-1].get("timestamp") if records else None
    if not last:
        return True
    try:
        then = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return True
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - then).total_seconds() >= cfg.fresh_repos_topup_hours * 3600


def mark_seen(keys: list[str], clicked: bool = False) -> None:
    """The panel saw these cards (or you clicked one). Never raises."""
    try:
        from .. import freshness
        freshness.mark_seen(keys, clicked=clicked)
    except Exception:
        pass


def get_trends(cfg: MyGeekyConfig) -> dict[str, Any]:
    """The saved research trends -- local only, no network."""
    from .. import papers
    return papers.load_trends()


def trends_due(cfg: MyGeekyConfig) -> bool:
    from .. import papers
    return profile_ready(cfg) and papers.trends_due(cfg, papers.load_trends())   # OpenAlex: no GitHub needed


def refresh_trends(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    from .. import papers
    try:
        return papers.refresh_trends(cfg, force=force)
    except Exception as exc:   # surfaced in the view, not a crash
        from ..errors import describe
        return {**papers.load_trends(), "error": f"Couldn't update the research trends: {describe(exc)}"}


def repo_people(cfg: MyGeekyConfig, repo: str) -> list[dict[str, Any]]:
    from .. import papers
    try:
        return papers.repo_people(_build_client(cfg), repo)
    except Exception:
        return []


def refresh_contributions(cfg: MyGeekyConfig) -> list[dict[str, Any]] | dict[str, Any]:
    """Runs a real `mygeeky contribute` -- only ever called from an explicit button click."""
    if not profile_ready(cfg):      # public repos matched to your field; your own account is not consulted
        return {"error": "Run `mygeeky init` in a terminal first."}
    try:
        return _run_contribute(cfg)
    except Exception as exc:  # surfaced to the panel, not a crash
        return {"error": str(exc)}


def _followed_only(cache: dict[str, Any]) -> list[dict[str, Any]]:
    """Caches written before 0.2.3 hold strangers' events too; drop them on
    read. Profile-match events were vetted when fetched, so they stay."""
    following = cache.get("following")
    if following is None:
        return cache["events"]
    allowed = {u.lower() for u in following}
    return [e for e in cache["events"]
            if e.get("source") == "match" or (e.get("actor") or "").lower() in allowed]


def _profile_matches(cfg: MyGeekyConfig, following: list[str]) -> list[str]:
    """Your best-scoring recent suggestions (both lists), i.e. people already
    matched against your CV, ORCID and repos and past the quality gates.
    People you follow are skipped -- their activity comes in anyway."""
    if cfg.gui_activity_match_people <= 0:
        return []
    skip = {u.lower() for u in following} | {cfg.github_username.lower()}
    pool = last_suggestions(cfg.gui_activity_match_people, list_type="domain", exclude=skip)         + last_suggestions(cfg.gui_activity_match_people, list_type="followback", exclude=skip)
    seen: set[str] = set()
    picked = []
    for r in sorted(pool, key=lambda r: r.get("score", 0), reverse=True):
        name = r.get("username") or ""
        if name and name.lower() not in seen:
            seen.add(name.lower())
            picked.append(name)
    return picked[: cfg.gui_activity_match_people]


def get_activity(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    if not cfg.github_username:
        return {"events": [], "error": "not configured"}

    cache = load_activity_cache()
    now = datetime.now(timezone.utc)
    if not force and cache:
        try:
            fetched_at = datetime.fromisoformat(cache["fetched_at"])
            age_minutes = (now - fetched_at).total_seconds() / 60
        except (KeyError, ValueError):
            age_minutes = float("inf")
        if age_minutes < cfg.gui_activity_refresh_minutes:
            return {"events": _followed_only(cache), "fetched_at": cache["fetched_at"], "cached": True}

    try:
        client = _build_client(cfg)
        # piggybacks on the same rate-limited refresh, so people you follow
        # from the browser drop out of the suggestions within a few minutes;
        # also restricts the feed to people you actually follow
        following = client.list_following(cfg.github_username)
        # new follows, and repos you starred or forked, teach myGeeKy what you're into
        before = {u.lower() for u in (cache or {}).get("following") or []}
        if before:
            try:
                from .. import interests
                interests.learn_from_github(client, cfg, [u for u in following if u.lower() not in before])
            except Exception:
                pass   # learning is a bonus; the activity feed matters more
        events = get_recent_activity(client, cfg.github_username, limit=cfg.gui_activity_limit,
                                     following=following)
        for e in events:
            e["source"] = "following"
        events += get_matched_activity(client, _profile_matches(cfg, following))
        events.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    except Exception as exc:
        if cache:
            return {"events": _followed_only(cache), "fetched_at": cache["fetched_at"], "cached": True, "error": str(exc)}
        return {"events": [], "error": str(exc)}

    fetched_at_iso = now.isoformat()
    save_activity_cache(events, fetched_at_iso, following)
    return {"events": events, "fetched_at": fetched_at_iso, "cached": False}


def group_activity(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry per person, busiest-recent first: their events newest first,
    and `source` "following" if any of their events came from people you
    follow, else "match"."""
    groups: dict[str, dict[str, Any]] = {}
    for e in sorted(events, key=lambda e: e.get("created_at", ""), reverse=True):
        key = (e.get("actor") or "").lower()
        if not key:
            continue
        g = groups.setdefault(key, {
            "actor": e.get("actor", ""),
            "actor_avatar": e.get("actor_avatar", ""),
            "profile_url": e.get("profile_url", ""),
            "source": "match",
            "latest": e.get("created_at", ""),
            "events": [],
        })
        g["events"].append(e)
        if e.get("source") != "match":
            g["source"] = "following"
    return list(groups.values())


def get_news(cfg: MyGeekyConfig) -> dict[str, Any]:
    """The saved news -- local only, no network."""
    from .. import news
    return news.load_state()


def get_headlines(cfg: MyGeekyConfig) -> dict[str, Any]:
    """The saved headlines -- local only, no network."""
    from .. import headlines
    return headlines.load_state()


def refresh_headlines(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    from .. import headlines
    try:
        return headlines.refresh(cfg, force=force)
    except Exception as exc:   # surfaced in the tab, not a crash
        from ..errors import describe
        return {**headlines.load_state(), "error": f"Couldn't update the headlines: {describe(exc)}"}


def refresh_news_and_headlines(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    return {"news": refresh_news(cfg, force=force), "headlines": refresh_headlines(cfg, force=force)}


def news_mentions(repos: list[str]) -> dict[str, dict[str, Any]]:
    """{owner/name: the story} for repos in this week's news or discussions (local files only)."""
    from .. import badges, headlines, news
    try:
        items = (news.load_state().get("items") or []) + (headlines.load_state().get("items") or [])
        return badges.in_the_news(repos, items)
    except Exception:
        return {}


def news_refresh_due(cfg: MyGeekyConfig) -> bool:
    from .. import news
    from .. import headlines
    return (bool(cfg.news_sources) and news.refresh_due(cfg, news.load_state())) or \
        (cfg.headlines_enabled and headlines.refresh_due(cfg, headlines.load_state()))


def refresh_news(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    from .. import keywords, news
    try:
        keywords.refresh_if_due()   # a newer keyword dictionary, at most once a week
    except Exception:
        pass
    try:
        return news.refresh(cfg, force=force)
    except Exception as exc:   # surfaced in the tab, not a crash
        from ..errors import describe
        return {**news.load_state(), "error": f"Couldn't update the news: {describe(exc)}"}


def sync_enabled(cfg: MyGeekyConfig) -> bool:
    if not cfg.sync_repo or not cfg.sync_auto:
        return False
    try:
        from .. import sync
        return sync.is_initialized() and sync.git_exe() is not None
    except Exception:
        return False


def sync_now(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Two-way sync with your private data repo: this computer's changes go up,
    the other computers' come down. Returns whether anything came down."""
    from .. import sync
    if not sync_enabled(cfg):
        return {"ok": False, "skipped": True}
    try:
        before = sync._git("rev-parse", "HEAD", check=False).stdout.strip()
        message = sync.push()
        after = sync._git("rev-parse", "HEAD", check=False).stdout.strip()
    except Exception as exc:
        from ..errors import describe
        return {"ok": False, "error": describe(exc)}
    return {"ok": True, "changed": before != after, "message": message}


def get_keywords(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Your keywords, each green (the dictionary knows what it means) or red
    (used as a plain word until the dictionary learns it)."""
    from .. import keywords
    rows = []
    for word in cfg.keywords:
        entry = keywords.lookup(word)
        rows.append({"word": word, "known": entry is not None,
                     "related": [keywords.label_of(r) for r, _ in (entry or {}).get("related", [])
                                 if len(r) >= 3][:6]})
    terms = keywords.load()["terms"]
    return {"rows": rows, "version": keywords.load().get("version", ""),
            "vocabulary": sorted({keywords.label_of(t) for t in terms})}


def set_keywords(cfg: MyGeekyConfig, words: list[str]) -> dict[str, Any]:
    """Save your keywords; on Signals, republish your beacon so red ones reach the maker."""
    seen, clean = set(), []
    for w in words:
        w = " ".join(str(w).split())[:40]
        if w and w.lower() not in seen:
            seen.add(w.lower())
            clean.append(w)
    cfg.keywords = clean
    save_config(cfg)
    note = ""
    if cfg.beacon_enabled and auth.get_beacon_token(cfg.github_username):
        try:
            from .. import beacon as bc
            bc.publish(cfg, bc.load_my_beacon())
        except Exception as exc:
            note = f"Saved. (Couldn't update your beacon: {exc})"
    return {"ok": True, "note": note}


def suggest_keyword(word: str) -> bool:
    from .. import ideas
    return open_link(ideas.keyword_url(word))


def is_admin(cfg: MyGeekyConfig) -> bool:
    from .. import admin
    return admin.is_admin(cfg)


# ---- the maker's listing scout (scout.py)
def scout_state() -> dict[str, Any]:
    from .. import scout
    st = scout.load()
    last = st.get("last_run") or {}
    text = ""
    if last.get("at"):
        text = (f"Last look {last['at'][:16].replace('T', ' ')} UTC: {last.get('added', 0)} found, "
                f"{last.get('dropped', 0)} dropped by the checks")
    return {"has_key": bool(scout.get_key()), "new": scout.candidates("new"), "accepted": scout.candidates("accepted"),
            "sources": st["sources"], "focus": st["focus"], "last_run_text": text}


def scout_set_key(key: str) -> bool:
    from .. import scout
    return scout.set_key(key)


def scout_set_sources(sources: list[dict[str, Any]], focus: str) -> None:
    from .. import scout
    scout.set_sources(sources)
    scout.set_focus(focus)


def scout_find(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Slow (reads sites and asks DeepSeek): off the UI thread. Errors come back as {"error"}."""
    from .. import scout
    try:
        return scout.find(cfg)
    except PermissionError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        from ..errors import describe
        return {"error": f"Couldn't finish: {describe(exc)}"}


def scout_set_status(cid: str, status: str, item: dict[str, Any] | None = None) -> bool:
    from .. import scout
    return scout.set_status(cid, status, item)


def scout_publish() -> dict[str, Any]:
    from .. import scout
    try:
        return scout.publish()
    except FileNotFoundError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Couldn't publish: {exc}"}


def github_calls() -> dict[str, Any]:
    """What myGeeKy asked GitHub today, and what it didn't have to ask (ghcache.py).

    GitHub's limit is per person -- your own token gets 5,000 an hour -- so this is about your refreshes
    staying quick, not about GitHub's servers. A 304 ("nothing changed") costs nothing against it."""
    from .. import ghcache
    store = ghcache.store()
    today = store.today()
    asked = int(today.get("requests") or 0)
    free = int(today.get("not_modified") or 0) + int(today.get("from_cache") or 0)
    return {"asked": asked, "not_modified": int(today.get("not_modified") or 0),
            "from_cache": int(today.get("from_cache") or 0), "offline": int(today.get("offline") or 0),
            "searches": int(today.get("searches") or 0), "saved": free, "entries": store.entries(),
            "share": round(100 * free / (asked + free)) if (asked + free) else 0}


def forget_github_cache() -> int:
    """Throw away what GitHub told us. Nothing is lost: the next refresh asks for it again."""
    from .. import ghcache
    store = ghcache.store()
    n = store.entries()
    store.clear()
    return n


def admin_data(cfg: MyGeekyConfig) -> dict[str, Any]:
    """The admin tab from local state (no network), after anything the phone asked for (adminlog.py)."""
    from .. import admin, adminlog
    try:
        adminlog.apply(cfg)
    except Exception:  # noqa: BLE001
        pass
    state = admin.load()
    return {"prospects": admin.prospects(state), "funnel": admin.funnel(state),
            "invited_today": admin.invited_today(state), "inbox": state.get("inbox") or [],
            "adoption": state.get("adoption") or {}, "fetched_at": state.get("updated_at"),
            "keyword_requests": state.get("keyword_requests") or []}


def admin_refresh(cfg: MyGeekyConfig) -> dict[str, Any]:
    from .. import admin, ideas
    if not admin.is_admin(cfg):
        return {"error": "Admin only."}
    try:
        client = _build_client(cfg)
        admin.refresh_prospects(client, cfg)
        state = admin.load()
        state["inbox"] = ideas.inbox(client)
        state["adoption"] = admin.adoption(client)
        from .. import keywords
        state["keyword_requests"] = keywords.keyword_requests(client, cfg)
        admin.save(state)
    except Exception as exc:
        from ..errors import describe
        return {"error": f"Couldn't refresh: {describe(exc)}"}
    return {"ok": True}


def admin_mark(login: str, status: str) -> dict[str, Any]:
    from .. import admin
    return admin.mark(login, status)


def admin_invite(cfg: MyGeekyConfig, person: dict[str, Any]) -> dict[str, str]:
    from .. import admin
    return admin.invite(person, cfg)


def get_brain(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Everything myGeeKy has learned about you, for the Model tab -- local only."""
    from datetime import timedelta
    from .. import interests, papers, scholar
    field = [t["name"] for t in (papers.load_trends().get("topics") or [])]
    if not field:
        field = list(cfg.topics) + scholar.scholar_topics(scholar.load_scholar_profile())
    since = datetime.now(timezone.utc) - timedelta(days=30)
    taught = {"clicks": 0, "follows": 0, "stars": 0, "forks": 0}
    for ev in interests.load_events():
        try:
            if datetime.fromisoformat(ev["at"]) < since:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        kind = ev.get("kind")
        key = {"follow": "follows", "star": "stars", "fork": "forks"}.get(kind, "clicks")
        taught[key] += 1
    return {
        "user": cfg.github_username,
        "field": field[:6],
        "learned": interests.learned_terms(cfg, 10) if cfg.interest_learning else [],
        "explore": interests.explore_terms(cfg, 3) if cfg.explore_share > 0 else [],
        "explore_share": cfg.explore_share,
        "taught": taught,
        "learning": cfg.interest_learning,
        "half_life": cfg.interest_half_life_days,
    }


def get_learned_interests(cfg: MyGeekyConfig) -> list[tuple[str, float]]:
    from .. import interests
    return interests.learned_terms(cfg, 10)


def get_market(cfg: MyGeekyConfig) -> dict[str, Any]:
    """The saved board -- local only, no network."""
    from .. import producthunt
    from ..market import compute_board, load_state
    state = load_state()
    from .. import papers
    rows = [{**r, "paper": papers.cached_paper(r.get("repo", ""))} for r in compute_board(state)]
    return {"rows": rows, "updated_at": state.get("updated_at"),
            "producthunt": producthunt.load_state().get("posts") or [],
            "producthunt_token": bool(cfg.github_username and auth.get_producthunt_token(cfg.github_username))}


def get_hf_models(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Hugging Face models (local only, no network)."""
    from .. import hfmodels
    return hfmodels.load_state()


def refresh_hf_models(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    from .. import hfmodels
    try:
        return hfmodels.refresh(cfg, force=force)
    except Exception as exc:
        from ..errors import describe
        return {**hfmodels.load_state(), "error": f"Couldn't update the models: {describe(exc)}"}


def hf_models_due(cfg: MyGeekyConfig) -> bool:
    from .. import hfmodels
    return cfg.market_hf_enabled and hfmodels.refresh_due(cfg, hfmodels.load_state())


# --------------------------------------------------------------------------- growing: skills, learning, wins
def get_growth(cfg: MyGeekyConfig, save: bool = True) -> dict[str, Any]:
    """Rising Skills, your protocols, learning resources and your wins -- all from
    saved files (no network). Slow-ish (reads everything about your field): call it off the UI thread."""
    from .. import curated, skills, wins
    rising = skills.rising(cfg, save=save)
    wanted = {s["name"].lower(): 0.7 for s in rising["skills"][:6]}
    data = curated.load()
    resources = curated.ranked(cfg, "resources", data=data, extra_terms=wanted)
    from .. import protocols
    return {"rising": rising, "paths": protocols.views(cfg, data), "resources": resources,
            "reviewed": [{"id": p["id"], "skill": p["skill"], "goal": p.get("goal", ""), "title": p["title"],
                          "summary": p.get("summary", "")} for p in protocols.reviewed(data)],
            "wins": wins.recent(), "wins_updated_at": wins.load().get("updated_at"),
            "has_orcid": bool(cfg.orcid_id), "has_github": bool(cfg.github_username)}


def refresh_growth(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    """Fetch the newest curated lists and read your stars, forks and citations (when due), then
    everything as get_growth. Network errors are kept in `error`, never raised."""
    from .. import curated, wins
    errors = []
    try:
        curated.refresh_if_due(force=force)
    except Exception as exc:
        from ..errors import describe
        errors.append(f"Couldn't fetch the newest lists: {describe(exc)}")
    try:
        client = _build_client(cfg) if cfg.github_username else None
        wins.refresh(cfg, client=client, force=force)
    except Exception as exc:
        from ..errors import describe
        errors.append(f"Couldn't read your stars and citations: {describe(exc)}")
    out = get_growth(cfg)
    out["error"] = " ".join(errors)
    return out


def growth_due(cfg: MyGeekyConfig) -> bool:
    from .. import wins
    return profile_ready(cfg) and wins.due(wins.load())


def scout_mailbox(address: str = "", host: str = "", folder: str = "") -> dict[str, Any]:
    """Which mailbox and folder the job alerts are read from. Nothing here is the password."""
    from .. import scout
    return scout.mailbox_settings(address, host, folder)


def scout_set_mail_password(password: str) -> bool:
    """Keep the mailbox password in this computer's credential store, and nowhere else."""
    from .. import mailbox
    return mailbox.set_password(password)


def scout_forget_mail_password() -> None:
    from .. import mailbox
    mailbox.forget_password()


def scout_from_alerts(cfg: MyGeekyConfig, kind: str) -> dict[str, Any]:
    """Read the alert emails in the chosen folder and queue what checks out.

    A third way in beside the sites myGeeKy reads and the pages the maker pastes: the boards that refuse a
    robot will gladly email their listings to anyone who subscribes. Maker-only, like the rest of the
    scout -- it is the maker's own mailbox, read-only, and users only ever see what gets published."""
    from .. import scout
    try:
        return scout.from_alerts(kind)
    except (PermissionError, ValueError) as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def scout_from_paste(cfg: MyGeekyConfig, kind: str, text: str, url: str) -> dict[str, Any]:
    """Read listings out of a page the maker copied by hand.

    The way in for everything a robot cannot have: the aggregators that answer 403 or forbid it in their
    terms, and the university portals that answer with an empty shell because their listings arrive later
    by JavaScript. A person reading a page in their browser and copying it is doing none of that, and the
    checking is unharmed -- the pasted text stands in for the page, so a quote must still be found in it
    word for word."""
    from .. import scout
    try:
        return scout.from_paste(kind, text, url)
    except (PermissionError, ValueError) as exc:
        return {"error": str(exc)}
    except Exception as exc:                       # a network or DeepSeek failure, said plainly
        return {"error": f"{type(exc).__name__}: {exc}"}


def get_seasons(cfg: MyGeekyConfig, today: Any = None) -> dict[str, Any]:
    """The scholarships that come back every year, grouped into the periods people step through.

    {"windows": [...], "at": index of the period we are in, "unverified": n}

    Only seasons with a sentence found on their own page reach anybody; the rest are shown to the maker
    alone, marked, exactly as an accepted-but-unpublished listing is. No network: the periods are worked
    out from the lists already on this computer."""
    from .. import curated, seasons as _seasons
    everything = curated.load().get("seasons") or []
    # eligibility matters more here than anywhere else: MEXT-through-Cairo is for Egyptians and is noise to
    # everyone else. Nobody is made to say where they are from -- an empty answer is shown everything.
    nationality = str(getattr(cfg, "country", "") or "")
    maker = is_admin(cfg)
    windows = _seasons.windows(everything, today, nationality=nationality, only_evidenced=not maker)
    for w in windows:
        for s in w["seasons"]:
            s["unverified"] = not _seasons.evidenced(s)
    offered = _seasons.around(windows, today)
    at = next((i for i, w in enumerate(offered) if w["now"]),
              next((i for i, w in enumerate(offered) if not w["past"]), 0))
    return {"windows": offered, "at": at,
            "unverified": sum(1 for s in everything if not _seasons.evidenced(s)),
            "total": len(everything)}


def get_opportunities(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Verified jobs, funding and conferences, matched to you here (no network)."""
    from .. import curated, interests
    data = curated.load()
    if is_admin(cfg):              # the maker sees what they accepted at once, marked "not published yet"
        try:
            from .. import scout
            pending = scout.candidates("accepted")
        except Exception:
            pending = []
        if pending:
            data = {**data, **{k: list(data.get(k, [])) for k in curated.DATED}}
            have = {it["url"] for k in curated.DATED for it in data[k]}
            for c in pending:
                if c["kind"] in curated.DATED and c["item"]["url"] not in have:
                    data[c["kind"]].append({**c["item"], "pending": True})
    weights = interests.profile_terms(cfg)
    return {kind: curated.ranked(cfg, kind, weights=weights, data=data) for kind in curated.DATED} | {
        "version": data.get("version", "")}


def refresh_opportunities(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    from .. import curated
    error = ""
    try:
        curated.refresh_if_due(force=force)
    except Exception as exc:
        from ..errors import describe
        error = f"Couldn't fetch the newest lists: {describe(exc)}"
    return {**get_opportunities(cfg), "error": error}


def vote(kind: str, item_id: str, up: bool, text: str = "", tags: list[str] | None = None) -> int:
    """👍 / 👎 on a skill, resource, job, call, conference or person. Same thumb again: taken back."""
    from .. import taste
    return taste.vote(kind, item_id, up, text, tags or [])


def vote_of(kind: str, item_id: str) -> int:
    from .. import taste
    return taste.vote_of(kind, item_id)


def unhide(kind: str) -> int:
    """Take back every 👎 on this kind of thing, so they show again."""
    from .. import taste
    return taste.clear(kind, -1)


def report_links(kind: str, item: dict[str, Any]) -> dict[str, str]:
    from .. import curated
    return curated.report_links(kind, item)


# ---- protocols: a skill as ordered stages (protocols.py)
def build_protocol(cfg: MyGeekyConfig, skill: str, goal: str = "") -> dict[str, Any]:
    """Start a protocol for `skill`: the reviewed one if there is one, else one built now from GitHub and
    OpenAlex with the protocol model. Slow (searches): call it off the UI thread. {"id"} or {"error"}."""
    import requests
    from .. import protocols
    skill = " ".join((skill or "").split())[:60]
    if not skill:
        return {"error": "Which skill?"}
    try:
        client = _build_client(cfg)
    except Exception:
        client = None
    try:
        with requests.Session() as session:
            proto = protocols.build(cfg, skill, goal, client=client, session=session)
    except ValueError as exc:
        return {"error": str(exc)}            # myGeeKy doesn't teach this: the reason is already plain
    except Exception as exc:
        from ..errors import describe
        return {"error": f"Couldn't build it: {describe(exc)}"}
    pid = protocols.start(cfg, proto)
    return {"id": pid, "reviewed": proto.get("reviewed", False)} if pid else {"error": "Couldn't build it."}


def protocol_action(cfg: MyGeekyConfig, action: str, pid: str, *args: Any) -> Any:
    """Change one of your protocols: tick, known, quiz, stop, or an edit (move_stage, rename_stage,
    add_stage, remove_stage, move_item, remove_item, add_item)."""
    from .. import protocols
    fn = {"tick": protocols.tick, "known": protocols.mark_known, "quiz": protocols.answer_quiz,
          "stop": protocols.stop, "move_stage": protocols.move_stage, "rename_stage": protocols.rename_stage,
          "add_stage": protocols.add_stage, "remove_stage": protocols.remove_stage,
          "move_item": protocols.move_item, "remove_item": protocols.remove_item,
          "add_item": protocols.add_item}.get(action)
    return fn(cfg, pid, *args) if fn else None


def publish_protocol(cfg: MyGeekyConfig, pid: str) -> dict[str, str]:
    """The prefilled public issue for one of your protocols (you press Submit, with your own account):
    {"url", "clipboard"} -- clipboard holds the protocol to paste when it's too long for a link."""
    from .. import protocols
    entry = protocols.mine(cfg).get(pid)
    return protocols.publish(entry) if entry else {"url": "", "clipboard": ""}


# ---- quizzes: a protocol's questions, marked here (quiz.py)
def quiz_state(cfg: MyGeekyConfig, pid: str = "") -> dict[str, Any]:
    """What there is to take and what you scored: {"best", "counts", "can_try", "why", "badge"}."""
    from .. import protocols, quiz
    entry = protocols.mine(cfg).get(pid) if pid else None
    proto = entry["protocol"] if entry else None
    counts = quiz.counts(pid, (proto or {}).get("based_on", "")) if pid else {}
    ok, why = quiz.can_try(pid) if pid else (False, "")
    return {"best": quiz.best(pid) if pid else quiz.best(), "counts": counts, "can_try": ok, "why": why,
            "per_attempt": quiz.PER_ATTEMPT, "pass_mark": quiz.PASS, "flags": quiz.flags()}


def quiz_overview(cfg: MyGeekyConfig, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Everything the 🏆 Quiz tab shows: one row per protocol that has questions (yours first, then the
    reviewed ones you haven't started), your best scores, and what's left to try today."""
    from .. import curated, protocols, quiz
    data = data or curated.load()
    best = quiz.best()
    flags = set(quiz.flags())
    rows, seen = [], set()

    def row(proto: dict[str, Any], mine: bool) -> dict[str, Any] | None:
        counts = quiz.counts(proto["id"], proto.get("based_on", ""), None)
        if not counts["total"]:
            return None
        got = best.get(proto["id"]) or {}
        ok, why = quiz.can_try(proto["id"]) if mine else (True, "")
        return {"id": proto["id"], "title": proto["title"], "skill": proto["skill"], "mine": mine,
                "counts": counts, "best": got, "score": float(got.get("score") or 0.0),
                "can_try": ok and mine, "why": "" if mine else "Start this protocol to take its quiz",
                "why_not": why, "flagged": sum(1 for q in quiz.for_protocol(proto["id"], proto.get("based_on", ""))
                                               if q["id"] in flags)}

    for entry in protocols.mine(cfg, data).values():
        r = row(entry["protocol"], True)
        seen.add(entry["protocol"]["id"])
        if r:
            rows.append(r)
    for proto in protocols.reviewed(data):
        if proto["id"] not in seen:
            r = row(proto, False)
            if r:
                rows.append(r)
    done = [r for r in rows if r["best"]]
    with_quiz = {r["id"] for r in rows}
    waiting = [e["protocol"]["title"] for pid, e in protocols.mine(cfg, data).items() if pid not in with_quiz]
    return {"rows": rows, "waiting": waiting, "taken": len(done),
            "average": round(sum(r["score"] for r in done) / len(done), 4) if done else 0.0,
            "perfect": sum(1 for r in done if r["score"] >= 1.0), "flagged": len(flags),
            "questions": len(quiz.bank()["questions"]), "per_attempt": quiz.PER_ATTEMPT,
            "pass_mark": quiz.PASS, "mix": quiz.share()}


def quiz_unflag_all() -> int:
    """Take back every 🚩: those questions can come up again."""
    from .. import quiz
    gone = quiz.flags()
    for qid in gone:
        quiz.flag(qid, False)
    return len(gone)


def quiz_draw(cfg: MyGeekyConfig, pid: str, stage: str = "") -> Any:
    """A quiz for one of your protocols (`stage`: the level check for one step only). None if there's none."""
    from .. import protocols, quiz
    entry = protocols.mine(cfg).get(pid)
    if not entry:
        return None
    q = quiz.Quiz.draw(entry["protocol"], n=quiz.PER_ATTEMPT, flags=quiz.flags(), stage=stage)
    return q if q.questions else None


def quiz_mark(cfg: MyGeekyConfig, quiz_obj: Any, answers: list[int], stage: str = "") -> Any:
    """Mark an attempt, keep the best score, and -- for a step's check -- mark that step as known if passed."""
    from .. import protocols, quiz
    before = float((quiz.best(quiz_obj.protocol) or {}).get("score") or 0.0)
    attempt = quiz.mark(quiz_obj, answers, before)
    if not stage:
        quiz.record(attempt)
    elif attempt.passed:
        protocols.answer_quiz_score(cfg, quiz_obj.protocol, stage, attempt.score)
    return attempt


def quiz_flag(qid: str, on: bool = True) -> bool:
    from .. import quiz
    return quiz.flag(qid, on)


def quiz_report(question: Any, reason: str = "") -> str:
    from .. import quiz
    return quiz.report_question(question, reason)


def quiz_refresh(force: bool = False) -> dict[str, Any]:
    """Fetch the newest question bank (like the curated lists). Never raises."""
    from .. import quiz
    try:
        return {"changed": quiz.refresh_if_due(force=force)}
    except Exception as exc:
        from ..errors import describe
        return {"error": f"Couldn't fetch the questions: {describe(exc)}"}


# ---- showing a score on mygeeky.org: only if you ask, from your own account (leaderboard.py)
def share_state(cfg: MyGeekyConfig, share_name: bool = False, share_scores: bool = False) -> dict[str, Any]:
    """What would appear on the website, in plain words, before anything is sent anywhere."""
    from .. import leaderboard
    share = leaderboard.share_of(cfg, share_name, share_scores)
    ok, why = leaderboard.can_share(share)
    return {"lines": share.lines(), "ok": ok, "why": why, "login": share.login,
            "scores": share.shown_scores, "titles": share.titles, "min_shown": leaderboard.MIN_SHOWN}


def share_url(cfg: MyGeekyConfig, share_name: bool, share_scores: bool) -> str:
    """The prefilled issue where *you* write `accept`, from your own GitHub account. "" if nothing to share."""
    from .. import leaderboard
    share = leaderboard.share_of(cfg, share_name, share_scores)
    ok, _ = leaderboard.can_share(share)
    return leaderboard.accept_url(share) if ok else ""


def withdraw_url(cfg: MyGeekyConfig) -> str:
    """How to take it back: the same issue, where you write `withdraw`."""
    from .. import ideas
    login = (cfg.github_username or "").strip()
    return f"https://github.com/{ideas.IDEAS_REPO}/issues?q=is%3Aissue+label%3Aleaderboard+author%3A{login}"


# ---- the maker's quiz writer (quizwriter.py)
def quizwriter_state() -> dict[str, Any]:
    from .. import quiz, quizwriter, scout
    state = quizwriter.load()
    bank = quiz.bank()
    per: dict[str, dict[str, int]] = {}
    for q in bank["questions"]:
        per.setdefault(q["protocol"], {lv: 0 for lv in quiz.LEVELS})[q["level"]] += 1
    from .. import curated, protocols
    reviewed = [p["id"] for p in protocols.reviewed(curated.load())]
    ready = [pid for pid in reviewed if sum((per.get(pid) or {}).values()) >= quizwriter.READY]
    return {"has_key": bool(scout.get_key()), "bank": len(bank["questions"]), "per_protocol": per,
            "batches": state["batches"], "want": quizwriter.PER_PROTOCOL, "ready": quizwriter.READY,
            "good": quizwriter.GOOD, "protocols": len(reviewed), "with_quiz": len(ready),
            "missing": [pid for pid in reviewed if pid not in ready]}


def quizwriter_run(cfg: MyGeekyConfig, pid: str) -> dict[str, Any]:
    """Write and check a batch of questions for one protocol. Slow (reads pages, asks DeepSeek)."""
    import requests
    from .. import curated, protocols, quiz, quizwriter, scout
    key = scout.get_key()
    if not key:
        return {"error": "Add your DeepSeek key first."}
    proto = next((p for p in protocols.reviewed(curated.load()) if p["id"] == pid), None)
    if not proto:
        return {"error": "No reviewed protocol with that id."}
    have = [q["q"] for q in quiz.bank()["questions"] if q["protocol"] == pid]
    try:
        with requests.Session() as session:
            batch = quizwriter.write_for(proto, key, session=session, existing=have)
    except PermissionError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        from ..errors import describe
        return {"error": f"Couldn't finish: {describe(exc)}"}
    quizwriter.keep_batch(pid, batch)
    return {**batch, "summary": quizwriter.summary(batch), "reasons": quizwriter.reasons(batch)}


def quizwriter_accept(pid: str, verdict: str) -> dict[str, Any]:
    """The maker's spot check: "accepted" puts the batch in the shipped bank, "rewrite" throws it away."""
    from .. import quizwriter
    state = quizwriter.load()
    batch = state["batches"].get(pid)
    if not batch:
        return {"error": "Nothing to accept."}
    quizwriter.set_verdict(pid, verdict)
    if verdict != "accepted":
        return {"added": 0, "rewrite": True}
    try:
        return quizwriter.add_to_bank(quizwriter.balance(batch["questions"]))
    except Exception as exc:
        return {"error": f"Couldn't write the bank: {exc}"}


def get_collaborators(cfg: MyGeekyConfig, rising: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fellow myGeeKy users whose skills complement yours (from saved beacons; no network).
    `rising` is Grow's own result when it has one: reusing it skips reading your whole field and CV again."""
    from .. import beacon as bc, collab, interests, skills
    if not cfg.github_username or not cfg.beacon_enabled:
        return {"enabled": False, "people": [], "hidden": 0}
    cache, mine = bc.load_cache(), bc.load_my_beacon()
    try:
        weights = interests.profile_terms(cfg)
    except Exception:
        weights = {}
    people = bc.people(cache, cfg, mine, private_key=bc.private_key_or_none(cfg), weights=weights)
    if not (isinstance(rising, dict) and "have" in rising):
        rising = skills.rising(cfg, save=False, top=20)
    have = set(rising["have"]) | {"Git"}
    wanted = [s["name"] for s in rising["skills"]]
    strengths = [s["name"] for s in rising["strengths"]]
    can_send = auth.get_beacon_token(cfg.github_username) is not None
    return {"enabled": True, "can_send": can_send,
            **collab.matches(people, have, wanted, bc._sent_to(mine, "collab"), strengths=strengths)}


def market_refresh_due(cfg: MyGeekyConfig, now: datetime | None = None) -> bool:
    from ..market import load_state
    updated = load_state().get("updated_at")
    if not updated:
        return True
    try:
        age = (now or datetime.now(timezone.utc)) - datetime.fromisoformat(updated)
    except ValueError:
        return True
    return age.total_seconds() >= cfg.market_refresh_hours * 3600


def refresh_market(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    if not profile_ready(cfg):      # the board is public repos in YOUR field, not anything about your account
        return {"rows": [], "error": "Run `mygeeky init` in a terminal first."}
    try:
        from ..cli import _run_market
        _run_market(cfg, force=force)
    except Exception as exc:  # surfaced to the panel, not a crash
        return {**get_market(cfg), "error": str(exc)}
    return get_market(cfg)


def get_signals(cfg: MyGeekyConfig, force: bool = False) -> dict[str, Any]:
    """Beacon signals for the Signals tab. Re-reads everyone's beacons only
    when `beacon_refresh_minutes` have passed (or on a Refresh click)."""
    from .. import beacon as bc
    if not cfg.github_username or not cfg.beacon_enabled:
        return {"enabled": False, "incoming": [], "people": []}
    cache, error = bc.load_cache(), None
    if force or bc.refresh_due(cfg, cache):
        try:
            cache = bc.refresh(_build_client(cfg), cfg, force=True)
        except Exception as exc:  # surfaced to the panel, not a crash
            error = str(exc)
    can_send = auth.get_beacon_token(cfg.github_username) is not None
    if can_send:
        try:   # after an update: publish this computer's key once, so others can send to you
            bc.ensure_published(cfg)
        except Exception as exc:
            error = error or f"Couldn't update your beacon: {exc}"
    key = bc.private_key_or_none(cfg)
    mine = bc.load_my_beacon()
    incoming = bc.inbox(cache, cfg, mine, key)
    from .. import interests
    try:
        weights = interests.profile_terms(cfg)      # local files only: your work never leaves this computer
    except Exception:
        weights = {}
    return {
        "enabled": True,
        "can_send": can_send,
        "quiet": cfg.beacon_quiet,
        "incoming": [] if cfg.beacon_quiet else incoming,
        "held": len(incoming) if cfg.beacon_quiet else 0,
        "people": bc.people(cache, cfg, mine, private_key=key, weights=weights),
        "calls": bc.calls_for_me(cache, cfg, mine, weights=weights),
        "my_calls": bc.my_calls(cache, cfg, incoming),
        "fetched_at": cache.get("fetched_at"),
        "error": error,
    }


def send_signal(cfg: MyGeekyConfig, to: str, gesture: str, repo: str | None = None) -> dict[str, Any]:
    """Only ever called from a click on Send (or a gesture button)."""
    from .. import beacon as bc
    try:
        bc.send(cfg, to, gesture, repo)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


# --------------------------------------------------------------------------- calls for contributors
def _beacon_action(fn, *args, **kwargs) -> dict[str, Any]:
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "result": result}


def create_call(cfg: MyGeekyConfig, repo: str, note: str, skills: list[str], level: str, time: str,
                days: int) -> dict[str, Any]:
    """Only ever called from Publish in the invite window."""
    from .. import beacon as bc
    return _beacon_action(bc.create_call, cfg, repo, note, skills, level, time, days)


def close_call(cfg: MyGeekyConfig, call_id: str, filled: bool) -> dict[str, Any]:
    from .. import beacon as bc
    return _beacon_action(bc.close_call, cfg, call_id, filled)


def join_call(cfg: MyGeekyConfig, call: dict[str, Any]) -> dict[str, Any]:
    """I'm in: a sealed signal to the caller, and your model learns from it like a fork."""
    from .. import beacon as bc
    from .. import interests
    out = _beacon_action(bc.join_call, cfg, call["owner"], call["id"], call.get("matched") or [])
    if out["ok"]:
        try:
            interests.record("join", text=call.get("note", ""), topics=call.get("skills") or [],
                             source=call.get("full_name", ""), cfg=cfg)
        except Exception:
            pass
    return out


def leave_call(cfg: MyGeekyConfig, owner: str, call_id: str) -> dict[str, Any]:
    from .. import beacon as bc
    return _beacon_action(bc.leave_call, cfg, owner, call_id)


def hide_call(owner: str, call_id: str) -> None:
    from .. import beacon as bc
    bc.hide_call(owner, call_id)


def list_repos_for_call(cfg: MyGeekyConfig, login: str | None = None) -> list[dict[str, Any]]:
    """Public repos (your own by default) for the invite and signal windows: name, topics,
    language, newest first. Forks, archived repos and your beacon are left out."""
    from .. import beacon as bc
    login = login or cfg.github_username
    if not login:
        return []
    try:
        repos = _build_client(cfg).list_repos(login, max_pages=1)
    except Exception:
        return []
    out = []
    for r in repos:
        if r.get("fork") or r.get("archived") or r.get("private") or r.get("name") == bc.BEACON_REPO:
            continue
        out.append({"name": r.get("name") or "", "full_name": r.get("full_name") or "",
                    "topics": [t.replace("-", " ") for t in (r.get("topics") or [])][:8],
                    "language": r.get("language") or "", "description": r.get("description") or ""})
    return out


def set_signals_quiet(cfg: MyGeekyConfig, quiet: bool) -> dict[str, Any]:
    from .. import beacon as bc
    try:
        bc.set_quiet(cfg, quiet)
    except Exception as exc:
        cfg.beacon_quiet = not quiet
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


def mute_signals(cfg: MyGeekyConfig, login: str, mute: bool = True) -> None:
    """Hide (or show again) someone's signals. They're never told."""
    from .. import beacon as bc
    bc.set_muted(cfg, login, mute)


def get_model_history() -> list[dict[str, Any]]:
    return load_model_history()


FEATURE_LABELS = {
    "content_similarity": "Content match",
    "follow_back_ratio": "Follows people back",
    "activity_recency": "Recently active",
    "shared_languages": "Shared languages",
    "shared_topics": "Shared topics",
}


def get_model_weights() -> list[dict[str, Any]]:
    """What the trained model rewards (+) and penalizes (-): the logistic
    regression's coefficients on standardized features, so their sizes are
    comparable. Empty when no model has been trained yet."""
    from ..matcher import FEATURE_NAMES, LearnedModel

    model = LearnedModel.load()
    if not model.is_trained:
        return []
    try:
        coef = model.pipeline[1].coef_[0]
    except (AttributeError, IndexError, TypeError):
        return []
    weights = [{"feature": name, "label": FEATURE_LABELS.get(name, name), "weight": float(c)}
               for name, c in zip(FEATURE_NAMES, coef)]
    return sorted(weights, key=lambda w: abs(w["weight"]), reverse=True)


def auc_verdict(auc: float | None) -> tuple[str, str]:
    """(short grade, one-line explanation) for a cross-validated AUC."""
    if auc is None:
        return "Untrained", "Run mygeeky bootstrap to teach it who follows back."
    if auc >= 0.8:
        return "Sharp", "Reliably tells who will follow you back."
    if auc >= 0.7:
        return "Good", "Clearly better than chance at spotting follow-backs."
    if auc >= 0.6:
        return "Learning", "Some signal -- more follow-backs will sharpen it."
    return "Early", "Barely above a coin flip; keep running mygeeky learn."


def get_friend_stats(cfg: MyGeekyConfig) -> dict[str, Any]:
    """Friend-count and follow-back stats for the Live tab -- built entirely
    from local data already on disk (the last following snapshot and the
    labeled training examples logged by `learn`/`bootstrap`), so viewing it
    never triggers a network call of its own."""
    total_friends = len(load_following_snapshot())

    examples = load_training_examples()
    now = datetime.now(timezone.utc)
    new_this_week = 0
    for e in examples:
        try:
            ts = datetime.fromisoformat(e.get("timestamp", ""))
        except ValueError:
            continue
        if (now - ts).days < 7:
            new_this_week += 1

    total_labeled = len(examples)
    positives = sum(1 for e in examples if e.get("label") == 1)
    follow_back_rate = (positives / total_labeled) if total_labeled else None

    return {
        "total_friends": total_friends,
        "new_this_week": new_this_week,
        "follow_back_rate": follow_back_rate,
        "total_labeled": total_labeled,
    }


def person_card(login: str) -> dict[str, Any]:
    """Someone at a glance (see profile_card.py); uses your read token if any."""
    from .. import profile_card
    cfg = load_config()
    token = auth.get_token(cfg.github_username) if cfg.github_username else None
    return profile_card.fetch(login, token)


def open_profile(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        return False
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(url))
    return True


LINK_PREFIXES = ("https://github.com/", "https://www.producthunt.com/posts/", "https://arxiv.org/abs/",
                 "https://www.producthunt.com/products/", "https://huggingface.co/",
                 "https://www.biorxiv.org/content/", "https://news.ycombinator.com/item?id=",
                 "https://doi.org/", "https://orcid.org/", "https://openalex.org/")


def _curated_link(url: str) -> bool:
    """A link from the maker's curated lists (jobs, funding, conferences, resources), a learning-path
    search, or a report to support: those, and only those, may go anywhere https."""
    if url.startswith(("mailto:support@mygeeky.org?", "https://github.com/search?",
                       "https://github.com/mygeeky/myGeeKy-ideas/issues/new?")):
        return True
    try:
        from .. import curated
        data = curated.load()
        if any(url == it.get("url") for kind in curated.LISTS for it in data.get(kind, [])):
            return True
        from .. import scout             # a listing the scout found, for you to check
        if any(url == c["item"]["url"] for c in scout.load()["candidates"].values()):
            return True
        from .. import protocols         # a link in a reviewed protocol, or in one of yours
        for p in protocols.reviewed(data) + [e["protocol"] for e in protocols.mine().values()]:
            if any(url == it["url"] for st in p["stages"] for it in st["items"]):
                return True
        return False
    except Exception:
        return False


def open_link(url: str) -> bool:
    """Like open_profile, but also lets Product Hunt launch pages through."""
    from .. import headlines
    if not isinstance(url, str) or not (url.startswith(LINK_PREFIXES) or headlines.allowed_link(url)
                                        or _curated_link(url)):
        return False
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(url))
    return True


def _panel_geometry(cfg: MyGeekyConfig, folded: bool, screen_rect,
                    min_width: int = 0, min_height: int = 0) -> tuple[int, int, int, int]:
    """Returns (x, y, width, height) docked to the configured edge of
    `screen_rect` (the screen's available area, i.e. minus the taskbar).
    On the left or right edge it sits in the middle, folded or open. In a
    bottom corner the folded icon sits in the corner, and the open panel
    rises to the middle of that edge.

    `min_width`/`min_height` are what the content actually needs: Qt won't
    shrink a window below that, so the position is computed from the real
    size -- otherwise a right-docked panel wider than configured hangs off
    the right edge onto the neighbouring monitor. The result always stays
    inside `screen_rect`, whatever its (possibly negative) origin."""
    if folded:
        width, height = cfg.gui_folded_width, cfg.gui_folded_height
    else:
        width, height = cfg.gui_expanded_width, int(screen_rect.height() * clamp_panel_height(cfg.gui_panel_height_fraction))
    width = min(max(width, min_width), screen_rect.width())
    height = min(max(height, min_height), screen_rect.height())
    side = dock_side(cfg)
    if folded and side.startswith("bottom"):
        y = screen_rect.y() + screen_rect.height() - height
    else:
        y = screen_rect.y() + (screen_rect.height() - height) // 2
    x = screen_rect.x() if side.endswith("left") else screen_rect.x() + screen_rect.width() - width
    return x, y, width, height


# A native Windows DWM Acrylic backdrop (DwmExtendFrameIntoClientArea +
# DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE=3)) was tried here and
# deliberately removed: isolated side-by-side testing (two otherwise-
# identical minimal Qt windows, one with the DWM calls and one without)
# showed it reliably turns an already-working, genuinely transparent Qt
# window (WA_TranslucentBackground) fully opaque instead -- reproduced with
# and without window focus, so it isn't a focus-dependent Windows rendering
# quirk. Qt's own translucency is what actually ships; layering DWM's
# system backdrop on top of it made things strictly worse on this setup.


def main() -> None:
    """Start the panel. It usually runs without a console (pythonw), so a
    failure must be shown in a message box -- otherwise it just never appears."""
    import sys
    from ..config import LOG_DIR
    from ..errors import ISSUES_URL, describe, save_crash_report, show_message_box

    from .. import crashreport, use_system_certificates
    use_system_certificates()
    # every error from here on (main thread, background threads, hard crashes) is
    # saved as a report; once the panel is up it offers to send it (see _main)
    crashreport.install(LOG_DIR, on_report=lambda path: _CRASH_INBOX.append(path), keep_stderr=True)
    try:
        _main()
    except SystemExit:
        raise
    except Exception as exc:
        report = save_crash_report(exc, LOG_DIR, "panel start-up")
        show_message_box("myGeeKy couldn't start",
                         f"{describe(exc)}\n\n"
                         + (f"Full details were saved to:\n{report}\n\n" if report else "")
                         + f"If it keeps happening, please report it at {ISSUES_URL}")
        raise SystemExit(1)


def _main() -> None:
    import os
    import sys
    from .bootstrap import ensure_qt
    ensure_qt()  # installs Qt on first use, wherever this Python can hold it
    # Linux desktops without the xdg-desktop-portal "Settings" interface make Qt's
    # GNOME theme code log a harmless dbus error on every start; it only means Qt
    # can't ask the desktop for its dark/light preference. Keep the terminal quiet.
    rules = os.environ.get("QT_LOGGING_RULES", "")
    if "qt.qpa.theme" not in rules:
        os.environ["QT_LOGGING_RULES"] = ";".join(r for r in (rules, "qt.qpa.theme.gnome=false") if r)

    from PySide6.QtCore import QLockFile
    from PySide6.QtWidgets import QApplication

    from ..config import DATA_DIR, ensure_dirs
    from .qt_panel import ICON_WINDOW, MyGeekyPanel

    # One panel at a time: the Start menu, the sign-in shortcut and the
    # installer can all launch it. A crashed panel's lock is detected as
    # stale (its process is gone) and taken over. `*.lock` is never synced.
    ensure_dirs()
    lock = QLockFile(str(DATA_DIR / "panel.lock"))
    if not lock.tryLock(200):
        _bring_running_panel_forward()   # don't just do nothing: the panel may be folded at the edge
        return
    try:                                   # an older weekly task opened a console every Monday
        import threading
        from .. import scheduler
        def tidy_weekly_task() -> None:
            scheduler.make_windowless()
            if scheduler.is_installed():
                scheduler.catch_up_settings()     # tasks made before this: run when missed, and on battery
        threading.Thread(target=tidy_weekly_task, daemon=True).start()
    except Exception:
        pass

    from .macos import set_app_name
    set_app_name()                           # macOS: the menu bar says myGeeKy, not Python
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("mygeeky")
    if sys.platform == "darwin":
        app.setApplicationDisplayName("myGeeKy")   # elsewhere Qt would add it to every window title
    if sys.platform.startswith("linux"):
        app.setDesktopFileName("mygeeky")    # the dock/taskbar uses the menu entry's icon
    if ICON_WINDOW.exists():
        from PySide6.QtGui import QIcon
        app.setWindowIcon(QIcon(str(ICON_WINDOW)))
    from PySide6.QtCore import qInstallMessageHandler
    from .. import crashreport
    from ..config import LOG_DIR
    qInstallMessageHandler(crashreport.qt_message_handler(LOG_DIR))
    cfg = load_config()
    splash = _play_intro_once(cfg)
    panel = MyGeekyPanel(cfg)
    panel.show()
    if splash is not None:
        splash.finish()
    from .macos import keep_on_all_spaces
    keep_on_all_spaces(panel)                # macOS: stay at the edge on every Space, beside full-screen apps
    _watch_crashes(panel, cfg.github_username)
    _say_if_settings_recovered(panel)
    _listen_for_second_start(panel)
    app.exec()
    crashreport.clean_fatal_log(LOG_DIR)
    # Quitting mid-refresh: let running work finish (everything is saved as it happens).
    # A thread stuck in a slow download can't be stopped, and Qt aborts if it's still
    # running at exit, so after a few seconds leave without waiting for it.
    from .qt_panel import _Worker
    if _Worker.drain(5000):
        _leave_now()


def _leave_now() -> None:
    """Exit at once, with background work still running. On Windows even
    os._exit unloads Qt, which aborts over the running threads, and that abort
    would come back as a crash report on the next start, so end the process
    directly; and stop recording fatal errors first."""
    import faulthandler
    import os
    import sys
    faulthandler.disable()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.TerminateProcess(k32.GetCurrentProcess(), 0)
    os._exit(0)


def _play_intro_once(cfg: MyGeekyConfig):
    """The first time the panel starts: the badge animates in the middle of the screen
    while the panel is built. Never stops myGeeKy from starting."""
    if cfg.gui_intro_shown:
        return None
    cfg.gui_intro_shown = True
    save_config(cfg)                       # once, even if something below fails
    try:
        from .splash import make_splash
        splash = make_splash()
        splash.play()
        return splash
    except Exception:
        return None


def _instance_name() -> str:
    import getpass
    import re
    try:
        user = getpass.getuser()
    except Exception:
        user = "user"
    return "mygeeky-panel-" + re.sub(r"[^A-Za-z0-9_.-]", "_", user)   # per user: one machine, several people


def _listen_for_second_start(panel) -> None:
    """Starting myGeeKy again (Start menu, desktop icon) brings this panel forward."""
    from PySide6.QtNetwork import QLocalServer
    server = QLocalServer(panel)
    QLocalServer.removeServer(_instance_name())          # a leftover from a crashed panel
    if not server.listen(_instance_name()):
        return

    def on_connect() -> None:
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.disconnectFromServer()
        try:
            panel.unfold()
        except Exception:
            pass
        panel.show()
        panel.raise_()
        panel.activateWindow()
    server.newConnection.connect(on_connect)
    panel._instance_server = server


def _bring_running_panel_forward() -> None:
    try:
        from PySide6.QtNetwork import QLocalSocket
        sock = QLocalSocket()
        sock.connectToServer(_instance_name())
        if sock.waitForConnected(1000):
            sock.disconnectFromServer()
    except Exception:
        pass


def _say_if_settings_recovered(panel) -> None:
    """config.json was damaged (e.g. a power cut during a save) and was restored from a copy."""
    from .. import config
    if not config.RECOVERED_FROM:
        return
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox
    source = ("the copy saved just before the last change" if config.RECOVERED_FROM == "config.previous.json"
              else "your last backup of them" if config.RECOVERED_FROM.startswith("config.backup")
              else "the copy synced from your other computers" if config.RECOVERED_FROM == "config.synced.json"
              else "the defaults (no good copy was found)")
    box = QMessageBox(QMessageBox.Information, "myGeeKy",
                      "Your settings file was damaged (this happens if the computer turns off while it's being "
                      f"saved), so myGeeKy restored your settings from {source}.\n\nThe damaged file was kept "
                      f"next to it as {config.CONFIG_FILE.name}.broken-…, in {config.CONFIG_FILE.parent}. "
                      "If anything looks wrong, check ⚙ Settings.", QMessageBox.Ok, panel)
    box.setWindowFlag(Qt.WindowStaysOnTopHint, True)     # in front of the panel, without locking it
    box.setWindowModality(Qt.NonModal)
    box.setAttribute(Qt.WA_DeleteOnClose, True)
    box.show()


_CRASH_INBOX: list = []      # reports saved by any thread, waiting to be offered on the main one


def _watch_crashes(panel, login: str) -> None:
    """Offer reports: any left from earlier runs (incl. a hard crash) a few seconds after
    start, then new ones as they happen. Reports are collected from every thread and
    shown from the main one."""
    from PySide6.QtCore import QTimer
    from .. import crashreport
    from ..config import LOG_DIR
    from .crash_dialog import CrashDialog
    _CRASH_INBOX.extend(p for p in crashreport.pending(LOG_DIR) if p not in _CRASH_INBOX)

    def offer() -> None:
        if not _CRASH_INBOX:
            return
        new, _CRASH_INBOX[:] = list(_CRASH_INBOX), []
        dlg = getattr(panel, "_crash_dialog", None)
        try:
            if dlg is not None and dlg.isVisible():
                for p in reversed(new):
                    dlg.add(p)
                return
        except RuntimeError:            # its window was closed and deleted
            pass
        theme = THEMES.get(getattr(panel, "_theme_name", lambda: "")(), None)
        panel._crash_dialog = CrashDialog(panel, new, LOG_DIR, login, theme)
        panel._crash_dialog.show()
        panel._crash_dialog.raise_()

    timer = QTimer(panel)
    timer.timeout.connect(offer)
    QTimer.singleShot(4000, lambda: (offer(), timer.start(3000)))   # let the panel settle first


if __name__ == "__main__":
    main()
