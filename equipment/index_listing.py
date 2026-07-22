"""메인 매물 목록(index) 필터·정렬 공통 로직."""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode, urlparse

from django.core.cache import cache
from django.db.models import Q, F, Case, When, IntegerField, Value
from django.db.models.functions import Coalesce
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Equipment
from .premium_utils import get_premium_user_ids
from .diversity_utils import diversify_by_author
from .listing_filters import (
    exclude_excavator_misclassified_for_non_excavator_tabs,
    exclude_attachment_like_from_non_attachment_tabs,
    filter_attachment_tab,
)


class _AuthorPk:
    """diversify_by_author용 경량 래퍼 (pk + author_id만)."""

    __slots__ = ("pk", "author_id")

    def __init__(self, pk, author_id):
        self.pk = pk
        self.author_id = author_id


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


_ATT_TO_CR_WEIGHT_MAP = {
    'EXC_ATT_LT_1': 'EXC_CR_LE_3_5',
    'EXC_ATT_LE_2': 'EXC_CR_LE_2',
    'EXC_ATT_LE_3_5': 'EXC_CR_LE_3_5',
    'EXC_ATT_LE_6_5': 'EXC_CR_LE_6_5',
    'EXC_ATT_LE_16': 'EXC_CR_LE_16',
    'EXC_ATT_EQ_20': 'EXC_CR_EQ_20',
    'EXC_ATT_GE_30': 'EXC_CR_GE_30',
}

# 검색 UI「미니굴삭기 1~3ton」(EXC_CR_LE_3_5)에는 등록폼의 더 작은 구간(1t 미만·2t 미만)도 포함.
# 등록은 EXC_CR_LE_2 등으로 세분되는데, 검색 드롭다운에는 미니만 있어 안 보이던 문제 보정.
_WEIGHT_FILTER_INCLUDE_SMALLER = {
    'EXC_CR_LE_3_5': ('EXC_CR_LE_3_5', 'EXC_CR_LE_2', 'EXC_CR_LT_1'),
    'EXC_ATT_LE_3_5': ('EXC_ATT_LE_3_5', 'EXC_ATT_LE_2', 'EXC_ATT_LT_1', 'EXC_CR_LE_3_5', 'EXC_CR_LE_2', 'EXC_CR_LT_1'),
}


def equivalent_weight_classes(weight_class: str) -> list[str]:
    """같은 톤수 구간으로 취급하는 중량 코드(어태치↔크롤러 매핑 포함)."""
    code = (weight_class or '').strip()
    if not code:
        return []
    classes = {code}
    if code in _ATT_TO_CR_WEIGHT_MAP:
        classes.add(_ATT_TO_CR_WEIGHT_MAP[code])
    cr_to_att = {v: k for k, v in _ATT_TO_CR_WEIGHT_MAP.items()}
    if code in cr_to_att:
        classes.add(cr_to_att[code])
    return list(classes)


def weight_classes_for_filter(weight_class: str) -> list[str]:
    """목록 검색용 중량 코드. 미니(1~3t) 선택 시 하위 톤수 구간까지 포함."""
    code = (weight_class or '').strip()
    if not code:
        return []
    if code in _WEIGHT_FILTER_INCLUDE_SMALLER:
        return list(_WEIGHT_FILTER_INCLUDE_SMALLER[code])
    return equivalent_weight_classes(code)


def filter_similar_equipment_listings(queryset, equipment):
    """비슷한 시세 매물: 같은 기종·제조사·년식±2·같은 중량구분."""
    qs = queryset.exclude(pk=equipment.pk).filter(is_sold=False)
    if equipment.equipment_type:
        qs = qs.filter(equipment_type=equipment.equipment_type)
    if equipment.manufacturer:
        qs = qs.filter(manufacturer=equipment.manufacturer)
    year_val = equipment.year_manufactured or 0
    if year_val and 1980 <= year_val <= 2030:
        qs = qs.filter(
            year_manufactured__gte=year_val - 2,
            year_manufactured__lte=year_val + 2,
        )
    eq_classes = equivalent_weight_classes(equipment.weight_class)
    if eq_classes:
        qs = qs.filter(weight_class__in=eq_classes)
    return qs


VALID_CATEGORIES = ('excavator', 'forklift', 'dump', 'loader', 'crane', 'attachment', 'other')
INDEX_INITIAL_COUNT = 20
INDEX_FILTER_MAX = 120  # 상세필터 시 한 번에 로드 상한
INDEX_ROW_MODE_START = 100  # 누적 이 개수를 넘어가면 더보기를 카드 대신 한줄형(row)으로
INDEX_ROW_CHUNK = 50  # 한줄형 단계에서 더보기 한 번당 로드 개수
MIN_ITEMS_FOR_INTERLEAVE = 4
INDEX_INTERLEAVE_CACHE_TTL = 90
INDEX_INTERLEAVE_CACHE_KEY_PREFIX = 'index_interleave_v1'

# 어드민 changelist는 모델 필드명과 같은 GET(sub_type 등)을 거부하므로 xsf_ 접두사 사용.
EXCAVATOR_ADMIN_QUERY_KEYS = frozenset({
    'xsf_maker', 'xsf_sub_type', 'xsf_weight_class', 'xsf_year_min', 'xsf_year_max', 'xsf_model',
})
EXCAVATOR_ADMIN_SKIP_PRESERVE_KEYS = EXCAVATOR_ADMIN_QUERY_KEYS | frozenset({'e'})


def _wheeled_excavator_model_q() -> Q:
    """타이어식(휠) 모델명이 크롤러로 잘못 저장된 매물 제외용."""
    return (
        Q(model_name__iregex=r"(?i)(?:^|[^A-Za-z0-9])(?:EW|HW)\s*\d{2,3}")
        | Q(model_name__iregex=r"(?i)(?:DX|EC|HX|SK|PC|ZX)\s*\d{2,3}\s*W(?:\b|-)")
        | Q(model_name__icontains="휠")
        | Q(model_name__icontains="타이어식")
    )


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
        if sub_type == 'EXC_CRAWLER':
            equipment_list = equipment_list.filter(
                Q(sub_type='EXC_CRAWLER')
                | (Q(sub_type='') & Q(weight_class__startswith='EXC_CR_'))
            ).exclude(_wheeled_excavator_model_q())
        elif sub_type:
            equipment_list = equipment_list.filter(sub_type=sub_type)

        if weight_class:
            if sub_type == 'EXC_ATTACHMENT':
                filter_codes = weight_classes_for_filter(weight_class)
                equipment_list = equipment_list.filter(
                    Q(weight_class__in=filter_codes) | Q(weight_class='')
                )
            else:
                filter_codes = weight_classes_for_filter(weight_class)
                equipment_list = equipment_list.filter(weight_class__in=filter_codes)
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
        # 첫 화면(카테고리 미지정)은 1시간 단위로 번갈아 노출:
        #  - 짝수 시: 전체 기종 + 최신순
        #  - 홀수 시: 굴삭기 기종 + 프리미엄(유료 광고) 우선
        if timezone.localtime().hour % 2 == 0:
            filter_category = ''
        else:
            filter_category = 'excavator'
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
    if list_per_page not in (24, 40, 60, 80):
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


INDEX_LIST_QUERY_KEYS = (
    'category', 'expand', 'q', 'maker', 'sub_type', 'weight_class', 'model',
    'year_min', 'year_max', 'region_sido', 'region_sigungu', 'mast_type',
    'sort', 'per_page', 'premium_only',
)


def build_index_list_back_url_from_get(get_params) -> str:
    """GET 파라미터 → 매물 목록 페이지 URL (offset 등 더보기 전용 키 제외)."""
    pairs = []
    for key in INDEX_LIST_QUERY_KEYS:
        val = (get_params.get(key) or '').strip() if hasattr(get_params, 'get') else ''
        if val:
            pairs.append((key, val))
    qs = urlencode(pairs)
    return reverse('index') + ('?' + qs if qs else '')


def build_index_list_back_url(request) -> str:
    """매물 상세 next·목록 복귀용 URL — load-more API가 아닌 목록 페이지."""
    if request.path.rstrip('/').endswith('index/load-more'):
        return build_index_list_back_url_from_get(request.GET)
    get_copy = request.GET.copy()
    get_copy.pop('offset', None)
    path = request.path or reverse('index')
    qs = get_copy.urlencode()
    return path + ('?' + qs if qs else '')


def sanitize_index_list_back_url(request, url: str) -> str:
    """잘못 저장된 load-more API URL 등을 목록 페이지 URL로 보정."""
    url = (url or '').strip()
    if not url:
        return url
    allowed_hosts = {request.get_host()}
    if not url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts):
        return url
    parsed = urlparse(url)
    if '/index/load-more' in (parsed.path or ''):
        qd = QueryDict(parsed.query, mutable=True)
        qd.pop('offset', None)
        return build_index_list_back_url_from_get(qd)
    if parsed.query and 'offset=' in parsed.query:
        qd = QueryDict(parsed.query, mutable=True)
        qd.pop('offset', None)
        back = parsed.path or reverse('index')
        qs = qd.urlencode()
        return back + ('?' + qs if qs else '')
    return url


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
        if (
            not hide_advanced_filters
            and not query
            and filter_category in VALID_CATEGORIES
            and premium_author_ids
        ):
            # 특정 기종 선택 화면: 프리미엄(유료 광고) 매물 우선 노출 후 최신순
            equipment_list = equipment_list.annotate(
                premium_rank=Case(
                    When(author_id__in=premium_author_ids, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).order_by('premium_rank', '-effective_order')
        else:
            # 전체 기종(또는 검색·상세필터) 화면: 순수 최신순
            equipment_list = equipment_list.order_by('-effective_order')

    return equipment_list.select_related('author__profile').prefetch_related('images')


def _premium_sort_active(params: dict, premium_author_ids) -> bool:
    """build_index_equipment_queryset() sort=new 프리미엄 우선 정렬 조건과 동일."""
    return (
        not params['hide_advanced_filters']
        and not (params.get('query') or '').strip()
        and params.get('filter_category') in VALID_CATEGORIES
        and bool(premium_author_ids)
    )


def should_apply_index_interleave(params: dict, total_count: int) -> bool:
    return params.get('sort') == 'new' and total_count >= MIN_ITEMS_FOR_INTERLEAVE


def _build_interleave_cache_key(params: dict, premium_author_ids) -> str:
    payload = {
        'sort': params.get('sort'),
        'query': params.get('query'),
        'filter_category': params.get('filter_category'),
        'maker': params.get('maker'),
        'sub_type': params.get('sub_type'),
        'weight_class': params.get('weight_class'),
        'model': params.get('model'),
        'year_min': params.get('year_min'),
        'year_max': params.get('year_max'),
        'region_sido': params.get('region_sido'),
        'region_sigungu': params.get('region_sigungu'),
        'mast_type': params.get('mast_type'),
        'premium_only': params.get('premium_only'),
        'hide_advanced_filters': params.get('hide_advanced_filters'),
        'premium_sort': _premium_sort_active(params, premium_author_ids),
        'premium_ids': sorted(set(premium_author_ids)),
        'diversity': 4,  # A=전체 유료 RR(명함식), B=중복 제외 최신 절반
    }
    digest = hashlib.md5(
        json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()
    return f'{INDEX_INTERLEAVE_CACHE_KEY_PREFIX}:{digest}'


def get_interleave_groups(qs, params: dict, premium_author_ids):
    """
    Group A/B pk 목록과 total_count 반환.
    interleave 미적용 시 group_a_ids, group_b_ids 는 None.
    """
    premium_author_ids = set(premium_author_ids)
    cache_key = _build_interleave_cache_key(params, premium_author_ids)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    total = qs.count()
    if not should_apply_index_interleave(params, total):
        return total, None, None

    n_b = total // 2
    # qs 기본 정렬 순서 (기종 탭: premium_rank, -effective_order)
    ordered_rows = list(qs.values_list('pk', 'author_id'))
    latest_ids = list(
        qs.order_by('-effective_order').values_list('pk', flat=True)
    )

    if _premium_sort_active(params, premium_author_ids):
        # 유료 전체(명함처럼 회원 1명당 1건씩) 라운드로빈 → Group A 앞쪽
        premium_items = []
        free_ids_all = []
        for pk, aid in ordered_rows:
            if aid is not None and aid in premium_author_ids:
                premium_items.append(_AuthorPk(pk, aid))
            else:
                free_ids_all.append(pk)
        a_prem_ids = [item.pk for item in diversify_by_author(premium_items)]
        a_prem_set = set(a_prem_ids)
        # Group B: 순수 최신 절반 (A 유료와 중복 제거)
        group_b_ids = [pk for pk in latest_ids if pk not in a_prem_set][:n_b]
        b_set = set(group_b_ids)
        # Group A: 다양화 유료 + B에 안 들어간 무료
        free_in_a = [pk for pk in free_ids_all if pk not in b_set]
        group_a_ids = a_prem_ids + free_in_a
    else:
        group_b_ids = latest_ids[:n_b]
        b_set = set(group_b_ids)
        group_a_ids = [pk for pk, _ in ordered_rows if pk not in b_set]

    result = (total, group_a_ids, group_b_ids)
    cache.set(cache_key, result, INDEX_INTERLEAVE_CACHE_TTL)
    return result


def interleave_index_equipment_slice(
    qs,
    offset: int,
    limit: int,
    premium_author_ids,
    params: dict,
) -> tuple[list, int]:
    """
    index % 2 alternating interleave 슬라이스.
    짝수 index → Group A(프리미엄 우선), 홀수 index → Group B(순수 최신순).
    """
    total, group_a_ids, group_b_ids = get_interleave_groups(qs, params, premium_author_ids)
    if group_a_ids is None:
        return list(qs[offset:offset + limit]), total

    a_cursor = (offset + 1) // 2
    b_cursor = offset // 2
    result_pks = []

    for pos in range(offset, offset + limit):
        if pos % 2 == 0:
            if a_cursor < len(group_a_ids):
                result_pks.append(group_a_ids[a_cursor])
                a_cursor += 1
            elif b_cursor < len(group_b_ids):
                result_pks.append(group_b_ids[b_cursor])
                b_cursor += 1
            else:
                break
        elif b_cursor < len(group_b_ids):
            result_pks.append(group_b_ids[b_cursor])
            b_cursor += 1
        elif a_cursor < len(group_a_ids):
            result_pks.append(group_a_ids[a_cursor])
            a_cursor += 1
        else:
            break

    if not result_pks:
        return [], total

    by_pk = {eq.pk: eq for eq in qs.filter(pk__in=result_pks)}
    return [by_pk[pk] for pk in result_pks if pk in by_pk], total
