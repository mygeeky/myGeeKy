# Changelog

What changed in each myGeeKy release. Versions before 0.20.0 are described in
[GitHub Releases](https://github.com/mygeeky/myGeeKy/releases).

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
