from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout
from django.http import HttpResponse, HttpResponseRedirect
from equipment.views import (
    user_login,
    user_logout,
    signup,
    check_username,
    find_username,
    legacy_redirect_viewsale_list,
)
from equipment.forms import MigratedPasswordResetForm
from equipment.sitemap_views import sitemap_xml


def _social_callback_alias(request, provider: str):
    """Developer console callback aliases -> allauth callback URL."""
    provider = (provider or "").strip().lower()
    if provider not in ("kakao", "naver"):
        return HttpResponseRedirect("/login/")
    query = request.META.get("QUERY_STRING", "")
    target = f"/accounts/{provider}/login/callback/"
    if query:
        target = f"{target}?{query}"
    return HttpResponseRedirect(target)


def _admin_view_site(request):
    """
    관리자 상단 '사이트 보기' 전용:
    관리자 세션을 먼저 종료한 뒤 메인으로 이동한다.
    """
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        logout(request)

    response = HttpResponseRedirect("/")
    cookie_name = settings.SESSION_COOKIE_NAME
    host = (request.get_host() or "").split(":")[0].strip().lower()

    paths = {"/", "/admin"}
    if settings.SESSION_COOKIE_PATH:
        paths.add(settings.SESSION_COOKIE_PATH)

    domains = {None}
    if settings.SESSION_COOKIE_DOMAIN:
        domains.add(settings.SESSION_COOKIE_DOMAIN)
    if host:
        domains.add(host)
        domains.add(f".{host}")
    # 운영에서 실제 사용 중인 호스트들까지 함께 만료해 쿠키 잔존 이슈를 줄인다.
    domains.update({"211.110.140.201"})

    for domain in domains:
        for path in paths:
            response.delete_cookie(cookie_name, path=path, domain=domain)

    return response


def _redirect_authenticated_to_mypage(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect("/mypage/")
    return None


def _robots_txt(request):
    # 색인 불필요(개인정보·결제·관리) 경로는 차단, 공개 콘텐츠(매물·카테고리·정보)는 허용.
    disallow = [
        "/admin/",
        "/login/",
        "/logout/",
        "/signup/",
        "/mypage/",
        "/accounts/",
        "/password-reset/",
        "/password-reset-confirm/",
        "/billing/checkout/",
        "/billing/success/",
        "/billing/fail/",
        "/chat/",
    ]
    lines = ["User-agent: *"]
    lines += [f"Disallow: {p}" for p in disallow]
    lines.append("Allow: /")
    lines.append("")
    # 네이버 Yeti
    lines.append("User-agent: Yeti")
    lines += [f"Disallow: {p}" for p in disallow]
    lines.append("Allow: /")
    lines.append("")
    # 과도한 트래픽을 유발하는 AI/SEO 분석 크롤러 전체 차단.
    # (정상 검색엔진 Googlebot·Bingbot·Yandex·Yeti 는 차단하지 않음)
    blocked_bots = ["GPTBot", "SemrushBot", "AhrefsBot", "MJ12bot", "DotBot"]
    for bot in blocked_bots:
        lines.append(f"User-agent: {bot}")
        lines.append("Disallow: /")
        lines.append("")
    lines.append("Sitemap: https://www.direct-nara.co.kr/sitemap.xml")
    lines.append("")
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def _google_site_verification(request):
    body = "google-site-verification: googledb8cba55fc2c39e4.html"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def _naver_site_verification(request):
    body = "naver-site-verification: naverf64974053e050b966dec6a8be99e4970.html"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def _naver_site_verification_www(request):
    body = "naver-site-verification: naver228461d9e717dc8f2780d4adc712f733.html"
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


# ── 레거시(구버전) 사이트 URL → 신버전 301 영구 리다이렉트 매핑 ──
# 구 사이트가 모바일(/m/…) 과 PC(/…) 경로 양쪽으로 색인되어 있어 두 접두사를 모두 처리한다.
# (개별 매물 viewsale_010100.html?uid= 는 DB 매핑이 필요해 별도 뷰로 처리)
_LEGACY_HTML_REDIRECTS = {
    'main/main.html': '/',
    'offering/offering_010100.html': '/equipment/create/',
    'job/job_010100.html': '/jobs/',
    'attachment/attachment_010100.html': '/?category=attachment',
    'community/community.html': '/',
    'etc/about.html': '/company/',
    'etc/terms.html': '/terms/',
    'etc/privacy.html': '/privacy/',
    'ad/ad_010100.html': '/billing/upgrade/',
    'member/login.html': '/login/',
}


def _build_legacy_redirects():
    patterns = []
    for prefix in ('m/', ''):
        # 구형 매물 목록/다이렉트 매물보기 등 viewsale/*.html 일괄 처리
        patterns.append(
            re_path(
                rf'^{prefix}viewsale/[a-zA-Z0-9_]+\.html$',
                legacy_redirect_viewsale_list,
            )
        )
        # 구형 PHP 매물 상세 (네이버 색인: view/sale_view.php?idx=)
        patterns.append(
            re_path(
                rf'^{prefix}view/sale_view\.php$',
                legacy_redirect_viewsale_list,
            )
        )
        # 구형 이용안내/이용약관 (네이버 색인: info/info_010100.html)
        patterns.append(
            re_path(
                rf'^{prefix}info/[a-zA-Z0-9_]+\.html$',
                RedirectView.as_view(url='/terms/', permanent=True),
            )
        )
        for old_path, new_url in _LEGACY_HTML_REDIRECTS.items():
            patterns.append(
                path(prefix + old_path, RedirectView.as_view(url=new_url, permanent=True))
            )
    # 위에서 못 잡은 나머지 /m/* 모바일 경로는 홈으로 (반드시 마지막)
    patterns.append(re_path(r'^m/.*$', RedirectView.as_view(url='/', permanent=True)))
    return patterns


admin.site.site_url = "/admin/view-site/"

urlpatterns = [
    path('googledb8cba55fc2c39e4.html', _google_site_verification, name='google_site_verification'),
    path(
        'naverf64974053e050b966dec6a8be99e4970.html',
        _naver_site_verification,
        name='naver_site_verification',
    ),
    path(
        'naver228461d9e717dc8f2780d4adc712f733.html',
        _naver_site_verification_www,
        name='naver_site_verification_www',
    ),
    path('robots.txt', _robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('admin/view-site/', _admin_view_site, name='admin_view_site'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # 소셜 로그인: /accounts/login/ 에서 카카오/네이버
    # 소셜 콜백 별칭: 개발자센터 등록 URL을 /auth/... 로 써도 동작하게 함
    path('auth/kakao/callback', lambda request: _social_callback_alias(request, 'kakao')),
    path('auth/naver/callback', lambda request: _social_callback_alias(request, 'naver')),
    # ── 레거시 사이트 URL → 신버전 301 (모바일 /m/… + PC /… 양쪽) ──
    *_build_legacy_redirects(),
    path('chat/', include('chat.urls')),
    path('soil/', include('soil.urls')),
    path('rental/', include('rental.urls')),
    path('trust/', include('trust.urls')),
    path('billing/', include('billing.urls')),
    path('', include('equipment.urls')),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('signup/check-username/', check_username, name='check_username'),
    path('signup/', signup, name='signup'),
    path('find-username/', find_username, name='find_username'),
    # 비밀번호 찾기(재설정)
    path('password-reset/', lambda request: (
        _redirect_authenticated_to_mypage(request)
        or auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            form_class=MigratedPasswordResetForm,
            success_url='/password-reset/done/'
        )(request)
    ), name='password_reset'),
    path('password-reset/done/', lambda request: (
        _redirect_authenticated_to_mypage(request)
        or auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html'
        )(request)
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html',
        success_url='/password-reset-complete/'
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
