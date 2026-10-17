"""The soundtrack for launch/video/falling.mp4: calm music, plus a sound for everything that moves.

    python launch/video/make_soundtrack.py   ->  launch/video/falling-soundtrack.wav, muxed into falling.mp4

Every sound here is synthesised from scratch -- sine waves, filtered noise and a plucked-string model -- so
there is nothing borrowed and nothing to license: it is as free to use as the code that makes it. The
timings come from make_falling.py itself (when each brick lands, when GeekOc swims, when each line and
screen appears), so the sound follows the picture, and re-running both keeps them in step.

The opening has no music, only quiet sounds: the kid's footsteps, GeekOc swimming, the bricks landing.
The music, a simple, playful marimba at 96 bpm, comes in at 0:32 as GeekOc swims off happy, starts to
fade at 2:30 and is silent by 2:34; after that, nothing.
"""

from __future__ import annotations

import runpy
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

HERE = Path(__file__).parent
SR = 44100
RNG = np.random.default_rng(7)

MUSIC_FROM = 32.0          # the music comes in (video time, seconds)...
FADE_FROM, SILENT_AT = 150.0, 154.0   # ...starts to fade at 2:30, and everything is silent from 2:34

# The kid's footsteps, where they fall in his clip (found from its own audio: peaks of the 60-1500 Hz
# band, every ~0.45 s). He stops after the last one.
STEPS = [0.41, 0.87, 1.32, 1.77, 2.20, 2.66, 3.13, 3.58, 4.08, 4.58]


# --------------------------------------------------------------------------- building blocks
def t_(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def env(n: int, a: float, r: float, curve: float = 1.0) -> np.ndarray:
    """An attack/release envelope over n samples (seconds for a and r)."""
    t = np.arange(n) / SR
    up = np.clip(t / max(a, 1e-4), 0, 1)
    down = np.clip((n / SR - t) / max(r, 1e-4), 0, 1)
    return (up * down) ** curve


def band(x: np.ndarray, lo: float | None, hi: float | None, order: int = 2) -> np.ndarray:
    if lo and hi:
        sos = butter(order, [lo, hi], "band", fs=SR, output="sos")
    elif lo:
        sos = butter(order, lo, "high", fs=SR, output="sos")
    else:
        sos = butter(order, hi, "low", fs=SR, output="sos")
    return sosfilt(sos, x)


def hz(note: str) -> float:
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    return 440.0 * 2 ** ((names[note[:-1]] + 12 * (int(note[-1]) + 1) - 69) / 12)


def marimba(f: float, dur: float = 0.6) -> np.ndarray:
    """A wooden mallet bar: a quick-dying fundamental with a bright fourth harmonic on the strike."""
    t = t_(dur)
    return (np.sin(2 * np.pi * f * t) * np.exp(-9 * t)
            + 0.35 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-30 * t)) * env(len(t), 0.002, 0.1)


def bell(f: float, dur: float = 1.8) -> np.ndarray:
    """A small bell: inharmonic partials that ring out at different speeds."""
    t = t_(dur)
    out = np.zeros_like(t)
    for ratio, amp, decay in ((1.0, 1.0, 2.2), (2.76, 0.45, 3.5), (5.4, 0.22, 6.0), (8.93, 0.1, 9.0)):
        out += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-decay * t)
    return out * env(len(t), 0.003, 0.2)


def tok(f: float, click: bool = True) -> np.ndarray:
    """A wooden tok: a brick landing on bricks. Without the click it is a soft, rounded knock."""
    t = t_(0.18)
    body = np.sin(2 * np.pi * f * t) * np.exp(-38 * t) + 0.5 * np.sin(2 * np.pi * f * 2.31 * t) * np.exp(-55 * t)
    body *= env(len(t), 0.004, 0.05)                     # no hard edge at the start
    if not click:
        return body * 0.8
    tick = band(RNG.normal(0, 1, len(t)), 1500, 6000) * np.exp(-180 * t) * 0.35
    return (body + tick) * 0.8


def step(f: float = 95.0) -> np.ndarray:
    """A soft footstep: a low thump under a short scuff of filtered noise."""
    t = t_(0.16)
    thump = np.sin(2 * np.pi * (f + 40 * np.exp(-30 * t)) * t) * np.exp(-28 * t)
    scuff = band(RNG.normal(0, 1, len(t)), 200, 1100, 4) * np.exp(-55 * t) * 0.22   # soft soles, not a hiss
    return thump + scuff


def swirl(dur: float = 0.9) -> np.ndarray:
    """Water moved by a stroke: low, dark noise that swells gently and drains away, with a slow wobble,
    like hearing it from under the surface. No hiss."""
    n = int(dur * SR)
    noise = band(RNG.normal(0, 1, n), 90, 420, 4)
    wobble = 1 + 0.35 * np.sin(2 * np.pi * 5.5 * np.arange(n) / SR + RNG.uniform(0, 6.28))
    shape = np.sin(np.linspace(0, np.pi, n)) ** 3
    return noise * wobble * shape * 0.9


def bubble(f: float) -> np.ndarray:
    t = t_(0.07)
    return np.sin(2 * np.pi * f * (1 + 2.2 * t / 0.07) * t) * np.exp(-40 * t) * env(len(t), 0.004, 0.02)


def swish(dur: float = 0.45) -> np.ndarray:
    n = int(dur * SR)
    noise = band(RNG.normal(0, 1, n), 1200, 7000)
    shape = np.linspace(0, 1, n) ** 2 * np.exp(-np.linspace(0, 4, n)) * 3
    return noise * shape * 0.35


def key_click() -> np.ndarray:
    t = t_(0.03)
    return band(RNG.normal(0, 1, len(t)), 2000, 8000) * np.exp(-260 * t) * 0.6


class Track:
    """A stereo bus that sounds are dropped into at a time, a level and a pan."""

    def __init__(self, dur: float):
        self.buf = np.zeros((int(dur * SR) + SR * 4, 2))

    def add(self, sound: np.ndarray, at: float, gain: float = 1.0, pan: float = 0.0) -> None:
        i = int(at * SR)
        if i < 0 or i >= len(self.buf):
            return
        s = sound[: len(self.buf) - i] * gain
        self.buf[i:i + len(s), 0] += s * np.sqrt((1 - pan) / 2)
        self.buf[i:i + len(s), 1] += s * np.sqrt((1 + pan) / 2)


def reverb(x: np.ndarray, seconds: float = 2.2, wet: float = 0.28) -> np.ndarray:
    """A room: convolution with exponentially decaying noise, different per side."""
    n = int(seconds * SR)
    decay = np.exp(-np.linspace(0, 7, n))
    out = np.empty_like(x)
    for ch in (0, 1):
        ir = band(RNG.normal(0, 1, n), 200, 7000) * decay
        ir /= np.sqrt((ir ** 2).sum())
        out[:, ch] = fftconvolve(x[:, ch], ir)[: len(x)]
    return x * (1 - wet) + out * wet


# --------------------------------------------------------------------------- the score
def main() -> None:
    sys.argv = [sys.argv[0]]
    v = runpy.run_path(str(HERE / "make_falling.py"), run_name="soundtrack")   # its timings, not its render
    L = v["KID_LEAD"]                                  # scene time -> video time
    total = L + v["DUR"]
    music, sfx = Track(total), Track(total)

    # ---- music: a playful marimba at 96 bpm, from 0:32 to the end of the fade. Each bar (2.5 s) is
    # one chord: an arpeggio in eighths over a low bar on beats one and three. A little tune comes and
    # goes in ten-second phrases, two versions taking turns, so it never just loops.
    eighth = 60 / 96 / 2
    chords = [["C3", "E4", "G4", "C5"], ["G2", "D4", "G4", "B4"], ["A2", "C4", "E4", "A4"], ["F2", "C4", "F4", "A4"]]
    scale = [hz(n) for n in ("C5", "D5", "E5", "G5", "A5", "C6", "D6", "E6")]
    tunes = [[0, 2, 4, 5, 4, 2, None, 3, 4, None, 2, 0, 1, 2, None, None],
             [4, 5, 6, 5, 4, 2, None, 0, 2, None, 4, 2, 1, 0, None, None]]
    t, k = MUSIC_FROM, 0
    while t < SILENT_AT:
        c = [hz(n) for n in chords[k % 4]]
        arp = [c[1], c[2], c[3], c[2] * 2, c[3], c[2], c[1] * 2, c[3]]
        for j, f in enumerate(arp):
            music.add(marimba(f), t + j * eighth, 0.22, pan=-0.4 + 0.8 * (j % 2))
        music.add(marimba(c[0], 1.0), t, 0.25)
        music.add(marimba(c[0], 1.0), t + 4 * eighth, 0.18)
        phrase = (k // 4) % 4                          # 4 bars = 10 s: tune, rest, the other tune, rest
        if k % 4 == 0 and phrase in (0, 2):
            for i, n in enumerate(tunes[phrase // 2]):
                if n is not None:
                    music.add(marimba(scale[n], 0.8), t + i * eighth * 2, 0.12, pan=0.15)
        t += 8 * eighth
        k += 1

    # ---- the kid's footsteps, panned as he walks left to right
    for i, s in enumerate(STEPS):
        sfx.add(step(90 + 12 * (i % 2)), s, 0.30 if i < len(STEPS) - 1 else 0.18, pan=-0.2 + 0.07 * i)

    # ---- GeekOc swimming: a soft swirl of water on every wing beat, while he is stroking
    beat = 0.85
    for at, dur, x_from, x_to in ((0.0, v["SWIM_IN"], -0.9, -0.6), (v["SWIM_OUT_AT"], v["SWIM_OUT"], -0.6, 0.6),
                                  (v["LEAVE_AT"], v["LEAVE"], 0.6, 1.0)):
        n = 0
        while n / beat < dur * 0.8:
            when = at + n / beat
            pan = x_from + (x_to - x_from) * (n / beat) / dur
            sfx.add(swirl(), L + when, 0.16, pan=pan)
            if n % 2 == 0:                               # now and then one small, low bubble
                sfx.add(bubble(RNG.uniform(280, 420)), L + when + 0.45, 0.035, pan=pan)
            n += 1

    # ---- bricks: a soft knock on landing, fainter ones on the bounces, higher up the mountain
    icons = v["prepare_icons"]()
    for p in v["plan"](len(icons)):
        land = L + p["at"] + p["fall"]
        f = 520 + 60 * p["r"] + RNG.uniform(-40, 40)
        pan = (p["x"] - v["W"] / 2) / (v["W"] / 2) * 0.7
        sfx.add(tok(f, click=False), land, 0.075 * p["bounce"], pan)
        for (a, _b, h) in v["BOUNCES"][1:]:
            sfx.add(tok(f * 1.05, click=False), land + a, 0.05 * h / 52 * p["bounce"], pan)
    # the mountain and the kid fade: one soft reversed swell
    n = int(1.4 * SR)
    swell = band(RNG.normal(0, 1, n), 300, 3000) * np.linspace(0, 1, n) ** 3 * 0.3
    sfx.add(swell, L + v["OUTRO"] - 0.6, 0.6)

    # ---- the lines: a soft chime as each one begins
    start = L + v["SWIM_IN"] + 0.8
    for i in range(len(v["PHRASES"])):
        sfx.add(bell(hz(("E5", "G5", "A5", "C6", "E6")[i]), 2.0), start + i * (v["HOLD"] + v["GAP"]), 0.09)

    # ---- the logo drops in on the left and bounces
    land = L + v["LOGO_AT"] + v["LOGO_FALL"]
    sfx.add(swish(0.9), land - 0.9, 0.5, pan=-0.6)
    sfx.add(tok(260), land, 0.6, pan=-0.6)
    sfx.add(tok(300), land + 0.34, 0.25, pan=-0.6)
    sfx.add(tok(320), land + 0.56, 0.1, pan=-0.6)

    # ---- every screen arriving: a swish
    for i in range(len(v["TOUR"])):
        sfx.add(swish(), L + v["TOUR_AT"] + i * v["TOUR_EACH"], 0.30)
    sfx.add(swish(), L + v["PHONE_AT"], 0.30)
    for i in range(len(v["SETUP"])):
        sfx.add(swish(), L + v["INSTALL_AT"] + i * v["INSTALL_EACH"], 0.30)

    # ---- the terminal: a click for every key typed, and a tiny chime when it says "Successfully"
    term = L + v["TERM_AT"]
    sfx.add(swish(), term, 0.3)
    for at, kind, text in v["TERM_SCRIPT"]:
        if kind == "cmd":
            for c in range(len(text)):
                sfx.add(key_click(), term + at + c / 20 + RNG.uniform(0, 0.012), 0.25, pan=RNG.uniform(-0.2, 0.2))
        elif kind == "ok":
            sfx.add(bell(hz("G5"), 1.2), term + at, 0.08)

    # ---- the promises: each badge pops with a bell
    for i in range(len(v["PROMISES"])):
        sfx.add(bell(hz(("C5", "D5", "E5", "G5", "A5")[i]), 2.2), L + v["PROMISE_AT"] + i * v["PROMISE_EACH"], 0.13)

    # ---- the finale: the icon pops, then a tick for each platform
    sfx.add(bell(hz("C6"), 2.5), L + v["FINALE_AT"] + 0.1, 0.12)
    for i in range(3):
        sfx.add(tok(900 + 120 * i), L + v["PLATFORMS_AT"] + i * 0.3, 0.12, pan=-0.4 + 0.4 * i)

    # ---- mix: music in a soft room, effects drier. The music eases in over a second and a half at 0:32;
    # before that the effects play alone, kept low. Everything fades from 2:30 and is silent from 2:34.
    n = int(total * SR)
    tt = np.arange(len(music.buf)) / SR
    music.buf *= np.clip((tt - MUSIC_FROM) / 1.5, 0, 1)[:, None]
    sfx.buf[: int(MUSIC_FROM * SR)] *= 0.7
    mix = (reverb(music.buf, 2.6, 0.30) * 0.9 + reverb(sfx.buf, 1.2, 0.12))[:n]
    tt = np.arange(n) / SR
    fade = np.clip(tt / 0.4, 0, 1) * np.clip((SILENT_AT - tt) / (SILENT_AT - FADE_FROM), 0, 1) ** 1.5
    mix *= fade[:, None]
    mix *= 0.89 / np.abs(mix).max()                     # peak at about -1 dBFS
    out = HERE / "falling-soundtrack.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    print(f"Wrote {out} ({total:.0f} s)")

    # ---- into the video: the picture is copied as it is, only the sound is added
    import imageio_ffmpeg
    video, tmp = HERE / "falling.mp4", HERE / "falling.tmp.mp4"
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(video), "-i", str(out),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(video)
    print(f"Muxed into {video}")


if __name__ == "__main__":
    main()
