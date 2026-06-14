"""글쓰기 POST 전역 SQLi·Rate Limit 미들웨어."""
from __future__ import annotations

import re

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

from equipment.content_security import (
    ban_user_account,
    bump_write_rate_limit,
    check_write_rate_limit,
    record_attack_attempt,
    validate_request_post_data,
)

POST_SKIP_PATH_PREFIXES = (
    '/admin/',
    '/static/',
    '/media/',
    '/login/',
    '/logout/',
    '/accounts/',
    '/phone',
    '/setlang/',
    '/health',
    '/favicon',
    '/robots.txt',
)

POST_SKIP_PATH_RE = re.compile(
    r'^/(equipment/\d+/favorite/|toggle_|index/load-more/)',
)


class ContentSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'POST':
            return self.get_response(request)

        path = request.path or ''
        if any(path.startswith(prefix) for prefix in POST_SKIP_PATH_PREFIXES):
            return self.get_response(request)
        if POST_SKIP_PATH_RE.match(path):
            return self.get_response(request)

        # 텍스트 입력이 없는 POST(토글·삭제 체크 등)는 통과
        from equipment.content_security import iter_post_text_values

        text_pairs = iter_post_text_values(request)
        if not text_pairs:
            return self.get_response(request)

        rate_msg = check_write_rate_limit(request)
        if rate_msg:
            return self._reject(request, rate_msg, blocked=False)

        invalid_msg = validate_request_post_data(request)
        if invalid_msg:
            banned = record_attack_attempt(request)
            if banned:
                return self._reject(
                    request,
                    '비정상 입력이 반복되어 계정이 차단되었습니다.',
                    blocked=True,
                )
            return self._reject(request, invalid_msg, blocked=True)

        response = self.get_response(request)
        if getattr(response, 'status_code', 500) < 400:
            bump_write_rate_limit(request)
        return response

    def _reject(self, request, message: str, *, blocked: bool):
        if request.path.startswith('/trust/') or 'application/json' in (request.META.get('CONTENT_TYPE') or '').lower():
            status = 403 if blocked else 429
            return JsonResponse({'ok': False, 'message': message}, status=status)

        messages.error(request, message)
        referer = request.META.get('HTTP_REFERER') or ''
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            return redirect(referer)
        return redirect('/')
