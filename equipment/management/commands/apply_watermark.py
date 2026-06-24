"""기존 매물 이미지에 워터마크를 일괄 적용한다.

사용 예:
    python manage.py apply_watermark            # 아직 적용 안 된 이미지에만 적용
    python manage.py apply_watermark --all      # watermarked 플래그 무시하고 전체 재시도
    python manage.py apply_watermark --limit 100
    python manage.py apply_watermark --dry-run  # 대상만 출력

라이브 서버(gunicorn)가 같은 SQLite에 동시에 쓰므로, DB 잠금 충돌을 피하기 위해
  - busy_timeout 을 늘리고,
  - 플래그 갱신은 배치로 모아서 처리하며,
  - "database is locked" 발생 시 재시도한다.
"""
import os
import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, connection

from equipment.models import EquipmentImage
from equipment.watermark import apply_watermark


def _set_busy_timeout(ms=60000):
    try:
        with connection.cursor() as cur:
            cur.execute(f"PRAGMA busy_timeout={int(ms)};")
    except Exception:
        pass


def _flush_flags(pks, retries=8):
    """주어진 pk들의 watermarked=True 를 잠금 재시도와 함께 일괄 갱신."""
    if not pks:
        return
    delay = 0.5
    for attempt in range(retries):
        try:
            EquipmentImage.objects.filter(pk__in=pks).update(watermarked=True)
            return
        except OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 10)
                continue
            raise


class Command(BaseCommand):
    help = "기존 매물 이미지에 워터마크를 일괄 삽입한다."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true",
                            help="watermarked 플래그와 무관하게 전체 이미지를 대상으로 한다.")
        parser.add_argument("--limit", type=int, default=0,
                            help="처리할 최대 개수(0=무제한).")
        parser.add_argument("--batch", type=int, default=200,
                            help="플래그를 한 번에 갱신하는 배치 크기.")
        parser.add_argument("--dry-run", action="store_true",
                            help="실제로 적용하지 않고 대상 개수만 출력한다.")

    def handle(self, *args, **options):
        _set_busy_timeout(60000)

        qs = EquipmentImage.objects.all().order_by("pk")
        if not options["all"]:
            qs = qs.filter(watermarked=False)
        if options["limit"] and options["limit"] > 0:
            qs = qs[: options["limit"]]

        # 파일 처리 중 읽기 트랜잭션을 오래 잡지 않도록 대상 목록을 먼저 메모리로 가져온다.
        rows = list(qs.values_list("pk", "image"))
        total = len(rows)
        self.stdout.write(f"대상 이미지: {total}개")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry-run: 실제 적용하지 않음"))
            return

        batch = max(1, options["batch"])
        applied = 0
        failed = 0
        skipped = 0
        pending = []

        from django.conf import settings
        media_root = str(settings.MEDIA_ROOT)

        for pk, image_name in rows:
            if not image_name:
                skipped += 1
                continue
            path = os.path.join(media_root, image_name)
            if not os.path.exists(path):
                skipped += 1
                continue
            try:
                ok = apply_watermark(path)
            except Exception:
                ok = False
            if ok:
                pending.append(pk)
                applied += 1
            else:
                failed += 1

            if len(pending) >= batch:
                _flush_flags(pending)
                pending = []
                self.stdout.write(f"  진행: 적용 {applied} / 실패 {failed} / 건너뜀 {skipped} (총 {total})")

        _flush_flags(pending)
        self.stdout.write(self.style.SUCCESS(
            f"완료 — 적용 {applied}개, 실패 {failed}개, 건너뜀 {skipped}개"
        ))
