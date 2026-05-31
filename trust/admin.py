from django.contrib import admin

from .models import MannerScore, ReviewBadTag, SellerReport, SellerReview
from .services import recalculate_manner_score


class ReviewBadTagInline(admin.TabularInline):
    model = ReviewBadTag
    extra = 0


@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ['seller', 'reviewer', 'review_type', 'equipment', 'created_at']
    list_filter = ['review_type', 'created_at']
    search_fields = ['seller__username', 'reviewer__username', 'comment']
    inlines = [ReviewBadTagInline]
    raw_id_fields = ['seller', 'reviewer', 'equipment']


@admin.register(SellerReport)
class SellerReportAdmin(admin.ModelAdmin):
    list_display = ['seller', 'reason', 'reporter', 'reporter_ip', 'is_handled', 'created_at']
    list_filter = ['reason', 'is_handled', 'created_at']
    search_fields = ['seller__username', 'detail', 'reporter_ip']
    raw_id_fields = ['seller', 'reporter', 'equipment']
    actions = ['mark_handled']

    @admin.action(description='선택 신고 처리 완료')
    def mark_handled(self, request, queryset):
        sellers = set(queryset.values_list('seller_id', flat=True))
        queryset.update(is_handled=True)
        for seller_id in sellers:
            from django.contrib.auth import get_user_model

            seller = get_user_model().objects.filter(pk=seller_id).first()
            if seller:
                recalculate_manner_score(seller)


@admin.register(MannerScore)
class MannerScoreAdmin(admin.ModelAdmin):
    list_display = ['user', 'score', 'tier', 'total_reviews', 'good_count', 'bad_count', 'updated_at']
    list_filter = ['tier']
    search_fields = ['user__username']
    raw_id_fields = ['user']
