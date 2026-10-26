# Opening the Google Play developer account

> **Where it stands (2026-10-23):** the account is open and verified. The app `org.mygeeky.app` was created, every
> App content declaration and the store listing filled in (as in `LISTING.md`), and the first closed test
> (Closed testing – Alpha, 11800 / 1.18.0, 178 countries, the "myGeeKy testers" email list of 16 + the maker, feedback
> support@mygeeky.org) was **sent for review on 2026-10-23**. Next: once approved, send the opt-in link; 14 days from
> 12+ opted in; then apply for production.

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
2. Build the bundle: `python tools/play_bundle.py` (an `.aab`, which is what Play takes, not an APK; see
   `README.md`).
3. Upload it to a **Closed testing** track, add the testers' group, send the opt-in link. **The 14 days
   start now.**
4. While it runs: fill in the Console answers from `LISTING.md` (the screenshots are ready in `screenshots/`).
5. Day 14: apply for production access, then roll out.

Let Google sign the app (Play App Signing, the default); you keep the upload key (`README.md`). Losing it means
asking Play support for a new one, which takes days: keep a backup.

Uploads are by hand in the Console. Automating them later would need a Play **service account** JSON (Console →
Setup → API access): a credential, so your password manager only, never the repo.

---

## The two that get apps rejected

- **App access.** A reviewer cannot sign in with GitHub, and doesn't need to: the note in `LISTING.md` tells
  them to tap Start, skip GitHub and ORCID, and type a few keywords or *Continue without* (1.18.0 still says *Continue as guest*), which opens everything but the parts that read their own GitHub account.
- **Screenshots.** Play rejects screenshots with a device frame drawn around them. The ones in `screenshots/`
  (22 October 2026, app 1.17.1) have none.

**Data safety:** answer it from `LISTING.md`, which says **yes, data is collected** — because the app
sends your username to GitHub to work at all, and Play counts that as collection even though myGeeKy has
no server. That is the careful answer; "collects nothing" reads better and is the kind of claim that gets
an app pulled later.

**Realistically three to four weeks** from signing up to a public listing, nearly all of it waiting.

## Google Drive sign-in (Google Cloud project, set up 26 Oct 2026; for ideas 36–37)

- **Project:** `myGeeKy` in console.cloud.google.com, Google Drive API enabled. Domain `mygeeky.org` verified in
  Search Console (a TXT record in Cloudflare DNS, added by Google's Cloudflare button: **never remove it**).
- **Consent screen** (Google Auth Platform): External, **In production**, brand verified and published. Home page,
  `privacy.html` (its *Google Drive (optional)* section and the Limited Use sentence are what Google checks) and
  `terms.html`; authorised domain `mygeeky.org`; no logo yet (adding one re-checks the brand).
- **One scope only: `drive.appdata`** (non-sensitive). The "100 user cap" shown on the Audience page counts only
  unapproved sensitive or restricted scopes, so it doesn't apply. **Never add another scope**: `drive` is restricted
  (verification plus a yearly paid security assessment).
- **Clients:**
  - Desktop app `myGeeKy desktop`: ID `897067171099-a87clp5keoh0lh1e7afsdfkd70c43iob.apps.googleusercontent.com`;
    its JSON (with the secret, which Google treats as not confidential for desktop apps) is kept outside the repo in
    `~/.config/mygeeky-google/client.json` (mode 600).
  - Android, package `org.mygeeky.app`, one client per signing key (their client IDs end `-ekoba3goh4…`,
    `-15fdu87hr5…` and `-6ndflk23m1…`, in the order they were made; the JSON files, which hold no secret, are in
    `~/.config/mygeeky-google/android-*.json`; the console shows which SHA-1 each one has):

    | Client | Key | SHA-1 |
    |---|---|---|
    | myGeeKy Play | Play app signing key (Play Console → App integrity → App signing) | `A4:BD:C7:07:4C:FA:0E:08:01:F2:03:A5:94:C6:79:53:45:A7:51:13` |
    | myGeeKy upload | upload key `~/.config/mygeeky-play/upload-keystore.jks` | `8C:1B:B2:0C:C6:C5:BD:F4:A4:20:6C:F7:E0:43:CB:D5:C5:2A:EA:1C` |
    | myGeeKy debug | `mobile/android/app/debug.keystore` (emulator dev builds) | `5E:8F:16:06:2E:A3:CD:2C:4A:0D:54:78:76:BA:A6:F3:8C:AB:F6:25` |
