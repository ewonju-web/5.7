import logging

from django.db import DatabaseError, transaction
from django.utils.timezone import localdate

from ..models import VisitorLog
from ..visit_tracking import client_ip, is_bot_request, should_skip_path

logger = logging.getLogger(__name__)


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

        # 방문자 기록은 부가 기능 — DB 잠금(SQLite database is locked) 등으로
        # 절대 페이지/저장 요청을 500으로 떨어뜨리지 않도록 모든 예외를 흡수한다.
        try:
            with transaction.atomic():
                VisitorLog.objects.get_or_create(
                    ip_address=ip,
                    visit_date=today,
                    defaults={"referer": referer},
                )
        except DatabaseError:
            pass
        except Exception:
            logger.warning("VisitorLog 기록 실패", exc_info=True)

        return self.get_response(request)
