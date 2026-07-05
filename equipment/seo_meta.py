"""페이지별 SEO title·description 생성."""
from __future__ import annotations

from equipment.i18n.seo_i18n import (
    CATEGORY_SEO_I18N,
    get_category_type_label,
    get_equipment_seo_phrases,
    get_manufacturer_label,
    normalize_seo_lang,
)
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
    code = normalize_seo_lang(lang)
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


def _equipment_type_label(equipment, lang="ko") -> str:
    fallback = equipment.get_equipment_type_display() or ""
    return get_category_type_label(
        equipment.equipment_type,
        lang,
        fallback_display=fallback,
    )


def _manufacturer_label(equipment, lang="ko") -> str:
    return get_manufacturer_label(equipment.manufacturer, lang)


def _equipment_year_label(equipment, lang="ko") -> str:
    """연식 표기. ko: '2023년식', en: '2023' 등."""
    if not equipment.year_manufactured:
        return ""
    phrases = get_equipment_seo_phrases(lang)
    suffix = phrases.get("year_suffix", "")
    if suffix:
        return f"{equipment.year_manufactured}{suffix}"
    return str(equipment.year_manufactured)


def _equipment_location_label(equipment) -> str:
    location = (equipment.current_location or "").strip()
    if not location and equipment.region_sido:
        location = equipment.region_sido.strip()
        if equipment.region_sigungu:
            location = f"{location} {equipment.region_sigungu}".strip()
    return location


def _name_includes_type(name: str, type_label: str) -> bool:
    if not name or not type_label:
        return False
    return type_label in name


def _build_title_core(name: str, type_label: str, lang: str, phrases: dict) -> str:
    used = phrases["used"]
    sale = phrases["sale"]
    if name and type_label and not _name_includes_type(name, type_label):
        if lang == "ko":
            return f"{name} {used} {type_label} {sale}"
        if lang in ("en", "es", "vi"):
            return f"{used} {name} {type_label} {sale}"
        if lang == "ru":
            return f"{used} {type_label} {name} — {sale}"
        if lang == "ur":
            return f"{used} {name} {type_label} {sale}"
        return f"{used} {name} {type_label} {sale}"
    if name:
        if lang == "ko":
            return f"{name} {used} {sale}"
        return f"{used} {name} {sale}"
    if lang == "ko":
        return f"{used} {type_label} {sale}"
    return f"{used} {type_label} {sale}"


def _build_description_lead(name: str, type_label: str, lang: str, phrases: dict) -> str:
    used = phrases["used"]
    listing = phrases["listing"]
    if name:
        if lang == "ko":
            return f"{name} {used} {type_label} {listing}"
        return f"{name} — {used} {type_label} {listing}"
    if lang == "ko":
        return f"{used} {type_label} {listing}"
    return f"{used} {type_label} {listing}"


def equipment_seo_title(equipment, lang="ko") -> str:
    """제조사·모델명·장비종류·연식 활용, 없는 정보는 자연스럽게 생략."""
    lang = normalize_seo_lang(lang)
    phrases = get_equipment_seo_phrases(lang)
    manufacturer = _manufacturer_label(equipment, lang)
    model = (equipment.model_name or "").strip()
    type_label = _equipment_type_label(equipment, lang)
    name = " ".join(p for p in (manufacturer, model) if p)

    core = _build_title_core(name, type_label, lang, phrases)
    parts = [core]
    year_text = _equipment_year_label(equipment, lang)
    if year_text:
        parts.append(year_text)
    parts.append(phrases["brand_suffix"])
    return " | ".join(parts)


def equipment_seo_description(equipment, lang="ko") -> str:
    lang = normalize_seo_lang(lang)
    phrases = get_equipment_seo_phrases(lang)
    type_label = _equipment_type_label(equipment, lang)
    manufacturer = _manufacturer_label(equipment, lang)
    model = (equipment.model_name or "").strip()
    name = " ".join(p for p in (manufacturer, model) if p)

    lead = _build_description_lead(name, type_label, lang, phrases)

    specs: list[str] = []
    year_text = _equipment_year_label(equipment, lang)
    if year_text:
        specs.append(year_text)
    hours = equipment.operating_hours
    if hours:
        try:
            hours_val = int(hours)
            specs.append(
                f"{phrases['hours_label']} {hours_val:,}{phrases['hours_unit']}"
            )
        except (TypeError, ValueError):
            pass
    location = _equipment_location_label(equipment)
    if location:
        specs.append(location)

    if specs:
        spec_prefix = phrases["spec_bridge"].format(specs=", ".join(specs))
    else:
        spec_prefix = ""

    if equipment.is_sold:
        mid = f"{spec_prefix}{phrases['sold_notice']}"
    else:
        mid = f"{spec_prefix}{phrases['cta']}"

    tail = phrases["tail_template"].format(used=phrases["used"], type=type_label)
    text = f"{lead} {mid} {tail}"
    if len(text) > 160:
        text = text[:157].rstrip(" .,·") + "…"
    return text
