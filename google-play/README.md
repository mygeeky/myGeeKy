# Google Play: everything for the submission

Everything the Play Console asks for, in one place. The `.aab` (the app itself) is built into this folder and
never committed (`.gitignore`).

| Console asks for | Here | Status |
|---|---|---|
| The app bundle (`.aab`), signed with the upload key | `myGeeKy-<version>.aab` | built by EAS (below) |
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
cd mobile
npx eas-cli@latest login                    # once: the Expo account (alsammans-team)
npx eas-cli@latest build -p android --profile production
```

The first build asks to create the upload keystore: let EAS create and keep it (losing it means never updating the
app again). The version code rises by itself. When it finishes, download the `.aab` into this folder.

## In the Play Console, in this order

1. **Create app**: name `myGeeKy`, app (not game), free, the declarations ticked.
2. **App content** (Policy → App content): privacy policy, ads (no), app access (the note), content rating,
   target audience, news app, Data safety, government/financial/health (no). All from `LISTING.md`.
3. **Store listing**: the texts, the icon, the feature graphic, the seven screenshots.
4. **Testing → Closed testing**: create a track, upload the `.aab`, add the testers (a Google Group), roll out,
   send them the opt-in link. Play App Signing: accept (Google signs, EAS keeps the upload key).
5. After **14 days with 12+ testers opted in**: Dashboard → apply for production access, then release to
   production.

Retaking any of these: the screenshots (`LISTING.md`, the note under the files), the app's pictures for the README
and website (`docs/make_screenshots.py`, `docs/make_phone_hero.py`).
