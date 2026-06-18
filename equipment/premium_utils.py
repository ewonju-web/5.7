# 유료 회원 노출용: 첫화면 로테이션·우측 배너
import random

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.urls import reverse
from django.utils import timezone

from .models import Equipment, Profile

# 첫화면(굴삭기) 좌우 고정 명함: 총 슬롯 수·한쪽 최대 개수
PREMIUM_SIDEBAR_INDEX_TOTAL = 20
PREMIUM_SIDEBAR_INDEX_PER_SIDE = 10

# 첫화면 좌우 패널 제목 — 기종 탭별로 해당 기종 유료 매물만 노출 + 문구 분리
# 우측 「전문가들」 명함 소개글 — 한 줄 말줄임(레이아웃 깨짐 방지)
PREMIUM_EXPERT_BIO_MAX_LENGTH = 30

PREMIUM_SIDEBAR_EXPERT_TITLE_BY_CATEGORY = {
    "excavator": "굴삭기 전문가들",
    "forklift": "지게차 전문가들",
    "dump": "덤프트럭 전문가들",
    "loader": "스키로더/로더 전문가들",
    "crane": "크레인 전문가들",
}

# 명함 증명사진 미등록 시 캐릭터 아바타 색상 (배경, 아이콘)
PREMIUM_EXPERT_AVATAR_PALETTE = (
    ("#dbeafe", "#2563eb"),
    ("#dcfce7", "#16a34a"),
    ("#fce7f3", "#db2777"),
    ("#fef3c7", "#d97706"),
    ("#ede9fe", "#7c3aed"),
    ("#e0f2fe", "#0284c7"),
)


PREMIUM_USER_IDS_CACHE_KEY = "premium_user_ids_v1"
PREMIUM_USER_IDS_CACHE_TTL = 300  # 5분


def _premium_user_ids():
    cached = cache.get(PREMIUM_USER_IDS_CACHE_KEY)
    if cached is not None:
        return set(cached)
    today = timezone.now().date()
    ids = set(
        Profile.objects.filter(is_premium=True)
        .filter(
            models.Q(premium_until__isnull=True) | models.Q(premium_until__gte=today)
        )
        .values_list("user_id", flat=True)
    )
    cache.set(PREMIUM_USER_IDS_CACHE_KEY, list(ids), PREMIUM_USER_IDS_CACHE_TTL)
    return ids


def get_premium_equipment_rotation(limit=18, equipment_type: str | None = None):
    """첫 화면 로테이션용: 유료 회원 매물 중 노출 중인 것, 최신순 후 limit개 (캐러셀 슬라이드 여러 장)."""
    uids = _premium_user_ids()
    if not uids:
        return []
    qs = (
        Equipment.objects.visible()
        .filter(author_id__in=uids, is_sold=False)
    )
    if equipment_type:
        qs = qs.filter(equipment_type=equipment_type)
    return list(qs.order_by("-created_at")[:limit])


def get_premium_user_ids():
    """유료 회원(기간 유효) user id 목록."""
    return list(_premium_user_ids())


def get_premium_equipment_sidebar(limit=6, equipment_type: str | None = None):
    """우측 고정 배너용: 유료 회원 매물 명함, limit개 (로테이션과 구분해 순서 다르게)."""
    uids = _premium_user_ids()
    if not uids:
        return []
    qs = (
        Equipment.objects.visible()
        .filter(author_id__in=uids, is_sold=False)
    )
    if equipment_type:
        qs = qs.filter(equipment_type=equipment_type)
    return list(qs.order_by("?")[:limit])  # 랜덤


def pad_premium_sidebar_slots(items, limit=6):
    """우측 유료 사이드바를 항상 limit칸으로 맞춤. 부족한 칸은 None(빈 카드)."""
    items = list(items)[:limit]
    return items + [None] * (limit - len(items))


def pad_premium_expert_cards(cards, limit=10):
    """전문가 명함 슬롯 — 부족분은 None."""
    cards = list(cards)[:limit]
    return cards + [None] * (limit - len(cards))


def truncate_premium_expert_bio(text, max_length=PREMIUM_EXPERT_BIO_MAX_LENGTH):
    """명함 영역용 소개글 길이 제한."""
    s = (text or "").strip().replace("\n", " ").replace("\r", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    if len(s) <= max_length:
        return s
    return s[: max_length - 1].rstrip() + "…"


def _premium_display_name(profile):
    company = (profile.company_name or "").strip()
    if company:
        return company
    user = profile.user
    full = (user.get_full_name() or "").strip()
    if full:
        return full
    return (user.username or "").strip() or "전문가"


def _premium_expert_avatar_colors(user_id):
    bg, fg = PREMIUM_EXPERT_AVATAR_PALETTE[user_id % len(PREMIUM_EXPERT_AVATAR_PALETTE)]
    return {"avatar_bg": bg, "avatar_fg": fg}


def get_premium_expert_cards(limit=10, equipment_type=None, *, exclude_user_id=None):
    """
    유료 회원 명함 카드 — 프로필 사진·소개·전화 + 미니홈 링크.
    해당 기종 노출 매물이 1건 이상인 유료 회원만 포함.
    """
    uids = _premium_user_ids()
    if not uids:
        return []
    if exclude_user_id:
        uids = [uid for uid in uids if uid != exclude_user_id]
    profiles = (
        Profile.objects.filter(user_id__in=uids)
        .select_related("user")
        .order_by("?")
    )
    cards = []
    for profile in profiles:
        eq_qs = Equipment.objects.visible().filter(author_id=profile.user_id, is_sold=False)
        if equipment_type:
            eq_qs = eq_qs.filter(equipment_type=equipment_type)
        if not eq_qs.exists():
            continue
        photo_url = profile.profile_photo.url if profile.profile_photo else ""
        avatar_colors = _premium_expert_avatar_colors(profile.user_id)
        detail_url = reverse("author_listings", kwargs={"user_id": profile.user_id})
        if equipment_type:
            detail_url = f"{detail_url}?category={equipment_type}"
        cards.append(
            {
                "user_id": profile.user_id,
                "name": _premium_display_name(profile),
                "photo_url": photo_url,
                "avatar_bg": avatar_colors["avatar_bg"],
                "avatar_fg": avatar_colors["avatar_fg"],
                "bio": truncate_premium_expert_bio(profile.bio),
                "phone": (profile.phone or "").strip(),
                "detail_url": detail_url,
            }
        )
    random.shuffle(cards)
    return cards[:limit]


def is_user_premium(user):
    """해당 사용자가 현재 유료 회원인지."""
    if not user or not user.is_authenticated:
        return False
    try:
        profile = getattr(user, "profile", None)
        if profile and hasattr(profile, "is_premium_active"):
            return profile.is_premium_active
    except Exception:
        pass
    return False


def get_monthly_listing_count(user):
    """
    이번 달(당월)에 해당 사용자가 등록한 장비 매물 수.
    삭제한 것도 포함되며, 월 단위로만 초기화된다.
    """
    if not user or not user.is_authenticated:
        return 0
    now = timezone.now()
    return Equipment.objects.filter(
        author=user,
        created_at__year=now.year,
        created_at__month=now.month,
    ).count()


FREE_LISTING_LIMIT = 20  # 무료 회원 한 달 매물 20건까지
PREMIUM_LISTING_LIMIT = 50  # 유료 회원 한 달 매물 50건까지
# 유료 회원 이용료(원) — settings(.env)에서 조정 가능
PREMIUM_MONTHLY_PRICE = getattr(settings, "PREMIUM_MONTHLY_PRICE", 40000)  # 월
PREMIUM_YEARLY_PRICE = getattr(settings, "PREMIUM_YEARLY_PRICE", 400000)   # 연(약 2개월 무료)
PREMIUM_BID_SWITCH_MEMBER_COUNT = 20  # 이 인원 초과 시 입찰 방식 전환 예정
BUMP_WEEKS_PER_MONTH = 4  # 매물 1개당 주 1회 × 4주 = 월 한도
BUMP_LISTING_COOLDOWN_DAYS = 7  # 매물별 끌어올리기 재사용 대기(주 1회)
BUMP_WEEKLY_LIMIT = 3


def get_user_active_listing_count(user):
    """끌어올리기 한도 산정용: 현재 등록(보유) 매물 수(실시간)."""
    if not user or not user.is_authenticated:
        return 0
    return Equipment.objects.filter(author=user).count()


def get_user_monthly_bump_limit(user, listing_count=None):
    """유료 회원 월 끌어올리기 한도 = 등록 매물 수 × 4."""
    if listing_count is None:
        listing_count = get_user_active_listing_count(user)
    return listing_count * BUMP_WEEKS_PER_MONTH


def _month_start(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month_start(dt):
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(month=dt.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def get_listing_monthly_limit(user):
    """회원 유형별 월 등록 한도."""
    if is_user_premium(user):
        return PREMIUM_LISTING_LIMIT
    return FREE_LISTING_LIMIT


def get_free_listing_count(user):
    """하위 호환용 별칭."""
    return get_monthly_listing_count(user)


def get_listing_bump_cooldown(equipment, *, now=None):
    """매물별 끌어올리기 쿨다운(최근 7일 이내 사용 시 대기)."""
    from datetime import timedelta

    now = now or timezone.now()
    last = getattr(equipment, 'last_bumped_at', None)
    if not last:
        return {'on_cooldown': False, 'next_bump_at': None}
    next_at = last + timedelta(days=BUMP_LISTING_COOLDOWN_DAYS)
    if now >= next_at:
        return {'on_cooldown': False, 'next_bump_at': None}
    return {'on_cooldown': True, 'next_bump_at': next_at}


def attach_equipment_bump_ui_state(equipments, bump_status, *, now=None):
    """
    마이페이지 끌어올리기 버튼 UI 상태 부여.
    - ready: 사용 가능(활성 색)
    - cooldown: 해당 매물 7일 대기(비활성·회색)
    - monthly_exhausted: 당월 계정 한도 소진
    - hidden: 무료·판매완료 등
    """
    import math
    from datetime import timedelta

    now = now or timezone.now()
    window = timedelta(days=BUMP_LISTING_COOLDOWN_DAYS)
    is_premium = bump_status.get('is_premium', False)
    account_can = bump_status.get('can_bump', False)

    for eq in equipments:
        eq.bump_ui = 'hidden'
        eq.bump_next_at = None
        eq.bump_days_left = 0
        if not is_premium or getattr(eq, 'is_sold', False):
            continue
        last = getattr(eq, 'last_bumped_at', None)
        if last and (now - last) < window:
            eq.bump_ui = 'cooldown'
            eq.bump_next_at = last + window
            remaining_sec = (eq.bump_next_at - now).total_seconds()
            eq.bump_days_left = max(1, math.ceil(remaining_sec / 86400)) if remaining_sec > 0 else 0
            continue
        if account_can:
            eq.bump_ui = 'ready'
        else:
            eq.bump_ui = 'monthly_exhausted'


def get_user_bump_status(user):
    """유료 회원 월간 끌어올리기 잔여 횟수·다음 가능 시각(매물 수 × 4 기준)."""
    from equipment.models import EquipmentBumpLog

    status = {
        'is_premium': is_user_premium(user) if user and user.is_authenticated else False,
        'can_bump': False,
        'used': 0,
        'remaining': 0,
        'limit': 0,
        'listing_count': 0,
        'next_bump_at': None,
    }
    if not status['is_premium']:
        return status

    listing_count = get_user_active_listing_count(user)
    limit = get_user_monthly_bump_limit(user, listing_count)
    status['listing_count'] = listing_count
    status['limit'] = limit
    if limit <= 0:
        return status

    now = timezone.now()
    month_start = _month_start(now)
    used = EquipmentBumpLog.objects.filter(
        user=user,
        bumped_at__gte=month_start,
    ).count()
    status['used'] = used
    status['remaining'] = max(0, limit - used)
    if used < limit:
        status['can_bump'] = True
    else:
        status['next_bump_at'] = _next_month_start(now)
    return status
