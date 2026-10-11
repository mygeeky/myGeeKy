"""Small macOS touches that Qt doesn't do by itself.

The menu bar shows the name of the running program's bundle. myGeeKy runs
inside Python, so without this the menu bar says "Python". Changing the
bundle's name before Qt starts makes it say "myGeeKy". It is done through the
Objective-C runtime with ctypes (standard library only, no PyObjC), and only
when the bundle's info dictionary can be changed: an Objective-C exception
can't be caught from Python and ends the program. For the same reason the
window's Space behaviour is computed so it can never be a combination AppKit
rejects (see all_spaces_behavior).

Everything here does nothing on other systems.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import sys

APP_NAME = "myGeeKy"


def _objc():
    lib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    lib.objc_getClass.restype = ctypes.c_void_p
    lib.objc_getClass.argtypes = [ctypes.c_char_p]
    lib.sel_registerName.restype = ctypes.c_void_p
    lib.sel_registerName.argtypes = [ctypes.c_char_p]
    return lib


def _send(lib, obj, selector: str, *args, argtypes=(), restype=ctypes.c_void_p):
    send = lib.objc_msgSend
    send.restype = restype
    send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
    return send(obj, lib.sel_registerName(selector.encode()), *args)


def _nsstring(lib, text: str):
    return _send(lib, lib.objc_getClass(b"NSString"), "stringWithUTF8String:", text.encode("utf-8"),
                 argtypes=[ctypes.c_char_p])


def bundle_name() -> str | None:
    """CFBundleName as the system sees it now (for tests and the CI check)."""
    if sys.platform != "darwin":
        return None
    try:
        lib = _objc()
        bundle = _send(lib, lib.objc_getClass(b"NSBundle"), "mainBundle")
        info = _send(lib, bundle, "infoDictionary")
        value = _send(lib, info, "objectForKey:", _nsstring(lib, "CFBundleName"), argtypes=[ctypes.c_void_p])
        if not value:
            return None
        raw = _send(lib, value, "UTF8String", restype=ctypes.c_char_p)
        return raw.decode("utf-8") if raw else None
    except Exception:
        return None


CAN_JOIN_ALL_SPACES = 1 << 0          # NSWindowCollectionBehaviorCanJoinAllSpaces
MOVE_TO_ACTIVE_SPACE = 1 << 1         # ...MoveToActiveSpace (Qt sets it on Tool windows)
FULL_SCREEN_PRIMARY = 1 << 7
FULL_SCREEN_AUXILIARY = 1 << 8        # ...FullScreenAuxiliary: may sit next to a full-screen app
FULL_SCREEN_NONE = 1 << 9


def all_spaces_behavior(current: int) -> int:
    """`current` changed to join every Space and sit beside full-screen apps. Each group
    of these flags allows only one choice: AppKit raises an Objective-C exception for a
    mix (e.g. CanJoinAllSpaces with the MoveToActiveSpace Qt gives Tool windows), which
    Python can't catch and which ends the program. So the rivals are cleared first."""
    current &= ~(MOVE_TO_ACTIVE_SPACE | FULL_SCREEN_PRIMARY | FULL_SCREEN_NONE)
    return current | CAN_JOIN_ALL_SPACES | FULL_SCREEN_AUXILIARY


def _ns_window(widget):
    """The NSWindow behind a shown Qt widget (cocoa only; None otherwise)."""
    from PySide6.QtGui import QGuiApplication
    if sys.platform != "darwin" or QGuiApplication.platformName() != "cocoa":
        return None, None
    lib = _objc()
    view = ctypes.c_void_p(int(widget.winId()))          # on cocoa, winId() is the NSView
    has_window = _send(lib, view, "respondsToSelector:", lib.sel_registerName(b"window"),
                       argtypes=[ctypes.c_void_p], restype=ctypes.c_bool)
    return lib, (_send(lib, view, "window") if has_window else None)


def keep_on_all_spaces(widget) -> bool:
    """A window normally lives on one Space (desktop): switching Spaces, or a
    full-screen app, would leave the docked panel behind. Make it follow. True if set."""
    try:
        lib, window = _ns_window(widget)
        if not window:
            return False
        can = _send(lib, window, "respondsToSelector:", lib.sel_registerName(b"setCollectionBehavior:"),
                    argtypes=[ctypes.c_void_p], restype=ctypes.c_bool)
        if not can:
            return False
        current = _send(lib, window, "collectionBehavior", restype=ctypes.c_ulong)
        _send(lib, window, "setCollectionBehavior:", all_spaces_behavior(current),
              argtypes=[ctypes.c_ulong], restype=None)
        return True
    except Exception:   # Python errors only: an Objective-C exception can't be caught, hence all_spaces_behavior
        return False


def collection_behavior(widget) -> int | None:
    """For checks: the window's current collection behaviour."""
    try:
        lib, window = _ns_window(widget)
        return _send(lib, window, "collectionBehavior", restype=ctypes.c_ulong) if window else None
    except Exception:
        return None


def set_app_name(name: str = APP_NAME) -> bool:
    """Make the menu bar (and the About/Quit items) say `name`. Call before QApplication.
    True if it was set."""
    if sys.platform != "darwin":
        return False
    try:
        lib = _objc()
        bundle = _send(lib, lib.objc_getClass(b"NSBundle"), "mainBundle")
        done = False
        for getter in ("localizedInfoDictionary", "infoDictionary"):
            info = _send(lib, bundle, getter)
            if not info:
                continue
            can_set = _send(lib, info, "respondsToSelector:", lib.sel_registerName(b"setObject:forKey:"),
                            argtypes=[ctypes.c_void_p], restype=ctypes.c_bool)
            if can_set:
                _send(lib, info, "setObject:forKey:", _nsstring(lib, name), _nsstring(lib, "CFBundleName"),
                      argtypes=[ctypes.c_void_p, ctypes.c_void_p])
                done = True
        return done
    except Exception:          # never let a cosmetic touch stop the panel from starting
        return False
