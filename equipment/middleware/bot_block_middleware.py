"""알려진 봇 계정·IP 요청 차단."""
from __future__ import annotations

from django.contrib.auth import logout
from django.http import HttpResponseForbidden, JsonResponse

from equipment.bot_blocklist import is_blocked_bot_ip, is_blocked_bot_user
from equipment.content_security import block_ip
from equipment.finance_security import get_client_ip


class BotBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = get_client_ip(request)
        if is_blocked_bot_ip(ip):
            block_ip(ip, seconds=86400 * 30)
            return self._deny(request)

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and is_blocked_bot_user(user):
            logout(request)
            block_ip(ip, seconds=86400 * 30)
            return self._deny(request)

        return self.get_response(request)

    def _deny(self, request):
        accept = (request.META.get('HTTP_ACCEPT') or '').lower()
        if 'application/json' in accept or request.path.startswith('/account/'):
            return JsonResponse({'ok': False, 'error': '접근이 차단되었습니다.'}, status=403)
        return HttpResponseForbidden('접근이 차단되었습니다.')
