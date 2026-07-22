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
    # 실제 미니·소형 (~3.5톤 이하). 5~6톤급(DX55 등)은 GRADE02로 분리.
    "DX15", "DX17", "DX20", "DX30", "DX35",
    "EC15", "EC18", "EC20", "EC35",
    "ECR15", "ECR18", "ECR20", "ECR35",
    "HX35", "HD35",
    "SK017", "SK023", "SK10", "SK17", "SK23", "SK30",
    "U17", "U20", "U35", "E08", "ZX17", "ZX30",
    "VIO008", "VIO015", "VIO17", "VIO23", "VIO27", "VIO30", "VIO35",
    "ZX10", "ZX20",
    "U-008", "U-20", "U-30", "U30",
    "R25", "R30",
    "S015", "SL015", "SV08",
    "VO17",
    "솔라030", "MX3",
]

# fix_grade02_to_mini_weight 에서 02급 유지 (건드리지 않음)
PROTECTED_GRADE02_PREFIXES = ["ECR88", "SK75", "R80"]

GRADE02_MODELS = [
    "ECR88", "SK75", "DX75", "PC78", "ZX75", "HX75",
    # 5~6톤급 — 검색 UI「미니 1~3t」와 분리
    "DX55", "DX60", "DX65",
    "EC55", "EC60", "ECR58",
    "HX55", "HX60", "HX65",
    "R55", "KX57", "KX60",
    "VIO55", "VIO75", "SK55", "SL55", "S55", "ROBEX55",
    "솔라55", "HE50", "한라50",
]

# 휠식(타이어) 시리즈 — 크롤러 검색에서 제외·보정용
_WHEELED_SERIES_RE = re.compile(r"(?:^|[^A-Z0-9])(EW|HW)\s*(\d{2,3})", re.IGNORECASE)
_WHEELED_W_SUFFIX_RE = re.compile(
    r"(?:DX|EC|HX|SK|PC|ZX)\s*\d{2,3}\s*W(?:\b|-)",
    re.IGNORECASE,
)
_WHEELED_MARKER_RE = re.compile(r"휠|타이어식|wheeled", re.IGNORECASE)


def is_wheeled_excavator_model(model_name: str) -> bool:
    """모델명으로 타이어식(휠) 굴삭기 여부 판별."""
    name = (model_name or "").strip()
    if not name:
        return False
    if _WHEELED_MARKER_RE.search(name):
        return True
    if _WHEELED_SERIES_RE.search(name):
        return True
    if _WHEELED_W_SUFFIX_RE.search(name):
        return True
    return False


def tire_weight_from_wheeled_model(model_name: str) -> str | None:
    """휠식 모델번호 → 타이어 중량 코드."""
    name = (model_name or "").strip()
    m = _WHEELED_SERIES_RE.search(name)
    ton = None
    if m:
        try:
            ton = int(m.group(2))
        except ValueError:
            ton = None
    if ton is None:
        m2 = re.search(r"(?:DX|EC|HX|SK|PC|ZX)\s*(\d{2,3})\s*W", name, re.I)
        if m2:
            try:
                ton = int(m2.group(1))
            except ValueError:
                ton = None
    if ton is None:
        return None
    if ton <= 70:
        return "EXC_TIRE_LE_6"
    if ton <= 170:
        return "EXC_TIRE_LE_17"
    return "EXC_TIRE_LE_21"


GRADE06_MODELS = ["DX140", "DX150", "EC140", "EC160", "HX145", "SK140", "PC130", "EW140", "EW145", "HW140", "HW155"]
GRADE08_MODELS = [
    "DX210", "DX220", "DX235", "EC220", "EC250", "HX220", "HX230",
    "SK210", "SK230", "PC200", "PC210", "EW205",
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
    # 제조사명 등이 앞에 붙은 경우 (예: 두산DX55MT)
    for prefix, grade in _build_prefix_grade():
        if len(prefix) < 3:
            continue
        if re.search(rf"(?:^|[^A-Z0-9]){re.escape(prefix)}", compact):
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
