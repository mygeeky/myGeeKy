# Google Play: listing and Play Console answers

Everything here is a draft to paste into the Play Console. Lines marked **(you decide)** are calls only you can make.

## Files in this folder

| File | Play Console field | Size |
|---|---|---|
| `icon-512.png` | App icon | 512 × 512 |
| `feature-graphic.png` | Feature graphic | 1024 × 500 |
| `screenshots/1-home.png` … `7-month.png` | Phone screenshots (2–8), in this order | 1080 × 1920, no transparency |

> Taken 22 October 2026 on app 1.17.1, no device frame, Android's demo status bar (12:00): Home with its orbit of
> planets, Grow → Protocols (the folded dock), a quiz question answered with its source, Grow → Skills, Chances →
> Jobs, World → Papers, You → My month. To retake: `adb shell wm size 1080x1920` first (Play wants the long side at
> most twice the short one), then `adb shell wm size reset`. Leave out pages full of other people's names or other
> companies' brands (People, Live, the AI race).

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
• No myGeeKy account and no myGeeKy server: sign in with GitHub or ORCID, drop in your CV, or just give a few keywords
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

**Target audience** (you decide): 18 and over is simplest. Any age under 18 brings in the Families policy.

**News app** (you decide): the app shows headlines but is a research tool, not a publisher. Answering "No" is reasonable. "Yes" adds Google's news-app requirements.

**Content rating questionnaire (IARC)**:
- Category: "All other app types" (or Reference/News/Educational)
- Violence, sexuality, language, drugs, gambling: No
- **Users can interact or exchange content: Yes.** Signals and calls for contributors. Users can block anyone, and report them (to GitHub, where their beacon lives).
- Shares the user's location: No
- Digital purchases: No

**Data safety** (checked against the code and `website/privacy.html` on 2026-10-21; you confirm before entering it):
- Does the app collect or share user data? **Yes** (it sends data to GitHub, OpenAlex and others to work, which Play
  counts as collection even without a myGeeKy server). Nothing is **shared** in Play's sense: every transfer is one
  the user asks for, to a service they chose, and nothing goes to a myGeeKy server (there is none).
- Is all data encrypted in transit? **Yes** (HTTPS only; plain HTTP is refused by the app and by Android).
- Can users ask for their data to be deleted? **Yes**. Deletion URL: `https://mygeeky.org/delete.html`. In the app:
  *Start over* erases everything on the phone (settings, history, sign-in, tokens, the Signals key), as uninstalling does; the user can delete their own `mygeeky-beacon` and data repositories on GitHub and revoke
  myGeeKy's GitHub access in their GitHub settings.
- Data types:

| Type | Collected | Shared | Required? | Purpose | Where it goes |
|---|---|---|---|---|---|
| Personal info → User IDs (GitHub username, ORCID iD) | Yes | No | Optional (a guest needs neither) | App functionality, Personalization | GitHub, ORCID, OpenAlex (as searches) |
| Personal info → Name (*Find my papers*: the name and institution typed) | Yes | No | Optional | App functionality | OpenAlex, as a search |
| Personal info → Email address (only to get a free OpenAlex key) | Yes | No | Optional | App functionality | OpenAlex only; not kept by the app |
| App activity → App interactions (the interest terms of what you open, and which pages you use) | Yes, **only with a data repo connected** | No | Optional | Personalization | The user's own **private** GitHub repository |
| App activity → Other user-generated content (Signals status, interest tags, calls for contributors) | Yes | No | Optional | App functionality | The user's own **public** `mygeeky-beacon` repository |
| Messages (Signals) | **No**: end-to-end encrypted, only the recipient can read them (exempt) | | | | |
| Files and docs (*Drop a CV, thesis or abstract*) | **No**: read on the phone, not kept or sent; only the words the user keeps are saved | | | | |
| Location, contacts, photos/videos, audio, health, financial, web history | No | | | | |

Camera: asked only when the user taps *Scan from your computer* or *Receive a pack*, used only to read the QR code; no
picture or video is saved or sent, the microphone is never used. That's a permission, not data collection.

**User-generated content** (Policy → App content → if asked): users must agree to the Signals terms
(`https://mygeeky.org/terms.html`) before turning Signals on or posting a call; they can block anyone and report a
beacon (GitHub's abuse form, or support@mygeeky.org); a beacon that breaks the terms is hidden from every copy of the
app through the curated lists' `signals_hidden` (within hours).

**App access** (Policy → App content → App access): *All or some functionality is restricted*? **No login needed.**
Note for the reviewer:

> myGeeKy works without any account. On first launch choose **Continue as guest** (or type a few research keywords,
> e.g. "genomics, machine learning"): Home, World, Grow and Chances then work fully. Signing in with GitHub is optional
> and only adds features that read the user's own GitHub account (Live, People, My GitHub, Signals). Signals also
> needs a second, single-repository GitHub token the user creates themselves, so reviewers are not expected to test it;
> its terms are at https://mygeeky.org/terms.html.

**Government app / Financial features / Health**: No.

## Before the first upload

1. Create the developer account (play.google.com/console, $25). For a new personal account, Play asks for **a closed test with at least 12 testers for 14 days in a row** before production access.
2. Build: see `README.md` in this folder (an `.aab`; the version code rises on its own).
3. Create the app in the Play Console with the package `org.mygeeky.app`. Upload the first `.aab` by hand on a Closed testing track. After that, `eas submit -p android` can upload new builds with a Google service-account key.
4. Let Google sign the app (Play App Signing, the default). EAS keeps the upload key.
