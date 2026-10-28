# Changelog

What changed in each myGeeKy release. Versions before 0.20.0 are described in
[GitHub Releases](https://github.com/mygeeky/myGeeKy/releases).

## 0.40.0 (2026-10-28): Play with GeeKOc, fourteen games, and settings inside the panel (phone 1.22.0)

- **🎮 Games: Play with GeeKOc, fourteen games** (computer and phone). A Games entry in the main menu opens a page of every game with its icon, level, best score and progress: Word Hunter, Rise, GeeKOc goes home, GeeKOc run, Flappy GeeKOc, Whack-a-bug, Real tool or made up?, Gene or Pokémon?, Reviewer 2 attacks, Debug reef, Sort the catch, Fix the figure, Which came first? and Terminal typing (pick a right command; on the computer, type it for a bonus). They run on GEMS, one rulebook on both apps: a core pack of 283 sourced items; rounds picked about 70% from your field, 20% new and 10% due again (spaced repetition), harder items unlocked by level; points, stars, game and player levels; a mistake always says why; the Model learns from the topics you play, by right answers and playing time; new badges: Player, Sharp, Level Up. See docs/GEMS.md.
- **The folded menu fits short screens** (computer): its tiles get closer together instead of making the panel taller than the screen (with no GitHub account the panel needed 836 px; now 372).
- **Settings pages without a second menu, and they fit** (computer). Each settings page had its own row of buttons for the other settings pages, though the side menu already lists them: the row is gone. Beside a pinned menu some settings were cut off on the right; the account buttons now go one to a row when narrow, the WISEP buttons one to a line, and the pack's research field is short (its names in the tooltip).
- **Up a level works with the menu pinned** (computer). With the side menu pinned open, "‹ back" climbed from wherever the menu was browsing, not from the page: on Settings it said "‹ All sections", and on Home it showed a "‹ Home" that did nothing. It now always climbs from what the panel shows, and the menu drops down to the page you open.
- **No stray "Turn Signals off" window** (computer). Opening Accounts with Signals on also opened a small, nearly empty window beside the panel: an old hidden button being shown with nowhere to sit. It no longer appears.
- **Settings open inside the panel** (computer). Opening Accounts or any other settings page took over the whole panel: the side menu, the way back and where-you-are disappeared, and only ⚙ again closed it. Settings is now a page like the others: the menu stays, the trail says Settings › Accounts, "‹ Settings" goes up a level, and ⚙ still opens and closes it, returning to the page you were on.
- **Up a level takes the panel there** (computer). "‹ Grow" beside Grow › Skills used to move only the menu; now the panel shows that level too: Grow's pages as tiles with their counts, then all sections, then Home, as the phone's orbit does when you go back. A tile opens its page, or its own level when it has parts (Data). The menu moves with it.
- **The logo reads on the light theme** (computer). The opening animation's neon, half-transparent letters faded into a light background; on Frosted they now stand on the app icon's dark badge. The header's "myGeeKy" takes the theme's title colour.
- **Badges read on the light theme** (computer and phone). A badge's inside was see-through, which looked faint on Frosted; it is now a solid shade of its tier's colour (gold, silver, bronze), and the ring and the tier's word are darkened until they show. On the dark themes the tier's colour glows through the inside.
- **Every text follows the theme, not the computer** (computer): the panel now gives Qt the theme's colours and font, so any label, field, menu, tooltip or dialog that doesn't choose its own colour follows the theme. On a computer set to dark mode, some texts were white on Frosted. Each theme also names its font (the system's own UI font first), so the panel looks the same everywhere. The theme check now runs under a "hostile" system colour (white text under a light theme, black under a dark one), so anything that slips back to the computer's colour is caught.

## 0.39.0 (2026-10-27): What's new, a way back you can see, and the maker's Admin console (phone 1.21.0)

- **📰 What's new, first in News** (computer and phone): AI and technology news worth knowing, each item checked against its sources before it's shown, the newest first and nudged toward your field. It's the same for everyone and found from public sources, never from anything about you.
- **A way back you can see** (computer): beside where you are (*Grow › Skills*) a button says where it goes (*‹ Grow*), and the side menu has the same one, on its own line. Each press goes up a level, as the phone's Back does: the menu opens at the level above your page, then its group, then all sections, then Home.
- **The side menu's pin stands up when pinned** and leans when it isn't (computer), drawn in the theme's colours instead of an emoji.
- **Admin opens wide** (computer): the panel grows to fit Admin (up to 1120 px, never more than 85% of the screen) and goes back to your own width when you open anything else.
- **The maker's Admin console** (computer, for the maker): Admin opens wide with its own menu of nine sections: **Dashboard** (what needs you, adoption, today's budgets, the latest actions, and TRACE's eight plots), **Review** (news, listings, Highlights and quizzes in one place), **Publish** (exactly what goes to everyone, each link's site shown, and what went before), **Create**, **Outreach**, **Support**, **Inbox**, **Triggers** and **Settings** (with an activity log of every accept, publish, invite and reply).
- **TRACE** (computer, for the maker; `docs/TRACE.md`): a new YouTube video, feed entry or email from an allowed sender in the trigger inbox sets it off. TRACE looks around (the linked page, Hacker News, arXiv through WISEP), has DeepSeek write a short item from what it found, merges the same story told by several sources, and ranks what waits for the maker by how likely they are to accept it. It learns from the maker's Accept and Reject: each source earns a record (with its uncertainty), feeds are checked as often as they post, and a daily DeepSeek budget goes to the triggers most worth it, with a share kept for the maker and for new sources. Only allowed senders count, made-up links never get in, and nothing reaches users without the maker's Accept.
- **Support email in the console** (computer, for the maker): read support@mygeeky.org (read-only), let DeepSeek draft, improve, shorten or warm a reply from the email with personal details removed (a crash report is never sent to it), and send as support@mygeeky.org only after confirming. Users' emails stay on the maker's computer. The privacy policy says how.
- **The phone's Admin is an overview only** (phone): numbers from a small summary the computer writes (no names, no email addresses, no buttons that change anything), shown to the maker's GitHub account whether their data is in Google Drive or a repo. The old queue of admin actions from the phone is gone, on both apps.
- **Mailboxes read plain-text emails' links too** (computer), not only those in an email's HTML.
- **The maker's admin tools, made harder to misuse** (computer and phone). What the admin tab publishes to everyone (Chances listings, Highlights) is checked more strictly: a listing keeps its own link only when the pasted page says it word for word (a link the AI made up becomes the page itself); a translation can't add a link, an email, a phone number or a sum the English doesn't have; a Highlight always links to its DOI; every item is checked again just before publishing, and the Publish box lists each one with where its link goes. Both apps refuse links with a hidden `name@` in front of the site (`https://www.nature.com@evil.example`), backslashes or control characters, and the phone refuses a published list over 2 MB, as the computer does. An old action queued on the phone can change a listing's status, never its contents; an invite's email address can't carry extra recipients; message boxes show web text as text, never as HTML.

## 0.38.0 (2026-10-27): plain files in your own Google Drive, quicker, and a tidy-up (phone 1.20.0)

- **Your data is saved as plain files, no encryption** (computer and phone). Your settings and progress already live in your own private place (a hidden folder in your Google Drive, or your private GitHub repo) and travel over HTTPS, so the extra layer added in 0.37.0 is gone: no key, no recovery code, no *Encrypt it*. Drive and GitHub hold the same files under the same names, so switching copies them as they are. 0.37.0's encrypted copies in Drive are replaced by plain ones on the first sync; a GitHub repo syncs with git as it did up to 0.36.
- **Google Drive is quicker** (computer): files move four at a time and only the ones that changed, and after *Signed in with Google* the panel says it's copying your data instead of going quiet.
- **Google Drive's logo on the Saving sign** (computer and phone) when your data is saved there. On the phone the sign also lights up for Drive (it looked for a GitHub token before).
- **Fixes in syncing** (computer): a second computer can follow when another moved the data off Google Drive; where each computer saves is its own choice and no longer travels with your shared settings; a retry after Google asked for a fresh sign-in kept its upload intact; files that never sync (the model, caches, tokens) never come down from Drive either; two syncs at the same moment no longer collide.
- **Fixes on the computer**: turning on saving from ⚙ starts the automatic sync without a restart, and a profile change right after no longer switches saving off again; "Your setup" names Google Drive; the Signals windows are readable on the Frosted theme, as are badge tiers, Highlights' labels and "Is this you?"; text from other people's profiles shown in tooltips is always plain text; "We found your papers" only when it really did; the weekly run carries on past GitHub's hourly limit, and a limit or no internet is no longer saved as a crash report; finding your papers by name no longer fails when OpenAlex is unreachable.
- **Fixes on the phone**: switching from Drive to GitHub no longer loses what you opened just before; scanning your computer's code never changes where the phone already saves (it fills in your repo's name); a full queue of what you opened no longer drops the newest; Badges syncs once when opened, not on every settings change; a build that can't use Google Drive says so.
- **New quiz questions arrive without an update** (computer and phone), as the docs always said: the question bank is fetched like the lists, at most twice a day.
- **Old code removed**: the encryption, and functions nothing called anymore, on both apps.

## 0.37.0 (2026-10-26): save your data in Google Drive, encrypted on your devices (phone 1.19.0)

- **Save your data in Google Drive, encrypted** (computer and phone). Saving your settings and progress now asks one question: **Google Drive** (recommended: one sign-in, nothing to renew) or **a GitHub repo**, never both, and you can switch later. myGeeKy asks Google for one thing only, its own hidden folder in your Drive; it can't see your other files. The computer's setup and the phone's start ask it too (the phone's start has a fourth step, *Where should I save your settings and progress?*), and Settings → Accounts has it on the Saving card: Sync now, Switch to GitHub / Google Drive, and your recovery code.
- **Everything you save is encrypted on your devices** (computer and phone), in Google Drive and in a new GitHub repo alike, so the storage only ever holds unreadable files: not Google, not GitHub, nobody but your devices can read them. The key is made on your first device and reaches the others by the Connect your phone QR code or by a **recovery code** shown once (keep it safe: lose every device and the code, and nobody can read the data). An older repo stays as it was until you click **Encrypt it** on a computer, which also drops its readable history from GitHub; your other computers follow by themselves.
- **Syncing moves only what changed**: logs are kept one small file per month (and per device), compressed before they're encrypted, and a file is only fetched when its fingerprint changed, so a daily sync sends a few small files instead of whole histories.
- **Connect your phone works without GitHub** (computer): the QR code now also carries where your data is saved and its key, and needs only a profile (ORCID or keywords are enough).
- **⚙ Settings, split into six parts** (computer and phone): the last main is called Settings again, and holds **Accounts**, **Your profile**, **Look** (Look and window on the computer), **Notifications**, **Data & privacy** and **Help**. **Accounts** comes first: GitHub and ORCID, then saving your data and Signals, then your other device; a connected one folds into a green line, the optional ones say why you might want them, one whose access stopped working is red with what to do, and a yellow line (and a count on the planet) says what needs you, never nagging about what's optional. The token picture steps sit right on the card. On the computer the ⚙ panel gets a row of buttons to move between its pages. The same cards and words on both apps (accounts.py / accounts.ts).
- **Four signs beside the page's name** (computer and phone): GitHub, ORCID, Saving (your private data repo) and Beacon (Signals). Each is lit when it's on and faint when it was never set up. Saving and Beacon (and a GitHub sign-in) turn red when their access expires or stops working, and a small message reminds you to renew, at most once a day. Click or tap a sign to see what it means. They use only what myGeeKy already checks (the daily token check, the last sync), with no extra requests.
- **••• More, the last main** (computer and phone): it holds ⚙ Settings and ❓ Help. Settings left You on the phone (the ⚙ button stays on the computer, as a shortcut); the Settings page says what it holds.
- **Start over starts empty** (phone). It erased what was stored, but the running app kept its copy of your settings, and the new start filled itself from it (your old ORCID showed up again). Start over now forgets both, and the start is always empty.
- **GeeKOc's eyes stay white** (phone). Now and then, as his frames changed, an eye drew black; each frame is now a fresh drawing, with no clip paths.
- **A new start on the phone, one question a screen.** GeeKOc welcomes you, swimming (a tap makes him cheer; "Tap me" in five languages beneath him), with **Start** and **Scan from your computer**. Then link GitHub or **Skip for now**, sign in with ORCID (or find your papers by name) or skip, and last *Can you give me one of these?*: three keywords, your CV, or your ORCID iD, each a row that unfolds, or **Continue without**, and myGeeKy learns your field from what you open and like. Back (and Android's Back) goes to the step before. The data repo and Signals are no longer asked here: You → Model, the Signals page and scanning the computer's code have them.
- **Android's Back goes up a level** (phone). It ended the app from anywhere; now it closes a tour or an open card, then climbs the menu (Leading lights → Researchers → Circle → all sections) showing where you are, then goes Home; only on Home does it leave.
- **The folded menu says it opens** (phone): a "Sections" pill with the app's pink-to-violet edge and what's new in it, whose arrow lifts three times when it appears (then stays still, to spare the battery; still with reduce motion).
- **⚙ has the panel to itself** (computer). On a short screen (1366 × 768) ⚙ got about 300 px, with "Signed in as", the badges and where you are still taking room under it; now they step aside while ⚙ is open and come back when it closes.
- **Long names fit in the side menu** (computer). "Researchers" and "Leading lights" were cut to "Research…"; the menu is a little wider (140 px) and a long name shrinks slightly before it's ever cut.
- **🌟 Leading lights** (computer and phone, Circle → Researchers). Living people who lead your field — Nobel and other prize winners, the most cited on a topic, the people behind famous tools — four at a time, picked by your Model, a new set every three days. Each shows why they're here, their latest papers, Follow and their Scholar / ORCID link; a tap opens their report (numbers, the last ten years, topics you share, most cited papers). A first sample list of 112 people (Nobel Medicine and Chemistry, Turing Award, lupus, GWAS, and the people behind scikit-learn, Seurat, PLINK and Bioconductor), drafted from Wikidata and OpenAlex by `tools/lights_build.py`.
- **Follow works again in Researchers** (computer). The Follow buttons in Following, Suggested and Network handed the click's "checked" flag to the action instead of the person, so following someone failed in the background.
- **Datasets open when you click them** (computer). A dataset on Home, the "new datasets" banner's list and every card in Grow → Data did nothing: Zenodo, Figshare and NCBI weren't on the panel's list of links it may open. Now the checked datasets in Data (their page, download and tutorial) and the ones the dataset radar found on those sites open in your browser; any other link stays blocked as before.
- **No more false "hard crash" reports on Windows** (computer). Windows raises some errors inside its own COM and accessibility code and handles them itself (code 0x8001010d, seen while the intro played on Windows 11), but Python's crash recorder writes them down anyway, and myGeeKy then offered them on the next start as "the program closed". These are no longer counted, and a panel that closed normally now says so in its log, so only a real crash is offered.
- **Grow opens on Skills** (computer and phone). Highlights moved to the end of Grow until there are more of them, and 🤝 Collaborators is hidden for now: it matches you with other myGeeKy users on Signals, and there are still too few for it to find anyone. GeeKOc's Grow tour follows the new order.

## 0.36.0 (2026-10-23): GeeKOc shows you around, ❓ Help, and crash reports by email (phone 1.18.0)

- **Crash reports without GitHub** (computer). The "Something went wrong" window has **Email it**, which opens the cleaned report as a ready-made email to support@mygeeky.org in your own mail app, and **Copy report** for the whole thing. You still see exactly what goes and press Send yourself; nothing goes through a myGeeKy server.
- **GeeKOc shows you around** (computer and phone). The first time myGeeKy opens, GeeKOc asks which language you'd like (English, Français, العربية, 中文) and walks you through the places that fit what you gave at setup: GitHub, ORCID, both, a CV, or just keywords. Every tour visits Seasons and Jobs right after Home; each stop opens the page and points at where it lives in the menu, his arms swimming as he talks. It ends with what more you'd get by adding GitHub, ORCID or a CV, the five things myGeeKy never does, and *Your geeky friend who helps you grow, quietly.* Skip ends it; it comes back by itself only when an update brings new stops, and never under tests or on CI.
- **❓ Help, a new main** (computer and phone, last in the menu): start any tour again (the one that fits you, Settings, or one for each main), pick the tours' language, and read fourteen questions and answers on how and why myGeeKy works, in the same four languages.
- **Home cards fit beside a pinned menu** (computer). With the side menu pinned, Home was wider than its space and the right edge of every card, Open ↗ included, was cut off; the "new · updated" line and a long "See all in …" now wrap instead.

## 0.35.2 (2026-10-22): Home cards that open with a tap, and the phone first (phone 1.17.2)

- **Home cards open with a tap** (computer and phone). Tapping anywhere on a card opens the article, paper, repo or job itself, and its button is now a coloured **Open ↗** instead of a small grey arrow. The link to the page the card came from reads **See all in News** (no arrow), so it no longer looks like the way to open the card.
- **The phone first** on mygeeky.org and in the video: the website now opens with the phone app (seven of its screens), then "And on your desktop" with what the panel adds; the video is a new 3-minute tour, phone then desktop. New pictures from this version for the README, PyPI and the website.
- **The phone app no longer asks for fingerprint permissions** at all (they came in with the secure store's library and were never used).

## 0.35.1 (2026-10-22): delete your data, and a Start over that starts over (phone 1.17.1)

- **Delete your data, step by step**: mygeeky.org/delete.html says how to remove everything myGeeKy keeps, on your phone, your computers and in your own GitHub repos (there is no myGeeKy account or server to delete from). Linked from the privacy policy and the site's footer; it's the deletion link Google Play asks for.
- **Start over really starts over** (phone): it now also erases the data-repo token, the Signals token, this phone's Signals key and an OpenAlex key, as uninstalling would; before, they stayed in the phone's secure store.
- **Turning on sync says what goes there** (computer and phone): the text of your CV from a computer, and from the phone the words and kind of each thing you open.

## 0.35.0 (2026-10-21): ready for Google Play, and sync that gets through (phone 1.17.0)

- **Sync gets through again** (computer). An older myGeeKy had committed its GitHub cache (up to 432 MB) into syncs that never reached GitHub; the newer version stopped carrying the cache, but those waiting syncs still held it, so every upload -- in setup too -- stalled for a minute and failed with "Operation too slow", and nothing from that computer reached the others. Before uploading, waiting syncs that carry a file too big for GitHub are now folded into one holding exactly today's files (the cache stays on the computer); a file that big that is meant to sync is named instead of stalling.
- **Planets that open into more wear a dotted ring** (phone). In the orbit and the folded dock, a planet with pages inside has a dashed ring that turns slowly (once every 14 seconds, only while you can see it, and not at all with reduce motion on); a page has none, and a planet you opened loses it in the centre. It replaces the small bar under the planet.
- **Admin on the phone is a glance** (phone): downloads, stars, people on Signals and how much is waiting on your computer, as numbers only -- no names, emails or buttons that change anything; reviewing, inviting and publishing are on the computer. It opens for the GitHub account that owns your data repo, with no fingerprint lock, so the app no longer asks for fingerprint or face permissions.
- **The Play build no longer asks to draw over other apps** (phone; the development build keeps it for its developer menu).
- Checks: the readability check reads Retina screens right and isn't fooled by gradient buttons; macOS has its own memory budget (270 MB, Linux and Windows keep 250) because it counts ~50 MB more for the same app.

- **Signals terms** (computer and phone). Before you turn Signals on or post a call for contributors, myGeeKy shows the Signals terms in five lines (your beacon is public; be kind and honest; never post someone else's private information; you can block and report; a beacon that breaks the rules is hidden from everyone) and asks you to agree, once (again only if the terms change). The full terms are at mygeeky.org/terms.html. A beacon that breaks them can now be hidden from every copy of myGeeKy through the public curated lists. Beacons already on keep working; the terms are asked at your next call.
- **Privacy policy and terms links inside the app**: You → Settings on the phone, ⚙ on the computer. The privacy policy now says exactly what leaves your device when you ask for an OpenAlex key (your email, to OpenAlex only) and when My month reads your own GitHub activity, and states plainly that the camera is used only to read a QR code.

- **Every text is readable in every theme** (computer). Switching to the light ❄️ Frosted theme left Home, ⚙'s notifications, packs, papers and CV sections in the dark theme's near-white text; now every part restyles itself when the theme changes. Coloured text -- the "Circle › People" line above each page, Home's card kinds, the "learning on this computer only" note -- was too pale on a light theme; it's now darkened (or lightened on a dark one) just enough to read. The Researchers "Find" button no longer shows white on light blue. A new check (`tools/theme_audit.py`) opens every page and part in every theme and lists any text that's hard to read: it finds none now (it found 143).
- **⚙ settings scroll** (computer). They used to share the panel with the page and were squeezed until their rows drew on top of each other; now ⚙ has the panel to itself while open, scrolls, and fits even the narrowest panel. Its three sliders share the theme's look.

- **Home uses less memory** (computer): its cards share one style instead of each label carrying its own, and it draws 12 cards at first (more as you scroll) instead of 20. Home's cards now take about 8 MB instead of about 19.

## 0.34.0 (2026-10-21): Neon Home that teaches your Model, and a wider panel (phone 1.16.0)

- **🏠 Home's cards are Neon, and do more** (computer and phone). Each card is outlined and softly glowing in its kind's colour (a plain outline in light themes) and shows what makes it worth a look: a ring counting down the days left on a job, grant or conference, a repo's stars and this week's gain, a dataset's size and licence, a model's downloads, and quiz questions you answer right on the card. A banner on top celebrates what's new ("3 new papers from your circle this week", "2 deadlines this week"), and the end says what you got through. New buttons: **♡ More like this** teaches Home *and* your Model (the card's topics, never names; it used to teach only Home), **🔖 Save** keeps a card in **🔖 Saved** at the top of Home, and **✕ Fewer like this** comes with **Undo**. Deadline cards no longer repeat "closes in N days" under the title (the ring shows it).

- **A wider panel, as wide as you like, with the menu on the screen-edge side** (computer). The open panel is 460px wide (was 380px, before the side rail took its share); drag its inner edge, or use **⚙ → Panel width**, for anything from 360 to 900px (double-click the edge: back to normal). A width you had chosen yourself is kept. The side rail now sits on the side nearest the screen's edge -- on the right for a panel on the right, on the left for one on the left -- and follows the panel when you move it; **⚙ → Menu side** puts it always left or always right.

## 0.33.0 (2026-10-21): 🏠 Home, a scrolling feed that learns what you enjoy (phone 1.15.0)

- **🏠 Home, a scrolling feed, is the first page** (computer and phone). Cards from every part of myGeeKy (new work from your circle, rising papers, open jobs, funding and conferences, new datasets, repos, people, headlines, AI models, a daily quiz question), new first, then "You're all caught up" and what you've seen. It learns what you enjoy from taps, 👍/👎 and time on screen (switch: ⏱ learning), with a small bandit over the kinds of card so it keeps trying every kind, at most two of a kind in any four, and one in five from new territory 🔭. Built only from what the other pages keep: no downloads while you scroll. Each card says why it's there and leads to its page. The ranking is the same on both apps (tested).
- **Your Model stops learning names** (computer and phone). Following someone could be learned 20+ times (when GitHub sent your list of follows short once, the same people looked newly followed on every check), and each time it learned their name and company ("jake", "wharton", "skylightfamily") as interests. Now a follow, star or fork counts once -- this also fixes what was already learned, without rewriting your data -- and a follow teaches the person's bio only; words from their username are never learned. Opening a person (a suggestion or a Home card) no longer teaches their login, the repo owner's name or how they were found ("followers", "type", "user"); opening a Home card teaches its title, not the authors under it or "closes in 9 days".
- **Home's time on screen** counts a quick scroll past as "not for me" (it never did: a card had to stay a full second to be counted at all); leaving Home or refreshing it no longer counts the cards on screen as skipped; on the phone, time isn't counted while another screen covers Home, and cards leaving the screen together no longer overwrite each other's lessons.

## 0.32.0 (2026-10-21): a side rail to find your way, and the phone signs in again (phone 1.14.0)

- **A side rail for moving around the panel** (computer). The row of six unlabeled planets is replaced by a narrow rail down the left: folded (46px) it shows the six groups with their "new" counts and the page you're on written down the side; opened (128px) it lists the groups by name, a group drops down its pages and a page its parts, and tapping again or ‹ (Esc) goes up a level. Every count sits on its icon (groups, pages and parts alike), so the open rail needs no column for numbers. Unpinned it opens over the page and folds after you pick; 📌 pins it beside the page (remembered). The line above the page says where you are in its group's colour. News keeps its own count again (the group count used to overwrite it with 0).
- **"GitHub said 401" on the phone is fixed.** When GitHub refuses the token (an 8-hour sign-in that couldn't renew, or a token that expired or was revoked), the phone forgets it, shows **Sign in with GitHub** again, and keeps reading public data without it, instead of failing on every screen. The phone used to keep the expired token when the renewal was refused. The computer now does the same on a refused token: it reads on without it (the token warning still tells you to make a new one).

## 0.31.0 (2026-10-21): lighter and quieter, measured (phone 1.13.0)

- **Lighter when nobody is looking** (from the resource audit, `docs/RESOURCES.md`): the interest map (the phone's Model page and the computer's) moves for a few seconds when it appears or you touch it, then rests -- it used to redraw 20-30 times a second for as long as the page was open (over a full CPU core on the phone); the live ticker stops while the panel is folded, hidden or minimised; Activity and Signals no longer rebuild their pages when the 60-second / 5-minute check finds nothing new; a sealed signal is decrypted once, not on every check; the panel syncs every hour (and when you quit) instead of every 15 minutes. **Nothing grows forever:** the suggestion and repo histories keep four months live (older lines go to compressed monthly archives on that computer, not synced); avatar photos are capped (600 on disk, 400 in memory); the weekly log rotates at 1 MB; WISEP's call tally keeps three months; the phone's WISEP store stays well under Android's per-row limit. **The panel uses 44% less memory and opens faster:** scikit-learn, SciPy and NumPy (about 140 MB and a second) load only when something needs them, not at startup; your CV's vocabulary is counted without them (the same result), and the Model page reads its weights from a small file saved with the model (313 → 175 MB). On the phone, the four biggest bundled lists (protocol model, curated lists, quiz, datasets) are read when their page first needs them, not at startup. Background work shares a small pool of threads (a page of photos no longer starts dozens at once); Activity asks GitHub about your matched people every 30 minutes instead of every 5; a sync with nothing new on either side is a single quick check; Chances builds its cards the first time you open it (half the panel's widgets at startup).
- **A resource audit** (`tools/resource_audit.py`, run on Windows, macOS and Linux by `.github/workflows/resources.yml`): storage (the data folder, its git history, caches, logs, the beacon), a leak test (every page round after round: widgets and memory must level off), idle CPU shown and hidden with the timers still running, and startup; the findings and the plan to make myGeeKy lighter are in `docs/RESOURCES.md`. Four files the program calls "never synced" (notifications state, rank seen, your GitHub events, "Is this you?") were still synced: they no longer are.

## 0.30.1 (2026-10-21): sync stops carrying databases, and WISEP counts credits right

- **Sync no longer carries live databases, and the data folder shrinks back.** The GitHub cache (24 MB) and WISEP's database had ended up in the synced data folder: every sync, from every computer, stored a new copy (a data folder of several GB, slow syncs, a slow setup), and a copy pulled over the open file damaged it (the `.broken-…` files). They now live beside the data folder (`mygeeky-local`), moved there once; files the ignore list names stop being carried even if an older version committed them; a computer still running an older myGeeKy can't break a sync or overwrite anything (its conflict on such a file is settled by leaving the file out); git's loose copies are packed when they pile up (gently: capped memory, never failing a sync); damaged cache copies are trimmed to the newest two; uninstalling erases the new folder too. Update every computer you sync: an older version's sync stops at that conflict until it is updated.
- **WISEP knows an OpenAlex text search costs 10 credits** (a filtered list 1, one record by id nothing), as OpenAlex's own headers say; it counted every search as 1.
- The tests can no longer touch your real data: programs they start get temporary folders, background jobs a test starts must finish inside it, and tests can't reach the internet.

## 0.30.0 (2026-10-21): people who publish, a wiser way to ask, and packs to share (phone 1.12.0)

- **📦 Packs:** share your setup like a seed, as one to three QR codes (⚙ Settings → Packs on the computer, You → Settings → Packs on the phone). Tick what goes in (keywords and topics, research field, researchers you follow, a note); the codes show one at a time ("Code 1 of 3", Next). The phone receives them: the first scan says how many codes there are, it counts them in any order and asks for the next, checks the set is whole, shows what the pack holds, then Merge into mine or Start from it, with Undo. No internet, no server; a pack is plain data, checked on arrival.
- **📄 Researchers** (Circle → Researchers), on the computer and the phone: people who publish, not only people on GitHub. Follow anyone by name (picked from OpenAlex's author search with the "is this the right one?" check; the list stays on your device), see their new preprints and papers as they appear (a preprint and its published version show as one: "now published · first as a preprint on bioRxiv"), and get suggestions for free from who cites you and who leads your field's rising papers. Everyone you follow is looked up in one batched search, each about as often as they publish, through WISEP. A new optional notification: New work from people you follow. **🕸 Network:** you, your co-authors, the people one introduction away and the people you follow, with who connects you to anyone; rebuilt weekly with two searches. Your Model learns gently from the topics your circle publishes on (switch it off on the Network page).
- **WISEP** (Wisely, a Systematic Statistically adapted system for API calling), on the computer and the phone: every call to OpenAlex (and the dataset radar's Zenodo, NCBI and Figshare calls) now goes through one gateway that keeps the answers, estimates how often each really changes, learns which pages you open and when (on your device only), and asks again only when a fresh answer is worth it, within a daily budget per source, spaced, backing off when a source is busy, and with OpenAlex's polite-pool contact. Budget left at the end of the day is spent in the evening on what you'll want fresh tomorrow. WISEP paces itself to OpenAlex's real budget, read from its answers: without a key, 1,000 credits a day shared by everyone on your network (a search costs 1, one record by id nothing); when it's spent, WISEP rests until midnight UTC and shows what it kept. A free OpenAlex key (Settings: OpenAlex emails you a link) gives you a budget of your own. Every user sees their own WISEP in ⚙ / You → Settings → How myGeeKy asks the internet: today's calls, what it answered from what it kept, GitHub beside it, what it learned (with a button to forget it) and the Auto / Always / Never switch. WISEP tunes itself: each kind of answer's expected rhythm becomes what your device actually saw once there are two weeks of it. And it takes over from the modules' old once-a-day timers (Cited by, Papers, the dataset radar) once it has proven itself (14 days, 100 answers, 40% from the cache, few failures). In a month-long simulation it makes 85% fewer calls than fixed timers with answers about as fresh; checked on Windows, macOS and Linux by a new workflow (docs/WISEP.md).
- **Data's fields are planets in the navigation** (Grow → Data → ✨ For you and the ten fields), on the computer and the phone, like News: no tabs inside the page.
- **The maker's Admin, in six sections** (You → Admin → 📊 Overview, 📥 Review, ✍ Write, 💡 Inbox, 🤝 People, ⚙ Settings), as planets on the computer and the phone. Overview counts what's waiting and lists exactly what 🚀 Publish would send; Review puts listings, Highlight drafts and quizzes together; Settings holds the DeepSeek key, the scout's sites and field, the mailbox and the GitHub cache.
- **Bring your own answer** (Admin → ✍ Write, on the computer): paste or import (.json / .txt) an answer written anywhere -- another AI, a colleague, by hand -- for a Highlight, listings or quiz questions. It goes through exactly the checks a DeepSeek answer does (facts from OpenAlex, titles and deadline quotes found in the page's text, quotes on the quiz's source page) and waits in Review. Each kind shows its JSON shape and copies the very prompt myGeeKy gives DeepSeek. No DeepSeek key needed.
- **🆕 New data on your topics** (Grow → Data → New), on the computer and the phone: once a day, a search with your own keywords for public datasets just out on Zenodo, NCBI GEO (new series) and Figshare. What's open, needs no login, is on topic and in English stays for 60 days; 🆕 marks what you haven't seen, and a new notification kind (🗂 New data on your topics) can tell you. Only the search words leave your device.
- The macOS check no longer counts hidden widgets when it measures the panel's width.

## 0.29.0 (2026-10-20): where your field is heading, and data to practise on

- **🗂️ Data** (Grow → Data), on the computer and the phone: public datasets to practise and train on, across the sciences. Every one passes the same ten rules (open licence, no login, laptop-sized, common formats, documented, stable, validated or used, no personal data, says what to practise, one field), written down as a project skill and enforced in code. A hand-checked core plus the Galaxy Training Network's tutorial data and well-used datasets on Zenodo, NCBI's curated GEO DataSets and OpenML's vetted CC18 suite, re-harvested every week by a GitHub Action. ✨ For you first: your field and the skills rising for you.
- **Rising skills tell the field from your own reading**, on the computer and the phone. What myGeeKy reads for you is picked by your interests, so a topic you just started following used to look like it was rising. Growth is now measured where no one picked for you (the explore share of your feeds, and a new shared file counting skills in new bioRxiv, medRxiv and arXiv preprints, rebuilt daily by a GitHub Action), and a skill is called rising only when the growth is clear for how few mentions it has. New tags: 🌍 rising beyond your usual, 🪞 busy in your feed only. **🚀 Directions** come first: where your field is heading even if your feed never mentioned it (rising for sure across the new preprints, lately or since a year ago, and tied to a skill you have by preprints mentioning both), with 24 new direction-sized entries in the dictionary (genomic language models, AI scientists, virtual cell, AI protein design, self-driving labs, medical AI...), drawn as a launch pad, bridges and a horizon. After all the plots, 🧭 Start a protocol turns any direction or next step into stages. Then four views: 🧭 next steps, 🌉 bridges from what you know, 🪜 rising with you, 🔍 your lens. In a simulation with a known truth, self-made "rises" dropped from 92% to 4% and finding real ones doubled (F1 0.31 → 0.66).
- **Scrolling no longer opens the orbit** on the phone: reading folds it, and only **Orbit** brings it back. Scrolling to the top used to unfold it, which surprised people (and on a short page could happen while scrolling down).
- **📑 Who cited you** (You → Cited by), on the computer and the phone: for anyone with papers, even with no profile
  tracking their citations. Your citations and h-index, the new papers citing you (authors, institution, country,
  and which of your papers), the people who cite you most, and where you're read. Once a day from OpenAlex, asking
  only about papers whose count went up (one request covers 50); the first read sets the starting point. An
  optional "Someone cited your work" notification. `citedby.py` and `lib/cited-by.ts` agree (`tests/test_citedby.py`).
- **A new way to move around**, on the computer and the phone: the twelve planets are gathered into six groups
  (You, Grow, World, Circle, Repos, Chances). Tap one and its pages take its place, with a back planet first named
  after where it goes ("‹ All", "‹ World"); a page with parts (News, Repos, You, Grow, Chances) opens the same way,
  so the tabs inside pages are gone. On the phone the orbit zooms: the group flies to the centre with its pages
  around it, with a clear "‹ Back to …", the trail, and an ↑ on the centre planet; the folded dock moves the same
  way. On the computer, the planet row does, with "‹ Back to …" and where you are above it. `navtree.py` and
  `lib/nav-tree.ts` share the groups and the rules (`tests/test_navtree.py`).
- **🏁 AI race, the first part of News**, on the computer and the phone: who leads and how far open models trail
  (in points and in months), the newest releases and where each lands (NEW for the last two weeks), the race replayed
  month by month, what each recent model is best at (a dot per model under reasoning, coding, math, science, agents,
  knowledge, writing, vision or security; tap for the top five), a colourful "fingerprint" of the top models, and a
  picker that ranks models for the skills your work needs. Built for the panel's and the phone's narrow width.
  From Epoch AI's open benchmark data (CC BY 4.0), rebuilt daily by a GitHub Action (`.github/workflows/ai-race.yml`)
  into one file both apps read; `airace.py` and `lib/ai-race.ts` give the same numbers (`tests/test_airace.py`).
- **📝 Drop a CV, thesis or abstract**, on the computer and the phone: a new way to start in setup, and in ⚙ /
  You → Settings any time later. Drop or pick a PDF, Word (.docx) or text file, or paste the text; myGeeKy picks
  out your field's keywords (from the 1,200-word dictionary), your methods and tools (RNA-seq to thematic analysis,
  R to NVivo) and the people you've written with, and you untick what isn't you. A first-year student with only a
  thesis proposal gets a full profile. Read on the device and not kept: only the words you keep are saved.
  `docread.py` and `lib/doc-read.ts` find the same things in the same text (`tests/test_docread.py`); the phone
  reads PDFs and Word files itself (`lib/doc-text.ts`, new add-ons, so a new APK).
- **📄 "Is this you?" from OpenAlex**, on the computer and the phone: no ORCID? Type your name and institution in
  setup (**Find my papers**) or in ⚙ / You → Settings, and pick yourself among the researchers OpenAlex knows (their
  institution, topics and recent titles shown). Your papers then shape your profile as an ORCID would. If OpenAlex
  is busy, setup carries on with keywords and the search is tried again later by itself, asking "Is this you?"
  when it works. `whois.py` and `lib/whois.ts` rank alike (`tests/test_whois.py`).
- **A GitHub cache that never rewrites itself** (computer): what GitHub told myGeeKy now lives in a small SQLite
  database (`github_cache.sqlite`), one row per answer, instead of one JSON file rewritten whole while a refresh
  runs (it had reached ~400 MB). The old file moves in once (or, if huge, is simply dropped: it's all asked again);
  the panel and a scheduled refresh can share it; a damaged file is set aside, a busy one waited for.
- **Slow numbers wait a day**, on the computer and the phone: a repo's stars, forks and commit activity, its
  contributors, and a person's profile, known from less than a day ago, are read from the device without asking,
  so switching tabs shows them at once. Both apps use the same list (`ghcache.py`, `lib/github.ts`).
- **Suggestions without near-copies**: typing "pyth" no longer offers python2, python3, python 2 and python27 one
  after another (the most readable one stays), on both apps.

## 0.28.0 (2026-10-19): careful notifications, and words for every field

- **A dictionary for every field**: myGeeKy's keyword dictionary grew from 300 words to 1,200, built from 197
  starting topics across physics, chemistry, materials, mathematics, earth and ocean science, energy, medicine,
  imaging, engineering, economics, social science, psychology, language, the humanities, history and archaeology,
  education, agriculture, ecology, biology and AI. Typing a few letters of your field now suggests it, with its
  neighbours, on the computer and the phone. The build saves its progress as it goes, so a crash resumes it.
- **A much lighter GitHub cache on the computer**: it had grown to ~400 MB (a search answer weighs ~0.7 MB and the
  cap counted entries, not size) and was rewritten every few seconds while a refresh ran, keeping slow disks busy.
  It now stays under 25 MB, and half-written copies left by a crash are cleaned up.
- **The phone shows only English listings, like the computer**: a job written only in French was kept on the
  phone (`lib/curated.ts` now has `englishEnough`, the desktop's `english_enough`). Found by the new check below.
- **Keeping the two apps in step** (for development): `tests/phone.py` runs any phone file in Node next to the
  desktop's code; `tests/test_phone_rules_match_desktop.py` checks curated lists and deadlines, 👍/👎 taste, quiz
  banks, protocol shapes and token expiry on both; `tools/parity.py` reads the desktop↔phone map, lists shared files
  changed on one side only (also on every pull request, `.github/workflows/parity.yml`) and which pairs have a test.

- **🔔 Careful notifications, off unless you switch them on**, on the computer and the phone. Choose kinds in
  setup or Settings (a Season opening; a job, funding or conference that fits you very well; an important new
  paper in your field; a new Highlight), daily or weekly, and quiet hours. Only what's really worth it, each
  thing once, all in one line, and tapping it opens the right place. Settings shows exactly what's on and has
  "Turn all off". `notify.py` and `lib/notify.ts` decide the same (`tests/test_notify.py`); the computer shows a
  system notification and a dot on the tab (`gui/notify_ui.py`), the phone a notification from a background
  check (`lib/notify-store.ts`, `components/notify-settings.tsx`; new add-ons, so a new APK).

## 0.27.0 (2026-10-19): your month, your rank, and research told as stories

- **Continue as a guest**, on the computer and the phone: setup offers GitHub, ORCID or a guest start with your
  keywords (word suggestions while you type, from myGeeKy's dictionary). After a GitHub sign-in the phone walks
  you through your data repo and Signals, both optional. Tabs put You first, and without GitHub the ones that
  would only say "add GitHub" go last.
- **Learning before an account**: what you open is learned on the device even with no data repo, and nothing is
  lost when you connect one later (it's sent then).
- **Token guides in pictures**: what to click on GitHub to make each token, drawn step by step, on both apps.
- **Ideas by email** for people without GitHub ("✉ Send by email").
- **"Your protocol is built"** floats up after building one, wherever you've scrolled; reviewed protocols show
  the 3 that fit your field best, then "See all".
- **Seasons**: 74 more scholarships and calls from around the world (and CIHEAM Chania's MSc in Greece), each
  checked on its own site; a season's period no longer chains into a whole year.
- **Security**: text from the internet is never shown as HTML in the panel, and quiz code written by AI never
  runs. Phone pairing accepts long and dotted GitHub tokens.
- **Saving the same file from two threads at once** no longer fails (`files.write_text_atomic`).

- **✨ Highlights in Grow** (first, on the computer and the phone): research articles picked by the maker,
  each retold as a short science news article -- a headline, a standfirst and 4 to 7 whole paragraphs, one
  idea each (a line or two on its own is joined into a paragraph): what they found, who did it and where (and the collaboration), the problem and what came before,
  what they did and with which tools, the findings, the limits -- readable in Arabic, French, German,
  Spanish and Chinese, with "learn these tools" turning a skill into a protocol. Opening one counts as a
  paper read. (`highlight_shape.py`, `lib/highlight-shape.ts`, `gui/highlights_ui.py`,
  `components/highlights-view.tsx`; `tests/test_highlights.py`.)
- **Writing Highlights, in the admin tab** (`highlights.py`, skill `mygeeky-article`): paste DOIs or links,
  open the articles, paste their text (all in one box, split at each title) or drop PDFs, or write from the
  abstracts; DeepSeek writes each with the article skill (`data/article_skill.md`) and translates it. Facts
  (team leader, institutions, countries, journal, date, open access) come from OpenAlex, not from the model;
  every number and tool in the article is checked against the text. Accepted ones go out with Publish.
- **GeekOc swims while things load**, on the computer (`gui/geek_loader.py`) and the phone
  (`components/geek-loader.tsx`), instead of a spinner or a plain "Loading…". Once he appears he stays at least 0.8 s, so
  he's seen rather than flashed; the phone's pull-down circle now shows only for a pull you made.
- **The opening animation has no disc behind the logo** (`gui/splash.py`, `components/loading-intro.tsx`):
  the ring and letters stand on their own.
- **🎖 My month and your rank**, the first part of **You** on the computer (`gui/month_ui.py`; the Model tab now
  has two parts, My month and Model) and the phone (`components/month-view.tsx`). What you did this month as a calendar card with GeekOc, your three highlights
  (firsts get a ribbon) and every count; and a rank from Soldier to General, from points for what you do yourself
  (reading, learning, building, sharing ideas, meeting people), counted over all your time so it never goes down.
  Save or copy the card on the computer; share it from the phone's share sheet. `month.py` and `lib/month.ts`
  count and draw the same (`tests/test_phone_month_match_desktop.py`); the rules are in `data/ranks.json`.
- **Your month in pictures** (`monthviz.py`, `lib/month-viz.ts`): eight drawings with GeekOc -- your GitHub
  contributions as a glowing calendar, your languages as his arms, your wins on a ribbon, your protocols as
  constellations, a compass of the topics you explored, a sky clock of your hours with your badges as medals,
  what you gave and got, and how your interests moved. Your own GitHub events are read at most once an hour and
  kept for 400 days (`refresh_my_github`, `lib/my-github.ts`); the same parity test compares every drawing.
- **The usage log notes more kinds of things you do** (by kind only, never what): a protocol step done, a
  protocol built or published, a quiz, a skill, a chance you 👍. The phone now counts ideas you send too, and
  keeps up to 5000 lines while no data repo is connected.
- **GeekOc in the apps**: `tools/geekoc_poses.py` draws him in a few poses from the website's rig into
  `data/geekoc.json` (identical on the phone).
- **400 warnings gone**: a language button's stylesheet ended in a stray `}}` (`gui/growth_ui.py`), so Qt
  reported it each time the button was drawn.
- The phone gains `react-native-view-shot` and `expo-sharing` (a new APK is needed).

## 0.26.2 (2026-10-17): your geeky friend who helps you grow, quietly

- **A new README** (`README.md`, which is also this PyPI page), built around what myGeeKy does for you: helps you
  **see** what is moving in your field, **learn** what comes next, **meet** the people working on the same
  problems and **catch** opportunities while they are still open. One tagline, three buttons (Windows, pip, the
  video), install moved up, each section's detail folded away, and the five promises as a table.
- **A new website** (`website/index.html`) saying the same: GeekOc alive in the hero (the website's own rig, his
  arms reaching for your pointer), the four promises as cards, and the sixteen tiles and nine feature sections
  merged into See, Learn, Meet and Catch. Install now matches the README (`mygeeky setup`), and the code signing
  policy is unchanged.
- **A new video**, [youtu.be/u1qmX5PtMdE](https://youtu.be/u1qmX5PtMdE), made in the repo
  (`launch/video/make_falling.py`, `make_soundtrack.py`, `make_thumbnail.py`): the kid, GeekOc, the brick
  mountain, every screen, install, the promises, and an original soundtrack synthesised from scratch.

## 0.26.1 (2026-10-16): output going nowhere is not a crash

- **`mygeeky ... | head` no longer reports a crash** (`src/mygeeky/cli.py`). Closing the pipe is what
  `head` does once it has its lines, and the panel stops reading when the view that asked for a command
  is closed. Windows calls that write "Invalid argument" (errno 22) rather than a broken pipe, so it was
  caught as an unexpected failure, saved as a crash report and shown as "myGeeKy hit a problem" --
  [issue #6](https://github.com/mygeeky/myGeeKy/issues/6). A command whose reader has gone now ends
  quietly. A real errno 22 from anywhere else is still reported, and saying what went wrong no longer
  depends on output still working.
- **A crash report keeps each header with its own traceback** (`src/mygeeky/crashreport.py`). A burst of
  errors was shortened by keeping the first lines of the whole bundle and the last, which put the newest
  report's header above an older report's traceback: #6 named `profile show` while the traceback was in
  `interests_cmd`, and the version it named was not the version that crashed. Reports are now trimmed
  one at a time, and a whole older report is dropped -- and said to be dropped -- rather than half of one.

## 0.26.0 (2026-10-16): the phone, one more computer in sync (phone app 1.9.0)

- **The phone reads and writes your private data repo**, like one more computer in sync. Give it its own
  fine-grained token (that repo only, Contents: Read and write) and it shows your real model -- the interest map,
  what teaches it, room to explore, who follows you back, the weights and the AUC trend, all computed exactly as
  the desktop does -- your badges, and your profile, so every list on the phone is ranked by you. What you open
  on the phone goes back as interest events and usage lines, which your computers learn from.
- **The maker's admin on the phone**, behind GitHub's word on who you are and the phone's own fingerprint or
  PIN: adoption, listings to review (accept, edit, reject), quizzes, the ideas inbox and people to invite. The
  phone never edits the shared files: it appends to `admin_actions.jsonl`, which your computers apply at sync
  (`src/mygeeky/adminlog.py`) -- once, in order, never over a later undo. `scout.json` and `quizwriter.json` now
  sync so the phone can show them; keys never leave the computer.
- **"Not taking signals right now" works from the phone too.** It is written to your beacon with when it changed,
  and a computer takes up a later change instead of publishing over it (`beacon.adopt_quiet`).
- **On the phone**, brought level with the desktop: 🛠 Repos to help out and 📈 Rising (the market board) in
  Repos; 💬 Papers & discussions (arXiv, bioRxiv, Hacker News) in News; headings, abstracts, summaries, authors
  and code links on Papers, News and AI models; Seasons as the desktop shows them; ⚙ Settings with the three
  themes; 💡 Ideas; new things marked with a dot and counted on the planets; warnings before a token expires.

## 0.25.0 (2026-10-15): start with nothing but your own words

- **You can use myGeeKy without a GitHub account, an ORCID, or an account anywhere** (`src/mygeeky/fieldstart.py`).
  Pick keywords from the dictionary and 🛒 Market, 🛠️ Repos to improve and the field half of 👥 People work at
  once — they search public repositories against your interests and never read an account of yours. Only
  follow-back scoring, 📣 Activity, 📊 Signals, 🤝 Collab and phone sync need one, and the program says so where
  it needs it rather than at the door.
  - **A decision tree, not a blank box**: five suggestions a round — three near what you have picked, two from
    further off, so a wrong first guess does not wall you in. Dismissing one rules out its neighbourhood.
    Ready at six picks across three areas, not a flat count of ten.
  - **When a keyword is not in the dictionary** it offers the nearest ones that are, and asks OpenAlex for real
    topics if none fit, rather than silently dropping what you typed.
  - **It asks about an account on days 7, 21, 45 and 90, and then never again.** Nothing is ever withdrawn for
    saying no.
- **🗓️ Seasons: the scholarships that come back every year** (`src/mygeeky/seasons.py`). The periods are a drop
  box that opens on the one you are in, so what is open now is what you see first.
- **A listing in another language is translated, not dropped.** Arabic, French, German, Spanish and Chinese
  listings are read, translated and still checked against their own page — and jobs, funding and conferences are
  shown in English whatever language the board was in.
- **📬 Read the job alerts in your mailbox**, beside the sites it already watches and pages you paste
  (`src/mygeeky/mailbox.py`). The password lives in your system keyring, never in a file.
- **Paste a page the robot cannot read**, and **filter listings by country** — the location filter sits above the
  four kinds, because it applies to all of them.
- **Ten bugs fixed** by auditing and by actually using the program, including `mygeeky --help` crashing on a
  Windows console since 0.8.0 (cp1252 could not print the output's arrows), and wrapping labels that drew nothing
  at all in the flow layout.
- **🏆 Quiz admin folds away the quizzes that need nothing**, instead of one "add more questions" button per quiz
  down the page.
- **Sections are icons in one row**, and the open one says its name. The drop boxes follow the theme instead of
  Qt's black default.
- **Curated lists**: 23 jobs, 6 funding calls and 11 conferences added, everything past its deadline removed, and
  the French bioinformatics society's board added as a source.
- **📱 Phone app 1.8.0**: Seasons and the country filter, ported from the desktop and checked against it — the
  phone's own TypeScript is run in Node against the Python on a fixed date, so the two cannot drift apart quietly.
- **🐙 GeekOc**, the myGeeKy octopus, joins the website (`website/geekoc/`): a parametric rig with nine poses, ten
  faces and five ways of swimming, his arms simulated rather than drawn. Not part of the pip package.

## 0.24.0 (2026-10-14): for computer science and for data analysis, and quizzes

- **myGeeKy now covers three kinds of work at a computer**, not only bioinformatics: 💻 computer scientists and
  developers, 🧬 bioinformaticians and data scientists, and 📊 experimental researchers analysing their own data.
  Setup asks which fits you best (`work_style`), which only tilts the starting balance of what's suggested.
  - **22 new skills in the dictionary**: 15 computer-science ones (algorithms, system design, databases, frontend,
    backend, DevOps, security, HCI, compilers, graphics, embedded…), and 7 for people starting to analyse their own
    data (statistics basics, scientific plotting, spreadsheets, GraphPad, power analysis, image quantification,
    experimental design).
  - **9 new reviewed protocols** (14 in all), every link checked by hand: Git and GitHub teamwork, algorithms for
    interviews, a first web app, machine learning outside a notebook, a first pull request · from Excel to R,
    statistics for experiments, figures for papers, images into numbers with Fiji.
  - **📘 Guides** join repos, papers, books, courses, tutorials and videos as a kind of link: a project's or tool's
    own documentation.
- **myGeeKy does not teach laboratory work, and now refuses to** (`src/mygeeky/safety.py`). It covers code, data,
  statistics, figures and pipelines. A protocol whose skill, goal or title names a bench technique is refused with
  a plain reason, and protocol repositories, protocol journals and suppliers' method libraries are refused as
  sources — in a protocol built on a device, in the curated file, in one another user published, and as a quiz
  question's source. Analysing the data an experiment produced is welcome, and is what the gentlest protocols are
  for. (An earlier version of this release had bench protocols; they were removed before it went out.)
- **258 questions, written by hand**, covering all 14 reviewed protocols (14 to 20 each): every one quotes a
  sentence that is really on one of that protocol's own sources, and `tools/quiz/verify.py` checks all 258
  against the live pages. `tools/quiz/sources.py` and `tools/quiz/add.py` are the maker-side tools for
  writing more.
- **🏆 Quiz, a new tab in 🌱 Grow** (and on the phone), next to Protocols: every quiz in one place, with your
  best score on each, what you can still try today, and the reviewed protocols you could start. **Taking one
  happens inside that tab** — pressing 🏁 on a protocol, or 🎓 on a step, moves you there and draws the attempt
  in the tab, with a dot per question (`QuizRunView`, `QuestionDots`, `AnswerRow`). No pop-up windows. Every reviewed
  protocol can have a question bank; an attempt is ten questions drawn at random: 50% easy, 35% applied,
  15% real pitfalls.
  - Each question **comes from one of that protocol's own sources** and quotes the sentence that proves the answer,
    and the card shows that source once you answer, with why.
  - Only your best score counts, one attempt a day, and 🚩 drops a question you think is wrong (and can tell the maker).
  - The shipped bank stores each answer as a **hash** rather than its position, so the file doesn't show which
    option is right. That is obfuscation, not security — four options can be hashed and compared — and the
    board stays, honestly, for fun ([docs/QUIZZES.md](docs/QUIZZES.md)).
  - A step's level check now uses that step's questions when there are any.
  - **The maker's side** (`quizwriter.py`, admin tab → 📝 Quizzes): DeepSeek writes them from the real page; myGeeKy
    checks the quote is on it, runs the code, and a blind second read must pick the same answer twice. The maker
    reads five ([docs/QUIZZES.md](docs/QUIZZES.md)).
- **🌍 Scores on mygeeky.org, only if you ask.** Your name and your scores are two separate choices; you see exactly
  what would appear; and you agree by writing `accept` on a public GitHub issue **from your own account** — the proof
  — with `withdraw` to undo it. A score below 80% is never shown, the maker is excluded, and the board keeps the
  month's top three plus the first five to finish each protocol (🏴 Pathfinder for the first).
  A daily workflow collects consents and opens a pull request the maker approves ([docs/LEADERBOARD.md](docs/LEADERBOARD.md)).
- **Phone app:** the same quizzes, one question per page, with the source and the score breakdown.
- **Far fewer GitHub calls, with nothing going stale** (`src/mygeeky/ghcache.py`). Every answer is kept with
  its ETag and every request carries it, so GitHub can reply 304 Not Modified — which costs nothing against
  your limit. Measured: re-reading three profiles cost 3 requests, then 0. Also: the same question asked
  twice in one refresh goes out once; a deleted account isn't re-asked for hours; and **when GitHub or the
  network is away the app keeps working** on what it kept. The Admin tab shows what was asked and what was
  free today, with a Forget button.

## 0.23.0 (2026-10-13): 🌱 Grow, 🎯 Chances and protocols (phone app 1.7.0)

- **🌱 Grow, a new planet.**
  - **📈 Rising Skills:** what's growing in your field and missing from your profile, CV, papers and repos, each with
    why. It comes from the rising papers, trending repos and models, and people myGeeKy already reads for you.
  - **🧭 Protocols:** a skill as ordered stages, e.g. R basics → statistics with R → R for data analysis → a real
    project → your own work.
    - A level check skips what you know: your repos as evidence, a short quiz, or "I can do these".
    - Five reviewed protocols to start with: R for data analysis, Python for data analysis, GWAS, Nextflow, and
      single-cell RNA-seq.
    - For any other skill myGeeKy builds one from GitHub and papers, with a small protocol model trained for this
      (`tools/protocol_model`: about 400 KB, trained on 7,440 labelled examples across 55 skills; the same numbers on the computer and the phone).
    - Edit it (reorder, rename, add, remove), then 📤 publish it to the maker as a public issue. Published protocols
      become reviewed ones and training data for the next model.
    - Shown as a road map: numbered circles that make room for the step you're on, one step at a time, and a card
      per link (a repo with its stars and language, a paper with its year and citations, a book or course with its
      site), each with one clear button.
  - **📚 Learn:** hand-picked learning resources, matched to you and your rising skills.
  - **🎉 Wins:** new stars, forks and citations, with the newest paper citing you.
  - **🤝 Collaborators:** fellow users whose skills complement yours, asked with the sealed, mutual-only 🤝.
- **🎯 Chances, a new planet:** verified jobs, funding and conferences, each checked by hand. They disappear after
  their deadline, and a 🚩 reports one that looks fake. They're curated in one file
  ([docs/CURATED.md](docs/CURATED.md)), and a daily workflow removes what's past its deadline.
- **👍 / 👎 everywhere in them.** They teach your model; the same thumb again takes a vote back. Votes stay on your
  devices (and your private sync repository).
- **Phone app:** the same two planets on the rings: 🌱 Grow on your circle, 🎯 Chances on the world. Sign in with
  ORCID now finishes on Android too (1.6.1).
- **Fixes in the panel:** rows of buttons wrap instead of making the panel wider; Grow fits from the start (no click
  needed); old buttons no longer pile up behind redrawn ones; dialogs are readable in every theme; Collaborators
  opens at once.
- **For the maker:** a listing scout in the admin tab finds jobs, funding and conferences on chosen sites with
  DeepSeek, checks every answer against its page, and publishes only what the maker accepts.

## 0.22.0 (2026-10-12): Sign in with ORCID, no GitHub needed, and where the panel lives (phone app 1.6.0)

- **Sign in with ORCID.** In setup (on the computer, in `mygeeky init`, and on the phone), a green **Sign in with ORCID** button opens orcid.org; you sign in there, and myGeeKy gets your confirmed ORCID iD and the name on your record.
  - **No server, no secret.** ORCID returns to [mygeeky.org/orcid/](https://mygeeky.org/orcid/), a static page that hands the answer straight to the app (on a computer, to myGeeKy on that same computer) and stores nothing.
  - **Only who you are.** It asks for the `openid` permission alone. ORCID's token lasts 10 minutes; myGeeKy uses it once to ask whose it is, then forgets it. It never sees your ORCID password and can't read or change your record.
  - **A typed iD is checked.** ORCID iDs end in a check digit, so a mistyped one (`…-0098` for `…-0097`) is caught on both the computer and the phone.
- **myGeeKy without a GitHub account.** The GitHub username is now optional: your ORCID, a few topics or keywords are each enough to start.
  - **Works straight away:** News, Research, AI models and Launches, for your field.
  - **Needs GitHub:** People, Repos, Activity and Signals each show what adding GitHub would unlock, with an **Add GitHub** button (and a link to create a free account). Add it any time; everything fills in.
  - **Setup** skips the token, sync and Signals pages when there's no GitHub username, and Research now refreshes on its own without one.
- **Where the panel lives (⚙ Settings → Window).**
  - **Stay:** *In front* (as before), *Normal* (other windows can cover it), or *Behind* (folded, it waits under your windows, on the desktop).
  - **Place on screen:** click a spot on a small drawing of your screen: the right or left edge, or the bottom-right or bottom-left corner. In a corner the folded icon sits low; opening it rises to the middle of the edge, and folding sinks it back.
  - **Off screen:** hides the panel until you open myGeeKy again.
  - **Right-click the folded icon** for the same choices in a menu.
- **Fixed: a crash when a profile closed while it was loading** ([#4](https://github.com/mygeeky/myGeeKy/issues/4)). Closing a person's card before their details arrived made the late answer update a card that no longer existed. Late answers for closed windows are now dropped, everywhere.
- **Fixed: a "crash" when quitting while GitHub was slow** ([#5](https://github.com/mygeeky/myGeeKy/issues/5)).
  - Activity refreshed every minute without waiting for the last refresh, so a slow GitHub piled them up. Now one runs at a time.
  - Quitting with work still running now ends quietly; on Windows it used to record a fatal error that the next start offered as a crash report.
  - A long crash report keeps its first lines (where the cause is) when it's trimmed to fit in a GitHub link.
- **A support address: [support@mygeeky.org](mailto:support@mygeeky.org).** For anyone who'd rather write privately, or has no GitHub account. It's on the website, the privacy page, the README, the guide, the PyPI page, the 💡 window and the phone's settings.
- **Phone app 1.6.0:** Sign in with ORCID and starting without GitHub (it then opens on Papers), the support link, and **block and report**: a flag on every signal, call and person offers *Report to GitHub* or *Block*. Blocked people's signals and calls disappear, and a Blocked list lets you undo it.

## 0.21.4 (2026-10-12): calls for contributors, a new Signals planet, and a Linux crash fixed (phone app 1.5.0)

- **Fixed a crash on Linux.** After running for hours, the panel could close by itself ("free(): invalid pointer" while a tab refreshed). The small "new" dot on new cards was a Python-made Qt object hooked onto its card; when Qt deleted a refreshed card, freeing that dot could corrupt memory. Linux's allocator caught it and stopped the program; Windows and macOS never noticed. The dot is now a plain label owned by the card, and a test keeps it that way.
- **Crash reports say why.** Started from a menu or at sign-in there's no terminal, so the last line Qt or the system printed before a hard crash was lost. It now goes into the crash log, and a hard-crash report also includes Qt's last critical messages.

- **Calls for contributors.** Invite people whose skills fit to help with one of your repos, on the computer or the phone.
  - **Posting a call:** pick one of your own public repos, the skills you need (up to 6, filled in from its topics), one or two sentences (no links), a level, the time it takes, and how long it stays open (30, 60 or 90 days). At most 3 open calls, one per repo.
  - **Where it lives:** in the beacon you already have, so there's no new repo or token. Mark a call filled or close it; it also ends on its own.
  - **Who sees it:** nobody is targeted. Each reader's own myGeeKy scores every call against their work, on their own computer or phone. Calls that fit show under "Projects calling for you", and the usual 20% go to 🔭 new territory outside their work.
  - **"I'm in":** a sealed signal only you can read, with their name and the skills of theirs that matched. It counts like a fork in their interest model, so their suggestions lean toward that area. "Changed my mind" takes it back, and "Not for me" hides a call.
  - **Your calls:** each one lists who said they're in, with their matching skills.
- **A new Signals planet.**
  - **"Your field":** a thin ruler at the top with everyone on Signals and every call that fits you. Further right is closer to your work; calls sit above the line and people below. Unfold it into a radar with you in the middle, and tap a dot to open its card.
  - **Two buttons under it:** "Invite to a project" and "Send a signal". The signal window lets you pick a person (best fit first, or search by name or topic), a signal, and for ⭐ which of their repos, and shows exactly what they'll see before you send.
  - **Below it:** For you, Projects calling for you, Your calls, and People on Signals. The long explanation is now one line.
- **The phone and the computer agree.** A test runs the phone's real code against the desktop's: which calls count, a call made on the phone, and "I'm in" in both directions.

- **An opening animation.** The badge's arms spin in out of nothing, then G, ee and K pop in, and m and y land last with a flash.
  - **On the computer:** it plays in the middle of the screen the first time myGeeKy starts, while the panel is being built.
  - **On the phone:** it plays each time the app opens (tap to skip). The phone used to open on a plain white screen, because its start-up screen was never set; it's now the app's own dark background, which hands straight over to the animation.
  - **For the web:** an animated SVG of the same thing (`docs/loader.svg`).
  - All three use the same pictures and the same timeline.

## 0.21.3 (2026-10-11): a panel that never fades away, and a smooth Transparency slider

- **The panel never fades away.** The Transparency slider still goes from 0% to 100%, but 100% now means 40% see-through instead of invisible. A panel set more see-through than that comes back to 40% on its own.
- **The Transparency slider no longer makes the panel lag.** Dragging it sent a change for nearly every pixel the mouse moved, and each one made the system redraw the whole see-through window (about 600 redraws in a few seconds). It now redraws at most about 30 times a second (about 11 times fewer), while the % number still follows your mouse.
- **Transparency set with the keyboard or mouse wheel is kept.** Only letting go of a drag used to save it, so a change made with the arrow keys or the wheel was lost on restart.
- **Posts you've seen are easier to read.** In Activity (and the few seen cards kept at the end of other tabs) they now show at 80% instead of 55%: still quieter than new ones, but no longer faint.

## 0.21.2 (2026-10-11): a new look, and Signals on the phone (app 1.4.0)

- **A new look: find friends · collaborate · away from noise.**
  - **A new icon:** a round badge: the name inside a glowing ring of two arms hugging. It's used in the panel, the Windows installer, the Linux menu, the website, the README and the phone app (including Android's adaptive and themed icons).
  - **A character:** the geek in a hoodie, working quietly against a brick wall. It introduces the README's "Why this exists", a new Why section on the website, and the poster.
  - **The phrase** "find friends, collaborate, away from noise" now leads the README, the website (title, headline, link previews), the poster, the setup window's welcome, the phone's first screen, the command-line help, the Linux menu entry and the PyPI description.
  - The screenshots were retaken with the new icon.
- **Signals on the phone (app 1.4.0).** Read the signals people send you and send your own (🙏 📚 ⭐ 👀 🤝) from the 📡 Signals planet.
  - **Its own key:** the phone creates a key that never leaves it, kept in the phone's secure store, and adds its public half to your beacon next to your computers' keys. Signals sent to you from then on open on the phone too.
  - **Its own token:** it writes with its own Signals token (one per device), and keeps everything your computers put in the beacon (their keys, your status, your interests, the signals they sent). It refuses rather than push a computer's key out when the beacon already holds 4 devices.
  - **The same encryption and rules as the desktop.** A test runs the phone's real code against the desktop's Python, both ways: phone to computer, computer to phone, and both keeping each other's keys and signals.
  - **On the desktop for now:** mute, block, taking a signal back, and changing your status. Signals sent before the phone joined open only on your computers.

- **The token warning goes away by itself.** After you sign in again (or paste a new token) in the setup window or a terminal, an open panel kept showing "Token 1 expires…" until it was restarted. Now, while that warning shows, the panel checks again whenever you open it (at most once a minute).

## 0.21.1 (2026-10-11): myGeeKy's housekeeping no longer counts as your activity

- **No more green squares from myGeeKy.** Sync and Signals commits used to carry your own git email, so GitHub counted myGeeKy's housekeeping as your activity: green squares and "contributions", even on days you didn't work.
  - myGeeKy's commits are now signed **myGeeKy <housekeeping@mygeeky.invalid>**.
  - GitHub counts a commit only when its email is linked to your account, and a `.invalid` address never can be.
  - Your own work counts exactly as before.
- Squares already recorded stay; see the release notes for how to remove them if you want.

## 0.21.0 (2026-10-11): always something new, and sign-ins that keep working

- **myGeeKy remembers what you've seen.** A card counts as seen when it was mostly on screen for about a second and a half (or you clicked it).
  - What you've seen makes room for what you haven't, when you next open the panel or switch tabs. Never while you're reading.
- **Each tab has its own rule:**
  - **People and repos** rest for 7 days, then may come back. Clicked people never come back.
  - **Market rows** move down for 3 days.
  - **News, headlines, papers and models** are read once. A few stay at the end, dimmed.
  - **Activity** keeps its order and dims what you've seen.
  - Anything seen 3 times and never clicked rests for 30 days.
- **People and Repos rotate through everything suggested lately** (the last 90 days), not just the last search.
- **New things keep coming:** when a tab runs low on unseen items, myGeeKy searches GitHub again in the background (people at most every 6 hours, repos every 12). Results wait for your next visit to that tab.
- **You can see what's new:** a dot on new cards, a count on each tab's planet ("People: 4 new"), and an "all caught up" note when you've seen everything.
- **Settings:** `fresh_people_days`, `fresh_repos_days`, `fresh_market_days`, `fresh_ignored_after`, `fresh_ignored_days`, `fresh_people_topup_hours`, `fresh_repos_topup_hours`.
- **Tests:** the test run no longer aborts at exit when a test's panel still has a download running.

### Sign in with GitHub keeps working
- **GitHub now gives myGeeKy's sign-in tokens an 8-hour life.** It became the default for new OAuth apps on 14 August 2026. Before this release, a sign-in quietly stopped working after 8 hours, on the desktop and on the phone.
- **myGeeKy now renews the token by itself:**
  - It keeps GitHub's refresh token in the system's secure store (keyring / phone secure store) and renews shortly before the 8 hours are up.
  - No app secret is needed for a device-flow sign-in; this was checked against GitHub.
  - On the desktop, the panel and the weekly run can't renew at the same moment. Each renewal replaces the refresh token, so two at once would sign you out.
- **`mygeeky auth status`** says "renews itself automatically" for such tokens. It warns only if you haven't used myGeeKy for nearly 6 months.
- **An 8-hour token from an older version** now says "sign in again" instead of "renew it on GitHub's token page". The panel's banner offers **Sign in again**, which opens the setup window.
- **Connect your phone** no longer passes along a sign-in token that renews itself (it would stop working on one of the two); the phone signs in by itself.
- **Logout and uninstall** remove the refresh token too.

## 0.20.0 (2026-10-10): first-class on macOS, and uv support

### uv
- **Qt installs in uv environments.** Environments made by `uv tool install` or `uv venv` have no pip, so `mygeeky gui` used to fail at the Qt step. It now installs Qt with this Python's pip if it has one, then with `uv pip install --python …` when uv is available, then after setting up pip with `ensurepip`. uv is also found outside PATH (in `~/.local/bin`, `~/.cargo/bin` and Homebrew), because an app started from the Dock gets a bare PATH. If nothing works, the message suggests `uv tool install mygeeky --with PySide6-Essentials`.
- **Update and uninstall work for uv installs.** The panel's **Update** runs `uv tool upgrade mygeeky` for a uv tool install, which keeps the Qt it was installed `--with`. A `uv venv` without pip updates with `uv pip`. Uninstalling uses `uv tool uninstall`.

### macOS
- **A real app.** `~/Applications/myGeeKy.app`, with its name and icon in Launchpad, Spotlight and the Dock.
  - It contains an `Info.plist`, a launcher that runs myGeeKy's own Python, and an `.icns` icon built from the PNG icons (no Xcode tools needed).
  - It's created by `mygeeky desktop install`, `mygeeky gui`, the setup window's Finish, and the one-line installer, and removed by uninstall.
  - `mygeeky gui` and the setup window start the panel through the app, so macOS treats it as myGeeKy.
- **Open at login** with a LaunchAgent (`org.mygeeky.panel.login`) that opens the app, instead of the Linux autostart file. `mygeeky desktop install --autostart` turns it on and `--no-autostart` turns it off.
- **The weekly run uses launchd** (`org.mygeeky.weekly`, Monday 09:00) instead of cron, which is deprecated on macOS and may need Full Disk Access. launchd also runs a missed Monday when the Mac wakes. A cron line left by an older myGeeKy is removed.
- **Polish.**
  - The menu bar says **myGeeKy**, not Python.
  - The panel stays visible when another app is active: macOS hides Qt "tool" windows otherwise.
  - The panel follows you to every Space and sits beside full-screen apps.
  - Token paste hints say **⌘V**.
- **install.sh on Darwin.**
  - It creates the app instead of skipping that step.
  - It works with Homebrew's Python, the python.org one, and macOS's own `/usr/bin/python3`. When Apple's Command Line Tools aren't installed, that last one is a stub that opens an "install developer tools" dialog, so the installer skips it.
  - It says how to put `~/.local/bin` on PATH.

### CI
- **New `macos-install` workflow on `macos-latest`:**
  - **Tests:** the full test suite, including macOS-only checks: Apple's `plutil` and `iconutil` on the app and its icon, the menu-bar name, and a panel-like window following every Space.
  - **One-line installer:** run with `MYGEEKY_NO_LAUNCH=1`, with Homebrew's Python and with `/usr/bin/python3`, followed by the login item, the launchd weekly run, an update and an uninstall.
  - **uv:** `uv tool install mygeeky --with PySide6-Essentials`, and a uv install without Qt that then installs it through uv. In both, `mygeeky --version` must work and PySide6 must import.

### Docs
- A short **On a Mac** section in the README and a **macOS** section in the guide: the one-line installer, uv, Homebrew Python, the Keychain, login and weekly agents, and uninstalling.
