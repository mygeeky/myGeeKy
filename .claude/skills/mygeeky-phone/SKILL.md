---
name: mygeeky-phone
description: Use when running, testing, screenshotting or debugging the myGeeKy phone app (Expo / React Native in mobile/) on the Android emulator or a phone, including black screens, "isn't responding", the keyboard not typing, Metro, or seeing a phone change before release.
---

# Running the myGeeKy phone app

Read `mobile/AGENTS.md` first: Expo changes between SDKs, so check the versioned docs, use `npx expo install`,
and never hand-edit `mobile/android/` or `mobile/ios/` (they are generated).

## Start it

```bash
# 1. the emulator (use a working AVD; list them with: ~/Android/Sdk/emulator/emulator -list-avds)
~/Android/Sdk/emulator/emulator -avd myGeeKy_Pixel2 -gpu host -netdelay none -netspeed full   # in the background
# 2. Metro, the JS server (NOT with CI=1, which turns off live reload)
cd mobile && EXPO_NO_TELEMETRY=1 npx expo start --port 8081                                    # in the background
# 3. once booted
adb wait-for-device; until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = 1 ]; do sleep 2; done
adb shell svc power stayon true; adb shell input keyevent KEYCODE_WAKEUP; adb shell wm dismiss-keyguard
adb reverse tcp:8081 tcp:8081
adb shell am start -a android.intent.action.VIEW -d "mygeeky://expo-development-client/?url=http%3A%2F%2Flocalhost%3A8081"
```

The installed app is a development build that loads its JavaScript from Metro, so code changes appear live.
Native changes (new native module, `app.json` plugins, version) need a rebuild:
`cd mobile && npx expo run:android --no-bundler` (then `git checkout -- mobile/package.json`).

## Known problems

- **First load takes 30 s–2 min** (Metro bundles ~1700 modules). The screen is dark meanwhile; right after boot
  Android may say "myGeeKy isn't responding": tap **Wait**. It is not a crash.
- **Black screen while Android is awake** (`adb shell dumpsys power | grep mWakefulness` says Awake, but every
  `adb exec-out screencap -p` is black, and the emulator log shows "bad color buffer"): the AVD's graphics are
  broken. Don't keep retrying modes; create a fresh AVD from the same system image.
- **Display asleep:** `adb shell svc power stayon true` and `KEYCODE_WAKEUP`.
- **Keyboard types nothing:** a new AVD from `avdmanager` gets `hw.keyboard=no`. Set `hw.keyboard=yes` in
  `~/.android/avd/<name>.avd/config.ini` and restart the emulator.
- **Seeing first-run setup again** needs the app's data cleared (`adb shell pm clear org.mygeeky.app`), which
  erases that emulator's test data: ask first.
- **Don't type into the emulator while the user is using it**: check the current screen with a screenshot first.

## Seeing a screen without the emulator

The web build renders the same screens: `cd mobile && npx expo start --web --port 8082`, then open
`http://localhost:8082/<route>` (e.g. `/setup`) at phone width (412×915) in headless Chrome. Good for quick
layout checks; native-only parts (secure storage, camera) won't work there.

## Before saying a phone change is done

`cd mobile && npx tsc --noEmit && npx expo lint`, look at it (emulator or web), and run the
`mygeeky-platforms` checklist: does the desktop need the same change?
