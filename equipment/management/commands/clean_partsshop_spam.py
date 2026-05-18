# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from equipment.models import PartsShop
from equipment.partsshop_validation import is_partsshop_spam


class Command(BaseCommand):
    help = "SQL 인젝션·스캐너로 오염된 PartsShop 레코드를 삭제합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="삭제 대상만 출력하고 실제 삭제는 하지 않습니다.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        spam_ids = [shop.pk for shop in PartsShop.objects.all() if is_partsshop_spam(shop)]
        total = PartsShop.objects.count()

        if dry_run:
            self.stdout.write(f"삭제 예정: {len(spam_ids)}건 / 전체 {total}건")
            for pk in spam_ids[:10]:
                shop = PartsShop.objects.get(pk=pk)
                self.stdout.write(f"  - [{pk}] {shop.name!r} / {shop.region!r}")
            if len(spam_ids) > 10:
                self.stdout.write(f"  ... 외 {len(spam_ids) - 10}건")
            return

        deleted, _ = PartsShop.objects.filter(pk__in=spam_ids).delete()
        remaining = PartsShop.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"스팸 삭제 완료: {deleted}건 삭제, 남은 레코드 {remaining}건 (이전 {total}건)"
            )
        )
