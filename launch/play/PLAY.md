# Putting myGeeKy on Google Play

The phone app (`mobile/`, package `org.mygeeky.app`) on the Play Store, step by step. Only the maker can
do the account parts: Google wants one real person's identity and card, and neither can be automated.

**The decision already made:** a **personal** developer account. That is the quick one to open, and it
carries one real cost — see "The 12-tester rule" below, which is the long pole of this whole job. Start
the closed test as early as you can; everything else can be finished while its 14 days run.

---

## 1. The account (about 30 minutes, then a few days of waiting)

At <https://play.google.com/console/signup>:

| What | Use |
|---|---|
| Google account | A Google account you will keep. `support@mygeeky.org` forwards to Gmail, so a Google account on that address keeps store mail out of your personal inbox. |
| Developer name | `myGeeKy` — this is what buyers see. It can be changed later. |
| Account type | **Personal** |
| Fee | **US$25, once**, by card. Not refundable. |
| Identity | A government ID and a selfie, through Google's verifier. Your legal name must match the ID. |
| Address and phone | Verified by code. A personal address is fine; it is not shown publicly. |
| Contact email | Shown on your store listing, so use `support@mygeeky.org`, not a private address. |

Verification usually takes **1–3 days**, sometimes longer. Nothing below can be submitted until it passes,
but everything below can be *prepared* now.

---

## 2. The 12-tester rule — start this first

Any **personal** account opened after 13 November 2023 must run a **closed test** before the app may go
public: **at least 12 testers opted in, continuously, for 14 days.** It applies to every new app, and the
clock only runs while 12 people are actually opted in — if one drops to 11 on day 9, the counter suffers.

So: recruit **15–16**, not 12, for the drop-outs.

How it goes:

1. In Play Console: **Testing → Closed testing → Create track**, upload the AAB (section 4).
2. Add testers by **Google account email**, or make a Google Group and add the group — a group is far
   easier, because you can add a replacement without a new release.
3. Send each person the **opt-in link** Play gives you. **They must press it and accept** — being on the
   list is not enough, and this is where most of the 14 days get lost.
4. After 14 continuous days with 12+ opted in, **apply for production access** on the Console dashboard.
   Google then reviews, which takes a few more days.

Who to ask: colleagues, the lab, people in the Carpentries and bioinformatics circles, anyone who has
starred the repo. Tell them plainly that it is a two-week opt-in and that they can leave afterwards.

---

## 3. The store listing — the text is written, the pictures are not

**Name** (max 30): `myGeeKy`

**Short description** (max 80):

> Grow your skills, find chances, and keep your research work moving.

**Full description** (max 4000): draft in `LISTING.md` next to this file.

**Graphics Google requires:**

| Asset | Size | Status |
|---|---|---|
| App icon | 512×512 PNG | `mobile/assets/icon.png` — check it is 512 and has no transparency |
| Feature graphic | 1024×500 PNG/JPG | **to make** |
| Phone screenshots | 2–8, at least 1080px on the short side | **to make** (take them in the running app) |
| Tablet screenshots | optional | skip for now |

**Privacy policy URL:** <https://mygeeky.org/privacy.html> — already live and required.

---

## 4. The build

`eas.json` is already right: the `production` profile builds an **app bundle** (`.aab`, what Play wants,
not an APK) with `autoIncrement`, and `appVersionSource: "remote"` keeps the version code on EAS's side so
two builds never collide.

```
cd mobile
eas build --platform android --profile production
```

The first production build asks to create an **upload key** — let EAS keep it, and leave Play App Signing
on. Losing that key means never updating the app again, so if you ever hold it yourself, back it up.

Then either upload the `.aab` by hand once, or set up `eas submit` with a Play **service account** JSON
(Play Console → Setup → API access). That JSON is a credential: **GitHub Secrets or your password manager
only, never the repo**.

---

## 5. The forms Google asks, answered from what the app actually does

I read the phone app's code for these. They are declarations under your name, so read them before you
tick them.

**Data safety** — the honest answer is **no data collected and none shared**:

- There is **no myGeeKy server**. The app talks to GitHub, ORCID, OpenAlex and a few public feeds
  directly from the phone; `mygeeky.org` is a static site.
- Your GitHub token lives in the phone's **secure store** (`expo-secure-store`), never leaves it, and is
  deleted when you sign out.
- Quiz answers, scores and protocol progress stay **on the phone**.
- The **camera** is used only to scan the QR code that pairs the phone with the desktop app. Nothing is
  recorded or uploaded — declare it as processed on the device, not collected.
- **No analytics, no ads, no tracking SDKs** — I checked: there is no Firebase, no AdMob, no Sentry.

**Content rating:** answer the questionnaire honestly; a tool with no user content, violence or purchases
comes out "Everyone" / PEGI 3.

**Target audience:** 18+ (researchers and developers). Do not tick children, or you inherit the Families
policy.

**Ads:** none.

**App access:** the app needs a GitHub sign-in, so reviewers cannot see it cold. Under **App access →
All functionality is restricted**, explain the QR pairing and give them a throwaway GitHub account's
credentials, or Google will reject it for being untestable.

**Account deletion:** myGeeKy creates no account on any server of ours — the sign-in is GitHub's. Say so
in the form, and point at Settings → sign out, which deletes the stored token.

---

## 6. The order to do it in

1. Open the account and pay the $25 — the verification days start running.
2. Build the AAB and put it on a **closed testing** track.
3. Recruit 15–16 testers and make sure each one **presses the opt-in link**. The 14 days start now.
4. While that runs: feature graphic, screenshots, the listing text, the forms above.
5. Day 14: apply for production access, then roll out.

Realistically **three to four weeks** from today to a public listing, nearly all of it waiting.

---

## What is still open

- The feature graphic and the phone screenshots.
- A signed production build, which needs the Expo side sorted (a paid plan, or the free queue).
- The throwaway GitHub account for the reviewers.
