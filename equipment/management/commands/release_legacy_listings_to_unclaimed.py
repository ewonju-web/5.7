"""legacy_ 계정에 묶인 이관 매물을 미연결(unclaimed_phone_norm) 상태로 전환."""

from django.core.management.base import BaseCommand
from django.db import transaction

from equipment.claim_utils import normalize_phone_digits
from equipment.models import Equipment, Profile


class Command(BaseCommand):
    help = (
        "legacy_ 작성자에게 묶인 매물을 author=null + unclaimed_phone_norm 으로 바꿉니다. "
        "신규 가입 후 내 매물 찾기로 연결할 수 있게 합니다."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 저장 없이 대상 건수만 출력",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="최대 처리 건수 (0=전체)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"] or None

        qs = (
            Equipment.objects.filter(author__username__startswith="legacy_")
            .select_related("author")
            .order_by("pk")
        )
        if limit:
            qs = qs[:limit]

        converted = 0
        skipped_no_phone = 0

        with transaction.atomic():
            for eq in qs:
                try:
                    profile = Profile.objects.get(user_id=eq.author_id)
                    phone_norm = normalize_phone_digits(profile.phone)
                except Profile.DoesNotExist:
                    phone_norm = ""

                if not phone_norm:
                    if eq.unclaimed_phone_norm:
                        phone_norm = normalize_phone_digits(eq.unclaimed_phone_norm)
                if not phone_norm:
                    skipped_no_phone += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"SKIP equipment={eq.pk} legacy_author={eq.author.username} (전화번호 없음)"
                        )
                    )
                    continue

                if dry_run:
                    converted += 1
                    continue

                eq.author = None
                eq.unclaimed_phone_norm = phone_norm
                eq.save(update_fields=["author", "unclaimed_phone_norm"])
                converted += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = "(dry-run) " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}전환 {converted}건, 전화번호 없어 스킵 {skipped_no_phone}건"
            )
        )
