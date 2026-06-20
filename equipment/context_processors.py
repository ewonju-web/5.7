from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import localdate

from .models import VisitSession


def site_flags(request):
    """템플릿: 신규 가입·신뢰도 등 기능 토글."""
    return {
        'SIGNUP_ENABLED': getattr(settings, 'SIGNUP_ENABLED', True),
    }


def _unique_sessions(day):
    """해당 일자(한국 날짜)의 고유 방문 세션 수.

    VisitSession 은 VisitAnalyticsMiddleware 기록 시 is_bot_request 로 봇이 이미
    제외된 사람 트래픽만 들어오므로, 오늘자 고유 session_key 수가 곧 방문자 수.
    """
    return (
        VisitSession.objects.filter(started_at__date=day)
        .values("django_session_key")
        .distinct()
        .count()
    )


def visitor_stats(request):
    """푸터 방문자 수 — VisitSession 일별 고유 세션키 기준(봇 제외)."""
    today = localdate()
    cache_key = f"visitor_stats:v2:{today.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    yesterday = today - timedelta(days=1)
    result = {
        "VISITOR_TODAY": _unique_sessions(today),
        "VISITOR_YESTERDAY": _unique_sessions(yesterday),
    }
    cache.set(cache_key, result, timeout=300)
    return result
