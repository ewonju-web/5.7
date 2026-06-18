"""
자동 정기결제 청구 (토스 빌링키).

next_billing_at 이 지난 ACTIVE 빌링키를 찾아 토스에 청구하고,
성공 시 멤버십을 연장(fulfill)하고 다음 청구일을 갱신한다.
실패하면 fail_count 를 올리고, 한도(기본 3회) 초과 시 빌링키를 FAILED 로 비활성화한다.

크론 예시 (매일 새벽 4시):
    0 4 * * * cd /srv/excavator && venv/bin/python manage.py charge_due_billing >> /var/log/gn_billing.log 2>&1
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from billing.models import (
    BillingKey,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentStatus,
)
from billing.services import toss
from billing.services.fulfillment import fulfill_billing_payment

MAX_FAIL = 3
PG_PROVIDER = "toss"


def _order_id() -> str:
    return "GNB" + timezone.now().strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:8]


class Command(BaseCommand):
    help = "기한이 도래한 자동 정기결제(빌링키)를 청구합니다."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="청구하지 않고 대상만 출력")
        parser.add_argument("--limit", type=int, default=500, help="한 번에 처리할 최대 건수")

    def handle(self, *args, **opts):
        now = timezone.now()
        dry = opts["dry_run"]
        qs = (
            BillingKey.objects.filter(status=BillingKey.STATUS_ACTIVE, next_billing_at__lte=now)
            .select_related("user", "product")
            .order_by("next_billing_at")[: opts["limit"]]
        )
        total = qs.count() if hasattr(qs, "count") else len(qs)
        self.stdout.write(f"[charge_due_billing] 대상 {total}건 (now={now.isoformat()})")

        ok = fail = 0
        for bk in qs:
            label = f"BillingKey#{bk.id} user={bk.user_id} plan={bk.plan} {bk.amount}원"
            if dry:
                self.stdout.write(f"  - (dry) {label} next={bk.next_billing_at}")
                continue

            order_id = _order_id()
            order_name = f"굴삭기나라 프리미엄 {'연간' if bk.plan == BillingKey.PLAN_YEARLY else '월간'} 자동결제"
            try:
                charged = toss.charge_billing_key(
                    bk.billing_key, bk.customer_key, int(bk.amount), order_id, order_name,
                    customer_email=(bk.user.email or ""),
                    customer_name=(bk.user.get_full_name() or bk.user.username or ""),
                )
            except toss.TossPaymentError as exc:
                fail += 1
                bk.fail_count = (bk.fail_count or 0) + 1
                if bk.fail_count >= MAX_FAIL:
                    bk.status = BillingKey.STATUS_FAILED
                bk.save(update_fields=["fail_count", "status", "updated_at"])
                self.stderr.write(f"  ✗ {label} 실패({exc.code}) fail_count={bk.fail_count}")
                continue

            paid_at = timezone.now()
            with transaction.atomic():
                order = Order.objects.create(
                    user=bk.user,
                    order_number=order_id,
                    status=OrderStatus.PENDING,
                    total_amount=Decimal(int(bk.amount)),
                )
                OrderItem.objects.create(
                    order=order, product=bk.product, quantity=1,
                    unit_price=Decimal(int(bk.amount)),
                    metadata={"plan": bk.plan, "mode": "auto", "billing_key_id": bk.id, "recurring": True},
                )
                payment = Payment.objects.create(
                    order=order, pg_provider=PG_PROVIDER,
                    pg_tid=charged.get("paymentKey") or "",
                    amount=Decimal(int(bk.amount)),
                    status=PaymentStatus.SUCCESS, paid_at=paid_at, raw_response=charged,
                )
                days = 365 if bk.plan == BillingKey.PLAN_YEARLY else 30
                bk.last_charged_at = paid_at
                bk.next_billing_at = (bk.next_billing_at or paid_at) + timedelta(days=days)
                # 밀린 경우 미래로 보정
                while bk.next_billing_at <= paid_at:
                    bk.next_billing_at += timedelta(days=days)
                bk.fail_count = 0
                bk.save(update_fields=["last_charged_at", "next_billing_at", "fail_count", "updated_at"])

            fulfill_billing_payment(payment, auto_renew=True)
            ok += 1
            self.stdout.write(f"  ✓ {label} 청구완료 next={bk.next_billing_at}")

        self.stdout.write(self.style.SUCCESS(f"[charge_due_billing] 완료: 성공 {ok} · 실패 {fail}"))
