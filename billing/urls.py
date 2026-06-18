"""billing 결제 라우트 (토스페이먼츠). 프로젝트 urls 에서 'billing/' 로 include."""
from django.urls import path

from . import views

urlpatterns = [
    path("premium/", views.premium_plans, name="billing_premium"),
    path("checkout/", views.checkout, name="billing_checkout"),
    path("success/", views.billing_success, name="billing_success"),
    path("fail/", views.billing_fail, name="billing_fail"),
    path("cancel-auto/", views.cancel_auto_billing, name="billing_cancel_auto"),
    path("webhook/toss/", views.toss_webhook, name="billing_toss_webhook"),
]
