"""Split the myGeeKy badge into layers (badge, arms, G, ee, K, m, y) and animate them in one SVG.

The layers are the real artwork: each pixel is "un-blended" from the badge's dark background
(colour-to-alpha), so stacking the layers back on the background gives the original exactly."""
import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = Path(sys.argv[1])            # the 512 px round icon
OUT = Path(sys.argv[2])            # the .svg
SIZE = 384                         # layer resolution inside the 512 viewBox (keeps the file small)

im = Image.open(SRC).convert("RGBA")
a = np.asarray(im).astype(float)
rgb, alpha = a[..., :3], a[..., 3] / 255
bg = np.median(rgb[(alpha > 0.98) & (rgb.max(axis=2) < 40)], axis=0)

# the parts: bright connected shapes
bright = (rgb.max(axis=2) > 110) & (alpha > 0.8)
lab, n = ndimage.label(bright)
parts = {}
for i, sl in enumerate(ndimage.find_objects(lab), 1):
    comp = lab == i
    area = comp.sum()
    if area < 150:
        continue
    cx = (sl[1].start + sl[1].stop) / 2
    cy = (sl[0].start + sl[0].stop) / 2
    w = sl[1].stop - sl[1].start
    if w > 300:
        name = "ring"                                  # the two arms
    elif area > 15000:
        name = "G" if cx < 256 else "K"
    elif cy < 200:
        name = "m"
    elif cy > 330:
        name = "y"
    else:
        name = "ee"
    parts[name] = parts.get(name, np.zeros_like(comp)) | comp
print("parts:", sorted(parts))

# every letter takes its soft edge with it; everything else (arms, glow) is the ring
owner = {}
taken = np.zeros(alpha.shape, bool)
for name in ("G", "K", "ee", "m", "y"):
    grown = ndimage.binary_dilation(parts[name], iterations=4) & ~taken
    owner[name] = grown
    taken |= grown
owner["ring"] = ~taken

# colour-to-alpha against the background
diff = rgb - bg
up = np.where(diff > 0, diff / (255 - bg), -diff / np.maximum(bg, 1))
fa = np.clip(up.max(axis=2), 0, 1)
fg = np.where(fa[..., None] > 0, bg + diff / np.maximum(fa[..., None], 1e-6), bg)
fg = np.clip(fg, 0, 255)


def layer(mask: np.ndarray) -> Image.Image:
    out = np.zeros(a.shape, np.uint8)
    out[..., :3] = fg.astype(np.uint8)
    out[..., 3] = (fa * alpha * mask * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def badge() -> Image.Image:
    out = np.zeros(a.shape, np.uint8)
    out[..., :3] = bg.astype(np.uint8)
    out[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def uri(img: Image.Image) -> str:
    img = img.resize((SIZE, SIZE), Image.LANCZOS)
    bbox = img.getchannel("A").getbbox() or (0, 0, 1, 1)
    crop = img.crop(bbox)
    buf = io.BytesIO()
    px = np.asarray(crop).copy()
    px[px[..., 3] == 0, :3] = 0                       # hidden pixels: blank, so they compress
    Image.fromarray(px, "RGBA").save(buf, "WEBP", quality=92, method=6)
    k = 512 / SIZE
    x, y, w, h = bbox[0] * k, bbox[1] * k, crop.width * k, crop.height * k
    return (f'x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
            f'href="data:image/webp;base64,{base64.b64encode(buf.getvalue()).decode()}"')


layers = {"badge": badge(), **{k: layer(v) for k, v in owner.items()}}
CSS = """
  svg { overflow: visible; }
  .p { transform-box: fill-box; transform-origin: center; }
  #badge { animation: fade .5s ease-out both; }
  #ring  { transform-box: view-box; transform-origin: 256px 256px;
           animation: spin 1.4s cubic-bezier(.16,.84,.3,1) both, breathe 2s ease-in-out 3.2s infinite; }
  #ringflash { animation: flashfade .8s ease-out 2.8s both; }
  #G  { animation: pop .6s cubic-bezier(.34,1.56,.64,1) 1.2s both; }
  #ee { animation: slide .55s cubic-bezier(.34,1.4,.64,1) 1.55s both; }
  #K  { animation: drop .6s cubic-bezier(.34,1.56,.64,1) 1.7s both; }
  #m  { animation: fall .7s cubic-bezier(.2,1.5,.5,1) 2.3s both; }
  #y  { animation: rise .7s cubic-bezier(.2,1.5,.5,1) 2.4s both; }
  @keyframes fade  { from { opacity: 0; } to { opacity: 1; } }
  @keyframes spin  { from { opacity: .05; transform: rotate(-360deg) scale(.92); }
                     to   { opacity: 1;   transform: rotate(0deg) scale(1); } }
  @keyframes breathe { 0%,100% { opacity: 1; } 50% { opacity: .8; } }
  @keyframes flashfade { 0% { opacity: 0; } 30% { opacity: .85; } 100% { opacity: 0; } }
  @keyframes pop   { 0% { opacity: 0; transform: scale(.6); } 60% { opacity: 1; transform: scale(1.08); }
                     100% { opacity: 1; transform: scale(1); } }
  @keyframes slide { 0% { opacity: 0; transform: translateX(-28px) scale(.7); }
                     100% { opacity: 1; transform: none; } }
  @keyframes drop  { 0% { opacity: 0; transform: translateY(-40px) scale(.85); }
                     60% { opacity: 1; transform: translateY(4px) scale(1.05); }
                     100% { opacity: 1; transform: none; } }
  @keyframes fall  { 0% { opacity: 0; transform: translateY(-120px) scale(1.8); filter: blur(6px) brightness(2); }
                     55% { opacity: 1; filter: blur(0) brightness(1.8); }
                     100% { opacity: 1; transform: none; filter: none; } }
  @keyframes rise  { 0% { opacity: 0; transform: translateY(120px) scale(1.8); filter: blur(6px) brightness(2); }
                     55% { opacity: 1; filter: blur(0) brightness(1.8); }
                     100% { opacity: 1; transform: none; filter: none; } }
  @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
"""
# the finish: a bright, soft copy of the ring flashes once
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="myGeeKy is loading">
<title>myGeeKy</title>
<style>{CSS}</style>
<circle id="badge" cx="256" cy="256" r="255.5" fill="#{''.join(f'{int(v):02x}' for v in bg)}"/>
<g id="ring"><image id="ringimg" {uri(layers['ring'])}/></g>
<g id="ringflash" style="mix-blend-mode:screen;opacity:0"><use href="#ringimg" style="filter:brightness(1.6) blur(2px)"/></g>
<image id="G" class="p" {uri(layers['G'])}/>
<image id="ee" class="p" {uri(layers['ee'])}/>
<image id="K" class="p" {uri(layers['K'])}/>
<image id="m" class="p" {uri(layers['m'])}/>
<image id="y" class="p" {uri(layers['y'])}/>
</svg>
"""
OUT.write_text(svg, encoding="utf-8")
print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")

# the same layers as plain images, for the desktop splash and the phone's opening screen
# (neither can play the SVG's CSS animation): make_loader.py <icon> <svg> <dir> [<dir> ...]
for folder in sys.argv[3:]:
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    for name in ("ring", "G", "ee", "K", "m", "y"):
        img = layers[name].resize((SIZE, SIZE), Image.LANCZOS)
        px = np.asarray(img).copy()
        px[px[..., 3] == 0, :3] = 0
        Image.fromarray(px, "RGBA").save(d / f"loader_{name}.png", optimize=True)
    print(f"layers in {d}")
