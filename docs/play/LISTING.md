# Google Play: listing and Play Console answers

Everything here is a draft to paste into the Play Console. Lines marked **(you decide)** are calls only you can make.

## Files in this folder

| File | Play Console field | Size |
|---|---|---|
| `icon-512.png` | App icon | 512 × 512 |
| `feature-graphic.png` | Feature graphic | 1024 × 500 |
| `screenshot-1.png` … `screenshot-6.png` | Phone screenshots (2–8) | 1080 × 1920 |

> **The screenshots are from 12 October and show the app before 🌱 Grow, 🎯 Chances and 🏆 Quiz.**
> Retake them before the listing goes up: Grow → Protocols, a quiz question mid-attempt, Chances →
> Funding, Skills, Badges. No device frame around them, or Play rejects them.

## Store listing

**App name** (max 30): `myGeeKy`

**Short description** (max 80):
`Grow your skills, find real chances, and keep your research moving. No tracking.`

**Full description** (max 4000):

```
myGeeKy is a quiet companion for people who work at a computer: developers and computer
scientists, bioinformaticians and data scientists, and researchers who analyse their own
experiments.

GROW
Pick a skill and follow a reviewed protocol: a short path of steps, each pointing at a real
tutorial, repository, paper or course that somebody checked by hand. Fourteen of them so far,
from Git and GitHub teamwork to statistics for experiments, from a first web app to
single-cell RNA-seq, from algorithms for interviews to turning images into numbers.

PROVE IT
Every protocol has a quiz. Each question quotes a sentence that is really on one of that
protocol's own sources, so any answer can be checked against the page it came from. Ten
questions an attempt, a mix of easy, applied and the real pitfalls. Only your best score
counts, one attempt a day, and you can flag a question you think is wrong.

FIND YOUR CHANCES
Jobs, funding calls and conferences, each one read and verified before it is listed, ranked
by how well it fits what you actually work on. Deadlines are checked, and anything past its
date disappears by itself.

KEEP UP WITHOUT THE NOISE
Rising papers in your field, the tools your field runs on, trending AI models, new launches,
and who builds what. Badges for the things you got done.

Signals (optional): private thank-yous between myGeeKy users. Each one is encrypted so only
the person it is for can read it, and no reply is ever expected.

PRIVATE BY DESIGN
• No myGeeKy account and no myGeeKy server: you sign in with GitHub or ORCID
• No analytics, no ads, no tracking
• What it learns about you stays on your phone
• Your GitHub token is kept in the phone's secure storage and only ever sent to GitHub
• It only reads public data. It never follows, stars or posts anything for you

Pair it with the desktop app by scanning a QR code, and the two show the same things.

myGeeKy is free and open source (MIT). The code, the reviewed protocols and every quiz
question are public at github.com/mygeeky/myGeeKy. It also runs on Windows, macOS and
Linux: mygeeky.org
```

**What's new** (max 500), for the first release:

```
The first release on Google Play.

Grow: 14 reviewed protocols with every link checked by hand.
Quizzes: 258 questions, each quoting the sentence on its own source that proves the answer.
Chances: jobs, funding and conferences, verified and matched to your work.
Pair with the desktop app by scanning a QR code.

No account, no adverts, no tracking. Free and open source.
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
