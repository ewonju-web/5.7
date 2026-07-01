from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from allauth.socialaccount.providers.base import AuthProcess


class DirectNaraSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    소셜 OAuth는 기존 회원의 로그인·연결(connect)만 허용한다.
    신규 회원은 아이디·비밀번호 가입 후 마이페이지에서 소셜을 연결해야 한다.
    """

    def _redirect_social_guide(self, request, reason="login"):
        from urllib.parse import urlencode

        url = reverse("social_connect_guide")
        query = urlencode({"reason": reason})
        raise ImmediateHttpResponse(redirect(f"{url}?{query}"))

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        process = sociallogin.state.get("process")
        if process == AuthProcess.CONNECT:
            if not request.user.is_authenticated:
                messages.warning(
                    request,
                    "소셜 계정 연결은 회원가입·로그인 후 마이페이지에서 진행해 주세요.",
                )
                self._redirect_social_guide(request, reason="connect")
            return
        if not sociallogin.is_existing:
            messages.warning(
                request,
                "회원가입 후 마이페이지에서 카카오·네이버·구글 계정을 연결해 주세요.",
            )
            self._redirect_social_guide(request, reason="login")
