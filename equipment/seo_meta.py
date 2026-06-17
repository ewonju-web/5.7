"""페이지별 SEO title·description 생성."""
from __future__ import annotations


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


def equipment_seo_title(equipment) -> str:
    """예: 구보다 U17저가동 굴삭기 매물 - 1,400만원 | 굴삭기나라"""
    manufacturer = (equipment.manufacturer or "").strip()
    model = (equipment.model_name or "").strip()
    type_label = _equipment_type_label(equipment)
    price = _format_price_manwon(equipment.listing_price)

    name_parts = [p for p in (manufacturer, model) if p]
    if name_parts:
        name = " ".join(name_parts)
        if type_label and type_label not in name:
            headline = f"{name} {type_label} 매물 - {price}"
        else:
            headline = f"{name} 매물 - {price}"
    else:
        headline = f"{type_label} 매물 - {price}"

    return f"{headline} | 굴삭기나라"


def equipment_seo_description(equipment) -> str:
    type_label = _equipment_type_label(equipment)
    manufacturer = (equipment.manufacturer or "").strip()
    model = (equipment.model_name or "").strip()
    price = _format_price_manwon(equipment.listing_price)

    name_parts = [p for p in (manufacturer, model) if p]
    if name_parts:
        lead = " ".join(name_parts)
    else:
        lead = type_label

    details: list[str] = [f"{lead} 중고 {type_label} 매물", price]

    if equipment.year_manufactured:
        year_text = f"{equipment.year_manufactured}년"
        month = equipment.month_manufactured
        if month and 1 <= int(month) <= 12:
            year_text = f"{equipment.year_manufactured}년 {int(month)}월"
        details.append(f"{year_text}식")

    hours = equipment.operating_hours
    if hours:
        try:
            details.append(f"가동 {int(hours):,}시간")
        except (TypeError, ValueError):
            pass

    location = (equipment.current_location or "").strip()
    if not location and equipment.region_sido:
        location = equipment.region_sido.strip()
        if equipment.region_sigungu:
            location = f"{location} {equipment.region_sigungu}".strip()
    if location:
        details.append(location)

    short_desc = (equipment.description or "").strip()
    if short_desc:
        details.append(short_desc)

    if equipment.is_sold:
        details.append("판매완료")

    text = ". ".join(details) + ". 굴삭기나라에서 사진·시세·연락처를 확인하세요."
    if len(text) > 160:
        text = text[:157].rstrip(" .,·") + "…"
    return text
