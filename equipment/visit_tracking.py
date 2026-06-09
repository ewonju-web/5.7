"""방문 추적 미들웨어 공통 유틸."""

SKIP_PREFIXES = (
    "/admin/",
    "/static/",
    "/media/",
    "/index/load-more/",
    "/favicon",
)
SKIP_EXACT = {"/robots.txt", "/health", "/health/"}


def client_ip(request) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def should_skip_path(request) -> bool:
    path = request.path or ""
    if path in SKIP_EXACT:
        return True
    if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = (request.headers.get("Accept") or "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False
