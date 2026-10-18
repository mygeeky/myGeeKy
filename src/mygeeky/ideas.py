"""The 💡: send an idea, a problem or a question to myGeeKy's maker.

Each one becomes an issue in the public repo IDEAS_REPO. The sender's own
browser opens a prefilled "new issue" page and they click Submit with their
own GitHub account -- no token or password passes through myGeeKy, and
nothing is sent until they press it. GitHub then notifies the maker, and the
admin tab's inbox lists them.

No GitHub account, or rather private? The same idea opens as a ready-made email to SUPPORT_EMAIL in the
sender's own mail app (email_url); they send it themselves, so nothing leaves without them either.

"Include version info" adds only the myGeeKy and Python versions and the OS --
never tokens, usernames of others, file paths or anything from your data.
"""

from __future__ import annotations

import platform
import sys
from typing import Any
from urllib.parse import quote, urlencode

from . import __version__

IDEAS_REPO = "mygeeky/myGeeKy-ideas"
SUPPORT_EMAIL = "support@mygeeky.org"
KINDS = {
    "idea": ("💡", "Idea", "idea"),
    "problem": ("🐞", "Problem", "problem"),
    "question": ("❓", "Question", "question"),
    "keyword": ("🔤", "Keyword", "keyword"),
    "report": ("🚩", "Report", "report"),   # a job, call or resource that looks fake
    "protocol": ("🧭", "Protocol", "protocol"),   # a learning protocol a user published (protocols.py)
    "score": ("🏆", "Quiz score", "leaderboard"),  # someone asking for their score to be shown (leaderboard.py)
}


def keyword_url(word: str) -> str:
    """A prefilled issue asking for `word` to join the keyword dictionary."""
    return issue_url("keyword", f"Keyword: {word}",
                     f"Please teach myGeeKy's keyword dictionary the word **{word}**.\n\n"
                     "What it means to me (optional):", include_version=True)
MAX_URL = 7000          # browsers and GitHub cope with ~8k; stay well under
MAX_MAILTO = 1800       # some mail apps cut a mailto: link near 2000 characters


def version_info() -> str:
    return (f"myGeeKy {__version__} · Python {sys.version.split()[0]} · "
            f"{platform.system()} {platform.release()}")


def issue_url(kind: str, title: str, details: str = "", include_version: bool = True) -> str:
    """The prefilled new-issue page for this idea."""
    emoji, label, gh_label = KINDS.get(kind, KINDS["idea"])
    title = " ".join((title or "").split())[:120] or label
    body = (details or "").strip()
    if kind == "problem" and not body:
        body = "What happened, and what did you expect?\n"
    if include_version:
        body += f"\n\n---\n<sub>Sent from the 💡 in myGeeKy · {version_info()}</sub>"
    else:
        body += "\n\n---\n<sub>Sent from the 💡 in myGeeKy</sub>"
    params = {"title": f"{emoji} {title}", "body": body, "labels": gh_label}
    url = f"https://github.com/{IDEAS_REPO}/issues/new?" + urlencode(params)
    while len(url) > MAX_URL and len(params["body"]) > 200:   # a very long text: trim, never drop the title
        params["body"] = params["body"][: int(len(params["body"]) * 0.8)] + "\n\n(trimmed: please add the rest after opening)"
        url = f"https://github.com/{IDEAS_REPO}/issues/new?" + urlencode(params)
    return url


def _enc(s: str) -> str:
    """Percent-encoding exactly as JavaScript's encodeURIComponent, so the phone builds the same email."""
    return quote(s, safe="!~*'()")


def email_url(kind: str, title: str, details: str = "", include_version: bool = True) -> str:
    """The same idea as a ready-made email to SUPPORT_EMAIL: for people without GitHub, or who'd rather
    keep it private. Plain text (no GitHub markup); the phone's lib/ideas.ts builds the same."""
    emoji, label, _ = KINDS.get(kind, KINDS["idea"])
    title = " ".join((title or "").split())[:120] or label
    body = (details or "").strip()
    if kind == "problem" and not body:
        body = "What happened, and what did you expect?\n"
    body += f"\n\n---\nSent from the 💡 in myGeeKy · {version_info()}" if include_version else "\n\n---\nSent from the 💡 in myGeeKy"
    make = lambda b: f"mailto:{SUPPORT_EMAIL}?subject={_enc(f'{emoji} {title}')}&body={_enc(b)}"  # noqa: E731
    url = make(body)
    while len(url) > MAX_MAILTO and len(body) > 200:   # a very long text: trim, never drop the title
        body = body[: int(len(body) * 0.8)] + "\n\n(trimmed: please add the rest in the email)"
        url = make(body)
    return url


def kind_of(issue: dict[str, Any]) -> str:
    labels = {(l.get("name") or "").lower() for l in issue.get("labels") or [] if isinstance(l, dict)}
    title = issue.get("title") or ""
    for key, (emoji, _, gh_label) in KINDS.items():
        if gh_label in labels or title.startswith(emoji):
            return key
    return "idea"


def inbox(client, state: str = "open", limit: int = 30) -> list[dict[str, Any]]:
    """Newest ideas/problems/questions (read-only; the repo is public)."""
    resp = client._get(f"/repos/{IDEAS_REPO}/issues",
                       params={"state": state, "per_page": limit, "sort": "created", "direction": "desc"})
    if resp.status_code != 200:
        return []
    out = []
    for i in resp.json():
        if "pull_request" in i:
            continue
        out.append({
            "number": i.get("number"),
            "kind": kind_of(i),
            "title": " ".join(str(i.get("title") or "").split())[:160],
            "author": (i.get("user") or {}).get("login", ""),
            "created_at": i.get("created_at", ""),
            "comments": i.get("comments", 0),
            "reactions": (i.get("reactions") or {}).get("+1", 0),
            "url": f"https://github.com/{IDEAS_REPO}/issues/{i.get('number')}",
        })
    return out
