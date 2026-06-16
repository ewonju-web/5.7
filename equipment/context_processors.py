from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils.timezone import localdate

from .models import VisitorLog


def site_flags(request):
    """템플릿: 신규 가입·신뢰도 등 기능 토글."""
    return {
        'SIGNUP_ENABLED': getattr(settings, 'SIGNUP_ENABLED', True),
    }


def visitor_stats(request):
    """푸터 방문자 수 — VisitorLog 고유 IP 기준."""
    today = localdate()
    cache_key = f"visitor_stats:{today.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    yesterday = today - timedelta(days=1)
    result = {
        "VISITOR_TODAY": VisitorLog.objects.filter(visit_date=today).count(),
        "VISITOR_YESTERDAY": VisitorLog.objects.filter(visit_date=yesterday).count(),
    }
    cache.set(cache_key, result, timeout=300)
    return result
