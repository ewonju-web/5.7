"""매물 목록/상세 페이지의 대량 크롤링 방지용 레이트리밋.

- IP 기준 1분당 60회(비로그인) / 120회(로그인) 초과 시 429 응답.
- 검색엔진 봇(Googlebot, NaverBot/Yeti 등)은 색인 유지를 위해 제한에서 제외한다.
- 프록시(nginx) 뒤에 있으므로 X-Real-IP / X-Forwarded-For로 실제 클라이언트 IP를 추출한다.
"""
from functools import wraps

from django.http import HttpResponse
from django.template.loader import render_to_string
from django_ratelimit import ALL
from django_ratelimit.core import is_ratelimited

ANON_RATE = "60/m"
AUTH_RATE = "120/m"

# 색인 유지를 위해 제한에서 제외할 검색엔진 봇(User-Agent 부분 일치, 소문자 비교)
_SEARCH_ENGINE_BOTS = (
    "googlebot",
    "bingbot",
    "yeti",          # 네이버
    "naverbot",
    "daum",          # 다음/카카오
    "yandexbot",
    "duckduckbot",
    "applebot",
)


def _client_ip(request):
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (
        request.META.get("HTTP_X_REAL_IP")
        or request.META.get("REMOTE_ADDR")
        or ""
    ).strip()


def _is_search_engine(request):
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    return any(bot in ua for bot in _SEARCH_ENGINE_BOTS)


def _ip_key(group, request):
    return _client_ip(request)


def listing_ratelimit(view_func):
    """목록/상세 뷰에 적용하는 레이트리밋 데코레이터.

    제한 초과 시 커스텀 429.html 을 status=429 로 렌더링한다.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if _is_search_engine(request):
            return view_func(request, *args, **kwargs)

        rate = AUTH_RATE if request.user.is_authenticated else ANON_RATE
        limited = is_ratelimited(
            request=request,
            group="equipment:listing",
            fn=view_func,
            key=_ip_key,
            rate=rate,
            method=ALL,
            increment=True,
        )
        if limited:
            # 차단 페이지는 컨텍스트 프로세서/세션에 의존하지 않도록 가볍게 렌더링한다.
            html = render_to_string("429.html")
            return HttpResponse(html, status=429)
        return view_func(request, *args, **kwargs)

    return _wrapped
