from django.db import IntegrityError, transaction
from django.utils.timezone import localdate

from ..models import VisitorLog
from ..visit_tracking import client_ip, is_bot_request, should_skip_path


class VisitorCounterMiddleware:
    """푸터 방문자 수: 일별 고유 IP(VisitorLog)만 기록."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if should_skip_path(request) or is_bot_request(request):
            return self.get_response(request)

        ip = client_ip(request)
        if not ip:
            return self.get_response(request)

        today = localdate()
        referer = request.META.get("HTTP_REFERER") or "직접 접속"

        try:
            with transaction.atomic():
                VisitorLog.objects.get_or_create(
                    ip_address=ip,
                    visit_date=today,
                    defaults={"referer": referer},
                )
        except IntegrityError:
            pass

        return self.get_response(request)
