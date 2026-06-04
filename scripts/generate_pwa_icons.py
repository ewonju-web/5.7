#!/usr/bin/env python3
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance
ROOT = Path(__file__).resolve().parents[1]
MARK = ROOT / "static" / "img" / "icon-mark.png"
OUT_DIR = ROOT / "static" / "img"
RING_GREY = (218, 220, 224, 255)
MARK_RATIO = 1.05
MARK_FILL_IN_SOURCE = 1.0

def _load_mark():
    mark = Image.open(MARK).convert("RGBA")
    bbox = mark.getbbox()
    if bbox:
        mark = mark.crop(bbox)
    w, h = mark.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(mark, ((side - w) // 2, (side - h) // 2), mark)
    fill = int(side * MARK_FILL_IN_SOURCE)
    mark = canvas.resize((fill, fill), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(mark, ((side - fill) // 2, (side - fill) // 2), mark)
    return out

def _mark_vivid(mark):
    mark = mark.convert("RGBA")
    r, g, b, a = mark.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb = ImageEnhance.Color(rgb).enhance(1.12)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.08)
    out = Image.new("RGBA", mark.size)
    out.paste(rgb, (0, 0))
    out.putalpha(a)
    return out

def _paste_mark(canvas, size, mark_ratio):
    mark = _mark_vivid(_load_mark())
    inner = int(size * mark_ratio)
    pad = (size - inner) // 2
    ratio = min(inner / mark.width, inner / mark.height)
    nw, nh = int(mark.width * ratio), int(mark.height * ratio)
    mark = mark.resize((nw, nh), Image.Resampling.LANCZOS)
    x = pad + (inner - nw) // 2
    y = pad + (inner - nh) // 2
    canvas.paste(mark, (x, y), mark)

def _render_icon(size, mark_ratio=MARK_RATIO):
    canvas = Image.new("RGBA", (size, size), RING_GREY)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((0, 0, size - 1, size - 1), fill=RING_GREY)
    _paste_mark(canvas, size, mark_ratio)
    return canvas

def _render_maskable(size):
    canvas = Image.new("RGBA", (size, size), RING_GREY)
    _paste_mark(canvas, size, 1.05)
    return canvas

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in {
        "icon-192.png": lambda: _render_icon(192),
        "icon-512.png": lambda: _render_icon(512),
        "apple-touch-icon.png": lambda: _render_icon(180, mark_ratio=1.08),
        "icon-maskable-512.png": lambda: _render_maskable(512),
    }.items():
        icon = builder()
        icon.save(OUT_DIR / name, format="PNG", optimize=True)
        print("wrote", OUT_DIR / name)

if __name__ == "__main__":
    main()
