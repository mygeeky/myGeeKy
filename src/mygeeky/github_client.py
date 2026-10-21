"""Minimal, read-only GitHub REST API client, with conditional requests.

Every answer is remembered with its ETag (ghcache.py), and every request carries
`If-None-Match`, so GitHub can reply **304 Not Modified** -- which costs nothing
against the rate limit. Nothing goes stale: we still ask each time, GitHub just
answers "unchanged" for free. When the network or GitHub is away, the cached
answer is served instead, marked `from_cache`, so the app keeps working.

Deliberate design constraint: this file contains no `follow` / `unfollow`
method, and never calls `PUT/DELETE /user/following/*`. myGeeKy suggests;
it does not act on GitHub on your behalf. If you ever extend this client,
keep it that way -- see README "Safety" section for why. (The single,
opt-in write myGeeKy can make -- your own beacon file -- lives apart from
this client, in beacon.BeaconWriter, with its own narrowly scoped token.)
"""

from __future__ import annotations

import time
from typing import Any, Iterable, Iterator

import requests

from . import ghcache

API_ROOT = "https://api.github.com"
MAX_WAIT = 60          # seconds a request may wait for GitHub's limit; longer, and we say so instead


class RateLimited(requests.RequestException):
    """GitHub asked us to wait longer than is reasonable inside one refresh. A
    RequestException, so every caller that copes with a network error copes with this."""

    def __init__(self, reset_at: float, secondary: bool = False) -> None:
        self.reset_at = reset_at
        when = time.strftime("%H:%M", time.localtime(reset_at))
        kind = "asked to slow down" if secondary else "limit reached"
        super().__init__(f"GitHub {kind}: myGeeKy will try again after {when}."
                         + ("" if secondary else " Signing in (a token) raises the limit a lot."))


class NotGitHub(requests.ConnectionError):
    """The network answered with a web page of its own (hotel/airport Wi-Fi sign-in)."""

    def __init__(self) -> None:
        super().__init__("The network answered with a web page instead of GitHub: probably a Wi-Fi sign-in page. "
                         "Open your browser, sign in to the network, then refresh.")


def _looks_like_web_page(resp: requests.Response) -> bool:
    kind = str(resp.headers.get("Content-Type", "")).lower()
    if "json" in kind:
        return False
    return str(getattr(resp, "text", "") or "").lstrip()[:15].lower().startswith(("<!doctype", "<html"))


def _is_slow_down(resp: requests.Response) -> bool:
    if resp.headers.get("Retry-After") or resp.headers.get("X-RateLimit-Remaining") == "0":
        return True
    try:
        return "rate limit" in str(resp.json().get("message", "")).lower()
    except (ValueError, AttributeError):
        return False


def _retry_after(resp: requests.Response) -> float:
    try:
        return max(1.0, float(resp.headers["Retry-After"]))
    except (KeyError, ValueError):
        pass
    try:
        return max(1.0, float(resp.headers["X-RateLimit-Reset"]) - time.time() + 1)
    except (KeyError, ValueError):
        return 60.0        # GitHub's advice when it says neither


class GitHubClient:
    def __init__(self, token: str | None, rate_limit_sleep: float = 1.5, search_pause: float = 2.1,
                 user_agent: str = "mygeeky-cli", cache: "ghcache.Store | None" = None,
                 use_cache: bool = True):
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": user_agent,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.session.headers.update(headers)
        self.token_refused = False    # GitHub answered 401: the token is expired or revoked (token_check says so)
        self.rate_limit_sleep = rate_limit_sleep
        self._blocked_until = 0.0
        # what GitHub already told us, and what this client did with it
        self.cache = (cache or ghcache.store()) if use_cache else None
        self.stats = ghcache.Stats()
        self._poll_until = 0.0        # GitHub's X-Poll-Interval for the events endpoints
        # GitHub's /search/* endpoints have their own, much tighter rate limit
        # (~30 requests/min) independent of the main 5000/hour REST limit, so
        # they need their own, longer pacing regardless of X-RateLimit-Remaining.
        self.search_pause = search_pause

    def _get(self, path: str, params: dict[str, Any] | None = None, is_search: bool = False) -> Any:
        """One read. It may be answered by GitHub, by GitHub saying "unchanged" (free), or -- when the
        network is away -- out of the cache, in which case the answer carries `from_cache`."""
        url = path if path.startswith("http") else f"{API_ROOT}{path}"
        key = ghcache.key_of(url, params)
        self.stats.note(path)
        held = self.cache.get(key) if self.cache is not None else None
        if held is not None:
            # the same question twice in one refresh, and a 404 we were told about recently, are not asked again
            # ... nor slow numbers (stars, commit activity, a profile) known from less than a day ago
            if held.age < ghcache.SAME_RUN_SECONDS or (held.status == 404 and held.age < ghcache.MISSING_SECONDS) \
                    or (held.status == 200 and held.age < ghcache.slow_seconds(url)):
                self.stats.from_cache += 1
                if self.cache is not None:
                    self.cache.count("from_cache")
                return ghcache.CachedResponse(held)
        if self._blocked_until > time.time():
            if held is not None:                     # the limit is spent: what we know beats nothing
                self.stats.from_cache += 1
                self.stats.offline += 1
                return ghcache.CachedResponse(held)
            raise RateLimited(self._blocked_until)
        headers = held.headers() if held is not None else {}
        try:
            resp = self.session.get(url, params=params, headers=headers or None, timeout=30)
        except requests.RequestException:
            if held is not None:                     # no network: the app keeps working on what it has
                self.stats.from_cache += 1
                self.stats.offline += 1
                if self.cache is not None:
                    self.cache.count("offline")
                return ghcache.CachedResponse(held)
            raise
        if resp.status_code in (403, 429) and _is_slow_down(resp):
            # GitHub's secondary limit: it says how long to back off (Retry-After) or when the limit resets
            wait = _retry_after(resp)
            if wait > MAX_WAIT:
                self._blocked_until = time.time() + wait
                raise RateLimited(self._blocked_until, secondary=True)
            time.sleep(wait)
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code in (403, 429) and _is_slow_down(resp):
                self._blocked_until = time.time() + max(_retry_after(resp), MAX_WAIT)
                raise RateLimited(self._blocked_until, secondary=True)
        if resp.status_code == 401 and "Authorization" in self.session.headers:
            # the token was refused (expired or revoked): read public data without it for the rest of this run,
            # instead of every read failing; the token warning (token_check) tells you to make a new one.
            # The phone does the same (lib/github.ts).
            self.token_refused = True
            del self.session.headers["Authorization"]
            resp = self.session.get(url, params=params, timeout=30)
        if resp.status_code == 200 and _looks_like_web_page(resp):
            raise NotGitHub()
        resp = self._remember(key, resp, is_search)
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) <= 1:
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(0, reset - int(time.time())) + 1
            if wait <= MAX_WAIT:
                time.sleep(wait)
            else:                      # this answer is fine; the next request would have to wait an hour
                self._blocked_until = float(reset)
        elif is_search and self.search_pause:
            time.sleep(self.search_pause)
        elif self.rate_limit_sleep and not getattr(resp, "fresh", False):
            time.sleep(self.rate_limit_sleep)       # a 304 cost nothing, so there is nothing to pace
        return resp

    def _remember(self, key: str, resp: requests.Response, is_search: bool) -> Any:
        """Count what this answer was, and keep it (or keep what 304 just confirmed)."""
        self.stats.requests += 1
        if is_search:
            self.stats.searches += 1
        if self.cache is None:
            return resp
        self.cache.count("requests")
        if is_search:
            self.cache.count("searches")
        if resp.status_code == 304:                  # free: nothing changed since last time
            self.stats.not_modified += 1
            self.cache.count("not_modified")
            row = self.cache.touch(key, resp.headers.get("ETag", ""), resp.headers.get("Last-Modified", ""))
            if row is not None:
                return ghcache.CachedResponse(row, fresh=True)
            return resp                              # we were asked to revalidate something we no longer hold
        if resp.status_code == 200:
            try:
                body = resp.json()
            except ValueError:
                return resp                          # not JSON (204s and the like): nothing to keep
            self.cache.put(key, body, 200, resp.headers.get("ETag", ""), resp.headers.get("Last-Modified", ""))
        elif resp.status_code == 404:
            self.cache.put(key, None, 404)           # a deleted account isn't asked for again all day
        elif resp.status_code >= 500:
            held = self.cache.get(key)               # GitHub is having a bad day: use what we have
            if held is not None and held.status == 200:
                self.stats.from_cache += 1
                return ghcache.CachedResponse(held)
        return resp

    def done(self) -> ghcache.Stats:
        """Write the cache once, at the end of a refresh, and hand back what this run did."""
        if self.cache is not None:
            self.cache.save()
        return self.stats

    def get_user(self, username: str) -> dict[str, Any] | None:
        resp = self._get(f"/users/{username}")
        if resp.status_code != 200:
            return None
        return resp.json()

    def get_authenticated_user(self) -> dict[str, Any]:
        resp = self._get("/user")
        resp.raise_for_status()
        return resp.json()

    def list_repos(self, username: str, max_pages: int = 3, per_page: int = 100,
                    sort: str = "updated") -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            resp = self._get(
                f"/users/{username}/repos",
                params={"per_page": per_page, "page": page, "sort": sort, "type": "owner"},
            )
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < per_page:
                break
        return repos

    def _list_paginated_logins(self, path: str, max_pages: int = 10, per_page: int = 100) -> list[str]:
        logins: list[str] = []
        for page in range(1, max_pages + 1):
            resp = self._get(path, params={"per_page": per_page, "page": page})
            if resp.status_code != 200:
                break
            batch = resp.json()
            if not batch:
                break
            logins.extend(u["login"] for u in batch)
            if len(batch) < per_page:
                break
        return logins

    def list_followers(self, username: str, max_pages: int = 10) -> list[str]:
        return self._list_paginated_logins(f"/users/{username}/followers", max_pages=max_pages)

    def list_following(self, username: str, max_pages: int = 10) -> list[str]:
        return self._list_paginated_logins(f"/users/{username}/following", max_pages=max_pages)

    def list_stargazers(self, owner_repo: str, max_pages: int = 3) -> list[str]:
        """`owner_repo` is `"owner/name"`. Candidates who starred a relevant repo tend to
        be genuinely interested in the subject matter, not just search-matched."""
        return self._list_paginated_logins(f"/repos/{owner_repo}/stargazers", max_pages=max_pages)

    def list_contributors(self, owner_repo: str, per_page: int = 30) -> list[dict[str, Any]]:
        """Top contributors by commit count (logins + `type`, so bots can be skipped)."""
        resp = self._get(f"/repos/{owner_repo}/contributors", params={"per_page": per_page})
        if resp.status_code != 200:
            return []
        return resp.json()

    def list_received_events(self, username: str, per_page: int = 30, page: int = 1) -> list[dict[str, Any]]:
        """GitHub's own news-feed data source. Note it is NOT only the accounts
        `username` follows: it also carries every event on repos owned by
        orgs you follow (strangers starring/forking/opening issues there), so
        callers should filter by actor."""
        resp = self._get(f"/users/{username}/received_events", params={"per_page": per_page, "page": page})
        if resp.status_code != 200:
            return []
        return resp.json()

    def list_user_events(self, username: str, per_page: int = 10) -> list[dict[str, Any]]:
        """One account's own recent public events."""
        resp = self._get(f"/users/{username}/events/public", params={"per_page": per_page})
        if resp.status_code != 200:
            return []
        return resp.json()

    def get_repo(self, owner_repo: str) -> dict[str, Any] | None:
        resp = self._get(f"/repos/{owner_repo}")
        if resp.status_code != 200:
            return None
        return resp.json()

    def get_repo_file(self, owner_repo: str, path: str) -> dict[str, Any] | None:
        """One file's contents-API record (base64 `content`, `size`, ...), or None."""
        resp = self._get(f"/repos/{owner_repo}/contents/{path}")
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data if isinstance(data, dict) else None

    def is_following(self, source_username: str, target_username: str) -> bool:
        """True if `source_username` follows `target_username` (public, read-only check)."""
        resp = self._get(f"/users/{source_username}/following/{target_username}")
        return resp.status_code == 204

    def search_repositories(self, query: str, max_pages: int = 1, per_page: int = 30,
                             sort: str = "updated") -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            resp = self._get(
                "/search/repositories",
                params={"q": query, "per_page": per_page, "page": page, "sort": sort},
                is_search=True,
            )
            if resp.status_code != 200:
                break
            items = resp.json().get("items", [])
            repos.extend(items)
            if len(items) < per_page:
                break
        return repos

    def list_open_issues(self, owner_repo: str, label: str, per_page: int = 10) -> list[dict[str, Any]]:
        """Open issues (not PRs) carrying `label`, newest first."""
        resp = self._get(f"/repos/{owner_repo}/issues",
                         params={"state": "open", "labels": label, "per_page": per_page,
                                 "sort": "created", "direction": "desc"})
        if resp.status_code != 200:
            return []
        return [i for i in resp.json() if "pull_request" not in i]

    def list_closed_pulls(self, owner_repo: str, per_page: int = 30) -> list[dict[str, Any]]:
        """Most recently updated closed PRs -- each carries `merged_at` and the
        author's `author_association`, enough to tell whether maintainers
        merge outside contributors' work."""
        resp = self._get(f"/repos/{owner_repo}/pulls",
                         params={"state": "closed", "per_page": per_page,
                                 "sort": "updated", "direction": "desc"})
        if resp.status_code != 200:
            return []
        return resp.json()

    def search_users(self, query: str, max_pages: int = 3, per_page: int = 30) -> Iterator[dict[str, Any]]:
        for page in range(1, max_pages + 1):
            resp = self._get(
                "/search/users",
                params={"q": query, "per_page": per_page, "page": page},
                is_search=True,
            )
            if resp.status_code != 200:
                break
            items = resp.json().get("items", [])
            if not items:
                break
            for item in items:
                yield item
            if len(items) < per_page:
                break


def build_search_queries(languages: Iterable[str], locations: Iterable[str],
                          min_followers: int, max_followers: int, min_repos: int) -> list[str]:
    """Build one or more GitHub user-search query strings from config facets.

    Fans out one query per language (or a single bare query if no languages
    are configured), each carrying the shared followers/repos/location
    filters. `topics` are not usable here (GitHub's /search/users endpoint
    has no `topic:` qualifier) -- they instead feed content-similarity
    scoring in matcher.py.
    """
    shared = [
        f"followers:{min_followers}..{max_followers}",
        f"repos:>={min_repos}",
        "type:user",
    ]
    for loc in locations:
        shared.append(f'location:"{loc}"')

    # Note: GitHub's /search/users endpoint has no `topic:` qualifier (that
    # only exists for /search/repositories), so `topics` is used later, in
    # matcher.py, for content-similarity scoring rather than the query itself.
    queries: list[str] = []
    langs = list(languages) or [None]
    for lang in langs:
        parts = list(shared)
        if lang:
            parts.append(f"language:{lang}")
        queries.append(" ".join(p for p in parts if p))
    return queries
