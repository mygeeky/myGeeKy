# Changelog

What changed in each myGeeKy release. Versions before 0.20.0 are described in
[GitHub Releases](https://github.com/mygeeky/myGeeKy/releases).

## Unreleased

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
