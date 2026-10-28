"""Cut the games' icons out of one generated sheet (4 × 4 tiles on white, filled left to right, top to bottom, in
GEMS order: src/mygeeky/gems.py GAMES) and write one transparent PNG per game for both apps.

    python tools/game_icons.py ~/Downloads/sheet.jpeg
    python tools/game_icons.py --hub ~/Downloads/geekoc-playing.jpeg     (the Games entry's own icon)

Each tile is found as a block of non-white pixels; the white outside its rounded corners becomes transparent
(flooded in from the tile's own edge, so white inside the drawing stays). Output, 256 px:
    src/mygeeky/gui/assets/game_<id>.png   (the computer)
    mobile/assets/games/<id>.png           (the phone)
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mygeeky.gems import GAMES  # noqa: E402

SIZE = 256
WHITE = 236            # brighter than this on all three channels counts as the sheet's white


def _array(img: QImage) -> np.ndarray:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine() // 4, 4)
    return a[:, :img.width()].copy()


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Start and end of each run of True, ignoring runs shorter than 3% of the side (specks)."""
    out, start = [], None
    for i, v in enumerate(list(mask) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start > len(mask) * 0.03:
                out.append((start, i))
            start = None
    return out


def tiles(a: np.ndarray) -> list[tuple[int, int, int, int]]:
    ink = (a[:, :, :3] < WHITE).any(axis=2)
    rows, cols = _runs(ink.mean(axis=1) > 0.02), _runs(ink.mean(axis=0) > 0.02)
    boxes = []
    for y0, y1 in rows:
        for x0, x1 in cols:
            if ink[y0:y1, x0:x1].mean() > 0.3:          # an empty cell (15, 16) holds no tile
                boxes.append((x0, y0, x1, y1))
    return boxes


def cut(a: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    pad = 2
    t = a[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad].copy()
    h, w = t.shape[:2]
    white = (t[:, :, :3] >= WHITE - 20).all(axis=2)
    outside = np.zeros((h, w), bool)
    q = deque((y, x) for y in range(h) for x in (0, w - 1))
    q.extend((y, x) for x in range(w) for y in (0, h - 1))
    while q:                                             # flood the sheet's white in from the edge
        y, x = q.popleft()
        if outside[y, x] or not white[y, x]:
            continue
        outside[y, x] = True
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and not outside[ny, nx]:
                q.append((ny, nx))
    t[:, :, 3] = np.where(outside, 0, 255)
    side = max(h, w)                                     # square, centred
    sq = np.zeros((side, side, 4), np.uint8)
    sq[(side - h) // 2:(side - h) // 2 + h, (side - w) // 2:(side - w) // 2 + w] = t
    return sq


def main(sheet: str) -> None:
    img = QImage(sheet)
    if img.isNull():
        raise SystemExit(f"can't read {sheet}")
    a = _array(img)
    boxes = tiles(a)
    if len(boxes) != len(GAMES):
        raise SystemExit(f"found {len(boxes)} tiles, expected {len(GAMES)} (one per game in GEMS order)")
    desk, phone = ROOT / "src/mygeeky/gui/assets", ROOT / "mobile/assets/games"
    phone.mkdir(parents=True, exist_ok=True)
    for game, box in zip(GAMES, boxes):
        sq = np.ascontiguousarray(cut(a, box))
        q = QImage(sq.data, sq.shape[1], sq.shape[0], sq.shape[1] * 4, QImage.Format_RGBA8888).copy()
        q = q.scaled(SIZE, SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        q.save(str(desk / f"game_{game['id']}.png"))
        q.save(str(phone / f"{game['id']}.png"))
        print(f"{game['id']:10} {box}")


def hub(picture: str) -> None:
    """The Games entry's own icon (GeeKOc playing): one picture on white, cropped to the drawing, the white around
    it transparent. Written as gui/assets/games_hub.png and mobile/assets/games/hub.png."""
    img = QImage(picture)
    if img.isNull():
        raise SystemExit(f"can't read {picture}")
    a = _array(img)
    ink = (a[:, :, :3] < WHITE).any(axis=2)
    ys, xs = np.where(ink)
    sq = cut(a, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    sq = np.ascontiguousarray(sq)
    q = QImage(sq.data, sq.shape[1], sq.shape[0], sq.shape[1] * 4, QImage.Format_RGBA8888).copy()
    q = q.scaled(SIZE, SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    q.save(str(ROOT / "src/mygeeky/gui/assets/games_hub.png"))
    (ROOT / "mobile/assets/games").mkdir(parents=True, exist_ok=True)
    q.save(str(ROOT / "mobile/assets/games/hub.png"))
    print("hub", q.width(), q.height())


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--hub":
        hub(sys.argv[2])
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Downloads/Gemini_Generated_Image_svw6q4svw6q4svw6.jpeg"))
