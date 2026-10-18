"""Build the picture guides for making GitHub tokens: src/mygeeky/data/token_guides.json, and the phone's
identical copy mobile/src/data/token-guides.json. Run it after changing a step:

    python tools/token_guides.py

Each step has a title, one line of text and a small drawing of the part of GitHub's page that matters, with
the place to click ringed in myGeeKy pink. Drawn, not screenshots: they stay sharp, read in light and dark,
and don't go stale each time GitHub moves its page around. The SVG uses only plain shapes and text, so the
desktop (QtSvg) and the phone (react-native-svg) draw it the same. tests/test_token_guides.py checks both
copies equal this script's output.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = [ROOT / "src" / "mygeeky" / "data" / "token_guides.json", ROOT / "mobile" / "src" / "data" / "token-guides.json"]
NEW_TOKEN = "https://github.com/settings/personal-access-tokens/new"
SECONDS = 4                      # each step stays this long, unless you pick one yourself

W, H = 320, 150
BG, LINE, TEXT, MUTED, HI, GREEN = "#0d1117", "#30363d", "#e6edf3", "#8b949e", "#ff6fd8", "#238636"
FONT = "font-family='Helvetica, Arial, sans-serif'"


def _t(x, y, s, size=11, color=TEXT, weight="normal", anchor="start"):
    return (f"<text x='{x}' y='{y}' {FONT} font-size='{size}' fill='{color}' font-weight='{weight}' "
            f"text-anchor='{anchor}'>{escape(s)}</text>")


def _box(x, y, w, h, fill="#161b22", stroke=LINE, r=6):
    return f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{r}' fill='{fill}' stroke='{stroke}' stroke-width='1'/>"


def _ring(x, y, w, h):
    """The place to click, ringed."""
    return f"<rect x='{x - 4}' y='{y - 4}' width='{w + 8}' height='{h + 8}' rx='9' fill='none' stroke='{HI}' stroke-width='2.5'/>"


def _svg(*parts, caption=""):
    body = "".join(parts)
    cap = _t(W / 2, H - 8, caption, 10, MUTED, anchor="middle") if caption else ""
    return (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {W} {H}' width='{W}' height='{H}'>"
            f"{_box(0.5, 0.5, W - 1, H - 1, BG, LINE, 10)}{body}{cap}</svg>")


def page_header(title):
    return _t(16, 26, title, 13, TEXT, "bold") + f"<line x1='16' y1='36' x2='{W - 16}' y2='36' stroke='{LINE}'/>"


# ------------------------------------------------------------------ the drawings, one per kind of step
def open_page():
    return _svg(_box(12, 14, W - 24, 26, "#161b22"), _t(24, 31, "github.com/settings/personal-access-tokens/new", 10, MUTED),
                _t(16, 66, "Fine-grained personal access tokens", 12, TEXT, "bold"),
                _box(16, 82, 150, 28, GREEN, GREEN), _t(91, 100, "Generate new token", 11, "#ffffff", "bold", "middle"),
                _ring(16, 82, 150, 28), caption="The button in myGeeKy opens this page for you")


def name_field(value):
    return _svg(page_header("New fine-grained token"), _t(16, 58, "Token name *", 11, TEXT, "bold"),
                _box(16, 66, 220, 26), _t(26, 83, value, 11), _ring(16, 66, 220, 26),
                _t(16, 112, "Any name works: it is only a label for you", 10, MUTED))


def expiration():
    return _svg(page_header("New fine-grained token"), _t(16, 58, "Expiration *", 11, TEXT, "bold"),
                _box(16, 66, 140, 26), _t(26, 83, "90 days", 11), _t(144, 83, "▾", 11, MUTED, anchor="end"),
                _ring(16, 66, 140, 26), _t(16, 112, "Pick a long one: myGeeKy reminds you before it ends", 10, MUTED))


def repo_access(choice, repo=""):
    opts = ["Public repositories", "All repositories", "Only select repositories"]
    parts = [page_header("Repository access")]
    for i, o in enumerate(opts):
        y = 58 + i * 24
        on = o == choice
        parts.append(f"<circle cx='24' cy='{y - 4}' r='6' fill='{BG}' stroke='{TEXT if on else MUTED}' stroke-width='1.5'/>")
        if on:
            parts.append(f"<circle cx='24' cy='{y - 4}' r='3' fill='{TEXT}'/>")
            parts.append(_ring(14, y - 15, 170, 20))
        parts.append(_t(38, y, o, 11, TEXT if on else MUTED))
    if repo:
        parts += [_box(196, 100, 108, 24), _t(204, 116, repo, 10), _ring(196, 100, 108, 24)]
    return _svg(*parts)


def permission(group, name, level, note=""):
    parts = [page_header(f"Permissions · {group}"), _box(16, 52, W - 32, 30), _t(26, 71, name, 11, TEXT, "bold"),
             _box(W - 132, 56, 106, 22), _t(W - 124, 71, level, 10), _t(W - 32, 71, "▾", 10, MUTED, anchor="end"),
             _ring(W - 132, 56, 106, 22)]
    if note:
        parts.append(_t(16, 104, note, 10, MUTED))
    return _svg(*parts)


def generate():
    return _svg(page_header("Overview"), _box(16, 50, 130, 28, GREEN, GREEN),
                _t(81, 68, "Generate token", 11, "#ffffff", "bold", "middle"), _ring(16, 50, 130, 28),
                _box(16, 92, W - 32, 26), _t(26, 109, "github_pat_11ABC…", 10),
                _box(W - 64, 96, 40, 18, "#21262d"), _t(W - 44, 109, "Copy", 10, TEXT, anchor="middle"),
                _ring(W - 64, 96, 40, 18))


def paste(where):
    return _svg(_t(16, 28, "myGeeKy", 13, HI, "bold"), _t(16, 50, where, 11, TEXT),
                _box(16, 62, W - 32, 28), _t(26, 80, "github_pat_11ABC…", 11), _ring(16, 62, W - 32, 28),
                _t(16, 112, "It stays on this device only, in its secure storage", 10, MUTED))


# ------------------------------------------------------------------ the guides
def guide(key, title, name, repo_choice, repo, perms, where, tips):
    steps = [
        {"title": "Open GitHub's new token page", "text": "Use the button: it opens GitHub's \"New fine-grained token\" "
                                                          "page. Sign in to GitHub there if it asks.", "svg": open_page()},
        {"title": "Name it anything", "text": f"For example \"{name}\". The name is only a label for you.",
         "svg": name_field(name)},
        {"title": "Choose how long it lasts", "text": "A long one is easiest (90 days or a year); myGeeKy reminds you "
                                                      "a week before it ends.", "svg": expiration()},
        {"title": "Repository access", "text": (f"Choose \"{repo_choice}\"" + (f" and pick {repo}." if repo else ".")),
         "svg": repo_access(repo_choice, repo)},
    ]
    for group, pname, level, note in perms:
        steps.append({"title": f"{pname}: {level}", "text": f"Under {group} permissions, set {pname} to \"{level}\"."
                      + (f" {note}" if note else ""), "svg": permission(group, pname, level, note)})
    steps += [
        {"title": "Generate it, then copy it", "text": "Click Generate token at the bottom of the page, then copy the "
                                                       "token: GitHub shows it only once.", "svg": generate()},
        {"title": "Paste it into myGeeKy", "text": f"Come back here and paste it {where}.", "svg": paste(f"Paste it {where}")},
    ]
    return {"key": key, "title": title, "url": NEW_TOKEN, "tips": tips, "steps": steps}


SAME = "The name can be anything. You can make several tokens for the same repo, for example one per phone or computer."
GUIDES = {
    "data": guide("data", "Make the data repo token", "myGeeKy phone", "Only select repositories", "mygeeky-data",
                  [("Repository", "Contents", "Read and write", "Metadata: Read-only is added by itself.")],
                  "into the token box", [SAME, "Exactly this: only your mygeeky-data repo, Contents: Read and write."]),
    "signals": guide("signals", "Make the Signals token", "myGeeKy Signals", "Only select repositories",
                     "mygeeky-beacon",
                     [("Repository", "Contents", "Read and write", "Metadata: Read-only is added by itself.")],
                     "into the Signals token box",
                     [SAME, "Exactly this: only your mygeeky-beacon repo, Contents: Read and write.",
                      "Signals is optional: skip it and everything else still works."]),
    "read": guide("read", "Make a read-only token", "mygeeky", "Public repositories", "",
                  [("Account", "Followers", "Read-only", "Add nothing else.")], "into the token box",
                  [SAME, "Exactly this: Public repositories, and Account → Followers: Read-only. It can never "
                         "follow anyone or write anything.",
                   "Easier: Sign in with GitHub instead, and you need no token at all."]),
}


def build() -> dict:
    return {"version": 1, "seconds": SECONDS, "guides": GUIDES}


if __name__ == "__main__":
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    for p in OUT:
        p.write_text(text, encoding="utf-8")
        print("wrote", p.relative_to(ROOT))
