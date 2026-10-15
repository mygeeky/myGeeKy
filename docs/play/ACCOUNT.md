# Opening the Google Play developer account

What `LISTING.md` is for the store page, this is for the account behind it. Only the maker can do these
steps: Google wants one real person's identity and card.

**Decided:** a **personal** account, not an organisation one. It opens in days rather than weeks, and the
cost is the testing rule below — which is the long pole of the whole job, so start it first.

---

## 1. Sign up (about 30 minutes, then 1–3 days of waiting)

<https://play.google.com/console/signup>

| Screen asks | Answer |
|---|---|
| Google account | The Gmail account you already keep and can recover. The account you sign in with is **not** what buyers see, so there is no need to make a new one. |
| Account type | **Personal** |
| Developer name | **Your own name** (`Alsamman Alsamman`), *not* `myGeeKy`. It is account-wide: every app you ever publish is shown under it, so a tool-specific name reads wrongly under the next one. |
| Fee | **US$25, once**, by card. Not refundable, and it covers every app you ever publish. |
| Identity | A government ID and a selfie, through Google's verifier. The name must match the ID. |
| Address, phone | Verified by code. Not shown publicly. |
| Public profile email | Account-wide too, so **not** `support@mygeeky.org`: use an address that suits every tool. Each app sets its own **support email** separately, which is where `support@mygeeky.org` belongs. |
| About you | "I have an app ready to publish." No company, no D-U-N-S. |

**One account, every tool.** The $25 and the identity check happen once, and this account can publish
LYNXgwas, SciWeave or anything later. That is why the name and the public email are chosen to fit all of
them, not just myGeeKy: both can be changed afterwards, but they change for every app at once and can
send you back through verification.

Also check before typing it: the public email is verified by a code, and `support@mygeeky.org` is a
Cloudflare forward rather than a mailbox. Send a test to it from another account first.

Then wait for verification. Nothing can be submitted until it passes; everything in `LISTING.md` can be
prepared while it runs.

---

## 2. The testing rule, which is the real wait

A **personal** account opened after 13 November 2023 must run a **closed test** before an app may go
public: **at least 12 testers opted in, continuously, for 14 days**. It is **per app**, not per account —
every new app repeats it, though the same testers can carry over.

- Recruit **15–16**, not 12: one person dropping out stalls the count.
- Add them as a **Google Group**, not as individual emails. Then a replacement needs no new release.
- Each person must **press the opt-in link and accept**. Being on your list does nothing by itself, and
  this is where most of the fortnight gets lost.
- After 14 continuous days with 12+ opted in, apply for **production access** on the Console dashboard.
  Google then reviews it, which is a few days more.

Who to ask: colleagues, the lab, the Carpentries and bioinformatics circles, people who starred the repo.
Say plainly that it is a two-week opt-in and they can leave afterwards.

---

## 3. Then, in this order

1. Create the app in the Console with the package **`org.mygeeky.app`**.
2. Build the bundle: `cd mobile && eas build --platform android --profile production` (the `production`
   profile already makes an `.aab`, which is what Play takes — not an APK).
3. Upload it to a **Closed testing** track, add the testers' group, send the opt-in link. **The 14 days
   start now.**
4. While it runs: retake the screenshots, and fill in the Console answers from `LISTING.md`.
5. Day 14: apply for production access, then roll out.

Let Google sign the app (Play App Signing, the default); EAS keeps the upload key. Losing that key means
never updating the app again.

For later uploads, `eas submit -p android` needs a Play **service account** JSON (Console → Setup → API
access). That file is a credential: **GitHub Secrets or your password manager only, never the repo.**

---

## The two that get apps rejected

- **App access.** A reviewer cannot sign in with GitHub. Give them a throwaway GitHub account, or use the
  note in `LISTING.md`: setup accepts any public username (`octocat`) and the token is optional.
- **Screenshots.** The ones in this folder predate 🌱 Grow, 🎯 Chances and 🏆 Quiz, and Play rejects
  screenshots with a device frame drawn around them.

**Data safety:** answer it from `LISTING.md`, which says **yes, data is collected** — because the app
sends your username to GitHub to work at all, and Play counts that as collection even though myGeeKy has
no server. That is the careful answer; "collects nothing" reads better and is the kind of claim that gets
an app pulled later.

**Realistically three to four weeks** from signing up to a public listing, nearly all of it waiting.
