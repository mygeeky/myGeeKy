"""Settings → Accounts: the cards, in order, with what each says (the phone has the same, lib/accounts.ts;
tests/test_accounts.py checks both agree).

GitHub and ORCID first, then saving your data and Signals, then your other device. Each card is on (folded, green),
off (optional ones say why you might want them) or bad (its access stopped working: red, unfolded). Only saving your
data counts as something to do: when it isn't set up, or when any card has gone bad. GitHub, ORCID, Signals and the
other device are optional and never nag.
"""

from __future__ import annotations

ORDER = ("github", "orcid", "data", "beacon", "device")
OPTIONAL = ("github", "orcid", "beacon", "device")
HEADINGS = {"github": "SIGN IN", "data": "SAVING AND SIGNALS", "device": "YOUR OTHER DEVICES"}
TITLES = {"github": "GitHub", "orcid": "ORCID", "data": "Saving your data", "beacon": "Signals (beacon)"}
PILLS = {"on": "Connected", "bad": "Needs renewing", "optional": "Optional", "off": "Not set up"}


def _why(key: str, state: str, platform: str, d: dict[str, str]) -> str:
    here = "this phone" if platform == "phone" else "this computer"
    if key == "github":
        return {"on": f"Signed in as {d.get('user') or 'you'}. Read-only: myGeeKy never follows, stars or posts for you.",
                "bad": "Your GitHub sign-in stopped working. Sign in again."}.get(
            state, "Why link it: people worth following, your own repos, and My month from your GitHub activity. "
                   "Read-only: myGeeKy never posts for you.")
    if key == "orcid":
        return (f"Linked: {d.get('orcid')}. Your papers shape your feeds." if state == "on" else
                "Why link it: myGeeKy finds your papers, shows who cites you, and fits jobs to your field. "
                "No papers yet? Your keywords are enough.")
    if key == "data":
        repo = d.get("repo") or "your data repo"
        place = "Google Drive" if d.get("where") == "drive" else repo
        if state == "on":
            if d.get("where") == "github-plain":
                return f"Saving to {repo}. It isn't encrypted yet: encrypt it, so only your devices can read it."
            return f"Saving to {place}, encrypted: only your devices can read it. Your computers and phone share " \
                   "your settings and progress."
        if state == "bad":
            if d.get("problem") == "key":
                return f"Your saved data is encrypted with a key {here} doesn't have yet. Type your recovery code" + (
                    ", or scan the QR code your computer shows." if platform == "phone" else ".")
            if d.get("where") == "drive":
                return f"Google Drive stopped accepting {here}'s sign-in, so nothing has been saved since. " \
                       "Sign in with Google again."
            return f"Access to {repo} stopped working, so nothing has been saved since. " + (
                "On GitHub, open the token, click Regenerate token, and paste the new one here." if platform == "phone"
                else "Open the setup window to connect it again.") + " (Google Drive never needs renewing.)"
        return f"Right now, your settings and progress are only on {here}. Save them in Google Drive (recommended) " \
               "or a private GitHub repo: choose one. Either works the same, and you can switch later. They're " \
               "encrypted on your devices, so only your devices can read them."
    if key == "beacon":
        return {"on": f"Signals is on: private thank-yous and collab invites, with a key kept only on {here}.",
                "bad": "Your Signals token stopped working: renew it to keep Signals on."}.get(
            state, "Why turn it on: private thank-yous and collab invites between myGeeKy users, through your public "
                   "repo mygeeky-beacon.")
    if platform == "phone":
        return ("Your computer's profile, interests and badges came over by scan." if state == "on" else
                "Have myGeeKy on a computer? One scan brings over your profile, interests and badges.")
    return "Have the phone app? Show a QR code: one scan sets it up with your profile and badges."


def cards(states: dict[str, str], platform: str = "desktop", details: dict[str, str] | None = None) -> list[dict]:
    """The five cards for these states ('on' | 'off' | 'bad' per key; a missing key is off). ORCID never goes bad (it
    doesn't expire); the computer can't know about a phone, so its device card is always an optional one."""
    d = details or {}
    out = []
    for key in ORDER:
        st = states.get(key, "off")
        if st not in ("on", "off", "bad") or (key == "orcid" and st == "bad"):
            st = "on" if st == "bad" else "off"
        if key == "device" and platform != "phone":
            st = "off"
        pill = PILLS["optional"] if st == "off" and key in OPTIONAL else PILLS[st]
        title = TITLES.get(key) or ("Your computer" if platform == "phone" else "Your phone")
        out.append({"key": key, "state": st, "title": title, "pill": pill, "why": _why(key, st, platform, d),
                    "heading": HEADINGS.get(key, ""), "optional": key in OPTIONAL, "folded": st == "on"})
    return out


def todo(items: list[dict]) -> int:
    """How many things need you: a card gone bad, or saving your data not set up."""
    return sum(1 for c in items if c["state"] == "bad" or (c["key"] == "data" and c["state"] == "off"))


def todo_text(n: int) -> str:
    if n <= 0:
        return ""
    return "1 thing would make myGeeKy work better for you" if n == 1 else f"{n} things would make myGeeKy work better for you"
