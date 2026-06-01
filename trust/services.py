"""판매자 매너점수 계산·조회·등록 제한."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Avg

from .models import MannerScore, SellerReport, SellerReview

User = get_user_model()

SCORE_FIELDS = (
    'score_accuracy',
    'score_response',
    'score_promise',
    'score_price',
    'score_disclosure',
)

ITEM_SCORE_LABELS = {
    'score_accuracy': 'trust_item_accuracy',
    'score_response': 'trust_item_response',
    'score_promise': 'trust_item_promise',
    'score_price': 'trust_item_price',
    'score_disclosure': 'trust_item_disclosure',
}

DEFAULT_SCORE = 70.0
DEFAULT_TIER = 'verified'


def is_trust_system_enabled() -> bool:
    return getattr(settings, 'TRUST_SYSTEM_ENABLED', False)


class SellerListingBlocked(ValidationError):
    """이용 제한(tier=blocked) 판매자 매물 등록 차단."""


def tier_from_score(score: float) -> str:
    if score >= 90:
        return 'best'
    if score >= 70:
        return 'verified'
    if score >= 50:
        return 'caution'
    return 'blocked'


def is_seller_blocked(user) -> bool:
    if not user or not getattr(user, 'pk', None):
        return False
    try:
        return user.manner_score.tier == 'blocked'
    except MannerScore.DoesNotExist:
        return False


def assert_seller_can_list(user) -> None:
    if is_seller_blocked(user):
        raise SellerListingBlocked(
            '매너점수 이용 제한으로 매물을 등록할 수 없습니다. 고객센터에 문의해 주세요.'
        )


def get_or_create_manner_score(user):
    if not user or not user.pk:
        return None
    obj, _ = MannerScore.objects.get_or_create(
        user=user,
        defaults={'score': DEFAULT_SCORE, 'tier': DEFAULT_TIER},
    )
    return obj


def recalculate_manner_score(seller) -> None:
    if not seller or not seller.pk:
        return

    reviews = SellerReview.objects.filter(seller=seller)
    total = reviews.count()
    if total == 0:
        MannerScore.objects.update_or_create(
            user=seller,
            defaults={
                'score': DEFAULT_SCORE,
                'tier': DEFAULT_TIER,
                'total_reviews': 0,
                'good_count': 0,
                'bad_count': 0,
            },
        )
        return

    good = reviews.filter(review_type='good').count()
    bad = reviews.filter(review_type='bad').count()

    avgs = reviews.filter(review_type='good').aggregate(
        a=Avg('score_accuracy'),
        r=Avg('score_response'),
        p=Avg('score_promise'),
        pr=Avg('score_price'),
        d=Avg('score_disclosure'),
    )
    avg_values = [v for v in avgs.values() if v is not None]
    if avg_values:
        item_avg = sum(avg_values) / len(avg_values)
        item_score = item_avg * 20
    else:
        item_score = DEFAULT_SCORE

    report_penalty = SellerReport.objects.filter(
        seller=seller,
        is_handled=False,
    ).count() * 3

    ratio_score = (good / total) * 100
    final = (ratio_score * 0.4) + (item_score * 0.6) - report_penalty
    final = max(0.0, min(100.0, final))
    tier = tier_from_score(final)

    MannerScore.objects.update_or_create(
        user=seller,
        defaults={
            'score': round(final, 1),
            'tier': tier,
            'total_reviews': total,
            'good_count': good,
            'bad_count': bad,
        },
    )


def get_seller_item_averages(seller) -> dict:
    """항목별 평균 1~5 (good 평가만)."""
    qs = SellerReview.objects.filter(seller=seller, review_type='good')
    if not qs.exists():
        return {field: 0.0 for field in SCORE_FIELDS}
    agg = qs.aggregate(**{f: Avg(f) for f in SCORE_FIELDS})
    return {k: round(float(agg[k] or 0), 1) for k in SCORE_FIELDS}


def buyer_can_review_equipment(user, equipment) -> bool:
    """해당 매물 채팅방 구매자(문의자)만 평가 가능."""
    if not user or not user.is_authenticated or not equipment or not equipment.author_id:
        return False
    if user.pk == equipment.author_id:
        return False
    from chat.models import ChatRoom

    return ChatRoom.objects.filter(
        equipment_id=equipment.pk,
        buyer_id=user.pk,
        seller_id=equipment.author_id,
    ).exists()


def user_reviewed_equipment(user, equipment) -> bool:
    if not user or not user.is_authenticated or not equipment:
        return False
    return SellerReview.objects.filter(
        reviewer_id=user.pk,
        equipment_id=equipment.pk,
    ).exists()


def manner_score_to_dict(ms: MannerScore | None) -> dict:
    if ms is None:
        return {
            'score': DEFAULT_SCORE,
            'tier': DEFAULT_TIER,
            'tier_label': dict(MannerScore.TIER_CHOICES).get(DEFAULT_TIER, ''),
            'total_reviews': 0,
            'good_count': 0,
            'bad_count': 0,
        }
    return {
        'score': ms.score,
        'tier': ms.tier,
        'tier_label': ms.get_tier_display(),
        'total_reviews': ms.total_reviews,
        'good_count': ms.good_count,
        'bad_count': ms.bad_count,
    }


def build_seller_trust_template_context(request, seller_user, equipment=None):
    """매물 상세·판매자 미니홈 공통 신뢰도 템플릿 컨텍스트."""
    if not is_trust_system_enabled():
        return {}

    from equipment.templatetags.i18n_extras import translate

    from trust.i18n_helpers import translated_bad_tag_choices, translated_report_choices

    if not seller_user or not seller_user.pk:
        return {}

    ms = get_or_create_manner_score(seller_user)
    item_scores = get_seller_item_averages(seller_user)
    item_bars = [
        {'field': field, 'label_key': ITEM_SCORE_LABELS[field], 'avg': item_scores.get(field, 0.0)}
        for field in SCORE_FIELDS
    ]
    lang = (getattr(request, 'session', None) and request.session.get('lang')) or 'ko'
    lang = (lang or 'ko').strip().lower()

    ctx = {
        'trust_seller_id': seller_user.pk,
        'trust_equipment_id': equipment.pk if equipment else None,
        'seller_manner_score': ms,
        'seller_item_scores': item_scores,
        'seller_item_bars': item_bars,
        'seller_manner_tier_label': translate(lang, f'trust_tier_{ms.tier}'),
        'trust_bad_tag_choices': translated_bad_tag_choices(request),
        'trust_report_choices': translated_report_choices(request),
        'trust_can_review': False,
        'trust_has_reviewed': False,
    }
    if equipment and getattr(request, 'user', None) and request.user.is_authenticated:
        ctx['trust_can_review'] = buyer_can_review_equipment(request.user, equipment)
        ctx['trust_has_reviewed'] = user_reviewed_equipment(request.user, equipment)
    return ctx


def review_to_dict(review: SellerReview) -> dict:
    return {
        'id': review.pk,
        'review_type': review.review_type,
        'comment': review.comment,
        'created_at': review.created_at.isoformat(),
        'reviewer_name': (
            review.reviewer.get_full_name() or review.reviewer.username
            if review.reviewer_id
            else '익명'
        ),
        'scores': {f: getattr(review, f) for f in SCORE_FIELDS},
        'bad_tags': list(review.bad_tags.values_list('tag', flat=True)),
    }
