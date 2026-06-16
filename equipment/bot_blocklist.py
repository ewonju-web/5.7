"""알려진 SQLi·가입 봇(fnF 계열) 차단."""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model

from equipment.claim_utils import normalize_phone_digits
from equipment.content_security import ban_user_account, block_ip

User = get_user_model()

BOT_USERNAME_PREFIX = 'fnfOzvSR'
BOT_PHONE_DIGITS = '5556660606'
BOT_BLOCKED_IPS = frozenset({'119.50.228.24'})

_BOT_USERNAME_RE = re.compile(r'^fnfOzvSR', re.I)
_BOT_AT_USERNAME_RE = re.compile(r'^@@')


def is_blocked_bot_username(username: str) -> bool:
    value = (username or '').strip()
    if not value:
        return False
    if _BOT_USERNAME_RE.match(value):
        return True
    if _BOT_AT_USERNAME_RE.match(value):
        return True
    return False


def is_blocked_bot_phone(phone: str) -> bool:
    digits = normalize_phone_digits(phone)
    return digits == BOT_PHONE_DIGITS


def is_blocked_bot_ip(ip: str) -> bool:
    ip = (ip or '').strip()
    if not ip:
        return False
    if ip in BOT_BLOCKED_IPS:
        return True
    return False


def is_blocked_bot_user(user) -> bool:
    if not user or not getattr(user, 'pk', None):
        return False
    if is_blocked_bot_username(getattr(user, 'username', '')):
        return True
    try:
        profile = user.profile
    except Exception:
        profile = None
    if profile and is_blocked_bot_phone(getattr(profile, 'phone', '') or ''):
        return True
    return False


def block_bot_ip(ip: str, *, seconds: int = 86400 * 30) -> None:
    ip = (ip or '').strip()
    if ip:
        block_ip(ip, seconds=seconds)


def find_bot_user_queryset():
    from equipment.models import Profile

    user_ids = set(
        User.objects.filter(username__iregex=r'^(fnfOzvSR|@@)').values_list('pk', flat=True)
    )
    user_ids |= set(
        Profile.objects.filter(phone__icontains='555-666-0606').values_list('user_id', flat=True)
    )
    return User.objects.filter(pk__in=user_ids)


def purge_known_bots(*, dry_run: bool = False) -> dict:
    """알려진 봇 계정 비활성화 및 관련 IP 차단."""
    from equipment.models import VisitPageLog

    users = list(find_bot_user_queryset())
    blocked_ips: set[str] = set(BOT_BLOCKED_IPS)

    for user in users:
        for ip in VisitPageLog.objects.filter(user_id=user.pk).values_list('ip_address', flat=True):
            if ip:
                blocked_ips.add(ip)

    if dry_run:
        return {
            'users': len(users),
            'ips': len(blocked_ips),
            'usernames': [u.username for u in users],
        }

    for user in users:
        if user.is_active:
            ban_user_account(user)

    for ip in blocked_ips:
        block_bot_ip(ip)

    return {
        'users': len(users),
        'ips': len(blocked_ips),
        'usernames': [u.username for u in users],
    }
