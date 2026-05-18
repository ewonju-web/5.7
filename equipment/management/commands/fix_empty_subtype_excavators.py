# -*- coding: utf-8 -*-
"""
sub_type / weight_class 가 비어 있는 visible 굴삭기를 model_name 패턴으로 분류·보정.

사용법:
  python manage.py fix_empty_subtype_excavators --dry-run
  python manage.py fix_empty_subtype_excavators --commit
"""
from __future__ import annotations

import re
from collections import Counter

from django.core.management.base import BaseCommand

from equipment.excavator_model_grades import crawler_weight_by_model_prefix
from equipment.models import Equipment

EXC_TIRE = "EXC_TIRE"
EXC_CRAWLER = "EXC_CRAWLER"
EXC_ATTACHMENT = "EXC_ATTACHMENT"

EXC_CR_LE_3_5 = "EXC_CR_LE_3_5"
EXC_CR_LE_6_5 = "EXC_CR_LE_6_5"
EXC_CR_LE_16 = "EXC_CR_LE_16"
EXC_CR_EQ_20 = "EXC_CR_EQ_20"
EXC_CR_GE_30 = "EXC_CR_GE_30"

EXC_TIRE_LE_6 = "EXC_TIRE_LE_6"
EXC_TIRE_LE_17 = "EXC_TIRE_LE_17"
EXC_TIRE_LE_21 = "EXC_TIRE_LE_21"

_TIRE_MARKERS = ("회링", "휠", "wheeled", "wa")
_TIRE_W_RE = re.compile(r"W", re.IGNORECASE)

_ATTACH_MARKERS = (
    "버켓",
    "버킷",
    "집게",
    "브레이커",
    "어태치",
    "틸트",
    "로테이터",
    "뿌레카",
    "브레카",
    "지게발",
)

# SK008, U-008, E08 또는 모델명에 008 포함
_MINI_008_RE = re.compile(r"(?:SK|U-?)008\b|E08", re.IGNORECASE)
_CONTAINS_008_RE = re.compile(r"008")

# MX3, MX3W, MX3A 등
_MX3_START_RE = re.compile(r"^MX3", re.IGNORECASE)

# 제조사 접두 + 톤수 숫자 (긴 접두 우선: ECR before EC)
_TON_PREFIX_RE = re.compile(
    r"(?:ECR|DX|EC|SK|HX|KX|EW|HW|ZX|CAT|R)(\d{2,3})",
    re.IGNORECASE,
)


def _is_tire_model(model_name: str) -> bool:
    lower = model_name.lower()
    if any(m in model_name or m in lower for m in _TIRE_MARKERS):
        return True
    if _TIRE_W_RE.search(model_name):
        return True
    return False


def _is_attachment_model(model_name: str) -> bool:
    return any(m in model_name for m in _ATTACH_MARKERS)


def _compact_name(model_name: str) -> str:
    return re.sub(r"\s+", "", (model_name or "").strip().upper())


def _is_mini_008_model(model_name: str) -> bool:
    compact = _compact_name(model_name)
    if not compact:
        return False
    if _MINI_008_RE.search(compact):
        return True
    return bool(_CONTAINS_008_RE.search(compact))


def _is_mx3_model(model_name: str) -> bool:
    return bool(_MX3_START_RE.match(_compact_name(model_name)))


def extract_small_tonnage(model_name: str) -> int | None:
    """17 미만 톤수(06, 08 등) 추출 — 타이어 키워드 없을 때 미니 처리용."""
    compact = _compact_name(model_name)
    if not compact:
        return None
    found: list[int] = []
    for m in re.finditer(r"(?<!\d)(\d{2,3})(?!\d)", compact):
        n = int(m.group(1))
        if n < 17:
            found.append(n)
    for m in re.finditer(r"(?<!\d)(\d{1,2})[Ww](?![A-Za-z])", compact):
        n = int(m.group(1))
        if n < 17:
            found.append(n)
    return min(found) if found else None


def extract_tonnage(model_name: str) -> int | None:
    """모델명에서 굴삭기 톤급 추정 숫자(17~999)를 추출."""
    if not (model_name or "").strip():
        return None
    compact = re.sub(r"\s+", "", model_name.upper())
    nums: list[int] = []
    for m in _TON_PREFIX_RE.finditer(compact):
        n = int(m.group(1))
        if 10 <= n <= 999:
            nums.append(n)
    if nums:
        return max(nums)
    # 접두 없는 2~3자리 숫자 fallback (예: 06w 틸트로테이터)
    for m in re.finditer(r"(?<!\d)(\d{2,3})(?!\d)", compact):
        n = int(m.group(1))
        if 17 <= n <= 999:
            nums.append(n)
    return max(nums) if nums else None


def crawler_weight_class(ton: int) -> str | None:
    if ton < 17:
        return EXC_CR_LE_3_5
    if ton <= 65:
        return EXC_CR_LE_3_5
    if ton <= 99:
        return EXC_CR_LE_6_5
    if ton <= 199:
        return EXC_CR_LE_16
    if ton <= 249:
        return EXC_CR_EQ_20
    if ton >= 250:
        return EXC_CR_GE_30
    return None


def tire_weight_class(ton: int) -> str | None:
    if ton <= 65:
        return EXC_TIRE_LE_6
    if ton <= 99:
        return EXC_TIRE_LE_6
    if ton <= 199:
        return EXC_TIRE_LE_17
    if ton >= 200:
        return EXC_TIRE_LE_21
    return None


def classify(model_name: str) -> tuple[str, str] | None:
    """
    (sub_type, weight_class) 반환.
    분류 불가 시 None (DB 유지).
    """
    name = (model_name or "").strip()
    if not name:
        return None

    if _is_attachment_model(name):
        return EXC_ATTACHMENT, ""

    if _is_mx3_model(name):
        return EXC_CRAWLER, EXC_CR_LE_3_5

    if _is_mini_008_model(name):
        return EXC_CRAWLER, EXC_CR_LE_3_5

    if _is_tire_model(name):
        ton = extract_tonnage(name)
        if ton is None:
            return None
        wc = tire_weight_class(ton)
        if wc is None:
            return None
        return EXC_TIRE, wc

    wc = crawler_weight_by_model_prefix(name)
    if wc:
        return EXC_CRAWLER, wc

    ton = extract_tonnage(name)
    if ton is not None:
        wc = crawler_weight_class(ton)
        if wc is None:
            return None
        return EXC_CRAWLER, wc

    if not _is_tire_model(name):
        if extract_small_tonnage(name) is not None:
            return EXC_CRAWLER, EXC_CR_LE_3_5

    return None


def _label(sub_type: str, weight_class: str) -> str:
    wc = weight_class or "''"
    return f"{sub_type} / {wc}"


class Command(BaseCommand):
    help = "sub_type·weight_class 빈 visible 굴삭기를 model_name 패턴으로 분류·보정"

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument(
            "--dry-run",
            action="store_true",
            help="저장하지 않고 분류 결과만 출력",
        )
        mode.add_argument(
            "--commit",
            action="store_true",
            help="분류 결과를 DB에 저장",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        qs = Equipment.objects.visible().filter(
            equipment_type="excavator",
            sub_type="",
            weight_class="",
        )
        rows = list(qs.only("id", "model_name", "sub_type", "weight_class").order_by("id"))
        total = len(rows)

        counts: Counter[str] = Counter()
        unclassified: list[Equipment] = []
        to_update: list[tuple[Equipment, str, str]] = []

        for eq in rows:
            result = classify(eq.model_name or "")
            if result is None:
                counts["UNCLASSIFIED"] += 1
                unclassified.append(eq)
                continue
            sub_type, weight_class = result
            key = _label(sub_type, weight_class)
            counts[key] += 1
            to_update.append((eq, sub_type, weight_class))

        self.stdout.write(f"총 {total}건 분류 결과:")
        order = [
            _label(EXC_CRAWLER, EXC_CR_LE_3_5),
            _label(EXC_CRAWLER, EXC_CR_LE_6_5),
            _label(EXC_CRAWLER, EXC_CR_LE_16),
            _label(EXC_CRAWLER, EXC_CR_EQ_20),
            _label(EXC_CRAWLER, EXC_CR_GE_30),
            _label(EXC_TIRE, EXC_TIRE_LE_6),
            _label(EXC_TIRE, EXC_TIRE_LE_17),
            _label(EXC_TIRE, EXC_TIRE_LE_21),
            _label(EXC_ATTACHMENT, ""),
        ]
        for key in order:
            n = counts.get(key, 0)
            if n:
                self.stdout.write(f"  {key} : {n}건")
        extra_keys = sorted(k for k in counts if k not in order and k != "UNCLASSIFIED")
        for key in extra_keys:
            self.stdout.write(f"  {key} : {counts[key]}건")
        self.stdout.write(f"  분류불가 (그대로 유지)       : {counts.get('UNCLASSIFIED', 0)}건")

        if unclassified:
            self.stdout.write("\n분류불가 샘플:")
            for eq in unclassified[:20]:
                self.stdout.write(f"  id={eq.id} model={eq.model_name!r}")

        if commit:
            updated = 0
            for eq, sub_type, weight_class in to_update:
                eq.sub_type = sub_type
                eq.weight_class = weight_class
                eq.save(update_fields=["sub_type", "weight_class"])
                updated += 1
            self.stdout.write(self.style.SUCCESS(f"\n저장 완료: {updated}건"))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n드라이런 종료 (변경 {len(to_update)}건 예정). "
                    "적용: python manage.py fix_empty_subtype_excavators --commit"
                )
            )
