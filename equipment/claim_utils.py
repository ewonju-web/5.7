"""미연결 매물 ↔ 본인 전화번호 매칭용 유틸."""

import re

from django.db.models import Q


def normalize_phone_digits(phone: str | None) -> str:
    """숫자만 남겨 비교 키로 사용 (하이픈·공백 제거)."""
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone).strip())


def active_member_for_phone(phone_norm: str):
    """활성 정식 회원(legacy_ 제외) 중 프로필 전화번호가 일치하는 계정."""
    if not phone_norm:
        return None
    from equipment.models import Profile

    profiles = (
        Profile.objects.filter(user__is_active=True)
        .exclude(user__username__startswith="legacy_")
        .select_related("user")
        .only("phone", "user_id", "withdrawn_at", "user__username", "user__is_active")
    )
    for profile in profiles:
        if normalize_phone_digits(profile.phone) == phone_norm:
            return profile
    return None


def legacy_member_for_phone(phone_norm: str):
    """이관(legacy_) 계정 중 전화번호가 일치하는 프로필."""
    if not phone_norm:
        return None
    from equipment.models import Profile

    legacy_ids = legacy_author_ids_for_phone(phone_norm)
    if not legacy_ids:
        return None
    return (
        Profile.objects.filter(user_id__in=legacy_ids)
        .select_related("user")
        .first()
    )


def legacy_author_ids_for_phone(phone_norm: str) -> list[int]:
    """이관(legacy_) 계정 중 프로필 전화번호가 일치하는 작성자 ID."""
    if not phone_norm:
        return []
    from equipment.models import Profile

    ids: list[int] = []
    profiles = (
        Profile.objects.filter(
            user__username__startswith="legacy_",
            user__is_active=True,
            withdrawn_at__isnull=True,
        )
        .select_related("user")
        .only("phone", "user_id", "withdrawn_at")
    )
    for profile in profiles:
        if normalize_phone_digits(profile.phone) == phone_norm:
            ids.append(profile.user_id)
    return ids


def claimable_listings_q(phone_norm: str) -> Q:
    """전화번호로 연결 가능한 매물 조건 (미연결 + legacy 이관 계정 소유)."""
    q = Q(author__isnull=True, unclaimed_phone_norm=phone_norm)
    legacy_ids = legacy_author_ids_for_phone(phone_norm)
    if legacy_ids:
        q |= Q(author_id__in=legacy_ids)
    return q


def claimable_listings_queryset(phone_norm: str):
    from equipment.models import Equipment

    if not phone_norm:
        return Equipment.objects.none()
    return Equipment.objects.filter(claimable_listings_q(phone_norm)).distinct()
