from django.contrib import admin
from django import forms
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.formats import number_format
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django.conf import settings
import json
from urllib.parse import urlencode
from django.urls import reverse
from urllib.request import urlopen, Request
from .models import (
    Equipment, EquipmentImage, Profile, JobPost, ExamPost, ExamComment,
    Part, PartImage, PartsShop, DriverProfile, YoutubeContent,
    EquipmentFavorite, PartFavorite, Comment, DeletedListingLog, EquipmentType, EquipmentBumpLog,
    FinanceConsultation,
    ExcavatorEquipment, ForkliftEquipment, DumpEquipment, LoaderEquipment,
    CraneEquipment, AttachmentEquipment, OtherEquipment,
    VisitSession, VisitPageLog, VisitorCount, VisitorLog,
)
from django.contrib.admin.views.main import ERROR_FLAG
from .index_listing import (
    EXCAVATOR_ADMIN_QUERY_KEYS,
    apply_excavator_detail_filters,
    excavator_admin_filters_active,
    excavator_admin_preserved_params,
    parse_excavator_admin_filters,
)


# 굴삭기 어드민: 세부 유형·중량 코드 → 사용자 화면과 동일한 한글 라벨
_EXCAVATOR_SUB_TYPE_LABELS = {
    "EXC_TIRE": "타이어식",
    "EXC_CRAWLER": "크롤러식(체인)",
    "EXC_ATTACHMENT": "어테치먼트",
}
_EXCAVATOR_MANUFACTURERS = (
    "HD 현대", "두산", "볼보", "구보다", "얀마", "밥켓", "코츠마츠", "코벨코",
    "히타치", "케터피라", "존디어", "SANY",
)
_EXCAVATOR_WEIGHT_CLASS_LABELS = {
    "EXC_TIRE_LE_6": "03W 5~6 ton",
    "EXC_TIRE_LE_17": "06W 12~16 ton",
    "EXC_TIRE_LE_21": "08W 20~22 ton",
    "EXC_CR_LT_1": "1 ton 미만",
    "EXC_CR_LE_2": "2 ton 미만",
    "EXC_CR_LE_3_5": "3.5 ton 미만",
    "EXC_CR_LE_6_5": "5~6 ton 02급",
    "EXC_CR_LE_16": "12~16 ton 06급",
    "EXC_CR_EQ_20": "20~22 ton 08급",
    "EXC_CR_GE_30": "30~50 ton 10급 이상",
    "EXC_ATT_LT_1": "1톤 미만 (어테치)",
    "EXC_ATT_LE_2": "2톤 이하 (어테치)",
    "EXC_ATT_LE_3_5": "3.5톤 이하 (어테치)",
    "EXC_ATT_LE_6_5": "6.5톤 이하 (어테치)",
    "EXC_ATT_LE_16": "16톤 이하 (어테치)",
    "EXC_ATT_EQ_20": "20톤 (어테치)",
}


class EquipmentOwnerFilter(admin.SimpleListFilter):
    title = '작성자(소유)'
    parameter_name = 'equipment_owner'

    def lookups(self, request, model_admin):
        return [
            ('unclaimed', '미연결 (작성자 없음)'),
            ('claimed', '연결됨'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'unclaimed':
            return queryset.filter(author__isnull=True)
        if self.value() == 'claimed':
            return queryset.filter(author__isnull=False)
        return queryset


# 1. 매물 관리
class EquipmentImageInline(admin.TabularInline):
    model = EquipmentImage
    extra = 1
    show_change_link = True
    fields = ('image_preview', 'image')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if not obj or not getattr(obj, 'pk', None) or not getattr(obj, 'image', None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="width:72px;height:54px;object-fit:cover;border-radius:6px;border:1px solid #ddd;" alt="preview">',
                obj.image.url,
            )
        except Exception:
            return "-"
    image_preview.short_description = '미리보기'


@admin.register(EquipmentImage)
class EquipmentImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'equipment', 'image_preview', 'image')
    search_fields = ('equipment__model_name', 'equipment__author__username')
    list_select_related = ('equipment',)
    list_per_page = 100

    def image_preview(self, obj):
        if not obj or not getattr(obj, 'image', None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="width:84px;height:63px;object-fit:cover;border-radius:6px;border:1px solid #ddd;" alt="thumb">',
                obj.image.url,
            )
        except Exception:
            return "-"
    image_preview.short_description = '미리보기'


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'representative_image_preview', 'equipment_type', 'model_name', 'manufacturer', 'year_manufactured', 'listing_price_display',
        'current_location', 'vehicle_number', 'listing_status', 'is_sold', 'author',
        'unclaimed_phone_norm', 'ownership_claimed_at', 'last_bumped_at', 'created_at',
    ]
    list_filter = ('equipment_type', EquipmentOwnerFilter, 'author', 'listing_status', 'is_sold', 'manufacturer')
    search_fields = (
        '=id',
        '=legacy_listing_id',
        'model_name',
        'manufacturer',
        'current_location',
        'description',
        'author__username',
        'author__first_name',
        'author__last_name',
        'author__profile__phone',
        'unclaimed_phone_norm',
    )
    date_hierarchy = 'created_at'
    list_per_page = 50
    inlines = [EquipmentImageInline]
    list_editable = ('listing_status', 'is_sold')
    readonly_fields = ('created_at',)
    fieldsets = (
        (None, {'fields': ('author', 'equipment_type', 'model_name', 'manufacturer', 'year_manufactured', 'month_manufactured', 'operating_hours')}),
        ('가격·위치·차량번호', {'fields': ('listing_price', 'current_location', 'vehicle_number', 'description')}),
        ('미연결·소유권 이전', {
            'fields': ('unclaimed_phone_norm', 'ownership_claimed_at', 'legacy_listing_id'),
            'description': '작성자 없이 남길 때: 연락처 숫자만 입력. 가입자가 본인 전화로 「내 매물 찾기」에서 연결하면 작성자가 채워집니다.',
        }),
        ('상태', {'fields': ('listing_status', 'is_sold', 'password', 'created_at')}),
    )

    def listing_price_display(self, obj):
        if obj.listing_price is None:
            return "-"
        return f"{number_format(obj.listing_price, use_l10n=True)}원"
    listing_price_display.short_description = '판매가'

    def representative_image_preview(self, obj):
        """목록용 대표사진(등록 순 첫 장)."""
        first = None
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            imgs = obj._prefetched_objects_cache['images']
            first = imgs[0] if imgs else None
        if first is None:
            first = obj.images.order_by('id').first()
        if not first or not getattr(first, 'image', None):
            return "-"
        try:
            return format_html(
                '<img src="{}" style="width:72px;height:54px;object-fit:cover;border-radius:6px;border:1px solid #ddd;" alt="대표">',
                first.image.url,
            )
        except Exception:
            return "-"

    representative_image_preview.short_description = '대표사진'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            Prefetch('images', queryset=EquipmentImage.objects.order_by('id'))
        )

    def get_search_results(self, request, queryset, search_term):
        """
        기본 search_fields 결과 + 숫자 검색 보강.
        - 매물번호(id), 이관번호(legacy_listing_id)
        - 작성자 전화번호(author__profile__phone, 하이픈/공백 제거 후)
        """
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        term = (search_term or "").strip()
        digits = "".join(ch for ch in term if ch.isdigit())
        if digits:
            digit_qs = self.model.objects.filter(
                Q(id=int(digits)) |
                Q(legacy_listing_id=int(digits)) |
                Q(author__profile__phone__icontains=digits)
            )
            queryset = queryset | digit_qs
        return queryset, use_distinct


class EquipmentTypeProxyAdmin(EquipmentAdmin):
    equipment_type_value = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self.equipment_type_value:
            qs = qs.filter(equipment_type=self.equipment_type_value)
        return qs

    def save_model(self, request, obj, form, change):
        if self.equipment_type_value:
            obj.equipment_type = self.equipment_type_value
        super().save_model(request, obj, form, change)


@admin.register(ExcavatorEquipment)
class ExcavatorEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.EXCAVATOR
    change_list_template = "admin/equipment/excavatorequipment/change_list.html"
    list_display = [
        "id",
        "representative_image_preview",
        "equipment_type",
        "model_name",
        "manufacturer",
        "excavator_sub_type_display",
        "excavator_weight_class_display",
        "year_manufactured",
        "listing_price_display",
        "current_location",
        "vehicle_number",
        "listing_status",
        "is_sold",
        "author",
        "unclaimed_phone_norm",
        "ownership_claimed_at",
        "last_bumped_at",
        "created_at",
    ]
    list_filter = (
        EquipmentOwnerFilter,
        "author",
        "listing_status",
        "is_sold",
    )

    def _excavator_admin_filter_params(self, request):
        cached = getattr(request, "_gn_excavator_admin_filters", None)
        if cached is not None:
            return cached
        return parse_excavator_admin_filters(request)

    def _strip_excavator_admin_query_params(self, request):
        """ChangeList가 xsf_*를 모델 lookup으로 검증해 e=1 리다이렉트하는 것 방지."""
        if not any(k in request.GET for k in EXCAVATOR_ADMIN_QUERY_KEYS):
            return request
        params = parse_excavator_admin_filters(request)
        request._gn_excavator_admin_filters = params
        stripped = request.GET.copy()
        for key in EXCAVATOR_ADMIN_QUERY_KEYS:
            stripped.pop(key, None)
        if ERROR_FLAG in stripped:
            stripped.pop(ERROR_FLAG, None)
        request.GET = stripped
        return request

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        params = self._excavator_admin_filter_params(request)
        if excavator_admin_filters_active(params):
            qs = apply_excavator_detail_filters(qs, **params)
        return qs

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        params = parse_excavator_admin_filters(request)
        request = self._strip_excavator_admin_query_params(request)
        preserved = excavator_admin_preserved_params(request)
        clear_url = reverse("admin:equipment_excavatorequipment_changelist")
        if preserved:
            clear_url = f"{clear_url}?{urlencode(preserved, doseq=True)}"
        extra_context.update({
            "excavator_filter": params,
            "excavator_filter_active": excavator_admin_filters_active(params),
            "excavator_manufacturers": _EXCAVATOR_MANUFACTURERS,
            "excavator_filter_years": list(range(2000, 2027)),
            "excavator_preserved_params": preserved,
            "excavator_filter_clear_url": clear_url,
            "excavator_sub_type_labels": _EXCAVATOR_SUB_TYPE_LABELS,
            "excavator_weight_class_labels": _EXCAVATOR_WEIGHT_CLASS_LABELS,
        })
        return super().changelist_view(request, extra_context=extra_context)

    def excavator_sub_type_display(self, obj):
        code = (obj.sub_type or "").strip()
        if not code:
            return "-"
        return _EXCAVATOR_SUB_TYPE_LABELS.get(code, code)

    excavator_sub_type_display.short_description = "세부 유형"
    excavator_sub_type_display.admin_order_field = "sub_type"

    def excavator_weight_class_display(self, obj):
        code = (obj.weight_class or "").strip()
        if not code:
            return "-"
        return _EXCAVATOR_WEIGHT_CLASS_LABELS.get(code, code)

    excavator_weight_class_display.short_description = "중량 구분"
    excavator_weight_class_display.admin_order_field = "weight_class"


@admin.register(ForkliftEquipment)
class ForkliftEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.FORKLIFT


@admin.register(DumpEquipment)
class DumpEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.DUMP


@admin.register(LoaderEquipment)
class LoaderEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.LOADER


@admin.register(CraneEquipment)
class CraneEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.CRANE


@admin.register(AttachmentEquipment)
class AttachmentEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.ATTACHMENT


@admin.register(OtherEquipment)
class OtherEquipmentAdmin(EquipmentTypeProxyAdmin):
    equipment_type_value = EquipmentType.OTHER


# 2. 부품 관리 (사진 포함)
class PartImageInline(admin.TabularInline):
    model = PartImage
    extra = 3
    show_change_link = True


@admin.register(Part)
class PartAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'created_at']
    list_filter = ['category']
    search_fields = ('title', 'location', 'compatibility', 'description')
    date_hierarchy = 'created_at'
    list_per_page = 50
    inlines = [PartImageInline]

    def name(self, obj):
        return obj.title
    name.short_description = "name"


@admin.register(PartsShop)
class PartsShopAdmin(admin.ModelAdmin):
    class PartsShopAdminForm(forms.ModelForm):
        equipment_types = forms.MultipleChoiceField(
            choices=[(x, x) for x in PartsShop.EQUIPMENT_TYPE_CHOICES],
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label="취급 장비",
        )
        manufacturer = forms.MultipleChoiceField(
            choices=[(x, x) for x in PartsShop.MANUFACTURER_CHOICES],
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label="취급 제조사",
        )
        manufacturers = forms.MultipleChoiceField(
            choices=[(x, x) for x in PartsShop.MANUFACTURER_CHOICES],
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label="취급 제조사(신규 필터용)",
        )
        ton_ranges = forms.MultipleChoiceField(
            choices=[(x, x) for x in PartsShop.TON_RANGE_CHOICES],
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label="톤급",
        )
        repair_types = forms.MultipleChoiceField(
            choices=[(x, x) for x in PartsShop.REPAIR_TYPE_CHOICES],
            required=False,
            widget=forms.CheckboxSelectMultiple,
            label="정비 유형",
        )

        class Meta:
            model = PartsShop
            fields = "__all__"

    form = PartsShopAdminForm
    list_display = ['name', 'shop_kind', 'region', 'contact', 'address', 'lat', 'lng', 'created_at']
    list_filter = ('shop_kind', 'region')
    search_fields = ['name', 'region', 'address', 'note', 'contact']
    list_per_page = 50
    radio_fields = {'shop_kind': admin.HORIZONTAL}
    fieldsets = (
        (None, {'fields': ('name', 'shop_kind', 'region', 'contact')}),
        ('취급 정보', {'fields': ('equipment_types', 'manufacturer', 'manufacturers', 'ton_ranges', 'repair_types')}),
        ('주소·좌표', {'fields': ('address', ('lat', 'lng'), 'note')}),
    )

    def _get_kakao_rest_key(self):
        key = (getattr(settings, 'KAKAO_REST_API_KEY', '') or '').strip()
        if key:
            return key
        try:
            from allauth.socialaccount.models import SocialApp
            key = (
                SocialApp.objects.filter(provider="kakao")
                .values_list("client_id", flat=True)
                .first()
                or ""
            ).strip()
            return key
        except Exception:
            return ""

    def _geocode_address(self, address):
        addr = (address or "").strip()
        if not addr:
            return None
        key = self._get_kakao_rest_key()
        if not key:
            return None
        try:
            query = urlencode({"query": addr})
            req = f"https://dapi.kakao.com/v2/local/search/address.json?{query}"
            request_obj = Request(req, headers={"Authorization": f"KakaoAK {key}"})
            with urlopen(request_obj, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            docs = payload.get("documents") or []
            if not docs:
                return None
            top = docs[0]
            return (float(top.get("y")), float(top.get("x")))
        except Exception:
            return None

    def save_model(self, request, obj, form, change):
        # 주소가 있고 좌표가 비어있거나, 주소가 변경되었으면 저장 시 자동 지오코딩
        address_changed = False
        if change:
            try:
                old = PartsShop.objects.get(pk=obj.pk)
                address_changed = (old.address or "").strip() != (obj.address or "").strip()
            except PartsShop.DoesNotExist:
                address_changed = True
        else:
            address_changed = True

        needs_geocode = bool((obj.address or "").strip()) and (
            obj.lat is None or obj.lng is None or address_changed
        )
        if needs_geocode:
            coords = self._geocode_address(obj.address)
            if coords:
                obj.lat, obj.lng = coords

        super().save_model(request, obj, form, change)


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "equipment_type", "region", "day_rate", "is_available", "created_at")
    list_filter = ("equipment_type", "is_available")
    search_fields = ("name", "region", "contact")


@admin.register(YoutubeContent)
class YoutubeContentAdmin(admin.ModelAdmin):
    list_display = [
        "title", "equipment_type", "purpose", "sort_order", "is_active", "created_at",
    ]
    list_filter = ("equipment_type", "purpose", "is_active")
    search_fields = ("title", "description", "youtube_url")
    list_editable = ("sort_order", "is_active")
    ordering = ("sort_order", "-created_at")


# 3. 구인구직 및 프로필
@admin.register(JobPost)
class JobPostAdmin(admin.ModelAdmin):
    list_display = ['id', 'legacy_guin_uid', 'job_type', 'title', 'company_name', 'region_sido', 'region_sigungu', 'recruit_count', 'deadline_type', 'deadline', 'author', 'created_at']
    list_filter = ('job_type', 'region_sido', 'created_at')
    search_fields = ('title', 'location', 'region_sido', 'region_sigungu', 'content', 'writer_display')
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(ExamPost)
class ExamPostAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'category', 'equipment', 'author', 'views', 'youtube_url', 'created_at']
    list_filter = ('category', 'equipment', 'created_at')
    search_fields = ('title', 'content', 'youtube_url')
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(ExamComment)
class ExamCommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'post', 'author', 'created_at']
    list_filter = ('created_at',)
    search_fields = ('content',)
    raw_id_fields = ('post', 'author')


# --- 회원(Profile) 목록: 기존/신규, 인증, 개인·사업자, 무료·유료, 매물수, 결제이력, 신고 ---
class MemberTypeFilter(admin.SimpleListFilter):
    title = '회원 구분'
    parameter_name = 'member_type'
    def lookups(self, request, model_admin):
        return [('legacy', '기존회원'), ('new', '신규회원')]
    def queryset(self, request, queryset):
        if self.value() == 'legacy':
            return queryset.exclude(legacy_member_id__isnull=True)
        if self.value() == 'new':
            return queryset.filter(legacy_member_id__isnull=True)
        return queryset


class PremiumStatusFilter(admin.SimpleListFilter):
    title = '요금 구분'
    parameter_name = 'premium'
    def lookups(self, request, model_admin):
        return [('free', '무료'), ('paid', '유료')]
    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == 'free':
            return queryset.filter(
                Q(is_premium=False) | Q(is_premium=True, premium_until__lt=today)
            )
        if self.value() == 'paid':
            return queryset.filter(
                is_premium=True
            ).filter(Q(premium_until__isnull=True) | Q(premium_until__gte=today))
        return queryset


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    # 기존 사이트에서 로그인 아이디가 전화번호였던 이력 때문에 username/이름 폴백이 전화번호처럼 보일 수 있어,
    # 목록에서는 꼭 필요한 정보만 최소 표시하도록 줄입니다.
    list_display = [
        'member_number_display',  # 회원번호(전화번호 우선)
        'phone',                   # 연락처(원본 전화)
        'name_display',           # 이름
        'monthly_listing_status_display',
        'monthly_bump_status_display',
        'created_display',        # 가입일
    ]
    list_filter = (MemberTypeFilter, 'phone_verified', 'user_type', PremiumStatusFilter, 'is_approved')
    search_fields = ('user__username', 'user__first_name', 'user__email', 'company_name', 'phone')
    list_per_page = 50
    # 목록에서 최소 컬럼만 보여주도록 줄였기 때문에,
    # list_editable은 list_display에 없는 필드를 가리키면 SystemCheckError가 발생합니다.
    # 여기서는 편집 기능을 끄고(기본값) 조회 중심으로 동작하도록 합니다.
    list_editable = ()
    actions = (
        'mark_premium_30_days',
        'mark_premium_unlimited',
        'mark_premium_off',
    )
    readonly_fields = (
        'equipment_count_display',
        'payment_count_display',
        'reported_display',
        'created_display',
        'monthly_listing_status_display',
        'monthly_bump_status_display',
    )
    date_hierarchy = 'user__date_joined'

    @admin.action(description='선택 회원 유료 전환 (30일)')
    def mark_premium_30_days(self, request, queryset):
        from datetime import timedelta
        today = timezone.now().date()
        changed = 0
        for profile in queryset:
            base = profile.premium_until if profile.premium_until and profile.premium_until >= today else today
            profile.is_premium = True
            profile.premium_until = base + timedelta(days=30)
            profile.save(update_fields=['is_premium', 'premium_until'])
            changed += 1
        self.message_user(request, f'{changed}명 회원을 30일 유료로 전환했습니다.')

    @admin.action(description='선택 회원 유료 전환 (무기한)')
    def mark_premium_unlimited(self, request, queryset):
        changed = queryset.update(is_premium=True, premium_until=None)
        self.message_user(request, f'{changed}명 회원을 무기한 유료로 전환했습니다.')

    @admin.action(description='선택 회원 유료 해제')
    def mark_premium_off(self, request, queryset):
        changed = queryset.update(is_premium=False, premium_until=None)
        self.message_user(request, f'{changed}명 회원의 유료 상태를 해제했습니다.')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user').annotate(_equipment_count=Count('user__authored_equipment', distinct=True))

    def name_display(self, obj):
        """이름: User.first_name 또는 상호명."""
        if not obj.user_id:
            return '-'
        name = (getattr(obj.user, 'first_name', None) or '').strip()
        if name:
            return name
        # accounts.MemberProfile에 이름이 들어있는 회원 fallback
        try:
            mp_name = (getattr(obj.user, 'member_profile', None).ceo_name or '').strip()
            if mp_name:
                return mp_name
        except Exception:
            pass
        if (getattr(obj, 'company_name', None) or '').strip():
            return obj.company_name.strip()
        # 최후 fallback: 화면에서 "빈칸"처럼 보이지 않게 로그인 아이디라도 표시
        return (getattr(obj.user, 'username', None) or '').strip() or '-'
    name_display.short_description = '이름'

    def user_nickname_display(self, obj):
        """관리자 목록에서 '사용자'는 로그인 아이디 대신 닉네임(이름)을 보여줌."""
        if not obj.user_id:
            return '-'
        first = (getattr(obj.user, 'first_name', None) or '').strip()
        if first:
            return first
        # MemberProfile에 값이 있는 경우 우선
        try:
            mp_ceo = (getattr(obj.user, 'member_profile', None).ceo_name or '').strip()
            if mp_ceo:
                return mp_ceo
        except Exception:
            pass
        if (getattr(obj, 'company_name', None) or '').strip():
            return obj.company_name.strip()
        # User.last_name은 "닉네임"으로 쓰는 편이어서 이름 표시 용 fallback으로도 활용
        last = (getattr(obj.user, 'last_name', None) or '').strip()
        if last:
            return last
        return obj.user.username or '-'

    user_nickname_display.short_description = '사용자'

    def member_number_display(self, obj):
        """회원번호: 전화번호 우선 표시."""
        ph = (getattr(obj, 'phone', None) or '').strip()
        if ph:
            return ph
        username = (getattr(obj.user, 'username', None) or '').strip() if getattr(obj, 'user_id', None) else ''
        return username or '-'

    member_number_display.short_description = '회원번호'

    def member_type_display(self, obj):
        if obj.legacy_member_id is not None:
            return format_html('<span style="color:#059669;">기존</span>')
        if getattr(obj.user, 'username', '').startswith('legacy_'):
            return format_html('<span style="color:#059669;">기존</span>')
        return format_html('<span style="color:#6b7280;">신규</span>')
    member_type_display.short_description = '구분'

    def verified_display(self, obj):
        if getattr(obj, 'phone_verified', False):
            return format_html('<span style="color:#059669;">O</span>')
        return format_html('<span style="color:#dc2626;">X</span>')
    verified_display.short_description = '인증'

    def user_type_display(self, obj):
        return obj.get_user_type_display() if obj.user_type else '-'
    user_type_display.short_description = '개인/사업자'

    def premium_display(self, obj):
        """현재 유료 상태."""
        if not getattr(obj, 'is_premium', False):
            return format_html('<span>무료</span>')
        today = timezone.now().date()
        if obj.premium_until and obj.premium_until < today:
            return format_html('<span style="color:#9ca3af;">만료</span>')
        return format_html('<span style="color:#d97706; font-weight:bold;">유료</span>')
    premium_display.short_description = '유료 상태'

    def premium_remaining_display(self, obj):
        """남은 기간: D-day, 무기한, 만료, -."""
        if not getattr(obj, 'is_premium', False):
            return '-'
        if not obj.premium_until:
            return format_html('<span style="color:#059669;">무기한</span>')
        today = timezone.now().date()
        if obj.premium_until < today:
            return format_html('<span style="color:#9ca3af;">만료</span>')
        delta = (obj.premium_until - today).days
        if delta == 0:
            return 'D-0'
        return f'D-{delta}'
    premium_remaining_display.short_description = '남은 기간'

    def payment_memo_display(self, obj):
        """최근 결제 여부 또는 메모: 마지막 결제완료 주문의 결제일·메모."""
        try:
            from billing.models import Order
            last_order = Order.objects.filter(user_id=obj.user_id, status='PAID').order_by('-updated_at').first()
            if not last_order:
                return format_html('<span style="color:#9ca3af;">결제 없음</span>')
            parts = []
            last_payment = getattr(last_order, 'payments', None)
            if last_payment:
                paid = last_payment.filter(status='SUCCESS').order_by('-paid_at').first()
                if paid and getattr(paid, 'paid_at', None):
                    parts.append(paid.paid_at.strftime('%Y-%m-%d'))
            if not parts and getattr(last_order, 'updated_at', None):
                parts.append(last_order.updated_at.strftime('%Y-%m-%d'))
            memo = (getattr(last_order, 'admin_memo', None) or '').strip()
            if memo:
                parts.append(memo[:25] + '…' if len(memo) > 25 else memo)
            return ' · '.join(parts) if parts else '결제 O'
        except Exception:
            return '-'
    payment_memo_display.short_description = '최근 결제/메모'

    def equipment_count_display(self, obj):
        if hasattr(obj, '_equipment_count'):
            return obj._equipment_count
        return getattr(obj.user, 'authored_equipment', []).count() if obj.user_id else 0
    equipment_count_display.short_description = '매물 수'

    def payment_count_display(self, obj):
        try:
            from billing.models import Order
            cnt = Order.objects.filter(user_id=obj.user_id, status='PAID').count()
            return f'{cnt}건' if cnt else '-'
        except Exception:
            return '-'
    payment_count_display.short_description = '결제 이력'

    def reported_display(self, obj):
        return '없음'
    reported_display.short_description = '신고'

    def created_display(self, obj):
        if not obj.user_id:
            return '-'
        try:
            d = obj.user.date_joined
            return d.strftime('%Y-%m-%d %H:%M') if d else '-'
        except Exception:
            return '-'
    created_display.short_description = '가입일'

    def monthly_listing_status_display(self, obj):
        try:
            from equipment.premium_utils import (
                is_user_premium,
                get_monthly_listing_count,
                FREE_LISTING_LIMIT,
                PREMIUM_LISTING_LIMIT,
            )
            if not obj.user_id:
                return '-'
            count = get_monthly_listing_count(obj.user)
            limit = PREMIUM_LISTING_LIMIT if is_user_premium(obj.user) else FREE_LISTING_LIMIT
            return f'{count}/{limit}건'
        except Exception:
            return '-'
    monthly_listing_status_display.short_description = '당월 등록'

    def monthly_bump_status_display(self, obj):
        try:
            from equipment.premium_utils import get_user_bump_status
            if not obj.user_id:
                return '-'
            status = get_user_bump_status(obj.user)
            if not status['is_premium']:
                return '무료'
            return f"{status['used']}/{status['limit']}회 (매물 {status['listing_count']}개)"
        except Exception:
            return '-'
    monthly_bump_status_display.short_description = '당월 끌어올리기'


@admin.register(EquipmentFavorite)
class EquipmentFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'equipment', 'created_at']
    list_filter = ('created_at',)
    search_fields = ('user__username', 'equipment__model_name')
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(PartFavorite)
class PartFavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'part', 'created_at']
    list_filter = ('created_at',)
    search_fields = ('user__username', 'part__title')
    date_hierarchy = 'created_at'
    list_per_page = 50


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['id', 'author', 'author_name', 'content_type', 'object_id', 'content_short', 'created_at']
    list_filter = ('content_type', 'created_at')
    search_fields = ('content', 'author_name', 'author__username')
    date_hierarchy = 'created_at'
    list_per_page = 50
    readonly_fields = ('created_at',)

    def content_short(self, obj):
        if not obj.content:
            return ""
        return obj.content[:40] + "…" if len(obj.content) > 40 else obj.content
    content_short.short_description = '내용'


@admin.register(DeletedListingLog)
class DeletedListingLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'equipment_type', 'year_manufactured', 'listing_price', 'model_name', 'deleted_at')
    list_filter = ('deleted_at',)
    search_fields = ('user__username', 'model_name', 'equipment_type')
    date_hierarchy = 'deleted_at'
    readonly_fields = ('deleted_at',)


@admin.register(EquipmentBumpLog)
class EquipmentBumpLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'equipment', 'bumped_at')
    list_filter = ('bumped_at',)
    search_fields = ('user__username', 'equipment__model_name')
    date_hierarchy = 'bumped_at'
    readonly_fields = ('bumped_at',)


@admin.register(FinanceConsultation)
class FinanceConsultationAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "applicant_name",
        "contact",
        "desired_equipment",
        "budget_manwon",
        "desired_months",
        "status",
    )
    list_filter = ("status", "desired_months", "created_at")
    search_fields = ("applicant_name", "contact", "desired_equipment", "memo")
    list_editable = ("status",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 50


class CustomAuthUserAdmin(DjangoUserAdmin):
    """auth.User 목록을 리뉴얼 회원 관리 용도에 맞춰 단순 표시."""
    # auth.User 목록은 username이 전화번호 형태인 경우가 있어 중복/혼란이 발생합니다.
    # 목록에서는 회원번호(전화번호 우선) + 이름 + 가입일만 보여줍니다.
    list_display = (
        "member_no_display",
        "name_display",
        "joined_display",
    )
    search_fields = ("username", "first_name", "profile__phone")
    ordering = ("-date_joined",)

    def member_no_display(self, obj):
        # 회원번호는 전화번호 우선(없으면 username 사용)
        try:
            ph = (getattr(obj, "profile", None).phone or "").strip()
        except Exception:
            ph = ""
        return ph or obj.username

    member_no_display.short_description = "전화번호"

    def name_display(self, obj):
        return (obj.first_name or "").strip() or "-"

    name_display.short_description = "이름"

    def joined_display(self, obj):
        d = getattr(obj, "date_joined", None)
        return d.strftime("%Y-%m-%d %H:%M") if d else "-"

    joined_display.short_description = "가입일"


def _format_duration(seconds):
    if seconds is None:
        return "-"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}초"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}분 {sec}초"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}시간 {minutes}분"


class VisitPageLogInline(admin.TabularInline):
    model = VisitPageLog
    extra = 0
    can_delete = False
    fields = ("viewed_at", "path_display", "duration_display", "referer_short")
    readonly_fields = ("viewed_at", "path_display", "duration_display", "referer_short")
    ordering = ("viewed_at",)

    @admin.display(description="경로")
    def path_display(self, obj):
        if obj.query_string:
            return f"{obj.path}?{obj.query_string}"
        return obj.path

    @admin.display(description="체류")
    def duration_display(self, obj):
        return _format_duration(obj.duration_seconds)

    @admin.display(description="유입/이전")
    def referer_short(self, obj):
        ref = (obj.referer or "").strip()
        if not ref:
            return "—"
        return ref if len(ref) <= 80 else ref[:77] + "…"


@admin.register(VisitSession)
class VisitSessionAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "visitor_display",
        "ip_address",
        "landing_path",
        "last_path",
        "page_view_count",
        "duration_display",
        "referer_short",
    )
    list_filter = ("started_at",)
    search_fields = (
        "ip_address",
        "landing_path",
        "last_path",
        "referer",
        "user__username",
        "user__first_name",
    )
    readonly_fields = (
        "django_session_key",
        "user",
        "ip_address",
        "user_agent",
        "referer",
        "landing_path",
        "last_path",
        "started_at",
        "last_seen_at",
        "duration_seconds",
        "page_view_count",
    )
    date_hierarchy = "started_at"
    inlines = (VisitPageLogInline,)
    list_per_page = 50

    @admin.display(description="방문자")
    def visitor_display(self, obj):
        if obj.user_id:
            name = (obj.user.first_name or "").strip()
            return f"{name or obj.user.username} ({obj.user.username})"
        return f"비회원 · {obj.ip_address}"

    @admin.display(description="체류")
    def duration_display(self, obj):
        return _format_duration(obj.duration_seconds)

    @admin.display(description="유입 URL")
    def referer_short(self, obj):
        ref = (obj.referer or "").strip()
        if not ref:
            return "직접 접속"
        return ref if len(ref) <= 60 else ref[:57] + "…"


@admin.register(VisitPageLog)
class VisitPageLogAdmin(admin.ModelAdmin):
    list_display = (
        "viewed_at",
        "path_display",
        "visitor_display",
        "ip_address",
        "duration_display",
        "referer_short",
        "session",
    )
    list_filter = ("viewed_at",)
    search_fields = ("path", "ip_address", "referer", "user__username")
    readonly_fields = (
        "session",
        "path",
        "query_string",
        "referer",
        "user",
        "ip_address",
        "viewed_at",
        "duration_seconds",
    )
    date_hierarchy = "viewed_at"
    list_per_page = 100
    list_select_related = ("user", "session")

    @admin.display(description="경로")
    def path_display(self, obj):
        if obj.query_string:
            return f"{obj.path}?{obj.query_string}"
        return obj.path

    @admin.display(description="방문자")
    def visitor_display(self, obj):
        if obj.user_id:
            return obj.user.username
        return f"비회원 · {obj.ip_address}"

    @admin.display(description="체류")
    def duration_display(self, obj):
        return _format_duration(obj.duration_seconds)

    @admin.display(description="유입/이전")
    def referer_short(self, obj):
        ref = (obj.referer or "").strip()
        if not ref:
            return "—"
        return ref if len(ref) <= 60 else ref[:57] + "…"


@admin.register(VisitorCount)
class VisitorCountAdmin(admin.ModelAdmin):
    list_display = ("date", "count", "session_count")
    readonly_fields = ("date", "count", "session_count")
    date_hierarchy = "date"


@admin.register(VisitorLog)
class VisitorLogAdmin(admin.ModelAdmin):
    list_display = ("visit_date", "ip_address", "referer_short")
    list_filter = ("visit_date",)
    search_fields = ("ip_address", "referer")
    readonly_fields = ("ip_address", "visit_date", "referer")
    date_hierarchy = "visit_date"

    @admin.display(description="유입")
    def referer_short(self, obj):
        ref = (obj.referer or "").strip()
        return ref if len(ref) <= 80 else ref[:77] + "…"


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomAuthUserAdmin)
