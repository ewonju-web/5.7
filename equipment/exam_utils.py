"""자격증 시험 — 유튜브 URL·API 검색 유틸."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

EXAM_VIDEO_KEYWORD_MAP = {
    '': '굴삭기 지게차 운전기능사 실기 필기 시험',
    'excavator': '굴삭기운전기능사 실기 필기 시험',
    'forklift': '지게차운전기능사 실기 필기 시험',
    'crane': '기중기운전기능사 실기 시험',
    'common': '건설기계 운전기능사 시험',
}

EXAM_VIDEO_EQUIPMENT_LABELS = {
    '': '전체',
    'excavator': '굴삭기',
    'forklift': '지게차',
    'crane': '기중기',
    'common': '공통',
}


def extract_youtube_id(url: str) -> str:
    """youtu.be/ID 와 youtube.com/watch?v=ID (및 /embed/ID) 처리."""
    if not url:
        return ''
    url = url.strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        return ''
    host = (parsed.hostname or '').lower().replace('www.', '')
    if host == 'youtu.be':
        video_id = (parsed.path or '').strip('/').split('/')[0]
        return video_id if video_id else ''
    if host in ('youtube.com', 'm.youtube.com', 'music.youtube.com'):
        if parsed.path.startswith('/embed/'):
            return parsed.path.split('/embed/')[1].split('/')[0]
        if parsed.path.startswith('/shorts/'):
            return parsed.path.split('/shorts/')[1].split('/')[0]
        qs = parse_qs(parsed.query)
        if qs.get('v'):
            return qs['v'][0]
    return ''


def fetch_exam_youtube_videos(equipment_key: str = '') -> list[dict]:
    """정비유튜브(excavator_info)와 동일 API·캐시 방식으로 시험 관련 영상 검색."""
    equipment_key = (equipment_key or '').strip()
    if equipment_key not in EXAM_VIDEO_KEYWORD_MAP:
        equipment_key = ''
    query_keyword = EXAM_VIDEO_KEYWORD_MAP[equipment_key]
    equipment_label = EXAM_VIDEO_EQUIPMENT_LABELS.get(equipment_key, '전체')

    api_key = (getattr(settings, 'YOUTUBE_API_KEY', '') or '').strip()
    if not api_key:
        return []

    cache_key = f'youtube_api:exam:{equipment_key or "all"}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    params = {
        'part': 'snippet',
        'q': query_keyword,
        'type': 'video',
        'maxResults': 24,
        'order': 'relevance',
        'regionCode': 'KR',
        'safeSearch': 'moderate',
        'key': api_key,
    }
    req_url = f'https://www.googleapis.com/youtube/v3/search?{urlencode(params)}'
    try:
        req = Request(req_url)
        with urlopen(req, timeout=7) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except Exception:
        return []

    items = []
    for row in payload.get('items') or []:
        video_id = ((row.get('id') or {}).get('videoId') or '').strip()
        snippet = row.get('snippet') or {}
        if not video_id:
            continue
        thumbs = snippet.get('thumbnails') or {}
        thumb = (
            ((thumbs.get('high') or {}).get('url'))
            or ((thumbs.get('medium') or {}).get('url'))
            or ((thumbs.get('default') or {}).get('url'))
            or ''
        )
        items.append({
            'video_id': video_id,
            'title': (snippet.get('title') or '').strip(),
            'channel_title': (snippet.get('channelTitle') or '').strip(),
            'thumbnail_url': thumb,
            'youtube_url': f'https://www.youtube.com/watch?v={video_id}',
            'equipment_label': equipment_label,
        })
    cache.set(cache_key, items, timeout=86400)
    return items
