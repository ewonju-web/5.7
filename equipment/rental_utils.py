"""카카오 로컬 API — 임대·지역중기·중기호출 키워드 자동수집."""
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import re

from django.conf import settings
from django.core.cache import cache


RENTAL_KEYWORDS = {
    "all": ["중기 임대", "건설기계 임대", "굴삭기 임대", "중장비 임대"],
    "excavator": ["굴삭기 임대", "포크레인 임대", "굴삭기 렌탈"],
    "forklift": ["지게차 임대", "지게차 렌탈"],
    "crane": ["크레인 임대", "기중기 임대"],
    "dump": ["덤프트럭 임대", "덤프 임대"],
    "loader": ["스키로더 임대", "로더 임대"],
    "attachment": ["어태치먼트 임대"],
    "other": ["건설기계 임대", "중장비 렌탈"],
}

CALL_KEYWORDS = {
    "all": [
        "중장비 작업",
        "건설기계 작업",
        "굴삭기 작업",
        "굴삭기 출장",
        "건설기계 기사",
        "중기 호출",
    ],
    "excavator": ["굴삭기 작업", "굴삭기 출장", "포크레인 작업", "굴삭기 운전"],
    "forklift": ["지게차 작업", "지게차 출장", "지게차 기사"],
    "crane": ["크레인 작업", "기중기 작업", "크레인 출장"],
    "dump": ["덤프트럭 작업", "덤프 기사"],
    "loader": ["스키로더 작업", "로더 작업"],
    "other": ["건설기계 기사", "중장비 작업", "건설기계 작업"],
}

# 카카오맵 "중기" 검색과 동일 — 지역별 중기(건설기계) 취급 업체
REGIONAL_HEAVY_KEYWORD = "중기"

KAKAO_SEARCH_REGIONS = [
    "서울",
    "경기",
    "인천",
    "부산",
    "대구",
    "광주",
    "대전",
    "울산",
    "세종",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
]

# 카카오 category_name → 기종 힌트
_CATEGORY_EQUIPMENT_HINTS = [
    (("굴삭", "포크레인"), "excavator"),
    (("지게차",), "forklift"),
    (("크레인", "기중"), "crane"),
    (("덤프",), "dump"),
    (("로더", "스키로더"), "loader"),
    (("어태치", "부속"), "attachment"),
]


def get_kakao_rest_key():
    """REST API 키 — settings → SocialApp(카카오) 순으로 조회."""
    key = (getattr(settings, "KAKAO_REST_API_KEY", "") or "").strip()
    if key:
        return key
    try:
        from allauth.socialaccount.models import SocialApp

        return (
            SocialApp.objects.filter(provider="kakao")
            .values_list("client_id", flat=True)
            .first()
            or ""
        ).strip()
    except Exception:
        return ""


def _infer_equipment_type(place_name, category_name, keyword_equipment):
    text = f"{place_name} {category_name}"
    for needles, eq in _CATEGORY_EQUIPMENT_HINTS:
        if any(n in text for n in needles):
            return eq
    return keyword_equipment if keyword_equipment != "all" else "other"


def _fetch_kakao_keyword_places(
    keywords,
    equipment_type="all",
    region="",
    cache_prefix="kakao",
    *,
    max_pages=3,
    region_scan=None,
):
    cache_key = f"{cache_prefix}:{equipment_type}:{region or '전국'}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    key = get_kakao_rest_key()
    if not key:
        cache.set(cache_key, [], 60 * 10)
        return []

    found = {}
    queries = []
    if region_scan:
        for scan_region in region_scan:
            for keyword in keywords:
                queries.append(f"{scan_region} {keyword}".strip())
    else:
        region_prefix = "" if region in ("", "전국") else f"{region} "
        for keyword in keywords:
            queries.append(f"{region_prefix}{keyword}".strip())

    for query in queries:
        for page in range(1, max_pages + 1):
            params = urlencode({"query": query, "size": 15, "page": page})
            req_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?{params}"
            try:
                request_obj = Request(req_url, headers={"Authorization": f"KakaoAK {key}"})
                with urlopen(request_obj, timeout=10) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except Exception:
                break

            docs = payload.get("documents") or []
            if not docs:
                break

            for doc in docs:
                doc_id = str(doc.get("id") or "")
                if not doc_id:
                    continue
                place_name = (doc.get("place_name") or "").strip()
                category_name = (doc.get("category_name") or "").strip()
                lat_raw, lng_raw = doc.get("y"), doc.get("x")
                try:
                    lat = float(lat_raw) if lat_raw else None
                    lng = float(lng_raw) if lng_raw else None
                except (TypeError, ValueError):
                    lat, lng = None, None

                found[doc_id] = {
                    "id": doc_id,
                    "name": place_name,
                    "phone": (doc.get("phone") or "").strip(),
                    "address": (doc.get("road_address_name") or doc.get("address_name") or "").strip(),
                    "lat": lat,
                    "lng": lng,
                    "place_url": (doc.get("place_url") or "").strip(),
                    "category_name": category_name,
                    "region": _extract_region_from_address(
                        doc.get("road_address_name") or doc.get("address_name") or ""
                    ),
                    "equipment_type": _infer_equipment_type(place_name, category_name, equipment_type),
                }

    results = list(found.values())
    cache.set(cache_key, results, 60 * 60 * 24)
    return results


def _extract_region_from_address(address):
    addr = (address or "").strip()
    if not addr:
        return ""
    # 시·도 단위 추출 (예: 경기 남양주시 → 경기)
    m = re.match(r"^(\S+?(?:특별자치도|광역시|특별시|도)?)", addr)
    if m:
        token = m.group(1)
        for suffix in ("특별자치도", "광역시", "특별시", "도"):
            if token.endswith(suffix):
                return token[: -len(suffix)]
        return token
    return ""


def fetch_rental_companies(equipment_type="all", region="전국"):
    keywords = RENTAL_KEYWORDS.get(equipment_type) or RENTAL_KEYWORDS["all"]
    return _fetch_kakao_keyword_places(
        keywords,
        equipment_type=equipment_type,
        region=region,
        cache_prefix="rental_kakao",
    )


def fetch_call_companies(equipment_type="all", region="전국"):
    keywords = CALL_KEYWORDS.get(equipment_type) or CALL_KEYWORDS["all"]
    return _fetch_kakao_keyword_places(
        keywords,
        equipment_type=equipment_type,
        region=region,
        cache_prefix="call_kakao",
    )


def fetch_regional_heavy_companies(equipment_type="all", region="전국"):
    """카카오맵 '중기' 검색 — 지역별 건설기계(중기) 취급 업체."""
    region = (region or "").strip()
    if region and region not in ("", "전국"):
        return _fetch_kakao_keyword_places(
            [REGIONAL_HEAVY_KEYWORD],
            equipment_type=equipment_type,
            region=region,
            cache_prefix="regional_heavy",
            max_pages=3,
        )
    return _fetch_kakao_keyword_places(
        [REGIONAL_HEAVY_KEYWORD],
        equipment_type=equipment_type,
        region="전국",
        cache_prefix="regional_heavy",
        max_pages=3,
        region_scan=KAKAO_SEARCH_REGIONS,
    )
