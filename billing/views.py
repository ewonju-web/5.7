"""
토스페이먼츠 결제 흐름 (프리미엄 유료회원).

지원: 1회 결제(월/연) + 자동 정기결제(월/연).

흐름
- 1회 결제:
    premium_plans → checkout(once) [Order PENDING 생성]
    → 토스 결제창 → success(once) [confirm → Payment SUCCESS → 멤버십 연장]
- 자동 정기결제:
    premium_plans → checkout(auto)
    → 토스 카드등록(requestBillingAuth) → success(auto)
      [빌링키 발급·저장 → 첫 청구 → 멤버십 연장 → next_billing_at 설정]
    → 이후 management command(charge_due_billing)가 주기적으로 청구
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (
    BillingKey,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
)
from .services import toss
from .services.fulfillment import fulfill_billing_payment
from .services.products import ensure_premium_products, get_product_for_plan

logger = logging.getLogger(__name__)

PG_PROVIDER = "toss"
VALID_PLANS = ("monthly", "yearly")
VALID_MODES = ("once", "auto")


def _plan_label(plan: str) -> str:
    return "연간" if plan == "yearly" else "월간"


def _order_name(plan: str, mode: str) -> str:
    base = f"굴삭기나라 프리미엄 {_plan_label(plan)}"
    return f"{base} 자동결제" if mode == "auto" else base


def _new_order_number() -> str:
    """토스 orderId(6~64자, 영숫자-_) 규칙에 맞는 고유 주문번호."""
    return "GN" + timezone.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:10]


def _customer_key(user) -> str:
    """토스 customerKey: 사용자별 안정적·비유추 값."""
    return f"gncust_{user.id}_{secrets.token_hex(8)}"


def _abs_url(request, name: str, query: str = "") -> str:
    url = request.build_absolute_uri(reverse(name))
    return f"{url}?{query}" if query else url


# --------------------------------------------------------------------------
# 요금제 선택
# --------------------------------------------------------------------------
@login_required
def premium_plans(request):
    """프리미엄 요금제·결제수단 선택 페이지."""
    ensure_premium_products()
    monthly_price = int(getattr(settings, "PREMIUM_MONTHLY_PRICE", 40000))
    yearly_price = int(getattr(settings, "PREMIUM_YEARLY_PRICE", 400000))
    return render(request, "billing/premium_plans.html", {
        "monthly_price": monthly_price,
        "yearly_price": yearly_price,
        "yearly_monthly_equiv": round(yearly_price / 12),
        "toss_is_live": getattr(settings, "TOSS_IS_LIVE", False),
    })


# --------------------------------------------------------------------------
# 결제창 진입 (체크아웃)
# --------------------------------------------------------------------------
@login_required
def checkout(request):
    """plan·mode 검증 후 토스 SDK 페이지를 렌더."""
    plan = (request.GET.get("plan") or "monthly").strip()
    mode = (request.GET.get("mode") or "once").strip()
    if plan not in VALID_PLANS or mode not in VALID_MODES:
        return HttpResponseBadRequest("잘못된 요금제/결제수단입니다.")

    product = get_product_for_plan(plan)
    amount = int(product.price)
    order_name = _order_name(plan, mode)
    customer_key = _customer_key(request.user)
    order_id = _new_order_number()

    if mode == "once":
        # 금액 위변조 방지를 위해 서버에서 Order 를 먼저 만들어 둔다.
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                order_number=order_id,
                status=OrderStatus.PENDING,
                total_amount=Decimal(amount),
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=1,
                unit_price=Decimal(amount),
                metadata={"plan": plan, "mode": mode},
            )
        success_q = f"mode=once&plan={plan}"
    else:
        # 자동결제: 카드등록 성공 시 success 에서 빌링키 발급·첫 청구·Order 생성
        success_q = f"mode=auto&plan={plan}"

    ctx = {
        "client_key": getattr(settings, "TOSS_CLIENT_KEY", ""),
        "is_widget_key": getattr(settings, "TOSS_IS_WIDGET_KEY", True),
        "mode": mode,
        "plan": plan,
        "plan_label": _plan_label(plan),
        "amount": amount,
        "order_id": order_id,
        "order_name": order_name,
        "customer_key": customer_key,
        "customer_email": (request.user.email or ""),
        "customer_name": (request.user.get_full_name() or request.user.username or ""),
        "success_url": _abs_url(request, "billing_success", success_q),
        "fail_url": _abs_url(request, "billing_fail"),
    }
    return render(request, "billing/checkout.html", ctx)


# --------------------------------------------------------------------------
# 결제 성공 콜백
# --------------------------------------------------------------------------
@login_required
def billing_success(request):
    mode = (request.GET.get("mode") or "once").strip()
    plan = (request.GET.get("plan") or "monthly").strip()
    if plan not in VALID_PLANS:
        plan = "monthly"

    if mode == "auto":
        return _success_auto(request, plan)
    return _success_once(request)


def _success_once(request):
    payment_key = (request.GET.get("paymentKey") or "").strip()
    order_id = (request.GET.get("orderId") or "").strip()
    amount_raw = (request.GET.get("amount") or "").strip()
    if not (payment_key and order_id and amount_raw):
        messages.error(request, "결제 정보가 올바르지 않습니다.")
        return redirect("billing_premium")

    try:
        amount = int(amount_raw)
    except ValueError:
        return HttpResponseBadRequest("잘못된 결제 금액입니다.")

    try:
        order = Order.objects.get(order_number=order_id, user=request.user)
    except Order.DoesNotExist:
        raise Http404("주문을 찾을 수 없습니다.")

    # 금액 위변조 검증
    if int(order.total_amount) != amount:
        logger.warning("결제 금액 불일치 order=%s db=%s req=%s", order_id, order.total_amount, amount)
        messages.error(request, "결제 금액이 일치하지 않습니다.")
        return redirect("billing_premium")

    # 이미 처리된 주문이면 멱등 처리
    if order.status == OrderStatus.PAID:
        return render(request, "billing/success.html", {"order": order, "plan": None})

    try:
        data = toss.confirm_payment(payment_key, order_id, amount)
    except toss.TossPaymentError as exc:
        logger.warning("토스 승인 실패 order=%s code=%s", order_id, exc.code)
        Payment.objects.create(
            order=order, pg_provider=PG_PROVIDER, pg_tid=payment_key,
            amount=Decimal(amount), status=PaymentStatus.FAILED, raw_response=exc.raw,
        )
        messages.error(request, f"결제 승인에 실패했습니다. ({exc.message})")
        return redirect("billing_fail")

    paid_at = timezone.now()
    payment = Payment.objects.create(
        order=order,
        pg_provider=PG_PROVIDER,
        pg_tid=data.get("paymentKey") or payment_key,
        amount=Decimal(amount),
        status=PaymentStatus.SUCCESS,
        paid_at=paid_at,
        raw_response=data,
    )
    fulfill_billing_payment(payment, auto_renew=False)
    return render(request, "billing/success.html", {"order": order, "auto": False})


def _success_auto(request, plan):
    auth_key = (request.GET.get("authKey") or "").strip()
    customer_key = (request.GET.get("customerKey") or "").strip()
    if not (auth_key and customer_key):
        messages.error(request, "카드 등록 정보가 올바르지 않습니다.")
        return redirect("billing_premium")

    product = get_product_for_plan(plan)
    amount = int(product.price)

    # 1) 빌링키 발급
    try:
        issue = toss.issue_billing_key(auth_key, customer_key)
    except toss.TossPaymentError as exc:
        logger.warning("빌링키 발급 실패 code=%s", exc.code)
        messages.error(request, f"카드 등록에 실패했습니다. ({exc.message})")
        return redirect("billing_fail")

    billing_key = issue.get("billingKey") or ""
    card = issue.get("card") or {}
    if not billing_key:
        messages.error(request, "빌링키 발급에 실패했습니다.")
        return redirect("billing_fail")

    plan_const = BillingKey.PLAN_YEARLY if plan == "yearly" else BillingKey.PLAN_MONTHLY

    with transaction.atomic():
        bk = BillingKey.objects.create(
            user=request.user,
            customer_key=customer_key,
            billing_key=billing_key,
            product=product,
            plan=plan_const,
            amount=amount,
            card_company=card.get("issuerCode") or card.get("company") or "",
            card_number_masked=card.get("number") or "",
            status=BillingKey.STATUS_ACTIVE,
            next_billing_at=timezone.now(),  # 첫 청구 직후 갱신
        )

    # 2) 첫 회 즉시 청구
    order_id = _new_order_number()
    try:
        charged = toss.charge_billing_key(
            billing_key, customer_key, amount, order_id, _order_name(plan, "auto"),
            customer_email=(request.user.email or ""),
            customer_name=(request.user.get_full_name() or request.user.username or ""),
        )
    except toss.TossPaymentError as exc:
        logger.warning("첫 자동결제 청구 실패 code=%s", exc.code)
        bk.status = BillingKey.STATUS_FAILED
        bk.fail_count = 1
        bk.save(update_fields=["status", "fail_count", "updated_at"])
        messages.error(request, f"첫 결제에 실패했습니다. 카드를 확인해 주세요. ({exc.message})")
        return redirect("billing_fail")

    paid_at = timezone.now()
    with transaction.atomic():
        order = Order.objects.create(
            user=request.user,
            order_number=order_id,
            status=OrderStatus.PENDING,
            total_amount=Decimal(amount),
        )
        OrderItem.objects.create(
            order=order, product=product, quantity=1, unit_price=Decimal(amount),
            metadata={"plan": plan, "mode": "auto", "billing_key_id": bk.id},
        )
        payment = Payment.objects.create(
            order=order,
            pg_provider=PG_PROVIDER,
            pg_tid=charged.get("paymentKey") or "",
            amount=Decimal(amount),
            status=PaymentStatus.SUCCESS,
            paid_at=paid_at,
            raw_response=charged,
        )
        days = 365 if plan == "yearly" else 30
        bk.last_charged_at = paid_at
        bk.next_billing_at = paid_at + timedelta(days=days)
        bk.fail_count = 0
        bk.save(update_fields=["last_charged_at", "next_billing_at", "fail_count", "updated_at"])

    fulfill_billing_payment(payment, auto_renew=True)
    return render(request, "billing/success.html", {"order": order, "auto": True})


@login_required
def billing_fail(request):
    code = (request.GET.get("code") or "").strip()
    message = (request.GET.get("message") or "결제가 취소되었거나 실패했습니다.").strip()
    return render(request, "billing/fail.html", {"code": code, "message": message})


# --------------------------------------------------------------------------
# 자동결제 해지
# --------------------------------------------------------------------------
@login_required
@require_POST
def cancel_auto_billing(request):
    """자동 정기결제 해지. 남은 이용기간은 유지하고 다음 청구만 중단."""
    bk = (
        BillingKey.objects.filter(user=request.user, status=BillingKey.STATUS_ACTIVE)
        .order_by("-created_at")
        .first()
    )
    if not bk:
        messages.info(request, "활성화된 자동결제가 없습니다.")
        return redirect("my_page")

    bk.status = BillingKey.STATUS_CANCELLED
    bk.cancelled_at = timezone.now()
    bk.save(update_fields=["status", "cancelled_at", "updated_at"])

    from .models import DealerMembership
    DealerMembership.objects.filter(user=request.user).update(is_auto_renew=False)

    messages.success(request, "자동결제가 해지되었습니다. 남은 이용기간은 그대로 유지됩니다.")
    return redirect("my_page")


# --------------------------------------------------------------------------
# 웹훅 (선택) — 상태 동기화용
# --------------------------------------------------------------------------
@csrf_exempt
def toss_webhook(request):
    """토스 결제 상태 변경 웹훅. 현재는 수신·기록만(향후 환불 동기화 등 확장)."""
    if request.method != "POST":
        return HttpResponseBadRequest("POST only")
    try:
        import json
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}
    logger.info("토스 웹훅 수신: %s", payload.get("eventType") or payload)
    return JsonResponse({"ok": True})
