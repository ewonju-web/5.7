# -*- coding: utf-8 -*-
"""
미니 모델명인데 weight_class가 02급/06급으로 잘못된 매물을 EXC_CR_LE_3_5로 보정.

MINI_MODELS 접두어 매칭 사용.
- EXC_CR_LE_6_5: ECR88/SK75/R80 제외
- EXC_CR_LE_16: 접두어가 미니(LE_3_5)인 경우만

사용법:
  python manage.py fix_grade02_to_mini_weight --dry-run
  python manage.py fix_grade02_to_mini_weight --commit
"""
from django.core.management.base import BaseCommand

from equipment.excavator_model_grades import (
    EXC_CR_LE_3_5,
    EXC_CR_LE_6_5,
    EXC_CR_LE_16,
    should_demote_grade02_to_mini,
    should_demote_grade16_to_mini,
)
from equipment.models import Equipment

TARGET_WEIGHT = EXC_CR_LE_3_5

SOURCE_RULES = (
    (EXC_CR_LE_6_5, should_demote_grade02_to_mini, "ECR88/SK75/R80 제외"),
    (EXC_CR_LE_16, should_demote_grade16_to_mini, "미니 접두어만"),
)


class Command(BaseCommand):
    help = "02급/06급으로 잘못 분류된 미니 모델명 매물을 EXC_CR_LE_3_5로 보정"

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--commit", action="store_true")

    def handle(self, *args, **options):
        commit = options["commit"]
        all_rows: list[tuple[str, object]] = []

        for source_weight, predicate, note in SOURCE_RULES:
            candidates = (
                Equipment.objects.visible()
                .filter(equipment_type="excavator", weight_class=source_weight)
                .only("id", "model_name", "sub_type", "weight_class")
                .order_by("model_name", "id")
            )
            rows = [eq for eq in candidates if predicate(eq.model_name or "")]
            self.stdout.write(
                f"\n[{source_weight} → {TARGET_WEIGHT}] ({note}) {len(rows)}건"
            )
            for eq in rows:
                self.stdout.write(
                    f"  id={eq.id} sub={eq.sub_type!r} model={eq.model_name!r}"
                )
                all_rows.append((source_weight, eq))

        self.stdout.write(f"\n총 {len(all_rows)}건")

        if commit:
            updated = 0
            for _src, eq in all_rows:
                eq.weight_class = TARGET_WEIGHT
                eq.save(update_fields=["weight_class"])
                updated += 1
            self.stdout.write(self.style.SUCCESS(f"\n저장 완료: {updated}건"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n드라이런 종료 (변경 {len(all_rows)}건 예정). "
                    "적용: python manage.py fix_grade02_to_mini_weight --commit"
                )
            )
