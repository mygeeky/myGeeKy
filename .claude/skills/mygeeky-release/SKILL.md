---
name: mygeeky-release
description: Use when releasing myGeeKy (a new version, "push and release", a tag, PyPI, the Windows installer, a phone APK or a Play Store build), or when bumping the version or writing the changelog.
---

# Releasing myGeeKy

**Only when the maintainer says so.** Nothing goes to GitHub (push, tag, release, asset upload), PyPI, Google
Play or the website until the maintainer asks for it in the current conversation. Commit locally meanwhile, and
after each major improvement ask whether to push or publish, listing what would go out. An earlier "yes" doesn't
cover new work.

## Desktop release (PyPI + Windows installer)

1. **Check first:** `git fetch && git status` (main up to date, nothing unexpected), and the full test suite:
   `.venv/bin/python -m pytest -q`. Run the `mygeeky-platforms` checklist: nothing shared may be half done
   (see `PARITY.md` if it exists).
2. **Bump the version in both places:** `pyproject.toml` (`version = "0.X.Y"`) and
   `src/mygeeky/__init__.py` (`__version__`). They must match.
3. **Changelog:** add an entry at the top of `CHANGELOG.md` in the existing style.
4. **Commit:** message `0.X.Y: <short theme>` (e.g. `0.26.2: your geeky friend who helps you grow, quietly`).
5. **Tag and push:** `git tag -a v0.X.Y -m "0.X.Y" && git push origin main --follow-tags`.
   The tag starts `.github/workflows/release.yml`, which builds `MyGeeKySetup-0.X.Y.exe` and attaches it to the
   GitHub release. Watch it with `gh run watch`.
6. **PyPI:** build with `.venv/bin/python -m build`, then (only when the maintainer has said to publish)
   `.venv/bin/python -m twine upload -u __token__ dist/mygeeky-0.X.Y*`. The token lives in the system keyring
   (`keyring set https://upload.pypi.org/legacy/ __token__`, a project-scoped PyPI token), so twine reads it
   itself: never ask for it, never print it, never write it to a file or `~/.pypirc`. Check it is there with
   `.venv/bin/python -m keyring get https://upload.pypi.org/legacy/ __token__ | cut -c1-5` (prints `pypi-`).
7. Pushes touching `website/**` redeploy mygeeky.org (`pages.yml`).

## Phone

- Version: `mobile/app.json` → `expo.version`. Keep the desktop CHANGELOG entry mentioning phone changes.
- **Test APK (for your own phone):** build locally — faster and more reliable than CI:
  ```bash
  cd mobile && export ANDROID_HOME=$HOME/Android/Sdk
  npx expo prebuild -p android --clean --no-install
  cd android && ./gradlew assembleRelease --no-daemon
  ```
  Output: `mobile/android/app/build/outputs/apk/release/app-release.apk` (debug-signed). `expo prebuild` edits
  `mobile/package.json` scripts: restore it with `git checkout -- mobile/package.json`. Copy it to
  `dist/myGeeKy-<version>-test.apk`, attach with `gh release upload v0.X.Y <file> --clobber`, and offer a QR
  code of the download URL. `.github/workflows/phone-test-apk.yml` does the same on GitHub but can hang.
- **Google Play:** needs an `.aab` signed with the upload key, never the test APK:
  `npx eas-cli@latest build --platform android --profile production`, then
  `npx eas-cli@latest submit --platform android --profile production` (EAS keeps the keystore; Expo account
  `alsammans-team`). See `docs/play/ACCOUNT.md` and `docs/play/LISTING.md`.

## After a release

- Confirm the release page has the installer (and APK if any): `gh release view v0.X.Y`.
- YouTube/README/website links and screenshots: update if the release changed what they show.
