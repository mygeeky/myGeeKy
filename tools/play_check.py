"""Play check: does a built phone app meet Google Play's technical rules? (the mygeeky-play skill)

    python tools/play_check.py                         # the newest APK in dist/ (or the last local build)
    python tools/play_check.py path/to/app.apk         # a given APK (an AAB: turn it into an APK with bundletool)
    python tools/play_check.py --play                  # also fail what only a Play upload must avoid (debug signing)
    python tools/play_check.py --json

Reads the APK only; never builds, signs or uploads. Needs the Android SDK build-tools (aapt2, zipalign, apksigner)
under $ANDROID_HOME or ~/Android/Sdk; the 16 KB check of the native libraries is done here, in Python.

What each line checks, and why, is in .claude/skills/mygeeky-play/SKILL.md. The numbers to update when Google moves
them: MIN_TARGET_SDK (new apps and updates since 31 Aug 2026: API 36).
"""

from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_TARGET_SDK = 36                      # Play: new apps and updates from 31 Aug 2026 (extension to 1 Nov 2026)
PAGE_16K = 0x4000
FORBIDDEN = {                            # Play refuses these without a declaration myGeeKy can't make
    "android.permission.QUERY_ALL_PACKAGES": "only device search, antivirus, file managers and browsers",
    "android.permission.SCHEDULE_EXACT_ALARM": "only alarm, timer and calendar apps",
    "android.permission.USE_EXACT_ALARM": "only alarm, timer and calendar apps",
    "android.permission.READ_MEDIA_IMAGES": "use a picker (expo-document-picker) instead",
    "android.permission.READ_MEDIA_VIDEO": "use a picker instead",
    "android.permission.ACCESS_BACKGROUND_LOCATION": "myGeeKy has no use for location",
    "android.permission.ACCESS_FINE_LOCATION": "myGeeKy has no use for location",
    "android.permission.ACCESS_COARSE_LOCATION": "myGeeKy has no use for location",
    "android.permission.RECORD_AUDIO": "the QR camera never records sound",
    "android.permission.READ_CONTACTS": "myGeeKy never reads contacts",
    "android.permission.READ_SMS": "never",
    "android.permission.READ_CALL_LOG": "never",
}
UNNEEDED = {                             # not refused, but more than myGeeKy needs: block them in app.json
    "android.permission.SYSTEM_ALERT_WINDOW": "draws over other apps; the prebuild template's (blocked in app.json, debug keeps it)",
    "android.permission.USE_BIOMETRIC": "androidx.biometric, via expo-secure-store; myGeeKy never asks for a fingerprint (blocked in app.json)",
    "android.permission.USE_FINGERPRINT": "the same, for older Android (blocked in app.json)",
    # READ/WRITE_EXTERNAL_STORAGE come from expo-file-system, capped at Android 12 (maxSdkVersion 32): likely unneeded (files
    # come through the document picker), but only an Android 12 test can show it, and Play doesn't mind them capped.
}


def _sdk() -> Path | None:
    for base in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"), str(Path.home() / "Android" / "Sdk")):
        if base and (Path(base) / "build-tools").is_dir():
            tools = sorted((Path(base) / "build-tools").iterdir(), key=lambda p: [int(x) for x in re.findall(r"\d+", p.name)])
            if tools:
                return tools[-1]
    return None


def _run(tool: Path, *args: str) -> str:
    return subprocess.run([str(tool), *args], capture_output=True, text=True, timeout=120).stdout


def _apk(argv: list[str]) -> Path | None:
    given = [a for a in argv[1:] if not a.startswith("--")]
    if given:
        return Path(given[0])
    found = sorted(ROOT.glob("dist/myGeeKy-*-test.apk"), key=lambda p: p.stat().st_mtime)
    local = ROOT / "mobile/android/app/build/outputs/apk/release/app-release.apk"
    candidates = found + ([local] if local.exists() else [])
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def elf_load_aligns(data: bytes) -> list[int]:
    """The alignment of every LOAD segment of a 64-bit little-endian ELF library (what the 16 KB rule is about)."""
    if data[:4] != b"\x7fELF" or data[4] != 2:
        return []
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
    out = []
    for i in range(phnum):
        off = phoff + i * phentsize
        p_type = struct.unpack_from("<I", data, off)[0]
        if p_type == 1:                                    # PT_LOAD
            out.append(struct.unpack_from("<Q", data, off + 48)[0])
    return out


def check(apk: Path, play: bool = False) -> list[dict]:
    rows: list[dict] = []

    def say(name: str, verdict: str, detail: str) -> None:
        rows.append({"check": name, "verdict": verdict, "detail": detail})

    bt = _sdk()
    if bt is None:
        say("build-tools", "FAIL", "Android SDK build-tools not found (set ANDROID_HOME)")
        return rows
    badging = _run(bt / "aapt2", "dump", "badging", str(apk))
    m = re.search(r"targetSdkVersion:'(\d+)'", badging)
    target = int(m.group(1)) if m else 0
    version = (re.search(r"versionName='([^']*)'", badging) or [None, "?"])[1]
    code = (re.search(r"versionCode='([^']*)'", badging) or [None, "?"])[1]
    say("target API", "PASS" if target >= MIN_TARGET_SDK else "FAIL",
        f"targets API {target}; Play needs {MIN_TARGET_SDK}+ (version {version}, code {code})")

    perms = set(re.findall(r"uses-permission(?:-sdk-23)?: name='([^']+)'", _run(bt / "aapt2", "dump", "permissions", str(apk))))
    bad = sorted(p for p in perms if p in FORBIDDEN)
    say("permissions Play refuses", "FAIL" if bad else "PASS",
        "; ".join(f"{p.split('.')[-1]} ({FORBIDDEN[p]})" for p in bad) or f"none of {len(FORBIDDEN)} ({len(perms)} asked)")
    extra = sorted(p for p in perms if p in UNNEEDED)
    vendor = sorted(p for p in perms if not p.startswith("android.permission.") and "BADGE" in p.upper())
    say("permissions not needed", "WARN" if extra or vendor else "PASS",
        "; ".join([f"{p.split('.')[-1]} ({UNNEEDED[p]})" for p in extra] + ([f"{len(vendor)} launcher-badge permissions"] if vendor else []))
        or "none")
    fgs = sorted(p for p in perms if p.startswith("android.permission.FOREGROUND_SERVICE_"))
    say("foreground service types", "WARN" if fgs else "PASS",
        f"declare in the Console: {', '.join(fgs)}" if fgs else "none typed (WorkManager only)")

    manifest = _run(bt / "aapt2", "dump", "xmltree", "--file", "AndroidManifest.xml", str(apk))
    cleartext = re.search(r"usesCleartextTraffic\(0x[0-9a-f]+\)=\(type 0x12\)0xffffffff", manifest)
    say("plain HTTP traffic", "FAIL" if cleartext else "PASS", "usesCleartextTraffic=true" if cleartext else "not allowed")
    debuggable = re.search(r"debuggable\(0x[0-9a-f]+\)=\(type 0x12\)0xffffffff", manifest)
    say("debuggable", "FAIL" if debuggable else "PASS", "android:debuggable=true" if debuggable else "no")

    zip_ok = "Verification successful" in _run(bt / "zipalign", "-c", "-P", "16", "-v", "4", str(apk))
    say("16 KB zip alignment", "PASS" if zip_ok else "FAIL", "zipalign -c -P 16 " + ("passes" if zip_ok else "fails"))
    misaligned, libs = [], 0
    with zipfile.ZipFile(apk) as z:
        for name in z.namelist():
            if name.endswith(".so") and ("/arm64-v8a/" in name or "/x86_64/" in name):
                libs += 1
                aligns = elf_load_aligns(z.read(name))
                if aligns and min(aligns) < PAGE_16K:
                    misaligned.append(name.rsplit("/", 1)[-1])
    say("16 KB native libraries", "FAIL" if misaligned else "PASS",
        f"{len(misaligned)} of {libs} misaligned: {', '.join(sorted(set(misaligned))[:6])}" if misaligned
        else f"all {libs} 64-bit libraries aligned to 16 KB")

    certs = _run(bt / "apksigner", "verify", "--print-certs", str(apk))
    debug_key = "CN=Android Debug" in certs
    say("signing key", ("FAIL" if play else "WARN") if debug_key else "PASS",
        "signed with the public Android Debug key: never for Play; testers must uninstall before a Play build"
        if debug_key else (re.search(r"certificate DN: (.*)", certs) or [None, "unknown"])[1])
    return rows


def main(argv: list[str]) -> int:
    apk = _apk(argv)
    if apk is None or not apk.exists():
        print("No APK found: build one (mygeeky-release skill) or give its path.")
        return 2
    rows = check(apk, play="--play" in argv)
    if "--json" in argv:
        print(json.dumps({"apk": str(apk), "checks": rows}, indent=1))
    else:
        print(f"Play check: {apk}")
        for r in rows:
            print(f"  {r['verdict']:4s}  {r['check']:26s} {r['detail']}")
    worst = "FAIL" if any(r["verdict"] == "FAIL" for r in rows) else "WARN" if any(r["verdict"] == "WARN" for r in rows) else "PASS"
    print(f"verdict: {worst}")
    return 1 if worst == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
