# Google Play: everything for the submission

Everything the Play Console asks for, in one place. The `.aab` (the app itself) is built into this folder and
never committed (`.gitignore`).

| Console asks for | Here | Status |
|---|---|---|
| The app bundle (`.aab`), signed with the upload key | `myGeeKy-<version>-<code>.aab` | built here (below) |
| App icon, 512 × 512 | `icon-512.png` | ✅ |
| Feature graphic, 1024 × 500 | `feature-graphic.png` | ✅ (22 Oct 2026, the current tagline) |
| Phone screenshots, 2–8 | `screenshots/1-home.png` … `7-month.png` | ✅ (22 Oct 2026, app 1.17.1, 1080 × 1920) |
| App name, short and full description, what's new | `LISTING.md` → Store listing | ✅ paste as written |
| Category, website, contact email | `LISTING.md` → Store listing | ✅ (category: you decide) |
| Privacy policy | https://mygeeky.org/privacy.html | ✅ live |
| Data deletion URL (Data safety) | https://mygeeky.org/delete.html | ✅ live |
| Signals terms (user content) | https://mygeeky.org/terms.html | ✅ live |
| Data safety answers | `LISTING.md` → Data safety | ✅ checked against the code |
| Content rating (IARC), ads, target audience, news app | `LISTING.md` → App content | ✅ (audience, news: you decide) |
| App access (note for the reviewer) | `LISTING.md` → App access | ✅ *Continue as guest* |
| The developer account, the closed test (12 testers × 14 days) | `ACCOUNT.md` | your steps |

## Build the bundle

```bash
python tools/play_bundle.py                 # about 25 minutes; writes google-play/myGeeKy-<version>-<code>.aab
```

Built on this computer, no Expo account needed. It's signed with the **upload key**,
`~/.config/mygeeky-play/upload-keystore.jks` (alias `upload`), whose password is in the system keyring (service
`mygeeky-play-upload-key`). **Back up both** (the keystore file, and the password from
`python -m keyring get mygeeky-play-upload-key upload`) somewhere safe outside this computer. Google signs the app
for the store (Play App Signing), so a lost upload key can be reset through Play support, but that takes days.

Each upload needs a higher version code: `android.versionCode` in `mobile/app.json`, kept as
major × 10000 + minor × 100 + patch of the version (1.17.1 → 11701); the script refuses a mismatch.

## In the Play Console, in this order

1. **Create app**: name `myGeeKy`, app (not game), free, the declarations ticked.
2. **App content** (Policy → App content): privacy policy, ads (no), app access (the note), content rating,
   target audience, news app, Data safety, government/financial/health (no). All from `LISTING.md`.
3. **Store listing**: the texts, the icon, the feature graphic, the seven screenshots.
4. **Testing → Closed testing**: create a track, upload the `.aab`, add the testers (a Google Group), roll out,
   send them the opt-in link. Play App Signing: accept (Google signs for the store; you keep the upload key).
5. After **14 days with 12+ testers opted in**: Dashboard → apply for production access, then release to
   production.

Retaking any of these: the screenshots (`LISTING.md`, the note under the files), the app's pictures for the README
and website (`docs/make_screenshots.py`, `docs/make_phone_hero.py`).
