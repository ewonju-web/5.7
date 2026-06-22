"""schema.org 구조화 데이터(JSON-LD) 생성."""
from __future__ import annotations

import json

from django.utils.safestring import mark_safe

from equipment.seo_meta import _equipment_type_label, equipment_seo_description

SCHEMA_ORG = "https://schema.org"
USED_CONDITION = f"{SCHEMA_ORG}/UsedCondition"
IN_STOCK = f"{SCHEMA_ORG}/InStock"
OUT_OF_STOCK = f"{SCHEMA_ORG}/OutOfStock"
# 반품 불가(중고 중장비 직거래 특성상 반품 정책 없음)
MERCHANT_RETURN_NOT_PERMITTED = f"{SCHEMA_ORG}/MerchantReturnNotPermitted"
SITE_HOME = "https://www.direct-nara.co.kr/"


def _product_name(equipment) -> str:
    manufacturer = (equipment.manufacturer or "").strip()
    model = (equipment.model_name or "").strip()
    type_label = _equipment_type_label(equipment)
    name_parts = [p for p in (manufacturer, model) if p]
    if name_parts:
        name = " ".join(name_parts)
        if type_label and type_label not in name:
            return f"{name} {type_label}"
        return name
    return type_label


def _price_krw(listing_price) -> int | None:
    if listing_price is None:
        return None
    try:
        val = int(listing_price)
    except (TypeError, ValueError):
        return None
    if val <= 0:
        return None
    return val * 10_000


def _canonical_absolute_url(request, path: str = "") -> str:
    url = request.build_absolute_uri(path) if path else request.build_absolute_uri()
    host = (request.get_host() or "").split(":")[0].lower()
    if host.endswith("direct-nara.co.kr") and url.startswith("http://"):
        return "https://" + url[7:]
    return url


def _absolute_media_url(request, image_url: str) -> str:
    url = (image_url or "").strip()
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        if "direct-nara.co.kr" in url and url.startswith("http://"):
            return "https://" + url[7:]
        return url
    return _canonical_absolute_url(request, url)


def _image_urls(request, detail_images) -> list[str]:
    urls: list[str] = []
    for image in detail_images or []:
        field = getattr(image, "image", None)
        name = getattr(field, "name", "") if field else ""
        if not (name or "").strip():
            continue
        absolute = _absolute_media_url(request, field.url)
        if absolute:
            urls.append(absolute)
    return urls


def build_equipment_schema_graph(
    equipment,
    *,
    page_url: str,
    image_urls: list[str],
    category_url: str,
) -> dict:
    name = _product_name(equipment)
    type_label = _equipment_type_label(equipment)

    product: dict = {
        "@type": "Product",
        "@id": f"{page_url}#product",
        "name": name,
        "description": equipment_seo_description(equipment),
        "sku": str(equipment.pk),
        "productID": str(equipment.pk),
        "category": type_label,
        "itemCondition": USED_CONDITION,
        "url": page_url,
    }

    if image_urls:
        product["image"] = image_urls

    manufacturer = (equipment.manufacturer or "").strip()
    if manufacturer:
        product["brand"] = {"@type": "Brand", "name": manufacturer}

    additional: list[dict] = []
    if equipment.year_manufactured:
        year_text = f"{equipment.year_manufactured}년"
        month = equipment.month_manufactured
        if month and 1 <= int(month) <= 12:
            year_text = f"{equipment.year_manufactured}년 {int(month)}월"
        additional.append(
            {"@type": "PropertyValue", "name": "연식", "value": year_text}
        )
    if equipment.operating_hours:
        try:
            additional.append(
                {
                    "@type": "PropertyValue",
                    "name": "가동시간",
                    "value": f"{int(equipment.operating_hours):,}시간",
                }
            )
        except (TypeError, ValueError):
            pass
    location = (equipment.current_location or "").strip()
    if not location and equipment.region_sido:
        location = equipment.region_sido.strip()
        if equipment.region_sigungu:
            location = f"{location} {equipment.region_sigungu}".strip()
    if location:
        additional.append(
            {"@type": "PropertyValue", "name": "위치", "value": location}
        )
    if additional:
        product["additionalProperty"] = additional

    offer: dict = {
        "@type": "Offer",
        "@id": f"{page_url}#offer",
        "url": page_url,
        "priceCurrency": "KRW",
        "availability": OUT_OF_STOCK if equipment.is_sold else IN_STOCK,
        "itemCondition": USED_CONDITION,
        "seller": {
            "@type": "Organization",
            "name": "굴삭기나라",
            "url": SITE_HOME,
        },
        # 운송은 판매자·구매자 직접 협의(플랫폼 별도 배송비 없음). 구조화 데이터 필수 필드 충족용 최소값.
        "shippingDetails": {
            "@type": "OfferShippingDetails",
            "shippingDestination": {
                "@type": "DefinedRegion",
                "addressCountry": "KR",
            },
            "shippingRate": {
                "@type": "MonetaryAmount",
                "value": "0",
                "currency": "KRW",
            },
        },
        # 중고 중장비 직거래 특성상 반품 정책 없음(반품 불가).
        "hasMerchantReturnPolicy": {
            "@type": "MerchantReturnPolicy",
            "applicableCountry": "KR",
            "returnPolicyCategory": MERCHANT_RETURN_NOT_PERMITTED,
        },
    }
    price_krw = _price_krw(equipment.listing_price)
    if price_krw is not None:
        offer["price"] = str(price_krw)

    product["offers"] = offer

    breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": f"{page_url}#breadcrumb",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "굴삭기나라",
                "item": SITE_HOME,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": type_label,
                "item": category_url,
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": name,
                "item": page_url,
            },
        ],
    }

    return {
        "@context": SCHEMA_ORG,
        "@graph": [product, breadcrumb],
    }


def render_equipment_schema_script(equipment, request, detail_images) -> str:
    page_url = _canonical_absolute_url(request)
    equipment_type = (equipment.equipment_type or "").strip()
    if equipment_type:
        category_url = _canonical_absolute_url(request, f"/?category={equipment_type}")
    else:
        category_url = _canonical_absolute_url(request, "/")

    data = build_equipment_schema_graph(
        equipment,
        page_url=page_url,
        image_urls=_image_urls(request, detail_images),
        category_url=category_url,
    )
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')
