"""봇 트래픽을 방문자 집계(VisitorLog)에서 제외하는 미들웨어.

다음 중 하나에 해당하면 봇으로 보고 집계에서 제외한다.
  1) bot_blocklist(IP 차단 목록)에 등록/캐시된 IP
  2) User-Agent 가 비어있고(=UA 없음) + HTTP_REFERER 도 없는(=직접접속, 체류추적 불가) 패턴

집계 제외 처리는 ``request._skip_visitor_log = True`` 플래그로만 표시하며,
실제 VisitorLog 기록 로직(VisitorCounterMiddleware)은 그대로 둔다.
(VisitorCounterMiddleware 가 이 플래그를 보고 기록을 건너뛴다.)

제외된 요청은 분석용으로 BotLog 에 IP/경로/UA 만 남긴다.

※ settings.MIDDLEWARE 등록 위치: 반드시
  'equipment.middleware.visitor_middleware.VisitorCounterMiddleware' '바로 위(앞)'에
  둬서 카운터보다 먼저 실행되어 플래그를 세팅해야 한다.
"""
from __future__ import annotations

import logging

from django.db import DatabaseError, transaction

from ..content_security import is_ip_blocked
from ..visit_tracking import client_ip, should_skip_path

logger = logging.getLogger(__name__)


class BotAnalyticsExclusionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _is_excluded_bot(request) -> bool:
        ip = client_ip(request)
        # 1) bot_blocklist 연동 — 차단 IP 목록/캐시 참조
        if ip and is_ip_blocked(ip):
            return True
        # 2) UA 없음 + 리퍼러 없음(직접접속, 체류추적 불가) 패턴
        ua = (request.META.get("HTTP_USER_AGENT") or "").strip()
        referer = (request.META.get("HTTP_REFERER") or "").strip()
        if not ua and not referer:
            return True
        return False

    def __call__(self, request):
        if not should_skip_path(request) and self._is_excluded_bot(request):
            request._skip_visitor_log = True
            self._record_botlog(request)
        return self.get_response(request)

    @staticmethod
    def _record_botlog(request):
        # 부가 기능 — DB 잠금 등 어떤 예외도 요청을 깨뜨리지 않도록 모두 흡수한다.
        from ..models import BotLog

        ip = client_ip(request)
        if not ip:
            return
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:300]
        path = (request.path or "")[:500]
        try:
            with transaction.atomic():
                BotLog.objects.create(ip_address=ip, path=path, user_agent=ua)
        except DatabaseError:
            pass
        except Exception:
            logger.warning("BotLog 기록 실패", exc_info=True)
