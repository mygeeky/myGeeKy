"""The four signs on the right of the top strip: is GitHub linked, is ORCID, is myGeeKy saving to your data repo,
is your Signals beacon on. Each is on (lit), off (faint: never set up) or bad (red: it was set up and its access
stopped working, or is about to); a bad one also reminds you, at most once a day, to renew it.

The apps only say what they know already (the daily token check, the last sync): no request is made for the signs.
The phone does the same (lib/signs.ts); tests/test_signs.py checks both agree.
"""

from __future__ import annotations

from datetime import datetime, timedelta

ORDER = ("github", "orcid", "data", "beacon")
LABELS = {"github": "GitHub", "orcid": "ORCID", "data": "Saving", "beacon": "Beacon"}
TIPS = {
    "github": {"on": "Signed in with GitHub.",
               "off": "GitHub isn't linked. Link it in Settings → Accounts for people, your repos and Signals.",
               "bad": "Your GitHub sign-in stopped working. Sign in again in Settings → Accounts."},
    "orcid": {"on": "ORCID is linked: your papers shape what you see.",
              "off": "ORCID isn't linked. Add it in Settings → Accounts for your papers and who cites you."},
    "data": {"on": "Saving your settings and progress: your computers and phone share them.",
             "off": "Not saving anywhere yet: your settings and progress are only on this device.",
             "bad": "myGeeKy can't save any more: its access to your storage stopped working. See Settings → "
                    "Accounts."},
    "beacon": {"on": "Your Signals beacon is on.",
               "off": "Signals is off.",
               "bad": "Your Signals token expired or stopped working: renew it to keep Signals on."},
}
DRIVE_TIPS = {"on": "Saving your settings and progress in Google Drive: your computers and phone share them.",
              "bad": "myGeeKy can't save to Google Drive any more: sign in with Google again in Settings → Accounts."}
REMIND_HOURS = 24


def state(present: bool, broken: bool = False) -> str:
    """'off' when it was never set up, 'bad' when it was and its access stopped (or is about to), else 'on'."""
    if not present:
        return "off"
    return "bad" if broken else "on"


def signs(github: str, orcid: str, data: str, beacon: str, where: str = "") -> list[dict[str, str]]:
    """The four, in order: key, label, state, what it means (ORCID never goes bad: it doesn't expire) and the icon:
    "drive" (Google Drive's logo) on Saving when your data is saved there, else "" (the sign's own)."""
    given = {"github": github, "orcid": "on" if orcid != "off" else "off", "data": data, "beacon": beacon}
    out = []
    for key in ORDER:
        st = given[key] if given[key] in ("on", "off", "bad") else "off"
        drive = key == "data" and where == "drive" and st != "off"
        out.append({"key": key, "label": LABELS[key], "state": st, "icon": "drive" if drive else "",
                    "tip": DRIVE_TIPS[st] if drive else TIPS[key][st]})
    return out


def reminder(items: list[dict[str, str]], last: str, now: datetime) -> str:
    """The message to show now about a sign gone red, or '' (none is red, or one was shown within REMIND_HOURS).
    `last` is when the last one was shown (ISO), '' for never."""
    bad = [s for s in items if s["state"] == "bad"]
    if not bad:
        return ""
    try:
        if last and now - datetime.fromisoformat(last) < timedelta(hours=REMIND_HOURS):
            return ""
    except ValueError:
        pass
    return " ".join(s["tip"] for s in bad)
