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
from django.core.cache import cache
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
    attach_equipment_bump_ui_state,
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
    INDEX_FILTER_MAX,
    VALID_CATEGORIES,
)


def _image_hash_from_upload(uploaded_file):
    """?낅줈???뚯씪 ?댁슜?쇰줈 MD5 ?댁떆 (?숈씪 ?ъ쭊 ?ъ뾽濡쒕뱶 媛먯?)."""
    import hashlib
    try:
        uploaded_file.seek(0)
        return hashlib.md5(uploaded_file.read()).hexdigest()
    except Exception:
        return ""


def _image_hash_from_equipment(equipment):
    """留ㅻЪ ????ъ쭊(泥?踰덉㎏) ?댁떆 (??젣 ??濡쒓렇??."""
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
    """?대???蹂몄씤?몄쬆 ?щ?. Profile ?놁쑝硫??앹꽦 ??False."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = Profile.objects.get(user=user)
    except Profile.DoesNotExist:
        profile = Profile.objects.create(user=user)
    return getattr(profile, 'phone_verified', False)


def _social_auth_login_url(provider, next_url=''):
    """?뚯뀥 濡쒓렇??URL. process=login 諛?濡쒓렇????蹂듦? 寃쎈줈(next) ?좎?."""
    params = {'process': 'login'}
    if next_url:
        params['next'] = next_url
    return f'/accounts/{provider}/login/?' + urlencode(params)


def _login_next_url(request, explicit_next=''):
    """濡쒓렇????蹂듦? 寃쎈줈 ??next ?뚮씪誘명꽣 ?곗꽑, ?놁쑝硫?濡쒓렇??吏곸쟾 ?섏씠吏(留ㅻЪ蹂닿린 媛뺤젣 ?대룞 諛⑹?)."""
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
    """濡쒓렇??+ ?대???蹂몄씤?몄쬆 ?꾩닔(?ㅽ깭???쒖쇅). ?낆껜 ?먯쭊?깅줉쨌?꾩옣 ?먯옱 ??怨듦컻 ?깅줉??"""
    if not request.user.is_authenticated:
        return redirect(reverse('login') + '?next=' + quote(request.get_full_path(), safe=''))
    if request.user.is_staff or request.user.is_superuser:
        return None
    if not _get_profile_phone_verified(request.user):
        return redirect(reverse('phone_verify') + '?next=' + quote(request.get_full_path(), safe=''))
    return None


def _user_has_social_account(user):
    """?뚯뀥(移댁뭅???ㅼ씠踰??? 濡쒓렇?몄쑝濡?媛?끒룹뿰?숇맂 怨꾩젙?몄? ?щ?. ?꾩씠??鍮꾨?踰덊샇留??곕뒗 ?뚯썝? False."""
    if not user or not user.is_authenticated:
        return False
    try:
        from allauth.socialaccount.models import SocialAccount
        return SocialAccount.objects.filter(user=user).exists()
    except Exception:
        return False


def _require_phone_verified(request, next_url=None):
    """
    留ㅻЪ ?깅줉쨌?좊즺 寃곗젣 ?????대????몄쬆 ?꾩닔.
    ?? ?꾩씠??鍮꾨?踰덊샇濡?媛?낇븳 ?뚯썝(?뚯뀥 ?곕룞 ?놁쓬)? 蹂몄씤?몄쬆 ?앸왂.
    ?몄쬆 ?꾩슂?섍퀬 ???먯쑝硫?redirect ?묐떟 諛섑솚, ?듦낵 ??None.
    """
    if not request.user.is_authenticated:
        return redirect('login')
    # ?꾩씠?붋룸퉬諛踰덊샇濡쒕쭔 媛?낇븳 ?뚯썝? 蹂몄씤?몄쬆 遺덊븘??    if not _user_has_social_account(request.user):
        return None
    if _get_profile_phone_verified(request.user):
        return None
    from urllib.parse import quote
    from django.urls import reverse
    next_path = next_url or request.get_full_path()
    return redirect(reverse('phone_verify') + '?next=' + quote(next_path, safe=''))


def _build_location_text(region_sido: str, region_sigungu: str) -> str:
    """留ㅻЪ ?꾩튂 臾몄옄?? ???꽷룹떆/援?援щ쭔 ?ъ슜 (?곸꽭 二쇱냼 ?낅젰 ?놁쓬)."""
    sido = (region_sido or '').strip()
    sigungu = (region_sigungu or '').strip()
    if sido and sigungu:
        return f"{sido} {sigungu}"
    return sido or ''


def _post_with_coalesced_weight_class(post):
    """
    equipment_form.html ??name=weight_class 媛 以묐났(?⑥? ?꾨뱶 + simple/dump)????    QueryDict.get 媛 留덉?留?媛믩쭔 ?곕㈃ 鍮?臾몄옄?댁씠 ?욎そ 肄붾뱶瑜???뼱?대떎.
    援댁궘湲걔룹?寃뚯감: EXC_/FORK_/DUMP_ 肄붾뱶媛 ?덉쑝硫?洹멸쾬???⑥씪 weight_class 濡??대떎.
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
    """援댁궘湲??곸꽭寃?됱뿉??'??댁뼱??5~6 ton' ?좏깮 ?щ?."""
    return sub_type == 'EXC_TIRE' and weight_class == 'EXC_TIRE_LE_6'


def _legacy_excavator_tire_5_6_q() -> Q:
    """
    ?덇굅???곗씠???명솚:
    - ?덉쟾 ?닿? ?곗씠?곕뒗 sub_type/weight_class 肄붾뱶媛 鍮꾩뼱?덇굅???섎せ??寃쎌슦媛 ?덉뼱
      紐⑤뜽紐??⑦꽩(EW60/HW60/DX55W/06W ?????④퍡 寃?됲븳??
    """
    return Q(
        model_name__iregex=(
            r"(EW\s*60|EW\s*55|HW\s*60|DX\s*55\s*W|R\s*555\s*W|"
            r"\b55\s*W(?:I)?\b|\b0?6\s*W\b)"
        )
    )


def _exclude_mislabeled_mini_crawler_in_tire_heavy_search(sub_type: str, weight_class: str):
    """
    ??댁뼱??06W/08W 寃?됱씤??DB??泥댁씤 誘몃땲(DX55 ??媛 ??댁뼱+??ㅼ닔濡??ㅽ몴湲곕맂 留ㅻЪ???욎씠??寃쎌슦 ?쒖쇅.
    紐⑤뜽紐낆뿉 W(????댁뼱 蹂??媛 ?덉쑝硫??쒖쇅?섏? ?딅뒗??
    ?대떦 議곌굔???꾨땲硫?None.
    """
    if sub_type != "EXC_TIRE" or weight_class not in ("EXC_TIRE_LE_17", "EXC_TIRE_LE_21"):
        return None
    # DX50~DX59, EC55, HX55 ???뚰삎 泥댁씤 紐낆묶 ??紐⑤뜽??W媛 ?ㅼ뼱媛硫??? DX55W) ??댁뼱 蹂?뺤쑝濡?蹂몃떎.
    return (
        Q(model_name__iregex=r"(?i)\bDX\s*5[0-9]\b(?!.*W)")
        | Q(model_name__iregex=r"(?i)\bEC\s*55\b(?!.*W)")
        | Q(model_name__iregex=r"(?i)\bHX\s*55\b(?!.*W)")
    )


def legacy_redirect_equipment_uid(request, uid):
    """
    援ы삎 留ㅻЪ URL ??/equipment/<pk>/ (301).
    /viewsale/援댁궘湲?uid}, /attachment/{uid} ?? uid???닿? ??legacy_listing_id ?곗꽑, ?놁쑝硫?pk濡?議고쉶.
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
    """援ы삎 /job/{uid}/ ??/jobs/<pk>/ (301). uid??legacy_guin_uid ?곗꽑, ?놁쑝硫?pk."""
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
    """援ы삎 /community/{uid}/ ??/board/{uid}/ (301)."""
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        raise Http404()
    return redirect("board_detail", pk=uid_int, permanent=True)


def board_post_detail(request, pk):
    """
    ?좉퇋 而ㅻ??덊떚 ?곸꽭 URL (/board/<pk>/).
    寃뚯떆??紐⑤뜽 ?곕룞 ?꾧퉴吏??404 (援?URL 301 ??곷쭔 ?좏슚).
    """
    raise Http404()


def _redirect_repaired_index_query(request):
    """
    ?섎せ??GET name=/?category=... (pathname+search媛 name 媛믪쑝濡??ㅼ뼱??寃쎌슦)瑜?    ?댁옣 荑쇰━?ㅽ듃留곸쓣 ????뺤긽 紐⑸줉 URL濡?302 由щ떎?대젆?명븳??
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
    """紐⑸줉 移대뱶 partial ?뚮뜑??怨듯넻 而⑦뀓?ㅽ듃."""
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
        total_count_label = "?좊즺?뚯썝"
    elif query or has_detail_filters:
        total_count_label = "寃?됯껐怨?
    elif filter_category in VALID_CATEGORIES:
        category_label_map = {
            "excavator": "援댁궘湲?,
            "forklift": "吏寃뚯감",
            "dump": "?ㅽ봽?몃윮",
            "loader": "?ㅽ궎濡쒕뜑/濡쒕뜑",
            "crane": "?щ젅??,
            "attachment": "?댄깭移섎㉫??,
            "other": "湲고? 以묒옣鍮?,
        }
        total_count_label = category_label_map.get(filter_category, "?꾩껜")
    else:
        total_count_label = "?꾩껜"
    return {
        'equipment_list': equipment_chunk,
        'premium_author_ids': premium_author_ids,
        'favorited_equipment_ids': favorited_ids,
        'equipment_detail_next_q': quote(request.get_full_path(), safe=''),
        'total_count_label': total_count_label,
    }


def index_load_more(request):
    """?붾낫湲? offset遺??per_page媛?移대뱶 HTML(JSON) 諛섑솚."""
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


# [1] 硫붿씤 ?섏씠吏 (?ㅼ썙??+ ?뺣젹留?
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
        equipment_list = list(qs[:INDEX_FILTER_MAX])
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
    """TEST 踰꾪듉 ?꾩슜: ?섑뵆 30媛??ъ쭊 ?ы븿) 誘몃━蹂닿린 ?붾㈃."""
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
                'title': f"[TEST {i + 1:02d}] {base.model_name or '援댁궘湲??섑뵆 留ㅻЪ'}",
                'manufacturer': base.manufacturer or '?뚯뒪?몄젣議곗궗',
                'year': base.year_manufactured or '-',
                'location': base.current_location or base.region_sido or '?뚯뒪?몄???,
                'price': base.listing_price,
                'image_url': first_image.image.url if first_image else '',
                'detail_url': reverse('equipment_detail', args=[base.pk]),
            })
    else:
        for i in range(30):
            sample_items.append({
                'id': i + 1,
                'title': f"[TEST {i + 1:02d}] 援댁궘湲??섑뵆 留ㅻЪ",
                'manufacturer': '?뚯뒪?몄젣議곗궗',
                'year': '-',
                'location': '?뚯뒪?몄???,
                'price': None,
                'image_url': '',
                'detail_url': reverse('index'),
            })

    return render(request, 'equipment/premium_experts_test.html', {
        'sample_items': sample_items,
    })


# [2] 濡쒓렇??愿??def user_login(request):
    if request.user.is_authenticated:
        return _redirect_after_login(request, request.GET.get('next', ''))
    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        if not username or not password:
            messages.error(request, '?꾩씠?붿? 鍮꾨?踰덊샇瑜??낅젰?섏꽭??')
            next_url = request.POST.get('next') or request.GET.get('next', '')
            return render(request, 'registration/login.html', {
                'next_url': next_url,
                'kakao_login_url': _social_auth_login_url('kakao', next_url),
                'naver_login_url': _social_auth_login_url('naver', next_url),
            })
        user = authenticate(request, username=username, password=password)
        # 蹂댁셿 濡쒓렇?몄? ?쒖꽦 怨꾩젙?먮쭔 ?쒗븳?쒕떎.
        # (?덊눜 怨꾩젙? ?먮룞 蹂듦뎄?섏? ?딄퀬 ?좉퇋媛???먮쫫?쇰줈 ?좊룄)
        if user is None:
            # ?쇰? ?섍꼍?먯꽌 authenticate ?ㅽ뙣媛 ?섎뒗 寃쎌슦瑜?蹂댁셿?섎릺,
            # is_active=True ?ъ슜?먮쭔 ?덉슜?쒕떎.
            candidate = User.objects.filter(username=username, is_active=True).first()
            if candidate and candidate.check_password(password):
                candidate.backend = 'django.contrib.auth.backends.ModelBackend'
                user = candidate
        if user is not None:
            # ?댁쁺 ?뺤콉: ?대뱶誘?怨꾩젙? ?쇰컲 ?쒕퉬??濡쒓렇?몄뿉???ъ슜?섏? ?딆쓬
            # (愿由ъ옄 怨꾩젙? /admin/ ?먯꽌留?濡쒓렇??
            if user.is_staff or user.is_superuser:
                messages.error(request, '愿由ъ옄 怨꾩젙? 愿由ъ옄 ?섏씠吏?먯꽌留?濡쒓렇?명븷 ???덉뒿?덈떎.')
                return redirect('/admin/login/')
            login(request, user)
            next_url = request.POST.get('next') or request.GET.get('next', '')
            return _redirect_after_login(request, next_url)
        messages.error(request, '?꾩씠???먮뒗 鍮꾨?踰덊샇媛 ?щ컮瑜댁? ?딆뒿?덈떎.')
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
    # ?몄뀡???⑥? ?뚮옒???뚯뀥 濡쒓렇???깃났 ??瑜?鍮꾩슦吏 ?딆쑝硫?/login/ ?깆뿉???ㅻ뒭寃?蹂댁씪 ???덉쓬
    list(messages.get_messages(request))
    logout(request)
    return redirect('index')


def _signup_open_required(request):
    """?좉퇋 媛??鍮꾪솢?????덈궡 ?섏씠吏."""
    from django.conf import settings
    if getattr(settings, 'SIGNUP_ENABLED', True):
        return None
    return render(request, 'registration/signup_soon.html')


def signup_soon(request):
    """?좉퇋 ?뚯썝媛??以鍮?以??덈궡 (SIGNUP_ENABLED=False)."""
    if request.user.is_authenticated:
        return redirect('my_page')
    return render(request, 'registration/signup_soon.html')


def join_choice(request):
    """?뚯썝媛??吏꾩엯: ?대????낅젰 ??湲곗〈 ?뚯썝?몄? ?뺤씤 ??湲곗〈 ?꾪솚 ?먮뒗 ?좉퇋 媛???덈궡."""
    if request.user.is_authenticated:
        return redirect('my_page')
    # ?뚯썝媛???먮쫫?먯꽌???대쫫 留ㅼ묶 ????(legacy ?꾪솚 ?꾩슜 ?몄뀡 ?쒓굅)
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
    """?몄쬆踰덊샇 諛쒖넚. POST phone ??6?먮━ 諛쒖넚, ?щ컻??30珥??쒗븳. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_raw = (request.POST.get('phone') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '?대???踰덊샇瑜??뺥솗???낅젰??二쇱꽭??'})
    from .phone_verify_service import send_code
    success, err = send_code(phone_norm)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    return JsonResponse({'ok': True})


def legacy_convert_send_code(request):
    """湲곗〈 ?뚯썝 ?꾪솚: ?대쫫+?대?????????몄쬆踰덊샇 諛쒖넚. POST name, phone. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    name = (request.POST.get('name') or '').strip()
    phone_raw = (request.POST.get('phone') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '?대???踰덊샇瑜??뺥솗???낅젰??二쇱꽭??'})
    request.session['legacy_convert_name'] = name or ''
    request.session.modified = True
    from .phone_verify_service import send_code
    success, err = send_code(phone_norm)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    return JsonResponse({'ok': True})


def phone_verify(request):
    """?몄쬆踰덊샇 寃利? POST phone, code ???깃났 ??session['verified_phone'] ?ㅼ젙. 5??珥덇낵 ???ㅽ뙣. JSON."""
    from django.http import JsonResponse
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Method not allowed'}, status=405)
    phone_raw = (request.POST.get('phone') or '').strip()
    code = (request.POST.get('code') or '').strip()
    phone_norm = _normalize_phone(phone_raw)
    if not phone_norm or len(phone_norm) < 10:
        return JsonResponse({'ok': False, 'error': '?대???踰덊샇瑜??낅젰??二쇱꽭??'})
    if not code or len(code) != 6:
        return JsonResponse({'ok': False, 'error': '?몄쬆踰덊샇 6?먮━瑜??낅젰??二쇱꽭??'})
    from .phone_verify_service import verify_code
    success, err = verify_code(phone_norm, code)
    if not success:
        return JsonResponse({'ok': False, 'error': err})
    request.session['verified_phone'] = phone_norm  # ?섏씠???쒓굅 ?????    request.session.modified = True
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
    """?レ옄留?異붿텧 (010-1234-5678 ??01012345678)."""
    if not s:
        return ''
    import re
    return re.sub(r'\D', '', str(s))


def legacy_convert_intro(request):
    """湲곗〈 ?뚯썝 ?꾪솚: ?대쫫+?대??????몄쬆踰덊샇 ?뺤씤 ??湲곗〈 ?뺣낫 議고쉶 ??濡쒓렇?????뺤떇 ?꾪솚."""
    if request.user.is_authenticated and request.user.username.startswith('legacy_'):
        return redirect('legacy_convert')
    if request.user.is_authenticated:
        return redirect('my_page')
    from urllib.parse import quote
    login_url = '/login/?next=' + quote('/account/convert/')
    return render(request, 'registration/legacy_convert_intro.html', {'login_url': login_url})


def signup_choices(request):
    """?좉퇋 ?뚯썝媛?? 移댁뭅???ㅼ씠踰??쇰컲 ?좏깮 (?꾩슂 ?쒖젏?먮쭔 ?대????몄쬆쨌?ъ뾽?먃룹쑀猷?."""
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
    """?쇰컲 ?뚯썝媛???꾨즺 ?덈궡 ?붾㈃(濡쒓렇???섏씠吏濡??대룞)."""
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
        return JsonResponse({"ok": False, "msg": "?뚯썝媛?낆? 怨??ㅽ뵂?⑸땲??"})
    username = (request.GET.get("username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "msg": "?꾩씠?붾? ?낅젰?섏꽭??"})
    existing = User.objects.filter(username=username).first()
    if existing and existing.is_active:
        return JsonResponse({"ok": False, "msg": "?대? ?ъ슜 以묒씤 ?꾩씠?붿엯?덈떎."})
    return JsonResponse({"ok": True, "msg": "?ъ슜 媛?ν븳 ?꾩씠?붿엯?덈떎."})


def find_username(request):
    """?대찓?쇰줈 媛?????ъ슜???꾩씠???? ?덈궡"""
    result = None
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip().lower()
        if email:
            users = User.objects.filter(email__iexact=email).values_list('username', flat=True)
            result = list(users) if users else []
        else:
            messages.error(request, '?대찓?쇱쓣 ?낅젰?섏꽭??')
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
            messages.warning(request, '紐낇븿 ?ㅼ젙? ?좊즺?뚯썝留??댁슜?????덉뒿?덈떎.')
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
        messages.success(request, '?좊즺?뚯썝 紐낇븿 ?뺣낫媛 ??λ릺?덉뒿?덈떎.')
        return redirect('my_page')

    my_equipments = list(
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
    total_views = sum((e.view_count or 0) for e in my_equipments)
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
                    region_label = sido or "吏??誘몄엯??
                premium_region_inquiry_alerts.append({
                    'region_label': region_label,
                    'unread_count': row.get('unread_count') or 0,
                    'room_count': row.get('room_count') or 0,
                })
        except Exception:
            premium_region_inquiry_alerts = []

    stats = {
        'my_count': len(my_equipments),
        'fav_count': fav_equipments.count() + fav_parts.count(),
        'total_views': total_views,
        'grade_label': '?좊즺?뚯썝' if profile.is_premium_active else '臾대즺?뚯썝',
    }
    is_legacy_user = request.user.username.startswith('legacy_')
    bump_status = get_user_bump_status(request.user)
    attach_equipment_bump_ui_state(my_equipments, bump_status)
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
    """?좊즺 ?뚯썝 쨌 愿묎퀬 ?덈궡 ?섏씠吏."""
    return render(request, 'billing/upgrade.html', {
        'kakao_inquiry_url': getattr(settings, 'KAKAO_INQUIRY_URL', 'https://open.kakao.com/'),
        'slot': (request.GET.get('slot') or '').strip(),
        'premium_monthly_price': PREMIUM_MONTHLY_PRICE,
        'premium_bid_switch_count': PREMIUM_BID_SWITCH_MEMBER_COUNT,
        'free_listing_limit': FREE_LISTING_LIMIT,
        'premium_listing_limit': PREMIUM_LISTING_LIMIT,
        'bump_weekly_limit': BUMP_WEEKLY_LIMIT,
    })


def terms_of_service(request):
    return render(request, "legal/terms.html")


def privacy_policy(request):
    return render(request, "legal/privacy.html")


def company_intro(request):
    """?뚯궗?뚭컻 ?섏씠吏."""
    return render(request, 'equipment/company_intro.html', {
        'company_address': '異⑹껌遺곷룄 ?뚯꽦援??뚯씠硫??뚯씠濡?313',
        'company_lat': 36.9312186590944,
        'company_lng': 127.752392155881,
        'kakao_map_js_key': _get_kakao_map_js_key(),
        'show_parts_as_section': True,
    })


@login_required(login_url='/login/')
def find_my_listings(request):
    """
    湲곗〈 留ㅻЪ(?묒꽦???놁쓬 + unclaimed_phone_norm)???꾨줈???꾪솕踰덊샇濡?李얠븘 怨꾩젙???곌껐.
    ?뚯뀥 媛?낆옄??蹂몄씤?몄쬆 ?꾨즺 ???댁슜.
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
            '?곕씫泥섍? ?깅줉?섏뼱 ?덉뼱???⑸땲?? 留덉씠?섏씠吏?먯꽌 ?꾪솕踰덊샇瑜??낅젰?????대???蹂몄씤?몄쬆???꾨즺??二쇱꽭??',
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
            messages.warning(request, '?곌껐??留ㅻЪ???좏깮??二쇱꽭??')
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
            messages.success(request, f'{claimed}嫄댁쓽 留ㅻЪ????怨꾩젙???곌껐?덉뒿?덈떎.')
        else:
            messages.warning(request, '?곌껐?????덈뒗 留ㅻЪ???놁뒿?덈떎. ?대? ?곌껐?섏뿀嫄곕굹 議곌굔??留욎? ?딆뒿?덈떎.')
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
    ?대???蹂몄씤?몄쬆 ?섏씠吏. 留ㅻЪ ?깅줉쨌?좊즺 寃곗젣 ???꾩닔.
    ?ㅼ젣 ?몄쬆 API(?ㅼ씠踰?移댁뭅???섏씠???? ?곕룞 ?꾧퉴吏???덈궡 ?섏씠吏.
    DEBUG ???test=1 濡??뚯뒪???몄쬆 媛??
    """
    if _get_profile_phone_verified(request.user):
        next_url = request.GET.get('next', '').strip()
        if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
            return redirect(next_url)
        return redirect('my_page')

    if request.method == 'POST':
        phone = (request.POST.get('phone') or '').strip()
        # DEBUG ???뚯뒪???몄쬆 (?ㅼ꽌鍮꾩뒪?먯꽌???쒓굅 ?먮뒗 鍮꾪솢?깊솕)
        next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()
        if getattr(settings, 'DEBUG', False) and request.GET.get('test'):
            try:
                profile = Profile.objects.get(user=request.user)
                profile.phone = phone or profile.phone
                profile.phone_verified = True
                profile.phone_verified_at = timezone.now()
                profile.save()
                messages.success(request, '?대????몄쬆???꾨즺?섏뿀?듬땲?? (?뚯뒪??紐⑤뱶)')
                if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
                    return redirect(next_url)
                return redirect('my_page')
            except Profile.DoesNotExist:
                Profile.objects.create(user=request.user, phone=phone or '', phone_verified=True, phone_verified_at=timezone.now())
                messages.success(request, '?대????몄쬆???꾨즺?섏뿀?듬땲?? (?뚯뒪??紐⑤뱶)')
                if next_url and url_has_allowed_host_and_scheme(next_url, request.get_host()):
                    return redirect(next_url)
                return redirect('my_page')
        messages.info(request, '蹂몄씤?몄쬆 API ?곕룞 ???댁슜 媛?ν빀?덈떎. 臾몄쓽: 愿由ъ옄.')
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
    ?닿? ?뚯썝(legacy_* ?꾩씠?? ?뺤떇 ?뚯썝 ?꾪솚: ???꾩씠?붋룹씠硫붿씪쨌鍮꾨?踰덊샇 ?ㅼ젙.
    ?뚯썝媛???몄쬆?먯꽌 ??寃쎌슦 session['verified_phone'] ??Profile.phone_verified 泥섎━.
    """
    user = request.user
    if not user.username.startswith('legacy_'):
        messages.info(request, '?대? ?뺤떇 ?뚯썝?닿굅???꾪솚 ??곸씠 ?꾨떃?덈떎.')
        return redirect('my_page')
    verified_phone = request.session.pop('verified_phone', None)
    if verified_phone:
        try:
            profile = Profile.objects.get(user=user)
            profile.phone = verified_phone  # ?섏씠???쒓굅??踰덊샇 ???            profile.phone_verified = True
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
            errors.append('??濡쒓렇???꾩씠?붾? ?낅젰?섏꽭??')
        elif new_username.startswith('legacy_'):
            errors.append('???꾩씠?붾뒗 legacy_ 濡??쒖옉?????놁뒿?덈떎.')
        elif User.objects.filter(username=new_username, is_active=True).exclude(pk=user.pk).exists():
            errors.append('?대? ?ъ슜 以묒씤 ?꾩씠?붿엯?덈떎.')
        if not email:
            errors.append('?대찓?쇱쓣 ?낅젰?섏꽭??')
        if len(password1) < 8:
            errors.append('鍮꾨?踰덊샇??8???댁긽?댁뼱???⑸땲??')
        elif password1 != password2:
            errors.append('鍮꾨?踰덊샇媛 ?쇱튂?섏? ?딆뒿?덈떎.')

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
        # 鍮꾨?踰덊샇 蹂寃????몄뀡 ?좎? (Django??鍮꾨?踰덊샇 諛붾뚮㈃ ?몄뀡 臾댄슚?뷀븷 ???덉쓬)
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        messages.success(request, '?뺤떇 ?뚯썝 ?꾪솚???꾨즺?섏뿀?듬땲?? ???꾩씠?붾줈 濡쒓렇?명빐 ?댁슜??二쇱꽭??')
        return redirect('my_page')

    return render(request, 'registration/legacy_convert.html', {})


@login_required(login_url='/login/')
def account_delete(request):
    """
    ?뚯썝 ?덊눜: 怨꾩젙 鍮꾪솢?깊솕 + 留ㅻЪ 蹂닿? ?뺤콉 ?곸슜.
    - GET: ?뺤씤 ?섏씠吏
    - POST:
      - 湲곕낯: 留ㅻЪ 6媛쒖썡 蹂닿? ???먮룞 ??젣 ?덉빟
      - ?듭뀡 ?좏깮 ?? 留ㅻЪ 利됱떆 ??젣
    """
    user = request.user

    if request.method != 'POST':
        return render(request, 'registration/account_delete_confirm.html', {'user_obj': user})

    delete_listings_now = request.POST.get('delete_listings_now') == '1'
    now_ts = timezone.now()
    purge_at = now_ts + timedelta(days=180)

    # 留ㅻЪ: 湲곕낯? 6媛쒖썡 蹂닿?, ?좏깮 ??利됱떆 ??젣
    if delete_listings_now:
        Equipment.objects.filter(author=user).delete()
    else:
        # author瑜??좎??댁빞 紐⑸줉/?쒖꽭 李멸퀬 ?곗씠?곕줈 怨꾩냽 ?몄텧?⑸땲??
        Equipment.objects.filter(author=user).update(is_sold=True)

    # 湲고? ?묒꽦 肄섑뀗痢좊뒗 利됱떆 ??젣
    Part.objects.filter(author=user).delete()
    JobPost.objects.filter(author=user).delete()
    SoilPost.objects.filter(author=user).delete()

    # ?뚯뀥 怨꾩젙 ?곌껐 ?댁젣:
    # ?덊눜 ???ш??낆? "?좉퇋媛?? ?뺤콉?대?濡?湲곗〈 ?뚯뀥 ?곌껐???딆뼱 inactive 猷⑦봽濡?鍮좎?吏 ?딄쾶 ?쒕떎.
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
    # ?뺤콉: ?덊눜 ???ш??낆? ?좉퇋?뚯썝媛?낆쑝濡?泥섎━
    # -> legacy_member_id瑜?鍮꾩썙 湲곗〈?뚯썝 ?꾪솚 ?먯? ??곸뿉???쒖쇅
    profile.legacy_member_id = None
    profile.save(update_fields=['withdrawn_at', 'listing_purge_at', 'legacy_member_id'])

    # 濡쒓렇??李⑤떒??鍮꾪솢?깊솕 泥섎━ (?곗씠??蹂닿? 紐⑹쟻)
    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=['is_active', 'password'])
    logout(request)

    if delete_listings_now:
        messages.success(request, f'"{username}" 怨꾩젙 ?덊눜 諛?留ㅻЪ 利됱떆 ??젣媛 ?꾨즺?섏뿀?듬땲??')
    else:
        messages.success(
            request,
            f'"{username}" 怨꾩젙 ?덊눜媛 ?꾨즺?섏뿀?듬땲?? ?깅줉 留ㅻЪ? ?쒖꽭 李멸퀬?⑹쑝濡?6媛쒖썡 蹂닿? ???먮룞 ??젣?⑸땲??',
        )
    return redirect('index')


def _job_list_equipment_q(equipment_key: str):
    """援ъ씤援ъ쭅 湲곗쥌 ?좏깮 ???쒕ぉ쨌?댁슜쨌?꾩슂?λ퉬 ?꾨뱶 OR 寃??"""
    if not equipment_key:
        return None
    if equipment_key == 'excavator':
        return (
            Q(equipment_type__icontains='援댁궘')
            | Q(title__icontains='援댁궘')
            | Q(content__icontains='援댁궘')
        )
    if equipment_key == 'forklift':
        return (
            Q(equipment_type__icontains='吏寃?)
            | Q(title__icontains='吏寃뚯감')
            | Q(content__icontains='吏寃뚯감')
        )
    if equipment_key == 'crane':
        return (
            Q(equipment_type__icontains='?щ젅??)
            | Q(title__icontains='?щ젅??)
            | Q(content__icontains='?щ젅??)
        )
    if equipment_key == 'site':
        return (
            Q(equipment_type__icontains='嫄댁꽕')
            | Q(equipment_type__icontains='?꾩옣')
            | Q(title__icontains='嫄댁꽕?꾩옣')
            | Q(content__icontains='嫄댁꽕?꾩옣')
            | Q(title__icontains='嫄댁꽕')
            | Q(content__icontains='嫄댁꽕')
        )
    if equipment_key == 'etc':
        return (
            Q(equipment_type__icontains='湲고?')
            | Q(title__icontains='湲고?')
            | Q(content__icontains='湲고?')
        )
    return None


JOB_EQUIPMENT_KEYS = frozenset({'excavator', 'forklift', 'crane', 'site', 'etc'})
JOB_EQUIPMENT_LABEL_MAP = {
    'excavator': '援댁궘湲?,
    'forklift': '吏寃뚯감',
    'crane': '?щ젅?멸린??,
    'site': '嫄댁꽕?꾩옣',
    'etc': '湲고?',
}
JOB_FORM_EQUIPMENT_CHOICES = [
    ('', '?좏깮 ????),
    ('excavator', '援댁궘湲?),
    ('forklift', '吏寃뚯감'),
    ('crane', '?щ젅?멸린??),
    ('site', '嫄댁꽕?꾩옣'),
    ('etc', '湲고?'),
]


def _merge_job_equipment_type(category_key: str, detail: str) -> str:
    """湲?곌린 湲곗쥌 ?좏깮 + ?곸꽭 ?낅젰 ??equipment_type ???꾨뱶?????"""
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
    """?섏젙 ?? equipment_type ??(?좏깮媛? ?곸꽭 ?띿뒪??."""
    et = (equipment_type or '').strip()
    if not et:
        return '', ''
    for key, label in JOB_EQUIPMENT_LABEL_MAP.items():
        if et.startswith(label):
            rest = et[len(label) :].strip()
            return key, rest
    return '', et


# [3] 援ъ씤援ъ쭅 愿??def job_list(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    JOB_EQUIPMENT_CHOICES = [
        ('', '?꾩껜'),
        ('excavator', '援댁궘湲?),
        ('forklift', '吏寃뚯감'),
        ('crane', '?щ젅?멸린??),
        ('site', '嫄댁꽕?꾩옣'),
        ('etc', '湲고?'),
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

    # 湲됱뿬 而щ읆 ?쒖떆 ?щ?(??嫄댁씠?쇰룄 湲됱뿬 ?낅젰???덉쑝硫??쒖떆)
    show_pay_column = qs.exclude(pay__isnull=True).exclude(pay='').exists()

    # 紐⑸줉???쒖떆 ?곗씠???뺣━: 吏??以묐났 ?쒓굅 + ??以??쒓린
    jobs = list(qs)
    for job in jobs:
        sido = (job.region_sido or '').strip()
        sigungu = (job.region_sigungu or '').strip()
        location = (job.location or '').strip()

        if sido and sigungu:
            region_line = f"{sido} 쨌 {sigungu}"
        elif sido:
            region_line = sido
        elif sigungu:
            region_line = sigungu
        else:
            region_line = location

        if location and region_line and location not in (sido, sigungu, f"{sido} {sigungu}".strip()):
            region_line = f"{region_line} 쨌 {location}" if (sido or sigungu) else location

        job.region_line = region_line or '??

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
    """援ъ씤援ъ쭅 ?곸꽭. 臾몄쓽??1:1 梨꾪똿?쇰줈留?媛??怨듦컻 ?볤? ?놁쓬)."""
    job = get_object_or_404(JobPost, pk=pk)
    return render(request, 'equipment/job_detail.html', {'job': job})


@login_required(login_url='/login/')
def job_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '援ъ씤쨌援ъ쭅 湲 ?깅줉???꾪빐 ?대???蹂몄씤?몄쬆???꾩슂?⑸땲??')
        return redirect_resp
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        writer = (request.POST.get("writer") or "?듬챸").strip()
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
            label = "援ъ쭅"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "援ъ씤"
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
            messages.error(request, "???꾩? ??援?援щ? 紐⑤몢 ?좏깮??二쇱꽭??")
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
            title = f"[{label}] ?쒕ぉ?놁쓬"

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
        writer = (request.POST.get("writer") or "?듬챸").strip()
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
            label = "援ъ쭅"
            machine = (request.POST.get("seek_machine") or "").strip()
        else:
            location = (request.POST.get("location") or "").strip()
            label = "援ъ씤"
            machine = (request.POST.get("machine") or "").strip()

        eq_cat = (request.POST.get("equipment_category") or "").strip()
        if eq_cat not in JOB_EQUIPMENT_KEYS and eq_cat != "":
            eq_cat = ""
        machine = _merge_job_equipment_type(eq_cat, machine)

        if not region_sido or not region_sigungu:
            messages.error(request, "???꾩? ??援?援щ? 紐⑤몢 ?좏깮??二쇱꽭??")
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
            title = f"[{label}] ?쒕ぉ?놁쓬"
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
    messages.success(request, "湲????젣?섏뿀?듬땲??")
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

    # 湲곗텧臾몄젣: 湲곗쥌? ??긽 ?꾩껜(紐⑤뱺 湲곗쥌??湲곗텧 ?쒖떆)
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
        'exam_equipment_tabs': [('', '?꾩껜')] + list(ExamPost.EQUIPMENT_CHOICES),
        'exam_category_tabs': [('', '?꾩껜')] + list(ExamPost.CATEGORY_CHOICES),
        'jobs_section': 'exam',
    }


def exam_video_list(request):
    """?쒗뿕?숈쁺?????좏뒠釉?API ?먮룞 ?섏쭛 (?뺣퉬?좏뒠釉?/info/ ? ?숈씪 諛⑹떇)."""
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
    post = get_object_or_404(
        ExamPost.objects.select_related('author').prefetch_related('attachments'),
        pk=pk,
    )

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.get_full_path()}")
        content = (request.POST.get('content') or '').strip()
        if content:
            ExamComment.objects.create(post=post, author=request.user, content=content)
            messages.success(request, '?볤????깅줉?섏뿀?듬땲??')
        else:
            messages.error(request, '?볤? ?댁슜???낅젰??二쇱꽭??')
        return redirect('exam_detail', pk=post.pk)

    ExamPost.objects.filter(pk=pk).update(views=F('views') + 1)
    post.refresh_from_db(fields=['views'])
    comments = post.comments.select_related('author').order_by('created_at')
    youtube_id = ''
    if post.category == 'video' and post.youtube_url:
        youtube_id = extract_youtube_id(post.youtube_url)
    attachments = list(post.attachments.all())
    return render(request, 'equipment/exam_detail.html', {
        'post': post,
        'comments': comments,
        'attachments': attachments,
        'youtube_id': youtube_id,
        'jobs_section': 'exam',
    })


@login_required(login_url='/login/')
def exam_create(request):
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '湲 ?깅줉???꾪빐 ?대???蹂몄씤?몄쬆???꾩슂?⑸땲??')
        return redirect_resp

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        content = (request.POST.get('content') or '').strip()
        category = (request.POST.get('category') or '').strip()
        equipment = (request.POST.get('equipment') or '').strip()
        youtube_url = (request.POST.get('youtube_url') or '').strip()
        upload = request.FILES.get('file')

        if not title:
            messages.error(request, '?쒕ぉ???낅젰??二쇱꽭??')
        elif category not in _EXAM_CATEGORY_KEYS:
            messages.error(request, '?좏삎???좏깮??二쇱꽭??')
        elif equipment not in _EXAM_EQUIPMENT_KEYS:
            messages.error(request, '湲곗쥌???좏깮??二쇱꽭??')
        elif category == 'video':
            if not youtube_url:
                messages.error(request, '?쒗뿕?숈쁺???좏삎? ?좏뒠釉?URL???낅젰??二쇱꽭??')
            elif not extract_youtube_id(youtube_url):
                messages.error(request, '?щ컮瑜??좏뒠釉?URL???낅젰??二쇱꽭??')
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
                messages.success(request, '湲???깅줉?섏뿀?듬땲??')
                return redirect('exam_list')
        elif not content:
            messages.error(request, '?댁슜???낅젰??二쇱꽭??')
        else:
            ExamPost.objects.create(
                author=request.user,
                title=title,
                content=content,
                category=category,
                equipment=equipment,
                file=upload,
            )
            messages.success(request, '湲???깅줉?섏뿀?듬땲??')
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
        messages.info(request, '湲 ?섏젙???꾪빐 ?대???蹂몄씤?몄쬆???꾩슂?⑸땲??')
        return redirect_resp

    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        content = (request.POST.get('content') or '').strip()
        category = (request.POST.get('category') or '').strip()
        equipment = (request.POST.get('equipment') or '').strip()
        youtube_url = (request.POST.get('youtube_url') or '').strip()
        upload = request.FILES.get('file')

        if not title:
            messages.error(request, '?쒕ぉ???낅젰??二쇱꽭??')
        elif category not in _EXAM_CATEGORY_KEYS:
            messages.error(request, '?좏삎???좏깮??二쇱꽭??')
        elif equipment not in _EXAM_EQUIPMENT_KEYS:
            messages.error(request, '湲곗쥌???좏깮??二쇱꽭??')
        elif category == 'video':
            if not youtube_url:
                messages.error(request, '?쒗뿕?숈쁺???좏삎? ?좏뒠釉?URL???낅젰??二쇱꽭??')
            elif not extract_youtube_id(youtube_url):
                messages.error(request, '?щ컮瑜??좏뒠釉?URL???낅젰??二쇱꽭??')
            else:
                post.title = title
                post.content = content
                post.category = category
                post.equipment = equipment
                post.youtube_url = youtube_url
                if upload:
                    post.file = upload
                post.save()
                messages.success(request, '湲???섏젙?섏뿀?듬땲??')
                return redirect('exam_detail', pk=post.pk)
        elif not content:
            messages.error(request, '?댁슜???낅젰??二쇱꽭??')
        else:
            post.title = title
            post.content = content
            post.category = category
            post.equipment = equipment
            post.youtube_url = youtube_url or None
            if upload:
                post.file = upload
            post.save()
            messages.success(request, '湲???섏젙?섏뿀?듬땲??')
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
        messages.success(request, '湲????젣?섏뿀?듬땲??')
        return redirect('exam_list')
    messages.warning(request, '??젣???뺤씤 ??吏꾪뻾??二쇱꽭??')
    return redirect('exam_detail', pk=pk)


# [3-1] 援댁궘湲??좏뒠釉뙿룹젙蹂?def excavator_info(request):
    """?좏뒠釉?肄섑뀗痢? 湲곗쥌 + 紐⑹쟻 ?숈떆 ?꾪꽣 (YouTube Data API + ??1??罹먯떆)."""
    import json
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
    from django.core.cache import cache

    selected_equipment_type = (request.GET.get("equipment_type", "all") or "all").strip().lower()
    selected_purpose = (request.GET.get("purpose", "excavator_maintenance") or "excavator_maintenance").strip().lower()

    equipment_tabs = [
        ("all", "?꾩껜"),
        ("excavator", "援댁궘湲?),
        ("forklift", "吏寃뚯감"),
        ("dump", "?ㅽ봽?몃윮"),
        ("loader", "?ㅽ궎濡쒕뜑"),
        ("crane", "?щ젅??),
        ("attachment", "?댄깭移섎㉫??),
    ]
    equipment_label_map = {
        "all": "?꾩껜",
        "excavator": "援댁궘湲?,
        "forklift": "吏寃뚯감",
        "dump": "?ㅽ봽?몃윮",
        "loader": "?ㅽ궎濡쒕뜑",
        "crane": "?щ젅??,
        "attachment": "?댄깭移섎㉫??,
    }
    purpose_tabs = [
        ("excavator_maintenance", "援댁궘湲??뺣퉬"),
        ("excavator_repair", "援댁궘湲??섎━"),
        ("forklift_maintenance", "吏寃뚯감 ?뺣퉬"),
        ("dump_maintenance", "?ㅽ봽?몃윮 ?뺣퉬"),
        ("excavator_inspection", "援댁궘湲??먭?"),
    ]
    purpose_keyword_map = {
        "excavator_maintenance": "援댁궘湲??뺣퉬",
        "excavator_repair": "援댁궘湲??섎━",
        "forklift_maintenance": "吏寃뚯감 ?뺣퉬",
        "dump_maintenance": "?ㅽ봽?몃윮 ?뺣퉬",
        "excavator_inspection": "援댁궘湲??먭?",
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
                "equipment_label": equipment_label_map.get(selected_equipment_type, "?꾩껜"),
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
                "channel_title": "援댁궘湲곕굹??,
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
    """湲덉쑖/?좊? 怨꾩궛湲?+ ?곷떞 ?좎껌."""
    from .claim_utils import normalize_phone_digits
    from .models import FinanceConsultation
    from .phone_verify_service import send_sms

    months_options = [12, 24, 36, 48, 60, 72]
    equipment_options = [
        "援댁궘湲?,
        "吏寃뚯감",
        "?ㅽ봽?몃윮",
        "?ㅽ궎濡쒕뜑/濡쒕뜑",
        "?щ젅??,
        "?댄깭移섎㉫??,
        "湲고? 以묒옣鍮?,
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
                errors.append("?좎껌???대쫫???낅젰??二쇱꽭??")
            if not contact:
                errors.append("?곕씫泥섎? ?낅젰??二쇱꽭??")
            if not desired_equipment:
                errors.append("?щ쭩 ?λ퉬瑜??좏깮?섍굅??吏곸젒 ?낅젰??二쇱꽭??")
            try:
                budget_manwon = int(budget_raw)
                if budget_manwon <= 0:
                    raise ValueError
            except Exception:
                budget_manwon = 0
                errors.append("援ъ엯 ?덉궛(留뚯썝)???щ컮瑜닿쾶 ?낅젰??二쇱꽭??")
            try:
                desired_months = int(desired_months_raw)
                if desired_months not in months_options:
                    raise ValueError
            except Exception:
                desired_months = 0
                errors.append("?щ쭩 ?좊?湲곌컙???좏깮??二쇱꽭??")

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
                        "[援댁궘湲곕굹?? 留ㅻЪ ?좊??곷떞 ?좎껌\n"
                        f"留ㅻЪ紐? {source_listing.model_name or source_listing.get_equipment_type_display()}\n"
                        f"?대쫫: {applicant_name}\n"
                        f"?곕씫泥? {contact}\n"
                        f"?щ쭩 ?좊?湲곌컙: {desired_months}媛쒖썡"
                    )
                else:
                    admin_msg = (
                        "[援댁궘湲곕굹?? ?좊??곷떞 ?좎껌\n"
                        f"?대쫫: {applicant_name}\n"
                        f"?곕씫泥? {contact}\n"
                        f"?щ쭩?λ퉬: {desired_equipment}\n"
                        f"?덉궛: {budget_manwon:,}??n"
                        f"?좊?湲곌컙: {desired_months}媛쒖썡"
                    )
                if admin_phone:
                    send_sms(admin_phone, admin_msg)
                messages.success(request, "?좊? ?곷떞 ?좎껌???묒닔?섏뿀?듬땲??")
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


KAKAO_MAP_JS_KEY_CACHE = "kakao_map_js_key_v1"
KAKAO_MAP_JS_KEY_CACHE_TTL = 3600


def _get_kakao_map_js_key():
    cached = cache.get(KAKAO_MAP_JS_KEY_CACHE)
    if cached is not None:
        return cached
    key = (getattr(settings, "KAKAO_MAP_JS_KEY", "") or "").strip()
    if not key:
        try:
            from allauth.socialaccount.models import SocialApp
            key = (
                SocialApp.objects.filter(provider="kakao")
                .values_list("client_id", flat=True)
                .first()
                or ""
            ).strip()
        except Exception:
            key = ""
    cache.set(KAKAO_MAP_JS_KEY_CACHE, key, KAKAO_MAP_JS_KEY_CACHE_TTL)
    return key




def _parts_as_back_url(request):
    """parts_as ??李쎌뿉???뚯븘媛??댁쟾 ?섏씠吏 (?back=)."""
    back = (request.GET.get("back") or "").strip()
    if back and url_has_allowed_host_and_scheme(back, allowed_hosts={request.get_host()}):
        return back
    return ""

def parts_as(request):
    """遺??AS ?쇳꽣 吏??+ 紐⑸줉 寃???섏씠吏."""
    region = (request.GET.get('region', '') or '').strip()
    equipment_type = (request.GET.get('equipment_type', 'all') or 'all').strip().lower()
    shop_kind = (request.GET.get('shop_kind') or request.GET.get('type') or 'all').strip().lower()
    focus_shop_id = request.GET.get('shop', '').strip()

    equipment_type_choices = [
        ("all", "?꾩껜"),
        ("excavator", "援댁궘湲?),
        ("forklift", "吏寃뚯감"),
        ("dump", "?ㅽ봽?몃윮"),
        ("loader", "?ㅽ궎濡쒕뜑쨌濡쒕뜑"),
        ("crane", "?щ젅??),
        ("attachment", "?댄깭移섎㉫??),
        ("other", "湲고?"),
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
        'parts_as_back_url': _parts_as_back_url(request),
    })


@login_required(login_url='/login/')
def parts_as_register(request):
    """?낆껜 ?먯쭊 ?깅줉(濡쒓렇??+ ?대???蹂몄씤?몄쬆 ?꾩닔)."""
    redirect_resp = _require_phone_verified_strict(request)
    if redirect_resp:
        return redirect_resp

    equipment_type_options = [
        ("excavator", "援댁궘湲?),
        ("dump", "?ㅽ봽?몃윮"),
        ("forklift", "吏寃뚯감"),
        ("crane", "?щ젅??),
        ("skidloader", "?ㅽ궎濡쒕뜑쨌濡쒕뜑"),
        ("other", "湲고?"),
    ]
    shop_kind_options = [
        ("parts", "遺?덉젏"),
        ("as", "AS?쇳꽣"),
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
            messages.error(request, "?낆껜紐? 吏?? ?곕씫泥섎뒗 ?꾩닔?낅땲??")
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
            # 以묐났 ?쒓굅 + ?낅젰 ?쒖꽌 ?좎?
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
            messages.success(request, "?낆껜 ?깅줉???꾨즺?섏뿀?듬땲??")
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
    """以묎린 ?몄텧 紐⑸줉(湲곗궗 吏곸젒?깅줉 + 移댁뭅???먮룞?섏쭛)."""
    region = (request.GET.get("region", "") or "").strip()
    equipment_type = (request.GET.get("equipment_type", "all") or "all").strip().lower()
    focus_driver_id = request.GET.get("driver", "").strip()

    equipment_type_choices = [
        ("all", "?꾩껜"),
        ("excavator", "援댁궘湲?),
        ("forklift", "吏寃뚯감"),
        ("dump", "?ㅽ봽?몃윮"),
        ("loader", "?ㅽ궎濡쒕뜑쨌濡쒕뜑"),
        ("crane", "?щ젅??),
        ("attachment", "?댄깭移섎㉫??),
        ("other", "湲고?"),
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
        "parts_as_back_url": _parts_as_back_url(request),
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
            messages.error(request, "?대쫫, ?쒕룞 吏?? ?곕씫泥섎뒗 ?꾩닔?낅땲??")
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
            messages.success(request, "以묎린 湲곗궗 ?깅줉???꾨즺?섏뿀?듬땲??")
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
        messages.success(request, "湲곗궗 ?뺣낫媛 ?섏젙?섏뿀?듬땲??")
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
        messages.success(request, "湲곗궗 ?뺣낫媛 ??젣?섏뿀?듬땲??")
        return redirect(f"{reverse('parts_as')}?type=call")
    return redirect("driver_detail", pk=pk)


def _equipment_aliases_by_key():
    return {
        "excavator": {"excavator", "援댁궘湲?, "?ы겕?덉씤"},
        "dump": {"dump", "?ㅽ봽", "?ㅽ봽?몃윮"},
        "forklift": {"forklift", "吏寃뚯감"},
        "crane": {"crane", "?щ젅??},
        "loader": {"loader", "skidloader", "?ㅽ궎濡쒕뜑", "濡쒕뜑", "?ㅽ궎濡쒕뜑쨌濡쒕뜑"},
        "attachment": {"attachment", "?댄깭移섎㉫??},
        "other": {"other", "湲고?"},
    }


def _equipment_label_by_key():
    return {
        "excavator": "援댁궘湲?,
        "forklift": "吏寃뚯감",
        "dump": "?ㅽ봽?몃윮",
        "loader": "?ㅽ궎濡쒕뜑쨌濡쒕뜑",
        "crane": "?щ젅??,
        "attachment": "?댄깭移섎㉫??,
        "other": "湲고?",
    }


def _match_equipment_type(equipment_type, equipment_tokens):
    if not equipment_type or equipment_type == "all":
        return True
    aliases = _equipment_aliases_by_key().get(equipment_type, {equipment_type})
    return any(token in aliases for token in equipment_tokens)


def _normalize_type_filter(request):
    """type(?좉퇋) ?먮뒗 center_type(湲곗〈) ?뚮씪誘명꽣瑜??듯빀."""
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
        "equipment_label": eq_label if equipment_type != "all" else (eq_label or "嫄댁꽕湲곌퀎"),
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
    """吏??紐⑸줉 留덉빱???쒕퉬?ㅼ꽱??+ ?꾨?쨌吏??쨷湲걔룻샇異??곗씠??API."""
    from rental.models import RentalCompany, RentalPost

    equipment_type = (request.GET.get("equipment_type") or "all").strip().lower()
    manufacturers = [x.strip() for x in (request.GET.get("manufacturers") or "").split(",") if x.strip()]
    ton_ranges = [x.strip() for x in (request.GET.get("ton_ranges") or "").split(",") if x.strip()]
    repair_types = [x.strip() for x in (request.GET.get("repair_types") or "").split(",") if x.strip()]
    region = (request.GET.get("region") or "").strip()
    type_filter = _normalize_type_filter(request)
    equipment_label_by_key = _equipment_label_by_key()
    region_scope = region or "?꾧뎅"

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
                "center_type": "?꾨??낆껜",
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
                "center_type": "(媛쒖씤) ?꾨?",
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
                center_type_label="?꾨?(移댁뭅??",
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
                center_type_label="吏??쨷湲?,
                equipment_label_by_key=equipment_label_by_key,
                equipment_type=equipment_type,
                region=region,
            )
            if row and row.get("lat") is not None and row.get("lng") is not None:
                if not row.get("operating_hours"):
                    row["operating_hours"] = "嫄댁꽕湲곌퀎"
                centers.append(row)

    if type_filter in ("all", "call"):
        for item in fetch_call_companies(equipment_type=equipment_type, region=region_scope):
            row = _kakao_place_to_center(
                item,
                uid_prefix="call_kakao",
                place_type="call_kakao",
                center_type_label="以묎린?몄텧",
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
                "center_type": "以묎린?몄텧 湲곗궗",
                "center_type_key": "call_driver",
                "equipment_label": driver.get_equipment_type_display(),
                "manufacturers": [],
                "ton_ranges": [],
                "repair_types": [],
                "operating_hours": "",
                "region": driver.region,
                "rating": 0,
                "review_count": 0,
                "rental_price": f"{driver.day_rate:,}?? if driver.day_rate else "?묒쓽",
                "rental_period": "",
                "detail_url": reverse("driver_detail", kwargs={"pk": driver.pk}),
                "is_personal": True,
                "title": driver.name,
                "experience": driver.get_experience_display(),
                "day_rate": driver.day_rate or 0,
            })

    return JsonResponse({"centers": centers})


def _resolve_equipment_detail_back_url(request, equipment):
    """?곸꽭 ?붾㈃?먯꽌 紐⑸줉?쇰줈 ?뚯븘媛?URL (寃?됀룻븘?걔룹젙???곹깭 ?좎?)."""
    if (request.GET.get('from') or '').strip().lower() == 'mypage' and request.user.is_authenticated:
        return reverse('my_page'), '?ㅻ줈媛湲?

    allowed_hosts = {request.get_host()}
    next_url = (request.GET.get('next') or '').strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts):
        return next_url, '紐⑸줉?쇰줈 媛湲?

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
            return back, '紐⑸줉?쇰줈 媛湲?

    detail_back_url = reverse('index')
    if equipment.equipment_type:
        detail_back_url += f'?category={equipment.equipment_type}'
    return detail_back_url, '紐⑸줉?쇰줈 媛湲?


# [4] 留ㅻЪ 愿??def attachment_ad_site_redirect(request, pk):
    """?댄깭移섎㉫?맞룻??댁뼱 愿묎퀬 移대뱶 ???대떦 留ㅻЪ ?곸꽭."""
    return redirect("equipment_detail", pk=pk)




def _bump_equipment_view_count(request, equipment_pk):
    """議고쉶??DB 媛깆떊 ???숈씪 諛⑸Ц??30遺꾩뿉 1??"""
    if request.method != "GET":
        return False
    if not request.session.session_key:
        request.session.save()
    visitor = request.session.session_key or request.META.get("REMOTE_ADDR", "anon")
    cache_key = f"eqview:{equipment_pk}:{visitor}"
    if cache.get(cache_key):
        return False
    cache.set(cache_key, 1, 1800)
    Equipment.objects.filter(pk=equipment_pk).update(view_count=F("view_count") + 1)
    return True

def equipment_detail(request, pk):
    equipment = get_object_or_404(
        Equipment.objects.select_related("author__profile").prefetch_related("images"),
        pk=pk,
    )
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
                author_name=(request.POST.get('comment_author_name') or '').strip() or '?듬챸',
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

    if _bump_equipment_view_count(request, equipment.pk):
        equipment.refresh_from_db(fields=['view_count'])

    premium_ids = set(get_premium_user_ids())
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
                    # ?꾪솕踰덊샇???レ옄媛 ?덉뼱???좏슚 (?? legacy_XXXX 媛숈? 媛?諛⑹?)
                    if author_phone and not any(ch.isdigit() for ch in author_phone):
                        author_phone = None
                author_is_dealer = getattr(profile, 'user_type', None) == 'DEALER'
                author_is_premium = getattr(profile, 'is_premium_active', False) or (
                    equipment.author_id in premium_ids
                )
                author_display = getattr(profile, 'company_name', None) or equipment.author.get_full_name() or equipment.author.username
                author_company = (getattr(profile, "company_name", None) or "").strip()
                author_youtube = (getattr(profile, "youtube_url", None) or "").strip()
            else:
                author_display = equipment.author.get_full_name() or equipment.author.username
                author_is_premium = equipment.author_id in premium_ids
        except Exception:
            author_display = equipment.author.username if equipment.author else None

    # ?묒꽦???곌껐???녿뒗 ?닿? 留ㅻЪ 蹂댁젙:
    # 媛숈? ?듭떖 ?뺣낫(紐⑤뜽/媛寃??꾩튂/?깅줉????理쒓렐 留ㅻЪ?먯꽌 ?곕씫泥섎? fallback?쇰줈 ?ъ슜
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
                        or sibling.author_id in premium_ids
                    )
                break

    # ?곸꽭 ?ъ쭊 (prefetch ?쒖슜, ?붿뒪??exists 泥댄겕 ?쒓굅濡??묐떟 ?띾룄 媛쒖꽑)
    detail_images = [
        image for image in equipment.images.all()
        if (getattr(image.image, 'name', '') or '').strip()
    ]

    # 湲덉쑖 ?덉긽 ?쒕룄 / ???⑹엯??60媛쒖썡, ??7% 媛??
    finance_limit = None
    finance_monthly_60 = None
    try:
        if equipment.listing_price and equipment.listing_price > 0:
            price = Decimal(equipment.listing_price)
            principal = (price * Decimal('0.8')).quantize(Decimal('1.'), rounding=ROUND_HALF_UP)  # 留ㅻЪ媛??80% (留뚯썝 ?⑥쐞)
            r = Decimal('0.07') / Decimal('12')  # ??7% 媛??            n = Decimal('60')
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

    # 鍮꾩듂??湲곗쥌쨌?꾩떇(짹2?? ?쒖꽭 ?듦퀎 諛?鍮꾩듂??留ㅻЪ 紐⑸줉 (?몄텧 以묒씤 寃껊쭔)
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
    similar_list = list(similar_qs.prefetch_related('images').order_by('-created_at')[:6])

    # ?곸꽭 醫뚯륫 ?덉씪(援댁궘湲??꾩슜): ?댄깭移섎㉫????댁뼱 愿묎퀬 (?뱀씤 ?낆껜留????꾩옱 鍮꾨끂異?
    left_specialist_cards = []
    if False and (equipment.equipment_type or "") == "excavator":
        left_specialist_cards = list(
            Equipment.objects.visible()
            .filter(is_sold=False)
            .filter(
                Q(equipment_type="excavator", sub_type="EXC_ATTACHMENT")
                | Q(equipment_type="excavator", sub_type="EXC_TIRE")
            )
            .filter(author__profile__attachment_tire_ad_active=True)
            .exclude(pk=equipment.pk)
            .select_related("author__profile")
            .order_by("-created_at")[:5]
        )

    # ?곸꽭 ?덉씪: 媛숈? 湲곗쥌 ?좊즺 ?꾨Ц媛 紐낇븿 (?ъ쭊쨌?뚭컻쨌?꾪솕)
    _ptype = equipment.equipment_type or None
    premium_sidebar_expert_title = PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY.get(_ptype or "", "")
    if not premium_sidebar_expert_title and _ptype:
        premium_sidebar_expert_title = (
            f"{equipment.get_equipment_type_display()} ?꾨Ц媛??
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

    # ???먮ℓ?먯쓽 ?ㅻⅨ 留ㅻЪ 2媛?誘몃━蹂닿린 (?좊즺?뚯썝쨌蹂몃Ц ?쒖쇅)
    author_other_listings = []
    if equipment.author_id:
        author_other_listings = list(
            Equipment.objects.visible()
            .filter(author_id=equipment.author_id, is_sold=False)
            .exclude(pk=equipment.pk)
            .prefetch_related('images')
            .order_by('-created_at')[:2]
        )

    # ?곗륫 ?덉씪: ?꾧뎅 遺?덉젏 A/S ?쇳꽣(吏???대룞 留곹겕??
    nearby_parts_shops = []
    if equipment.region_sido:
        nearby_parts_shops = list(
            PartsShop.objects.filter(region__icontains=equipment.region_sido)
            .order_by('region', 'name')[:6]
        )
    if not nearby_parts_shops:
        nearby_parts_shops = list(
            PartsShop.objects.order_by('region', 'name')[:6]
        )

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
        'show_parts_as_section': True,
    })


def equipment_create(request):
    from .region_choices import SIDO_CHOICES, SIGUNGU_MAP
    import json

    if not request.user.is_authenticated:
        return redirect('login')
    redirect_resp = _require_phone_verified(request)
    if redirect_resp:
        messages.info(request, '留ㅻЪ ?깅줉???꾪빐 ?대???蹂몄씤?몄쬆???꾩슂?⑸땲??')
        return redirect_resp

    from trust.services import SellerListingBlocked, is_seller_blocked

    if is_seller_blocked(request.user):
        messages.error(
            request,
            '留ㅻ꼫?먯닔 ?댁슜 ?쒗븳?쇰줈 留ㅻЪ???깅줉?????놁뒿?덈떎. 怨좉컼?쇳꽣??臾몄쓽??二쇱꽭??',
        )
        return redirect('my_page')

    if request.method == 'POST':
        form = EquipmentForm(_post_with_coalesced_weight_class(request.POST))
        if form.is_valid():
            # ?뚯썝 ?깃툒蹂????깅줉 ?쒗븳
            current_count = get_monthly_listing_count(request.user)
            monthly_limit = get_listing_monthly_limit(request.user)
            if current_count >= monthly_limit:
                if is_user_premium(request.user):
                    limit_msg = f'?좊즺 ?뚯썝? ???ъ뿉 留ㅻЪ??{PREMIUM_LISTING_LIMIT}嫄닿퉴吏留??깅줉?????덉뒿?덈떎.'
                else:
                    limit_msg = f'臾대즺 ?뚯썝? ???ъ뿉 留ㅻЪ??{FREE_LISTING_LIMIT}嫄닿퉴吏留??깅줉?????덉뒿?덈떎.'
                messages.error(
                    request,
                    limit_msg + ' ?대쾲 ???쒕룄瑜?紐⑤몢 ?ъ슜?덉뒿?덈떎. ??젣 ???ㅼ떆 ?щ젮???뱀썡 嫄댁닔???ы븿?섎ŉ, ?ㅼ쓬 ?щ????덈줈 ?깅줉?????덉뒿?덈떎.'
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
            # ?덉쐞 留ㅻЪ 諛⑹?: ?ъ쭊 理쒖냼 1???꾩닔
            image_files = request.FILES.getlist('images')
            if not image_files or len(image_files) < 1:
                form.add_error(None, ValidationError('?덉쐞 留ㅻЪ 諛⑹?瑜??꾪빐 ?ъ쭊??理쒖냼 1???댁긽 ?깅줉?댁＜?몄슂.'))
            else:
                # ?꾨같 諛⑹?: ??젣 ??7???대궡 ?숈씪 留ㅻЪ(湲곗쥌+?곗떇+媛寃? ?щ벑濡?李⑤떒
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
                        '?꾨같 諛⑹?瑜??꾪빐 ??젣 ??7???대궡?먮뒗 ?숈씪 留ㅻЪ(媛숈? 湲곗쥌쨌?곗떇쨌媛寃????ㅼ떆 ?깅줉?????놁뒿?덈떎.'
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
                # ?댁떆 怨꾩궛?쇰줈 ?쎌? 泥??대?吏 ?ъ씤??珥덇린??(??????ъ슜)
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
                    form.add_error(None, ValidationError('?깅줉 泥섎━ 以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎. ?ъ쭊 ?⑸웾/?뺤떇???뺤씤?????ㅼ떆 ?쒕룄??二쇱꽭??'))
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

    # ??湲留??섏젙 媛??(author媛 None?대㈃ ?쇰떒 留됱쓬)
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
                        '?덉쐞 留ㅻЪ 諛⑹?瑜??꾪빐 ?ъ쭊??理쒖냼 1???댁긽 ?④린嫄곕굹, ??젣??留뚰겮 ???ъ쭊??異붽???二쇱꽭??'
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
                    form.add_error(None, ValidationError('?섏젙 ???以??ㅻ쪟媛 諛쒖깮?덉뒿?덈떎. ?ъ쭊 ?⑸웾/?뺤떇???뺤씤?????ㅼ떆 ?쒕룄??二쇱꽭??'))
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
        messages.error(request, '蹂몄씤留???젣?????덉뒿?덈떎.')
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
    # ??젣 濡쒓렇 湲곕줉(?꾨같 諛⑹?: 7???대궡 ?숈씪 湲곗쥌+?곗떇+媛寃??щ벑濡??쒗븳)
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
    messages.success(request, '留ㅻЪ????젣?섏뿀?듬땲??')
    return redirect(redirect_to)


def equipment_bump(request, pk):
    """?뚯뼱?щ━湲????좊즺?뚯썝留? 理쒓렐 7??湲곗? 理쒕? 3?? 留덉씠?섏씠吏?먯꽌 ?댁슜."""
    equipment = get_object_or_404(Equipment, pk=pk)
    bump_back = reverse('my_page')

    if not request.user.is_authenticated:
        messages.info(request, '濡쒓렇?????댁슜??二쇱꽭??')
        return redirect('login')
    if equipment.author_id != request.user.id:
        messages.error(request, '蹂몄씤 留ㅻЪ留??뚯뼱?щ┫ ???덉뒿?덈떎.')
        return redirect(bump_back)
    if not is_user_premium(request.user):
        messages.error(request, '?뚯뼱?щ━湲곕뒗 ?좊즺 ?뚯썝留??댁슜?????덉뒿?덈떎.')
        return redirect(bump_back)

    status = get_user_bump_status(request.user)
    if not status['can_bump']:
        next_at = status.get('next_bump_at')
        if next_at:
            messages.warning(
                request,
                f'?뚯뼱?щ━湲곕뒗 理쒓렐 7??湲곗? 理쒕? {BUMP_WEEKLY_LIMIT}?뚮쭔 媛?ν빀?덈떎. '
                f'?ㅼ쓬 ?댁슜 媛?? {next_at.strftime("%Y-%m-%d %H:%M")}',
            )
        else:
            messages.warning(
                request,
                f'?뚯뼱?щ━湲곕뒗 理쒓렐 7??湲곗? 理쒕? {BUMP_WEEKLY_LIMIT}?뚮쭔 媛?ν빀?덈떎.',
            )
        return redirect(bump_back)

    now = timezone.now()
    from .models import EquipmentBumpLog

    equipment.last_bumped_at = now
    equipment.save(update_fields=['last_bumped_at'])
    EquipmentBumpLog.objects.create(user=request.user, equipment=equipment)
    messages.success(request, '?뚯뼱?щ━湲곌? ?꾨즺?섏뿀?듬땲?? 理쒖떊??紐⑸줉 ?곷떒???몄텧?⑸땲??')
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
    """???뚯썝???щ┛ 紐⑤뱺 留ㅻЪ 蹂닿린."""
    author_user = get_object_or_404(User, pk=user_id)
    author_profile = getattr(author_user, 'profile', None)
    author_showcase_public = bool(
        author_profile and getattr(author_profile, 'is_premium_active', False)
    )
    # "???뚯썝 留ㅻЪ ?꾩껜 蹂닿린"???좊즺 ?뚯썝留?怨듦컻
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
    featured_listings = list(base_qs.order_by('-created_at')[:3])
    total_count = len(listings)
    sold_count = sum(1 for item in listings if item.is_sold)
    avg_response_text = "鍮좊쫫"

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


# [5] 遺??愿??def part_list(request):
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
                author_name=(request.POST.get('comment_author_name') or '').strip() or '?듬챸',
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
        messages.info(request, '遺??留ㅻЪ ?깅줉???꾪빐 ?대???蹂몄씤?몄쬆???꾩슂?⑸땲??')
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

    # ??湲留??섏젙 媛??    if part.author_id != request.user.id:
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
