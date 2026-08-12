"""업로드 이미지 웹용 정규화(HEIC→JPEG, 대용량 리사이즈/재압축)."""
from __future__ import annotations

import logging
import os
import re
from io import BytesIO

logger = logging.getLogger(__name__)

_HEIC_EXTS = (".heic", ".heif")

# 상세·라이트박스 기준 장변. 원본(아이폰 12MP+)을 그대로 두면 수 MB~수십 MB가 되어 로딩이 느리다.
MAX_IMAGE_SIDE = 1920
JPEG_QUALITY = 85
# 이 크기 이상이면 장변이 MAX 이하여도 재압축(품질 통일).
MIN_RECOMPRESS_BYTES = 400_000


def is_heic_name(name: str | None) -> bool:
    n = (name or "").lower().split("?", 1)[0]
    return n.endswith(_HEIC_EXTS)


def _register_heif():
    from pillow_heif import register_heif_opener

    register_heif_opener()


def _safe_jpeg_basename(name: str | None) -> str:
    base = os.path.basename(name or "photo.heic")
    stem = os.path.splitext(base)[0] or "photo"
    stem = re.sub(r"[^\w.\-가-힣]+", "_", stem).strip("._") or "photo"
    return f"{stem}.jpg"


def _to_web_jpeg(im) -> "Image.Image":
    """EXIF 회전 반영 + RGB + 장변 제한."""
    from PIL import ImageOps

    im = ImageOps.exif_transpose(im)
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    longest = max(w, h)
    if longest > MAX_IMAGE_SIDE:
        from PIL import Image

        im = im.copy()
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), resample=Image.Resampling.LANCZOS)
    return im


def _as_jpeg_content(im, src_name: str | None):
    from django.core.files.base import ContentFile

    out = _to_web_jpeg(im)
    buf = BytesIO()
    out.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read(), name=_safe_jpeg_basename(src_name))


def convert_uploaded_heic_to_jpeg(uploaded_file):
    """
    Django UploadedFile / FieldFile → JPEG ContentFile.
    EXIF 회전을 픽셀에 반영한 뒤 웹용 RGB JPEG로 저장한다.
    """
    from PIL import Image

    _register_heif()
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    with Image.open(uploaded_file) as im:
        return _as_jpeg_content(im, getattr(uploaded_file, "name", None) or "photo.heic")


def normalize_uploaded_image(uploaded_file):
    """
    새 업로드 파일을 웹용으로 맞춤.
    - HEIC/HEIF → JPEG
    - 장변 > MAX 또는 용량 ≥ MIN_RECOMPRESS_BYTES → 리사이즈/재압축 JPEG
    - 이미 작으면 원본 그대로 반환
    """
    from PIL import Image

    if not uploaded_file:
        return uploaded_file

    name = getattr(uploaded_file, "name", None) or "photo.jpg"
    if is_heic_name(name):
        return convert_uploaded_heic_to_jpeg(uploaded_file)

    size = getattr(uploaded_file, "size", None)
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        with Image.open(uploaded_file) as im:
            w, h = im.size
            too_large = max(w, h) > MAX_IMAGE_SIDE or (
                size is not None and size >= MIN_RECOMPRESS_BYTES
            )
            if not too_large:
                try:
                    uploaded_file.seek(0)
                except Exception:
                    pass
                return uploaded_file
            return _as_jpeg_content(im, name)
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        raise


def convert_heic_path_to_jpeg(src_path: str, dest_path: str | None = None) -> str:
    """디스크상의 HEIC 파일을 JPEG로 변환. 반환: JPG 경로."""
    from PIL import Image

    if not src_path or not os.path.exists(src_path):
        raise FileNotFoundError(src_path)
    _register_heif()
    if dest_path is None:
        root, _ = os.path.splitext(src_path)
        dest_path = root + ".jpg"

    with Image.open(src_path) as im:
        out = _to_web_jpeg(im)
        out.save(dest_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return dest_path


def recompress_jpeg_path(path: str, max_side: int = MAX_IMAGE_SIDE, quality: int = JPEG_QUALITY) -> bool:
    """이미 JPG인 대용량 파일을 웹용으로 재압축(덮어쓰기). 변경되면 True."""
    from PIL import Image, ImageOps

    if not path or not os.path.exists(path):
        return False
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        w, h = im.size
        before = os.path.getsize(path)
        if max(w, h) > max_side:
            im = im.copy()
            im.thumbnail((max_side, max_side), resample=Image.Resampling.LANCZOS)
        elif before < MIN_RECOMPRESS_BYTES:
            return False
        tmp = path + ".tmp.jpg"
        im.save(tmp, format="JPEG", quality=quality, optimize=True)
    os.replace(tmp, path)
    return True
