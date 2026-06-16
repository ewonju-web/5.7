"""방문 경로·회원·체류 시간 — 어드민 VisitSession / VisitPageLog 기록."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils.timezone import now

from ..models import VisitPageLog, VisitSession
from ..visit_tracking import SKIP_EXACT, SKIP_PREFIXES, client_ip, is_bot_request


class VisitAnalyticsMiddleware:
    SESSION_TIMEOUT_SECONDS = 30 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if self._should_track(request, response):
            self._record_visit(request)
        return response

    def _should_track(self, request, response) -> bool:
        if is_bot_request(request):
            return False
        if response.status_code >= 400:
            return False
        path = request.path or ""
        if path in SKIP_EXACT:
            return False
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return False
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return False
        accept = (request.headers.get("Accept") or "").lower()
        if "application/json" in accept and "text/html" not in accept:
            return False
        return True

    def _record_visit(self, request) -> None:
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key
        if not session_key:
            return

        ip = client_ip(request)
        if not ip:
            return

        current_time = now()
        path = (request.path or "/")[:500]
        query = (request.META.get("QUERY_STRING") or "")[:500]
        referer = (request.META.get("HTTP_REFERER") or "")[:2000]
        user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:300]
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

        try:
            with transaction.atomic():
                visit = (
                    VisitSession.objects.select_for_update()
                    .filter(
                        django_session_key=session_key,
                        last_seen_at__gte=current_time - timedelta(seconds=self.SESSION_TIMEOUT_SECONDS),
                    )
                    .order_by("-last_seen_at")
                    .first()
                )

                if visit is None:
                    visit = VisitSession.objects.create(
                        django_session_key=session_key,
                        user=user,
                        ip_address=ip,
                        user_agent=user_agent,
                        referer=referer,
                        landing_path=path,
                        last_path=path,
                        last_seen_at=current_time,
                        duration_seconds=0,
                        page_view_count=1,
                    )
                    VisitPageLog.objects.create(
                        session=visit,
                        path=path,
                        query_string=query,
                        referer=referer,
                        user=user,
                        ip_address=ip,
                    )
                    return

                last_log = VisitPageLog.objects.filter(
                    session_id=visit.pk,
                    duration_seconds__isnull=True,
                ).order_by("-viewed_at").first()
                if last_log:
                    delta = int((current_time - last_log.viewed_at).total_seconds())
                    last_log.duration_seconds = max(0, min(delta, self.SESSION_TIMEOUT_SECONDS))
                    last_log.save(update_fields=["duration_seconds"])

                VisitPageLog.objects.create(
                    session=visit,
                    path=path,
                    query_string=query,
                    referer=referer,
                    user=user,
                    ip_address=ip,
                )

                duration = int((current_time - visit.started_at).total_seconds())
                session_updates = {
                    "last_path": path,
                    "last_seen_at": current_time,
                    "duration_seconds": max(0, duration),
                    "page_view_count": visit.page_view_count + 1,
                }
                if user:
                    session_updates["user_id"] = user.pk
                VisitSession.objects.filter(pk=visit.pk).update(**session_updates)
        except Exception:
            pass
