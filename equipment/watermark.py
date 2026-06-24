"""매물 이미지 워터마크 처리 (Pillow).

업로드된 매물 이미지 우측 하단에 반투명 텍스트 워터마크를 삽입해 무단 복제·재사용을
어렵게 한다. 폰트 크기는 이미지 너비의 약 3%로 자동 조정하며, 원본 파일을 덮어쓴다.

주의: 이 기능은 일반적인 이미지 도용을 어렵게 할 뿐, 개발자도구/원본 추적 등을 통한
완벽한 차단은 불가능하다.
"""
import logging
import os

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

logger = logging.getLogger(__name__)

WATERMARK_TEXT = "굴삭기나라 direct-nara.co.kr"

# 이미지 메타데이터에 남겨 중복 적용을 방지하는 마커(주로 PNG에서 유효).
# JPEG/WEBP 등은 모델의 watermarked 플래그로 중복 적용을 막는다.
_MARKER_KEY = "gn_watermark"
_MARKER_VALUE = "1"

# 이미지 너비 대비 폰트 크기 비율(약 3%)
_FONT_RATIO = 0.03
_MIN_FONT_SIZE = 14
# 워터마크 텍스트 불투명도(0~255). 값이 낮을수록 더 투명.
_TEXT_ALPHA = 150
_SHADOW_ALPHA = 110


def _load_font(size):
    """한글 지원 폰트를 우선 로드하고, 실패 시 기본 폰트로 대체한다."""
    custom = (getattr(settings, "WATERMARK_FONT_PATH", "") or "").strip()
    candidates = [custom] if custom else []
    candidates += ["DejaVuSans.ttf"]
    for path in candidates:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    except Exception:
        return draw.textsize(text, font=font)


def is_watermarked(path):
    """파일 메타데이터 마커로 워터마크 적용 여부를 판단(가능한 포맷에 한해)."""
    try:
        with Image.open(path) as img:
            return img.info.get(_MARKER_KEY) == _MARKER_VALUE
    except Exception:
        return False


def apply_watermark(path):
    """이미지에 워터마크를 삽입하고 원본을 덮어쓴다.

    반환값: 처리 후 이미지가 워터마크를 가진 상태이면 True(새로 적용했거나 이미 적용됨),
    파일이 없거나 처리에 실패하면 False.
    """
    if not path or not os.path.exists(path):
        return False
    try:
        with Image.open(path) as img:
            fmt = (img.format or "").upper()
            if img.info.get(_MARKER_KEY) == _MARKER_VALUE:
                return True  # 이미 적용됨 → 중복 적용 안 함

            base = img.convert("RGBA")
            width, height = base.size
            if width < 40 or height < 20:
                return False  # 너무 작은 이미지는 건너뜀

            font_size = max(_MIN_FONT_SIZE, int(width * _FONT_RATIO))
            font = _load_font(font_size)

            overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            text_w, text_h = _text_size(draw, WATERMARK_TEXT, font)

            margin = max(8, int(width * 0.012))
            x = width - text_w - margin
            y = height - text_h - margin
            if x < margin:
                x = margin

            # 가독성을 위한 옅은 그림자 + 반투명 흰색 텍스트
            shadow_offset = max(1, font_size // 18)
            draw.text(
                (x + shadow_offset, y + shadow_offset),
                WATERMARK_TEXT,
                font=font,
                fill=(0, 0, 0, _SHADOW_ALPHA),
            )
            draw.text((x, y), WATERMARK_TEXT, font=font, fill=(255, 255, 255, _TEXT_ALPHA))

            combined = Image.alpha_composite(base, overlay)

            _save(combined, path, fmt)
        return True
    except Exception:
        logger.exception("워터마크 적용 실패: %s", path)
        return False


def _save(image_rgba, path, fmt):
    """원본 포맷에 맞춰 저장(덮어쓰기). PNG에는 중복 방지 마커를 남긴다."""
    ext = os.path.splitext(path)[1].lower()
    fmt = fmt or ""

    if fmt == "PNG" or ext == ".png":
        meta = PngImagePlugin.PngInfo()
        meta.add_text(_MARKER_KEY, _MARKER_VALUE)
        image_rgba.save(path, format="PNG", optimize=True, pnginfo=meta)
        return

    if fmt == "WEBP" or ext == ".webp":
        image_rgba.save(path, format="WEBP", quality=90, method=6)
        return

    if fmt == "GIF" or ext == ".gif":
        image_rgba.convert("P", palette=Image.ADAPTIVE).save(path, format="GIF")
        return

    # 기본: JPEG (RGBA → RGB, 흰 배경 합성)
    rgb = Image.new("RGB", image_rgba.size, (255, 255, 255))
    rgb.paste(image_rgba, mask=image_rgba.split()[-1])
    rgb.save(path, format="JPEG", quality=90, optimize=True)
