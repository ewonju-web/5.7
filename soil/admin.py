from django.contrib import admin
from .models import SoilPost
from .antispam import is_obvious_soil_spam


@admin.action(description='선택 글 비활성화(숨김)')
def deactivate_posts(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.action(description='봇 도배 의심 글 일괄 비활성화')
def deactivate_obvious_spam(modeladmin, request, queryset):
    ids = [p.pk for p in queryset if is_obvious_soil_spam(p)]
    SoilPost.objects.filter(pk__in=ids).update(is_active=False)


@admin.register(SoilPost)
class SoilPostAdmin(admin.ModelAdmin):
    list_display = ('id', 'post_type', 'material_type', 'title', 'location', 'quantity', 'contact', 'author', 'created_at', 'is_active')
    list_filter = ('material_type', 'post_type', 'is_active')
    search_fields = ('title', 'location', 'contact', 'note', 'description')
    date_hierarchy = 'created_at'
    list_editable = ('is_active',)
    actions = (deactivate_posts, deactivate_obvious_spam)
