---
name: mygeeky-play
description: Use when preparing, checking or submitting the myGeeKy phone app for Google Play, or changing anything that Play reviews -- Android permissions (mobile/app.json), the target API / Expo SDK, signing, the Data safety answers, the privacy policy, in-app links to it, Signals' user content rules, the store listing (docs/play/), or what data leaves the phone. Holds Play's current rules with dates and sources, where myGeeKy stands on each, the gaps still open, and the automatic check (tools/play_check.py).
---

# myGeeKy on Google Play

**Never submit, upload or start an EAS build without the maintainer's go-ahead** (`CLAUDE.md`). This skill is for
getting the app *ready* and checking it; the build and submit commands are in `mygeeky-release`.

The rules change every year. Each one below carries the date it was checked and its source: before relying on a
number, open the source and update this file if Google moved it.

## The automatic check

```bash
.venv/bin/python tools/play_check.py                 # the newest APK in dist/ (or the last local build)
.venv/bin/python tools/play_check.py some.apk --play # a given APK; --play also fails debug signing
```

It reads the APK only (aapt2, zipalign and apksigner from the SDK build-tools; the 16 KB ELF check in Python) and
says PASS / WARN / FAIL for: target API, permissions Play refuses, permissions myGeeKy doesn't need, foreground
service types, plain-HTTP traffic, debuggable, 16 KB zip alignment, 16 KB native libraries, the signing key. An AAB
(what Play receives) is checked by turning it into a universal APK first:
`bundletool build-apks --bundle app.aab --output a.apks --mode=universal` (bundletool isn't installed here; the
Console's App bundle explorer also shows its own 16 KB report).

Run it after any change to `mobile/app.json`, `mobile/package.json` (an Expo or native library upgrade) or
`eas.json`, and before every Play submission.

## Play's rules (checked 2026-10-21) and where myGeeKy stands

| Rule | myGeeKy |
|---|---|
| **Target API 36** for new apps and updates since **31 Aug 2026** (extension to 1 Nov 2026 on request); API 37 likely by Aug 2027, not announced. [target-sdk](https://developer.android.com/google/play/requirements/target-sdk) | ✅ Expo SDK 57 → compile/target 36, min 24. SDK 58 compiles against 37: move up before Aug 2027. |
| **16 KB memory pages**: updates that don't support them can't be released from **1 Feb 2027** (targets 35+, 64-bit). LOAD segments aligned ≥ 2¹⁴ and `zipalign -c -P 16` passes. [page-sizes](https://developer.android.com/guide/practices/page-sizes) | ✅ all 56 64-bit `.so` aligned, zipalign passes (AGP 8.12, `useLegacyPackaging=false`). The optional RELRO note (NDK r27) is unresolved: confirm in the Console's report; SDK 58 / NDK r28 should clear it. |
| **AAB + Play App Signing** for new apps. [9844279](https://support.google.com/googleplay/android-developer/answer/9844279) | ✅ `eas.json` production: `app-bundle`, `autoIncrement`, `appVersionSource: remote`. Let Google keep the signing key (`docs/play/ACCOUNT.md`). |
| **New personal accounts**: a closed test with **≥12 testers opted in for 14 days** before production. [14151465](https://support.google.com/googleplay/android-developer/answer/14151465) | Documented in `docs/play/ACCOUNT.md` §2. |
| **Privacy policy**: public URL in the Console **and a link inside the app**, matching the Data safety answers. [User Data](https://support.google.com/googleplay/android-developer/answer/10144311) | ⚠️ `website/privacy.html` exists; **no link in the app yet**; it says the app doesn't use the camera, but QR pairing does. |
| **Data safety**: anything that leaves the device is "collected" (SDKs included); exempt: on-device only, in-memory only, end-to-end encrypted. [10787469](https://support.google.com/googleplay/android-developer/answer/10787469) | ⚠️ the draft in `docs/play/LISTING.md` misses: the email typed for an OpenAlex key, sync to the user's GitHub repo (CV text, settings, history, votes), reading the user's own GitHub events (My month), the Signals beacon's public tags. Signals messages are E2E encrypted (exempt). In transit: HTTPS only. |
| **Account deletion** applies when the app (or a flow it links to) creates an account. [13327111](https://support.google.com/googleplay/android-developer/answer/13327111) | Probably out of scope (GitHub/ORCID sign-in only), but `app/home.tsx` links to github.com/signup. Cheap safety: a `mygeeky.org/delete.html` page with the steps (Start over, uninstall, delete the beacon and sync repos, revoke the GitHub grant) given as the deletion URL. |
| **User-generated content**: terms accepted before posting, prohibited content defined, in-app report and block, ongoing moderation. [9876937](https://support.google.com/googleplay/android-developer/answer/9876937) | ⚠️ Signals and calls for contributors are user content. Block and report exist; **no terms to accept** and no terms page. |
| **Prominent disclosure** right before data use a person wouldn't expect, with a way to decline. [11150561](https://support.google.com/googleplay/android-developer/answer/11150561) | Likely fine (data leaves only on the user's action); make sure turning on sync says it uploads the CV text to their GitHub. |
| **Restricted permissions**: QUERY_ALL_PACKAGES, exact alarms, READ_MEDIA_*, location, RECORD_AUDIO need a core-use declaration. [10158779](https://support.google.com/googleplay/android-developer/answer/10158779), [13161072](https://support.google.com/googleplay/android-developer/answer/13161072), [14115180](https://support.google.com/googleplay/android-developer/answer/14115180) | ✅ none (`play_check.py` fails if one appears). Camera: `expo-camera` with microphone off. Notifications: POST_NOTIFICATIONS asked only when turned on; fired immediately, no exact alarms. |
| **Foreground service types** for targets 34+. [13392821](https://support.google.com/googleplay/android-developer/answer/13392821) | ✅ only WorkManager's generic service, no typed one; watch for a Console prompt. |
| **Security**: no cleartext HTTP, exported components protected, tokens in secure storage, backups excluding secrets. [cleartext](https://developer.android.com/privacy-and-security/risks/cleartext-communications) | ✅ no cleartext, no `http://` in `mobile/src`; exported: launcher activity (`mygeeky://`), system-permission-guarded services/receivers; tokens in SecureStore (Keystore), excluded from backup; no WebView; links open in the browser and only `https://`. |
| **Developer verification** (2026): live 30 Sep 2026 in BR/ID/SG/TH, **worldwide in 2027**, for apps on certified devices from any source. [developer-verification](https://developer.android.com/developer-verification/guides) | ⚠️ the GitHub test APKs are signed with the public **Android Debug** key: they can't be registered, and a Play build won't install over them (uninstall first). |

## Open gaps, in order

Blockers (or near-certain rejection):
1. **Privacy policy link in the app** (You → Settings / About, beside the support mailto in `components/you-parts.tsx`)
   -- and the desktop's ⚙ too (`mygeeky-platforms`). Fix the policy's camera sentence.
2. **Signals terms**: rules of use (what's prohibited, block and report, a beacon is public, how moderation works),
   accepted with "I agree" before setting up Signals or posting a call; published as `website/terms.html`, linked
   from the policy.
3. **Data safety answers** in `docs/play/LISTING.md` completed as above, and `privacy.html` saying the same.
4. **Reviewer access** (a way in without the maintainer's account) and fresh screenshots without a device frame.

Before submitting:
5. **Block unneeded permissions** in `mobile/app.json` → `android.blockedPermissions` (never edit `mobile/android/`,
   it's regenerated): SYSTEM_ALERT_WINDOW, USE_FINGERPRINT, READ/WRITE_EXTERNAL_STORAGE (check the document picker
   still works), the vendor launcher-badge permissions. `play_check.py` lists them.
6. **A data-deletion page** (`website/delete.html`) for the Data safety deletion question.

Good practice:
7. **Test APK signing**: sign the GitHub APK with a private release key (never committed; the keystore outside the
   repo), or send testers to the Play closed test instead.
8. **Network security config** with `cleartextTrafficPermitted="false"` via a config plugin (expo-build-properties),
   so HTTPS-only survives a future library.
9. **Verified App Link** for the ORCID return (`https://mygeeky.org/orcid`, `autoVerify`, `/.well-known/assetlinks.json`
   with Play's signing SHA-256) instead of the `mygeeky://` scheme.
10. Check expo-notifications' Firebase pieces in the Play SDK Index when filling in Data safety (no push is used).

When a gap is closed, move it into the table above and say how it was done.

## How to work a Play change

1. Read this file and `docs/play/ACCOUNT.md` / `LISTING.md`; open the sources of any rule you rely on.
2. Change config only through `mobile/app.json` / plugins (`npx expo install` for libraries, `mobile/AGENTS.md`).
3. Build a test APK (`mygeeky-release`), run `tools/play_check.py`, look at the app on the emulator (`mygeeky-phone`).
4. Anything about data, accounts or permissions also changes `website/privacy.html`, `docs/play/LISTING.md`
   (Data safety) and the in-app text: they must say the same thing.
5. Ask before any build on EAS or submission; say what would go out.
