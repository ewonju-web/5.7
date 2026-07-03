# -*- coding: utf-8 -*-
"""부품점 검색용 장비/제조사 매칭 유틸."""

MANUFACTURER_KEYWORDS = {
    "현대": ("현대", "HD현대", "HD 현대"),
    "두산": ("두산", "디벨론", "DEVELON", "Doosan"),
    "볼보": ("볼보", "VOLVO", "Volvo"),
    "코벨코": ("코벨코", "고베코", "KOBELCO", "Kobelco"),
    "히타치": ("히타치", "HITACHI", "Hitachi"),
    "캐터필러": ("캐터필러", "캐터필라", "Caterpillar", "CAT"),
    "얀마": ("얀마", "YANMAR", "Yanmar"),
    "클라스": ("클라스", "CLAAS", "Claas"),
}


def detect_manufacturers(name="", keyword_text=""):
    """업체명·키워드에서 취급 제조사를 추정."""
    text = f"{name or ''} {keyword_text or ''}"
    if not text.strip():
        return []

    found = []
    for maker, keywords in MANUFACTURER_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            found.append(maker)
    return found


def match_manufacturers(filters, center):
    """제조사 필터와 업체 데이터가 일치하는지 확인."""
    if not filters:
        return True

    stored = list(center.manufacturers or center.manufacturer or [])
    if any(x in stored for x in filters):
        return True

    text = f"{center.name or ''} {center.note or ''}"
    for mfr in filters:
        keywords = MANUFACTURER_KEYWORDS.get(mfr, (mfr,))
        if any(kw in text for kw in keywords):
            return True
    return False
