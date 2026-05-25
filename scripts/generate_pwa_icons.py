#!/usr/bin/env python3
"""PWA / 홈 화면 추가용 앱 아이콘 — 회색 원 + 네이비 둥근 사각 + 선명한 노란 심볼."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "static" / "img" / "logo-gulsakgi-nara.png"
OUT_DIR = ROOT / "static" / "img"

# 사용자 제공 홈 화면 시안
RING_GREY = (218, 220, 224, 255)  # #DADCE0
PANEL_DARK = (24, 30, 46, 255)  # #181E2E


def _load_mark() -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    w, h = logo.size
    mark = logo.crop((0, 0, min(128, int(w * 0.36)), h))
    bbox = mark.getbbox()
    if bbox:
        mark = mark.crop(bbox)
    return mark


def _mark_vivid(mark: Image.Image) -> Image.Image:
    """노란 심볼 채도·대비 강화."""
    mark = mark.convert("RGBA")
    r, g, b, a = mark.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb = ImageEnhance.Color(rgb).enhance(1.55)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.2)
    rgb = ImageEnhance.Brightness(rgb).enhance(1.06)
    rgb = ImageEnhance.Sharpness(rgb).enhance(1.25)
    out = Image.new("RGBA", mark.size)
    out.paste(rgb, (0, 0))
    out.putalpha(a.point(lambda p: min(255, int(p * 1.05))))
    return out


def _draw_panel(size: int, draw: ImageDraw.ImageDraw, *, panel_ratio: float) -> tuple[int, int, int, int]:
    pw = int(size * panel_ratio)
    ph = pw
    px = (size - pw) // 2
    py = (size - ph) // 2
    radius = max(6, int(pw * 0.13))
    draw.rounded_rectangle((px, py, px + pw, py + ph), radius=radius, fill=PANEL_DARK)
    return px, py, pw, ph


def _paste_mark(canvas: Image.Image, px: int, py: int, pw: int, ph: int) -> None:
    mark = _mark_vivid(_load_mark())
    pad = int(min(pw, ph) * 0.14)
    inner = min(pw, ph) - pad * 2
    ratio = min(inner / mark.width, inner / mark.height)
    nw, nh = int(mark.width * ratio), int(mark.height * ratio)
    mark = mark.resize((nw, nh), Image.Resampling.LANCZOS)
    x = px + (pw - nw) // 2
    y = py + (ph - nh) // 2
    canvas.paste(mark, (x, y), mark)


def _render_icon(size: int, *, panel_ratio: float = 0.56) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # 회색 원형 배경
    draw.ellipse((0, 0, size - 1, size - 1), fill=RING_GREY)

    # 네이비 둥근 사각
    px, py, pw, ph = _draw_panel(size, draw, panel_ratio=panel_ratio)
    _paste_mark(canvas, px, py, pw, ph)

    return canvas


def _render_maskable(size: int) -> Image.Image:
    """maskable: 회색 풀블리드 + 중앙 안전영역 디자인."""
    canvas = Image.new("RGBA", (size, size), RING_GREY)
    draw = ImageDraw.Draw(canvas)
    px, py, pw, ph = _draw_panel(size, draw, panel_ratio=0.5)
    _paste_mark(canvas, px, py, pw, ph)
    return canvas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "icon-192.png": lambda: _render_icon(192),
        "icon-512.png": lambda: _render_icon(512),
        "apple-touch-icon.png": lambda: _render_icon(180, panel_ratio=0.54),
        "icon-maskable-512.png": lambda: _render_maskable(512),
    }
    for name, builder in outputs.items():
        icon = builder()
        path = OUT_DIR / name
        icon.save(path, format="PNG", optimize=True)
        print(f"wrote {path} ({icon.size[0]}x{icon.size[1]})")


if __name__ == "__main__":
    main()
