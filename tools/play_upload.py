"""Upload a Google Play bundle (.aab) to a testing track, through the Google Play Developer API.

    python tools/play_upload.py                                   # dry run: checks the key, lists the tracks
    python tools/play_upload.py google-play/myGeeKy-1.23.0-12300.aab --notes google-play/whats-new/1.23.0.txt
    python tools/play_upload.py <aab> --notes <file> --upload     # really upload it (the maintainer said so)

Only with the maintainer's go-ahead in the conversation (CLAUDE.md): without --upload nothing is changed on Play
(the edit it opens to read the tracks is thrown away).

The key is a service account's JSON key in ~/.config/mygeeky-play/play-service-account.json (outside the repo,
chmod 600): never printed, logged or copied. The account has no Google Cloud role; in the Play Console it may only
release myGeeKy to testing tracks, so this can't reach production. It asks Google for the androidpublisher scope
only, for this tool on the maker's computer: the app itself never sees it.

No Google libraries needed: the token is a JWT signed here (cryptography) and the API is plain REST (requests).
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parent.parent
KEY = Path.home() / ".config" / "mygeeky-play" / "play-service-account.json"
PACKAGE = "org.mygeeky.app"
SCOPE = "https://www.googleapis.com/auth/androidpublisher"
API = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE}"
UPLOAD = f"https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PACKAGE}"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def token() -> str:
    """An access token for the service account (one hour), from a JWT signed with its key."""
    if not KEY.is_file():
        sys.exit(f"No key at {KEY}: see the comment at the top of this file.")
    key = json.loads(KEY.read_text(encoding="utf-8"))
    now = int(time.time())
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps({"iss": key["client_email"], "scope": SCOPE, "aud": key["token_uri"],
                            "iat": now, "exp": now + 3600}).encode())
    private = serialization.load_pem_private_key(key["private_key"].encode(), password=None)
    signature = _b64(private.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256()))
    r = requests.post(key["token_uri"], timeout=30, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": f"{head}.{body}.{signature}"})
    if r.status_code != 200:
        sys.exit(f"Google refused the key ({r.status_code}): {r.json().get('error_description', r.text[:200])}")
    return r.json()["access_token"]


def call(session: requests.Session, method: str, url: str, **kw) -> dict:
    r = session.request(method, url, timeout=kw.pop("timeout", 60), **kw)
    if r.status_code >= 300:
        try:
            msg = r.json()["error"]["message"]
        except Exception:
            msg = r.text[:300]
        sys.exit(f"Play said {r.status_code} to {method} {url.split(PACKAGE)[-1] or '/'}: {msg}")
    return r.json() if r.content else {}


def version_code(aab: Path) -> int:
    m = re.search(r"-(\d+)\.aab$", aab.name)              # play_bundle.py names it myGeeKy-<version>-<code>.aab
    if not m:
        sys.exit(f"Can't read the version code from {aab.name} (expected myGeeKy-<version>-<code>.aab)")
    return int(m[1])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("aab", nargs="?", type=Path, help="the bundle; without it, only list the tracks")
    ap.add_argument("--track", default="alpha", help="testing track (default: alpha, the closed test)")
    ap.add_argument("--notes", type=Path, help="a text file with the release notes (en-US, at most 500 characters)")
    ap.add_argument("--draft", action="store_true", help="leave the release as a draft in the Console")
    ap.add_argument("--upload", action="store_true", help="really upload (otherwise a dry run)")
    a = ap.parse_args()
    if a.track == "production":
        sys.exit("This tool releases to testing tracks only.")

    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + token()
    edit = call(s, "POST", f"{API}/edits")["id"]
    committed = False
    try:
        tracks = call(s, "GET", f"{API}/edits/{edit}/tracks").get("tracks", [])
        highest = 0
        for t in tracks:
            for rel in t.get("releases", []):
                codes = [int(c) for c in rel.get("versionCodes", [])]
                highest = max([highest, *codes])
                print(f"  {t['track']:<12} {rel.get('name', ''):<10} {rel.get('status', ''):<11} codes {codes}")
        if not tracks:
            print("  (no tracks with releases yet)")
        if not a.aab:
            print("Key works; nothing changed.")
            return
        code, notes = version_code(a.aab), ""
        if not a.aab.is_file():
            sys.exit(f"No file {a.aab}")
        if code <= highest:
            sys.exit(f"Version code {code} is not higher than {highest}, already on Play.")
        if a.notes:
            notes = a.notes.read_text(encoding="utf-8").strip()
            if len(notes) > 500:
                sys.exit(f"Release notes are {len(notes)} characters; Play allows 500.")
        name = a.aab.stem.split("-")[1] if a.aab.stem.count("-") >= 2 else str(code)
        print(f"Would upload {a.aab.name} ({a.aab.stat().st_size / 1e6:.0f} MB) as {name} ({code}) to '{a.track}'"
              f"{' as a draft' if a.draft else ''}, notes: {len(notes)} characters.")
        if not a.upload:
            print("Dry run: nothing changed (add --upload to do it).")
            return
        with a.aab.open("rb") as f:
            got = call(s, "POST", f"{UPLOAD}/edits/{edit}/bundles", params={"uploadType": "media"}, data=f,
                       headers={"Content-Type": "application/octet-stream"}, timeout=900)
        if int(got.get("versionCode", 0)) != code:
            sys.exit(f"Play read version code {got.get('versionCode')}, not {code}: stopping.")
        release = {"name": name, "versionCodes": [str(code)], "status": "draft" if a.draft else "completed"}
        if notes:
            release["releaseNotes"] = [{"language": "en-US", "text": notes}]
        call(s, "PUT", f"{API}/edits/{edit}/tracks/{a.track}", json={"track": a.track, "releases": [release]})
        call(s, "POST", f"{API}/edits/{edit}:commit")
        committed = True
        print(f"Uploaded {name} ({code}) to '{a.track}'. Google reviews it before testers get it.")
    finally:
        if not committed:                                  # a dry run, or a stop: throw the edit away
            s.delete(f"{API}/edits/{edit}", timeout=30)


if __name__ == "__main__":
    main()
