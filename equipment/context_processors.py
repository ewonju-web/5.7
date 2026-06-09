from datetime import timedelta

from django.conf import settings
from django.contrib.auth import logout
from django.utils.timezone import localdate

from .models import VisitorCount, VisitorLog


def site_flags(request):
    """템플릿: 신규 가입·신뢰도 등 기능 토글."""
    return {
        'SIGNUP_ENABLED': getattr(settings, 'SIGNUP_ENABLED', True),
    }

def visitor_stats(request):
    # 운영 환경에서 미들웨어 누락/순서 문제로 관리자 세션이 프론트에 남는 경우를 방지한다.
    user = getattr(request, "user", None)
    path = (getattr(request, "path", "") or "").strip()
    if (
        user
        and user.is_authenticated
        and (user.is_staff or user.is_superuser)
        and not path.startswith("/admin/")
    ):
        logout(request)

    today = localdate()
    yesterday = today - timedelta(days=1)

    today_row = VisitorCount.objects.filter(date=today).values('count', 'session_count').first() or {}
    yesterday_row = VisitorCount.objects.filter(date=yesterday).values('count', 'session_count').first() or {}

    # 화면 표시: 당일 고유 IP(VisitorLog) 기준 — 집계 누락 시에도 실제 방문 반영
    today_unique = VisitorLog.objects.filter(visit_date=today).count()
    yesterday_unique = VisitorLog.objects.filter(visit_date=yesterday).count()

    return {
        "VISITOR_TODAY": today_unique,
        "VISITOR_YESTERDAY": yesterday_unique,
        "VISITOR_UNIQUE_TODAY": today_unique,
        "VISITOR_UNIQUE_YESTERDAY": yesterday_unique,
        "VISITOR_SESSION_TODAY": today_row.get('session_count') or 0,
        "VISITOR_SESSION_YESTERDAY": yesterday_row.get('session_count') or 0,
    }
