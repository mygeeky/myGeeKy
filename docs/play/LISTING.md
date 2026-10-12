# Google Play: listing and Play Console answers

Everything here is a draft to paste into the Play Console. Lines marked **(you decide)** are calls only you can make.

## Files in this folder

| File | Play Console field | Size |
|---|---|---|
| `icon-512.png` | App icon | 512 × 512 |
| `feature-graphic.png` | Feature graphic | 1024 × 500 |
| `screenshot-1.png` … `screenshot-6.png` | Phone screenshots (2–8) | 1080 × 1920 |

## Store listing

**App name** (max 30): `myGeeKy`

**Short description** (max 80):
`Your research field on your phone: papers, tools, AI models, people. No tracking.`

**Full description** (max 4000):

```
myGeeKy keeps you close to your field without the noise of social media.

Tell it your GitHub username (and, if you like, your ORCID iD and a few keywords). It learns what you work on, on your phone, and brings you what matters to that work:

• News: AI labs, journals and the tech press, ranked by your interests
• Papers: rising papers in your field, gaining citations fastest
• Repos: the popular, active tools your field runs on
• AI models: trending on Hugging Face, your field first
• Launches: new tools on Product Hunt
• People and activity: who builds the tools of your field, and who follows you
• Badges: small milestones as you read and explore

Signals (optional): private thank-yous between myGeeKy users. "Thanks", "I learned from your work", "I used your tool". Each one is encrypted so only the person it's for can read it, and no reply is ever expected. You can also invite people whose skills fit to help with one of your projects; each person's own myGeeKy decides whether your call fits their work, on their own device.

Private by design:
• No myGeeKy account, no myGeeKy server, no analytics, no ads
• What it learns about you stays on your phone
• Your GitHub token is kept in the phone's secure storage and only ever sent to GitHub
• It only reads public data. It never follows, stars or posts anything for you

myGeeKy is free and open source (MIT). It also runs on Windows, macOS and Linux: mygeeky.org
```

**App category** (you decide): Productivity (or Education)
**Tags**: Research, Productivity
**Website**: https://mygeeky.org
**Privacy policy**: https://mygeeky.org/privacy.html
**Contact email**: support@mygeeky.org (shown publicly on the listing; forwards to the maintainer's inbox)

## App content (Policy → App content)

**Privacy policy**: https://mygeeky.org/privacy.html

**Ads**: No, the app has no ads.

**App access**: All functionality is available without special access, except Signals. Note for reviewers:
> Setup asks only for a GitHub username. Enter any public username (for example `octocat`) and tap Continue; the token is optional. Signals (the 📡 planet) needs the user's own fine-grained GitHub token, so reviewers can skip it.

**Target audience** (you decide): 18 and over is simplest. Any age under 18 brings in the Families policy.

**News app** (you decide): the app shows headlines but is a research tool, not a publisher. Answering "No" is reasonable. "Yes" adds Google's news-app requirements.

**Content rating questionnaire (IARC)**:
- Category: "All other app types" (or Reference/News/Educational)
- Violence, sexuality, language, drugs, gambling: No
- **Users can interact or exchange content: Yes.** Signals and calls for contributors. Users can block anyone, and report them (to GitHub, where their beacon lives).
- Shares the user's location: No
- Digital purchases: No

**Data safety** (as accurate as I can make it; you confirm):
- Does the app collect or share user data? **Yes** (it sends data to GitHub to work, which Play counts as collection even without a myGeeKy server)
- Is all data encrypted in transit? **Yes** (HTTPS only)
- Can users ask for their data to be deleted? **Yes**: "Start over" in the app forgets settings and sign-in, uninstalling removes everything on the phone, and the user can delete their own `mygeeky-beacon` repository on GitHub
- Data types:

| Type | Collected | Shared | Required? | Purpose |
|---|---|---|---|---|
| Personal info → User IDs (GitHub username, ORCID iD) | Yes | No | Username required, ORCID optional | App functionality, Personalization |
| App activity → Other user-generated content (Signals, calls for contributors) | Yes | No | Optional | App functionality |
| App activity → App interactions | **No**: what you open is kept on the phone only | | | |
| Location, contacts, photos, files, health, financial | No | | | |

Camera: used only to scan the QR code from the desktop app; no picture is saved or sent. That's a permission, not data collection.

**Government app / Financial features / Health**: No.

## Before the first upload

1. Create the developer account (play.google.com/console, $25). For a new personal account, Play asks for **a closed test with at least 12 testers for 14 days in a row** before production access.
2. Build: `npx eas-cli@latest build -p android --profile production` (an `.aab`; the version code rises on its own).
3. Create the app in the Play Console with the package `org.mygeeky.app`. Upload the first `.aab` by hand on a Closed testing track. After that, `eas submit -p android` can upload new builds with a Google service-account key.
4. Let Google sign the app (Play App Signing, the default). EAS keeps the upload key.
