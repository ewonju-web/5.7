import json

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from equipment.models import Equipment

from .models import MannerScore, ReviewBadTag, SellerReport, SellerReview
from .services import (
    ITEM_SCORE_LABELS,
    SCORE_FIELDS,
    buyer_can_review_equipment,
    get_or_create_manner_score,
    get_seller_item_averages,
    manner_score_to_dict,
    review_to_dict,
    user_reviewed_equipment,
)

User = get_user_model()


def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _json_error(message, status=400):
    return JsonResponse({'ok': False, 'error': message}, status=status)


def _parse_json_body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return None
    return request.POST


@require_GET
def seller_profile(request, user_id):
    seller = get_object_or_404(User, pk=user_id)
    ms = get_or_create_manner_score(seller)
    items = get_seller_item_averages(seller)
    item_payload = {
        ITEM_SCORE_LABELS[field]: items.get(field, 0)
        for field in SCORE_FIELDS
    }
    data = manner_score_to_dict(ms)
    data['user_id'] = seller.pk
    data['display_name'] = seller.get_full_name() or seller.username
    data['item_scores'] = item_payload
    return JsonResponse({'ok': True, 'profile': data})


@require_GET
def seller_reviews(request, user_id):
    seller = get_object_or_404(User, pk=user_id)
    review_type = (request.GET.get('type') or 'all').strip().lower()
    qs = SellerReview.objects.filter(seller=seller).select_related('reviewer').prefetch_related('bad_tags')
    if review_type in ('good', 'bad'):
        qs = qs.filter(review_type=review_type)

    paginator = Paginator(qs, 10)
    page_num = request.GET.get('page') or 1
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        page_num = 1
    page = paginator.get_page(page_num)

    return JsonResponse({
        'ok': True,
        'reviews': [review_to_dict(r) for r in page.object_list],
        'page': page.number,
        'num_pages': paginator.num_pages,
        'total': paginator.count,
    })


@require_POST
def review_create(request):
    if not request.user.is_authenticated:
        return _json_error('로그인이 필요합니다.', 401)

    data = _parse_json_body(request)
    if data is None:
        return _json_error('잘못된 요청 형식입니다.')

    equipment_id = data.get('equipment_id')
    review_type = (data.get('review_type') or '').strip()
    comment = (data.get('comment') or '').strip()[:500]

    if review_type not in ('good', 'bad'):
        return _json_error('평가 유형을 선택해 주세요.')

    equipment = get_object_or_404(Equipment, pk=equipment_id)
    if not equipment.author_id:
        return _json_error('판매자 정보가 없는 매물입니다.')

    if not buyer_can_review_equipment(request.user, equipment):
        return _json_error('이 매물에 채팅 문의한 구매자만 평가할 수 있습니다.', 403)

    if user_reviewed_equipment(request.user, equipment):
        return _json_error('이미 이 매물에 대한 평가를 남기셨습니다.', 409)

    scores = {}
    for field in SCORE_FIELDS:
        try:
            val = int(data.get(field, 0))
        except (TypeError, ValueError):
            val = 0
        scores[field] = max(0, min(5, val))

    if review_type == 'good' and any(scores[f] < 1 for f in SCORE_FIELDS):
        return _json_error('좋았어요 평가는 항목별 1~5점을 모두 선택해 주세요.')

    review = SellerReview.objects.create(
        reviewer=request.user,
        seller_id=equipment.author_id,
        equipment=equipment,
        review_type=review_type,
        comment=comment,
        **scores,
    )

    if review_type == 'bad':
        tags = data.get('bad_tags') or []
        if isinstance(tags, str):
            tags = [tags]
        valid = {c[0] for c in ReviewBadTag.TAG_CHOICES}
        for tag in tags:
            tag = (tag or '').strip()
            if tag in valid:
                ReviewBadTag.objects.get_or_create(review=review, tag=tag)

    return JsonResponse({
        'ok': True,
        'message': '평가가 등록되었습니다.',
        'review_id': review.pk,
    })


@require_POST
def report_create(request):
    data = _parse_json_body(request)
    if data is None:
        return _json_error('잘못된 요청 형식입니다.')

    seller_id = data.get('seller_id')
    equipment_id = data.get('equipment_id')
    reason = (data.get('reason') or '').strip()
    detail = (data.get('detail') or '').strip()[:2000]

    valid_reasons = {c[0] for c in SellerReport.REPORT_CHOICES}
    if reason not in valid_reasons:
        return _json_error('신고 사유를 선택해 주세요.')

    seller = get_object_or_404(User, pk=seller_id)
    equipment = None
    if equipment_id:
        equipment = get_object_or_404(Equipment, pk=equipment_id)
        if equipment.author_id and equipment.author_id != seller.pk:
            return _json_error('매물과 판매자 정보가 일치하지 않습니다.')

    if request.user.is_authenticated and request.user.pk == seller.pk:
        return _json_error('본인을 신고할 수 없습니다.', 403)

    report = SellerReport.objects.create(
        reporter=request.user if request.user.is_authenticated else None,
        reporter_ip=_client_ip(request),
        seller=seller,
        equipment=equipment,
        reason=reason,
        detail=detail,
    )

    return JsonResponse({
        'ok': True,
        'message': '신고가 접수되었습니다.',
        'report_id': report.pk,
    })
