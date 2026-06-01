# -*- coding: utf-8 -*-
"""할부 상담 신청: reCAPTCHA v3 검증 및 IP 요청 제한."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

FINANCE_CONSULT_CACHE_PREFIX = "finance_consult_rl:"
FINANCE_CONSULT_ACTION = "finance_consult"
FINANCE_CONSULT_RATE_LIMIT = 3
FINANCE_CONSULT_RATE_WINDOW = 60


def get_client_ip(request) -> str:
    """프록시(nginx) 뒤 클라이언트 IP."""
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip() or "unknown"


def recaptcha_configured() -> bool:
    site = (getattr(settings, "RECAPTCHA_SITE_KEY", "") or "").strip()
    secret = (getattr(settings, "RECAPTCHA_SECRET_KEY", "") or "").strip()
    return bool(site and secret)


def verify_recaptcha_v3(token: str, remote_ip: str | None = None) -> tuple[bool, str]:
    secret = (getattr(settings, "RECAPTCHA_SECRET_KEY", "") or "").strip()
    if not secret:
        if getattr(settings, "DEBUG", False):
            return True, ""
        return False, "보안 검증이 설정되지 않았습니다. 관리자에게 문의해 주세요."

    token = (token or "").strip()
    if not token:
        return False, "보안 검증에 실패했습니다. 페이지를 새로고침한 뒤 다시 시도해 주세요."

    min_score = float(getattr(settings, "RECAPTCHA_MIN_SCORE", 0.5) or 0.5)
    payload = urllib.parse.urlencode(
        {
            "secret": secret,
            "response": token,
            "remoteip": remote_ip or "",
        }
    ).encode("utf-8")

    try:
        req = urllib.request.Request(
            "https://www.google.com/recaptcha/api/siteverify",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        logger.exception("reCAPTCHA verify request failed: %s", e)
        return False, "보안 검증 서버 연결에 실패했습니다. 잠시 후 다시 시도해 주세요."

    if not result.get("success"):
        codes = result.get("error-codes") or []
        logger.warning("reCAPTCHA verify failed: %s", codes)
        return False, "보안 검증에 실패했습니다. 다시 시도해 주세요."

    action = (result.get("action") or "").strip()
    if action and action != FINANCE_CONSULT_ACTION:
        logger.warning("reCAPTCHA action mismatch: %s", action)
        return False, "보안 검증에 실패했습니다."

    score = float(result.get("score") or 0)
    if score < min_score:
        logger.info("reCAPTCHA low score: %s (min=%s)", score, min_score)
        return False, "자동 입력으로 의심되어 요청을 차단했습니다. 잠시 후 다시 시도해 주세요."

    return True, ""


def check_finance_consult_rate_limit(ip: str) -> tuple[bool, str]:
    ip = (ip or "").strip() or "unknown"
    key = f"{FINANCE_CONSULT_CACHE_PREFIX}{ip}"
    try:
        count = cache.get(key, 0)
        if count >= FINANCE_CONSULT_RATE_LIMIT:
            return False, "요청이 너무 많습니다. 1분 후에 다시 시도해 주세요."
        if count == 0:
            cache.set(key, 1, FINANCE_CONSULT_RATE_WINDOW)
        else:
            cache.incr(key)
    except Exception as e:
        logger.exception("finance consult rate limit cache error: %s", e)
        return True, ""
    return True, ""
