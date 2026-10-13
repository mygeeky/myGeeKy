# Changelog

What changed in each myGeeKy release. Versions before 0.20.0 are described in
[GitHub Releases](https://github.com/mygeeky/myGeeKy/releases).

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
