from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from django.conf import settings
from django.core.cache import cache


CALL_KEYWORDS = {
    "all": ["중기 호출", "건설기계 호출", "굴삭기 작업"],
    "excavator": ["굴삭기 호출", "굴삭기 작업", "굴삭기 기사"],
    "forklift": ["지게차 호출", "지게차 작업", "지게차 기사"],
    "crane": ["기중기 호출", "크레인 호출"],
    "dump": ["덤프트럭 호출", "덤프 기사"],
    "loader": ["스키로더 호출", "로더 기사"],
    "other": ["건설기계 기사", "중기 기사"],
}


def _kakao_rest_key():
    return (getattr(settings, "KAKAO_REST_API_KEY", "") or "").strip()


def fetch_call_companies(equipment_type="all", region="전국"):
    cache_key = f"call_kakao:{equipment_type}:{region}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    key = _kakao_rest_key()
    if not key:
        cache.set(cache_key, [], 60 * 10)
        return []

    region_prefix = "" if region in ("", "전국") else f"{region} "
    keywords = CALL_KEYWORDS.get(equipment_type) or CALL_KEYWORDS["all"]

    found = {}
    for keyword in keywords:
        query = f"{region_prefix}{keyword}".strip()
        params = urlencode({"query": query, "size": 15})
        req_url = f"https://dapi.kakao.com/v2/local/search/keyword.json?{params}"
        try:
            request_obj = Request(req_url, headers={"Authorization": f"KakaoAK {key}"})
            with urlopen(request_obj, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue

        for doc in payload.get("documents") or []:
            doc_id = str(doc.get("id") or "")
            if not doc_id:
                continue
            found[doc_id] = {
                "id": doc_id,
                "name": (doc.get("place_name") or "").strip(),
                "phone": (doc.get("phone") or "").strip(),
                "address": (doc.get("road_address_name") or doc.get("address_name") or "").strip(),
                "lat": float(doc.get("y")) if doc.get("y") else None,
                "lng": float(doc.get("x")) if doc.get("x") else None,
                "place_url": (doc.get("place_url") or "").strip(),
                "region": region if region else "",
                "equipment_type": equipment_type or "all",
            }

    results = list(found.values())
    cache.set(cache_key, results, 60 * 60 * 24)
    return results
