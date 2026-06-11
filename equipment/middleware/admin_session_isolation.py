from django.contrib.auth.models import AnonymousUser


class AdminSessionIsolationMiddleware:
    """
    관리자(staff) 세션은 /admin/ 에서만 로그인 사용자로 동작한다.
    일반 서비스 경로에서는 익명으로 보이게만 하고 세션은 유지해,
    매물 미리보기 후에도 /admin/ 작업(저장 등)을 이어갈 수 있게 한다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        path = (getattr(request, "path", "") or "").strip()

        if (
            user
            and user.is_authenticated
            and (user.is_staff or user.is_superuser)
            and not path.startswith("/admin/")
        ):
            request.admin_user = user
            request.user = AnonymousUser()

        return self.get_response(request)
