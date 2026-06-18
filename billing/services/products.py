"""프리미엄 요금제(상품) 정의·시드."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from ..models import Product, ProductType

PREMIUM_MONTHLY_CODE = "PREMIUM_MONTHLY"
PREMIUM_YEARLY_CODE = "PREMIUM_YEARLY"


def _monthly_price() -> int:
    return int(getattr(settings, "PREMIUM_MONTHLY_PRICE", 40000) or 40000)


def _yearly_price() -> int:
    return int(getattr(settings, "PREMIUM_YEARLY_PRICE", 400000) or 400000)


def ensure_premium_products() -> dict[str, Product]:
    """프리미엄 월/연 상품이 없으면 생성하고, 가격은 settings 기준으로 동기화."""
    monthly, _ = Product.objects.get_or_create(
        code=PREMIUM_MONTHLY_CODE,
        defaults={
            "name": "프리미엄 유료회원 (월)",
            "product_type": ProductType.DEALER_MEMBERSHIP,
            "duration_days": 30,
            "price": Decimal(_monthly_price()),
            "is_recurring": False,
            "is_active": True,
            "sort_order": 1,
        },
    )
    yearly, _ = Product.objects.get_or_create(
        code=PREMIUM_YEARLY_CODE,
        defaults={
            "name": "프리미엄 유료회원 (연)",
            "product_type": ProductType.DEALER_MEMBERSHIP,
            "duration_days": 365,
            "price": Decimal(_yearly_price()),
            "is_recurring": False,
            "is_active": True,
            "sort_order": 2,
        },
    )
    # 가격이 settings 와 다르면 맞춤(운영 중 .env 로 조정 가능)
    if int(monthly.price) != _monthly_price():
        monthly.price = Decimal(_monthly_price())
        monthly.save(update_fields=["price", "updated_at"])
    if int(yearly.price) != _yearly_price():
        yearly.price = Decimal(_yearly_price())
        yearly.save(update_fields=["price", "updated_at"])

    return {"monthly": monthly, "yearly": yearly}


def get_product_for_plan(plan: str) -> Product:
    products = ensure_premium_products()
    return products["yearly"] if plan == "yearly" else products["monthly"]
