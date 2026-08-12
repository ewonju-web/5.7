"""기존 EquipmentImage 중 과대 파일을 웹용으로 재압축.

화면 표시 크기는 그대로이고, 장변≤1920·품질85로 용량만 줄인다.
워터마크는 이미 픽셀에 박혀 있으므로 재적용하지 않는다.
"""
from __future__ import annotations

import os
import sys
import time

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from equipment.heic_utils import MIN_RECOMPRESS_BYTES, recompress_jpeg_path  # noqa: E402
from equipment.models import EquipmentImage  # noqa: E402


def main() -> None:
    log_path = os.environ.get(
        "RECOMPRESS_LOG",
        "/srv/excavator/logs/recompress_equipment_images.log",
    )
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(msg: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    ids = list(EquipmentImage.objects.order_by("id").values_list("id", flat=True))
    total = len(ids)
    changed = 0
    skipped = 0
    errors = 0
    saved_bytes = 0
    t0 = time.time()
    log(f"start total={total} min_bytes={MIN_RECOMPRESS_BYTES}")

    for i, pk in enumerate(ids, 1):
        try:
            img = EquipmentImage.objects.only("id", "image").get(pk=pk)
            path = img.image.path
        except Exception as e:
            errors += 1
            if errors <= 20:
                log(f"error pk={pk} resolve {e}")
            continue
        if not path or not os.path.exists(path):
            skipped += 1
            continue
        before = os.path.getsize(path)
        if before < MIN_RECOMPRESS_BYTES:
            skipped += 1
            continue
        try:
            ok = recompress_jpeg_path(path)
        except Exception as e:
            errors += 1
            if errors <= 50:
                log(f"error pk={pk} recompress {e}")
            continue
        if not ok:
            skipped += 1
            continue
        after = os.path.getsize(path)
        changed += 1
        saved_bytes += max(0, before - after)
        if changed <= 30 or changed % 200 == 0 or i % 1000 == 0:
            log(
                f"progress i={i}/{total} changed={changed} "
                f"pk={pk} {before/1024:.0f}KB->{after/1024:.0f}KB "
                f"saved_MB={saved_bytes/1024/1024:.1f} "
                f"elapsed_s={time.time()-t0:.0f}"
            )

    log(
        f"done changed={changed} skipped={skipped} errors={errors} "
        f"saved_MB={saved_bytes/1024/1024:.1f} elapsed_s={time.time()-t0:.0f}"
    )


if __name__ == "__main__":
    main()
