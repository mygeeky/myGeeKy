"""Configuration storage for myGeeKy.

All state lives under the OS-appropriate user config/data directories
(via `platformdirs`) -- never inside the project/repo itself, so nothing
personal (CV keywords, search parameters, learned model) ever risks being
committed or published by accident.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_data_dir

from .files import write_json

APP_NAME = "mygeeky"

CONFIG_DIR = Path(user_config_dir(APP_NAME))
DATA_DIR = Path(user_data_dir(APP_NAME))
# Live databases (the GitHub cache, WISEP) sit beside the data folder, never in it: the data folder is a git repo that
# sync carries between computers, and a database replaced under a running program is damaged.
LOCAL_DIR = DATA_DIR.parent / f"{DATA_DIR.name}-local"

CONFIG_FILE = CONFIG_DIR / "config.json"
PREVIOUS_CONFIG_FILE = CONFIG_DIR / "config.previous.json"   # the version before the last save
SUGGESTIONS_LOG = DATA_DIR / "suggestions_history.jsonl"
TRAINING_LOG = DATA_DIR / "training_data.jsonl"
FOLLOWING_SNAPSHOT = DATA_DIR / "following_snapshot.json"
EXCLUDED_FILE = DATA_DIR / "excluded.json"
MODEL_FILE = DATA_DIR / "model.pkl"
MODEL_HISTORY_LOG = DATA_DIR / "model_history.jsonl"
ACTIVITY_CACHE_FILE = DATA_DIR / "activity_cache.json"
CV_TEXT_FILE = DATA_DIR / "cv_text.txt"
SCHOLAR_PROFILE_FILE = DATA_DIR / "scholar_profile.json"
CONTRIBUTE_LOG = DATA_DIR / "contribute_history.jsonl"
MARKET_FILE = DATA_DIR / "market.json"
PRODUCTHUNT_FILE = DATA_DIR / "producthunt.json"
UPDATE_CHECK_FILE = DATA_DIR / "update_check.json"   # last PyPI version check; never synced
TOKEN_CHECK_FILE = DATA_DIR / "token_check.json"     # tokens' expiry dates (never the tokens); never synced
INTEREST_EVENTS_FILE = DATA_DIR / "interest_events.jsonl"   # terms from what you click/follow/star (synced)
INTEREST_SEEN_FILE = DATA_DIR / "interest_seen.json"        # your stars/forks already learned from
NEWS_FILE = DATA_DIR / "news.json"
TRENDS_FILE = DATA_DIR / "trends.json"                 # research trends from OpenAlex
PAPERS_CACHE_FILE = DATA_DIR / "papers_cache.json"     # repo -> its published paper (the [P] badge)
USAGE_FILE = DATA_DIR / "usage.jsonl"                 # what kinds of things you open (badges); synced
WHOIS_FILE = DATA_DIR / "whois.json"                   # "Is this you?": a pending search and what it found; never synced
NOTIFY_STATE_FILE = DATA_DIR / "notify_state.json"     # when you were last notified, and what was told; never synced
RANK_SEEN_FILE = DATA_DIR / "rank_seen.json"           # the last rank you were told about (My month); never synced
MY_GITHUB_EVENTS_FILE = DATA_DIR / "my_github_events.json"   # your own GitHub events, slimmed (My month); never synced
GH_ACHIEVEMENTS_FILE = DATA_DIR / "github_achievements.json"   # your GitHub achievements, cached
HF_MODELS_FILE = DATA_DIR / "hf_models.json"         # Hugging Face models trending in your field
HEADLINES_FILE = DATA_DIR / "headlines.json"          # AI, science and tech headlines, ranked for you
ADMIN_FILE = DATA_DIR / "admin_prospects.json"         # the maker's admin tab: prospects and invites
SYNCED_CONFIG_FILE = DATA_DIR / "config.synced.json"
LOG_DIR = DATA_DIR / "logs"
AVATAR_CACHE_DIR = DATA_DIR / "avatar_cache"
MY_BEACON_FILE = DATA_DIR / "beacon.json"          # what you publish to <you>/mygeeky-beacon
BEACON_CACHE_FILE = DATA_DIR / "beacons_cache.json"  # everyone else's beacons, last read
# Who myGeeKy's own commits (sync, Signals) are signed by. GitHub counts a commit as
# YOUR activity only when its author email is linked to your account; .invalid is a
# reserved domain that can never be, so myGeeKy's housekeeping never shows up as you
# being active (green squares, "contributions in the last year").
COMMIT_NAME = "myGeeKy"
COMMIT_EMAIL = "housekeeping@mygeeky.invalid"
SEEN_FILE = DATA_DIR / "seen.json"                    # what you've already seen in the panel (synced)
TASTE_FILE = DATA_DIR / "taste.json"                  # your 👍/👎 on skills, jobs, resources... (synced)
CURATED_FILE = DATA_DIR / "curated.json"              # jobs, funding, conferences, resources: the newest list fetched
SKILLS_HISTORY_FILE = DATA_DIR / "skills_history.json"  # how often each skill showed up in your field, by day
MY_REPOS_FILE = DATA_DIR / "my_repos.json"            # your own repos (names, topics, stars), for paths and alerts
PATHS_FILE = DATA_DIR / "learning_paths.json"         # the protocols you started (synced)
QUIZ_FILE = DATA_DIR / "quiz.json"                    # your best quiz scores, flags and sharing choice (synced)
QUESTIONS_FILE = DATA_DIR / "questions.json"          # the question bank, newest copy fetched
WINS_FILE = DATA_DIR / "wins.json"                    # stars, forks and citations: the last counts and what changed
CITEDBY_FILE = DATA_DIR / "citedby.json"           # who cited you: the citing papers found, your totals (citedby.py)


@dataclass
class MyGeekyConfig:
    # Identity
    github_username: str = ""

    # Where your profile comes from beyond your GitHub repos -- all optional.
    # `mygeeky profile refresh` re-reads these (CV pdf -> text, ORCID + OpenAlex, Google Scholar).
    cv_path: str = ""                     # remembered so the CV can be re-extracted when it changes
    orcid_id: str = ""                    # e.g. "0000-0002-1825-0097"; enables ORCID + OpenAlex enrichment
    openalex_id: str = ""                 # "Is this you?" (whois.py): your OpenAlex author id (A...), used without an ORCID
    scholar_id: str = ""                  # Google Scholar user id, the `user=` part of your profile URL

    # What "geeks like him/her" means -- all optional, all adjustable.
    languages: list[str] = field(default_factory=list)      # e.g. ["Python", "Rust"]
    topics: list[str] = field(default_factory=list)         # e.g. ["bioinformatics", "llm"]
    keywords: list[str] = field(default_factory=list)       # extra free-text interests
    coauthors: list[str] = field(default_factory=list)      # people you've written with, from a CV you dropped in (docread.py)
    locations: list[str] = field(default_factory=list)      # optional, e.g. ["Cairo", "Remote"]
    # Starting from keywords alone, with no ORCID and no GitHub (see fieldstart.py). The date is when that
    # start happened, and the counters are how often myGeeKy has brought up making a real account: four
    # times over three months and then never again. Nothing is ever withdrawn for not having one.
    field_started_at: str = ""                              # ISO date, "" if never started this way
    account_asks: int = 0                                   # scheduled asks already made (max 4)
    account_asked_at: str = ""                              # ISO date of the last scheduled ask
    account_walls_asked: list[str] = field(default_factory=list)   # parts already explained once, by name
    # What kind of work you mostly do: "code" (you mostly build software), "analysis" (you mostly analyse
    # data), "both", or "" (not said). It only sets the starting balance of what myGeeKy suggests -- your
    # model still learns from what you like. Changeable any time.
    work_style: str = ""

    # Candidate filters
    min_followers: int = 0
    max_followers: int = 20000
    max_following: int = 500              # past this, following-to-followers ratio looks like growth-hacking,
                                           # not genuine engagement, even for non-bot accounts
    min_public_repos: int = 2
    require_followers_or_following: bool = True  # drop accounts with neither -- looks dormant/throwaway
    min_followers_gate: int = 5
    min_following_gate: int = 5
    exclude_organizations: bool = True
    exclude_already_following: bool = True
    exclude_users: list[str] = field(default_factory=list)

    # Candidate sources, beyond plain GitHub user search -- all optional
    seed_accounts: list[str] = field(default_factory=list)   # candidates = followers of these well-known accounts
    seed_repos: list[str] = field(default_factory=list)      # "owner/repo" -- candidates = stargazers of these
    include_own_stargazers: bool = True                       # candidates = people who starred your own repos
    include_second_degree: bool = False                        # candidates = who your followees follow (expensive)
    # candidates = owners/contributors of active repos matching your CV/publication terms;
    # these are ranked ahead of the plain language search, which mostly returns famous accounts
    include_domain_repo_people: bool = True
    domain_repo_terms: int = 6                 # how many profile terms to search repos for
    domain_repo_count: int = 20                # how many matching repos to take people from
    second_degree_sample: int = 15            # cap on how many of your followees to expand for second_degree
    source_max_pages: int = 3                  # pages fetched per source (stargazers/followers/etc.)

    # Real per-repo activity QC (hard gate; costs one extra API call per
    # candidate checked, so it only runs on the top-ranked candidates)
    activity_check_top_n: int = 150
    max_repo_push_age_days: int = 365          # a maintained repo must have been pushed to within this window
    recent_upload_days: int = 120              # OR: counts as active if a new (non-fork) repo was created this recently
    min_maintain_span_days: int = 60           # a "maintained" repo must be older than a one-day dump-and-abandon

    # Domain-fit scoring: a vocabulary auto-derived from YOUR OWN CV/repo
    # corpus (not a hardcoded wordlist), scored independently of follow-back
    # likelihood. Domain experts who follow almost no one on GitHub are
    # exactly the people the follow-back heuristic unfairly demotes.
    domain_vocab_size: int = 25
    domain_highlight_count: int = 15

    # Search / scoring knobs
    search_pages: int = 3                 # GitHub search pages to scan per run (30 users/page)
    max_candidates_per_run: int = 60
    # "Likely to follow back" list only: skip accounts that follow almost nobody
    # relative to their audience (following/followers below this), or that are
    # simply too famous to notice a follow. The domain-highlights list ignores these.
    followback_min_ratio: float = 0.05
    followback_max_followers: int = 3000
    max_suggestions_returned: int = 15
    similarity_threshold: float = 0.08
    content_similarity_weight: float = 0.5
    follow_back_ratio_weight: float = 0.3
    activity_weight: float = 0.2
    rate_limit_sleep_seconds: float = 1.5
    search_pause_seconds: float = 2.1     # GitHub's search endpoints have their own, tighter rate limit (~30/min)

    # Repos to contribute to (`mygeeky contribute`): active, non-archived repos
    # matching your profile, with open beginner/help-wanted issues and
    # maintainers who actually merge outside contributors' PRs. Suggest-only:
    # you fork and open PRs yourself.
    contribute_min_stars: int = 10
    contribute_max_stars: int = 20000      # huge projects rarely merge drive-by PRs quickly
    contribute_pushed_within_days: int = 90
    contribute_queries: int = 10           # how many profile terms to turn into repo searches
    contribute_check_top_n: int = 25       # how many top repos get the (costlier) maintainer check
    contribute_max_returned: int = 10
    contribute_extra_terms: list[str] = field(default_factory=list)  # always searched, e.g. ["gwas", "snakemake"]

    # Market: a momentum board of the popular, active repos in your field
    market_size: int = 25                  # repos on the board
    market_terms: int = 8                  # profile terms searched to pick them (weekly)
    market_min_stars: int = 50
    market_pushed_within_days: int = 180
    market_pinned: list[str] = field(default_factory=list)  # "owner/repo" always on the board
    market_refresh_hours: float = 12.0     # panel refreshes the board by itself once it's this old
    # Product Hunt launches in your field, under the board (needs `mygeeky auth producthunt`)
    market_ph_topics: list[str] = field(default_factory=lambda: [
        "developer-tools", "open-source", "github", "artificial-intelligence", "science", "health"])
    market_ph_days: int = 30               # launches from the last N days
    market_ph_size: int = 10               # launches shown
    market_hf_enabled: bool = True         # Hugging Face models on the Market (no key needed)
    market_hf_size: int = 15               # models per list (in your field, trending everywhere)
    market_hf_refresh_hours: float = 6.0

    # Cross-machine sync: your data dir is a clone of a PRIVATE GitHub repo
    # (`mygeeky sync init`). Uses your normal git/gh credentials, never
    # myGeeKy's read-only token, and never syncs any secret.
    sync_repo: str = ""                    # "owner/name", set by `mygeeky sync init`
    sync_auto: bool = True                 # `pipeline` pulls first and pushes last when sync is set up

    # Beacons (`mygeeky beacon init`): non-verbal signals between myGeeKy users
    # (wave, learn-from, collab, watching, kudos) through a PUBLIC repo,
    # <you>/mygeeky-beacon. Off until you opt in; everything in it is public.
    beacon_enabled: bool = False
    beacon_status: str = ""                 # one of beacon.STATUSES, e.g. "open-to-collab"
    beacon_share_interests: bool = True     # publish your topics/keywords/languages as interest tags
    beacon_blocked: list[str] = field(default_factory=list)  # never show signals from these
    signals_terms: str = ""                                  # the Signals terms you agreed to (beacon.TERMS_VERSION)
    beacon_daily_limit: int = 10            # signals you can send per day
    beacon_repeat_days: int = 30            # the same signal to the same person at most once in this many days
    beacon_weekly_new_people: int = 5       # people you can start signalling per week
    badges_seen: list[str] = field(default_factory=list)   # "id:tier" you've already been shown
    beacon_quiet: bool = False              # "not taking signals right now": others can't send to you
    beacon_quiet_at: str = ""               # when it last changed, here or on the phone: the later one wins
    beacon_muted: list[str] = field(default_factory=list)  # hide their signals (they're not told)
    beacon_gesture_ttl_days: int = 90       # signals expire (yours are pruned, others' ignored) after this
    beacon_refresh_minutes: int = 30        # min minutes between re-reading everyone's beacons
    beacon_max_users: int = 60              # beacons read per refresh (one API call each when changed)

    # Learning your interests from what you do, with room to explore (see interests.py)
    interest_learning: bool = True
    interest_half_life_days: float = 30.0  # an action counts half as much after this many days
    explore_share: float = 0.2             # share of every list kept for "new territory" outside your interests

    # News: new papers and discussions matching your interests (arXiv, bioRxiv, Hacker News)
    news_sources: list[str] = field(default_factory=lambda: ["arxiv", "biorxiv", "hackernews"])
    news_size: int = 25
    news_refresh_hours: float = 6.0
    news_days: int = 7                     # how far back to look
    headlines_enabled: bool = True         # titles from AI labs, journals and the tech press
    headlines_categories: list[str] = field(default_factory=lambda: ["ai", "science", "tech"])
    headlines_size: int = 30
    headlines_days: int = 4                # only this fresh
    headlines_refresh_hours: float = 3.0
    headlines_ai_min: int = 3              # always a few AI headlines, even if they don't match you

    # Research trends (Market tab -> Research): rising papers, tools with papers, people (OpenAlex)
    trends_months: int = 18                # how recent a paper must be
    trends_size: int = 15                  # papers per section
    trends_refresh_hours: float = 24.0

    # Updates: check PyPI for a newer myGeeKy once a day (one read-only request)
    check_for_updates: bool = True
    update_dismissed: str = ""             # "Later" on this version hides the banner until a newer one

    # Learning
    min_training_samples: int = 8         # need at least this many labeled examples before ML kicks in
    ml_blend_weight: float = 0.5          # how much the learned model influences the final score once trained
    training_mass_follow_outlier: int = 3000  # exclude accounts following more than this from training data

    # Optional live GUI (`mygeeky gui`, Qt is set up on first run) -- a
    # small always-on-top glass panel docked to a screen edge. Purely a local
    # viewer over the same data the CLI produces; it never runs a full
    # candidate search on its own (see gui/app.py) and never follows anyone --
    # every profile link is opened in your browser only when you click it.
    gui_dock_side: str = "right"          # "right" | "left" | "bottom-right" | "bottom-left" (bottom: opens rising to the middle)
    gui_layer: str = "front"              # "front" (always on top) | "normal" | "behind" (under other windows while folded)
    gui_expanded_width: int = 460             # the open panel's width; ⚙ or drag its inner edge (360-900)
    gui_rail_pinned: bool = False       # the side rail stays open beside the page (else it opens over it)
    gui_rail_side: str = "auto"               # the side rail: "auto" (the screen-edge side) | "left" | "right"
    tour_lang: str = ""                       # GeeKOc's tours and Help: "en" | "fr" | "ar" | "zh" ("" = ask first)
    tour_seen: int = 0                        # the last tour version seen (tour.py): 0 = never, so the tour opens once
    gui_folded_width: int = 76                # folded, the panel is just the app icon on the screen edge
    gui_folded_height: int = 76
    gui_hearts_enabled: bool = True           # folded icon lets a few small hearts drift up now and then
    gui_hearts_interval_minutes: float = 3.0  # how often; they fade out in ~3 s, never while the panel is open
    gui_folded_opacity: float = 0.5           # folded icon's opacity; it turns fully opaque while hovered
    gui_intro_shown: bool = False             # the opening animation plays once, the first time the panel starts
    gui_signals_radar_open: bool = False      # Signals: "Your field" unfolded into the radar (else a thin ruler)
    gui_panel_height_fraction: float = 0.6    # share of the screen's height the open panel takes; adjust
                                               # it in ⚙ or by dragging the panel's bottom edge (35%-90%)
    gui_activity_refresh_minutes: int = 5     # min minutes between automatic activity-feed refreshes
    gui_activity_limit: int = 30              # how many recent activity events to show
    gui_activity_match_people: int = 12       # also show activity of this many top suggestions (matched to your
                                               # CV/ORCID/repos); one API call each per refresh, 0 = followed only
    # freshness: seen things make room for new ones (see freshness.py)
    fresh_people_days: float = 7.0         # a person you've seen (not clicked) may come back after this
    fresh_repos_days: float = 7.0          # the same for repos to contribute to
    fresh_market_days: float = 3.0         # a Market row you've seen moves down for this long
    fresh_ignored_after: int = 3           # seen this many times and never clicked...
    fresh_ignored_days: float = 30.0       # ...then it rests this long instead
    fresh_people_topup_hours: float = 6.0  # search GitHub for more people at most this often, in the background
    fresh_repos_topup_hours: float = 12.0  # the same for repos
    gui_suggestions_auto_refresh_hours: float = 6.0  # panel searches again by itself once the follow-back list is
                                               # empty and the last search is this old; 0 = only on Refresh click
    gui_theme: str = "midnight"               # "frosted" | "midnight" | "aurora" -- switchable live via the panel's swatch buttons
    gui_live_rotate_seconds: float = 4.5      # how often the Live tab's spotlight card auto-advances
    gui_opacity: float = 1.0                  # whole-window opacity (0.6-1.0); the settings panel exposes this
                                               # as "Transparency" (0% = opaque, 100% = fully transparent), i.e.
                                               # the inverse of this value
    # careful notifications (notify.py): ALL OFF until you switch a kind on, in setup or in ⚙ Settings
    notify_kinds: list[str] = field(default_factory=list)   # seasons, jobs, funding, conferences, papers, highlights
    notify_every: str = "daily"                               # "daily" | "weekly": at most one summary that often
    notify_quiet: list[int] = field(default_factory=lambda: [22, 8])   # no notifications from 22:00 to 08:00

    # Bumped when a default changes in a way existing configs should pick up
    # (see _migrate). Every saved config carries every key, so a new default
    # alone never reaches people who already ran myGeeKy.
    config_version: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULTS = MyGeekyConfig()


def profile_ready(cfg: MyGeekyConfig) -> bool:
    """Enough to know your field: a GitHub username, an ORCID iD, topics, keywords or a CV.

    Keywords alone are a real profile, not a lesser one: Chances, Grow, News, Research, Market, Repos and
    the field half of People all match a field against public pages and never look you up. What needs an
    account is only what reads your account -- who would follow you back, Activity, Signals, Collab -- and
    carrying your data to a second device."""
    return bool(cfg.github_username or cfg.orcid_id or cfg.openalex_id or cfg.topics or cfg.keywords or cfg.cv_path)


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    AVATAR_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def local_db(name: str, keep_broken: int = 2) -> Path:
    """Where the live database `name` lives (LOCAL_DIR), moved there once from the data folder where older versions
    kept it (with its -wal and -shm files). Damaged copies an older version set aside are trimmed to the newest
    `keep_broken`: they're caches, and dozens of them filled the folder."""
    new, old = LOCAL_DIR / name, DATA_DIR / name
    try:
        LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        if old.exists() and not new.exists():
            for suffix in ("", "-wal", "-shm"):
                src = old.with_name(name + suffix)
                if src.exists():
                    os.replace(src, new.with_name(name + suffix))
        broken = sorted(DATA_DIR.glob(f"{name}.broken-*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for p in broken[keep_broken:]:
            p.unlink(missing_ok=True)
    except OSError:
        pass                    # in use (Windows) or read-only: start afresh beside it; it's only a cache
    return new


# set when this start had to recover settings from a damaged config.json (the panel says so)
RECOVERED_FROM: str = ""


def _readable(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))   # -sig: a BOM from a text editor is fine
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _recover_config() -> dict[str, Any]:
    """config.json is damaged (a crash or power cut during a save, a bad hand edit):
    keep it aside and take the newest good copy -- a save backup or the synced copy."""
    global RECOVERED_FROM
    from .files import set_aside
    set_aside(CONFIG_FILE)
    candidates = [PREVIOUS_CONFIG_FILE]
    candidates += sorted(CONFIG_FILE.parent.glob("config.backup-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    candidates.append(SYNCED_CONFIG_FILE)
    for path in candidates:
        raw = _readable(path)
        if raw:
            RECOVERED_FROM = path.name
            return raw
    RECOVERED_FROM = "defaults"
    return {}


def load_config() -> MyGeekyConfig:
    ensure_dirs()
    if not CONFIG_FILE.exists():
        return MyGeekyConfig()
    raw = _readable(CONFIG_FILE)
    recovered = raw is None
    if recovered:
        raw = _recover_config()
    base = asdict(MyGeekyConfig())
    # ignore keys this version doesn't know -- a config synced from another
    # machine may have been written by a newer myGeeKy
    base.update({k: v for k, v in raw.items() if k in base})
    cfg = MyGeekyConfig(**_migrate(base, raw.get("config_version", 1)))
    if recovered:
        write_json(CONFIG_FILE, cfg.to_dict(), indent=2)   # the restored settings become config.json again
    return cfg


def _migrate(values: dict[str, Any], version: int) -> dict[str, Any]:
    if version < 2:
        # 0.4: the folded icon grew from 58px; keep any size someone chose themselves
        if values.get("gui_folded_width") == 58 and values.get("gui_folded_height") == 58:
            values["gui_folded_width"] = values["gui_folded_height"] = 76
    if version < 3:
        # 0.14: the panel grew from a short strip; keep any height someone chose themselves
        if values.get("gui_panel_height_fraction") == 0.25:
            values["gui_panel_height_fraction"] = 0.6
    if version < 4:
        # 0.21.3: the panel is never more than 40% see-through (gui.app.MIN_OPACITY)
        if isinstance(values.get("gui_opacity"), (int, float)) and values["gui_opacity"] < 0.6:
            values["gui_opacity"] = 0.6
    if version < 5:
        # 0.34: the panel grew from 380px for the side rail; keep any width someone chose themselves
        if values.get("gui_expanded_width") == 380:
            values["gui_expanded_width"] = 460
    values["config_version"] = MyGeekyConfig.config_version
    return values


# settings that are painful to lose: a save that drops any of them keeps a backup first
_PRECIOUS = ("beacon_enabled", "sync_repo", "orcid_id", "openalex_id", "scholar_id", "cv_path", "keywords",
             "coauthors", "field_started_at")


def save_config(cfg: MyGeekyConfig) -> None:
    ensure_dirs()
    new = cfg.to_dict()
    try:
        old = _readable(CONFIG_FILE) or {}
        if any(old.get(k) and not new.get(k) for k in _PRECIOUS):
            from datetime import datetime
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            write_json(CONFIG_FILE.with_name(f"config.backup-{stamp}.json"), old, indent=2)
    except (OSError, ValueError):
        pass
    try:                                       # the last good version, for when config.json gets damaged anyway
        if _readable(CONFIG_FILE):
            write_json(PREVIOUS_CONFIG_FILE, _readable(CONFIG_FILE), indent=2)
    except OSError:
        pass
    write_json(CONFIG_FILE, new, indent=2)     # all at once: a crash mid-save leaves the old file, not half of it


def config_summary(cfg: MyGeekyConfig) -> str:
    lines = [f"Config file: {CONFIG_FILE}", ""]
    for k, v in cfg.to_dict().items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)
