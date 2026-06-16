"""중장비 유튜브(/info/) — YouTube API 검색·캐시."""
from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from .exam_utils import extract_youtube_id, youtube_thumbnail_pick
from .models import YoutubeContent

CATEGORY_TABS = [
    ("excavator_maintenance_repair", "굴삭기정비/수리"),
    ("excavator_inspection", "굴삭기 점검"),
    ("excavator_loading", "굴삭기 상하차"),
    ("forklift_maintenance", "지게차 정비"),
    ("dump_maintenance", "덤프트럭 정비"),
    ("loader_maintenance", "스키로더 정비"),
    ("crane_maintenance", "크레인 정비"),
]
CATEGORY_KEYWORD_MAP = {
    "excavator_maintenance_repair": "굴삭기 정비 수리",
    "excavator_inspection": "굴삭기 점검",
    "excavator_loading": "굴삭기 상하차",
    "forklift_maintenance": "지게차 정비",
    "dump_maintenance": "덤프트럭 정비",
    "loader_maintenance": "스키로더 정비",
    "crane_maintenance": "크레인 정비",
}
CATEGORY_FALLBACK_KEYWORDS = {
    "excavator_loading": ["굴삭기 트럭 상하차", "굴삭기 상차 하차"],
}
VALID_CATEGORIES = {key for key, _ in CATEGORY_TABS}
DEFAULT_CATEGORY = "excavator_maintenance_repair"

CACHE_PREFIX = "youtube_api:v5"
CACHE_TIMEOUT = 86400
FALLBACK_CACHE_TIMEOUT = 600


def normalize_category(category: str) -> str:
    category = (category or DEFAULT_CATEGORY).strip().lower()
    if category not in VALID_CATEGORIES:
        return DEFAULT_CATEGORY
    return category


def resolve_category_from_request(
    category: str | None,
    equipment_type: str | None = None,
    purpose: str | None = None,
) -> str:
    """category 파라미터 우선, 구 URL(equipment_type/purpose)은 하위 호환."""
    normalized = normalize_category(category or "")
    if category:
        return normalized

    purpose_key = (purpose or "").strip().lower()
    equipment_key = (equipment_type or "all").strip().lower()
    legacy_map = {
        "excavator_maintenance": "excavator_maintenance_repair",
        "excavator_repair": "excavator_maintenance_repair",
        "excavator_inspection": "excavator_inspection",
        "excavator_loading": "excavator_loading",
        "forklift_maintenance": "forklift_maintenance",
        "dump_maintenance": "dump_maintenance",
    }
    if purpose_key in legacy_map:
        mapped = legacy_map[purpose_key]
        if purpose_key in ("forklift_maintenance", "dump_maintenance"):
            return mapped
        if equipment_key in ("all", "excavator", ""):
            return mapped
        if equipment_key == "forklift" and purpose_key == "forklift_maintenance":
            return "forklift_maintenance"
        if equipment_key == "dump" and purpose_key == "dump_maintenance":
            return "dump_maintenance"
        if equipment_key == "loader":
            return "loader_maintenance"
        if equipment_key == "crane":
            return "crane_maintenance"
    return normalized


def build_query_keyword(category: str) -> str:
    category = normalize_category(category)
    return CATEGORY_KEYWORD_MAP[category]


def _cache_key(category: str) -> str:
    return f"{CACHE_PREFIX}:{category}"


def _fallback_db_items(category: str) -> list[dict]:
    fallback_cache_key = f"{CACHE_PREFIX}:fallback:{category}"
    cached = cache.get(fallback_cache_key)
    if cached is not None:
        return cached

    contents = YoutubeContent.objects.filter(is_active=True)
    items = []
    label = CATEGORY_KEYWORD_MAP.get(category, "")
    for item in contents[:24]:
        video_id = extract_youtube_id(item.youtube_url or "")
        thumb = youtube_thumbnail_pick(video_id) if video_id else {"url": "", "needs_crop": False}
        items.append({
            "video_id": video_id,
            "title": item.title,
            "channel_title": "굴삭기나라",
            "thumbnail_url": thumb["url"],
            "thumbnail_needs_crop": thumb["needs_crop"],
            "youtube_url": item.youtube_url,
            "category": category,
            "category_label": label,
        })
    cache.set(fallback_cache_key, items, timeout=FALLBACK_CACHE_TIMEOUT)
    return items


def _search_youtube(query_keyword: str, *, allow_api: bool) -> list[dict]:
    if not allow_api:
        return []

    api_key = (getattr(settings, "YOUTUBE_API_KEY", "") or "").strip()
    if not api_key:
        return []

    params = {
        "part": "snippet",
        "q": query_keyword,
        "type": "video",
        "maxResults": 24,
        "order": "relevance",
        "regionCode": "KR",
        "safeSearch": "moderate",
        "key": api_key,
    }
    req_url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
    try:
        req = Request(req_url)
        # 외부 API 지연으로 페이지 체감 속도가 떨어지지 않도록 타임아웃을 짧게 둔다.
        with urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    rows = []
    for row in payload.get("items") or []:
        video_id = ((row.get("id") or {}).get("videoId") or "").strip()
        snippet = row.get("snippet") or {}
        if not video_id:
            continue
        # 분야별 영상 목록은 응답 속도 우선:
        # 각 영상마다 썸네일 존재 확인 요청을 보내지 않고
        # YouTube API 응답 썸네일을 바로 사용한다.
        thumbs = snippet.get("thumbnails") or {}
        thumb_url = (
            ((thumbs.get("high") or {}).get("url"))
            or ((thumbs.get("medium") or {}).get("url"))
            or ((thumbs.get("default") or {}).get("url"))
            or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        )
        rows.append({
            "video_id": video_id,
            "title": (snippet.get("title") or "").strip(),
            "channel_title": (snippet.get("channelTitle") or "").strip(),
            "thumbnail_url": thumb_url,
            "thumbnail_needs_crop": False,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
        })
    return rows


def _search_category(category: str, *, allow_api: bool) -> list[dict]:
    category = normalize_category(category)
    queries = [build_query_keyword(category)]
    queries.extend(CATEGORY_FALLBACK_KEYWORDS.get(category, []))

    seen: set[str] = set()
    merged: list[dict] = []
    for query in queries:
        for row in _search_youtube(query, allow_api=allow_api):
            video_id = (row.get("video_id") or "").strip()
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            merged.append(row)
            if len(merged) >= 24:
                return merged
    return merged


def fetch_youtube_videos(
    category: str,
    *,
    allow_api: bool = True,
) -> list[dict]:
    """분야별 영상 목록 (캐시 → API → DB fallback)."""
    category = normalize_category(category)
    cache_key = _cache_key(category)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    category_label = CATEGORY_KEYWORD_MAP[category]
    raw_items = _search_category(category, allow_api=allow_api)

    if not raw_items and not allow_api:
        return _fallback_db_items(category)

    items = []
    for row in raw_items:
        items.append({
            **row,
            "category": category,
            "category_label": category_label,
        })

    if not items:
        return _fallback_db_items(category)

    cache.set(cache_key, items, timeout=CACHE_TIMEOUT)
    return items


def fetch_youtube_catalog(*, allow_api: bool = True) -> dict[str, list[dict]]:
    """모든 분야 영상을 한 번에 반환 (클라이언트 필터용)."""
    catalog: dict[str, list[dict]] = {}
    for category, _ in CATEGORY_TABS:
        catalog[category] = fetch_youtube_videos(category, allow_api=allow_api)
    return catalog


def count_catalog_items(catalog: dict[str, list[dict]]) -> int:
    return sum(len(items) for items in catalog.values())
