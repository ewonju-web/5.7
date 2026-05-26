"""자격증 시험 — 유튜브 URL 유틸."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse


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
