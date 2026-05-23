#!/usr/bin/env python3
"""PWA / 홈 화면 추가용 앱 아이콘 생성 (브랜드 골드 + 흰 심볼)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "static" / "img" / "logo-gulsakgi-nara.png"
OUT_DIR = ROOT / "static" / "img"

BRAND_GOLD = (245, 166, 35, 255)  # #F5A623
BRAND_RED = (232, 57, 70, 255)  # #E83946
WHITE = (255, 255, 255, 255)


def _load_mark() -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    w, h = logo.size
    mark = logo.crop((0, 0, min(128, int(w * 0.36)), h))
    bbox = mark.getbbox()
    if bbox:
        mark = mark.crop(bbox)
    return mark


def _mark_white(mark: Image.Image) -> Image.Image:
    """로고 심볼을 홈 화면용 흰색 실루엣으로."""
    mark = mark.convert("RGBA")
    r, g, b, a = mark.split()
    lum = Image.merge("RGB", (r, g, b)).convert("L")
    alpha = Image.composite(a, Image.new("L", mark.size, 0), lum)
    alpha = alpha.point(lambda p: min(255, int(p * 1.15)))
    white = Image.new("RGBA", mark.size, WHITE)
    white.putalpha(alpha)
    return white


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _render_icon(size: int, *, safe_ratio: float, maskable: bool = False) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), BRAND_GOLD)
    draw = ImageDraw.Draw(canvas)

    # 은은한 상단 하이라이트 (플랫 아이콘에 깊이)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((-size * 0.15, -size * 0.35, size * 0.85, size * 0.55), fill=(255, 255, 255, 38))
    canvas = Image.alpha_composite(canvas, glow)

    # 하단 브랜드 레드 라인 (얇게)
    line_h = max(3, size // 28) if not maskable else max(4, size // 22)
    draw.rectangle((0, size - line_h, size, size), fill=BRAND_RED)

    mark = _mark_white(_load_mark())
    pad = int(size * (1 - safe_ratio) / 2)
    inner = size - pad * 2 - line_h
    ratio = min(inner / mark.width, inner / mark.height)
    nw, nh = int(mark.width * ratio), int(mark.height * ratio)
    mark = mark.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (size - nw) // 2
    y = pad + (inner - nh) // 2
    canvas.paste(mark, (x, y), mark)

    if not maskable:
        # iOS 스쿼클 느낌 (선택적 소프트 모서리 — OS가 자르기 전 미리보기용)
        radius = int(size * 0.22)
        mask = _rounded_mask(size, radius)
        rounded = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        rounded.paste(canvas, (0, 0), mask)
        canvas = rounded

    return canvas


def _render_maskable(size: int) -> Image.Image:
    """Android maskable: 안전 영역 안에 심볼, 배경은 전체 골드."""
    canvas = Image.new("RGBA", (size, size), BRAND_GOLD)
    draw = ImageDraw.Draw(canvas)
    line_h = max(4, size // 20)
    draw.rectangle((0, size - line_h, size, size), fill=BRAND_RED)

    mark = _mark_white(_load_mark())
    inner = int(size * 0.52)
    ratio = min(inner / mark.width, inner / mark.height)
    nw, nh = int(mark.width * ratio), int(mark.height * ratio)
    mark = mark.resize((nw, nh), Image.Resampling.LANCZOS)
    x = (size - nw) // 2
    y = (size - line_h - nh) // 2
    canvas.paste(mark, (x, y), mark)
    return canvas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "icon-192.png": lambda: _render_icon(192, safe_ratio=0.72),
        "icon-512.png": lambda: _render_icon(512, safe_ratio=0.72),
        "apple-touch-icon.png": lambda: _render_icon(180, safe_ratio=0.7),
        "icon-maskable-512.png": lambda: _render_maskable(512),
    }
    for name, builder in outputs.items():
        icon = builder()
        path = OUT_DIR / name
        icon.save(path, format="PNG", optimize=True)
        print(f"wrote {path} ({icon.size[0]}x{icon.size[1]})")


if __name__ == "__main__":
    main()
