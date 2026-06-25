"""방문 추적 미들웨어 공통 유틸."""

import re

SKIP_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
    "/index/load-more/",
    "/favicon",
    # 언어 전환 등 즉시 리다이렉트되는 동작용 URL은 방문으로 집계하지 않는다
    # (표준 분석 도구도 페이지뷰로 세지 않음). 봇이 언어 링크를 긁어 카운트가 부풀던 문제 제거.
    "/chat/setlang",
)
SKIP_EXACT = {"/robots.txt", "/sitemap.xml", "/health", "/health/"}

_BOT_UA_RE = re.compile(
    r"bot|crawler|spider|crawling|slurp|gptbot|chatgpt|bytespider|semrush|ahrefs|"
    r"dotbot|petalbot|mj12bot|facebookexternalhit|linkedinbot|twitterbot|"
    r"whatsapp|telegrambot|applebot|yandex|baiduspider|headlesschrome",
    re.I,
)


def is_bot_request(request) -> bool:
    """크롤러·헤드리스 등 자동 트래픽 여부 (방문 기록·분석 스킵용)."""
    ua = (request.META.get("HTTP_USER_AGENT") or "").strip()
    if not ua:
        return True
    return bool(_BOT_UA_RE.search(ua))


def client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def should_skip_path(request) -> bool:
    path = request.path or ""
    if path in SKIP_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = (request.headers.get("Accept") or "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False
