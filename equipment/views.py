from equipment.forms import UserSignupForm
from django.contrib.auth.models import User
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Q, Min, Max, Avg, Count, F, Sum
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from urllib.parse import parse_qs, quote, urlencode, urlparse
import json

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from .models import (
    Equipment, JobPost, ExamPost, ExamComment, Part, EquipmentImage, PartImage, PartsShop,
    YoutubeContent, EquipmentFavorite, PartFavorite, Comment, DeletedListingLog, Profile,
    DriverProfile,
)
from .rental_utils import (
    fetch_call_companies,
    fetch_rental_companies,
    fetch_regional_heavy_companies,
    get_kakao_rest_key,
)
from .exam_utils import extract_youtube_id, fetch_exam_youtube_videos
from soil.models import SoilPost
from .forms import EquipmentForm, EquipmentEditForm, PartForm
from .premium_utils import (
    is_user_premium,
    get_free_listing_count,
    get_monthly_listing_count,
    get_listing_monthly_limit,
    FREE_LISTING_LIMIT,
    PREMIUM_LISTING_LIMIT,
    PREMIUM_MONTHLY_PRICE,
    PREMIUM_BID_SWITCH_MEMBER_COUNT,
    BUMP_WEEKLY_LIMIT,
    get_user_bump_status,
    get_premium_user_ids,
    get_premium_equipment_rotation,
    get_premium_expert_cards,
    pad_premium_expert_cards,
    PREMIUM_EXPERT_BIO_MAX_LENGTH,
    truncate_premium_expert_bio,
    PREMIUM_SIDEBAR_INDEX_PER_SIDE,
    PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY,
)
from .claim_utils import (
    claimable_listings_q,
    claimable_listings_queryset,
    normalize_phone_digits,
)
from .partsshop_validation import validate_partsshop_form
from .listing_filters import (
    exclude_excavator_misclassified_for_non_excavator_tabs,
    exclude_attachment_like_from_non_attachment_tabs,
    filter_attachment_tab,
)
from .index_listing import (
    parse_index_params,
    build_index_equipment_queryset,
    INDEX_INITIAL_COUNT,
    VALID_CATEGORIES,
)


def _image_hash_from_upload(uploaded_file):
    """업로드 파일 내용으로 MD5 해시 (동일 사진 재업로드 감지)."""
    import hashlib
    try:
        uploaded_file.seek(0)
        return hashlib.md5(uploaded_file.read()).hexdigest()
    except Exception:
        return ""


def _image_hash_from_equipment(equipment):
    """매물 대표 사진(첫 번째) 해시 (삭제 시 로그용)."""
    import hashlib
    first = equipment.images.first()
    if not first or not first.image:
        return ""
    try:
        with first.image.open("rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _get_profile_phone_verified(user):
    """휴대폰 본인인증 여부. Profile 없으면 생성 후 False."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
    return getattr(profile, 'phone_verified', False)


def _social_auth_login_url(provider, next_url=''):
    """소셜 로그인 URL. process=login 및 로그인 후 복귀 경로(next) 유지."""
    params = {'process': 'login'}
    if next_url:
        params['next'] = next_url
    return f'/accounts/{provider}/login/?' + urlencode(params)


def _login_next_url(request, explicit_next=''):
    """로그인 후 복귀 경로 — next 파라미터 우선, 없으면 로그인 직전 페이지(매물보기 강제 이동 방지)."""
    next_url = (explicit_next or '').strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    referer = (request.META.get('HTTP_REFERER') or '').strip()
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        from urllib.parse import urlparse
        path = urlparse(referer).path or '/'
        skip_prefixes = ('/login', '/join', '/signup', '/accounts/', '/admin/login')
        if not any(path.startswith(p) for p in skip_prefixes):
            return referer
    return ''


def _redirect_after_login(request, next_url='', default='index'):
    next_url = _login_next_url(request, next_url)
    if next_url:
        return redirect(next_url)
    if default:
        return redirect(default)
    return redirect('index')


def _require_phone_verified_strict(request):
    """로그인 + 휴대폰 본인인증 필수(스태프 제외). 업체 자진등록·현장 자재 등 공개 등록용."""
    if not request.user.is_authenticated:
        return redirect(reverse('login') + '?next=' + quote(request.get_full_path(), safe=''))
    if request.user.is_staff or request.user.is_superuser:
        return None
    if not _get_profile_phone_verified(request.user):
        return redirect(reverse('phone_verify') + '?next=' + quote(request.get_full_path(), safe=''))
    return None


def _user_has_social_account(user):
    """소셜(카카오/네이버 등) 로그인으로 가입·연동된 계정인지 여부. 아이디/비밀번호만 쓰는 회원은 False."""
    if not user or not user.is_authenticated:
        return False
    try:
        from allauth.socialaccount.models import SocialAccount
        return SocialAccount.objects.filter(user=user).exists()
    except Exception:
        return False


def _require_phone_verified(request, next_url=None):
    """
    매물 등록·유료 결제 등 전 휴대폰 인증 필수.
    단, 아이디/비밀번호로 가입한 회원(소셜 연동 없음)은 본인인증 생략.
    인증 필요하고 안 됐으면 redirect 응답 반환, 통과 시 None.
    """
    if not request.user.is_authenticated:
        return redirect('login')
    # 아이디·비밀번호로만 가입한 회원은 본인인증 불필요
    if not _user_has_social_account(request.user):
        return None
    if _get_profile_phone_verified(request.user):
        return None
    from urllib.parse import quote
    from django.urls import reverse
    next_path = next_url or request.get_full_path()
    return redirect(reverse('phone_verify') + '?next=' + quote(next_path, safe=''))


def _build_location_text(region_sido: str, region_sigungu: str) -> str:
    """매물 위치 문자열: 시/도·시/군/구만 사용 (상세 주소 입력 없음)."""
    sido = (region_sido or '').strip()
    sigungu = (region_sigungu or '').strip()
    if sido and sigungu:
        return f"{sido} {sigungu}"
    return sido or ''


def _post_with_coalesced_weight_class(post):
    """
    equipment_form.html 에 name=weight_class 가 중복(숨은 필드 + simple/dump)일 때
    QueryDict.get 가 마지막 값만 쓰면 빈 문자열이 앞쪽 코드를 덮어쓴다.
    굴삭기·지게차: EXC_/FORK_/DUMP_ 코드가 있으면 그것을 단일 weight_class 로 쓴다.
    """
    if post is None:
        return post
    post = post.copy()
    eq_type = (post.get('equipment_type') or '').strip()
    if eq_type not in ('excavator', 'forklift'):
        return post
    vals = post.getlist('weight_class')
    if len(vals) <= 1:
        return post
    best = ''
    for v in vals:
        s = (v or '').strip()
        if not s:
            continue
        if s.startswith(('EXC_', 'FORK_', 'DUMP_')):
            best = s
            break
    if not best:
        for v in vals:
            s = (v or '').strip()
            if s:
                best = s
                break
    post.setlist('weight_class', [best])
    return post


def _is_excavator_tire_5_6_filter(sub_type: str, weight_class: str) -> bool:
    """굴삭기 상세검색에서 '타이어식 5~6 ton' 선택 여부."""
    return sub_type == 'EXC_TIRE' and weight_class == 'EXC_TIRE_LE_6'


def _legacy_excavator_tire_5_6_q() -> Q:
    """
    레거시 데이터 호환:
    - 예전 이관 데이터는 sub_type/weight_class 코드가 비어있거나 잘못된 경우가 있어
      모델명 패턴(EW60/HW60/DX55W/06W 등)도 함께 검색한다.
    """
    return Q(
        model_name__iregex=(
            r"(EW\s*60|EW\s*55|HW\s*60|DX\s*55\s*W|R\s*555\s*W|"
            r"\b55\s*W(?:I)?\b|\b0?6\s*W\b)"
        )
    )


def _exclude_mislabeled_mini_crawler_in_tire_heavy_search(sub_type: str, weight_class: str):
    """
    타이어식 06W/08W 검색인데 DB에 체인 미니(DX55 등)가 타이어+대톤수로 오표기된 매물이 섞이는 경우 제외.
    모델명에 W(윤/타이어 변형)가 있으면 제외하지 않는다.
    해당 조건이 아니면 None.
    """
    if sub_type != "EXC_TIRE" or weight_class not in ("EXC_TIRE_LE_17", "EXC_TIRE_LE_21"):
        return None
    # DX50~DX59, EC55, HX55 등 소형 체인 명칭 — 모델에 W가 들어가면(예: DX55W) 타이어 변형으로 본다.
    return (
        Q(model_name__iregex=r"(?i)\bDX\s*5[0-9]\b(?!.*W)")
        | Q(model_name__iregex=r"(?i)\bEC\s*55\b(?!.*W)")
        | Q(model_name__iregex=r"(?i)\bHX\s*55\b(?!.*W)")
    )


def legacy_redirect_equipment_uid(request, uid):
    """
    구형 매물 URL → /equipment/<pk>/ (301).
    /viewsale/굴삭기{uid}, /attachment/{uid} 등. uid는 이관 시 legacy_listing_id 우선, 없으면 pk로 조회.
    """
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    eq = Equipment.objects.filter(legacy_listing_id=uid_int).first()
    if eq:
        return redirect("equipment_detail", pk=eq.pk, permanent=True)
    if Equipment.objects.filter(pk=uid_int).exists():
        return redirect("equipment_detail", pk=uid_int, permanent=True)
    raise Http404()


def legacy_redirect_job_uid(request, uid):
    """구형 /job/{uid}/ → /jobs/<pk>/ (301). uid는 legacy_guin_uid 우선, 없으면 pk."""
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    job = JobPost.objects.filter(legacy_guin_uid=uid_int).first()
    if job:
        return redirect("job_detail", pk=job.pk, permanent=True)
    if JobPost.objects.filter(pk=uid_int).exists():
        return redirect("job_detail", pk=uid_int, permanent=True)
    raise Http404()


def legacy_redirect_community_to_board(request, uid):
    """구형 /community/{uid}/ → /board/{uid}/ (301)."""
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    return redirect("board_detail", pk=uid_int, permanent=True)


def board_post_detail(request, pk):
    """
    신규 커뮤니티 상세 URL (/board/<pk>/).
    게시판 모델 연동 전까지는 404 (구 URL 301 대상만 유효).
    """
    raise Http404()


def _redirect_repaired_index_query(request):
    """
    잘못된 GET name=/?category=... (pathname+search가 name 값으로 들어온 경우)를
    내장 쿼리스트링을 풀어 정상 목록 URL로 302 리다이렉트한다.
    """
    raw_name = (request.GET.get('name') or '').strip()
    if not raw_name.startswith('/'):
        return None
    parsed = urlparse(raw_name)
    if not parsed.query:
        return None
    embedded = {
        k: (vals[0] if len(vals) == 1 else vals)
        for k, vals in parse_qs(parsed.query, keep_blank_values=True).items()
    }
    merged = {}
    for key in request.GET:
        if key == 'name':
            continue
        merged[key] = request.GET.get(key)
    merged.update(embedded)
    target_path = parsed.path or '/'
    target_qs = urlencode(merged)
    target = target_path + ('?' + target_qs if target_qs else '')
    if target == request.get_full_path():
        return None
    return redirect(target)


def _index_list_card_context(request, params, equipment_chunk, premium_author_ids, favorited_ids):
    """목록 카드 partial 렌더용 공통 컨텍스트."""
    query = params['query']
    hide_advanced_filters = params['hide_advanced_filters']
    filter_category = params['filter_category']
    has_detail_filters = any(
        bool(v) for v in (
            params['maker'],
            params['sub_type'],
            params['weight_class'],
            params['model'],
            params['year_min'],
            params['year_max'],
            params['region_sido'],
            params['region_sigungu'],
            params['mast_type'],
        )
    )
    if params['premium_only'] and not query and not has_detail_filters:
        total_count_label = "유료회원"
    elif query or has_detail_filters:
        total_count_label = "검색결과"
    elif filter_category in VALID_CATEGORIES:
        category_label_map = {
            "excavator": "굴삭기",
            "forklift": "지게차",
            "dump": "덤프트럭",
            "loader": "스키로더/로더",
            "crane": "크레인",
            "attachment": "어태치먼트",
            "other": "기타 중장비",
        }
        total_count_label = category_label_map.get(filter_category, "전체")
    else:
        total_count_label = "전체"
    return {
        'equipment_list': equipment_chunk,
        'premium_author_ids': premium_author_ids,
        'favorited_equipment_ids': favorited_ids,
        'equipment_detail_next_q': quote(request.get_full_path(), safe=''),
        'total_count_label': total_count_label,
    }


def index_load_more(request):
    """더보기: offset부터 per_page개 카드 HTML(JSON) 반환."""
    params = parse_index_params(request)
    if params['hide_advanced_filters']:
        return JsonResponse({'error': 'not_available'}, status=400)

    try:
        offset = max(INDEX_INITIAL_COUNT, int(request.GET.get('offset', str(INDEX_INITIAL_COUNT))))
    except (TypeError, ValueError):
        offset = INDEX_INITIAL_COUNT

    per_page = params['list_per_page']
    qs = build_index_equipment_queryset(request, params)
    total_count = qs.count()
    chunk = list(qs[offset:offset + per_page])

    premium_author_ids = list(get_premium_user_ids())
    favorited_ids = set()
    if request.user.is_authenticated:
        favorited_ids = set(
            EquipmentFavorite.objects.filter(user=request.user).values_list('equipment_id', flat=True)
        )

    card_ctx = _index_list_card_context(request, params, chunk, premium_author_ids, favorited_ids)
    html_mobile = ''.join(
        render_to_string('equipment/partials/index_card_mobile.html', {**card_ctx, 'equipment': eq}, request=request)
        for eq in chunk
    )
    html_pc = ''.join(
        render_to_string('equipment/partials/index_card_pc.html', {**card_ctx, 'equipment': eq}, request=request)
        for eq in chunk
    )
    new_offset = offset + len(chunk)
    return JsonResponse({
        'html_mobile': html_mobile,
        'html_pc': html_pc,
        'offset': new_offset,
        'has_more': new_offset < total_count,
        'total_count': total_count,
        'loaded_count': len(chunk),
    })


# [1] 메인 페이지 (키워드 + 정렬만)
def index(request):
    repaired = _redirect_repaired_index_query(request)
    if repaired is not None:
        return repaired

    params = parse_index_params(request)
    query = params['query']
    sort = params['sort']
    filter_category = params['filter_category']
    hide_advanced_filters = params['hide_advanced_filters']
    list_per_page = params['list_per_page']
    maker = params['maker']
    sub_type = params['sub_type']
    weight_class = params['weight_class']
    model = params['model']
    year_min = params['year_min']
    year_max = params['year_max']
    region_sido = params['region_sido']
    region_sigungu = params['region_sigungu']
    mast_type = params['mast_type']
    premium_only = params['premium_only']

    qs = build_index_equipment_queryset(request, params)
    total_count = qs.count()
    if hide_advanced_filters:
        equipment_list = list(qs)
    else:
        equipment_list = list(qs[:INDEX_INITIAL_COUNT])

    premium_author_ids = list(get_premium_user_ids())
    favorited_ids = set()
    if request.user.is_authenticated:
        favorited_ids = set(
            EquipmentFavorite.objects.filter(user=request.user).values_list('equipment_id', flat=True)
        )

    card_ctx = _index_list_card_context(request, params, equipment_list, premium_author_ids, favorited_ids)
    total_count_label = card_ctx['total_count_label']

    premium_rotation_list = get_premium_equipment_rotation(limit=18, equipment_type=filter_category or None)
    premium_rotation_chunks = [
        premium_rotation_list[i : i + 6]
        for i in range(0, len(premium_rotation_list), 6)
        if premium_rotation_list[i : i + 6]
    ]

    get_copy = request.GET.copy()
    if 'sort' in get_copy:
        get_copy.pop('sort')
    index_query_base = get_copy.urlencode()

    list_offset = INDEX_INITIAL_COUNT if not hide_advanced_filters else total_count
    has_more_list = (not hide_advanced_filters) and (total_count > INDEX_INITIAL_COUNT)

    return render(request, 'equipment/index.html', {
        'equipment_list': equipment_list,
        'list_per_page': list_per_page,
        'list_offset': list_offset,
        'has_more_list': has_more_list,
        'query': query,
        'sort': sort,
        'total_count': total_count,
        'total_count_label': total_count_label,
        'filter_category': filter_category if filter_category in VALID_CATEGORIES else '',
        'favorited_equipment_ids': favorited_ids,
        'premium_rotation_list': premium_rotation_list,
        'premium_rotation_chunks': premium_rotation_chunks,
        'premium_author_ids': premium_author_ids,
        'filter_maker': maker,
        'filter_sub_type': sub_type,
        'filter_weight_class': weight_class,
        'filter_model': model,
        'filter_year_min': year_min,
        'filter_year_max': year_max,
        'filter_region_sido': region_sido,
        'filter_region_sigungu': region_sigungu,
        'filter_mast_type': mast_type,
        'index_query_base': index_query_base,
        'hide_advanced_filters': hide_advanced_filters,
        'premium_only': premium_only,
        'list_back_url': request.get_full_path,
        'equipment_detail_next': quote(request.get_full_path(), safe=''),
    })


def premium_experts_test_view(request):
    """TEST 버튼 전용: 샘플 30개(사진 포함) 미리보기 화면."""
    seeds = list(
        Equipment.objects.visible()
        .filter(equipment_type='excavator')
        .select_related('author')
        .prefetch_related('images')
        .order_by('-created_at')[:30]
    )

    sample_items = []
    if seeds:
        for i in range(30):
            base = seeds[i % len(seeds)]
            first_image = base.images.first()
            sample_items.append({
                'id': i + 1,
                'title': f"[TEST {i + 1:02d}] {base.model_name or '굴삭기 샘플 매물'}",
                'manufacturer': base.manufacturer or '테스트제조사',
                'year': base.year_manufactured or '-',
                'location': base.current_location or base.region_sido or '테스트지역',
                'price': base.listing_price,
                'image_url': first_image.image.url if first_image else '',
                'detail_url': reverse('equipment_detail', args=[base.pk]),
            })
    else:
        for i in range(30):
            sample_items.append({
                'id': i + 1,
                'title': f"[TEST {i + 1:02d}] 굴삭기 샘플 매물",
                'manufacturer': '테스트제조사',
                'year': '-',
                'location': '테스트지역',
                'price': None,
                'image_url': '',
                'detail_url': reverse('index'),
            })

    return render(request, 'equipment/premium_experts_test.html', {
        'sample_items': sample_items,
    })


# [2] 로그인 관련
def user_login(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request, request.GET.get('next', ''))
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        if not username or not password:
            messages.error(request, '아이디와 비밀번호를 입력하세요.')
            next_url = request.POST.get('next') or request.GET.get('next', '')
            return render(request, 'registration/login.html', {
                'next_url': next_url,
                'kakao_login_url': _social_auth_login_url('kakao', next_url),
                'naver_login_url': _social_auth_login_url('naver', next_url),
            })
        user = authenticate(request, username=username, password=password)
        # 보완 로그인은 활성 계정에만 제한한다.
        # (탈퇴 계정은 자동 복구하지 않고 신규가입 흐름으로 유도)
        if user is None:
            # 일부 환경에서 authenticate 실패가 나는 경우를 보완하되,
            # is_active=True 사용자만 허용한다.
            candidate = User.objects.filter(username=username, is_active=True).first()
            if candidate and candidate.check_password(password):
                candidate.backend = 'django.contrib.auth.backends.ModelBackend'
                user = candidate
        if user is not None:
            # 운영 정책: 어드민 계정은 일반 서비스 로그인에서 사용하지 않음
            # (관리자 계정은 /admin/ 에서만 로그인)
            if user.is_staff or user.is_superuser:
                messages.error(request, '관리자 계정은 관리자 페이지에서만 로그인할 수 있습니다.')
                return redirect('/admin/login/')
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next', '')
            return _redirect_after_login(request, next_url)
        messages.error(request, '아이디 또는 비밀번호가 올바르지 않습니다.')
    next_url = _login_next_url(
        request,
        request.GET.get('next') or request.POST.get('next', '') or '',
    )
    kakao_login_url = _social_auth_login_url('kakao', next_url)
    naver_login_url = _social_auth_login_url('naver', next_url)
    return render(request, 'registration/login.html', {
        'next_url': next_url,
        'kakao_login_url': kakao_login_url,
        'naver_login_url': naver_login_url,
    })


def user_logout(request):
    # 세션에 남은 플래시(소셜 로그인 성공 등)를 비우지 않으면 /login/ 등에서 뒤늦게 보일 수 있음
    list(messages.get_messages(request))
    logout(request)
    return redirect('index')


def _signup_open_required(request):
    """신규 가입 비활성 시 안내 페이지."""
    from django.conf import settings
    if getattr(settings, 'SIGNUP_ENABLED', True):
        return None
    return render(request, 'registration/signup_soon.html')


def signup_soon(request):
    """신규 회원가입 준비 중 안내 (SIGNUP_ENABLED=False)."""
    if request.user.is_authenticated:
        return redirect('my_page')
    return render(request, 'registration/signup_soon.html')


def join_choice(request):
    """회원가입 진입: 휴대폰 입력 → 기존 회원인지 확인 → 기존 전환 또는 신규 가입 안내."""
    if request.user.is_authenticated:
        return redirect('my_page')
    # 회원가입 흐름에서는 이름 매칭 안 함 (legacy 전환 전용 세션 제거)
    if 'legacy_convert_name' in request.session:
        del request.session['legacy_convert_name']
        request.session.modified = True
    from urllib.parse import quote
    _base = '/accounts/{}/login/'
    context = {
        'kakao_signup_url': _base.format('kakao'),
        'naver_signup_url': _base.format('naver'),
    }
    return render(request, 'registration/join_choice.html', context)


def phone_send(request):
    """인증번호 발송. POST phone → 6자리 발송, 재발송 30초 제한. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_raw = (request.POST.get('phone') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '휴대폰 번호를 정확히 입력해 주세요.'})
    from .phone_verify_service import send_code
    success, err = send_code(phone_norm)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    return JsonResponse({'ok': True})


def legacy_convert_send_code(request):
    """기존 회원 전환: 이름+휴대폰 저장 후 인증번호 발송. POST name, phone. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    name = (request.POST.get('name') or '').strip()
    phone_raw = (request.POST.get('phone') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '휴대폰 번호를 정확히 입력해 주세요.'})
    request.session['legacy_convert_name'] = name or ''
    request.session.modified = True
    from .phone_verify_service import send_code
    success, err = send_code(phone_norm)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    return JsonResponse({'ok': True})


def phone_verify(request):
    """인증번호 검증. POST phone, code → 성공 시 session['verified_phone'] 설정. 5회 초과 시 실패. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_raw = (request.POST.get('phone') or '').strip()
    code = (request.POST.get('code') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '휴대폰 번호를 입력해 주세요.'})
    if not code or len(code) != 6:
        return JsonResponse({'ok': False, 'error': '인증번호 6자리를 입력해 주세요.'})
    from .phone_verify_service import verify_code
    success, err = verify_code(phone_norm, code)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    request.session['verified_phone'] = phone_norm  # 하이픈 제거 후 저장
    request.session.modified = True
    return JsonResponse({'ok': True})


def join_check(request):
    """인증 완료된 휴대폰(session)으로 연결 가능한 매물 건수 조회. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_norm = request.session.get('verified_phone')
    if not phone_norm:
        return JsonResponse({'ok': False, 'error': '휴대폰 인증을 먼저 완료해 주세요.'})
    listing_count = claimable_listings_queryset(phone_norm).count()
    if listing_count > 0:
        request.session['pending_listing_count'] = listing_count
    else:
        request.session.pop('pending_listing_count', None)
    request.session.modified = True
    return JsonResponse({
        'ok': True,
        'found': listing_count > 0,
        'listing_count': listing_count,
    })


def _normalize_phone(s):
    """숫자만 추출 (010-1234-5678 → 01012345678)."""
    if not s:
        return ''
    import re
    return re.sub(r'\D', '', str(s))


def legacy_convert_intro(request):
    """기존 회원 전환: 이름+휴대폰 → 인증번호 확인 → 기존 정보 조회 → 로그인 후 정식 전환."""
    if request.user.is_authenticated and request.user.username.startswith('legacy_'):
        return redirect('legacy_convert')
    if request.user.is_authenticated:
        return redirect('my_page')
    from urllib.parse import quote
    login_url = '/login/?next=' + quote('/account/convert/')
    return render(request, 'registration/legacy_convert_intro.html', {'login_url': login_url})


def signup_choices(request):
    """신규 회원가입: 카카오/네이버/일반 선택 (필요 시점에만 휴대폰 인증·사업자·유료)."""
    blocked = _signup_open_required(request)
    if blocked:
        return blocked
    if request.user.is_authenticated:
        return redirect('my_page')
    from urllib.parse import quote
    next_url = request.GET.get('next', '') or ''
    _base = '/accounts/{}/login/'
    kakao_signup_url = _base.format('kakao') + ('?next=' + quote(next_url) if next_url else '')
    naver_signup_url = _base.format('naver') + ('?next=' + quote(next_url) if next_url else '')
    return render(request, 'registration/signup_choices.html', {
        'kakao_signup_url': kakao_signup_url,
        'naver_signup_url': naver_signup_url,
    })


def signup(request):
    blocked = _signup_open_required(request)
    if blocked:
        return blocked
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            verified_phone = request.session.pop('verified_phone', None)
            if verified_phone:
                try:
                    profile = Profile.objects.get(user=user)
                    profile.phone = verified_phone
                    profile.phone_verified = True
                    profile.phone_verified_at = timezone.now()
                    profile.save(update_fields=['phone', 'phone_verified', 'phone_verified_at'])
                except Profile.DoesNotExist:
                    Profile.objects.create(user=user, phone=verified_phone, phone_verified=True, phone_verified_at=timezone.now())
            return redirect("signup_done")
    else:
        form = UserSignupForm()
    return render(request, "registration/signup.html", {"form": form})


def signup_done(request):
    """일반 회원가입 완료 안내 화면(로그인 페이지로 이동)."""
    pending_listing_count = int(request.session.get('pending_listing_count') or 0)
    return render(
        request,
        "registration/signup_done.html",
        {'pending_listing_count': pending_listing_count},
    )


def check_username(request):
    from django.conf import settings
    from django.http import JsonResponse
    if not getattr(settings, 'SIGNUP_ENABLED', True):
        return JsonResponse({"ok": False, "msg": "회원가입은 곧 오픈됩니다."})
    username = (request.GET.get("username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "msg": "아이디를 입력하세요."})
    existing = User.objects.filter(username=username).first()
    if existing and existing.is_active:
        return JsonResponse({"ok": False, "msg": "이미 사용 중인 아이디입니다."})
    return JsonResponse({"ok": True, "msg": "사용 가능한 아이디입니다."})


def find_username(request):
    """이메일로 가입 시 사용한 아이디(들) 안내"""
    result = None
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        if email:
            users = User.objects.filter(email__iexact=email).values_list('username', flat=True)
            result = list(users) if users else []
        else:
            messages.error(request, '이메일을 입력하세요.')
    return render(request, 'registration/find_username.html', {'result': result})


def my_page(request):
    if not request.user.is_authenticated:
        return redirect('login')

    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    if request.method == 'POST' and request.POST.get('action') in ('update_premium_card', 'update_bio'):
        if not profile.is_premium_active:
            messages.warning(request, '명함 설정은 유료회원만 이용할 수 있습니다.')
            return redirect('my_page')
        company_name = (request.POST.get('company_name') or '').strip()
        profile.company_name = company_name or None
        phone = (request.POST.get('phone') or '').strip()
        if phone:
            profile.phone = phone
        profile.bio = truncate_premium_expert_bio(request.POST.get('bio') or '')
        if request.POST.get('remove_profile_photo') == '1':
            if profile.profile_photo:
                try:
                    profile.profile_photo.delete(save=False)
                except Exception:
                    pass
            profile.profile_photo = None
        elif request.FILES.get('profile_photo'):
            profile.profile_photo = request.FILES['profile_photo']
        profile.save()
        messages.success(request, '유료회원 명함 정보가 저장되었습니다.')
        return redirect('my_page')

    my_equipments = (
        Equipment.objects
        .filter(author=request.user)
        .annotate(wish_count=Count('favorited_by', distinct=True))
        .order_by('-created_at')
    )
    fav_equipments = (
        Equipment.objects
        .filter(favorited_by__user=request.user)
        .annotate(wish_count=Count('favorited_by', distinct=True))
        .prefetch_related('images')
        .order_by('-favorited_by__created_at')
    )
    fav_parts = Part.objects.filter(favorited_by__user=request.user).order_by('-favorited_by__created_at')
    total_views = my_equipments.aggregate(total=Coalesce(Sum('view_count'), 0))['total'] or 0
    premium_region_inquiry_alerts = []
    if profile.is_premium_active:
        try:
            from chat.models import ChatRoom

            inquiry_rows = (
                ChatRoom.objects.filter(seller=request.user, equipment__isnull=False)
                .exclude(messages__sender=request.user)
                .filter(messages__is_read=False)
                .values('equipment__region_sido', 'equipment__region_sigungu')
                .annotate(
                    unread_count=Count('messages'),
                    room_count=Count('id', distinct=True),
                )
                .order_by('-unread_count', '-room_count')
            )
            for row in inquiry_rows:
                sido = (row.get('equipment__region_sido') or '').strip()
                sigungu = (row.get('equipment__region_sigungu') or '').strip()
                if sido and sigungu:
                    region_label = f"{sido} {sigungu}"
                else:
                    region_label = sido or "지역 미입력"
                premium_region_inquiry_alerts.append({
                    'region_label': region_label,
                    'unread_count': row.get('unread_count') or 0,
                    'room_count': row.get('room_count') or 0,
                })
        except Exception:
            premium_region_inquiry_alerts = []

    stats = {
        'my_count': my_equipments.count(),
        'fav_count': fav_equipments.count() + fav_parts.count(),
        'total_views': total_views,
        'grade_label': '유료회원' if profile.is_premium_active else '무료회원',
    }
    is_legacy_user = request.user.username.startswith('legacy_')
    bump_status = get_user_bump_status(request.user)
    claimable_listing_count = 0
    phone_norm = normalize_phone_digits(profile.phone)
    if phone_norm:
        claimable_listing_count = claimable_listings_queryset(phone_norm).count()
    return render(request, 'registration/my_page.html', {
        'profile': profile,
        'my_equipments': my_equipments,
        'bump_status': bump_status,
        'bump_weekly_limit': BUMP_WEEKLY_LIMIT,
        'fav_equipments': fav_equipments,
        'fav_parts': fav_parts,
        'stats': stats,
        'is_legacy_user': is_legacy_user,
        'free_listing_limit': FREE_LISTING_LIMIT,
        'premium_monthly_price': PREMIUM_MONTHLY_PRICE,
        'premium_region_inquiry_alerts': premium_region_inquiry_alerts,
        'premium_expert_bio_max_length': PREMIUM_EXPERT_BIO_MAX_LENGTH,
        'claimable_listing_count': claimable_listing_count,
    })


def billing_upgrade(request):
    """유료 회원 · 광고 안내 페이지."""
    return render(request, 'billing/upgrade.html', {
        'kakao_inquiry_url': getattr(settings, 'KAKAO_INQUIRY_URL', 'https://open.kakao.com/'),
        'slot': (request.GET.get('slot') or '').strip(),
        'premium_monthly_price': PREMIUM_MONTHLY_PRICE,
        'premium_bid_switch_count': PREMIUM_BID_SWITCH_MEMBER_COUNT,
        'free_listing_limit': FREE_LISTING_LIMIT,
        'premium_listing_limit': PREMIUM_LISTING_LIMIT,
        'bump_weekly_limit': BUMP_WEEKLY_LIMIT,
    })


def company_intro(request):
    """회사소개 페이지."""
    return render(request, 'equipment/company_intro.html', {
        'company_address': '충청북도 음성군 소이면 소이로 313',
        'company_lat': 36.9312186590944,
        'company_lng': 127.752392155881,
        'kakao_map_js_key': _get_kakao_map_js_key(),
    })


@login_required(login_url='/login/')
def find_my_listings(request):
    """
    기존 매물(작성자 없음 + unclaimed_phone_norm)을 프로필 전화번호로 찾아 계정에 연결.
    소셜 가입자는 본인인증 완료 후 이용.
    """
    if _user_has_social_account(request.user):
        need = _require_phone_verified(request, reverse('find_my_listings'))
        if need:
            return need

    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=request.user)

    norm = normalize_phone_digits(profile.phone)
    if not norm:
        messages.error(
            request,
            '연락처가 등록되어 있어야 합니다. 마이페이지에서 전화번호를 입력한 뒤 휴대폰 본인인증을 완료해 주세요.',
        )
        return redirect('my_page')

    candidates = claimable_listings_queryset(norm).order_by('-created_at')

    if request.method == 'POST':
        from django.db import transaction

        raw_ids = request.POST.getlist('equipment_id')
        id_list = []
        for x in raw_ids:
            try:
                id_list.append(int(x))
            except (TypeError, ValueError):
                continue
        if not id_list:
            messages.warning(request, '연결할 매물을 선택해 주세요.')
            return redirect('find_my_listings')

        claimable_q = claimable_listings_q(norm)
        claimed = 0
        with transaction.atomic():
            for eid in id_list:
                eq = (
                    Equipment.objects.select_for_update()
                    .filter(pk=eid)
                    .filter(claimable_q)
                    .first()
                )
                if not eq:
                    continue
                eq.author = request.user
                eq.unclaimed_phone_norm = ''
                eq.ownership_claimed_at = timezone.now()
                eq.save(
                    update_fields=['author', 'unclaimed_phone_norm', 'ownership_claimed_at']
                )
                claimed += 1

        if claimed:
            request.session.pop('pending_listing_count', None)
            request.session.modified = True
            messages.success(request, f'{claimed}건의 매물을 내 계정에 연결했습니다.')
        else:
            messages.warning(request, '연결할 수 있는 매물이 없습니다. 이미 연결되었거나 조건이 맞지 않습니다.')
        return redirect('my_page')

    return render(
        request,
        'registration/find_my_listings.html',
        {
            'candidates': candidates,
            'profile_phone_norm': norm,
        },
    )


@login_required(login_url='/login/')
def verify_phone_page(request):
    """
    휴대폰 본인인증 페이지. 매물 등록·유료 결제 전 필수.
    실제 인증 API(네이버/카카오/나이스 등) 연동 전까지는 안내 페이지.
    DEBUG 시 ?test=1 로 테스트 인증 가능.
    """
    if _get_profile_phone_verified(request.user):
        next_url = request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
            return redirect(next_url)
        return redirect('my_page')

    if request.method == 'POST':
        phone = (request.POST.get('phone') or '').strip()
        # DEBUG 시 테스트 인증 (실서비스에서는 제거 또는 비활성화)
        next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
        if getattr(settings, 'DEBUG', False) and request.GET.get('test'):
            try:
                profile = Profile.objects.get(user=request.user)
                profile.phone = phone or profile.phone
                profile.phone_verified = True
                profile.phone_verified_at = timezone.now()
                profile.save()
                messages.success(request, '휴대폰 인증이 완료되었습니다. (테스트 모드)')
                if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
                    return redirect(next_url)
                return redirect('my_page')
            except Profile.DoesNotExist:
                Profile.objects.create(user=request.user, phone=phone or '', phone_verified=True, phone_verified_at=timezone.now())
                messages.success(request, '휴대폰 인증이 완료되었습니다. (테스트 모드)')
                if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
                    return redirect(next_url)
                return redirect('my_page')
        messages.info(request, '본인인증 API 연동 후 이용 가능합니다. 문의: 관리자.')
    next_url = request.GET.get('next', '')
    try:
        profile = Profile.objects.get(user=request.user)
        phone = profile.phone or ''
    except Profile.DoesNotExist:
        phone = ''
    return render(request, 'registration/phone_verify.html', {
        'next_url': next_url,
        'debug': getattr(settings, 'DEBUG', False),
        'phone': phone,
    })


@login_required(login_url='/login/')
def legacy_convert(request):
    """
    이관 회원(legacy_* 아이디) 정식 회원 전환: 새 아이디·이메일·비밀번호 설정.
    회원가입 인증에서 온 경우 session['verified_phone'] → Profile.phone_verified 처리.
    """
    user = request.user
    if not user.username.startswith('legacy_'):
        messages.info(request, '이미 정식 회원이거나 전환 대상이 아닙니다.')
        return redirect('my_page')
    verified_phone = request.session.pop('verified_phone', None)
    if verified_phone:
        try:
            profile = Profile.objects.get(user=user)
            profile.phone = verified_phone  # 하이픈 제거된 번호 저장
            profile.phone_verified = True
            profile.phone_verified_at = timezone.now()
            profile.save(update_fields=['phone', 'phone_verified', 'phone_verified_at'])
        except Profile.DoesNotExist:
            Profile.objects.create(user=user, phone=verified_phone, phone_verified=True, phone_verified_at=timezone.now())

    if request.method == 'POST':
        new_username = (request.POST.get('new_username') or '').strip()
        email = (request.POST.get('email') or '').strip()
        password1 = request.POST.get('password1') or ''
        password2 = request.POST.get('password2') or ''

        errors = []
        if not new_username:
            errors.append('새 로그인 아이디를 입력하세요.')
        elif new_username.startswith('legacy_'):
            errors.append('새 아이디는 legacy_ 로 시작할 수 없습니다.')
        elif User.objects.filter(username=new_username, is_active=True).exclude(pk=user.pk).exists():
            errors.append('이미 사용 중인 아이디입니다.')
        if not email:
            errors.append('이메일을 입력하세요.')
        if len(password1) < 8:
            errors.append('비밀번호는 8자 이상이어야 합니다.')
        elif password1 != password2:
            errors.append('비밀번호가 일치하지 않습니다.')

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(request, 'registration/legacy_convert.html', {
                'new_username': new_username,
                'email': email,
            })

        user.username = new_username
        user.email = email
        user.set_password(password1)
        user.save()
        # 비밀번호 변경 후 세션 유지 (Django는 비밀번호 바뀌면 세션 무효화할 수 있음)
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        messages.success(request, '정식 회원 전환이 완료되었습니다. 새 아이디로 로그인해 이용해 주세요.')
        return redirect('my_page')

    return render(request, 'registration/legacy_convert.html', {})


@login_required(login_url='/login/')
def account_delete(request):
    """
    회원 탈퇴: 계정 비활성화 + 매물 보관 정책 적용.
    - GET: 확인 페이지
    - POST:
      - 기본: 매물 6개월 보관 후 자동 삭제 예약
      - 옵션 선택 시: 매물 즉시 삭제
    """
    user = request.user

    if request.method != 'POST':
        return render(request, 'registration/account_delete_confirm.html', {'user_obj': user})

    delete_listings_now = request.POST.get('delete_listings_now') == '1'
    now_ts = timezone.now()
    purge_at = now_ts + timedelta(days=180)

    # 매물: 기본은 6개월 보관, 선택 시 즉시 삭제
    if delete_listings_now:
        Equipment.objects.filter(author=user).delete()
    else:
        # author를 유지해야 목록/시세 참고 데이터로 계속 노출됩니다.
        Equipment.objects.filter(author=user).update(is_sold=True)

    # 기타 작성 콘텐츠는 즉시 삭제
    Part.objects.filter(author=user).delete()
    JobPost.objects.filter(author=user).delete()
    SoilPost.objects.filter(author=user).delete()

    # 소셜 계정 연결 해제:
    # 탈퇴 후 재가입은 "신규가입" 정책이므로 기존 소셜 연결을 끊어 inactive 루프로 빠지지 않게 한다.
    try:
        from allauth.socialaccount.models import SocialAccount
        SocialAccount.objects.filter(user=user).delete()
    except Exception:
        pass
    try:
        from allauth.account.models import EmailAddress
        EmailAddress.objects.filter(user=user).delete()
    except Exception:
        pass

    username = user.username
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.withdrawn_at = now_ts
    profile.listing_purge_at = None if delete_listings_now else purge_at
    # 정책: 탈퇴 후 재가입은 신규회원가입으로 처리
    # -> legacy_member_id를 비워 기존회원 전환 탐지 대상에서 제외
    profile.legacy_member_id = None
    profile.save(update_fields=['withdrawn_at', 'listing_purge_at', 'legacy_member_id'])

    # 로그인 차단용 비활성화 처리 (데이터 보관 목적)
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=['is_active', 'password'])
    logout(request)

    if delete_listings_now:
        messages.success(request, f'"{username}" 계정 탈퇴 및 매물 즉시 삭제가 완료되었습니다.')
    else:
        messages.success(
            request,
            f'"{username}" 계정 탈퇴가 완료되었습니다. 등록 매물은 시세 참고용으로 6개월 보관 후 자동 삭제됩니다.',
        )
    return redirect('index')


def _job_list_equipment_q(equipment_key: str):
    """구인구직 기종 선택 → 제목·내용·필요장비 필드 OR 검색."""
    if not equipment_key:
        return None
    if equipment_key == 'excavator':
        return (
            Q(equipment_type__icontains='굴삭')
            | Q(title__icontains='굴삭')
            | Q(content__icontains='굴삭')
        )
    if equipment_key == 'forklift':
        return (
            Q(equipment_type__icontains='지게')
            | Q(title__icontains='지게차')
            | Q(content__icontains='지게차')
        )
    if equipment_key == 'crane':
        return (
            Q(equipment_type__icontains='크레인')
            | Q(title__icontains='크레인')
            | Q(content__icontains='크레인')
        )
    if equipment_key == 'site':
        return (
            Q(equipment_type__icontains='건설')
            | Q(equipment_type__icontains='현장')
            | Q(title__icontains='건설현장')
            | Q(content__icontains='건설현장')
            | Q(title__icontains='건설')
            | Q(content__icontains='건설')
        )
    if equipment_key == 'etc':
        return (
            Q(equipment_type__icontains='기타')
            | Q(title__icontains='기타')
            | Q(content__icontains='기타')
        )
    return None


JOB_EQUIPMENT_KEYS = frozenset({'excavator', 'forklift', 'crane', 'site', 'etc'})
JOB_EQUIPMENT_LABEL_MAP = {
    'excavator': '굴삭기',
    'forklift': '지게차',
    'crane': '크레인기사',
    'site': '건설현장',
    'etc': '기타',
}
JOB_FORM_EQUIPMENT_CHOICES = [
    ('', '선택 안 함'),
    ('excavator', '굴삭기'),
    ('forklift', '지게차'),
    ('crane', '크레인기사'),
    ('site', '건설현장'),
    ('etc', '기타'),
]


def _merge_job_equipment_type(category_key: str, detail: str) -> str:
    """글쓰기 기종 선택 + 상세 입력 → equipment_type 한 필드에 저장."""
    detail = (detail or '').strip()
    cat = (category_key or '').strip()
    if cat and cat not in JOB_EQUIPMENT_LABEL_MAP:
        cat = ''
    if not cat:
        return detail
    label = JOB_EQUIPMENT_LABEL_MAP[cat]
    if not detail:
        return label
    return f"{label} {detail}"


def _split_job_equipment_type(equipment_type: str) -> tuple:
    """수정 폼: equipment_type → (선택값, 상세 텍스트)."""
    et = (equipment_type or '').strip()
    if not et:
        return '', ''
    for key, label in JOB_EQUIPMENT_LABEL_MAP.items():
        if et.startswith(label):
            rest = et[len(label) :].strip()
            return key, rest
    return '', et


# [3] 구인구직 관련
def job_list(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    JOB_EQUIPMENT_CHOICES = [
        ('', '전체'),
        ('excavator', '굴삭기'),
        ('forklift', '지게차'),
        ('crane', '크레인기사'),
        ('site', '건설현장'),
        ('etc', '기타'),
    ]

    qs = JobPost.objects.all().order_by('-created_at')
    job_type = (request.GET.get('type', '') or '').strip().upper()
    region_sido = (request.GET.get('region_sido', '') or '').strip()
    region_sigungu = (request.GET.get('region_sigungu', '') or '').strip()
    equipment = (request.GET.get('equipment', '') or '').strip()
    if equipment not in JOB_EQUIPMENT_KEYS and equipment != '':
        equipment = ''

    if job_type in ('HIRING', 'SEEKING'):
        qs = qs.filter(job_type=job_type)
    if region_sido:
        qs = qs.filter(region_sido=region_sido)
    if region_sigungu:
        qs = qs.filter(region_sigungu=region_sigungu)
    eq_q = _job_list_equipment_q(equipment)
    if eq_q is not None:
        qs = qs.filter(eq_q)

    # 급여 컬럼 표시 여부(한 건이라도 급여 입력이 있으면 표시)
    show_pay_column = qs.exclude(pay__isnull=True).exclude(pay='').exists()

    # 목록용 표시 데이터 정리: 지역 중복 제거 + 한 줄 표기
    jobs = list(qs)
    for job in jobs:
        sido = (job.region_sido or '').strip()
        sigungu = (job.region_sigungu or '').strip()
        location = (job.location or '').strip()

        if sido and sigungu:
            region_line = f"{sido} · {sigungu}"
        elif sido:
            region_line = sido
        elif sigungu:
            region_line = sigungu
        else:
            region_line = location

        if location and region_line and location not in (sido, sigungu, f"{sido} {sigungu}".strip()):
            region_line = f"{region_line} · {location}" if (sido or sigungu) else location

        job.region_line = region_line or '—'

    from django.utils import timezone as dj_tz

    today = dj_tz.now().date()
    job_stats = {
        'total': JobPost.objects.count(),
        'hiring': JobPost.objects.filter(job_type='HIRING').count(),
        'seeking': JobPost.objects.filter(job_type='SEEKING').count(),
        'today': JobPost.objects.filter(created_at__date=today).count(),
    }

    return render(request, 'equipment/job_list.html', {
        'job_list': jobs,
        'jobs': jobs,
        'jobs_section': 'jobs',
        'filter_type': job_type,
        'filter_region_sido': region_sido,
        'filter_region_sigungu': region_sigungu,
        'filter_equipment': equipment,
        'job_equipment_choices': JOB_EQUIPMENT_CHOICES,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
        'job_stats': job_stats,
        'show_pay_column': show_pay_column,
    })


def job_detail(request, pk):
    """구인구직 상세. 문의는 1:1 채팅으로만 가능(공개 댓글 없음)."""
    job = get_object_or_404(JobPost, pk=pk)
    can_view_contact = request.user.is_authenticated
    return render(
        request,
        'equipment/job_detail.html',
        {
            'job': job,
            'can_view_job_contact': can_view_contact,
        },
    )


@login_required(login_url='/login/')
def job_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '구인·구직 글 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        writer = (request.POST.get("writer") or "익명").strip()
        contact = (request.POST.get("contact") or "").strip()
        mode = request.POST.get("job_mode", "hire")
        content_main = (request.POST.get("content") or "").strip()
        pay = (request.POST.get("pay") or "").strip()
        exp = (request.POST.get("exp") or "").strip()
        deadline_str = (request.POST.get("deadline") or "").strip()
        region_sido = (request.POST.get("region_sido") or "").strip()
        region_sigungu = (request.POST.get("region_sigungu") or "").strip()
        deadline = None
        if deadline_str:
            from datetime import datetime
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        if mode == "seek":
            location = (request.POST.get("seek_location") or "").strip()
            label = "구직"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "구인"
            machine = (request.POST.get("machine") or "").strip()

        eq_cat = (request.POST.get("equipment_category") or "").strip()
        if eq_cat not in JOB_EQUIPMENT_KEYS and eq_cat != "":
            eq_cat = ""
        machine = _merge_job_equipment_type(eq_cat, machine)

        deadline_type = (request.POST.get("deadline_type") or "UNTIL_FILLED").strip()
        if deadline_type != "DATE":
            deadline = None
        recruit_count = None
        try:
            rc = request.POST.get("recruit_count", "").strip()
            if rc:
                recruit_count = int(rc)
        except (ValueError, TypeError):
            pass
        doc_resident = "doc_resident" in request.POST
        doc_license = "doc_license" in request.POST
        company_name = (request.POST.get("company_name") or "").strip()
        company_address = (request.POST.get("company_address") or "").strip()

        if not region_sido or not region_sigungu:
            messages.error(request, "시/도와 시/군/구를 모두 선택해 주세요.")
            return render(
                request,
                "equipment/job_form.html",
                {
                    "sido_choices": SIDO_CHOICES,
                    "sigungu_map_json": json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                    "job_equipment_form_choices": JOB_FORM_EQUIPMENT_CHOICES,
                    "equipment_category_selected": eq_cat,
                    "equipment_machine_detail": (
                        (request.POST.get("machine") or request.POST.get("seek_machine") or "").strip()
                    ),
                },
            )
        if not title:
            title = f"[{label}] 제목없음"

        JobPost.objects.create(
            title=title,
            content=content_main,
            location=location,
            region_sido=region_sido,
            region_sigungu=region_sigungu,
            equipment_type=machine,
            pay=pay,
            contact=contact,
            deadline=deadline,
            deadline_type=deadline_type,
            experience=exp,
            writer_display=writer,
            job_type=JobPost.JOB_TYPES[0][0] if mode == "hire" else JobPost.JOB_TYPES[1][0],
            author=request.user if request.user.is_authenticated else None,
            password_hash="",
            recruit_count=recruit_count,
            doc_resident=doc_resident,
            doc_license=doc_license,
            company_name=company_name,
            company_address=company_address,
        )
        return redirect("job_list")

    return render(
        request,
        "equipment/job_form.html",
        {
            "sido_choices": SIDO_CHOICES,
            "sigungu_map_json": json.dumps(SIGUNGU_MAP, ensure_ascii=False),
            "job_equipment_form_choices": JOB_FORM_EQUIPMENT_CHOICES,
            "equipment_category_selected": "",
            "equipment_machine_detail": "",
        },
    )


def job_edit(request, pk):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    job = get_object_or_404(JobPost, pk=pk)
    is_author = request.user.is_authenticated and job.author_id == request.user.id
    if not is_author:
        from django.http import Http404
        raise Http404()

    eq_cat, eq_detail = _split_job_equipment_type(job.equipment_type)
    ctx = {
        'job': job,
        'mode': 'edit',
        'is_author': True,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
        'job_equipment_form_choices': JOB_FORM_EQUIPMENT_CHOICES,
        'equipment_category_selected': eq_cat,
        'equipment_machine_detail': eq_detail,
    }
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        writer = (request.POST.get("writer") or "익명").strip()
        contact = (request.POST.get("contact") or "").strip()
        mode = request.POST.get("job_mode", "hire")
        content_main = (request.POST.get("content") or "").strip()
        pay = (request.POST.get("pay") or "").strip()
        exp = (request.POST.get("exp") or "").strip()
        deadline_str = (request.POST.get("deadline") or "").strip()
        region_sido = (request.POST.get("region_sido") or "").strip()
        region_sigungu = (request.POST.get("region_sigungu") or "").strip()
        deadline = None
        if deadline_str:
            from datetime import datetime
            try:
                deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        if mode == "seek":
            location = (request.POST.get("seek_location") or "").strip()
            label = "구직"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "구인"
            machine = (request.POST.get("machine") or "").strip()

        eq_cat = (request.POST.get("equipment_category") or "").strip()
        if eq_cat not in JOB_EQUIPMENT_KEYS and eq_cat != "":
            eq_cat = ""
        machine = _merge_job_equipment_type(eq_cat, machine)

        if not region_sido or not region_sigungu:
            messages.error(request, "시/도와 시/군/구를 모두 선택해 주세요.")
            ctx["equipment_category_selected"] = eq_cat
            ctx["equipment_machine_detail"] = (
                (request.POST.get("machine") or request.POST.get("seek_machine") or "").strip()
            )
            return render(request, 'equipment/job_form.html', ctx)

        deadline_type = (request.POST.get("deadline_type") or "UNTIL_FILLED").strip()
        if deadline_type != "DATE":
            deadline = None
        recruit_count = None
        try:
            rc = request.POST.get("recruit_count", "").strip()
            if rc:
                recruit_count = int(rc)
        except (ValueError, TypeError):
            pass
        doc_resident = "doc_resident" in request.POST
        doc_license = "doc_license" in request.POST
        company_name = (request.POST.get("company_name") or "").strip()
        company_address = (request.POST.get("company_address") or "").strip()

        if not title:
            title = f"[{label}] 제목없음"
        job.title = title
        job.content = content_main
        job.location = location
        job.region_sido = region_sido
        job.region_sigungu = region_sigungu
        job.equipment_type = machine
        job.pay = pay
        job.contact = contact
        job.deadline = deadline
        job.deadline_type = deadline_type
        job.experience = exp
        job.writer_display = writer
        job.job_type = JobPost.JOB_TYPES[0][0] if mode == "hire" else JobPost.JOB_TYPES[1][0]
        job.recruit_count = recruit_count
        job.doc_resident = doc_resident
        job.doc_license = doc_license
        job.company_name = company_name
        job.company_address = company_address
        job.save()
        return redirect("job_detail", pk=job.pk)

    return render(request, 'equipment/job_form.html', ctx)


def job_delete(request, pk):
    job = get_object_or_404(JobPost, pk=pk)
    is_author = request.user.is_authenticated and job.author_id == request.user.id
    if not is_author:
        from django.http import Http404
        raise Http404()

    if request.method != "POST":
        return render(request, 'equipment/job_delete_confirm.html', {'job': job, 'is_author': True})
    job.delete()
    messages.success(request, "글이 삭제되었습니다.")
    return redirect('job_list')


_EXAM_CATEGORY_KEYS = {c[0] for c in ExamPost.CATEGORY_CHOICES}
_EXAM_EQUIPMENT_KEYS = {c[0] for c in ExamPost.EQUIPMENT_CHOICES}
_EXAM_LIST_PAGE_SIZE = 20
_EXAM_DEFAULT_EQUIPMENT = 'excavator'


def _exam_list_queryset(request):
    qs = (
        ExamPost.objects.select_related('author')
        .annotate(comment_count=Count('comments'))
        .order_by('-created_at')
    )
    category = (request.GET.get('category') or '').strip()
    equipment = (request.GET.get('equipment') or '').strip()

    # 기출문제: 기종은 항상 전체(모든 기종의 기출 표시)
    if category == 'question':
        equipment = ''

    if category == 'video':
        pass
    elif category in _EXAM_CATEGORY_KEYS:
        qs = qs.filter(category=category)
    else:
        qs = qs.exclude(category='video')
    if equipment in _EXAM_EQUIPMENT_KEYS:
        qs = qs.filter(equipment=equipment)
    return qs, category, equipment


def _exam_list_context_base(filter_equipment=''):
    return {
        'filter_equipment': filter_equipment,
        'exam_equipment_tabs': [('', '전체')] + list(ExamPost.EQUIPMENT_CHOICES),
        'exam_category_tabs': [('', '전체')] + list(ExamPost.CATEGORY_CHOICES),
        'jobs_section': 'exam',
    }


def exam_video_list(request):
    """시험동영상 — 유튜브 API 자동 수집 (정비유튜브 /info/ 와 동일 방식)."""
    equipment = (request.GET.get('equipment') or '').strip()
    if equipment not in _EXAM_EQUIPMENT_KEYS:
        equipment = ''
    video_items = fetch_exam_youtube_videos(equipment)
    ctx = _exam_list_context_base(filter_equipment=equipment)
    ctx.update({
        'show_youtube_videos': True,
        'filter_category': 'video',
        'youtube_video_items': video_items,
        'exam_list': [],
        'page_obj': None,
    })
    return render(request, 'equipment/exam_list.html', ctx)


def exam_list(request):
    category = (request.GET.get('category') or '').strip()
    equipment = (request.GET.get('equipment') or '').strip()
    if category == 'question' and equipment:
        params = request.GET.copy()
        del params['equipment']
        url = reverse('exam_list')
        if params:
            url = f'{url}?{params.urlencode()}'
        return redirect(url)
    if category == 'video':
        params = request.GET.copy()
        if 'category' in params:
            del params['category']
        url = reverse('exam_video_list')
        if params:
            url = f'{url}?{params.urlencode()}'
        return redirect(url)
    if not category and not equipment and not request.GET.get('page'):
        return redirect(f"{reverse('exam_video_list')}?equipment={_EXAM_DEFAULT_EQUIPMENT}")

    qs, filter_category, filter_equipment = _exam_list_queryset(request)
    from django.core.paginator import Paginator

    paginator = Paginator(qs, _EXAM_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    posts = list(page_obj.object_list)

    ctx = _exam_list_context_base(filter_equipment=filter_equipment)
    ctx.update({
        'show_youtube_videos': False,
        'filter_category': filter_category,
        'exam_list': posts,
        'page_obj': page_obj,
        'youtube_video_items': [],
    })
    return render(request, 'equipment/exam_list.html', ctx)


def exam_detail(request, pk):
    post = get_object_or_404(ExamPost.objects.select_related('author'), pk=pk)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.get_full_path()}")
        content = (request.POST.get('content') or '').strip()
        if content:
            ExamComment.objects.create(post=post, author=request.user, content=content)
            messages.success(request, '댓글이 등록되었습니다.')
        else:
            messages.error(request, '댓글 내용을 입력해 주세요.')
        return redirect('exam_detail', pk=post.pk)

    ExamPost.objects.filter(pk=pk).update(views=F('views') + 1)
    post.refresh_from_db(fields=['views'])
    comments = post.comments.select_related('author').order_by('created_at')
    youtube_id = ''
    if post.category == 'video' and post.youtube_url:
        youtube_id = extract_youtube_id(post.youtube_url)
    return render(request, 'equipment/exam_detail.html', {
        'post': post,
        'comments': comments,
        'youtube_id': youtube_id,
        'jobs_section': 'exam',
    })


@login_required(login_url='/login/')
def exam_create(request):
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '글 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        content = (request.POST.get('content') or '').strip()
        category = (request.POST.get('category') or '').strip()
        equipment = (request.POST.get('equipment') or '').strip()
        youtube_url = (request.POST.get('youtube_url') or '').strip()
        upload = request.FILES.get('file')

        if not title:
            messages.error(request, '제목을 입력해 주세요.')
        elif category not in _EXAM_CATEGORY_KEYS:
            messages.error(request, '유형을 선택해 주세요.')
        elif equipment not in _EXAM_EQUIPMENT_KEYS:
            messages.error(request, '기종을 선택해 주세요.')
        elif category == 'video':
            if not youtube_url:
                messages.error(request, '시험동영상 유형은 유튜브 URL을 입력해 주세요.')
            elif not extract_youtube_id(youtube_url):
                messages.error(request, '올바른 유튜브 URL을 입력해 주세요.')
            else:
                ExamPost.objects.create(
                    author=request.user,
                    title=title,
                    content=content,
                    category=category,
                    equipment=equipment,
                    youtube_url=youtube_url,
                    file=upload,
                )
                messages.success(request, '글이 등록되었습니다.')
                return redirect('exam_list')
        elif not content:
            messages.error(request, '내용을 입력해 주세요.')
        else:
            ExamPost.objects.create(
                author=request.user,
                title=title,
                content=content,
                category=category,
                equipment=equipment,
                file=upload,
            )
            messages.success(request, '글이 등록되었습니다.')
            return redirect('exam_list')

    return render(request, 'equipment/exam_form.html', {
        'exam_category_choices': ExamPost.CATEGORY_CHOICES,
        'exam_equipment_choices': ExamPost.EQUIPMENT_CHOICES,
        'jobs_section': 'exam',
    })


@login_required(login_url='/login/')
def exam_edit(request, pk):
    post = get_object_or_404(ExamPost, pk=pk)
    if post.author_id != request.user.id and not request.user.is_staff:
        raise Http404()

    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '글 수정을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        content = (request.POST.get('content') or '').strip()
        category = (request.POST.get('category') or '').strip()
        equipment = (request.POST.get('equipment') or '').strip()
        youtube_url = (request.POST.get('youtube_url') or '').strip()
        upload = request.FILES.get('file')

        if not title:
            messages.error(request, '제목을 입력해 주세요.')
        elif category not in _EXAM_CATEGORY_KEYS:
            messages.error(request, '유형을 선택해 주세요.')
        elif equipment not in _EXAM_EQUIPMENT_KEYS:
            messages.error(request, '기종을 선택해 주세요.')
        elif category == 'video':
            if not youtube_url:
                messages.error(request, '시험동영상 유형은 유튜브 URL을 입력해 주세요.')
            elif not extract_youtube_id(youtube_url):
                messages.error(request, '올바른 유튜브 URL을 입력해 주세요.')
            else:
                post.title = title
                post.content = content
                post.category = category
                post.equipment = equipment
                post.youtube_url = youtube_url
                if upload:
                    post.file = upload
                post.save()
                messages.success(request, '글이 수정되었습니다.')
                return redirect('exam_detail', pk=post.pk)
        elif not content:
            messages.error(request, '내용을 입력해 주세요.')
        else:
            post.title = title
            post.content = content
            post.category = category
            post.equipment = equipment
            post.youtube_url = youtube_url or None
            if upload:
                post.file = upload
            post.save()
            messages.success(request, '글이 수정되었습니다.')
            return redirect('exam_detail', pk=post.pk)

    return render(request, 'equipment/exam_form.html', {
        'post': post,
        'is_edit': True,
        'exam_category_choices': ExamPost.CATEGORY_CHOICES,
        'exam_equipment_choices': ExamPost.EQUIPMENT_CHOICES,
        'jobs_section': 'exam',
    })


@login_required(login_url='/login/')
def exam_delete(request, pk):
    post = get_object_or_404(ExamPost, pk=pk)
    if post.author_id != request.user.id and not request.user.is_staff:
        raise Http404()
    if request.method == 'POST':
        post.delete()
        messages.success(request, '글이 삭제되었습니다.')
        return redirect('exam_list')
    messages.warning(request, '삭제는 확인 후 진행해 주세요.')
    return redirect('exam_detail', pk=pk)


# [3-1] 굴삭기 유튜브·정보
def excavator_info(request):
    """유튜브 콘텐츠: 기종 + 목적 동시 필터 (YouTube Data API + 일 1회 캐시)."""
    import json
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
    from django.core.cache import cache

    selected_equipment_type = (request.GET.get("equipment_type", "all") or "all").strip().lower()
    selected_purpose = (request.GET.get("purpose", "excavator_maintenance") or "excavator_maintenance").strip().lower()

    equipment_tabs = [
        ("all", "전체"),
        ("excavator", "굴삭기"),
        ("forklift", "지게차"),
        ("dump", "덤프트럭"),
        ("loader", "스키로더"),
        ("crane", "크레인"),
        ("attachment", "어태치먼트"),
    ]
    equipment_label_map = {
        "all": "전체",
        "excavator": "굴삭기",
        "forklift": "지게차",
        "dump": "덤프트럭",
        "loader": "스키로더",
        "crane": "크레인",
        "attachment": "어태치먼트",
    }
    purpose_tabs = [
        ("excavator_maintenance", "굴삭기 정비"),
        ("excavator_repair", "굴삭기 수리"),
        ("forklift_maintenance", "지게차 정비"),
        ("dump_maintenance", "덤프트럭 정비"),
        ("excavator_inspection", "굴삭기 점검"),
    ]
    purpose_keyword_map = {
        "excavator_maintenance": "굴삭기 정비",
        "excavator_repair": "굴삭기 수리",
        "forklift_maintenance": "지게차 정비",
        "dump_maintenance": "덤프트럭 정비",
        "excavator_inspection": "굴삭기 점검",
    }

    valid_equipment = {k for k, _ in equipment_tabs}
    valid_purpose = {k for k, _ in purpose_tabs}
    if selected_equipment_type not in valid_equipment:
        selected_equipment_type = "all"
    if selected_purpose not in valid_purpose:
        selected_purpose = "excavator_maintenance"

    base_keyword = purpose_keyword_map[selected_purpose]
    equipment_label = equipment_label_map.get(selected_equipment_type, "")
    if selected_equipment_type == "all" or equipment_label in base_keyword:
        query_keyword = base_keyword
    else:
        query_keyword = f"{equipment_label} {base_keyword}"

    def _fetch_youtube_items():
        api_key = (getattr(settings, "YOUTUBE_API_KEY", "") or "").strip()
        if not api_key:
            return []
        cache_key = f"youtube_api:{selected_equipment_type}:{selected_purpose}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        params = {
            "part": "snippet",
            "q": query_keyword,
            "type": "video",
            "maxResults": 24,
            "order": "relevance",
            "regionCode": "KR",
            "safeSearch": "moderate",
            "key": api_key,
        }
        req_url = f"https://www.googleapis.com/youtube/v3/search?{urlencode(params)}"
        try:
            req = Request(req_url)
            with urlopen(req, timeout=7) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return []

        items = []
        for row in payload.get("items") or []:
            video_id = (
                ((row.get("id") or {}).get("videoId") or "").strip()
            )
            snippet = row.get("snippet") or {}
            if not video_id:
                continue
            thumbs = snippet.get("thumbnails") or {}
            thumb = (
                ((thumbs.get("high") or {}).get("url"))
                or ((thumbs.get("medium") or {}).get("url"))
                or ((thumbs.get("default") or {}).get("url"))
                or ""
            )
            items.append({
                "title": (snippet.get("title") or "").strip(),
                "channel_title": (snippet.get("channelTitle") or "").strip(),
                "thumbnail_url": thumb,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                "equipment_label": equipment_label_map.get(selected_equipment_type, "전체"),
                "purpose_label": purpose_keyword_map.get(selected_purpose, ""),
            })
        cache.set(cache_key, items, timeout=86400)
        return items

    video_items = _fetch_youtube_items()
    if not video_items:
        contents = YoutubeContent.objects.filter(is_active=True)
        if selected_equipment_type != "all":
            contents = contents.filter(equipment_type=selected_equipment_type)
        fallback = []
        for item in contents[:24]:
            fallback.append({
                "title": item.title,
                "channel_title": "굴삭기나라",
                "thumbnail_url": "",
                "youtube_url": item.youtube_url,
                "equipment_label": item.get_equipment_type_display(),
                "purpose_label": item.get_purpose_display(),
            })
        video_items = fallback

    return render(request, "equipment/excavator_info.html", {
        "equipment_tabs": equipment_tabs,
        "purpose_tabs": purpose_tabs,
        "selected_equipment_type": selected_equipment_type,
        "selected_purpose": selected_purpose,
        "video_items": video_items,
    })


def finance(request):
    """금융/할부 계산기 + 상담 신청."""
    from .claim_utils import normalize_phone_digits
    from .models import FinanceConsultation
    from .phone_verify_service import send_sms

    months_options = [12, 24, 36, 48, 60, 72]
    equipment_options = [
        "굴삭기",
        "지게차",
        "덤프트럭",
        "스키로더/로더",
        "크레인",
        "어태치먼트",
        "기타 중장비",
    ]
    listing_id_raw = (request.GET.get("listing_id") or request.POST.get("listing_id") or "").strip()
    source_listing = None
    if listing_id_raw.isdigit():
        source_listing = Equipment.objects.filter(pk=int(listing_id_raw)).first()

    if request.method == "POST":
        from .finance_security import (
            check_finance_consult_rate_limit,
            get_client_ip,
            verify_recaptcha_v3,
        )

        security_passed = True
        client_ip = get_client_ip(request)
        allowed, rate_msg = check_finance_consult_rate_limit(client_ip)
        if not allowed:
            messages.error(request, rate_msg)
            security_passed = False
        if security_passed:
            captcha_token = (request.POST.get("g-recaptcha-response") or "").strip()
            captcha_ok, captcha_msg = verify_recaptcha_v3(captcha_token, client_ip)
            if not captcha_ok:
                messages.error(request, captcha_msg)
                security_passed = False

        if security_passed:
            applicant_name = (request.POST.get("applicant_name") or "").strip()
            contact = (request.POST.get("contact") or "").strip()
            desired_equipment_select = (request.POST.get("desired_equipment_select") or "").strip()
            desired_equipment_custom = (request.POST.get("desired_equipment_custom") or "").strip()
            budget_raw = (request.POST.get("budget_manwon") or "").strip().replace(",", "")
            desired_months_raw = (request.POST.get("desired_months") or "").strip()
            memo = (request.POST.get("memo") or "").strip()

            desired_equipment = desired_equipment_custom if desired_equipment_select == "custom" else desired_equipment_select
            if desired_equipment_select in ("", "none") and desired_equipment_custom:
                desired_equipment = desired_equipment_custom

            errors = []
            if not applicant_name:
                errors.append("신청자 이름을 입력해 주세요.")
            if not contact:
                errors.append("연락처를 입력해 주세요.")
            if not desired_equipment:
                errors.append("희망 장비를 선택하거나 직접 입력해 주세요.")
            try:
                budget_manwon = int(budget_raw)
                if budget_manwon <= 0:
                    raise ValueError
            except Exception:
                budget_manwon = 0
                errors.append("구입 예산(만원)을 올바르게 입력해 주세요.")
            try:
                desired_months = int(desired_months_raw)
                if desired_months not in months_options:
                    raise ValueError
            except Exception:
                desired_months = 0
                errors.append("희망 할부기간을 선택해 주세요.")

            if errors:
                for err in errors:
                    messages.error(request, err)
            else:
                FinanceConsultation.objects.create(
                    applicant_name=applicant_name,
                    contact=contact,
                    desired_equipment=desired_equipment,
                    budget_manwon=budget_manwon,
                    desired_months=desired_months,
                    memo=memo,
                )
                admin_phone = normalize_phone_digits(getattr(settings, "FINANCE_ADMIN_PHONE", ""))
                contact_digits = normalize_phone_digits(contact)
                if source_listing:
                    admin_msg = (
                        "[굴삭기나라] 매물 할부상담 신청\n"
                        f"매물명: {source_listing.model_name or source_listing.get_equipment_type_display()}\n"
                        f"이름: {applicant_name}\n"
                        f"연락처: {contact}\n"
                        f"희망 할부기간: {desired_months}개월"
                    )
                else:
                    admin_msg = (
                        "[굴삭기나라] 할부상담 신청\n"
                        f"이름: {applicant_name}\n"
                        f"연락처: {contact}\n"
                        f"희망장비: {desired_equipment}\n"
                        f"예산: {budget_manwon:,}원\n"
                        f"할부기간: {desired_months}개월"
                    )
                if admin_phone:
                    send_sms(admin_phone, admin_msg)
                messages.success(request, "할부 상담 신청이 접수되었습니다.")
                if source_listing:
                    return redirect(f"{reverse('finance')}?listing_id={source_listing.pk}")
                return redirect("finance")

    return render(request, "equipment/finance.html", {
        "months_options": months_options,
        "equipment_options": equipment_options,
        "default_rate": "5.9",
        "source_listing": source_listing,
        "recaptcha_site_key": (getattr(settings, "RECAPTCHA_SITE_KEY", "") or "").strip(),
    })


def _get_kakao_map_js_key():
    key = (getattr(settings, "KAKAO_MAP_JS_KEY", "") or "").strip()
    if key:
        return key
    try:
        from allauth.socialaccount.models import SocialApp
        return (
            SocialApp.objects.filter(provider="kakao")
            .values_list("client_id", flat=True)
            .first()
            or ""
        ).strip()
    except Exception:
        return ""


def parts_as(request):
    """부품/AS 센터 지도 + 목록 검색 페이지."""
    region = (request.GET.get('region', '') or '').strip()
    equipment_type = (request.GET.get('equipment_type', 'all') or 'all').strip().lower()
    shop_kind = (request.GET.get('shop_kind') or request.GET.get('type') or 'all').strip().lower()
    focus_shop_id = request.GET.get('shop', '').strip()

    equipment_type_choices = [
        ("all", "전체"),
        ("excavator", "굴삭기"),
        ("forklift", "지게차"),
        ("dump", "덤프트럭"),
        ("loader", "스키로더·로더"),
        ("crane", "크레인"),
        ("attachment", "어태치먼트"),
        ("other", "기타"),
    ]
    equipment_label_by_key = {k: v for k, v in equipment_type_choices}

    region_options = list(
        PartsShop.objects.exclude(region="").values_list("region", flat=True).distinct().order_by("region")
    )

    kakao_map_js_key = _get_kakao_map_js_key()

    return render(request, 'equipment/parts_as.html', {
        'region': region,
        'focus_shop_id': focus_shop_id,
        'selected_equipment_type': equipment_type if equipment_type in equipment_label_by_key else "all",
        'selected_shop_kind': shop_kind or "all",
        'equipment_type_choices': equipment_type_choices,
        'region_options': region_options,
        'excavator_manufacturers': PartsShop.MANUFACTURER_CHOICES,
        'excavator_ton_ranges': PartsShop.TON_RANGE_CHOICES,
        'excavator_repair_types': PartsShop.REPAIR_TYPE_CHOICES,
        'kakao_map_js_key': kakao_map_js_key,
        'show_driver_register_button': request.user.is_authenticated,
    })


@login_required(login_url='/login/')
def parts_as_register(request):
    """업체 자진 등록(로그인 + 휴대폰 본인인증 필수)."""
    redirect_resp = _require_phone_verified_strict(request)
    if redirect_resp:
        return redirect_resp

    equipment_type_options = [
        ("excavator", "굴삭기"),
        ("dump", "덤프트럭"),
        ("forklift", "지게차"),
        ("crane", "크레인"),
        ("skidloader", "스키로더·로더"),
        ("other", "기타"),
    ]
    shop_kind_options = [
        ("parts", "부품점"),
        ("as", "AS센터"),
    ]

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        shop_kind = (request.POST.get("shop_kind") or "parts").strip().lower()
        region = (request.POST.get("region") or "").strip()
        contact = (request.POST.get("contact") or "").strip()
        address = (request.POST.get("address") or "").strip()
        note = (request.POST.get("note") or "").strip()
        selected_equipment_types = [x for x in request.POST.getlist("equipment_types") if x]

        if not name or not region or not contact:
            messages.error(request, "업체명, 지역, 연락처는 필수입니다.")
        elif validation_error := validate_partsshop_form(
            name=name,
            region=region,
            contact=contact,
            address=address,
            note=note,
        ):
            messages.error(request, validation_error)
        else:
            if shop_kind not in ("parts", "as"):
                shop_kind = "parts"
            if not selected_equipment_types:
                selected_equipment_types = ["excavator"]
            # 중복 제거 + 입력 순서 유지
            selected_equipment_types = list(dict.fromkeys(selected_equipment_types))

            PartsShop.objects.create(
                name=name,
                shop_kind=shop_kind,
                region=region,
                equipment_types=selected_equipment_types,
                contact=contact,
                address=address,
                note=note,
            )
            messages.success(request, "업체 등록이 완료되었습니다.")
            return redirect("parts_as")

    return render(request, "equipment/parts_as_register.html", {
        "equipment_type_options": equipment_type_options,
        "shop_kind_options": shop_kind_options,
    })


def _kakao_geocode(address):
    addr = (address or "").strip()
    if not addr:
        return None
    key = get_kakao_rest_key()
    if not key:
        return None
    try:
        from urllib.request import Request, urlopen

        query = urlencode({"query": addr})
        req_url = f"https://dapi.kakao.com/v2/local/search/address.json?{query}"
        request_obj = Request(req_url, headers={"Authorization": f"KakaoAK {key}"})
        with urlopen(request_obj, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        docs = payload.get("documents") or []
        if not docs:
            return None
        top = docs[0]
        return float(top.get("y")), float(top.get("x"))
    except Exception:
        return None


def driver_list(request):
    """중기 호출 목록(기사 직접등록 + 카카오 자동수집)."""
    region = (request.GET.get("region", "") or "").strip()
    equipment_type = (request.GET.get("equipment_type", "all") or "all").strip().lower()
    focus_driver_id = request.GET.get("driver", "").strip()

    equipment_type_choices = [
        ("all", "전체"),
        ("excavator", "굴삭기"),
        ("forklift", "지게차"),
        ("dump", "덤프트럭"),
        ("loader", "스키로더·로더"),
        ("crane", "크레인"),
        ("attachment", "어태치먼트"),
        ("other", "기타"),
    ]
    equipment_label_by_key = {k: v for k, v in equipment_type_choices}
    region_options = list(
        PartsShop.objects.exclude(region="").values_list("region", flat=True).distinct().order_by("region")
    )

    return render(request, "equipment/parts_as.html", {
        "region": region,
        "focus_driver_id": focus_driver_id,
        "focus_shop_id": "",
        "selected_equipment_type": equipment_type if equipment_type in equipment_label_by_key else "all",
        "selected_shop_kind": "call",
        "equipment_type_choices": equipment_type_choices,
        "region_options": region_options,
        "excavator_manufacturers": PartsShop.MANUFACTURER_CHOICES,
        "excavator_ton_ranges": PartsShop.TON_RANGE_CHOICES,
        "excavator_repair_types": PartsShop.REPAIR_TYPE_CHOICES,
        "kakao_map_js_key": _get_kakao_map_js_key(),
        "show_driver_register_button": request.user.is_authenticated,
    })


@login_required(login_url="/login/")
def driver_register(request):
    redirect_resp = _require_phone_verified_strict(request)
    if redirect_resp:
        return redirect_resp

    equipment_choices = DriverProfile.EQUIPMENT_CHOICES
    experience_choices = DriverProfile.EXPERIENCE_CHOICES

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        equipment_type = (request.POST.get("equipment_type") or "excavator").strip().lower()
        experience = (request.POST.get("experience") or "1").strip()
        region = (request.POST.get("region") or "").strip()
        address = (request.POST.get("address") or "").strip()
        day_rate = (request.POST.get("day_rate") or "").strip()
        contact = (request.POST.get("contact") or "").strip()
        license_name = (request.POST.get("license") or "").strip()
        description = (request.POST.get("description") or "").strip()
        is_available = (request.POST.get("is_available") or "Y") == "Y"

        if not name or not region or not contact:
            messages.error(request, "이름, 활동 지역, 연락처는 필수입니다.")
        else:
            coords = _kakao_geocode(address) if address else None
            day_rate_val = None
            if day_rate.isdigit():
                day_rate_val = int(day_rate)
            profile = DriverProfile.objects.create(
                author=request.user,
                name=name,
                equipment_type=equipment_type if equipment_type in {x[0] for x in equipment_choices} else "other",
                experience=experience if experience in {x[0] for x in experience_choices} else "1",
                region=region,
                address=address,
                latitude=(coords[0] if coords else None),
                longitude=(coords[1] if coords else None),
                day_rate=day_rate_val,
                contact=contact,
                license=license_name,
                description=description,
                is_available=is_available,
            )
            messages.success(request, "중기 기사 등록이 완료되었습니다.")
            return redirect(f"{reverse('parts_as')}?type=call&driver={profile.pk}")

    return render(request, "equipment/driver_form.html", {
        "equipment_choices": equipment_choices,
        "experience_choices": experience_choices,
        "driver": None,
    })


def driver_detail(request, pk):
    driver = get_object_or_404(DriverProfile, pk=pk)
    return render(request, "equipment/driver_detail.html", {
        "driver": driver,
        "can_edit": request.user.is_authenticated and request.user.pk == driver.author_id,
        "kakao_map_js_key": _get_kakao_map_js_key(),
    })


@login_required(login_url="/login/")
def driver_edit(request, pk):
    driver = get_object_or_404(DriverProfile, pk=pk, author=request.user)
    redirect_resp = _require_phone_verified_strict(request)
    if redirect_resp:
        return redirect_resp

    equipment_choices = DriverProfile.EQUIPMENT_CHOICES
    experience_choices = DriverProfile.EXPERIENCE_CHOICES
    if request.method == "POST":
        driver.name = (request.POST.get("name") or "").strip()
        driver.equipment_type = (request.POST.get("equipment_type") or driver.equipment_type).strip().lower()
        driver.experience = (request.POST.get("experience") or driver.experience).strip()
        driver.region = (request.POST.get("region") or "").strip()
        driver.address = (request.POST.get("address") or "").strip()
        day_rate = (request.POST.get("day_rate") or "").strip()
        driver.day_rate = int(day_rate) if day_rate.isdigit() else None
        driver.contact = (request.POST.get("contact") or "").strip()
        driver.license = (request.POST.get("license") or "").strip()
        driver.description = (request.POST.get("description") or "").strip()
        driver.is_available = (request.POST.get("is_available") or "Y") == "Y"
        coords = _kakao_geocode(driver.address) if driver.address else None
        if coords:
            driver.latitude = coords[0]
            driver.longitude = coords[1]
        driver.save()
        messages.success(request, "기사 정보가 수정되었습니다.")
        return redirect("driver_detail", pk=driver.pk)

    return render(request, "equipment/driver_form.html", {
        "equipment_choices": equipment_choices,
        "experience_choices": experience_choices,
        "driver": driver,
    })


@login_required(login_url="/login/")
def driver_delete(request, pk):
    driver = get_object_or_404(DriverProfile, pk=pk, author=request.user)
    if request.method == "POST":
        driver.delete()
        messages.success(request, "기사 정보가 삭제되었습니다.")
        return redirect(f"{reverse('parts_as')}?type=call")
    return redirect("driver_detail", pk=pk)


def _equipment_aliases_by_key():
    return {
        "excavator": {"excavator", "굴삭기", "포크레인"},
        "dump": {"dump", "덤프", "덤프트럭"},
        "forklift": {"forklift", "지게차"},
        "crane": {"crane", "크레인"},
        "loader": {"loader", "skidloader", "스키로더", "로더", "스키로더·로더"},
        "attachment": {"attachment", "어태치먼트"},
        "other": {"other", "기타"},
    }


def _equipment_label_by_key():
    return {
        "excavator": "굴삭기",
        "forklift": "지게차",
        "dump": "덤프트럭",
        "loader": "스키로더·로더",
        "crane": "크레인",
        "attachment": "어태치먼트",
        "other": "기타",
    }


def _match_equipment_type(equipment_type, equipment_tokens):
    if not equipment_type or equipment_type == "all":
        return True
    aliases = _equipment_aliases_by_key().get(equipment_type, {equipment_type})
    return any(token in aliases for token in equipment_tokens)


def _normalize_type_filter(request):
    """type(신규) 또는 center_type(기존) 파라미터를 통합."""
    raw = (request.GET.get("type") or request.GET.get("center_type") or "all").strip().lower()
    mapping = {
        "as": "as_center",
        "as_center": "as_center",
        "parts": "parts",
        "rental": "rental",
        "rental_company": "rental",
        "rental_user": "rental",
        "call": "call",
        "call_kakao": "call",
        "call_driver": "call",
        "all": "all",
    }
    return mapping.get(raw, "all")


def _kakao_place_to_center(item, *, uid_prefix, place_type, center_type_label, equipment_label_by_key, equipment_type, region):
    item_eq = (item.get("equipment_type") or equipment_type or "other").strip().lower()
    if equipment_type and equipment_type != "all" and item_eq != equipment_type:
        if not _match_equipment_type(equipment_type, [item_eq]):
            return None
    eq_label = equipment_label_by_key.get(item_eq, item_eq)
    return {
        "id": item.get("id"),
        "uid": f"{uid_prefix}-{item.get('id')}",
        "type": place_type,
        "name": item.get("name") or center_type_label,
        "lat": item.get("lat"),
        "lng": item.get("lng"),
        "phone": item.get("phone") or "",
        "address": item.get("address") or "",
        "center_type": center_type_label,
        "center_type_key": place_type,
        "equipment_label": eq_label if equipment_type != "all" else (eq_label or "건설기계"),
        "manufacturers": [],
        "ton_ranges": [],
        "repair_types": [],
        "operating_hours": item.get("category_name") or "",
        "region": item.get("region") or region or "",
        "rating": 0,
        "review_count": 0,
        "rental_price": "",
        "rental_period": "",
        "detail_url": item.get("place_url") or "",
        "is_personal": False,
    }


def service_centers_api(request):
    """지도/목록 마커용 서비스센터 + 임대·지역중기·호출 데이터 API."""
    from rental.models import RentalCompany, RentalPost

    equipment_type = (request.GET.get("equipment_type") or "all").strip().lower()
    manufacturers = [x.strip() for x in (request.GET.get("manufacturers") or "").split(",") if x.strip()]
    ton_ranges = [x.strip() for x in (request.GET.get("ton_ranges") or "").split(",") if x.strip()]
    repair_types = [x.strip() for x in (request.GET.get("repair_types") or "").split(",") if x.strip()]
    region = (request.GET.get("region") or "").strip()
    type_filter = _normalize_type_filter(request)
    equipment_label_by_key = _equipment_label_by_key()
    region_scope = region or "전국"

    centers = []

    if type_filter in ("all", "as_center", "parts"):
        centers_qs = PartsShop.objects.all()
        if type_filter == "as_center":
            centers_qs = centers_qs.filter(shop_kind="as")
        elif type_filter == "parts":
            centers_qs = centers_qs.filter(shop_kind="parts")
        if region:
            centers_qs = centers_qs.filter(region__icontains=region)

        for center in centers_qs:
            center_manufacturers = list(center.manufacturers or center.manufacturer or [])
            center_ton_ranges = list(center.ton_ranges or [])
            center_repair_types = list(center.repair_types or [])
            center_equipment_types = [str(x).strip().lower() for x in (center.equipment_types or []) if str(x).strip()]
            if not _match_equipment_type(equipment_type, center_equipment_types):
                continue
            if manufacturers and not any(x in center_manufacturers for x in manufacturers):
                continue
            if ton_ranges and not any(x in center_ton_ranges for x in ton_ranges):
                continue
            if repair_types and not any(x in center_repair_types for x in repair_types):
                continue

            shop_type = "as_center" if center.shop_kind == "as" else "parts"
            centers.append({
                "id": center.pk,
                "uid": f"{shop_type}-{center.pk}",
                "type": shop_type,
                "name": center.name,
                "lat": center.lat,
                "lng": center.lng,
                "phone": center.contact,
                "address": center.address,
                "center_type": center.get_shop_kind_display(),
                "center_type_key": center.shop_kind,
                "equipment_label": ", ".join(
                    equipment_label_by_key.get(k, k)
                    for k in center_equipment_types
                    if k in equipment_label_by_key
                ) or "-",
                "manufacturers": center_manufacturers,
                "ton_ranges": center_ton_ranges,
                "repair_types": center_repair_types,
                "operating_hours": center.note or "",
                "region": center.region,
                "rating": float(center.rating or 0),
                "review_count": int(center.review_count or 0),
                "rental_price": "",
                "rental_period": "",
                "detail_url": "",
                "is_personal": False,
            })

    if type_filter in ("all", "rental"):
        rental_company_qs = RentalCompany.objects.filter(is_active=True)
        if region:
            rental_company_qs = rental_company_qs.filter(region__icontains=region)

        for company in rental_company_qs:
            company_equipment_types = [str(x).strip().lower() for x in (company.equipment_types or []) if str(x).strip()]
            if not _match_equipment_type(equipment_type, company_equipment_types):
                continue
            centers.append({
                "id": company.pk,
                "uid": f"rental_company-{company.pk}",
                "type": "rental_company",
                "name": company.name,
                "lat": company.lat,
                "lng": company.lng,
                "phone": company.contact,
                "address": company.address,
                "center_type": "임대업체",
                "center_type_key": "rental_company",
                "equipment_label": ", ".join(
                    equipment_label_by_key.get(k, k)
                    for k in company_equipment_types
                    if k in equipment_label_by_key
                ) or "-",
                "manufacturers": [],
                "ton_ranges": [],
                "repair_types": [],
                "operating_hours": company.note or "",
                "region": company.region,
                "rating": 0,
                "review_count": 0,
                "rental_price": "",
                "rental_period": "",
                "detail_url": "",
                "is_personal": False,
            })

        rental_post_qs = RentalPost.objects.filter(
            is_available=True,
            lat__isnull=False,
            lng__isnull=False,
        ).select_related("author")
        if region:
            rental_post_qs = rental_post_qs.filter(region__icontains=region)

        for post in rental_post_qs:
            post_equipment_types = [post.equipment_type]
            if not _match_equipment_type(equipment_type, post_equipment_types):
                continue
            centers.append({
                "id": post.pk,
                "uid": f"rental_user-{post.pk}",
                "type": "rental_user",
                "name": post.display_name,
                "lat": post.lat,
                "lng": post.lng,
                "phone": post.contact,
                "address": post.address,
                "center_type": "(개인) 임대",
                "center_type_key": "rental_user",
                "equipment_label": post.get_equipment_type_display(),
                "manufacturers": [],
                "ton_ranges": [],
                "repair_types": [],
                "operating_hours": "",
                "region": post.region,
                "rating": 0,
                "review_count": 0,
                "rental_price": post.rental_price or "",
                "rental_period": post.rental_period or "",
                "detail_url": f"/rental/{post.pk}/",
                "is_personal": True,
                "title": post.title,
            })

        for item in fetch_rental_companies(equipment_type=equipment_type, region=region_scope):
            row = _kakao_place_to_center(
                item,
                uid_prefix="rental_kakao",
                place_type="rental_kakao",
                center_type_label="임대(카카오)",
                equipment_label_by_key=equipment_label_by_key,
                equipment_type=equipment_type,
                region=region,
            )
            if row and row.get("lat") is not None and row.get("lng") is not None:
                centers.append(row)

        for item in fetch_regional_heavy_companies(equipment_type=equipment_type, region=region_scope):
            row = _kakao_place_to_center(
                item,
                uid_prefix="regional_heavy",
                place_type="regional_heavy",
                center_type_label="지역중기",
                equipment_label_by_key=equipment_label_by_key,
                equipment_type=equipment_type,
                region=region,
            )
            if row and row.get("lat") is not None and row.get("lng") is not None:
                if not row.get("operating_hours"):
                    row["operating_hours"] = "건설기계"
                centers.append(row)

    if type_filter in ("all", "call"):
        for item in fetch_call_companies(equipment_type=equipment_type, region=region_scope):
            row = _kakao_place_to_center(
                item,
                uid_prefix="call_kakao",
                place_type="call_kakao",
                center_type_label="중기호출",
                equipment_label_by_key=equipment_label_by_key,
                equipment_type=equipment_type,
                region=region,
            )
            if row and row.get("lat") is not None and row.get("lng") is not None:
                row["experience"] = ""
                row["day_rate"] = ""
                centers.append(row)

        driver_qs = DriverProfile.objects.filter(is_available=True)
        if region:
            driver_qs = driver_qs.filter(region__icontains=region)
        for driver in driver_qs:
            if not _match_equipment_type(equipment_type, [driver.equipment_type]):
                continue
            centers.append({
                "id": driver.pk,
                "uid": f"call_driver-{driver.pk}",
                "type": "call_driver",
                "name": driver.name,
                "lat": driver.latitude,
                "lng": driver.longitude,
                "phone": driver.contact,
                "address": driver.address,
                "center_type": "중기호출 기사",
                "center_type_key": "call_driver",
                "equipment_label": driver.get_equipment_type_display(),
                "manufacturers": [],
                "ton_ranges": [],
                "repair_types": [],
                "operating_hours": "",
                "region": driver.region,
                "rating": 0,
                "review_count": 0,
                "rental_price": f"{driver.day_rate:,}원" if driver.day_rate else "협의",
                "rental_period": "",
                "detail_url": reverse("driver_detail", kwargs={"pk": driver.pk}),
                "is_personal": True,
                "title": driver.name,
                "experience": driver.get_experience_display(),
                "day_rate": driver.day_rate or 0,
            })

    return JsonResponse({"centers": centers})


def _resolve_equipment_detail_back_url(request, equipment):
    """상세 화면에서 목록으로 돌아갈 URL (검색·필터·정렬 상태 유지)."""
    if (request.GET.get('from') or '').strip().lower() == 'mypage' and request.user.is_authenticated:
        return reverse('my_page'), '뒤로가기'

    allowed_hosts = {request.get_host()}
    next_url = (request.GET.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts):
        return next_url, '목록으로 가기'

    referer = (request.META.get('HTTP_REFERER') or '').strip()
    if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts=allowed_hosts):
        from urllib.parse import urlparse

        parsed = urlparse(referer)
        path = (parsed.path or '/').rstrip('/') or '/'
        index_path = reverse('index').rstrip('/') or '/'
        if path == index_path or path == '/' or path.startswith('/equipment/author/'):
            back = parsed.path or '/'
            if parsed.query:
                back += '?' + parsed.query
            return back, '목록으로 가기'

    detail_back_url = reverse('index')
    if equipment.equipment_type:
        detail_back_url += f'?category={equipment.equipment_type}'
    return detail_back_url, '목록으로 가기'


# [4] 매물 관련
def equipment_detail(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if equipment.author_id is None and not (
        request.user.is_authenticated and request.user.is_staff
    ):
        raise Http404()
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = EquipmentFavorite.objects.filter(user=request.user, equipment=equipment).exists()

    ct = ContentType.objects.get_for_model(Equipment)
    comments = Comment.objects.filter(content_type=ct, object_id=pk).order_by('created_at')

    if request.method == 'POST' and 'comment_content' in request.POST:
        content = (request.POST.get('comment_content') or '').strip()
        if content:
            Comment.objects.create(
                author=request.user if request.user.is_authenticated else None,
                author_name=(request.POST.get('comment_author_name') or '').strip() or '익명',
                content=content,
                content_type=ct,
                object_id=pk,
            )
        from urllib.parse import urlencode

        redir_params = {}
        if (request.GET.get('from') or '').strip().lower() == 'mypage':
            redir_params['from'] = 'mypage'
        next_after_comment = (request.GET.get('next') or '').strip()
        if next_after_comment and url_has_allowed_host_and_scheme(
            next_after_comment, allowed_hosts={request.get_host()}
        ):
            redir_params['next'] = next_after_comment
        redir = reverse('equipment_detail', kwargs={'pk': pk})
        if redir_params:
            redir += '?' + urlencode(redir_params)
        return redirect(redir)

    if request.method == 'GET':
        Equipment.objects.filter(pk=equipment.pk).update(view_count=F('view_count') + 1)
        equipment.refresh_from_db(fields=['view_count'])

    author_phone = None
    author_is_dealer = False
    author_is_premium = False
    author_display = None
    author_company = ""
    author_youtube = ""
    if equipment.author:
        try:
            profile = getattr(equipment.author, 'profile', None)
            if profile:
                author_phone = getattr(profile, 'phone', None)
                if author_phone is not None:
                    author_phone = str(author_phone).strip()
                    # 전화번호는 숫자가 있어야 유효 (예: legacy_XXXX 같은 값 방지)
                    if author_phone and not any(ch.isdigit() for ch in author_phone):
                        author_phone = None
                author_is_dealer = getattr(profile, 'user_type', None) == 'DEALER'
                author_is_premium = getattr(profile, 'is_premium_active', False) or (
                    equipment.author_id in set(get_premium_user_ids())
                )
                author_display = getattr(profile, 'company_name', None) or equipment.author.get_full_name() or equipment.author.username
                author_company = (getattr(profile, "company_name", None) or "").strip()
                author_youtube = (getattr(profile, "youtube_url", None) or "").strip()
            else:
                author_display = equipment.author.get_full_name() or equipment.author.username
                author_is_premium = equipment.author_id in set(get_premium_user_ids())
        except Exception:
            author_display = equipment.author.username if equipment.author else None

    # 작성자 연결이 없는 이관 매물 보정:
    # 같은 핵심 정보(모델/가격/위치/등록일)의 최근 매물에서 연락처를 fallback으로 사용
    if not author_phone:
        sibling_qs = (
            Equipment.objects.select_related('author__profile')
            .exclude(pk=equipment.pk)
            .exclude(author__isnull=True)
            .filter(
                model_name=equipment.model_name,
                listing_price=equipment.listing_price,
                current_location=equipment.current_location,
                created_at__date=equipment.created_at.date(),
            )
            .order_by('-created_at')
        )
        for sibling in sibling_qs[:10]:
            sibling_profile = getattr(getattr(sibling, 'author', None), 'profile', None)
            sibling_phone = getattr(sibling_profile, 'phone', None) if sibling_profile else None
            if sibling_phone:
                author_phone = str(sibling_phone).strip()
                if author_phone and not any(ch.isdigit() for ch in author_phone):
                    author_phone = None
                if not author_phone:
                    continue
                if not author_display:
                    author_display = (
                        getattr(sibling_profile, 'company_name', None)
                        or sibling.author.get_full_name()
                        or sibling.author.username
                    )
                if not author_is_dealer:
                    author_is_dealer = getattr(sibling_profile, 'user_type', None) == 'DEALER'
                if not author_is_premium:
                    author_is_premium = (
                        getattr(sibling_profile, 'is_premium_active', False)
                        or sibling.author_id in set(get_premium_user_ids())
                    )
                break

    # 실제 파일이 존재하는 사진만 상세 화면에 노출 (깨진 이미지 방지)
    detail_images = []
    for image in equipment.images.all():
        try:
            image_name = getattr(image.image, 'name', '') or ''
            if image_name and image.image.storage.exists(image_name):
                detail_images.append(image)
        except Exception:
            continue

    # 금융 예상 한도 / 월 납입액(60개월, 연 7% 가정)
    finance_limit = None
    finance_monthly_60 = None
    try:
        if equipment.listing_price and equipment.listing_price > 0:
            price = Decimal(equipment.listing_price)
            principal = (price * Decimal('0.8')).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)  # 매물가의 80% (만원 단위)
            r = Decimal('0.07') / Decimal('12')  # 연 7% 가정
            n = Decimal('60')
            if r > 0:
                factor = (r * (1 + r) ** n) / ((1 + r) ** n - 1)
                monthly = (principal * factor).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
            else:
                monthly = (principal / n).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
            finance_limit = principal
            finance_monthly_60 = monthly
    except Exception:
        finance_limit = None
        finance_monthly_60 = None

    # 비슷한 기종·년식(±2년) 시세 통계 및 비슷한 매물 목록 (노출 중인 것만)
    similar_qs = Equipment.objects.visible().exclude(pk=equipment.pk).filter(is_sold=False)
    year_val = equipment.year_manufactured or 0
    if equipment.manufacturer:
        similar_qs = similar_qs.filter(manufacturer=equipment.manufacturer)
    if year_val and 1980 <= year_val <= 2030:
        similar_qs = similar_qs.filter(
            year_manufactured__gte=year_val - 2,
            year_manufactured__lte=year_val + 2,
        )
    similar_stats = similar_qs.aggregate(
        cnt=Count('id'),
        price_min=Min('listing_price'),
        price_max=Max('listing_price'),
        price_avg=Avg('listing_price'),
    )
    similar_list = list(similar_qs.order_by('-created_at')[:6])

    # 상세 좌측 레일(굴삭기 전용): 어태치먼트/타이어 전문가 카드
    left_specialist_cards = []
    if (equipment.equipment_type or "") == "excavator":
        left_specialist_cards = list(
            Equipment.objects.visible()
            .filter(is_sold=False)
            .filter(
                Q(equipment_type="excavator", sub_type="EXC_ATTACHMENT")
                | Q(equipment_type="excavator", sub_type="EXC_TIRE")
            )
            .exclude(pk=equipment.pk)
            .select_related("author__profile")
            .order_by("-created_at")[:5]
        )

    # 상세 레일: 같은 기종 유료 전문가 명함 (사진·소개·전화)
    _ptype = equipment.equipment_type or None
    premium_sidebar_expert_title = PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY.get(_ptype or "", "")
    if not premium_sidebar_expert_title and _ptype:
        premium_sidebar_expert_title = (
            f"{equipment.get_equipment_type_display()} 전문가들"
        )
    _expert_cards = []
    if _ptype and premium_sidebar_expert_title:
        _expert_cards = get_premium_expert_cards(
            limit=PREMIUM_SIDEBAR_INDEX_PER_SIDE,
            equipment_type=_ptype,
        )
    right_premium_expert_cards = pad_premium_expert_cards(_expert_cards, PREMIUM_SIDEBAR_INDEX_PER_SIDE)
    if equipment.author_id:
        for card in right_premium_expert_cards:
            if card and card.get('user_id') == equipment.author_id:
                url = card.get('detail_url') or ''
                sep = '&' if '?' in url else '?'
                card['detail_url'] = f'{url}{sep}equipment={equipment.pk}'
    premium_sidebar_list = []
    premium_sidebar_slots = []

    # 이 판매자의 다른 매물 2개 미리보기 (유료회원·본문 제외)
    author_other_listings = []
    if equipment.author_id:
        author_other_listings = list(
            Equipment.objects.visible()
            .filter(author_id=equipment.author_id, is_sold=False)
            .exclude(pk=equipment.pk)
            .order_by('-created_at')[:2]
        )

    # 우측 레일: 전국 부품점 A/S 센터(지도 이동 링크용)
    shops_qs = PartsShop.objects.all().order_by('region', 'name')
    nearby_parts_shops = []
    if equipment.region_sido:
        nearby_parts_shops = list(shops_qs.filter(region__icontains=equipment.region_sido)[:6])
    if not nearby_parts_shops:
        nearby_parts_shops = list(shops_qs[:6])

    right_premium_slots = []
    has_right_ads = bool(
        any(right_premium_expert_cards)
        or left_specialist_cards
        or nearby_parts_shops
    )

    detail_back_url, detail_back_label = _resolve_equipment_detail_back_url(request, equipment)

    return render(request, 'equipment/equipment_detail.html', {
        'equipment': equipment,
        'detail_back_url': detail_back_url,
        'detail_back_label': detail_back_label,
        'detail_images': detail_images,
        'is_favorited': is_favorited,
        'comments': comments,
        'author_phone': author_phone,
        'author_is_dealer': author_is_dealer,
        'author_is_premium': author_is_premium,
        'author_display': author_display,
        'author_company': author_company,
        'author_youtube': author_youtube,
        'similar_stats': similar_stats,
        'similar_list': similar_list,
        'finance_limit': finance_limit,
        'finance_monthly_60': finance_monthly_60,
        'left_specialist_cards': left_specialist_cards,
        'premium_sidebar_list': premium_sidebar_list,
        'premium_sidebar_slots': premium_sidebar_slots,
        'right_premium_slots': right_premium_slots,
        'right_premium_expert_cards': right_premium_expert_cards,
        'has_right_ads': has_right_ads,
        'premium_sidebar_expert_title': premium_sidebar_expert_title,
        'author_other_listings': author_other_listings,
        'nearby_parts_shops': nearby_parts_shops,
        'kakao_map_js_key': _get_kakao_map_js_key(),
    })


def equipment_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    if not request.user.is_authenticated:
        return redirect('login')
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '매물 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp

    from trust.services import SellerListingBlocked, is_seller_blocked

    if is_seller_blocked(request.user):
        messages.error(
            request,
            '매너점수 이용 제한으로 매물을 등록할 수 없습니다. 고객센터에 문의해 주세요.',
        )
        return redirect('my_page')

    if request.method == 'POST':
        form = EquipmentForm(_post_with_coalesced_weight_class(request.POST))
        if form.is_valid():
            # 회원 등급별 월 등록 제한
            current_count = get_monthly_listing_count(request.user)
            monthly_limit = get_listing_monthly_limit(request.user)
            if current_count >= monthly_limit:
                if is_user_premium(request.user):
                    limit_msg = f'유료 회원은 한 달에 매물을 {PREMIUM_LISTING_LIMIT}건까지만 등록할 수 있습니다.'
                else:
                    limit_msg = f'무료 회원은 한 달에 매물을 {FREE_LISTING_LIMIT}건까지만 등록할 수 있습니다.'
                messages.error(
                    request,
                    limit_msg + ' 이번 달 한도를 모두 사용했습니다. 삭제 후 다시 올려도 당월 건수에 포함되며, 다음 달부터 새로 등록할 수 있습니다.'
                )
                return render(request, 'equipment/equipment_form.html', {
                    'form': form,
                    'mode': 'create',
                    'sido_choices': SIDO_CHOICES,
                    'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                    'free_listing_count': current_count,
                    'free_listing_limit': FREE_LISTING_LIMIT,
                    'premium_listing_limit': PREMIUM_LISTING_LIMIT,
                    'monthly_listing_count': current_count,
                    'monthly_listing_limit': monthly_limit,
                    'is_premium': is_user_premium(request.user),
                })
            # 허위 매물 방지: 사진 최소 1장 필수
            image_files = request.FILES.getlist('images')
            if not image_files or len(image_files) < 1:
                form.add_error(None, ValidationError('허위 매물 방지를 위해 사진을 최소 1장 이상 등록해주세요.'))
            else:
                # 도배 방지: 삭제 후 7일 이내 동일 매물(기종+연식+가격) 재등록 차단
                from datetime import timedelta
                since = timezone.now() - timedelta(days=7)
                equipment_type = (form.cleaned_data.get('equipment_type') or '').strip()
                year_manufactured = form.cleaned_data.get('year_manufactured')
                listing_price = form.cleaned_data.get('listing_price')
                if DeletedListingLog.objects.filter(
                    user=request.user,
                    deleted_at__gte=since,
                    equipment_type=equipment_type,
                    year_manufactured=year_manufactured,
                    listing_price=listing_price,
                ).exists():
                    messages.error(
                        request,
                        '도배 방지를 위해 삭제 후 7일 이내에는 동일 매물(같은 기종·연식·가격)을 다시 등록할 수 없습니다.'
                    )
                    return render(request, 'equipment/equipment_form.html', {
                        'form': form,
                        'mode': 'create',
                        'sido_choices': SIDO_CHOICES,
                        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                        'free_listing_count': get_monthly_listing_count(request.user),
                        'free_listing_limit': FREE_LISTING_LIMIT,
                        'premium_listing_limit': PREMIUM_LISTING_LIMIT,
                        'monthly_listing_count': get_monthly_listing_count(request.user),
                        'monthly_listing_limit': get_listing_monthly_limit(request.user),
                        'is_premium': is_user_premium(request.user),
                    })
                # 해시 계산으로 읽은 첫 이미지 포인터 초기화 (저장 시 사용)
                image_files[0].seek(0)
                try:
                    obj = form.save(commit=False)
                    obj.author = request.user
                    if obj.operating_hours is None:
                        obj.operating_hours = 0
                    obj.current_location = _build_location_text(obj.region_sido, obj.region_sigungu)
                    obj.save()
                    for f in image_files:
                        EquipmentImage.objects.create(equipment=obj, image=f)
                    return redirect('equipment_detail', obj.pk)
                except SellerListingBlocked as exc:
                    messages.error(request, str(exc.message) if hasattr(exc, 'message') else str(exc))
                    return render(request, 'equipment/equipment_form.html', {
                        'form': form,
                        'mode': 'create',
                        'sido_choices': SIDO_CHOICES,
                        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
                        'free_listing_count': current_count,
                        'free_listing_limit': FREE_LISTING_LIMIT,
                        'premium_listing_limit': PREMIUM_LISTING_LIMIT,
                        'monthly_listing_count': current_count,
                        'monthly_listing_limit': monthly_limit,
                        'is_premium': is_user_premium(request.user),
                    })
                except Exception:
                    import traceback
                    traceback.print_exc()
                    form.add_error(None, ValidationError('등록 처리 중 오류가 발생했습니다. 사진 용량/형식을 확인한 뒤 다시 시도해 주세요.'))
    else:
        form = EquipmentForm(initial={'equipment_type': 'excavator'})

    free_count = get_free_listing_count(request.user) if request.user.is_authenticated else 0
    monthly_count = get_monthly_listing_count(request.user) if request.user.is_authenticated else 0
    monthly_limit = get_listing_monthly_limit(request.user) if request.user.is_authenticated else FREE_LISTING_LIMIT
    return render(request, 'equipment/equipment_form.html', {
        'form': form,
        'mode': 'create',
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
        'free_listing_count': free_count,
        'free_listing_limit': FREE_LISTING_LIMIT,
        'premium_listing_limit': PREMIUM_LISTING_LIMIT,
        'monthly_listing_count': monthly_count,
        'monthly_listing_limit': monthly_limit,
        'is_premium': is_user_premium(request.user),
    })


def equipment_edit(request, pk):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    obj = get_object_or_404(Equipment.objects.prefetch_related('images'), pk=pk)

    if not request.user.is_authenticated:
        return redirect('login')

    # 내 글만 수정 가능 (author가 None이면 일단 막음)
    if obj.author_id != request.user.id:
        return redirect('equipment_detail', obj.pk)

    if request.method == 'POST':
        form = EquipmentEditForm(_post_with_coalesced_weight_class(request.POST), instance=obj)
        if form.is_valid():
            image_files = request.FILES.getlist('images')
            delete_ids = []
            for x in request.POST.getlist('delete_image_ids'):
                try:
                    delete_ids.append(int(x))
                except (TypeError, ValueError):
                    continue
            delete_ids = list(dict.fromkeys(delete_ids))
            n_delete = (
                EquipmentImage.objects.filter(equipment_id=obj.pk, pk__in=delete_ids).count()
                if delete_ids
                else 0
            )
            n_remain_after = obj.images.count() - n_delete
            if n_remain_after + len(image_files) < 1:
                form.add_error(
                    None,
                    ValidationError(
                        '허위 매물 방지를 위해 사진을 최소 1장 이상 남기거나, 삭제한 만큼 새 사진을 추가해 주세요.'
                    ),
                )
            else:
                try:
                    from django.db import transaction

                    with transaction.atomic():
                        obj = form.save(commit=False)
                        if obj.operating_hours is None:
                            obj.operating_hours = 0
                        obj.current_location = _build_location_text(obj.region_sido, obj.region_sigungu)
                        obj.save()
                        if delete_ids:
                            EquipmentImage.objects.filter(equipment_id=obj.pk, pk__in=delete_ids).delete()
                        for f in image_files:
                            EquipmentImage.objects.create(equipment=obj, image=f)
                    return redirect('equipment_detail', obj.pk)
                except Exception:
                    import traceback
                    traceback.print_exc()
                    form.add_error(None, ValidationError('수정 저장 중 오류가 발생했습니다. 사진 용량/형식을 확인한 뒤 다시 시도해 주세요.'))
    else:
        form = EquipmentEditForm(instance=obj)

    return render(request, 'equipment/equipment_form.html', {
        'form': form,
        'mode': 'edit',
        'equipment': obj,
        'sido_choices': SIDO_CHOICES,
        'sigungu_map_json': json.dumps(SIGUNGU_MAP, ensure_ascii=False),
    })


def equipment_delete(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if not request.user.is_authenticated:
        return redirect('login')
    if equipment.author_id != request.user.id:
        messages.error(request, '본인만 삭제할 수 있습니다.')
        return redirect('equipment_detail', pk=pk)
    if request.method != 'POST':
        next_url = request.GET.get('next', '')
        return render(request, 'equipment/equipment_delete_confirm.html', {'equipment': equipment, 'next_url': next_url})
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
    ):
        redirect_to = next_url
    else:
        redirect_to = reverse('my_page')
    # 삭제 로그 기록(도배 방지: 7일 이내 동일 기종+연식+가격 재등록 제한)
    try:
        img_hash = _image_hash_from_equipment(equipment)
        DeletedListingLog.objects.create(
            user=request.user,
            model_name=(equipment.model_name or '').strip(),
            image_hash=img_hash or '',
            equipment_type=(equipment.equipment_type or '').strip(),
            year_manufactured=equipment.year_manufactured,
            listing_price=equipment.listing_price,
        )
    except Exception:
        pass
    equipment.delete()
    messages.success(request, '매물이 삭제되었습니다.')
    return redirect(redirect_to)


def equipment_bump(request, pk):
    """끌어올리기 — 유료회원만, 최근 7일 기준 최대 3회. 마이페이지에서 이용."""
    equipment = get_object_or_404(Equipment, pk=pk)
    bump_back = reverse('my_page')

    if not request.user.is_authenticated:
        messages.info(request, '로그인 후 이용해 주세요.')
        return redirect('login')
    if equipment.author_id != request.user.id:
        messages.error(request, '본인 매물만 끌어올릴 수 있습니다.')
        return redirect(bump_back)
    if not is_user_premium(request.user):
        messages.error(request, '끌어올리기는 유료 회원만 이용할 수 있습니다.')
        return redirect(bump_back)

    status = get_user_bump_status(request.user)
    if not status['can_bump']:
        next_at = status.get('next_bump_at')
        if next_at:
            messages.warning(
                request,
                f'끌어올리기는 최근 7일 기준 최대 {BUMP_WEEKLY_LIMIT}회만 가능합니다. '
                f'다음 이용 가능: {next_at.strftime("%Y-%m-%d %H:%M")}',
            )
        else:
            messages.warning(
                request,
                f'끌어올리기는 최근 7일 기준 최대 {BUMP_WEEKLY_LIMIT}회만 가능합니다.',
            )
        return redirect(bump_back)

    now = timezone.now()
    from .models import EquipmentBumpLog

    equipment.last_bumped_at = now
    equipment.save(update_fields=['last_bumped_at'])
    EquipmentBumpLog.objects.create(user=request.user, equipment=equipment)
    messages.success(request, '끌어올리기가 완료되었습니다. 최신순 목록 상단에 노출됩니다.')
    return redirect(bump_back)


def toggle_equipment_favorite(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    equipment = get_object_or_404(Equipment, pk=pk)
    fav, created = EquipmentFavorite.objects.get_or_create(user=request.user, equipment=equipment)
    if not created:
        fav.delete()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'index'
    return redirect(next_url)


def author_listings(request, user_id):
    """이 회원이 올린 모든 매물 보기."""
    author_user = get_object_or_404(User, pk=user_id)
    author_profile = getattr(author_user, 'profile', None)
    author_showcase_public = bool(
        author_profile and getattr(author_profile, 'is_premium_active', False)
    )
    # "이 회원 매물 전체 보기"는 유료 회원만 공개
    if not author_showcase_public:
        raise Http404()

    base_qs = (
        Equipment.objects.visible()
        .filter(author_id=user_id)
        .select_related('author')
        .prefetch_related('images')
    )
    cat = (request.GET.get('category') or '').strip().lower()
    valid_cats = {c[0] for c in Equipment._meta.get_field('equipment_type').choices}
    if cat in valid_cats:
        base_qs = base_qs.filter(equipment_type=cat)

    sort = (request.GET.get('sort') or 'latest').strip().lower()
    if sort == 'price_low':
        qs = base_qs.order_by('listing_price', '-created_at')
    elif sort == 'price_high':
        qs = base_qs.order_by('-listing_price', '-created_at')
    else:
        sort = 'latest'
        qs = base_qs.order_by('-created_at')

    listings = list(qs)
    total_count = len(listings)
    sold_count = sum(1 for item in listings if item.is_sold)
    avg_response_text = "빠름"

    from trust.services import build_seller_trust_template_context

    trust_review_equipment = None
    eq_param = (request.GET.get('equipment') or '').strip()
    if eq_param.isdigit():
        trust_review_equipment = base_qs.filter(pk=int(eq_param)).first()
    trust_ctx = build_seller_trust_template_context(
        request, author_user, equipment=trust_review_equipment
    )
    favorited_ids = set()
    if request.user.is_authenticated:
        favorited_ids = set(
            EquipmentFavorite.objects.filter(user=request.user).values_list(
                'equipment_id', flat=True
            )
        )
    premium_author_ids = set(get_premium_user_ids())

    return render(request, 'equipment/author_listings.html', {
        'author_user': author_user,
        'author_profile': author_profile,
        'author_showcase_public': author_showcase_public,
        'listings': listings,
        'favorited_equipment_ids': favorited_ids,
        'premium_author_ids': premium_author_ids,
        'filter_category_param': cat if cat in valid_cats else '',
        'sort_param': sort,
        'total_count': total_count,
        'sold_count': sold_count,
        'avg_response_text': avg_response_text,
        'list_back_url': request.get_full_path,
        'equipment_detail_next': quote(request.get_full_path(), safe=''),
        **trust_ctx,
    })


# [5] 부품 관련
def part_list(request):
    part_list_qs = Part.objects.all()
    category = (request.GET.get('category') or '').strip().upper()
    if category and category in dict(Part.CATEGORY_CHOICES):
        part_list_qs = part_list_qs.filter(category=category)
    favorited_part_ids = set()
    if request.user.is_authenticated:
        favorited_part_ids = set(PartFavorite.objects.filter(user=request.user).values_list('part_id', flat=True))
    return render(request, 'equipment/part_list.html', {
        'part_list': part_list_qs,
        'favorited_part_ids': favorited_part_ids,
        'filter_category': category,
    })


def part_detail(request, pk):
    part = get_object_or_404(Part, pk=pk)
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = PartFavorite.objects.filter(user=request.user, part=part).exists()

    ct = ContentType.objects.get_for_model(Part)
    comments = Comment.objects.filter(content_type=ct, object_id=pk).order_by('created_at')

    if request.method == 'POST' and 'comment_content' in request.POST:
        content = (request.POST.get('comment_content') or '').strip()
        if content:
            Comment.objects.create(
                author=request.user if request.user.is_authenticated else None,
                author_name=(request.POST.get('comment_author_name') or '').strip() or '익명',
                content=content,
                content_type=ct,
                object_id=pk,
            )
        return redirect('part_detail', pk=pk)

    return render(request, 'equipment/part_detail.html', {
        'part': part,
        'is_favorited': is_favorited,
        'comments': comments,
    })


def toggle_part_favorite(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')
    part = get_object_or_404(Part, pk=pk)
    fav, created = PartFavorite.objects.get_or_create(user=request.user, part=part)
    if not created:
        fav.delete()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'part_list'
    return redirect(next_url)


@login_required(login_url='/login/')
def part_create(request):
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '부품 매물 등록을 위해 휴대폰 본인인증이 필요합니다.')
        return redirect_resp

    form = PartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        part = form.save(commit=False)
        part.author = request.user
        part.save()

        for f in request.FILES.getlist("images"):
            PartImage.objects.create(part=part, image=f)

        return redirect("part_detail", part.pk)

    return render(request, "equipment/part_create.html", {"mode": "create", "form": form})


def part_edit(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    part = get_object_or_404(Part, pk=pk)

    # 내 글만 수정 가능
    if part.author_id != request.user.id:
        return redirect("part_detail", part.pk)

    form = PartForm(request.POST or None, instance=part)
    if request.method == "POST" and form.is_valid():
        part = form.save(commit=False)
        part.save()

        for f in request.FILES.getlist("images"):
            PartImage.objects.create(part=part, image=f)

        return redirect("part_detail", part.pk)

    return render(request, "equipment/part_create.html", {"mode": "edit", "part": part, "form": form})


def part_delete(request, pk):
    if not request.user.is_authenticated:
        return redirect('login')

    part = get_object_or_404(Part, pk=pk)
    if part.author_id != request.user.id:
        return redirect("part_detail", part.pk)

    part.delete()
    return redirect("part_list")
