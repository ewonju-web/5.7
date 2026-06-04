"""메인 매물 목록(index) 필터·정렬 공통 로직."""
from __future__ import annotations

from django.db.models import Q, F, Case, When, IntegerField, Value
from django.db.models.functions import Coalesce

from .models import Equipment
from .premium_utils import get_premium_user_ids
from .listing_filters import (
    exclude_excavator_misclassified_for_non_excavator_tabs,
    exclude_attachment_like_from_non_attachment_tabs,
    filter_attachment_tab,
)


def _is_excavator_tire_5_6_filter(sub_type: str, weight_class: str) -> bool:
    return sub_type == 'EXC_TIRE' and weight_class == 'EXC_TIRE_LE_6'


def _legacy_excavator_tire_5_6_q() -> Q:
    return Q(
        model_name__iregex=(
            r"(EW\s*60|EW\s*55|HW\s*60|DX\s*55\s*W|R\s*555\s*W|"
            r"\b55\s*W(?:I)?\b|\b0?6\s*W\b)"
        )
    )


def _exclude_mislabeled_mini_crawler_in_tire_heavy_search(sub_type: str, weight_class: str):
    if sub_type != "EXC_TIRE" or weight_class not in ("EXC_TIRE_LE_17", "EXC_TIRE_LE_21"):
        return None
    return (
        Q(model_name__iregex=r"(?i)\bDX\s*5[0-9]\b(?!.*W)")
        | Q(model_name__iregex=r"(?i)\bEC\s*55\b(?!.*W)")
        | Q(model_name__iregex=r"(?i)\bHX\s*55\b(?!.*W)")
    )

VALID_CATEGORIES = ('excavator', 'forklift', 'dump', 'loader', 'crane', 'attachment', 'other')
INDEX_INITIAL_COUNT = 20
INDEX_FILTER_MAX = 120  # 상세필터 시 한 번에 로드 상한

# 어드민 changelist는 모델 필드명과 같은 GET(sub_type 등)을 거부하므로 xsf_ 접두사 사용.
EXCAVATOR_ADMIN_QUERY_KEYS = frozenset({
    'xsf_maker', 'xsf_sub_type', 'xsf_weight_class', 'xsf_year_min', 'xsf_year_max', 'xsf_model',
})
EXCAVATOR_ADMIN_SKIP_PRESERVE_KEYS = EXCAVATOR_ADMIN_QUERY_KEYS | frozenset({'e'})


def apply_excavator_sub_type_weight_filters(equipment_list, sub_type: str, weight_class: str):
    """굴삭기 종류·중량 상세 필터 (사이트·어드민 공통)."""
    if (
        sub_type
        and weight_class
        and _is_excavator_tire_5_6_filter(sub_type, weight_class)
    ):
        exact_tire_56 = Q(sub_type=sub_type, weight_class=weight_class)
        legacy_tire_56 = (
            _legacy_excavator_tire_5_6_q()
            & ~Q(sub_type="EXC_CRAWLER")
            & ~Q(sub_type="EXC_ATTACHMENT")
            & ~Q(weight_class__startswith="EXC_CR")
            & ~Q(weight_class__startswith="EXC_ATT")
        )
        equipment_list = equipment_list.filter(exact_tire_56 | legacy_tire_56)
    else:
        att_to_cr_map = {
            'EXC_ATT_LT_1': 'EXC_CR_LE_3_5',
            'EXC_ATT_LE_2': 'EXC_CR_LE_2',
            'EXC_ATT_LE_3_5': 'EXC_CR_LE_3_5',
            'EXC_ATT_LE_6_5': 'EXC_CR_LE_6_5',
            'EXC_ATT_LE_16': 'EXC_CR_LE_16',
            'EXC_ATT_EQ_20': 'EXC_CR_EQ_20',
            'EXC_ATT_GE_30': 'EXC_CR_GE_30',
        }
        if sub_type == 'EXC_CRAWLER':
            equipment_list = equipment_list.filter(
                Q(sub_type='EXC_CRAWLER')
                | (Q(sub_type='') & Q(weight_class__startswith='EXC_CR_'))
            )
        elif sub_type:
            equipment_list = equipment_list.filter(sub_type=sub_type)

        if weight_class:
            if sub_type == 'EXC_ATTACHMENT':
                cr_code = att_to_cr_map.get(weight_class)
                if cr_code:
                    equipment_list = equipment_list.filter(
                        Q(weight_class=weight_class)
                        | Q(weight_class=cr_code)
                        | Q(weight_class='')
                    )
                else:
                    equipment_list = equipment_list.filter(
                        Q(weight_class=weight_class) | Q(weight_class='')
                    )
            else:
                cr_code = att_to_cr_map.get(weight_class)
                if cr_code:
                    equipment_list = equipment_list.filter(
                        Q(weight_class=weight_class) | Q(weight_class=cr_code)
                    )
                else:
                    equipment_list = equipment_list.filter(weight_class=weight_class)
    mislabeled_q = _exclude_mislabeled_mini_crawler_in_tire_heavy_search(sub_type, weight_class)
    if mislabeled_q is not None:
        equipment_list = equipment_list.exclude(mislabeled_q)
    return equipment_list


def apply_excavator_detail_filters(
    equipment_list,
    *,
    maker: str = '',
    model: str = '',
    year_min: str = '',
    year_max: str = '',
    sub_type: str = '',
    weight_class: str = '',
):
    """굴삭기 상세검색 전체(어드민·사이트 excavator 탭)."""
    if sub_type != "EXC_ATTACHMENT":
        equipment_list = equipment_list.exclude(sub_type="EXC_ATTACHMENT")
    if maker:
        equipment_list = equipment_list.filter(manufacturer__iexact=maker)
    if model:
        equipment_list = equipment_list.filter(model_name__icontains=model)
    if year_min:
        try:
            equipment_list = equipment_list.filter(year_manufactured__gte=int(year_min))
        except (TypeError, ValueError):
            pass
    if year_max:
        try:
            equipment_list = equipment_list.filter(year_manufactured__lte=int(year_max))
        except (TypeError, ValueError):
            pass
    return apply_excavator_sub_type_weight_filters(equipment_list, sub_type, weight_class)


def parse_excavator_admin_filters(request):
    """굴삭기 어드민 changelist GET 상세검색 파라미터 (xsf_*)."""
    return {
        'maker': (request.GET.get('xsf_maker') or '').strip(),
        'sub_type': (request.GET.get('xsf_sub_type') or '').strip(),
        'weight_class': (request.GET.get('xsf_weight_class') or '').strip(),
        'year_min': (request.GET.get('xsf_year_min') or '').strip(),
        'year_max': (request.GET.get('xsf_year_max') or '').strip(),
        'model': (request.GET.get('xsf_model') or '').strip(),
    }


def excavator_admin_filters_active(params: dict) -> bool:
    return any(params.values())


def excavator_admin_preserved_params(request):
    """상세검색·오류 플래그 제외, changelist 기존 GET 유지용."""
    preserved = []
    for key in request.GET:
        if key in EXCAVATOR_ADMIN_SKIP_PRESERVE_KEYS:
            continue
        for val in request.GET.getlist(key):
            preserved.append((key, val))
    return preserved


def excavator_admin_filter_query_items(params: dict):
    """폼 hidden·초기화 URL용 xsf_* (값 있는 항목만)."""
    mapping = (
        ("xsf_maker", "maker"),
        ("xsf_sub_type", "sub_type"),
        ("xsf_weight_class", "weight_class"),
        ("xsf_year_min", "year_min"),
        ("xsf_year_max", "year_max"),
        ("xsf_model", "model"),
    )
    items = []
    for qkey, pkey in mapping:
        val = (params.get(pkey) or "").strip()
        if val:
            items.append((qkey, val))
    return items


def parse_index_params(request):
    """index / index_load_more 공통 GET 파라미터."""
    query = (request.GET.get('q', '') or '').strip()
    sort = (request.GET.get('sort', '') or 'new').strip().lower()
    if sort not in ('price_asc', 'price_desc', 'year_desc', 'new'):
        sort = 'new'

    filter_category = (request.GET.get('category', '') or '').strip().lower()
    if 'category' in request.GET and not (request.GET.get('category') or '').strip():
        request.session.pop('last_equipment_category', None)
    elif 'category' not in request.GET:
        last_category = (request.session.get('last_equipment_category') or '').strip().lower()
        if last_category in VALID_CATEGORIES:
            filter_category = last_category
    elif not filter_category and query:
        last_category = (request.session.get('last_equipment_category') or '').strip().lower()
        if last_category in VALID_CATEGORIES:
            filter_category = last_category

    if not filter_category and query:
        q = query.lower()
        if any(k in q for k in ("굴삭기", "excavator")):
            filter_category = "excavator"
        elif any(k in q for k in ("지게차", "forklift", "리프트")):
            filter_category = "forklift"
        elif any(k in q for k in ("덤프트럭", "덤프", "dump truck", "dump")):
            filter_category = "dump"
        elif any(k in q for k in ("로더", "휠로더", "wheel loader", "loader")):
            filter_category = "loader"
        elif any(k in q for k in ("크레인", "crane")):
            filter_category = "crane"
        elif any(k in q for k in ("어태치", "attachment")):
            filter_category = "attachment"

    if filter_category in VALID_CATEGORIES:
        request.session['last_equipment_category'] = filter_category

    maker = (request.GET.get('maker', '') or '').strip()
    sub_type = (request.GET.get('sub_type', '') or '').strip()
    weight_class = (request.GET.get('weight_class', '') or '').strip()
    model = (request.GET.get('model', '') or '').strip()
    year_min = (request.GET.get('year_min') or '').strip()
    year_max = (request.GET.get('year_max') or '').strip()
    region_sido = (request.GET.get('region_sido', '') or '').strip()
    region_sigungu = (request.GET.get('region_sigungu', '') or '').strip()
    mast_type = (request.GET.get('mast_type', '') or '').strip()
    premium_only = request.GET.get('premium_only') == '1'
    hide_advanced_filters = request.GET.get('expand') == '1' or any(
        bool(v) for v in (
            maker, sub_type, weight_class, model,
            year_min, year_max, region_sido, region_sigungu, mast_type,
        )
    )

    try:
        list_per_page = int(request.GET.get('per_page', '40'))
    except (TypeError, ValueError):
        list_per_page = 40
    if list_per_page not in (24, 40, 60):
        list_per_page = 40

    return {
        'query': query,
        'sort': sort,
        'filter_category': filter_category,
        'maker': maker,
        'sub_type': sub_type,
        'weight_class': weight_class,
        'model': model,
        'year_min': year_min,
        'year_max': year_max,
        'region_sido': region_sido,
        'region_sigungu': region_sigungu,
        'mast_type': mast_type,
        'premium_only': premium_only,
        'hide_advanced_filters': hide_advanced_filters,
        'list_per_page': list_per_page,
    }


def build_index_equipment_queryset(request, params: dict):
    """필터·정렬이 적용된 매물 QuerySet."""
    query = params['query']
    sort = params['sort']
    filter_category = params['filter_category']
    hide_advanced_filters = params['hide_advanced_filters']

    equipment_list = Equipment.objects.visible()
    if filter_category in VALID_CATEGORIES:
        if filter_category == "attachment":
            equipment_list = filter_attachment_tab(equipment_list)
        else:
            equipment_list = equipment_list.filter(equipment_type=filter_category)
    if filter_category == "excavator":
        if params['sub_type'] != "EXC_ATTACHMENT":
            equipment_list = equipment_list.exclude(sub_type="EXC_ATTACHMENT")
    equipment_list = exclude_excavator_misclassified_for_non_excavator_tabs(
        equipment_list, filter_category
    )
    equipment_list = exclude_attachment_like_from_non_attachment_tabs(
        equipment_list, filter_category
    )

    if query:
        lookups = (
            Q(model_name__icontains=query)
            | Q(manufacturer__icontains=query)
            | Q(current_location__icontains=query)
        )
        q_num = query.replace(',', '').replace('만원', '').replace('원', '').strip()
        if q_num.isdigit():
            lookups |= Q(listing_price=int(q_num))
            if len(q_num) == 4 and 1980 <= int(q_num) <= 2030:
                lookups |= Q(year_manufactured=int(q_num))
        equipment_list = equipment_list.filter(lookups).distinct()

    maker = params['maker']
    if maker:
        equipment_list = equipment_list.filter(manufacturer__iexact=maker)
    if params['model']:
        equipment_list = equipment_list.filter(model_name__icontains=params['model'])

    year_min, year_max = params['year_min'], params['year_max']
    if year_min:
        try:
            equipment_list = equipment_list.filter(year_manufactured__gte=int(year_min))
        except (TypeError, ValueError):
            pass
    if year_max:
        try:
            equipment_list = equipment_list.filter(year_manufactured__lte=int(year_max))
        except (TypeError, ValueError):
            pass

    if params['region_sido']:
        equipment_list = equipment_list.filter(region_sido=params['region_sido'])
    if params['region_sigungu']:
        equipment_list = equipment_list.filter(region_sigungu=params['region_sigungu'])

    sub_type = params['sub_type']
    weight_class = params['weight_class']
    if filter_category == 'excavator':
        equipment_list = apply_excavator_sub_type_weight_filters(
            equipment_list, sub_type, weight_class
        )
    elif filter_category == 'forklift':
        if sub_type:
            equipment_list = equipment_list.filter(sub_type=sub_type)
        if weight_class:
            equipment_list = equipment_list.filter(weight_class=weight_class)
        if params['mast_type']:
            equipment_list = equipment_list.filter(mast_type=params['mast_type'])
    elif filter_category == 'dump':
        if weight_class:
            equipment_list = equipment_list.filter(weight_class=weight_class)
    elif filter_category in ('loader', 'crane', 'attachment', 'other'):
        if weight_class:
            equipment_list = equipment_list.filter(weight_class__icontains=weight_class)

    premium_author_ids = set(get_premium_user_ids())
    if params['premium_only']:
        equipment_list = equipment_list.filter(author_id__in=premium_author_ids)

    if sort == 'price_asc':
        equipment_list = equipment_list.order_by('listing_price')
    elif sort == 'price_desc':
        equipment_list = equipment_list.order_by('-listing_price')
    elif sort == 'year_desc':
        equipment_list = equipment_list.order_by('-year_manufactured')
    else:
        equipment_list = equipment_list.annotate(
            effective_order=Coalesce(F('last_bumped_at'), F('created_at'))
        )
        if not hide_advanced_filters and not query and premium_author_ids:
            equipment_list = equipment_list.annotate(
                premium_rank=Case(
                    When(author_id__in=premium_author_ids, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).order_by('premium_rank', '-effective_order')
        else:
            equipment_list = equipment_list.order_by('-effective_order')

    return equipment_list.select_related('author__profile').prefetch_related('images')
