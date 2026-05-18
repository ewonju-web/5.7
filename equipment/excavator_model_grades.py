# -*- coding: utf-8 -*-
"""굴삭기 model_name 접두어 → weight_class (모델 번호 기준, 톤수 숫자 추출과 별도)."""
from __future__ import annotations

import re

EXC_CR_LE_3_5 = "EXC_CR_LE_3_5"
EXC_CR_LE_6_5 = "EXC_CR_LE_6_5"
EXC_CR_LE_16 = "EXC_CR_LE_16"
EXC_CR_EQ_20 = "EXC_CR_EQ_20"
EXC_CR_GE_30 = "EXC_CR_GE_30"

MINI_MODELS = [
    "DX15", "DX17", "DX20", "DX30", "DX35", "DX55",
    "EC15", "EC18", "EC20", "EC35", "EC55", "EC60",
    "ECR15", "ECR18", "ECR20", "ECR35",
    "HX35", "HX55", "HX60", "HD35",
    "SK017", "SK023", "SK10", "SK17", "SK23", "SK30",
    "U17", "U20", "U35", "E08", "ZX17", "ZX30",
    # 얀마·히타치·보바드 등 미니
    "VIO008", "VIO015", "VIO17", "VIO23", "VIO27", "VIO30",
    "ZX10", "ZX20",
    "U-008", "U-20", "U-30", "U30",
    "R25", "R30", "R55",
    "S015", "SL015", "SV08",
    "VO17",
    "KX57", "KX60", "DX60", "DX65", "HW60", "HW65",
    "VIO55", "VIO75", "SK55", "SL55", "S55", "ROBEX55",
    "솔라55", "솔라030", "HE50", "한라50", "MX3",
    "ECR58", "EW60", "HX65",
]

# fix_grade02_to_mini_weight 에서 02급 유지 (건드리지 않음)
PROTECTED_GRADE02_PREFIXES = ["ECR88", "SK75", "R80"]

GRADE02_MODELS = ["ECR88", "SK75", "DX75", "PC78", "ZX75", "HX75"]
GRADE06_MODELS = ["DX140", "DX150", "EC140", "EC160", "HX145", "SK140", "PC130"]
GRADE08_MODELS = [
    "DX210", "DX220", "DX235", "EC220", "EC250", "HX220", "HX230",
    "SK210", "SK230", "PC200", "PC210",
]
GRADE10_MODELS = [
    "DX240", "DX260", "DX300", "DX340", "DX350", "EC350", "EC360", "EC380",
    "EC460", "HX320", "HX380", "HX480", "HX520", "SK300", "SK350",
    "CAT330", "CAT336", "PC300",
]

_PREFIX_GRADE_CACHE: list[tuple[str, str]] | None = None


def _build_prefix_grade() -> list[tuple[str, str]]:
    global _PREFIX_GRADE_CACHE
    if _PREFIX_GRADE_CACHE is not None:
        return _PREFIX_GRADE_CACHE
    items: list[tuple[str, str]] = []
    for p in MINI_MODELS:
        items.append((p.upper(), EXC_CR_LE_3_5))
    for p in GRADE02_MODELS:
        items.append((p.upper(), EXC_CR_LE_6_5))
    for p in GRADE06_MODELS:
        items.append((p.upper(), EXC_CR_LE_16))
    for p in GRADE08_MODELS:
        items.append((p.upper(), EXC_CR_EQ_20))
    for p in GRADE10_MODELS:
        items.append((p.upper(), EXC_CR_GE_30))
    items.sort(key=lambda x: len(x[0]), reverse=True)
    _PREFIX_GRADE_CACHE = items
    return items


def compact_model_name(model_name: str) -> str:
    return re.sub(r"\s+", "", (model_name or "").strip().upper())


def crawler_weight_by_model_prefix(model_name: str) -> str | None:
    """모델 접두어 매칭 시 weight_class, 없으면 None."""
    compact = compact_model_name(model_name)
    if not compact:
        return None
    for prefix, grade in _build_prefix_grade():
        if compact.startswith(prefix):
            return grade
    return None


def is_protected_grade02_model(model_name: str) -> bool:
    """02급 유지 대상 (미니 보정 제외)."""
    compact = compact_model_name(model_name)
    if not compact:
        return False
    return any(compact.startswith(p.upper()) for p in PROTECTED_GRADE02_PREFIXES)


def should_demote_grade02_to_mini(model_name: str) -> bool:
    """02급 → 미니(EXC_CR_LE_3_5) 보정 대상 여부."""
    if is_protected_grade02_model(model_name):
        return False
    return crawler_weight_by_model_prefix(model_name) == EXC_CR_LE_3_5


def should_demote_grade16_to_mini(model_name: str) -> bool:
    """06급(LE_16) → 미니(EXC_CR_LE_3_5) 보정 대상 여부."""
    return crawler_weight_by_model_prefix(model_name) == EXC_CR_LE_3_5
