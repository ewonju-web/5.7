#!/usr/bin/env python3
"""PWA / 홈 화면 추가용 앱 아이콘 생성 (logo-gulsakgi-nara 심볼 기준)."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "static" / "img" / "logo-gulsakgi-nara.png"
OUT_DIR = ROOT / "static" / "img"

BG = (55, 65, 81, 255)  # #374151 — 상단 네비와 동일
ACCENT = (232, 163, 23, 255)  # #e8a317


def _load_mark() -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    w, h = logo.size
    # 왼쪽 X 심볼만 (한글 텍스트 제외)
    mark = logo.crop((0, 0, min(128, int(w * 0.36)), h))
    bbox = mark.getbbox()
    if bbox:
        mark = mark.crop(bbox)
    return mark


def _render_icon(size: int, *, safe_ratio: float) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(canvas)

    # 하단 포인트 컬러 라인
    line_h = max(4, size // 24)
    draw.rectangle((0, size - line_h, size, size), fill=ACCENT)

    mark = _load_mark()
    pad = int(size * (1 - safe_ratio) / 2)
    inner = size - pad * 2 - line_h
    ratio = min(inner / mark.width, inner / mark.height)
    nw, nh = int(mark.width * ratio), int(mark.height * ratio)
    mark = mark.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (size - nw) // 2
    y = pad + (inner - nh) // 2
    canvas.paste(mark, (x, y), mark)
    return canvas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "icon-192.png": (192, 0.78),
        "icon-512.png": (512, 0.78),
        "apple-touch-icon.png": (180, 0.76),
        "icon-maskable-512.png": (512, 0.62),
    }
    for name, (size, safe) in outputs.items():
        icon = _render_icon(size, safe_ratio=safe)
        path = OUT_DIR / name
        icon.save(path, format="PNG", optimize=True)
        print(f"wrote {path} ({size}x{size})")


if __name__ == "__main__":
    main()
