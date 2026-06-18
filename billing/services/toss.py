"""
토스페이먼츠 API 클라이언트.

- 1회 결제 승인:      confirm_payment(payment_key, order_id, amount)
- 결제 취소/환불:     cancel_payment(payment_key, reason, cancel_amount=None)
- 자동결제 빌링키 발급: issue_billing_key(auth_key, customer_key)
- 자동결제 승인(청구):  charge_billing_key(billing_key, customer_key, amount, order_id, order_name, ...)

시크릿 키는 `Basic base64("{secret}:")` 로 인증합니다(키 뒤 콜론 필수).
모든 함수는 성공 시 토스 응답(dict)을 반환하고, 실패 시 TossPaymentError 를 던집니다.
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 15  # seconds


class TossPaymentError(Exception):
    """토스 API 오류. code/message/http_status/raw 보관."""

    def __init__(self, message: str, *, code: str = "", http_status: int = 0, raw: Any = None):
        super().__init__(message)
        self.code = code or "UNKNOWN"
        self.message = message
        self.http_status = http_status
        self.raw = raw


def _auth_header() -> str:
    secret = (getattr(settings, "TOSS_SECRET_KEY", "") or "").strip()
    token = base64.b64encode(f"{secret}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _base_url() -> str:
    return (getattr(settings, "TOSS_API_BASE", "https://api.tosspayments.com") or "").rstrip("/")


def _request(method: str, path: str, *, body: Optional[dict] = None, idempotency_key: str = "") -> dict:
    url = f"{_base_url()}{path}"
    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            data=json.dumps(body) if body is not None else None,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.exception("토스 API 통신 오류: %s %s", method, path)
        raise TossPaymentError(f"결제 서버 통신 오류: {exc}", code="NETWORK_ERROR") from exc

    try:
        data = resp.json() if resp.content else {}
    except ValueError:
        data = {"raw_text": resp.text}

    if resp.status_code >= 400:
        code = (data.get("code") if isinstance(data, dict) else "") or f"HTTP_{resp.status_code}"
        message = (data.get("message") if isinstance(data, dict) else "") or "결제 처리 중 오류가 발생했습니다."
        logger.warning("토스 API 오류 %s %s -> %s %s", method, path, code, message)
        raise TossPaymentError(message, code=code, http_status=resp.status_code, raw=data)

    return data if isinstance(data, dict) else {"data": data}


# --- 1회 결제 ---
def confirm_payment(payment_key: str, order_id: str, amount: int) -> dict:
    """결제창에서 인증된 결제를 최종 승인. 성공 시 status=DONE 응답."""
    return _request(
        "POST",
        "/v1/payments/confirm",
        body={"paymentKey": payment_key, "orderId": order_id, "amount": int(amount)},
        idempotency_key=f"confirm-{order_id}",
    )


def cancel_payment(payment_key: str, reason: str, cancel_amount: Optional[int] = None) -> dict:
    """결제 취소/부분취소."""
    body: dict = {"cancelReason": reason or "고객 요청"}
    if cancel_amount is not None:
        body["cancelAmount"] = int(cancel_amount)
    return _request("POST", f"/v1/payments/{payment_key}/cancel", body=body)


# --- 자동결제(빌링) ---
def issue_billing_key(auth_key: str, customer_key: str) -> dict:
    """카드 등록(빌링 인증) 후 빌링키 발급. 응답에 billingKey, card 정보 포함."""
    return _request(
        "POST",
        "/v1/billing/authorizations/issue",
        body={"authKey": auth_key, "customerKey": customer_key},
    )


def charge_billing_key(
    billing_key: str,
    customer_key: str,
    amount: int,
    order_id: str,
    order_name: str,
    *,
    customer_email: str = "",
    customer_name: str = "",
    tax_free_amount: int = 0,
) -> dict:
    """발급된 빌링키로 결제 승인(정기 청구)."""
    body: dict = {
        "customerKey": customer_key,
        "amount": int(amount),
        "orderId": order_id,
        "orderName": order_name,
        "taxFreeAmount": int(tax_free_amount),
    }
    if customer_email:
        body["customerEmail"] = customer_email
    if customer_name:
        body["customerName"] = customer_name
    return _request(
        "POST",
        f"/v1/billing/{billing_key}",
        body=body,
        idempotency_key=f"billing-{order_id}",
    )


def get_payment(payment_key: str) -> dict:
    """결제 단건 조회(검증·웹훅 처리용)."""
    return _request("GET", f"/v1/payments/{payment_key}")
