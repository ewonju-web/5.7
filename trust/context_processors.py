from django.conf import settings


def trust_flags(request):
    """템플릿: 판매자 신뢰도 UI 노출 여부 (코드는 유지, 설정으로만 토글)."""
    return {
        'TRUST_SYSTEM_ENABLED': getattr(settings, 'TRUST_SYSTEM_ENABLED', False),
    }
