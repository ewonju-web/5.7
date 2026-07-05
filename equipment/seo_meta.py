"""페이지별 SEO title·description 생성."""
from __future__ import annotations

from equipment.i18n.seo_i18n import CATEGORY_SEO_I18N
from equipment.templatetags.i18n_extras import SUPPORTED_LANGS


# Deprecated: Korean-only legacy. Use CATEGORY_SEO_I18N via get_category_seo() instead.
# 카테고리(기종) 목록 페이지 SEO. 키는 Equipment.equipment_type(EquipmentType) 코드.
# 과장 없이 실제 제공 기능(실시간 등록 매물·시세 비교·직거래)을 반영한 문구.
CATEGORY_SEO = {
    "excavator": (
        "중고 굴삭기 매물·실시간 시세 | 굴삭기나라",
        "전국 중고 굴삭기 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 미니·중형·대형 굴삭기를 연식·가동시간·지역별로 비교할 수 있습니다 — 굴삭기나라.",
    ),
    "forklift": (
        "중고 지게차 매물·실시간 시세 | 굴삭기나라",
        "전국 중고 지게차 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 디젤·전동 지게차를 톤수·연식·지역별로 비교할 수 있습니다 — 굴삭기나라.",
    ),
    "dump": (
        "중고 덤프트럭 매물·실시간 시세 | 굴삭기나라",
        "전국 중고 덤프트럭 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 축수·연식·지역별로 매물을 비교할 수 있습니다 — 굴삭기나라.",
    ),
    "loader": (
        "중고 스키로더·로더 매물·실시간 시세 | 굴삭기나라",
        "전국 중고 스키로더·로더 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 연식·가동시간·지역별로 비교할 수 있습니다 — 굴삭기나라.",
    ),
    "crane": (
        "중고 크레인 매물·실시간 시세 | 굴삭기나라",
        "전국 중고 크레인 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 톤수·연식·지역별로 매물을 비교할 수 있습니다 — 굴삭기나라.",
    ),
    "attachment": (
        "중고 어태치먼트 매물·실시간 시세 | 굴삭기나라",
        "브레이커·집게·버킷 등 중고 어태치먼트 매물을 실시간 등록 시세와 함께 직거래로 확인하세요 — 굴삭기나라.",
    ),
    "other": (
        "중고 건설기계·중장비 매물·실시간 시세 | 굴삭기나라",
        "그 밖의 중고 건설기계·중장비 매물을 실시간 등록 시세와 함께 직거래로 확인하세요. 종류·연식·지역별로 비교할 수 있습니다 — 굴삭기나라.",
    ),
}


def get_category_seo(category_key, lang="ko"):
    """카테고리·언어별 (title, description) 반환. 없으면 None."""
    key = (category_key or "").strip()
    if not key or key not in CATEGORY_SEO_I18N:
        return None
    code = (lang or "ko").strip().lower()
    if code not in SUPPORTED_LANGS:
        code = "ko"
    cat = CATEGORY_SEO_I18N[key]
    entry = cat.get(code) or cat.get("ko")
    if not entry:
        return None
    return entry["title"], entry["description"]


def category_seo(filter_category, lang="ko"):
    """카테고리 코드에 맞는 (title, description) 반환. 없으면 None(홈/전체 = 기본 문구 유지).

    Prefer get_category_seo(). CATEGORY_SEO dict below is deprecated (Korean-only legacy).
    """
    result = get_category_seo(filter_category, lang)
    if result:
        return result
    # Deprecated fallback — kept for backward compatibility if i18n data is missing.
    return CATEGORY_SEO.get((filter_category or "").strip())


def _format_price_manwon(listing_price) -> str:
    if listing_price is None:
        return "가격 문의"
    try:
        val = int(listing_price)
    except (TypeError, ValueError):
        return "가격 문의"
    if val <= 0:
        return "가격 문의"
    return f"{val:,}만원"


def _equipment_type_label(equipment) -> str:
    return equipment.get_equipment_type_display() or "중장비"


def _equipment_year_label(equipment) -> str:
    """연식 표기: '2023년식' (월은 데이터상 기본값 비중이 커 연도만 사용)."""
    if not equipment.year_manufactured:
        return ""
    return f"{equipment.year_manufactured}년식"


def _equipment_location_label(equipment) -> str:
    location = (equipment.current_location or "").strip()
    if not location and equipment.region_sido:
        location = equipment.region_sido.strip()
        if equipment.region_sigungu:
            location = f"{location} {equipment.region_sigungu}".strip()
    return location


def equipment_seo_title(equipment) -> str:
    """예: 두산 DX55 중고 굴삭기 매매 | 2023년식 | 굴삭기나라
    (제조사·모델명·장비종류·연식 활용, 없는 정보는 자연스럽게 생략)"""
    manufacturer = (equipment.manufacturer or "").strip()
    model = (equipment.model_name or "").strip()
    type_label = _equipment_type_label(equipment)
    name = " ".join(p for p in (manufacturer, model) if p)

    if name and type_label and type_label not in name:
        core = f"{name} 중고 {type_label} 매매"
    elif name:
        core = f"{name} 중고 매매"
    else:
        core = f"중고 {type_label} 매매"

    parts = [core]
    year_text = _equipment_year_label(equipment)
    if year_text:
        parts.append(year_text)
    parts.append("굴삭기나라")
    return " | ".join(parts)


def equipment_seo_description(equipment) -> str:
    """예: 두산 DX55 중고 굴삭기 매물입니다. 2023년식, 판매가격 및 상세사진을 확인하고
    판매자에게 직접 문의하세요. 굴삭기나라에서 다양한 중고 굴삭기 매물을 만나보세요."""
    type_label = _equipment_type_label(equipment)
    manufacturer = (equipment.manufacturer or "").strip()
    model = (equipment.model_name or "").strip()
    name = " ".join(p for p in (manufacturer, model) if p)

    lead = f"{name} 중고 {type_label} 매물입니다." if name else f"중고 {type_label} 매물입니다."

    # 연식·가동시간·지역을 자연스러운 한 구절로 묶는다.
    specs: list[str] = []
    year_text = _equipment_year_label(equipment)
    if year_text:
        specs.append(year_text)
    hours = equipment.operating_hours
    if hours:
        try:
            specs.append(f"가동시간 {int(hours):,}시간")
        except (TypeError, ValueError):
            pass
    location = _equipment_location_label(equipment)
    if location:
        specs.append(location)
    spec_prefix = (", ".join(specs) + " 매물로, ") if specs else ""

    if equipment.is_sold:
        mid = f"{spec_prefix}현재 판매가 완료된 매물입니다."
    else:
        mid = f"{spec_prefix}판매가격과 상세사진을 확인하고 판매자에게 직접 문의하세요."

    tail = f"굴삭기나라에서 다양한 중고 {type_label} 매물을 만나보세요."
    text = f"{lead} {mid} {tail}"
    if len(text) > 160:
        text = text[:157].rstrip(" .,·") + "…"
    return text
